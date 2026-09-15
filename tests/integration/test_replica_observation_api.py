"""Real canonical identity + restricted PostgreSQL replica observations."""
from datetime import datetime, timezone

import psycopg
import pytest
from sqlalchemy import event
from sqlalchemy.engine import Engine

from saintvision.ids import new_id
from test_storage_catalog_api import catalogue
from test_server_container import business_login

pytestmark = pytest.mark.postgres
PATH = '/v1/storage/replica-status'
STATES = ('ready', 'transferring', 'stale', 'corrupt', 'evicted')


def seed(c, item, states):
    with psycopg.connect(c.owner) as conn:
        for state in states:
            node = new_id('node')
            conn.execute("""INSERT INTO public.nodes(node_id,tenant_id,hostname,os_type,os_version,
                agent_version,status,enrolled_at,heartbeat_sequence,version)
                VALUES(%s,%s,%s,'linux','22.04','0.1','lost',now(),0,1)""",
                         (node, item['tenant'], node))
            conn.execute("""INSERT INTO public.data_replicas(replica_id,tenant_id,location_id,
                node_id,contribution_id,state,local_bytes,checksum_sha256,verified_at,created_at)
                VALUES(%s,%s,%s,%s,%s,%s,7,%s,now(),now())""",
                         (new_id('replica'), item['tenant'], item['location'], node,
                          item['contribution'], state, 'a' * 64))


def observe(c, **params):
    return c.client.get(PATH, params={'uri': c.records[0]['uri'], **params}, headers=c.headers)


def test_recorded_counts_use_one_statement_and_never_claim_live_availability(catalogue):
    c = catalogue
    seed(c, c.records[0], STATES)
    seed(c, c.records[1], ('ready', 'ready'))
    seed(c, c.records[2], ('corrupt', 'corrupt'))
    statements = []

    def record(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith('SELECT') and 'data_replicas' in statement:
            statements.append(statement)

    event.listen(Engine, 'before_cursor_execute', record)
    before = datetime.now(timezone.utc)
    try:
        response = observe(c, reader_user_id=c.records[1]['user'], tenant_id=c.records[2]['tenant'])
    finally:
        event.remove(Engine, 'before_cursor_execute', record)
    assert response.status_code == 200
    body = response.json()['observation']
    assert body['locationId'] == c.records[0]['location']
    assert body['locationVersion'] == 1
    assert body['recordedStates'] == dict.fromkeys(STATES, 1)
    assert body['totalRecords'] == 5
    assert body['currentAvailability'] == 'unknown'
    assert body['requiresExecutionRevalidation'] is True
    assert before <= datetime.fromisoformat(body['observedAt']) <= datetime.now(timezone.utc)
    assert len(statements) == 1
    assert 'storage_contributions' in statements[0]
    assert 'registered_by_user_id' in statements[0]
    assert '/srv/' not in response.text and 'nodeId' not in response.text


def test_known_empty_location_is_observed_but_hidden_and_unknown_are_not(catalogue):
    c = catalogue
    response = observe(c)
    assert response.status_code == 200
    body = response.json()['observation']
    assert body['recordedStates'] == dict.fromkeys(STATES, 0)
    assert body['totalRecords'] == 0 and body['currentAvailability'] == 'unknown'
    for uri in (c.records[1]['uri'], 'inv://datasets/missing@1/data.bin'):
        response = observe(c, uri=uri)
        assert response.status_code == 404 and uri not in response.text
    with psycopg.connect(c.owner) as conn:
        conn.execute('DELETE FROM public.data_locations WHERE location_id=%s', (c.records[0]['location'],))
    # The same URI in the foreign tenant must not satisfy the lookup.
    assert observe(c).status_code == 404


def test_revocation_hides_previous_observation(catalogue):
    c = catalogue
    seed(c, c.records[0], ('ready',))
    assert observe(c).status_code == 200
    with psycopg.connect(c.owner) as conn:
        conn.execute("UPDATE public.storage_contributions SET status='revoked',revoked_at=now() WHERE contribution_id=%s",
                     (c.records[0]['contribution'],))
    assert observe(c).status_code == 404


def test_identity_and_method_boundaries(catalogue):
    c = catalogue
    for headers in ({}, {'Authorization': 'Bearer forged'},
                    {'Authorization': 'Bearer ' + c.identity.token('outsider')}):
        assert c.client.get(PATH, params={'uri': c.records[0]['uri']}, headers=headers).status_code == 401
    for method in ('POST', 'PUT', 'PATCH', 'DELETE'):
        assert c.client.request(method, PATH, params={'uri': c.records[0]['uri']}, headers=c.headers, json={}).status_code in (404, 405)
    with psycopg.connect(c.owner) as conn:
        conn.execute("UPDATE public.users SET status='suspended' WHERE user_id=%s", (c.records[0]['user'],))
    assert observe(c).status_code == 401


@pytest.mark.parametrize('uri', ['private-invalid-uri', 'inv://models/a@1/', 'x' * 2049])
def test_invalid_uri_is_bounded_and_not_reflected(catalogue, uri):
    response = observe(catalogue, uri=uri)
    assert response.status_code == 422 and uri not in response.text
