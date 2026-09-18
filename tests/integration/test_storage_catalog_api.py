"""Configured canonical app, real JWT trust and non-owner PostgreSQL queries."""
import json
from types import SimpleNamespace
from uuid import uuid4

import psycopg
from psycopg.conninfo import conninfo_to_dict
from sqlalchemy.engine import URL
from fastapi.testclient import TestClient
import pytest

from inv.app import create_configured_app
from jwt_support import jwt_fixture
from saintvision.ids import new_id
from test_server_container import business_login

pytestmark = pytest.mark.postgres


@pytest.fixture
def catalogue(env, tmp_path, monkeypatch, business_login):
    identity = jwt_fixture(tmp_path, env.tenant)
    other_tenant = str(uuid4())
    records = []
    with psycopg.connect(env.owner) as conn:
        for tenant in (env.tenant, other_tenant):
            conn.execute("INSERT INTO public.tenants(tenant_id,slug,display_name) VALUES(%s,%s,'catalogue')",
                         (tenant, uuid4().hex))
        for index, tenant in enumerate((env.tenant, env.tenant, other_tenant)):
            item = {"user": new_id("user"), "node": new_id("node"),
                    "contribution": new_id("storage_contribution"),
                    "location": new_id("data_location"), "tenant": tenant,
                    "uri": "inv://datasets/owned@1/data.bin" if index != 1 else "inv://datasets/private@1/data.bin"}
            subject = identity.subject("requester") if index == 0 else "unlinked-" + uuid4().hex
            conn.execute("INSERT INTO public.users(tenant_id,user_id,external_subject,display_name) VALUES(%s,%s,%s,'catalogue')",
                         (tenant, item['user'], subject))
            conn.execute("""INSERT INTO public.nodes(node_id,tenant_id,hostname,os_type,os_version,
                agent_version,status,enrolled_at,heartbeat_sequence,version)
                VALUES(%s,%s,%s,'linux','22.04','0.1','active',now(),0,1)""",
                         (item['node'], tenant, 'catalogue-' + str(index)))
            conn.execute("""INSERT INTO public.storage_contributions(contribution_id,tenant_id,node_id,
                declared_path,normalized_path,mode,status,registered_by_user_id,registered_at,version)
                VALUES(%s,%s,%s,'/srv/private','/srv/private','read_only','active',%s,now(),1)""",
                         (item['contribution'], tenant, item['node'], item['user']))
            conn.execute("""INSERT INTO public.data_locations(location_id,tenant_id,contribution_id,uri,
                kind,relative_path,byte_size,ready,catalogued_at,version)
                VALUES(%s,%s,%s,%s,'dataset','data.bin',7,false,now(),1)""",
                         (item['location'], tenant, item['contribution'], item['uri']))
            records.append(item)
    config = tmp_path / 'api.json'
    config.write_text(json.dumps({'identity': {
        'tenant_id': env.tenant, 'issuer': identity.issuer, 'audience': identity.audience,
        'client_ids': ['synthetic-web'], 'jwks_file': str(identity.path),
    }, 'business': True}), encoding='utf-8')
    config.chmod(0o600)
    info = conninfo_to_dict(env.runtime)
    role, password = business_login
    business_dsn = URL.create('postgresql+psycopg', username=role, password=password,
                             host=info['host'], port=int(info['port']), database=info['dbname'])
    monkeypatch.setenv('INV_API_CONFIG', str(config))
    monkeypatch.setenv('INV_RUNTIME_DSN', env.runtime)
    monkeypatch.setenv('INV_RECOVERY_EPOCH', env.epoch)
    monkeypatch.setenv('INV_BUSINESS_DSN', business_dsn.render_as_string(hide_password=False))
    api = create_configured_app()
    with TestClient(api) as client:
        yield SimpleNamespace(client=client, api=api, owner=env.owner, records=records,
                              headers={'Authorization': 'Bearer ' + identity.token()}, identity=identity)


def test_owner_resolves_actual_catalogue_and_lists_only_owned_rows(catalogue):
    c = catalogue
    response = c.client.get('/v1/storage/resolve', params={'uri': c.records[0]['uri']}, headers=c.headers)
    assert response.status_code == 200
    location = response.json()['location']
    assert location['locationId'] == c.records[0]['location']
    assert location['byteSize'] == 7 and location['ready'] is False
    assert location['checksumSha256'] is None
    for path, field, expected in (
        ('locations', 'locationId', c.records[0]['location']),
        ('contributions', 'contributionId', c.records[0]['contribution']),
    ):
        response = c.client.get('/v1/storage/' + path, headers=c.headers)
        assert response.status_code == 200
        assert [x[field] for x in response.json()['items']] == [expected]


