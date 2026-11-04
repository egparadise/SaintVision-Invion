from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from inv.contracts import validate_contract
from inv.errors import DomainError
from inv import node_certificates

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / 'contracts/fixtures/project-node-certificate-observation-response.json'
NOW = datetime(2026, 11, 4, 4, tzinfo=timezone.utc)
NODE = 'nod_01ARZ3NDEKTSV4RRFFQ69G5FAV'
PROJECT = 'prj_01ARZ3NDEKTSV4RRFFQ69G5FAV'
CONTRACT = "ProjectNodeCertificateObservationResponse"


def test_shared_fixture_and_required_observation_fields():
    value = json.loads(FIXTURE.read_text(encoding='utf-8'))
    validate_contract(CONTRACT, value)
    for field in ('observedAt', 'scope', 'complete', 'trust'):
        changed = deepcopy(value)
        del changed[field]
        with pytest.raises(DomainError):
            validate_contract(CONTRACT, changed)


@pytest.mark.parametrize('remaining,state', [
    (timedelta(days=7), 'ok'), (timedelta(days=2), 'renewal-window'),
    (timedelta(microseconds=1), 'renewal-window'),
    (timedelta(0), 'expired'), (timedelta(microseconds=-1), 'expired'),
])
def test_summary_uses_observed_database_time_and_exact_boundaries(remaining, state):
    item = {'nodeId': NODE, 'channelEnabled': True, 'certificateNotAfter': (NOW + remaining).isoformat()}
    result = node_certificates.certificate_summary([item], NOW, complete=True)
    assert result['state'] == state
    if remaining.total_seconds() < 0:
        assert result['secondsUntilEarliestExpiry'] == -1


@pytest.mark.parametrize('enabled,expiry,complete', [
    (None, None, True), (False, NOW + timedelta(days=7), True),
    (True, None, True), (True, NOW + timedelta(days=7), False),
])
def test_missing_disabled_or_incomplete_observations_never_claim_ok(enabled, expiry, complete):
    result = node_certificates.certificate_summary([
        {'nodeId': NODE, 'channelEnabled': enabled, 'certificateNotAfter': expiry.isoformat() if expiry else None},
    ], NOW, complete=complete)
    assert result == {'state': 'unknown', 'earliestCertificateNotAfter': None,
                      'renewalWindowStartsAt': None, 'secondsUntilEarliestExpiry': None}


class Database:
    recovery_epoch = '00000000-0000-0000-0000-000000000001'

    def __init__(self, rows):
        self.rows = rows
        self.queries = []

    @contextmanager
    def transaction(self, tenant):
        self.tenant = tenant
        yield self

    def execute(self, query, params=None):
        self.queries.append((query, params))
        return SimpleNamespace(fetchone=lambda: {'now': NOW}, fetchall=lambda: self.rows)


def test_serving_anchor_rejects_an_invalid_produced_response(monkeypatch):
    db = Database([])
    control = SimpleNamespace(db=db, grant=lambda *args: None)
    monkeypatch.setattr(node_certificates, 'certificate_summary', lambda *args, **kw: {'state': 'fabricated'})
    with pytest.raises(DomainError, match='ProjectNodeCertificateObservationResponse'):
        node_certificates.serve(control, SimpleNamespace(tenant_id='synthetic-tenant'), PROJECT)


def test_project_refusal_precedes_every_certificate_query():
    db = Database([])

    def refuse(*args):
        raise DomainError('AUTH-0001', 'Project denied', 403)

    with pytest.raises(DomainError):
        node_certificates.serve(SimpleNamespace(db=db, grant=refuse), SimpleNamespace(tenant_id='synthetic-tenant'), PROJECT)
    assert db.queries == []
    assert db.tenant == 'synthetic-tenant'


def test_truncation_is_visible_and_cannot_hide_an_unobserved_node():
    rows = [{'node_id': f'nod_{index:026d}', 'certificate_not_after': NOW + timedelta(days=7), 'channel_enabled': True} for index in range(201)]
    body = node_certificates.serve(SimpleNamespace(db=Database(rows), grant=lambda *args: None), SimpleNamespace(tenant_id='synthetic-tenant'), PROJECT)
    assert len(body['items']) == 200 and body['complete'] is False
    assert body['trust']['state'] == 'unknown'
