"""Actual Edge/Chromium -> Vite proxy -> canonical HTTP factory -> isolated PostgreSQL.
Synthetic JWT is injected in memory; no mocked HTTP and no operational SSO claim.
"""
import os
import socket
import psycopg
import pytest
from test_approval_browser import browser_page
from test_configured_server import running_server
from test_storage_catalog_api import catalogue, business_login
from test_model_view import view, storage_subject
from test_model_commit import model
from test_storage_commit import sample

pytestmark = [pytest.mark.postgres, pytest.mark.skipif(os.getenv('INV_BROWSER_TEST') != '1', reason='Explicit browser acceptance lane required')]

def port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]

def mount(page, token, project, view):
    page.wait_for_function('typeof window.mountDesktopTest === "function"')
    page.evaluate('(input) => window.mountDesktopTest(input)',
                  {'token':token,'projectId':project,'view':view})

def test_browser_real_catalogue_owner_scope_and_revocation(catalogue, env, tmp_path):
    from playwright.sync_api import expect
    c = catalogue
    p = port()
    with running_server(env, tmp_path, c.identity, business=True) as server, browser_page(server.base_url, p, entry='/tests/browser/desktop.html') as page:
        errors=[]; methods=[]
        page.on('pageerror',lambda error: errors.append(str(error)))
        page.on('request',lambda request: methods.append(request.method) if '/v1/' in request.url else None)
        mount(page,c.identity.token(),env.project,'files')
        owned = page.get_by_role('button',name=c.records[0]['uri'],exact=True)
        expect(owned).to_be_visible()
        expect(page.get_by_role('button',name=c.records[1]['uri'],exact=True)).to_have_count(0)
        owned.click()
        expect(page.get_by_text('현재 가용성: 미확인 · 실행 시 재검증 필요',exact=True)).to_be_visible()
        expect(page.get_by_text('전체 기록: 0',exact=True)).to_be_visible()
        page.get_by_label('파일 URI',exact=True).fill(c.records[1]['uri'])
        with page.expect_response(lambda r:'/storage/resolve?' in r.url) as response:
            page.get_by_role('button',name='조회',exact=True).click()
        assert response.value.status == 404
        expect(page.get_by_role('alert')).to_be_visible()
        expect(page.get_by_text('현재 가용성: 미확인 · 실행 시 재검증 필요',exact=True)).to_have_count(0)
        with psycopg.connect(c.owner) as conn:
            conn.execute("UPDATE public.storage_contributions SET status='revoked',revoked_at=now() WHERE contribution_id=%s",(c.records[0]['contribution'],))
        page.get_by_role('button',name='목록 새로고침').click()
        expect(page.get_by_text('등록된 파일이 없습니다.',exact=True)).to_be_visible()
        expect(owned).to_have_count(0)
        mount(page,'forged',env.project,'files')
        expect(page.get_by_role('alert')).to_contain_text('저장소 조회에 실패')
        assert methods and set(methods)=={'GET'} and not errors

def test_browser_real_committed_model_and_current_permission(view, tmp_path):
    from playwright.sync_api import expect
    a=view; p=port()
    with running_server(a.e,tmp_path,a.jwt) as server, browser_page(server.base_url,p,entry='/tests/browser/desktop.html') as page:
        errors=[];methods=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('request',lambda request:methods.append(request.method) if '/v1/' in request.url else None)
        mount(page,a.jwt.token(),a.e.project,'model')
        page.get_by_label('모델 ID',exact=True).fill(a.body['modelId'])
        page.get_by_label('버전',exact=True).fill(a.body['version'])
        with page.expect_response(lambda r:r.url.endswith('/commitment')) as response:
            page.get_by_role('button',name='기록 조회',exact=True).click()
        assert response.value.status==200
        expect(page.get_by_text('Manifest SHA-256: '+a.receipt['manifestHash'],exact=True)).to_be_visible()
        expect(page.get_by_text('현재 가용성: 미확인 · 실행 시 재검증 필요',exact=True)).to_be_visible()
        with psycopg.connect(a.e.owner) as conn:
            conn.execute('UPDATE inv.project_grants SET enabled=false WHERE tenant_id=%s',(a.e.tenant,))
        with page.expect_response(lambda r:r.url.endswith('/commitment')) as response:
            page.get_by_role('button',name='기록 조회',exact=True).click()
        assert response.value.status==403
        expect(page.get_by_role('alert')).to_be_visible()
        expect(page.get_by_text('Manifest SHA-256: '+a.receipt['manifestHash'],exact=True)).to_have_count(0)
        assert methods and set(methods)=={'GET'} and not errors
