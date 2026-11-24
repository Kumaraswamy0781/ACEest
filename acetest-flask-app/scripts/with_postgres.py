"""Run a command with PostgreSQL settings without printing database credentials."""
import argparse
import os
from pathlib import Path
import secrets
import subprocess
import sys

from sqlalchemy.engine import URL


def read_database_settings(path):
    values = {}
    for line in path.read_text().splitlines():
        if line.strip() and not line.lstrip().startswith('#'):
            name, separator, value = line.partition('=')
            if separator:
                values[name.strip()] = value
    required = ('POSTGRES_USER', 'POSTGRES_PASSWORD', 'POSTGRES_DB')
    if any(not values.get(name) for name in required):
        raise ValueError('Database env file must define POSTGRES_USER, POSTGRES_PASSWORD and POSTGRES_DB.')
    return values


def shared_secret(path):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(descriptor, 'w') as file:
            file.write(secrets.token_hex(32) + '\n')
    result = path.read_text().strip()
    if not result:
        raise ValueError('The shared session key file is empty.')
    return result


def main():
    config_dir = Path.home() / '.config' / 'aceest-a2'
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, default=config_dir / 'postgres.env')
    parser.add_argument('--session-key-file', type=Path, default=config_dir / 'session.key')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=15432)
    parser.add_argument('--tests', action='store_true')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command:
        parser.error('Specify a command after --.')
    try:
        settings = read_database_settings(args.env_file.expanduser())
        url = URL.create('postgresql+psycopg',
                         username=settings['POSTGRES_USER'],
                         password=settings['POSTGRES_PASSWORD'],
                         host=args.host, port=args.port, database=settings['POSTGRES_DB'])
        environment = os.environ.copy()
        if args.tests:
            # Importing app.py must not initialize deployment tables during tests.
            environment.pop('ACEEST_DATABASE_URL', None)
            environment['ACEEST_TEST_DATABASE_URL'] = url.render_as_string(hide_password=False)
        else:
            environment['ACEEST_DATABASE_URL'] = url.render_as_string(hide_password=False)
            if not environment.get('ACEEST_SECRET_KEY', '').strip():
                environment['ACEEST_SECRET_KEY'] = shared_secret(args.session_key_file.expanduser())
        return subprocess.run(command, env=environment, check=False).returncode
    except (OSError, ValueError) as error:
        # Do not include connection URLs, environment contents or credentials.
        print('PostgreSQL setup failed. Check the env file, session key file and command. '
              f'Error type: {type(error).__name__}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
