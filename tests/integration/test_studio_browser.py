"""Real full App navigation with synthetic OAuth server; no intercepted browser responses."""
import base64
from contextlib import contextmanager
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import secrets
import socket
from threading import Thread
from urllib.parse import parse_qs, urlencode, urlsplit
import psycopg
import pytest
from test_approvals import approval, request
from test_control_api import api
from test_configured_server import running_server
from test_approval_browser import browser_page, pytestmark, ROOT


@contextmanager
def synthetic_idp(identity, origin, *, invalid_token=False):
    codes = {}; observations = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_GET(self):
            params = parse_qs(urlsplit(self.path).query)
            assert urlsplit(self.path).path == '/authorize'
            assert params['response_type'] == ['code'] and params['client_id'] == ['synthetic-web']
            assert params['redirect_uri'] == [origin + '/callback']
            assert params['code_challenge_method'] == ['S256']
            assert params['scope'] == ['inv.api']
            code = secrets.token_urlsafe(32); codes[code] = params
            self.send_response(302)
            self.send_header('Location', origin + '/callback?' + urlencode({'code': code, 'state': params['state'][0]}))
            self.end_headers()
        def do_POST(self):
            assert self.path == '/token'
            assert self.headers.get('Origin') == origin
            assert self.headers.get('Content-Type') == 'application/x-www-form-urlencoded'
            assert not self.headers.get('Authorization') and not self.headers.get('traceparent')
            params = parse_qs(self.rfile.read(int(self.headers['Content-Length'])).decode())
            original = codes.pop(params['code'][0])  # One-use code, validates StrictMode behavior.
            assert params['grant_type'] == ['authorization_code']
            assert params['redirect_uri'] == original['redirect_uri'] and params['client_id'] == original['client_id']
            digest = base64.urlsafe_b64encode(hashlib.sha256(params['code_verifier'][0].encode()).digest()).decode().rstrip('=')
            assert original['code_challenge'] == [digest]
            observations.append('valid PKCE exchange')
            value = {'access_token': identity.token('alice', claims={'aud': 'wrong-api'} if invalid_token else None), 'token_type': 'Bearer'}
            raw = json.dumps(value).encode()
            self.send_response(200); self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Content-Type', 'application/json'); self.send_header('Cache-Control', 'no-store')
            self.end_headers(); self.wfile.write(raw)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True); thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        yield {'idpAuthorizeUrl': base + '/authorize', 'idpTokenUrl': base + '/token',
               'clientId': 'synthetic-web', 'scope': 'inv.api'}, observations
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)


@pytest.mark.parametrize('invalid_token', [False, True])
def test_full_studio_login_project_approval_and_logout(api, tmp_path, invalid_token):
    from playwright.sync_api import expect
    a = api; row = request(a)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
    origin = f'http://127.0.0.1:{port}'
    with synthetic_idp(a.jwt, origin, invalid_token=invalid_token) as (config, observations), \
         running_server(a.e, tmp_path, a.jwt, allowed_origins=[origin]) as server, \
         browser_page(server.base_url, port, entry='/studio', config=config) as page:
        expect(page.get_by_role('heading', name='SaintVision 로그인')).to_be_visible()
        with page.expect_response(lambda r: r.url.endswith('/v1/session')) as session:
            page.get_by_role('button', name='조직 계정으로 로그인').click()
        assert observations == ['valid PKCE exchange']
        assert page.url == origin + '/studio'
        assert page.evaluate('sessionStorage.length') == 0
        assert page.evaluate('localStorage.length') == 0
        if invalid_token:
            assert session.value.status == 401
            expect(page.get_by_role('alert')).to_have_text('서버가 인증 토큰을 허용하지 않았습니다.')
            expect(page.get_by_role('combobox', name='프로젝트', exact=True)).to_have_count(0)
            with psycopg.connect(a.e.owner) as c:
                assert c.execute('SELECT count(*) FROM inv.approval_votes WHERE approval_id=%s', (row['approvalId'],)).fetchone()[0] == 0
            return
        assert session.value.status == 200
        assert session.value.json()['subjectId'] == a.jwt.subject('alice')
        expect(page.get_by_role('combobox', name='프로젝트', exact=True)).to_have_value(a.e.project)
        page.get_by_role('button', name='승인 센터', exact=True).click()
        expect(page.get_by_text(a.jwt.subject('alice'), exact=True)).to_be_visible()
        expect(page.locator('pre').filter(has_text='synthetic-private-command')).to_have_count(1)
        with page.expect_response(lambda r: r.url.endswith('/decision')) as decision:
            page.get_by_role('button', name='승인 확정', exact=True).click()
        assert decision.value.status == 200
        with psycopg.connect(a.e.owner) as c:
            assert c.execute('SELECT count(*) FROM inv.approval_votes WHERE approval_id=%s', (row['approvalId'],)).fetchone()[0] == 1
        page.evaluate('window.scrollTo(0, 0)')
        page.screenshot(path=str(ROOT/'.work/studio-browser.png'), full_page=True)
        # Exercise the production Desktop entry with malformed persisted layout.
        page.evaluate("localStorage.setItem('saintvision_desktop_windows', '[null]')")
        browser_errors = []
        page.on('pageerror', lambda error: browser_errors.append(str(error)))
        page.get_by_role('button', name='Web Desktop으로 전환', exact=True).click()
        expect(page.get_by_role('dialog', name='내 컴퓨터 (Resource Explorer)')).to_be_visible()
        page.get_by_role('button', name='📑 클래식 포털 뷰로 전환', exact=True).click()
        assert not browser_errors
        page.get_by_role('button', name='로그아웃', exact=True).click()
        expect(page.get_by_role('heading', name='SaintVision 로그인')).to_be_visible()
        expect(page.locator('pre').filter(has_text='synthetic-private-command')).to_have_count(0)
        assert page.evaluate("async () => (await import('/src/shared/api/client.ts')).getAuthToken()") is None
