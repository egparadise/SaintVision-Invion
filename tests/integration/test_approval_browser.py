"""Actual Chromium page + configured server + isolated PG; synthetic JWT, not operational SSO."""
from contextlib import contextmanager
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time
from uuid import uuid4
import httpx
import psycopg
import pytest
from test_approvals import approval, request
from test_control_api import api
from test_configured_server import running_server
pytestmark = [pytest.mark.postgres, pytest.mark.skipif(os.getenv('INV_BROWSER_TEST') != '1', reason='Explicit browser test opt-in required')]
ROOT = Path(__file__).resolve().parents[2]

@contextmanager
def browser_page(api_url, port):
    import playwright.sync_api as playwright
    child = subprocess.Popen([shutil.which('node'), 'node_modules/vite/bin/vite.js', '--config',
        'tests/browser/vite.config.ts', '--port', str(port)], cwd=ROOT/'apps/web',
        env={**os.environ, 'INV_BROWSER_TEST_API_URL': str(api_url).rstrip('/')},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    try:
        url = f'http://127.0.0.1:{port}/tests/browser/approval.html'
        for _ in range(100):
            assert child.poll() is None, 'Test Vite server exited'
            try:
                if httpx.get(url, timeout=1, trust_env=False).status_code == 200: break
            except httpx.TransportError: pass
            time.sleep(.1)
        else: pytest.fail('Test Vite server unavailable')
        with playwright.sync_playwright() as p:
            options = {'headless': True}
            if os.name == 'nt': options['channel'] = 'msedge'
            browser = p.chromium.launch(**options)
            try:
                page = browser.new_page(); page.goto(url)
                page.wait_for_function('typeof window.mountApprovalTest === "function"')
                yield page
            finally: browser.close()
    finally:
        child.terminate()
        try: child.wait(timeout=10)
        except subprocess.TimeoutExpired: child.kill(); child.wait(timeout=10)


def mount(page, a, actor):
    page.evaluate('(input) => window.mountApprovalTest(input)',
                  {'token': a.jwt.token(actor), 'projectId': a.e.project, 'subject': a.jwt.subject(actor)})
    from playwright.sync_api import expect
    expect(page.get_by_text(a.jwt.subject(actor), exact=True)).to_be_visible()


def test_actual_browser_quorum_snapshot_and_no_duplicate_vote(api, tmp_path):
    from playwright.sync_api import expect
    a = api; row = request(a)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
    with running_server(a.e, tmp_path, a.jwt, allowed_origins=[f'http://127.0.0.1:{port}']) as server, browser_page(server.base_url, port) as page:
        mount(page, a, 'alice')
        expect(page.get_by_role('heading', name='승인할 작업 스냅샷')).to_be_visible()
        expect(page.locator('pre').filter(has_text='synthetic-private-command')).to_have_count(1)
        button = page.get_by_role('button', name='승인 확정', exact=True)
        expect(button).to_be_enabled(); button.click()
        expect(page.get_by_test_id('mutation-result')).to_have_text('decision committed')
        with psycopg.connect(a.e.owner) as c:
            assert c.execute('SELECT status FROM inv.approval_requests WHERE tenant_id=%s AND approval_id=%s',
                             (a.e.tenant, row['approvalId'])).fetchone()[0] == 'pending'
        button.click(); expect(page.get_by_test_id('mutation-result')).to_have_text('decision rejected')
        mount(page, a, 'bob'); expect(button).to_be_enabled(); button.click()
        expect(page.get_by_test_id('mutation-result')).to_have_text('decision committed')
        with psycopg.connect(a.e.owner) as c:
            assert c.execute('SELECT status FROM inv.approval_requests WHERE tenant_id=%s AND approval_id=%s',
                             (a.e.tenant, row['approvalId'])).fetchone()[0] == 'approved'
            assert c.execute('SELECT count(*) FROM inv.approval_votes WHERE tenant_id=%s AND approval_id=%s',
                             (a.e.tenant, row['approvalId'])).fetchone()[0] == 2
        expect(button).to_be_disabled()
        expect(page.get_by_role('button', name='반려', exact=True)).to_be_disabled()
        expect(page.get_by_text('파일 변경 내역이 이 응답에 포함되어 있지 않습니다.', exact=True)).to_be_visible()
        (ROOT/'.work').mkdir(exist_ok=True)
        page.screenshot(path=str(ROOT/'.work/approval-browser.png'), full_page=True)


def test_actual_browser_stale_run_and_revoked_review_are_rejected(api, tmp_path):
    from playwright.sync_api import expect
    a = api; row = request(a)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
    with running_server(a.e, tmp_path, a.jwt, allowed_origins=[f'http://127.0.0.1:{port}']) as server, browser_page(server.base_url, port) as page:
        mount(page, a, 'alice')
        button = page.get_by_role('button', name='승인 확정', exact=True)
        expect(button).to_be_enabled()
        a.control.cancel(a.people['requester'], a.e.project, row['runId'], row['runVersion'], str(uuid4()))
        with page.expect_response(lambda r: r.url.endswith('/challenge')) as response:
            button.click()
        assert response.value.status == 409
        assert response.value.json()['code'] == 'AUTH-0032'
        expect(page.get_by_test_id('mutation-result')).to_have_text('decision rejected')
        mount(page, a, 'outsider')
        expect(page.get_by_test_id('mutation-result')).to_have_text('load failed')
        expect(page.get_by_role('heading', name='승인할 작업 스냅샷')).to_have_count(0)
        with psycopg.connect(a.e.owner) as c:
            assert c.execute('SELECT count(*) FROM inv.approval_votes WHERE tenant_id=%s AND approval_id=%s',
                             (a.e.tenant, row['approvalId'])).fetchone()[0] == 0
