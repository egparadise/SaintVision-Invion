"""Built frontend image + verified TLS + real proxy sockets. Upstream is a transport fixture."""
from datetime import datetime, timedelta, timezone
import base64
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import ssl
import subprocess
import time
from types import SimpleNamespace
from uuid import uuid4

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(not os.getenv('INV_WEB_IMAGE'), reason='Explicit built image opt-in required')
LABEL = 'ai.saintvision.web-test'


def docker(*args):
    result = subprocess.run(['docker', *map(str, args)], check=True, capture_output=True, text=True, timeout=60)
    return (result.stdout + (result.stderr if args[0] == 'logs' else '')).strip()


@pytest.fixture(scope='module')
def web(tmp_path_factory):
    files = tmp_path_factory.mktemp('web-tls')
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'localhost')])
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(hours=1))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost'), x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]), critical=False)
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True).sign(key, hashes.SHA256()))
    certificate, private = files/'cert.pem', files/'key.pem'
    certificate.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    private.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    private.chmod(0o600)
    config = files/'auth-config.js'
    public_config = {'clientId': 'mounted-public-client', 'scope': 'inv.api',
                     'idpAuthorizeUrl': 'https://synthetic-idp.invalid/authorize',
                     'idpTokenUrl': 'https://synthetic-idp.invalid/token'}
    config.write_text('window.__SAINTVISION_CONFIG__ = ' + json.dumps(public_config) + ';', encoding='utf-8')
    group = 'sv-web-' + uuid4().hex
    network = None; containers = []
    try:
        network = docker('network', 'create', '--label', f'{LABEL}={group}', group)
        common = ['--network', group, '--label', f'{LABEL}={group}', '--memory', '128m', '--cpus', '1', '--pids-limit', '100']
        upstream = docker('run', '-d', *common, '--network-alias', 'control-plane', '--read-only',
                          '--mount', f'type=bind,source={ROOT / "tests/fixtures/nginx_transport.py"},target=/probe.py,readonly',
                          'python:3.12-slim', 'python', '/probe.py')
        containers.append(upstream)
        mounts = ['--mount', f'type=bind,source={certificate},target=/etc/ssl/certs/saintvision.crt,readonly',
                  '--mount', f'type=bind,source={private},target=/etc/ssl/private/saintvision.key,readonly',
                  '--mount', f'type=bind,source={config},target=/usr/share/nginx/html/auth-config.js,readonly']
        if os.getenv('INV_WEB_NGINX_CONFIG'):
            mounts += ['--mount', f'type=bind,source={Path(os.environ["INV_WEB_NGINX_CONFIG"]).resolve()},target=/etc/nginx/nginx.conf,readonly']
        container = docker('run', '-d', *common, *mounts, '--publish', '127.0.0.1::443', '--publish', '127.0.0.1::80',
                           '--health-interval', '1s', '--health-start-period', '1s', os.environ['INV_WEB_IMAGE'])
        containers.append(container)
        info = json.loads(docker('inspect', container))[0]
        assert info['State']['Running'], docker('logs', container)
        assert '443/tcp' in info['NetworkSettings']['Ports'], docker('logs', container)
        https = 'https://127.0.0.1:' + info['NetworkSettings']['Ports']['443/tcp'][0]['HostPort']
        http = 'http://127.0.0.1:' + info['NetworkSettings']['Ports']['80/tcp'][0]['HostPort']
        context = ssl.create_default_context(cafile=str(certificate))
        with httpx.Client(base_url=https, verify=context, trust_env=False, timeout=5) as client:
            for _ in range(60):
                try:
                    if client.get('/studio').status_code == 200: break
                except httpx.TransportError: pass
                time.sleep(.2)
            else: pytest.fail('Frontend TLS did not become live')
            yield SimpleNamespace(client=client, https=https, http=http, container=container, upstream=upstream,
                                  image_id=info['Image'], certificate=certificate,
                                  spki=base64.b64encode(hashlib.sha256(key.public_key().public_bytes(
                                      serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)).digest()).decode())
    finally:
        for container in reversed(containers):
            assert docker('inspect', container, '--format', '{{index .Config.Labels "' + LABEL + '"}}') == group
            docker('rm', '-f', container)
        if network:
            assert docker('network', 'inspect', network, '--format', '{{index .Labels "' + LABEL + '"}}') == group
            docker('network', 'rm', network)
        private.unlink(missing_ok=True)  # Exact test-owned file only, no recursive deletion.


def secure(response):
    assert response.headers.get('x-content-type-options') == 'nosniff'
    assert response.headers.get('x-frame-options') == 'DENY'
    assert response.headers.get('referrer-policy') == 'no-referrer'
    assert 'max-age=' in response.headers.get('strict-transport-security', '')


