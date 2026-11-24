"""Run behavior tests on SQLite, or on SQLite and isolated PostgreSQL schemas."""
import os
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool
from sqlalchemy.schema import CreateSchema, DropSchema


def pytest_addoption(parser):
    parser.addoption('--postgres', action='store_true',
                     help='Also run database behavior tests against ACEEST_TEST_DATABASE_URL.')


def pytest_configure(config):
    if config.getoption('--postgres') and not os.environ.get('ACEEST_TEST_DATABASE_URL'):
        raise pytest.UsageError('--postgres requires ACEEST_TEST_DATABASE_URL.')
    # Protect deployment settings before collection imports app.py and its WSGI app.
    config._aceest_import_db = TemporaryDirectory(prefix='aceest-pytest-import-')
    config._aceest_environment = pytest.MonkeyPatch()
    config._aceest_environment.delenv('ACEEST_DATABASE_URL', raising=False)
    config._aceest_environment.setenv(
        'ACEEST_DATABASE', str(Path(config._aceest_import_db.name) / 'import.sqlite')
    )


def pytest_unconfigure(config):
    if hasattr(config, '_aceest_environment'):
        config._aceest_environment.undo()
        config._aceest_import_db.cleanup()


def pytest_generate_tests(metafunc):
    if 'database_config' in metafunc.fixturenames:
        backends = ['sqlite', 'postgres'] if metafunc.config.getoption('--postgres') else ['sqlite']
        metafunc.parametrize('database_config', backends, indirect=True)


@pytest.fixture
def database_config(request, tmp_path):
    if request.param == 'sqlite':
        yield {'DATABASE': str(tmp_path / 'test.sqlite'), 'DATABASE_URL': None}
        return

    url = make_url(os.environ['ACEEST_TEST_DATABASE_URL']).set(drivername='postgresql+psycopg')
    admin = create_engine(url, poolclass=NullPool, connect_args={'connect_timeout': 5})
    schema = 'aceest_test_' + uuid.uuid4().hex
    try:
        with admin.begin() as connection:
            connection.execute(CreateSchema(schema))
        isolated = url.update_query_dict({'options': f'-csearch_path={schema}'})
        yield {'DATABASE_URL': isolated}  # URL repr masks the password in pytest failures.
    finally:
        with admin.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        admin.dispose()