def test_same_tenant_nonowner_unknown_and_other_tenant_are_not_disclosed(catalogue):
    c = catalogue
    for uri in (c.records[1]['uri'], 'inv://datasets/missing@1/data.bin'):
        response = c.client.get('/v1/storage/resolve', params={'uri': uri}, headers=c.headers)
        assert response.status_code == 404
        assert uri not in response.text
    for item in c.records[1:]:
        response = c.client.get('/v1/storage/locations', params={'contributionId': item['contribution']}, headers=c.headers)
        assert response.status_code == 200 and response.json()['items'] == []
    response = c.client.get('/v1/storage/resolve', params={'uri': c.records[0]['uri'], 'reader_user_id': c.records[1]['user']},
                            headers={**c.headers, 'X-Tenant-Id': c.records[2]['tenant']})
    assert response.json()['location']['locationId'] == c.records[0]['location']


def test_current_contribution_revocation_hides_locations_but_keeps_owner_status(catalogue):
    c = catalogue
    with psycopg.connect(c.owner) as conn:
        conn.execute("UPDATE public.storage_contributions SET status='revoked',revoked_at=now() WHERE contribution_id=%s",
                     (c.records[0]['contribution'],))
    assert c.client.get('/v1/storage/resolve', params={'uri': c.records[0]['uri']}, headers=c.headers).status_code == 404
    assert c.client.get('/v1/storage/locations', headers=c.headers).json()['items'] == []
    assert c.client.get('/v1/storage/contributions', headers=c.headers).json()['items'][0]['status'] == 'revoked'


@pytest.mark.parametrize('credential', [None, 'forged-admin', 'unlinked'])
def test_missing_forged_and_unprovisioned_identities_are_refused(catalogue, credential):
    c = catalogue
    headers = {} if credential is None else {'Authorization': 'Bearer ' + (
        c.identity.token('outsider') if credential == 'unlinked' else credential)}
    for path in ('/v1/storage/locations', '/v1/storage/contributions', '/v1/storage/resolve?uri=inv://datasets/a@1'):
        assert c.client.get(path, headers=headers).status_code == 401


def test_user_suspension_revokes_existing_valid_token(catalogue):
    c = catalogue
    with psycopg.connect(c.owner) as conn:
        conn.execute("UPDATE public.users SET status='suspended' WHERE user_id=%s", (c.records[0]['user'],))
    assert c.client.get('/v1/storage/locations', headers=c.headers).status_code == 401


def test_read_routes_do_not_forward_storage_mutations(catalogue):
    c = catalogue
    with psycopg.connect(c.owner) as conn:
        before = conn.execute('SELECT count(*) FROM public.storage_contributions').fetchone()[0]
    calls = [('POST', '/v1/storage/contributions'),
             ('POST', '/v1/storage/contributions/' + c.records[0]['contribution'] + '/activation'),
             ('DELETE', '/v1/storage/contributions/' + c.records[0]['contribution']),
             ('POST', '/v1/storage/resolve')]
    for method, path in calls:
        response = c.client.request(method, path, headers=c.headers, json={
            'nodeId': c.records[0]['node'], 'declaredPath': '/srv/forbidden-registration',
        })
        assert response.status_code in (404, 405)
    with psycopg.connect(c.owner) as conn:
        assert conn.execute('SELECT count(*) FROM public.storage_contributions').fetchone()[0] == before
        assert conn.execute("SELECT status FROM public.storage_contributions WHERE contribution_id=%s",
                            (c.records[0]['contribution'],)).fetchone()[0] == 'active'


@pytest.mark.parametrize('uri', ['not-an-inv-uri-secret', 'inv://models/a@1/', 'x' * 2049])
def test_bad_uri_is_bounded_and_not_reflected(catalogue, uri):
    response = catalogue.client.get('/v1/storage/resolve', params={'uri': uri}, headers=catalogue.headers)
    assert response.status_code == 422
    assert uri not in response.text
    assert response.headers['content-type'].startswith('application/problem+json')


def test_pagination_and_forged_cursor_stay_with_current_owner(catalogue):
    c = catalogue
    second = new_id('data_location')
    with psycopg.connect(c.owner) as conn:
        conn.execute("""INSERT INTO public.data_locations(location_id,tenant_id,contribution_id,uri,
            kind,relative_path,byte_size,ready,catalogued_at,version)
            VALUES(%s,%s,%s,'inv://datasets/owned@2/data.bin','dataset','data.bin',8,false,now(),1)""",
                     (second, c.records[0]['tenant'], c.records[0]['contribution']))
    first = c.client.get('/v1/storage/locations', params={'limit': 1}, headers=c.headers).json()
    assert len(first['items']) == 1 and first['nextCursor']
    following = c.client.get('/v1/storage/locations', params={'limit': 1, 'cursor': first['nextCursor']}, headers=c.headers).json()
    assert len(following['items']) == 1 and following['nextCursor'] is None
    assert {first['items'][0]['locationId'], following['items'][0]['locationId']} == {second, c.records[0]['location']}
    response = c.client.get('/v1/storage/locations', params={'cursor': c.records[1]['location'], 'limit': 999}, headers=c.headers)
    assert response.status_code == 200
    assert all(x['contributionId'] == c.records[0]['contribution'] for x in response.json()['items'])
