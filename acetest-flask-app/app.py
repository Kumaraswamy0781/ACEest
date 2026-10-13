"""Standalone ACEest Flask final version 3.2.4."""
import os
from pathlib import Path
import secrets
import sqlite3
from datetime import date
from io import BytesIO

import click
from flask import Flask, abort, flash, g, jsonify, redirect, render_template, request, send_file, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from db import close_db, get_db, init_db
from services import (PROGRAMS, MissingClient, ValidationError, add_record, generate_program,
                      get_client, history, save_client)


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(DATABASE=os.environ.get('ACEEST_DATABASE', str(Path(app.instance_path) / 'aceest.sqlite')),
                            SECRET_KEY=os.environ.get('ACEEST_SECRET_KEY'), SESSION_COOKIE_HTTPONLY=True,
                            SESSION_COOKIE_SAMESITE='Lax', MAX_CONTENT_LENGTH=1024 * 1024)
    if test_config:
        app.config.update(test_config)
    Path(app.config['DATABASE']).parent.mkdir(parents=True, exist_ok=True)
    if not app.config['SECRET_KEY']:
        Path(app.instance_path).mkdir(parents=True, exist_ok=True)
        secret_path = Path(app.instance_path) / '.session-key'
        try:
            descriptor = os.open(secret_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, 'w') as file:
                file.write(secrets.token_hex(32))
        except FileExistsError:
            pass
        app.config['SECRET_KEY'] = secret_path.read_text()
    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()

    def is_api():
        return request.path.startswith('/api/') or request.is_json or request.path in ('/clients', '/programs')

    def csrf_token():
        if 'csrf' not in session:
            session['csrf'] = secrets.token_hex(32)
        return session['csrf']
    app.jinja_env.globals['csrf_token'] = csrf_token

    @app.before_request
    def authenticate():
        g.user = None
        if session.get('user_id'):
            g.user = get_db().execute('SELECT id,username,role FROM users WHERE id=?', (session['user_id'],)).fetchone()
        if request.endpoint in ('static', 'health', 'programs', 'login'):
            if request.endpoint == 'login' and request.method == 'POST':
                check_csrf()
            return
        if g.user is None:
            if is_api():
                return jsonify(error='Authentication required.'), 401
            return redirect(url_for('login'))
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            if g.user['role'] == 'Viewer' and request.endpoint != 'logout':
                abort(403)
            check_csrf()

    def check_csrf():
        token = request.headers.get('X-CSRF-Token') or request.form.get('csrf_token', '')
        if not token or not secrets.compare_digest(token.encode('utf-8'), session.get('csrf', '').encode('utf-8')):
            abort(400, description='Invalid CSRF token. Reload the page or fetch /api/session.')

    @app.errorhandler(ValidationError)
    def validation_error(error):
        if is_api():
            return jsonify(error=str(error)), 400
        return render_template('error.html', message=str(error)), 400

    @app.errorhandler(MissingClient)
    def missing_client(error):
        if is_api():
            return jsonify(error=str(error)), 404
        return render_template('error.html', message=str(error)), 404

    @app.errorhandler(sqlite3.IntegrityError)
    def duplicate(error):
        message = 'A client with that name already exists.'
        if is_api():
            return jsonify(error=message), 409
        return render_template('error.html', message=message), 409

    @app.cli.command('create-user')
    @click.argument('username')
    @click.option('--role', type=click.Choice(['Admin', 'Coach', 'Viewer']), default='Admin')
    @click.password_option()
    def create_user(username, role, password):
        """Create a login account. Passwords are stored as hashes."""
        if not username.strip() or len(password) < 8:
            raise click.ClickException('Use a username and a password of at least 8 characters.')
        db = get_db()
        try:
            with db:
                db.execute('INSERT INTO users (username,password_hash,role) VALUES (?,?,?)',
                           (username.strip(), generate_password_hash(password), role))
        except sqlite3.IntegrityError:
            raise click.ClickException('That username already exists.')
        click.echo(f'Created {role} account {username}.')

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        error = None
        if request.method == 'POST':
            user = get_db().execute('SELECT * FROM users WHERE username=?', (request.form.get('username', '').strip(),)).fetchone()
            if user and check_password_hash(user['password_hash'], request.form.get('password', '')):
                session.clear()
                session['user_id'] = user['id']
                csrf_token()
                return redirect(url_for('dashboard'))
            error = 'Invalid username or password.'
        return render_template('login.html', error=error)

    @app.post('/logout')
    def logout():
        session.clear()
        return redirect(url_for('login'))

    @app.get('/health')
    def health():
        return jsonify(status='ok', version='3.2.4')

    @app.get('/api/programs')
    @app.get('/programs')
    def programs():
        return jsonify(PROGRAMS)

    @app.get('/api/session')
    def api_session():
        return jsonify(username=g.user['username'], role=g.user['role'], csrf_token=csrf_token())

    @app.get('/')
    def dashboard():
        clients = [get_client(row['id']) for row in get_db().execute('SELECT id FROM clients ORDER BY name')]
        return render_template('dashboard.html', clients=clients, programs=PROGRAMS)

    @app.post('/clients/save')
    def browser_save_client():
        client_id = request.form.get('client_id', type=int)
        client = save_client(request.form, client_id)
        flash('Client profile saved.')
        return redirect(url_for('client_view', client_id=client['id']))

    @app.get('/clients/<int:client_id>/view')
    def client_view(client_id):
        client = get_client(client_id)
        progress = history(client_id, 'progress')
        chart = [{'x': 30 + i * 540 / max(len(progress) - 1, 1), 'y': 170 - row['adherence'] * 1.4,
                  'label': row['week'], 'value': row['adherence']} for i, row in enumerate(progress)]
        return render_template('client.html', client=client, progress=progress, chart=chart,
                               workouts=history(client_id, 'workouts'), metrics=history(client_id, 'metrics'),
                               programs=PROGRAMS, today=date.today().isoformat())

    @app.post('/clients/<int:client_id>/action/<action>')
    def client_action(client_id, action):
        if action == 'generate':
            generate_program(client_id)
        elif action in ('progress', 'workouts', 'metrics'):
            data = request.form.to_dict()
            if action == 'workouts':
                exercises = []
                for line in data.pop('exercises', '').splitlines():
                    if not line.strip():
                        continue
                    parts = [part.strip() for part in line.split(',')]
                    if len(parts) != 4:
                        raise ValidationError('Each exercise line needs name, sets, reps, weight.')
                    exercises.append(dict(zip(('name', 'sets', 'reps', 'weight'), parts)))
                data['exercises'] = exercises
            add_record(client_id, action, data)
        else:
            abort(404)
        flash('Saved successfully.')
        return redirect(url_for('client_view', client_id=client_id))

    @app.get('/clients/<int:client_id>/report.pdf')
    def report(client_id):
        from reports import client_pdf
        return send_file(BytesIO(client_pdf(client_id)), mimetype='application/pdf', as_attachment=True,
                         download_name=f'client-{client_id}-report.pdf')

    def payload():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise ValidationError('A JSON object is required.')
        return data

    @app.route('/api/clients', methods=['GET', 'POST'])
    @app.route('/clients', methods=['GET', 'POST'])
    def clients_api():
        if request.method == 'POST':
            return jsonify(save_client(payload())), 201
        return jsonify([get_client(row['id']) for row in get_db().execute('SELECT id FROM clients ORDER BY name')])

    @app.route('/api/clients/<int:client_id>', methods=['GET', 'PUT'])
    def client_api(client_id):
        return jsonify(save_client(payload(), client_id) if request.method == 'PUT' else get_client(client_id))

    @app.route('/api/clients/<int:client_id>/<kind>', methods=['GET', 'POST'])
    def records_api(client_id, kind):
        if kind not in ('progress', 'workouts', 'metrics'):
            abort(404)
        if request.method == 'POST':
            return jsonify(add_record(client_id, kind, payload())), 201
        return jsonify(history(client_id, kind))

    @app.post('/api/clients/<int:client_id>/generate-program')
    def generate_api(client_id):
        return jsonify(generate_program(client_id))

    @app.get('/api/clients/<int:client_id>/membership')
    def membership_api(client_id):
        client = get_client(client_id)
        return jsonify(status=client['effective_membership_status'], end=client['membership_end'])

    return app


app = create_app()

if __name__ == '__main__':
    app.run()