def test_studio_callback_and_mounted_auth_config_have_security_headers(web):
    for path in ['/studio', '/callback?code=synthetic-code&state=synthetic-state', '/auth-config.js']:
        result = web.client.get(path)
        assert result.status_code == 200; secure(result)
        if path == '/auth-config.js':
            assert 'mounted-public-client' in result.text
        else:
            assert '<div id="root"></div>' in result.text
        if path != '/studio': assert result.headers['cache-control'] == 'no-store'
    html = web.client.get('/studio').text
    import re
    asset = re.search(r'src="(/assets/[^\"]+\.js)"', html).group(1)
    result = web.client.get(asset)
    assert result.status_code == 200 and 'immutable' in result.headers['cache-control']; secure(result)


def test_unknown_ca_is_rejected_and_tls_is_negotiated(web):
    with pytest.raises(httpx.ConnectError):
        httpx.get(web.https + '/studio', trust_env=False)
    result = web.client.get('/studio')
    tls = result.extensions['network_stream'].get_extra_info('ssl_object')
    assert tls.version() in ('TLSv1.2', 'TLSv1.3')


def test_built_studio_page_uses_mounted_config_without_caching_credentials(web):
    from playwright.sync_api import sync_playwright, expect
    with sync_playwright() as p:
        # Trust only this ephemeral key for this browser; never disable all TLS checks.
        options = {'headless': True, 'args': ['--ignore-certificate-errors-spki-list=' + web.spki]}
        if os.name == 'nt': options['channel'] = 'msedge'
        browser = p.chromium.launch(**options)
        try:
            page = browser.new_page()
            page.goto(web.https + '/studio')
            expect(page.get_by_role('heading', name='SaintVision 로그인')).to_be_visible()
            expect(page.get_by_role('button', name='조직 계정으로 로그인')).to_be_enabled()
            expect(page.get_by_role('alert')).to_have_count(0)
            assert page.evaluate('window.__SAINTVISION_CONFIG__.clientId') == 'mounted-public-client'
            page.evaluate('navigator.serviceWorker.ready')
            page.reload()
            expect(page.get_by_role('heading', name='SaintVision 로그인')).to_be_visible()
            page.evaluate("fetch('/auth-config.js').then(r => r.text())")
            page.evaluate("fetch('/v1/session', {headers:{Authorization:'Bearer synthetic-proxy-test'}}).then(r => r.json())")
            cached = page.evaluate('async () => (await Promise.all((await caches.keys()).map(async key => (await (await caches.open(key)).keys()).map(r => r.url)))).flat()')
            assert not any('/auth-config.js' in url or '/v1/' in url or '/callback' in url for url in cached)
            assert page.evaluate('localStorage.length + sessionStorage.length') == 0
            (ROOT/'.work').mkdir(exist_ok=True)
            page.screenshot(path=str(ROOT/'.work/web-container-studio.png'), full_page=True)
        finally:
            browser.close()


def test_real_proxy_preserves_authorization_errors_and_readiness(web):
    result = web.client.get('/v1/session', headers={'Authorization': 'Bearer synthetic-proxy-test'})
    assert result.json() == {'scope': 'transport-fixture', 'bearerReceived': True}
    assert result.headers['cache-control'] == 'no-store'; secure(result)
    result = web.client.get('/v1/unknown')
    assert result.status_code == 404 and result.json()['code'] == 'FIXTURE-404'; secure(result)
    result = web.client.get('/readyz')
    assert result.status_code == 503 and result.json()['scope'] == 'transport-fixture'; secure(result)


def test_canonical_run_events_are_not_buffered(web):
    start = time.monotonic()
    with web.client.stream('GET', '/v1/projects/project/runs/run/events') as result:
        assert result.status_code == 200
        lines = result.iter_lines()
        assert next(lines) == 'data: first'
        assert time.monotonic() - start < 2, 'First event was buffered until the upstream completed'
        assert 'data: second' in list(lines)


def test_callback_secrets_are_absent_from_http_and_https_access_logs(web):
    marker = 'synthetic-never-log-' + uuid4().hex
    web.client.get('/callback?code=' + marker)
    web.client.get('/studio?state=' + marker, headers={'Referer': web.https + '/callback?code=' + marker})
    result = httpx.get(web.http + '/callback?code=' + marker, trust_env=False)
    assert result.status_code == 301
    assert ':8443/callback?' in result.headers['location']
    assert marker not in docker('logs', web.container)


def test_proxy_fails_closed_and_reconnects_after_upstream_restart(web):
    docker('stop', '--time', '2', web.upstream)
    assert web.client.get('/v1/session').status_code in (502, 504)
    assert web.client.get('/readyz').status_code in (502, 504)
    docker('start', web.upstream)
    for _ in range(50):
        response = web.client.get('/v1/session')
        if response.status_code == 200: break
        time.sleep(.1)
    assert response.json()['scope'] == 'transport-fixture'
    for _ in range(30):
        status = json.loads(docker('inspect', web.container))[0]['State']['Health']['Status']
        if status == 'healthy': break
        time.sleep(.1)
    assert status == 'healthy'
