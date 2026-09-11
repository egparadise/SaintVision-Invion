"""Business HTTP + real JWT + PostgreSQL authorization and concurrent writers."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from jwt_support import jwt_fixture
from test_settings import org, NOW
from saintvision.api.app import create_app
from saintvision.config import Settings
from saintvision.db.session import tenant_scope
from saintvision.identity.oidc import OidcPrincipalVerifier
from saintvision.services import settings as service
from saintvision.errors import InvError
from inv.app import create_app as kernel_app

pytestmark = pytest.mark.postgres


@pytest.fixture
def account_api(app_engine, app_sessionmaker, owner_engine, org, tmp_path):
    jwt = jwt_fixture(tmp_path, str(org['tenant_a']))
    from inv.identity import public_subject
    with owner_engine.begin() as conn:
        for who in ('owner','viewer','second_owner'):
            conn.execute(text('UPDATE users SET external_subject=:s WHERE user_id=:u'),
                         {'s':public_subject(jwt.issuer,who),'u':org[who]})
    business = create_app(engine=app_engine, settings=Settings(database_url='unused'),
        verifier=OidcPrincipalVerifier(jwt.auth, app_sessionmaker), clock=lambda: NOW)
    with TestClient(kernel_app(tokens=jwt.auth, business=business), raise_server_exceptions=False) as client:
        yield SimpleNamespace(client=client, jwt=jwt,
            headers=lambda who='owner': {'Authorization':'Bearer '+jwt.token(who)})


def test_business_v1_routes_and_real_token_errors(account_api, org):
    a=account_api
    response=a.client.get('/v1/projects',headers=a.headers())
    assert response.status_code==200
    assert response.json()['projects'][0]['projectId']==org['project_id']
    assert a.client.get('/projects',headers=a.headers()).status_code==404
    assert a.client.get('/v1/projects',headers={'Authorization':'Bearer invalid'}).status_code==401
    assert a.client.get('/v1/projects',headers=a.headers('unregistered')).status_code==401
    assert a.client.get('/v1/projects',headers={**a.headers(),'Origin':'https://untrusted.invalid'}).status_code==403
    assert a.client.get('/v1/projects',headers=a.headers()).headers['cache-control']=='no-store'
    # Partial project matches must not swallow the kernel's deeper Run route.
    assert a.client.get('/v1/projects/'+org['project_id']+'/runs',headers=a.headers()).status_code==503


def test_nonmembers_cannot_list_members_or_permissions(account_api, org):
    for suffix in ('members','permissions/me'):
        responses=[account_api.client.get('/v1/projects/'+p+'/'+suffix,
            headers=account_api.headers('second_owner')) for p in (org['project_id'],'prj_unknown')]
        assert [r.status_code for r in responses]==[403,403]
        assert responses[0].json()['detail']==responses[1].json()['detail']


@pytest.mark.parametrize('who',['viewer','owner'])
def test_project_roles_do_not_grant_global_administration(account_api, org, owner_engine, who):
    a=account_api
    assert a.client.put('/v1/users/'+org['second_owner']+'/status',
        json={'status':'suspended'},headers=a.headers(who)).status_code==403
    assert a.client.put('/v1/capabilities/'+org['cpu_capability']+'/offer',
        json={'offeredQuantity':1,'unit':'cores'},headers=a.headers(who)).status_code==403
    with owner_engine.connect() as c:
        assert c.execute(text('SELECT status FROM users WHERE user_id=:u'),{'u':org['second_owner']}).scalar_one()=='active'
        assert c.execute(text('SELECT count(*) FROM resource_offers')).scalar_one()==0


def test_explicit_grant_is_scoped_and_revocation_is_immediate(account_api, org, owner_engine):
    a=account_api
    with owner_engine.begin() as c:
        c.execute(text("INSERT INTO inv.business_admin_grants VALUES(:t,:u,'users.manage',true)"),
                  {'t':org['tenant_a'],'u':org['owner']})
    url='/v1/users/'+org['second_owner']+'/status'
    assert a.client.put(url,json={'status':'suspended'},headers=a.headers()).status_code==200
    assert a.client.put('/v1/capabilities/'+org['cpu_capability']+'/offer',
        json={'offeredQuantity':1,'unit':'cores'},headers=a.headers()).status_code==403
    with owner_engine.begin() as c:
        c.execute(text('UPDATE inv.business_admin_grants SET enabled=false'))
    assert a.client.put(url,json={'status':'active'},headers=a.headers()).status_code==403


def test_suspended_token_and_archived_project_report_current_permissions(account_api, org, owner_engine):
    a=account_api
    url='/v1/projects/'+org['project_id']+'/status'
    assert a.client.put(url,json={'status':'archived'},headers=a.headers()).status_code==200
    row=a.client.get('/v1/projects',headers=a.headers()).json()['projects'][0]
    assert row['canRequest'] is False and row['canApprove'] is False
    assert a.client.put(url,json={'status':'active'},headers=a.headers()).status_code==200
    with owner_engine.begin() as c:
        c.execute(text("UPDATE users SET status='suspended' WHERE user_id=:u"),{'u':org['owner']})
    assert a.client.get('/v1/projects',headers=a.headers()).status_code==401


def test_definer_functions_cannot_cross_tenant_scope(app_sessionmaker, owner_engine, org):
    with owner_engine.begin() as c:
        c.execute(text("INSERT INTO inv.tenants VALUES(:t,'test')"),{'t':org['tenant_a']})
        c.execute(text('INSERT INTO inv.projects VALUES(:t,:p)'),{'t':org['tenant_a'],'p':org['project_id']})
        c.execute(text('INSERT INTO inv.business_projects(tenant_id,project_id) VALUES(:t,:p)'),{'t':org['tenant_a'],'p':org['project_id']})
        c.execute(text("INSERT INTO inv.business_admin_grants VALUES(:t,:u,'users.manage',true)"),{'t':org['tenant_a'],'u':org['owner']})
    with app_sessionmaker() as s, s.begin(), tenant_scope(s,org['tenant_b']):
        assert tuple(s.execute(text('SELECT * FROM public.project_kernel_link(:t,:p)'),{'t':org['tenant_a'],'p':org['project_id']}).one())==(False,False)
        assert s.execute(text("SELECT public.business_admin_allowed(:t,:u,'users.manage')"),{'t':org['tenant_a'],'u':org['owner']}).scalar_one() is False


def test_concurrent_owner_removal_leaves_an_owner(app_sessionmaker, owner_engine, org):
    with owner_engine.begin() as c:
        c.execute(text("INSERT INTO project_members VALUES(:t,:p,:u,'owner',now())"),
                  {'t':org['tenant_a'],'p':org['project_id'],'u':org['second_owner']})
    barrier=Barrier(2)
    def remove(who):
        try:
            with app_sessionmaker() as s,s.begin(),tenant_scope(s,org['tenant_a']):
                barrier.wait(timeout=5)
                service.remove_member(s,tenant_id=org['tenant_a'],project_id=org['project_id'],
                    user_id=org[who],acting_user_id=org[who])
            return 'removed'
        except InvError:
            return 'denied'
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(remove,('owner','second_owner')))==['denied','removed']
    with owner_engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM project_members WHERE role_code='owner'")).scalar_one()==1


def test_concurrent_offer_updates_have_one_current_interval(app_sessionmaker, owner_engine, org):
    barrier=Barrier(2)
    def offer(quantity):
        with app_sessionmaker() as s,s.begin(),tenant_scope(s,org['tenant_a']):
            barrier.wait(timeout=5)
            service.set_resource_offer(s,tenant_id=org['tenant_a'],capability_id=org['cpu_capability'],
                                      offered_quantity=quantity,unit='cores',now=NOW)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(offer,(1,2)))
    with owner_engine.connect() as c:
        rows=c.execute(text('SELECT effective_from,effective_to FROM resource_offers ORDER BY effective_from')).all()
        assert len(rows)==2 and rows[0][1]==rows[1][0] and rows[1][1] is None


def test_published_migration_heads_upgrade_without_rewriting():
    result=subprocess.run([sys.executable,'tools/check_migration_upgrade.py'],capture_output=True,timeout=180)
    assert result.returncode==0, 'Disposable migration paths failed; diagnostics withheld'
