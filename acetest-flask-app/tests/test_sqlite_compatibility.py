"""Regression coverage for SQLite runtimes without INSERT RETURNING."""
import sqlite3

from sqlalchemy import event

from app import create_app
from db import get_db


def test_generated_ids_work_without_sqlite_returning(tmp_path):
    application = create_app({
        'TESTING': True,
        'DATABASE': str(tmp_path / 'older-sqlite.sqlite'),
        'SECRET_KEY': 'compatibility-test-key',
    })
    engine = application.extensions['aceest_db']
    engine.dialect.insert_returning = False

    @event.listens_for(engine, 'before_cursor_execute')
    def reject_returning(connection, cursor, statement, parameters, context, many):
        if context.isinsert and 'RETURNING' in statement.upper():
            raise sqlite3.OperationalError('near "RETURNING": syntax error')

    with application.app_context():
        db = get_db()
        with db:
            first = db.insert('users', {
                'username': 'first',
                'password_hash': 'placeholder',
                'role': 'Admin',
            })
            second = db.insert('users', {
                'username': 'second',
                'password_hash': 'placeholder',
                'role': 'Coach',
            })

        assert isinstance(first, int) and first > 0
        assert second > first
        assert db.execute(
            'SELECT username FROM users WHERE id=:id',
            {'id': first},
        ).fetchone()['username'] == 'first'
        assert db.execute(
            'SELECT username FROM users WHERE id=:id',
            {'id': second},
        ).fetchone()['username'] == 'second'
