"""One verified account creates a business project and a kernel draft, with distinct DB roles."""
from uuid import uuid4
import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
from sqlalchemy.engine import URL
from fastapi.testclient import TestClient
import pytest

from jwt_support import jwt_fixture
from saintvision.ids import new_id
from inv.app import create_app
from inv.business_surface import configured_business


def test_account_project_and_kernel_use_same_identity_and_current_membership(env, tmp_path, monkeypatch):
    jwt=jwt_fixture(tmp_path,env.tenant)
    user=new_id('user')
    role='inv_business_test_'+uuid4().hex[:20]
    password=uuid4().hex
    with psycopg.connect(env.owner) as c:
        c.execute(sql.SQL('CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOBYPASSRLS').format(sql.Identifier(role),sql.Literal(password)))
        c.execute(sql.SQL('GRANT inv_app TO {}').format(sql.Identifier(role)))
        c.execute("INSERT INTO public.tenants(tenant_id,slug,display_name) VALUES(%s,%s,'account test')",(env.tenant,uuid4().hex))
        c.execute("INSERT INTO public.users(tenant_id,user_id,external_subject,display_name) VALUES(%s,%s,%s,'test')",(env.tenant,user,jwt.subject('owner')))
    info=conninfo_to_dict(env.runtime)
    url=URL.create('postgresql+psycopg',username=role,password=password,host=info['host'],
                   port=int(info['port']),database=info['dbname'])
    monkeypatch.setenv('INV_BUSINESS_DSN',url.render_as_string(hide_password=False))
    business=None
    try:
        business=configured_business(env.db,jwt.auth)
        with TestClient(create_app(env.db,jwt.auth,business=business),raise_server_exceptions=False) as client:
            headers={'Authorization':'Bearer '+jwt.token('owner'),'Idempotency-Key':uuid4().hex}
            response=client.post('/v1/projects',json={'code':'account-'+uuid4().hex[:8],'displayName':'Test'},headers=headers)
            assert response.status_code==201, response.text
            project=response.json()['projectId']
            assert response.json()['kernelLinked'] is False
            path='/v1/projects/'+project+'/runs'
            assert client.post(path,json={},headers=headers).status_code==403
            # Operator provisioning is synthetic test setup, never a browser grant.
            with psycopg.connect(env.owner) as c:
                c.execute('INSERT INTO inv.projects VALUES(%s,%s)',(env.tenant,project))
                c.execute('INSERT INTO inv.business_projects(tenant_id,project_id) VALUES(%s,%s)',(env.tenant,project))
                c.execute('INSERT INTO inv.business_subjects(tenant_id,subject_id,user_id) VALUES(%s,%s,%s)',(env.tenant,jwt.subject('owner'),user))
                c.execute('INSERT INTO inv.project_grants(tenant_id,project_id,subject_id,can_request,can_approve) VALUES(%s,%s,%s,true,false)',(env.tenant,project,jwt.subject('owner')))
            assert client.get('/v1/projects/'+project,headers=headers).json()['kernelLinked'] is True
            response=client.post(path,json={},headers=headers)
            assert response.status_code==201, response.text
            assert response.json()['state']=='draft'
            with psycopg.connect(env.owner) as c:
                c.execute("UPDATE public.project_members SET role_code='viewer' WHERE tenant_id=%s AND project_id=%s",(env.tenant,project))
            headers['Idempotency-Key']=uuid4().hex
            assert client.post(path,json={},headers=headers).status_code==403
            assert client.get('/v1/projects',headers=headers).json()['projects'][0]['canRequest'] is False
    finally:
        if business is not None:
            business.state.engine.dispose()
        with psycopg.connect(env.owner) as c:
            c.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(role)))


def test_business_factory_refuses_different_database_target_before_connecting(env, tmp_path, monkeypatch):
    jwt=jwt_fixture(tmp_path,env.tenant)
    monkeypatch.setenv('INV_BUSINESS_DSN','postgresql+psycopg://unused:unused@other.invalid:5432/other')
    with pytest.raises(ValueError,match='targets differ'):
        configured_business(env.db,jwt.auth)


def test_business_factory_rejects_database_owner(env, tmp_path, monkeypatch):
    jwt=jwt_fixture(tmp_path,env.tenant)
    info=conninfo_to_dict(env.owner)
    url=URL.create('postgresql+psycopg',username=info['user'],password=info['password'],
                   host=info['host'],port=int(info['port']),database=info['dbname'])
    monkeypatch.setenv('INV_BUSINESS_DSN',url.render_as_string(hide_password=False))
    with pytest.raises(ValueError,match='restricted business role'):
        configured_business(env.db,jwt.auth)
