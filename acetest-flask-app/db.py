"""Database connections and the schema for the standalone final release."""
import sqlite3
from flask import current_app, g


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
    return g.db


def close_db(error=None):
    connection = g.pop('db', None)
    if connection is not None:
        connection.close()


def init_db():
    get_db().executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY, username TEXT NOT NULL COLLATE NOCASE UNIQUE,
            password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('Admin','Coach','Viewer'))
        );
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL COLLATE NOCASE UNIQUE,
            age INTEGER NOT NULL, height REAL NOT NULL, weight REAL NOT NULL,
            program TEXT NOT NULL, generated_program TEXT,
            calories INTEGER NOT NULL, target_weight REAL, target_adherence INTEGER,
            membership_status TEXT NOT NULL DEFAULT 'Active', membership_end TEXT
        );
        CREATE TABLE IF NOT EXISTS progress (
            id INTEGER PRIMARY KEY, client_id INTEGER NOT NULL REFERENCES clients(id),
            week TEXT NOT NULL, adherence INTEGER NOT NULL CHECK(adherence BETWEEN 0 AND 100)
        );
        CREATE TABLE IF NOT EXISTS workouts (
            id INTEGER PRIMARY KEY, client_id INTEGER NOT NULL REFERENCES clients(id),
            date TEXT NOT NULL, workout_type TEXT NOT NULL,
            duration_min INTEGER NOT NULL CHECK(duration_min > 0), notes TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS exercises (
            id INTEGER PRIMARY KEY, workout_id INTEGER NOT NULL REFERENCES workouts(id),
            name TEXT NOT NULL, sets INTEGER NOT NULL, reps INTEGER NOT NULL, weight REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY, client_id INTEGER NOT NULL REFERENCES clients(id),
            date TEXT NOT NULL, weight REAL NOT NULL, waist REAL, bodyfat REAL
        );
    ''')
