"""Real HTTP and PostgreSQL observations; no Node execution is claimed."""
from copy import copy
from uuid import uuid4

import psycopg
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from inv.approvals import Principal
from inv.contracts import validate_contract
from inv.errors import DomainError
from inv.ids import new_id
from inv.shards import ShardAdmission, ShardRuntime
from test_approvals import approval, request
from test_control_api import api
from test_tool_admission import gateway, inputs

pytestmark = pytest.mark.postgres


def test_approval_pages_detail_filter_and_no_private_payload(api):
    a = api
    rows = [request(a)]
    for _ in range(2):
        child = copy(a)
        child.run = a.e.runs.create(a.e.tenant, a.e.project)
        for state in ['validated', 'planned']:
            child.run = a.e.runs.transition(a.e.tenant, child.run['runId'], state,
                                          expected_version=child.run['version'])
        rows.append(request(child, key=str(uuid4())))
    url = a.url + '/approvals'
    first = a.client.get(url, params={'limit': 2}, headers=a.headers('alice'))
    assert first.status_code == 200
    page = first.json()
    validate_contract('ApprovalPage', page)
    assert len(page['items']) == 2 and page['nextCursor']
    last = a.client.get(url, params={'limit': 2, 'after': page['nextCursor']},
                        headers=a.headers('alice')).json()
    assert len(last['items']) == 1 and last['nextCursor'] is None
    assert {r['approvalId'] for r in page['items'] + last['items']} == {r['approvalId'] for r in rows}
    for row in rows:
        detail = a.client.get(url + '/' + row['approvalId'], headers=a.headers()).json()
        validate_contract('ApprovalView', detail)
        assert detail == row
    filtered = a.client.get(url, params={'runId': a.run['runId']}, headers=a.headers()).json()
    assert filtered['items'] == [rows[0]]
    assert 'synthetic-private-command' not in first.text
    assert 'nonce' not in first.text and 'workload' not in first.text


def test_run_result_and_empty_views_expose_durable_state_time_not_read_time(api):
    a = api
    run_id = a.run['runId']
    with a.e.db.transaction(a.e.tenant) as c:
        updated_at = c.execute(
            'SELECT updated_at FROM inv.runs WHERE run_id=%s', (run_id,)
        ).fetchone()['updated_at']

    base = a.url + '/runs/' + run_id
    result = a.client.get(base + '/result', headers=a.headers()).json()
    artifacts = a.client.get(base + '/artifacts', headers=a.headers()).json()
    logs = a.client.get(base + '/logs', headers=a.headers()).json()
    validate_contract('RunResultView', result)
    validate_contract('RunArtifactList', artifacts)
    validate_contract('RunLogView', logs)
    assert result['stateUpdatedAt'] == updated_at.isoformat()
    assert artifacts['completedAt'] is None and artifacts['artifacts'] == []
    assert logs['completedAt'] is None and logs['stdout'] is None and logs['stderr'] is None


@pytest.mark.parametrize('params', [{'limit': 0}, {'limit': 201}, {'after': ''},
                                  {'after': 'bad'}, {'runId': 'bad'}])
def test_approval_pagination_rejects_invalid_input(api, params):
    assert api.client.get(api.url + '/approvals', params=params,
                          headers=api.headers()).status_code == 422


def test_approval_scope_and_revocation_are_checked_on_every_read(api):
    a = api
    row = request(a)
    other_project = new_id('prj')
    with psycopg.connect(a.e.owner) as c:
        c.execute('INSERT INTO inv.projects VALUES (%s,%s)', (a.e.tenant, other_project))
        c.execute('INSERT INTO inv.project_grants(tenant_id,project_id,subject_id,can_request) VALUES(%s,%s,%s,true)',
                  (a.e.tenant, other_project, a.jwt.subject('requester')))
    url = a.url + '/approvals'
    assert a.client.get(url).status_code == 401
    assert a.client.get(url, headers=a.headers('outsider')).status_code == 403
    assert a.client.get('/v1/projects/' + other_project + '/approvals/' + row['approvalId'],
                        headers=a.headers()).status_code == 404
    assert a.control.list_approvals(a.people['requester'], other_project)['items'] == []
    with psycopg.connect(a.e.owner) as c:
        # Identical project/subject identifiers in another tenant must not leak rows.
        c.execute('INSERT INTO inv.projects VALUES (%s,%s)', (a.e.other, a.e.project))
        c.execute('INSERT INTO inv.project_grants(tenant_id,project_id,subject_id,can_request) VALUES(%s,%s,%s,true)',
                  (a.e.other, a.e.project, a.jwt.subject('requester')))
    other = Principal(a.e.other, a.jwt.subject('requester'))
    assert a.control.list_approvals(other, a.e.project)['items'] == []
    with pytest.raises(DomainError) as error:
        a.control.get_approval(other, a.e.project, row['approvalId'])
    assert error.value.status == 404
    with psycopg.connect(a.e.owner) as c:
        c.execute('UPDATE inv.project_grants SET enabled=false WHERE tenant_id=%s AND project_id=%s AND subject_id=%s',
                  (a.e.tenant, a.e.project, a.jwt.subject('requester')))
    for suffix in ['', '/' + row['approvalId']]:
        assert a.client.get(url + suffix, headers=a.headers()).status_code == 403


