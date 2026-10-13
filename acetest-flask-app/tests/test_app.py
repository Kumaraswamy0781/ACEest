"""Behavior tests for the fresh final application using isolated databases."""
import sqlite3
from datetime import date, timedelta

import pytest
from werkzeug.security import generate_password_hash
from app import create_app
from db import get_db


@pytest.fixture
def app(tmp_path):
    application = create_app({'TESTING': True, 'DATABASE': str(tmp_path / 'test.sqlite'), 'SECRET_KEY': 'test-key'})
    with application.app_context():
        db = get_db()
        db.execute('INSERT INTO users (username,password_hash,role) VALUES (?,?,?)',
                   ('trainer', generate_password_hash('password123'), 'Admin'))
        db.commit()
    return application


def login(client, username='trainer', password='password123'):
    client.get('/login')
    with client.session_transaction() as session:
        token = session['csrf']
    return client.post('/login', data={'username': username, 'password': password, 'csrf_token': token})


def token(client):
    with client.session_transaction() as session:
        return session['csrf']


@pytest.fixture
def client(app):
    result = app.test_client()
    assert login(result).status_code == 302
    return result


def post(client, path, data):
    return client.post(path, json=data, headers={'X-CSRF-Token': token(client)})


def profile(**overrides):
    result = {'name': 'Asha', 'age': 30, 'height': 170, 'weight': 70, 'program': 'Fat Loss',
              'target_weight': 65, 'target_adherence': 90, 'membership_status': 'Active',
              'membership_end': (date.today() + timedelta(days=30)).isoformat()}
    result.update(overrides)
    return result


@pytest.fixture
def client_id(client):
    response = post(client, '/api/clients', profile())
    assert response.status_code == 201
    return response.json['id']


def test_health_is_public(app):
    assert app.test_client().get('/health').json == {'status': 'ok', 'version': '3.2.4'}


def test_anonymous_users_cannot_access_client_data(app):
    visitor = app.test_client()
    assert visitor.get('/').status_code == 302
    assert visitor.get('/api/clients').status_code == 401


def test_login_rejects_bad_password(app):
    visitor = app.test_client()
    response = login(visitor, password='wrong')
    assert response.status_code == 200
    assert b'Invalid username or password' in response.data
    assert visitor.get('/api/clients').status_code == 401


def test_logout_revokes_access(client):
    client.post('/logout', data={'csrf_token': token(client)})
    assert client.get('/api/clients').status_code == 401


def test_state_changes_require_csrf_token(client):
    assert client.post('/api/clients', json=profile()).status_code == 400
    assert client.get('/api/clients').json == []


@pytest.mark.parametrize('program,calories', [('Fat Loss', 1540), ('Muscle Gain', 2450), ('Beginner', 1820)])
def test_client_calories_and_bmi(client, program, calories):
    response = post(client, '/api/clients', profile(program=program))
    assert response.status_code == 201
    assert response.json['calories'] == calories
    assert response.json['bmi'] == 24.2


@pytest.mark.parametrize('overrides', [
    {'name': ''}, {'age': 0}, {'age': True}, {'height': 0}, {'weight': float('nan')},
    {'program': []}, {'target_adherence': 101}, {'membership_end': 'tomorrow'},
])
def test_invalid_client_is_not_saved(client, overrides):
    assert post(client, '/api/clients', profile(**overrides)).status_code == 400
    assert client.get('/api/clients').json == []


def test_duplicate_name_returns_conflict(client, client_id):
    assert post(client, '/api/clients', profile(name='asha')).status_code == 409
    assert len(client.get('/api/clients').json) == 1


def test_client_update_preserves_history(client, client_id):
    post(client, f'/api/clients/{client_id}/progress', {'adherence': 80})
    response = client.put(f'/api/clients/{client_id}', json=profile(weight=68), headers={'X-CSRF-Token': token(client)})
    assert response.status_code == 200
    assert response.json['calories'] == 1496
    assert len(client.get(f'/api/clients/{client_id}/progress').json) == 1


