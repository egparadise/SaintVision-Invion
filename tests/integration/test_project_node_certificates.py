"""Actual authenticated HTTP/RLS serving anchor for ProjectNodeCertificateObservationResponse."""

from datetime import datetime, timezone
from uuid import uuid4

import psycopg
import pytest

from inv.contracts import validate_contract
from test_approvals import approval  # noqa: F401 -- prerequisite of the reused usage_api fixture
from test_node_resource_usage import usage_api, _observe  # noqa: F401 -- shared disposable project fixture

pytestmark = pytest.mark.postgres


def endpoint(a):
    return f'/v1/projects/{a.e.project}/node-certificates'


def test_authenticated_missing_channel_is_explicitly_unknown(usage_api):
    a = usage_api
    assert a.client.get(endpoint(a)).status_code == 401
    assert a.client.get(endpoint(a), headers=a.headers('outsider')).status_code == 403
    response = a.client.get(endpoint(a), headers=a.headers())
    assert response.status_code == 200, response.text
    assert response.headers['cache-control'] == 'no-store'
    body = response.json()
    validate_contract('ProjectNodeCertificateObservationResponse', body)
    assert datetime.fromisoformat(body['observedAt']).tzinfo is not None
    assert body['items'] == [{'nodeId': a.e.node, 'certificateNotAfter': None, 'channelEnabled': None}]
    assert body['trust']['state'] == 'unknown'


def test_current_channel_is_observed_and_expiry_is_not_synthetic(usage_api):
    a = usage_api
    _observe(a)
    body = a.client.get(endpoint(a), headers=a.headers()).json()
    validate_contract('ProjectNodeCertificateObservationResponse', body)
    assert body['items'][0]['channelEnabled'] is True
    assert body['trust']['state'] == 'renewal-window'
    assert 86300 <= body['trust']['secondsUntilEarliestExpiry'] <= 86400
    with psycopg.connect(a.e.owner) as conn:
        conn.execute('UPDATE inv.node_channels SET version=version+1,certificate_not_after=clock_timestamp()-interval \'1 second\' WHERE tenant_id=%s AND node_id=%s', (a.e.tenant, a.e.node))
    body = a.client.get(endpoint(a), headers=a.headers()).json()
    assert body['trust']['state'] == 'expired' and body['trust']['secondsUntilEarliestExpiry'] < 0


@pytest.mark.parametrize('change', ['disabled', 'old-epoch', 'unlinked'])
def test_inactive_or_old_epoch_metadata_cannot_be_claimed_as_current(usage_api, change):
    a = usage_api
    _observe(a)
    with psycopg.connect(a.e.owner) as conn:
        if change == 'disabled':
            conn.execute('UPDATE inv.node_channels SET version=version+1,enabled=false WHERE tenant_id=%s AND node_id=%s', (a.e.tenant, a.e.node))
        elif change == 'old-epoch':
            conn.execute('UPDATE inv.node_channels SET version=version+1,recovery_epoch=%s WHERE tenant_id=%s AND node_id=%s', (uuid4(), a.e.tenant, a.e.node))
        else:
            conn.execute('UPDATE inv.project_nodes SET enabled=false WHERE tenant_id=%s AND node_id=%s', (a.e.tenant, a.e.node))
    body = a.client.get(endpoint(a), headers=a.headers()).json()
    assert body['trust']['state'] == 'unknown'
    if change == 'old-epoch':
        assert body['items'][0]['certificateNotAfter'] is None
    if change == 'unlinked':
        assert body['items'] == []


def test_http_serving_anchor_refuses_an_invalid_producer(usage_api, monkeypatch):
    from inv import node_certificates

    monkeypatch.setattr(node_certificates, 'certificate_summary', lambda *args, **kwargs: {'state': 'fabricated'})
    response = usage_api.client.get(endpoint(usage_api), headers=usage_api.headers())
    assert response.status_code != 200
    assert 'ProjectNodeCertificateObservationResponse' in response.text
