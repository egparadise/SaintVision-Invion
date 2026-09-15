"""Isolated PostgreSQL + HTTP proof of immutable approval review bindings."""
from copy import deepcopy
from uuid import uuid4
import psycopg
from psycopg.types.json import Jsonb
import pytest
from inv.contracts import validate_contract
from inv.approvals import Principal
from inv.errors import DomainError
from inv.ids import new_id
from test_approvals import approval, request, challenge, decide
from test_control_api import api
pytestmark = pytest.mark.postgres


def test_review_returns_exact_action_only_to_authorized_project_reviewer(api):
    a = api; row = request(a); url = a.url + '/approvals/' + row['approvalId'] + '/review'
    response = a.client.get(url, headers=a.headers('alice'))
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    body = response.json(); validate_contract('ApprovalReviewView', body)
    assert body['workload'] == a.workload and body['riskLevel'] == a.policy['riskLevel']
    assert body['approval'] == row
    assert a.client.get(url).status_code == 401
    assert a.client.get(url, headers=a.headers('outsider')).status_code == 403
    assert 'synthetic-private-command' not in a.client.get(a.url+'/approvals', headers=a.headers('alice')).text
    other = Principal(a.e.other, a.jwt.subject('alice'))
    with pytest.raises(DomainError) as error:
        a.store.review(other, a.e.project, row['approvalId'])
    assert error.value.status == 404
    with psycopg.connect(a.e.owner) as c:
        c.execute('UPDATE inv.project_grants SET can_approve=false WHERE tenant_id=%s AND project_id=%s AND subject_id=%s',
                  (a.e.tenant, a.e.project, a.jwt.subject('alice')))
    assert a.client.get(url, headers=a.headers('alice')).status_code == 403


def test_snapshot_is_immutable_and_request_replay_does_not_duplicate(approval):
    a = approval; row = request(a); assert request(a) == row
    with psycopg.connect(a.e.owner) as c:
        assert c.execute('SELECT count(*) FROM inv.approval_review_snapshots WHERE tenant_id=%s AND approval_id=%s', (a.e.tenant, row['approvalId'])).fetchone()[0] == 1
    for sql in ["UPDATE inv.approval_review_snapshots SET policy_sha256=repeat('b',64)",
                'DELETE FROM inv.approval_review_snapshots']:
        with psycopg.connect(a.e.owner) as c:
            with pytest.raises(psycopg.Error): c.execute(sql + ' WHERE tenant_id=%s AND approval_id=%s', (a.e.tenant, row['approvalId']))


@pytest.mark.parametrize('damage', ['workload', 'policy', 'missing'])
def test_corrupt_or_legacy_snapshot_cannot_be_reviewed_or_approved(approval, damage):
    a = approval; row = request(a); nonce = challenge(a, row)
    # Privileged corruption simulation in a disposable test database only.
    with psycopg.connect(a.e.owner) as c:
        c.execute('ALTER TABLE inv.approval_review_snapshots DISABLE TRIGGER immutable')
        if damage == 'missing':
            c.execute('DELETE FROM inv.approval_review_snapshots WHERE tenant_id=%s AND approval_id=%s', (a.e.tenant, row['approvalId']))
        elif damage == 'workload':
            altered = deepcopy(a.workload); altered['command'] = ['changed-private-command']
            c.execute('UPDATE inv.approval_review_snapshots SET workload=%s WHERE tenant_id=%s AND approval_id=%s', (Jsonb(altered), a.e.tenant, row['approvalId']))
        else:
            altered = deepcopy(a.policy); altered['riskLevel'] = 'L0'
            c.execute('UPDATE inv.approval_review_snapshots SET policy=%s WHERE tenant_id=%s AND approval_id=%s', (Jsonb(altered), a.e.tenant, row['approvalId']))
        c.execute('ALTER TABLE inv.approval_review_snapshots ENABLE TRIGGER immutable')
    for action in [lambda: a.store.review(a.people['alice'], a.e.project, row['approvalId']),
                   lambda: decide(a, row, 'alice', nonce)]:
        with pytest.raises(DomainError) as error: action()
        assert error.value.status == 409
        assert 'private-command' not in str(error.value)
    with psycopg.connect(a.e.owner) as c:
        assert c.execute('SELECT count(*) FROM inv.approval_votes WHERE tenant_id=%s AND approval_id=%s', (a.e.tenant, row['approvalId'])).fetchone()[0] == 0
        assert c.execute('SELECT consumed_at FROM inv.approval_nonces WHERE tenant_id=%s AND approval_id=%s', (a.e.tenant, row['approvalId'])).fetchone()[0] is None
    # Rejecting an unreviewable historical action remains possible.
    assert decide(a, row, 'alice', nonce, decision='reject')['status'] == 'rejected'


def test_cancelled_run_cannot_be_reviewed(api):
    a = api; row = request(a)
    a.control.cancel(a.people['requester'], a.e.project, row['runId'], row['runVersion'], str(uuid4()))
    response = a.client.get(a.url+'/approvals/'+row['approvalId']+'/review', headers=a.headers('alice'))
    assert response.status_code == 409


def test_review_cannot_cross_project_even_with_project_grant(api):
    a = api; row = request(a); other = new_id('prj')
    with psycopg.connect(a.e.owner) as c:
        c.execute('INSERT INTO inv.projects VALUES(%s,%s)', (a.e.tenant, other))
        c.execute('INSERT INTO inv.project_grants(tenant_id,project_id,subject_id,can_approve) VALUES(%s,%s,%s,true)',
                  (a.e.tenant, other, a.jwt.subject('alice')))
    response = a.client.get('/v1/projects/'+other+'/approvals/'+row['approvalId']+'/review', headers=a.headers('alice'))
    assert response.status_code == 404
