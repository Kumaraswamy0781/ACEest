"""Credential handling and environment propagation for the PostgreSQL helper."""
import hashlib
import importlib.util
from pathlib import Path
import stat
from types import SimpleNamespace

import pytest
from sqlalchemy.engine import make_url

spec = importlib.util.spec_from_file_location(
    'postgres_launcher', Path(__file__).resolve().parents[1] / 'scripts' / 'with_postgres.py'
)
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


@pytest.fixture
def database_env(tmp_path):
    path = tmp_path / 'postgres.env'
    path.write_text('# Development database\n\nPOSTGRES_USER=trainer\n'
                    'POSTGRES_DB=aceest\nPOSTGRES_PASSWORD=synthetic=pass:#%\n')
    return path


def invoke(monkeypatch, arguments, returncode=0):
    seen = {}

    def run(command, *, env, check):
        seen['command'] = command
        seen['check'] = check
        for name in ('ACEEST_DATABASE_URL', 'ACEEST_TEST_DATABASE_URL'):
            seen[name] = make_url(env[name]) if env.get(name) else None
        key = env.get('ACEEST_SECRET_KEY', '')
        seen['secret_digest'] = hashlib.sha256(key.encode()).hexdigest()
        return SimpleNamespace(returncode=returncode)

    monkeypatch.setattr(launcher, 'subprocess', SimpleNamespace(run=run))
    monkeypatch.setattr(launcher.sys, 'argv', ['with_postgres.py', *arguments])
    result = launcher.main()
    return result, seen


def test_env_file_keeps_equals_and_special_characters(database_env):
    settings = launcher.read_database_settings(database_env)
    assert settings['POSTGRES_USER'] == 'trainer'
    assert settings['POSTGRES_PASSWORD'] == 'synthetic=pass:#%'


def test_env_file_requires_password(tmp_path):
    path = tmp_path / 'missing.env'
    path.write_text('POSTGRES_USER=trainer\nPOSTGRES_DB=aceest\n')
    with pytest.raises(ValueError, match='POSTGRES_PASSWORD'):
        launcher.read_database_settings(path)


def test_shared_secret_is_private_and_reused(tmp_path):
    path = tmp_path / 'private' / 'session.key'
    first = launcher.shared_secret(path)
    assert len(first) == 64
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert launcher.shared_secret(path) == first


def test_test_mode_uses_only_test_url(database_env, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv('ACEEST_DATABASE_URL', 'postgresql://localhost/deployment')
    key = tmp_path / 'session.key'
    result, seen = invoke(monkeypatch, [
        '--env-file', str(database_env), '--session-key-file', str(key),
        '--tests', '--host', 'db.example', '--port', '5432',
        '--', 'python', '-m', 'pytest', '-q', '--postgres',
    ])
    assert result == 0
    assert seen['ACEEST_DATABASE_URL'] is None
    url = seen['ACEEST_TEST_DATABASE_URL']
    assert (url.host, url.port, url.database) == ('db.example', 5432, 'aceest')
    assert url.password == 'synthetic=pass:#%'
    assert seen['command'] == ['python', '-m', 'pytest', '-q', '--postgres']
    assert not key.exists()
    output = capsys.readouterr()
    assert 'synthetic=pass:#%' not in output.out + output.err


def test_application_mode_reuses_key_and_child_exit_code(database_env, tmp_path, monkeypatch):
    monkeypatch.delenv('ACEEST_SECRET_KEY', raising=False)
    key = tmp_path / 'session.key'
    result, seen = invoke(monkeypatch, [
        '--env-file', str(database_env), '--session-key-file', str(key),
        '--', 'python', '-m', 'flask', '--app', 'app', 'run',
    ], returncode=7)
    assert result == 7
    assert seen['ACEEST_DATABASE_URL'].drivername == 'postgresql+psycopg'
    assert seen['secret_digest'] == hashlib.sha256(key.read_text().strip().encode()).hexdigest()
    original = key.read_text()
    result, again = invoke(monkeypatch, [
        '--env-file', str(database_env), '--session-key-file', str(key),
        '--', 'python', '-m', 'flask', '--app', 'app', 'run',
    ])
    assert result == 0
    assert key.read_text() == original
    assert again['secret_digest'] == seen['secret_digest']


def test_application_mode_respects_explicit_secret(database_env, tmp_path, monkeypatch):
    monkeypatch.setenv('ACEEST_SECRET_KEY', 'explicit-test-session-key')
    key = tmp_path / 'unused-session.key'
    result, seen = invoke(monkeypatch, [
        '--env-file', str(database_env), '--session-key-file', str(key), '--', 'example-command',
    ])
    assert result == 0
    assert not key.exists()
    assert seen['secret_digest'] == hashlib.sha256(b'explicit-test-session-key').hexdigest()


def test_missing_env_file_fails_without_starting_command(tmp_path, monkeypatch, capsys):
    result, seen = invoke(monkeypatch, [
        '--env-file', str(tmp_path / 'absent.env'), '--', 'example-command',
    ])
    assert result == 1
    assert seen == {}
    assert 'FileNotFoundError' in capsys.readouterr().err
