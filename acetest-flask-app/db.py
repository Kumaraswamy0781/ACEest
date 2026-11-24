"""Portable SQLite/PostgreSQL schema and request-scoped connections."""
from pathlib import Path

from flask import current_app, g
from sqlalchemy import (
    CheckConstraint, Column, Float, ForeignKey, Index, Integer, MetaData,
    Table, Text, create_engine, event, func, insert, text,
)
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import NullPool, StaticPool

metadata = MetaData()
users = Table(
    'users', metadata,
    Column('id', Integer, primary_key=True),
    Column('username', Text, nullable=False),
    Column('password_hash', Text, nullable=False),
    Column('role', Text, nullable=False),
    CheckConstraint("role IN ('Admin','Coach','Viewer')", name='valid_user_role'),
)
Index('users_username_ci', func.lower(users.c.username), unique=True)
clients = Table(
    'clients', metadata,
    Column('id', Integer, primary_key=True),
    Column('name', Text, nullable=False),
    Column('age', Integer, nullable=False),
    Column('height', Float(53), nullable=False),
    Column('weight', Float(53), nullable=False),
    Column('program', Text, nullable=False),
    Column('generated_program', Text),
    Column('calories', Integer, nullable=False),
    Column('target_weight', Float(53)),
    Column('target_adherence', Integer),
    Column('membership_status', Text, nullable=False, server_default='Active'),
    Column('membership_end', Text),
)
Index('clients_name_ci', func.lower(clients.c.name), unique=True)
Table(
    'progress', metadata,
    Column('id', Integer, primary_key=True),
    Column('client_id', Integer, ForeignKey('clients.id'), nullable=False),
    Column('week', Text, nullable=False),
    Column('adherence', Integer, nullable=False),
    CheckConstraint('adherence BETWEEN 0 AND 100', name='valid_adherence'),
)
Table(
    'workouts', metadata,
    Column('id', Integer, primary_key=True),
    Column('client_id', Integer, ForeignKey('clients.id'), nullable=False),
    Column('date', Text, nullable=False),
    Column('workout_type', Text, nullable=False),
    Column('duration_min', Integer, nullable=False),
    Column('notes', Text, nullable=False),
    CheckConstraint('duration_min > 0', name='positive_duration'),
)
Table(
    'exercises', metadata,
    Column('id', Integer, primary_key=True),
    Column('workout_id', Integer, ForeignKey('workouts.id'), nullable=False),
    Column('name', Text, nullable=False),
    Column('sets', Integer, nullable=False),
    Column('reps', Integer, nullable=False),
    Column('weight', Float(53), nullable=False),
)
Table(
    'metrics', metadata,
    Column('id', Integer, primary_key=True),
    Column('client_id', Integer, ForeignKey('clients.id'), nullable=False),
    Column('date', Text, nullable=False),
    Column('weight', Float(53), nullable=False),
    Column('waist', Float(53)),
    Column('bodyfat', Float(53)),
)


class Database:
    """A small connection API using bound values and mapping rows."""

    def __init__(self, connection):
        self.connection = connection

    def execute(self, statement, parameters=None):
        return self.connection.execute(text(statement), parameters or {}).mappings()

    def executemany(self, statement, records):
        if records:
            return self.connection.execute(text(statement), records)
        return None

    def insert(self, table_name, values):
        table = metadata.tables[table_name]
        statement = insert(table).values(**values)
        result = self.connection.execute(statement)
        return result.inserted_primary_key[0]

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

    def close(self):
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception, traceback):
        if exception_type is None:
            self.commit()
        else:
            self.rollback()
        return False


def _sqlite_foreign_keys(connection, record):
    cursor = connection.cursor()
    cursor.execute('PRAGMA foreign_keys = ON')
    cursor.close()


def init_app(app):
    database_url = app.config.get('DATABASE_URL')
    if database_url:
        url = make_url(database_url)
        if url.drivername not in ('postgres', 'postgresql', 'postgresql+psycopg'):
            raise ValueError('ACEEST_DATABASE_URL must use PostgreSQL.')
        url = url.set(drivername='postgresql+psycopg')
        # Do not retain DB connections across Gunicorn's --preload fork.
        engine = create_engine(url, poolclass=NullPool, connect_args={'connect_timeout': 5})
    else:
        database = str(app.config['DATABASE'])
        if database != ':memory:':
            Path(database).parent.mkdir(parents=True, exist_ok=True)
        url = URL.create('sqlite', database=database)
        if database == ':memory:':
            engine = create_engine(url, poolclass=StaticPool,
                                   connect_args={'check_same_thread': False})
        else:
            engine = create_engine(url, poolclass=NullPool, connect_args={'timeout': 15})
        event.listen(engine, 'connect', _sqlite_foreign_keys)
    app.extensions['aceest_db'] = engine
    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()


def get_db():
    if 'db' not in g:
        g.db = Database(current_app.extensions['aceest_db'].connect())
    return g.db


def close_db(error=None):
    connection = g.pop('db', None)
    if connection is not None:
        connection.close()


def init_db():
    engine = current_app.extensions['aceest_db']
    with engine.begin() as connection:
        if engine.dialect.name == 'postgresql':
            # Serialize initial schema creation when multiple app workers start.
            connection.execute(text('SELECT pg_advisory_xact_lock(:key)'),
                               {'key': 202593079})
        metadata.create_all(connection)
