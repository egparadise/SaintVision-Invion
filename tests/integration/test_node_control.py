from concurrent.futures import ThreadPoolExecutor
import time
import psycopg
import pytest
from fastapi.testclient import TestClient
from inv.app import create_app
from jwt_support import jwt_fixture
from inv.control import Control
from inv.errors import DomainError
from inv.node_channels import revoke_channel
from inv.observation import NodeObservation
from test_approvals import approval
from test_node_runtime import node_runtime, prepare, active, container
from test_node_delivery import remote

pytestmark = pytest.mark.postgres


def test_real_mtls_probe_restores_offline_node_and_rejects_replay(remote):
    a = remote
    observer = NodeObservation(a.e.db, a.client)
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            "UPDATE inv.nodes SET status='offline',heartbeat_at=clock_timestamp()-interval '5 minutes' WHERE tenant_id=%s AND node_id=%s",
            (a.e.tenant, a.e.node),
        )
    proof, request = observer.begin(a.node)
    response = a.client.probe(proof, request)
    result = observer.accept(a.node, proof, request, response)
    assert result["status"] == "online" and result["profileVersion"] == a.profile.version
    with pytest.raises(DomainError):
        observer.accept(a.node, proof, request, response)
    assert not list((a.path / "state").glob("*.intent"))


def test_heartbeat_policy_controls_cannot_be_overridden_by_liveness(remote):
    a = remote
    observer = NodeObservation(a.e.db, a.client)
    for status in ["quarantined", "draining"]:
        with psycopg.connect(a.e.owner) as conn:
            conn.execute(
                "UPDATE inv.nodes SET status=%s WHERE tenant_id=%s AND node_id=%s",
                (status, a.e.tenant, a.e.node),
            )
        assert observer.poll(a.node)["status"] == status


def test_late_probe_and_revoked_certificate_cannot_refresh_heartbeat(remote):
    a = remote
    observer = NodeObservation(a.e.db, a.client)
    first = observer.begin(a.node)
    second = observer.begin(a.node)
    r1 = a.client.probe(*first)
    r2 = a.client.probe(*second)
    observer.accept(a.node, *second, r2)
    with pytest.raises(DomainError):
        observer.accept(a.node, *first, r1)
    third = observer.begin(a.node)
    r3 = a.client.probe(*third)
    with psycopg.connect(a.e.owner) as conn:
        revoke_channel(conn, a.node, expected_version=1)
    with pytest.raises(DomainError):
        observer.accept(a.node, *third, r3)


def test_missing_heartbeats_preserve_reserved_resources(remote):
    a = remote
    prepare(a)
    observer = NodeObservation(a.e.db, a.client)
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            "UPDATE inv.nodes SET heartbeat_at=clock_timestamp()-interval '61 seconds' WHERE tenant_id=%s AND node_id=%s",
            (a.e.tenant, a.e.node),
        )
    assert observer.mark_offline(a.e.tenant) == [a.e.node]
    assert active(a) == 2
    assert observer.mark_offline(a.e.tenant) == []


def test_authenticated_browser_cancel_then_mtls_stop_returns_resources(remote, tmp_path):
    a = remote
    a.workload.update(command=["/probe", "sleep", "10"], timeoutSeconds=15)
    prepare(a)
    with ThreadPoolExecutor(max_workers=2) as pool:
        execution = pool.submit(a.delivery.deliver, a.node, a.permit)
        until = time.monotonic() + 10
        while time.monotonic() < until:
            observed = container(a)
            if observed and observed["State"]["Running"]:
                break
            time.sleep(0.05)
        else:
            pytest.fail("Synthetic container did not start")
        run = a.e.runs.get(a.e.tenant, a.run["runId"])
        identity = jwt_fixture(tmp_path, a.e.tenant)
        with psycopg.connect(a.e.owner) as conn:
            conn.execute(
                "INSERT INTO inv.project_grants(tenant_id,project_id,subject_id,can_request) VALUES(%s,%s,%s,true)",
                (a.e.tenant, a.e.project, identity.subject("requester")),
            )
        with TestClient(create_app(a.e.db, identity.auth)) as client:
            response = client.post(
                "/v1/projects/" + a.e.project + "/runs/" + run["runId"] + "/cancel",
                json={"expectedVersion": run["version"]},
                headers={
                    "Authorization": "Bearer " + identity.token(),
                    "Idempotency-Key": "cancel-active",
                },
            )
        assert response.status_code == 200
        cancelled = response.json()
        assert cancelled["state"] == "cancelled" and cancelled["resourceReleasePending"]
        started = time.monotonic()
        stopped = a.delivery.deliver(a.node, a.permit, cancel_only=True)
        execution.result(timeout=10)
        assert time.monotonic() - started < 10 and stopped["receipt"]["reason"] == "cancelled"
        assert active(a) == 0 and container(a) is None
    assert a.e.runs.get(a.e.tenant, a.run["runId"])["state"] == "cancelled"


def test_cancel_unseen_command_persists_nonexecution_proof_and_releases(remote):
    a = remote
    prepare(a)
    result = a.delivery.deliver(a.node, a.permit, cancel_only=True)
    assert container(a) is None and active(a) == 0 and list((a.path / "state").glob("*.intent"))
    assert result["receipt"]["reason"] == "not_started"
    assert not result["receipt"]["processStarted"]