def test_shard_view_and_parent_cancel_use_actual_durable_admission(api, gateway):
    a = api
    runtime = ShardRuntime(a.e.db, a.profile)
    admission = ShardAdmission(a.node, a.command, a.workload, a.proofs, **inputs(a))
    queued = runtime.enqueue(a.e.tenant, a.e.project, 'browser-observation', [admission],
                             signing_key=Ed25519PrivateKey.generate(), splittable=True)
    parent_id = queued['parentRunId']
    url = a.url + '/runs/' + parent_id
    response = a.client.get(url + '/shards', headers=a.headers('alice'))
    assert response.status_code == 200
    validate_contract('ShardObservation', response.json())
    assert response.json() == runtime.status(a.e.tenant, a.e.project, 'browser-observation')
    with psycopg.connect(a.e.owner) as c:
        latest_run_update = c.execute(
            """SELECT max(r.updated_at) FROM inv.runs r WHERE r.tenant_id=%s AND r.run_id IN (
                 SELECT run_id FROM inv.shard_commands WHERE tenant_id=%s AND plan_id=%s
                 UNION SELECT run_id FROM inv.shard_parents WHERE tenant_id=%s AND plan_id=%s)""",
            (a.e.tenant, a.e.tenant, 'browser-observation', a.e.tenant, 'browser-observation'),
        ).fetchone()[0]
    assert response.json()['stateAsOf'] == latest_run_update.isoformat()
    assert response.json()['shards'][0]['runId'] == a.run['runId']
    assert not response.json()['allSucceeded'] and not response.json()['allPhysicallyStopped']
    assert response.json()['resultManifest'] is None
    assert a.client.get(url + '/shards', headers=a.headers('outsider')).status_code == 403
    assert a.client.get(a.url + '/runs/' + a.run['runId'] + '/shards', headers=a.headers()).status_code == 404
    parent = a.client.get(url, headers=a.headers()).json()
    payload = {'expectedVersion': parent['version']}
    denied = a.client.post(url + '/cancel', json=payload, headers=a.headers('alice'))
    assert denied.status_code == 403
    cancelled = a.client.post(url + '/cancel', json=payload, headers=a.headers(key='cancel-parent'))
    assert cancelled.status_code == 200
    assert cancelled.json()['state'] == 'cancelled'
    assert cancelled.json()['resourceReleasePending'] is True
    assert a.client.post(url + '/cancel', json=payload,
                         headers=a.headers(key='cancel-parent')).json() == cancelled.json()
    observed = a.client.get(url + '/shards', headers=a.headers()).json()
    assert observed['parentState'] == 'cancelled'
    assert observed['shards'][0]['state'] == 'cancelled'
    assert not observed['allPhysicallyStopped']
    validate_contract('ShardObservation', observed)
    with psycopg.connect(a.e.owner) as c:
        c.execute('UPDATE inv.project_grants SET enabled=false WHERE tenant_id=%s AND project_id=%s AND subject_id=%s',
                  (a.e.tenant, a.e.project, a.jwt.subject('requester')))
    assert a.client.get(url + '/shards', headers=a.headers()).status_code == 403
    assert a.client.post(url + '/cancel', json=payload,
                         headers=a.headers(key='cancel-parent')).status_code == 403


def test_incomplete_parent_is_not_success_and_tenant_cannot_observe_it(api):
    a = api
    run_id = a.run['runId']
    with psycopg.connect(a.e.owner) as c:
        c.execute('INSERT INTO inv.shard_plans VALUES(%s,%s,%s,%s,2)',
                  (a.e.tenant, a.e.project, 'incomplete', 'a' * 64))
        c.execute('INSERT INTO inv.shard_parents VALUES(%s,%s,%s,%s,%s)',
                  (a.e.tenant, a.e.project, 'incomplete', run_id, a.e.epoch))
        c.execute('INSERT INTO inv.projects VALUES(%s,%s)', (a.e.other, a.e.project))
        c.execute('INSERT INTO inv.project_grants(tenant_id,project_id,subject_id,can_request) VALUES(%s,%s,%s,true)',
                  (a.e.other, a.e.project, a.jwt.subject('requester')))
    url = a.url + '/runs/' + run_id
    response = a.client.get(url + '/shards', headers=a.headers())
    assert response.status_code == 200
    body = response.json()
    validate_contract('ShardObservation', body)
    assert body['shardCount'] == 2 and body['shards'] == []
    assert not body['allSucceeded'] and not body['allPhysicallyStopped']
    with pytest.raises(DomainError) as error:
        a.control.shards(Principal(a.e.other, a.jwt.subject('requester')), a.e.project, run_id)
    assert error.value.status == 404
    # Corrupt/incomplete admission cannot produce a pretend cancellation success.
    assert a.client.post(url + '/cancel', json={'expectedVersion': a.run['version']},
                         headers=a.headers()).status_code == 409
