"""Shared records, sessions, transaction safety and database configuration."""
import sqlite3

import pytest

from app import create_app
from db import IntegrityError, get_db


def build_app(database_config, **overrides):
    config = {'TESTING': True, **database_config, 'SECRET_KEY': 'shared-test-key'}
    config.update(overrides)
    return create_app(config)


def sign_in(client, username='trainer'):
    client.get('/login')
    with client.session_transaction() as session:
        csrf = session['csrf']
    response = client.post('/login', data={
        'username': username, 'password': 'password123', 'csrf_token': csrf,
    })
    assert response.status_code == 302


def test_two_instances_share_records_and_login_session(database_config):
    first = build_app(database_config, INSTANCE_ID='blue')
    result = first.test_cli_runner().invoke(
        args=['create-user', 'Trainer'], input='password123\npassword123\n',
    )
    assert result.exit_code == 0
    client = first.test_client()
    sign_in(client, username='tRaInEr')
    csrf = client.get('/api/session').json['csrf_token']
    response = client.post('/api/clients', json={
        'name': 'Shared Client', 'age': 30, 'height': 170,
        'weight': 70, 'program': 'Fat Loss',
    }, headers={'X-CSRF-Token': csrf})
    assert response.status_code == 201
    client_id = response.json['id']

    # Starting another instance must preserve users and existing records.
    second = build_app(database_config, INSTANCE_ID='green')
    visitor = second.test_client()
    cookie = client.get_cookie(first.config['SESSION_COOKIE_NAME'])
    visitor.set_cookie(second.config['SESSION_COOKIE_NAME'], cookie.value)

    assert visitor.get('/api/session').json['username'] == 'Trainer'
    assert visitor.get(f'/api/clients/{client_id}').json['name'] == 'Shared Client'
    updated = visitor.put(f'/api/clients/{client_id}', json={
        'name': 'Shared Client', 'age': 30, 'height': 170,
        'weight': 68, 'program': 'Fat Loss',
    }, headers={'X-CSRF-Token': csrf})
    assert updated.status_code == 200
    assert client.get(f'/api/clients/{client_id}').json['weight'] == 68


def test_different_session_key_rejects_another_instances_cookie(database_config):
    first = build_app(database_config)
    result = first.test_cli_runner().invoke(
        args=['create-user', 'trainer'], input='password123\npassword123\n',
    )
    assert result.exit_code == 0
    client = first.test_client()
    sign_in(client)
    second = build_app(database_config, SECRET_KEY='different-test-key')
    visitor = second.test_client()
    cookie = client.get_cookie(first.config['SESSION_COOKIE_NAME'])
    visitor.set_cookie(second.config['SESSION_COOKIE_NAME'], cookie.value)

    assert visitor.get('/api/clients').status_code == 401


def test_failed_transaction_rolls_back_all_writes(database_config):
    application = build_app(database_config)
    with application.app_context():
        db = get_db()
        with pytest.raises(IntegrityError):
            with db:
                db.execute('INSERT INTO users (username,password_hash,role) VALUES (:name,:hash,:role)',
                           {'name': 'valid-user', 'hash': 'placeholder', 'role': 'Admin'})
                db.execute('INSERT INTO users (username,password_hash,role) VALUES (:name,:hash,:role)',
                           {'name': 'invalid-user', 'hash': 'placeholder', 'role': 'Invalid'})
        assert list(db.execute('SELECT id FROM users')) == []


def test_database_enforces_foreign_keys(database_config):
    application = build_app(database_config)
    with application.app_context():
        db = get_db()
        with pytest.raises(IntegrityError):
            with db:
                db.execute('INSERT INTO progress (client_id,week,adherence) VALUES (:id,:week,:value)',
                           {'id': 999, 'week': '2026-W01', 'value': 80})
        assert list(db.execute('SELECT id FROM progress')) == []


def test_request_connection_closes_at_context_end(database_config):
    application = build_app(database_config)
    with application.app_context():
        db = get_db()
        assert db.connection.closed is False
    assert db.connection.closed is True


def test_postgres_requires_an_explicit_shared_secret():
    with pytest.raises(ValueError, match='ACEEST_SECRET_KEY'):
        create_app({'TESTING': True, 'DATABASE_URL': 'postgresql://localhost/unused',
                    'SECRET_KEY': None})


def test_explicit_sqlite_test_config_ignores_deployment_url(tmp_path, monkeypatch):
    monkeypatch.setenv('ACEEST_DATABASE_URL', 'postgresql://localhost/unreachable')
    application = create_app({'TESTING': True, 'DATABASE': str(tmp_path / 'test.sqlite'),
                              'SECRET_KEY': 'test-key'})
    assert application.extensions['aceest_db'].dialect.name == 'sqlite'
    assert application.test_client().get('/health').status_code == 200


def test_unsupported_database_url_fails_without_falling_back():
    with pytest.raises(ValueError, match='must use PostgreSQL'):
        create_app({'TESTING': True, 'DATABASE_URL': 'mysql://localhost/unused',
                    'SECRET_KEY': 'test-key'})


def test_legacy_sqlite_accounts_are_preserved(tmp_path):
    path = tmp_path / 'legacy.sqlite'
    from werkzeug.security import generate_password_hash
    with sqlite3.connect(path) as connection:
        connection.execute('''CREATE TABLE users (
            id INTEGER PRIMARY KEY, username TEXT NOT NULL COLLATE NOCASE UNIQUE,
            password_hash TEXT NOT NULL, role TEXT NOT NULL
        )''')
        connection.execute('INSERT INTO users VALUES (1,?,?,?)',
                           ('trainer', generate_password_hash('password123'), 'Admin'))
    application = create_app({'TESTING': True, 'DATABASE': str(path), 'SECRET_KEY': 'test-key'})
    client = application.test_client()
    sign_in(client)
    assert client.get('/api/session').json['username'] == 'trainer'