def test_expired_membership_is_computed_from_end_date(client):
    response = post(client, '/api/clients', profile(membership_end=(date.today() - timedelta(days=1)).isoformat()))
    membership = client.get(f"/api/clients/{response.json['id']}/membership").json
    assert membership['status'] == 'Expired'


def test_generated_program_uses_selected_category(client, client_id):
    response = post(client, f'/api/clients/{client_id}/generate-program', {})
    assert response.status_code == 200
    assert response.json['generated_program'] in ['Full Body HIIT', 'Circuit Training', 'Cardio + Weights']
    assert response.json['program'] == 'Fat Loss'


def test_workout_exercises_and_metrics_flow(client, client_id):
    workout = {'date': date.today().isoformat(), 'workout_type': 'Strength', 'duration_min': 45,
               'notes': 'Good session', 'exercises': [{'name': 'Squat', 'sets': 3, 'reps': 8, 'weight': 60}]}
    assert post(client, f'/api/clients/{client_id}/workouts', workout).status_code == 201
    history = client.get(f'/api/clients/{client_id}/workouts').json
    assert history[0]['exercises'][0]['name'] == 'Squat'
    assert post(client, f'/api/clients/{client_id}/metrics', {'date': date.today().isoformat(), 'weight': 69, 'waist': 80, 'bodyfat': 0}).status_code == 201
    assert client.get(f'/api/clients/{client_id}/metrics').json[0]['bodyfat'] == 0


def test_invalid_exercise_does_not_create_partial_workout(client, client_id):
    response = post(client, f'/api/clients/{client_id}/workouts', {
        'date': date.today().isoformat(), 'workout_type': 'Strength', 'duration_min': 45,
        'exercises': [{'name': 'Squat', 'sets': 0, 'reps': 8, 'weight': 60}]})
    assert response.status_code == 400
    assert client.get(f'/api/clients/{client_id}/workouts').json == []


def test_dates_and_adherence_are_validated(client, client_id):
    assert post(client, f'/api/clients/{client_id}/metrics', {'date': '2026-02-30', 'weight': 70}).status_code == 400
    assert post(client, f'/api/clients/{client_id}/progress', {'adherence': 101}).status_code == 400


def test_browser_forms_and_chart_render(client, client_id):
    assert b'Asha' in client.get('/').data
    response = client.post(f'/clients/{client_id}/action/progress', data={'csrf_token': token(client), 'adherence': 85})
    assert response.status_code == 302
    page = client.get(f'/clients/{client_id}/view')
    assert page.status_code == 200
    assert b'Weekly adherence chart for Asha' in page.data
    assert b'Download PDF report' in page.data
    assert b'85%' in page.data


def test_browser_can_create_client(client):
    response = client.post('/clients/save', data={**profile(), 'csrf_token': token(client)})
    assert response.status_code == 302
    assert client.get(response.headers['Location']).status_code == 200


def test_viewer_can_read_but_cannot_modify(app):
    with app.app_context():
        db = get_db()
        db.execute('INSERT INTO users (username,password_hash,role) VALUES (?,?,?)', ('reader', generate_password_hash('password123'), 'Viewer'))
        db.commit()
    reader = app.test_client()
    login(reader, username='reader')
    assert reader.get('/api/clients').status_code == 200
    assert post(reader, '/api/clients', profile()).status_code == 403


def test_pdf_download_is_valid_response(client, client_id):
    response = client.get(f'/clients/{client_id}/report.pdf')
    assert response.status_code == 200
    assert response.mimetype == 'application/pdf'
    assert response.data.startswith(b'%PDF-')
    assert 'attachment' in response.headers['Content-Disposition']


def test_missing_client_returns_404(client):
    assert client.get('/api/clients/999').status_code == 404
    assert client.get('/clients/999/report.pdf').status_code == 404


def test_create_user_command_stores_hashed_password(app):
    result = app.test_cli_runner().invoke(args=['create-user', 'coach', '--role', 'Coach'], input='password123\npassword123\n')
    assert result.exit_code == 0
    with app.app_context():
        user = get_db().execute('SELECT * FROM users WHERE username=?', ('coach',)).fetchone()
        assert user['role'] == 'Coach'
        assert user['password_hash'] != 'password123'
