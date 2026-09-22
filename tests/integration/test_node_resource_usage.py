"""Serving anchor for "NodeResourceUsageResponse" over the real HTTP path and real PostgreSQL.

The contract (decision #2 A, commit eceac8cf) exists as schema + fixture + generated types;
this file is what makes the kernel route ``GET /v1/projects/{project}/nodes/{node_id}/
resource-usage`` *serve* it. Every assertion here goes through ``TestClient`` against
``create_app`` so the auth dependency, the project grant and the contract validation on the
serving path are all exercised (not the read-model function alone).
"""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb
import pytest
from fastapi.testclient import TestClient

from inv.app import create_app
from inv.contracts import validate_contract
from jwt_support import jwt_fixture
from test_approvals import approval  # noqa: F401 -- fixture: env + project grants

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "contracts" / "fixtures" / "node-resource-usage-response.json"


@pytest.fixture
def usage_api(approval, tmp_path):
    a = approval
    a.jwt = jwt_fixture(tmp_path, a.e.tenant)
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            "INSERT INTO inv.project_grants(tenant_id,project_id,subject_id,can_request,can_approve) VALUES(%s,%s,%s,true,true)",
            (a.e.tenant, a.e.project, a.jwt.subject("requester")),
        )
        conn.execute(
            "INSERT INTO inv.project_nodes(tenant_id,project_id,node_id,enabled) VALUES(%s,%s,%s,true)",
            (a.e.tenant, a.e.project, a.e.node),
        )
    a.client = TestClient(
        create_app(a.e.db, a.jwt.auth, allowed_origins=["https://web.invalid"]),
        raise_server_exceptions=False,
    )
    a.headers = lambda actor="requester": {"Authorization": "Bearer " + a.jwt.token(actor)}
    a.url = f"/v1/projects/{a.e.project}/nodes/{a.e.node}/resource-usage"
    yield a
    a.client.close()


def _observe(a, *, seconds_ago=0, lease=None):
    """Seed an authorized, fresh observation (and optionally one unreleased lease)."""
    now = datetime.now(timezone.utc)
    received = now - timedelta(seconds=seconds_ago)
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            "INSERT INTO inv.node_channels(tenant_id,node_id,recovery_epoch,version,endpoint,certificate_sha256,certificate_not_after,enabled) "
            "VALUES(%s,%s,%s,1,'https://node.invalid:8443',%s,%s,true) ON CONFLICT(tenant_id,node_id) DO NOTHING",
            (a.e.tenant, a.e.node, a.e.epoch, "0" * 64, now + timedelta(days=1)),
        )
        conn.execute(
            "INSERT INTO inv.node_resource_snapshots(tenant_id,node_id,recovery_epoch,channel_version,received_at,snapshot) "
            "VALUES(%s,%s,%s,1,%s,%s) ON CONFLICT(tenant_id,node_id) DO UPDATE SET received_at=excluded.received_at",
            (a.e.tenant, a.e.node, a.e.epoch, received, Jsonb({})),
        )
        conn.execute(
            "UPDATE inv.nodes SET heartbeat_at=%s WHERE tenant_id=%s AND node_id=%s",
            (received, a.e.tenant, a.e.node),
        )
        if lease is not None:
            conn.execute(
                "INSERT INTO inv.resource_leases(tenant_id,project_id,run_id,resource_id,lease_id,amount,fencing_token,granted_at,expires_at,recovery_epoch) "
                "VALUES(%s,%s,%s,%s,%s,%s,1,%s,%s,%s)",
                (a.e.tenant, a.e.project, lease["run_id"], a.e.resource, lease["lease_id"], lease["amount"],
                 now, now + timedelta(minutes=5), a.e.epoch),
            )
    return received


def test_fixture_and_served_response_share_one_contract_shape(usage_api):
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    validate_contract("NodeResourceUsageResponse", fixture)
    body = usage_api.client.get(usage_api.url, headers=usage_api.headers()).json()
    validate_contract("NodeResourceUsageResponse", body)
    assert set(body) == set(fixture)
    assert set(body["resources"][0]) == set(fixture["resources"][0])


def test_unobserved_node_is_reported_unmeasured_not_zero(usage_api):
    a = usage_api
    response = a.client.get(a.url, headers=a.headers())
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source"] == "execution-kernel" and body["nodeId"] == a.e.node
    assert body["stateAsOf"] is None
    [item] = body["resources"]
    assert item["resourceId"] == a.e.resource
    assert (item["kind"], item["unit"]) == ("cpu", "millicores")
    assert (item["capacity"], item["offered"]) == (10, 10)
    assert item["measured"] is False
    assert item["reserved"] is None and item["spare"] is None and item["observedAt"] is None


def test_fresh_authorized_observation_reports_lease_allocation(usage_api):
    a = usage_api
    run = a.e.runs.create(a.e.tenant, a.e.project)
    from inv.ids import new_id

    observed = _observe(a, lease={"run_id": run["runId"], "lease_id": new_id("lse"), "amount": 3})
    body = a.client.get(a.url, headers=a.headers()).json()
    validate_contract("NodeResourceUsageResponse", body)
    [item] = body["resources"]
    assert item["measured"] is True
    assert (item["reserved"], item["spare"]) == (3, 7)
    assert datetime.fromisoformat(item["observedAt"]) == observed
    assert body["stateAsOf"] == item["observedAt"]


def test_stale_observation_falls_back_to_unmeasured(usage_api):
    a = usage_api
    _observe(a, seconds_ago=60)
    [item] = a.client.get(a.url, headers=a.headers()).json()["resources"]
    assert item["measured"] is False and item["reserved"] is None and item["observedAt"] is None


def test_serving_anchor_rejects_a_response_that_breaks_the_contract(usage_api, monkeypatch):
    """Removing the anchor must be visible: an invalid produced body is refused, not served."""
    a = usage_api
    import inv.node_resource_usage as module

    monkeypatch.setattr(module, "UNITS", {**module.UNITS, "cpu": "cores"})  # not in the unit enum
    response = a.client.get(a.url, headers=a.headers())
    assert response.status_code != 200
    assert "NodeResourceUsageResponse" in response.text


def test_project_grant_and_node_linkage_are_enforced(usage_api):
    a = usage_api
    assert a.client.get(a.url, headers=a.headers("outsider")).status_code == 403
    assert a.client.get(a.url).status_code == 401
    from inv.ids import new_id

    unknown = f"/v1/projects/{a.e.project}/nodes/{new_id('nod')}/resource-usage"
    assert a.client.get(unknown, headers=a.headers()).status_code == 404
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            "UPDATE inv.project_nodes SET enabled=false WHERE tenant_id=%s AND node_id=%s",
            (a.e.tenant, a.e.node),
        )
    assert a.client.get(a.url, headers=a.headers()).status_code == 404
