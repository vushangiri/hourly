import pytest
from hourly import create_app


@pytest.fixture
def app():
    return create_app({'TESTING':True,'SECRET_KEY':'test-key-with-more-than-32-characters','SESSION_COOKIE_SECURE':False})


def test_auth_page_security(app):
    r=app.test_client().get('/auth')
    assert r.status_code==200
    assert b'Welcome back.' in r.data
    assert r.headers['Cache-Control']=='no-store'
    assert "default-src 'self'" in r.headers['Content-Security-Policy']
    assert 'HttpOnly' in r.headers['Set-Cookie'] and 'SameSite=Lax' in r.headers['Set-Cookie']


def test_csrf_rejected_without_database(app):
    r=app.test_client().post('/auth',json={'mode':'login'})
    assert r.status_code==400


def test_private_api_requires_login(app):
    assert app.test_client().get('/api/dashboard').status_code==401


def test_offline_shell_contains_no_user(app):
    r=app.test_client().get('/offline')
    assert r.status_code==200
    assert b'name="account" content=""' in r.data


def test_manifest_and_worker(app):
    c=app.test_client();r=c.get('/static/manifest.webmanifest')
    import json
    m=json.loads(r.data)
    assert m['display']=='standalone'
    for icon in m['icons']:assert c.get(icon['src']).status_code==200
    assert c.get('/sw.js').status_code==200


def test_reject_sqlite():
    with pytest.raises(RuntimeError):create_app({'SECRET_KEY':'x'*40,'DATABASE_URL':'sqlite://'})
