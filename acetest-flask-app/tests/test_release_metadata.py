"""Release metadata behavior with isolated databases and environment variables."""
import pytest

import app as app_module


@pytest.fixture
def make_app(tmp_path, monkeypatch):
    for name in (
        'ACEEST_APP_VERSION', 'ACEEST_BUILD_SHA', 'ACEEST_INSTANCE_ID', 'HOSTNAME'
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(app_module.socket, 'gethostname', lambda: 'test-host')
    count = 0

    def factory(**overrides):
        nonlocal count
        count += 1
        config = {
            'TESTING': True,
            'DATABASE': str(tmp_path / f'metadata-{count}.sqlite'),
            'SECRET_KEY': 'metadata-test-key',
        }
        config.update(overrides)
        return app_module.create_app(config)

    return factory


def test_health_returns_default_release_without_login(make_app):
    response = make_app().test_client().get('/health')

    assert response.status_code == 200
    assert response.mimetype == 'application/json'
    assert response.json == {
        'status': 'ok',
        'version': '3.4.0',
        'build_sha': 'unknown',
        'instance': 'test-host',
    }


def test_environment_configures_release_metadata(make_app, monkeypatch):
    monkeypatch.setenv('ACEEST_APP_VERSION', '3.3.1')
    monkeypatch.setenv('ACEEST_BUILD_SHA', 'abc1234')
    monkeypatch.setenv('ACEEST_INSTANCE_ID', 'aceest-green-1')
    monkeypatch.setenv('HOSTNAME', 'fallback-host')

    response = make_app().test_client().get('/health')

    assert response.json == {
        'status': 'ok',
        'version': '3.3.1',
        'build_sha': 'abc1234',
        'instance': 'aceest-green-1',
    }


def test_explicit_config_overrides_environment(make_app, monkeypatch):
    monkeypatch.setenv('ACEEST_APP_VERSION', 'from-environment')
    monkeypatch.setenv('ACEEST_BUILD_SHA', 'environment-sha')
    monkeypatch.setenv('ACEEST_INSTANCE_ID', 'environment-instance')

    application = make_app(
        APP_VERSION='test-release',
        BUILD_SHA='test-sha',
        INSTANCE_ID='test-instance',
    )

    assert application.test_client().get('/health').json == {
        'status': 'ok',
        'version': 'test-release',
        'build_sha': 'test-sha',
        'instance': 'test-instance',
    }


def test_separate_apps_keep_their_startup_metadata(make_app, monkeypatch):
    monkeypatch.setenv('ACEEST_APP_VERSION', '3.3.0')
    monkeypatch.setenv('ACEEST_BUILD_SHA', 'stable-sha')
    monkeypatch.setenv('ACEEST_INSTANCE_ID', 'blue')
    stable = make_app()

    monkeypatch.setenv('ACEEST_APP_VERSION', '3.3.1')
    monkeypatch.setenv('ACEEST_BUILD_SHA', 'candidate-sha')
    monkeypatch.setenv('ACEEST_INSTANCE_ID', 'green')
    candidate = make_app()

    assert stable.test_client().get('/health').json == {
        'status': 'ok', 'version': '3.3.0',
        'build_sha': 'stable-sha', 'instance': 'blue',
    }
    assert candidate.test_client().get('/health').json == {
        'status': 'ok', 'version': '3.3.1',
        'build_sha': 'candidate-sha', 'instance': 'green',
    }


def test_instance_defaults_to_hostname_environment(make_app, monkeypatch):
    monkeypatch.setenv('HOSTNAME', 'aceest-pod-7c9')

    response = make_app().test_client().get('/health')

    assert response.json['instance'] == 'aceest-pod-7c9'


@pytest.mark.parametrize('value', ['', '   '])
def test_empty_metadata_uses_defaults(make_app, monkeypatch, value):
    for name in (
        'ACEEST_APP_VERSION', 'ACEEST_BUILD_SHA', 'ACEEST_INSTANCE_ID', 'HOSTNAME'
    ):
        monkeypatch.setenv(name, value)

    assert make_app().test_client().get('/health').json == {
        'status': 'ok', 'version': '3.4.0',
        'build_sha': 'unknown', 'instance': 'test-host',
    }


def test_environment_metadata_is_trimmed(make_app, monkeypatch):
    monkeypatch.setenv('ACEEST_APP_VERSION', ' 3.3.1 ')
    monkeypatch.setenv('ACEEST_BUILD_SHA', ' abc1234 ')
    monkeypatch.setenv('ACEEST_INSTANCE_ID', ' aceest-green-1 ')

    assert make_app().test_client().get('/health').json == {
        'status': 'ok', 'version': '3.3.1',
        'build_sha': 'abc1234', 'instance': 'aceest-green-1',
    }


def test_health_only_exposes_public_metadata(make_app):
    application = make_app(SECRET_KEY='private-session-secret', PRIVATE_TOKEN='hidden-token')
    response = application.test_client().get('/health')

    assert set(response.json) == {'status', 'version', 'build_sha', 'instance'}
    assert 'private-session-secret' not in response.get_data(as_text=True)
    assert 'hidden-token' not in response.get_data(as_text=True)
    assert application.config['DATABASE'] not in response.get_data(as_text=True)


def test_health_is_not_cached(make_app):
    response = make_app().test_client().get('/health')

    assert response.cache_control.no_store is True


def test_login_footer_displays_configured_release(make_app, monkeypatch):
    monkeypatch.setenv('ACEEST_APP_VERSION', '3.3.1')
    monkeypatch.setenv('ACEEST_BUILD_SHA', 'abc1234')
    monkeypatch.setenv('ACEEST_INSTANCE_ID', 'aceest-green-1')

    response = make_app().test_client().get('/login')
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'Version 3.3.1' in page
    assert 'Build abc1234' in page
    assert 'Instance aceest-green-1' in page


def test_footer_escapes_metadata_html(make_app):
    application = make_app(
        APP_VERSION='<script>version</script>',
        BUILD_SHA='<script>build</script>',
        INSTANCE_ID='<script>instance</script>',
    )

    page = application.test_client().get('/login').get_data(as_text=True)

    for value in ('version', 'build', 'instance'):
        assert f'<script>{value}</script>' not in page
        assert f'&lt;script&gt;{value}&lt;/script&gt;' in page
