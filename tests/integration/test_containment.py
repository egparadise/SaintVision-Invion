"""Operator containment with real PostgreSQL, and actual Go/mTLS/Docker receipts."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic, sleep
from uuid import uuid4
import psycopg
import pytest
from inv.containment import Containment, ContainmentReconciler
from inv.dispatch import DeliveryQueue, DeliveryWorker
from inv.errors import DomainError
from inv.ids import new_id
from inv.leases import Allocation, lock_run
from inv.observation import NodeObservation
from inv.policy import action_digest
from inv.runs import RunStore
from test_control_api import api
from test_approvals import approval, approved, dispatch, count
from test_tool_admission import gateway, claim
from test_node_delivery import remote, start
from test_node_runtime import node_runtime, active, container

pytestmark = pytest.mark.postgres


def operators(a):
    with psycopg.connect(a.e.owner) as conn:
        for name, stop, resume in [("requester", True, False), ("bob", False, True)]:
            conn.execute(
                "INSERT INTO inv.operator_grants(tenant_id,subject_id,can_contain,can_resume) VALUES(%s,%s,%s,%s)",
                (a.e.tenant, a.people[name].subject_id, stop, resume),
            )
    a.ops = Containment(a.e.db)
    return a


@pytest.fixture
def ops(api):
    return operators(api)


def change(a, operation, version=0, *, key=None, actor=None):
    return a.ops.change(
        a.people[actor or ("bob" if operation in {"clear", "resume"} else "requester")],
        operation,
        {"expectedVersion": version, "reasonCode": "maintenance"},
        key or operation,
        a.e.node if operation in {"drain", "resume"} else None,
    )


def test_http_operator_is_distinct_from_project_roles_and_client_claims(ops):
    a = ops
    url = "/v1/operations/kill-switch"
    data = {"expectedVersion": 0, "reasonCode": "incident"}
    assert a.client.post(url, json=data, headers=a.headers("alice")).status_code == 403
    assert a.client.post(url, json=data, headers=a.headers("bob")).status_code == 403
    assert (
        a.client.post(url, json={**data, "tenantId": a.e.tenant}, headers=a.headers()).status_code
        == 422
    )
    assert a.client.get(url, headers=a.headers("outsider")).status_code == 403
    assert (
        a.client.post(
            f"/v1/nodes/{new_id('nod')}/drain", json=data, headers=a.headers()
        ).status_code
        == 404
    )
    response = a.client.post(url, json=data, headers=a.headers())
    assert (
        response.status_code == 202 and response.json()["control"]["killSwitchActive"]
    ), response.text
    assert not response.json()["control"]["settled"]
    assert (
        a.client.post(
            url + "/clear", json={**data, "expectedVersion": 1}, headers=a.headers()
        ).status_code
        == 403
    )


def test_concurrent_control_replay_has_one_version_and_immutable_audit(ops):
    a = ops
    with ThreadPoolExecutor(max_workers=6) as pool:
        rows = list(pool.map(lambda _: change(a, "kill"), range(6)))
    assert all(r == rows[0] for r in rows)
    assert rows[0]["control"]["version"] == 1
    assert count(a, "containment_requests") == 1
    with pytest.raises(DomainError, match="IDEM-0001"):
        change(a, "kill", 1)
    with pytest.raises(DomainError, match="GRAPH-0003"):
        change(a, "kill", key="stale")
    assert count(a, "containment_requests") == 1


def test_revoked_operator_cannot_replay_or_read(ops):
    a = ops
    change(a, "kill")
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            "UPDATE inv.operator_grants SET enabled=false WHERE tenant_id=%s AND subject_id=%s",
            (a.e.tenant, a.people["requester"].subject_id),
        )
    with pytest.raises(DomainError, match="AUTH-0062"):
        change(a, "kill")
    with pytest.raises(DomainError, match="AUTH-0062"):
        a.ops.get(a.people["requester"])


def test_gate_serializes_kill_after_prior_admission_and_blocks_later_start(ops):
    a = ops
    started = Event()

    def kill():
        started.set()
        return change(a, "kill")

    with ThreadPoolExecutor(max_workers=1) as pool:
        with a.e.db.transaction(a.e.tenant) as conn:
            row = lock_run(conn, a.run["runId"])
            future = pool.submit(kill)
            assert started.wait(2)
            sleep(0.05)
            assert not future.done()
            scheduled = RunStore(a.e.db)._transition(
                conn, a.e.tenant, row, "scheduled", row["version"]
            )
        assert future.result(timeout=3)["control"]["killSwitchActive"]
    with pytest.raises(DomainError, match="AUTH-0061"):
        a.e.leases.reserve(
            a.e.tenant, a.e.project, a.run["runId"], [Allocation(a.e.resource, 1)], key="blocked"
        )
    with pytest.raises(DomainError, match="AUTH-0061"):
        with a.e.db.transaction(a.e.tenant) as conn:
            row = lock_run(conn, scheduled["runId"])
            RunStore(a.e.db)._transition(conn, a.e.tenant, row, "running", row["version"])
    assert a.e.runs.get(a.e.tenant, a.run["runId"])["state"] == "scheduled"


def test_kill_barrier_rejects_late_success_and_rolls_back_state(ops):
    a = ops
    with a.e.db.transaction(a.e.tenant) as conn:
        for state in ("scheduled", "running", "verifying"):
            row = lock_run(conn, a.run["runId"])
            RunStore(a.e.db)._transition(conn, a.e.tenant, row, state, row["version"])
    change(a, "kill")
    with pytest.raises(DomainError, match="AUTH-0061"):
        with a.e.db.transaction(a.e.tenant) as conn:
            row = lock_run(conn, a.run["runId"])
            RunStore(a.e.db)._transition(
                conn, a.e.tenant, row, "succeeded", row["version"], evidence_ready=True
            )
    assert a.e.runs.get(a.e.tenant, a.run["runId"])["state"] == "verifying"
    assert count(a, "evidence") == 0
    assert ContainmentReconciler(a.e.db).once(a.e.tenant) == "cancelled"


def test_kill_reclaims_unclaimed_reservation_and_clear_requires_settlement(ops):
    a = ops
    a.e.leases.reserve(
        a.e.tenant, a.e.project, a.run["runId"], [Allocation(a.e.resource, 1)], key="reserved"
    )
    result = change(a, "kill")
    assert result["control"]["activeLeases"] == 1
    with pytest.raises(DomainError, match="LEASE-0003"):
        change(a, "clear", 1)
    with pytest.raises(DomainError, match="AUTH-0061"):
        a.e.runs.create(a.e.tenant, a.e.project)
    worker = ContainmentReconciler(a.e.db)
    assert worker.once(a.e.tenant) == "cancelled"
    assert worker.once(a.e.tenant) == "idle"
    assert count(a, "reservation_aborts") == 1 and count(a, "node_stop_receipts") == 0
    assert active(a) == 0
    assert not change(a, "clear", 1)["control"]["killSwitchActive"]
    assert a.e.runs.create(a.e.tenant, a.e.project)["state"] == "draft"


def test_expired_unclaimed_reservation_is_cleaned_by_delivery_worker(ops):
    a = ops
    a.e.leases.reserve(
        a.e.tenant,
        a.e.project,
        a.run["runId"],
        [Allocation(a.e.resource, 1)],
        key="short",
        ttl_seconds=1,
    )
    sleep(1.05)
    worker = DeliveryWorker(a.e.db, None)
    assert worker.once(a.e.tenant) == "cancelled"
    assert active(a) == 0 and count(a, "reservation_aborts") == 1
    assert worker.once(a.e.tenant) == "idle"


def test_parallel_reconciliation_cleans_preexisting_cancelled_reservation_once(ops):
    a = ops
    a.e.leases.reserve(
        a.e.tenant, a.e.project, a.run["runId"], [Allocation(a.e.resource, 1)], key="reserved"
    )
    a.e.runs.transition(a.e.tenant, a.run["runId"], "cancelled", expected_version=a.run["version"])
    assert active(a) == 1
    with ThreadPoolExecutor(max_workers=4) as pool:
        outcomes = list(
            pool.map(lambda _: ContainmentReconciler(a.e.db).once(a.e.tenant), range(4))
        )
    assert outcomes.count("cancelled") == 1 and outcomes.count("idle") == 3
    assert active(a) == 0 and count(a, "reservation_aborts") == 1


def test_old_epoch_reservation_remains_reported_without_reconciliation_spin(ops):
    a = ops
    a.e.leases.reserve(
        a.e.tenant, a.e.project, a.run["runId"], [Allocation(a.e.resource, 1)], key="reserved"
    )
    a.e.runs.transition(a.e.tenant, a.run["runId"], "cancelled", expected_version=a.run["version"])
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            "UPDATE inv.resource_leases SET recovery_epoch=%s WHERE tenant_id=%s AND run_id=%s",
            (uuid4(), a.e.tenant, a.run["runId"]),
        )
    assert ContainmentReconciler(a.e.db).once(a.e.tenant) == "idle"
    assert active(a) == 1 and count(a, "reservation_aborts") == 0


def test_drain_blocks_reservations_and_cleans_unclaimed_without_fabricated_receipt(ops):
    a = ops
    a.e.leases.reserve(
        a.e.tenant, a.e.project, a.run["runId"], [Allocation(a.e.resource, 1)], key="reserved"
    )
    assert change(a, "drain")["control"]["nodeStatus"] == "draining"
    other = a.e.runs.create(a.e.tenant, a.e.project)
    for state in ["validated", "planned"]:
        other = a.e.runs.transition(
            a.e.tenant, other["runId"], state, expected_version=other["version"]
        )
    with pytest.raises(DomainError, match="RES-0006"):
        a.e.leases.reserve(
            a.e.tenant, a.e.project, other["runId"], [Allocation(a.e.resource, 1)], key="blocked"
        )
    assert ContainmentReconciler(a.e.db).once(a.e.tenant) == "cancelled"
    assert active(a) == count(a, "node_stop_receipts") == 0
    with pytest.raises(DomainError, match="NODE-0062"):
        change(a, "resume", 1)


def test_control_and_audit_roll_back_together(ops, monkeypatch):
    a = ops
    import inv.containment

    original = inv.containment.validate_contract

    def fail(name, value):
        if name == "ContainmentResult":
            raise RuntimeError("synthetic response failure")
        return original(name, value)

    monkeypatch.setattr(inv.containment, "validate_contract", fail)
    with pytest.raises(RuntimeError, match="synthetic"):
        change(a, "kill")
    assert not a.ops.get(a.people["requester"])["killSwitchActive"]
    assert count(a, "containment_requests") == 0
    monkeypatch.setattr(inv.containment, "validate_contract", original)
    assert change(a, "kill")["control"]["version"] == 1


def test_operator_and_audit_db_privileges_and_tenant_isolation(ops):
    a = ops
    change(a, "kill")
    with a.e.db.transaction(a.e.other) as conn:
        assert not conn.execute("SELECT kill_switch FROM inv.tenant_controls").fetchone()[
            "kill_switch"
        ]
        assert not conn.execute("SELECT 1 FROM inv.containment_requests").fetchone()
        assert not conn.execute("SELECT 1 FROM inv.operator_grants").fetchone()
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with a.e.db.transaction(a.e.tenant) as conn:
            conn.execute("UPDATE inv.operator_grants SET can_resume=true")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with a.e.db.transaction(a.e.tenant) as conn:
            conn.execute("DELETE FROM inv.containment_requests")
    with pytest.raises(psycopg.errors.CheckViolation):
        with a.e.db.transaction(a.e.tenant) as conn:
            conn.execute("UPDATE inv.containment_requests SET response='{}'")
    with psycopg.connect(a.e.owner) as conn:
        assert not conn.execute(
            "SELECT has_table_privilege('inv_app','inv.tenant_controls','UPDATE')"
        ).fetchone()[0]


def test_drain_cannot_override_quarantine_or_old_epoch(ops):
    a = ops
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            "UPDATE inv.nodes SET status='quarantined' WHERE tenant_id=%s AND node_id=%s",
            (a.e.tenant, a.e.node),
        )
    with pytest.raises(DomainError, match="NODE-0062"):
        change(a, "drain")
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            "UPDATE inv.nodes SET recovery_epoch=%s WHERE tenant_id=%s AND node_id=%s",
            (uuid4(), a.e.tenant, a.e.node),
        )
    with pytest.raises(DomainError, match="NODE-0033"):
        change(a, "drain")
    assert count(a, "containment_requests") == 0


def queued_node(a, *, sleeping=False):
    operators(a)
    if sleeping:
        a.workload.update(command=["/probe", "sleep"], timeoutSeconds=10)
    a.policy["actionDigest"] = action_digest(a.workload)
    a.command = dispatch(a, approved(a))
    a.leases = a.e.leases.reserve(
        a.e.tenant,
        a.e.project,
        a.run["runId"],
        [Allocation(a.e.resource, 500), Allocation(a.memory, 64 * 1024 * 1024)],
        key="containment-node",
        ttl_seconds=60,
    )
    a.proofs = {l["leaseId"]: l["fencingToken"] for l in a.leases}
    claim(a, queue_signing_key=a.key)
    return a


@pytest.mark.parametrize("operation", ["kill", "drain"])
def test_queued_containment_gets_real_no_start_tombstone(remote, operation):
    a = queued_node(remote)
    assert DeliveryWorker(a.e.db, a.delivery).once(a.e.tenant, control_only=True) == "idle"
    assert a.e.runs.get(a.e.tenant, a.run["runId"])["state"] == "scheduled"
    result = change(a, operation)
    assert result["control"]["activeLeases"] == 2
    assert DeliveryWorker(a.e.db, a.delivery).once(a.e.tenant, control_only=True) == "stopped"
    with a.e.db.transaction(a.e.tenant) as conn:
        receipt = conn.execute(
            "SELECT envelope FROM inv.node_stop_receipts WHERE command_id=%s",
            (a.command["commandId"],),
        ).fetchone()["envelope"]
    assert not receipt["processStarted"] and active(a) == 0
    assert a.e.runs.get(a.e.tenant, a.run["runId"])["state"] == "cancelled"
    assert not container(a)


@pytest.mark.parametrize("operation", ["kill", "drain"])
def test_control_between_start_reservation_and_preflight_cannot_orphan_command(remote, operation):
    a = queued_node(remote)
    queue = DeliveryQueue(a.e.db)
    attempt = queue.acquire(a.e.tenant)
    assert attempt.operation == "execute"
    change(a, operation)
    with pytest.raises(DomainError) as caught:
        a.delivery.deliver(attempt.node, attempt.envelope)
    assert caught.value.not_sent
    assert queue.finish(attempt, error_code=caught.value.code, not_sent=True) == "uncertain"
    assert active(a) == 2
    assert DeliveryWorker(a.e.db, a.delivery).once(a.e.tenant) == "stopped"
    assert active(a) == 0 and count(a, "node_stop_receipts") == 1
    assert not container(a)


def test_running_kill_preempts_network_call_and_releases_only_after_real_stop(remote):
    a = queued_node(remote, sleeping=True)
    with ThreadPoolExecutor(max_workers=1) as pool:
        start = pool.submit(DeliveryWorker(a.e.db, a.delivery).once, a.e.tenant)
        deadline = monotonic() + 5
        while monotonic() < deadline:
            current = container(a)
            if current and current["State"]["Running"]:
                break
            sleep(0.05)
        else:
            pytest.fail("Actual synthetic container did not start")
        stopped = change(a, "kill")
        assert stopped["control"]["activeLeases"] == 2
        with pytest.raises(DomainError, match="LEASE-0003"):
            change(a, "clear", 1)
        assert DeliveryWorker(a.e.db, a.delivery).once(a.e.tenant, control_only=True) == "stopped"
        assert start.result(timeout=15) in {"stopped", "superseded"}
    assert active(a) == 0 and not container(a)
    assert a.e.runs.get(a.e.tenant, a.run["runId"])["state"] == "cancelled"
    with a.e.db.transaction(a.e.tenant) as conn:
        receipt = conn.execute(
            "SELECT envelope FROM inv.node_stop_receipts WHERE command_id=%s",
            (a.command["commandId"],),
        ).fetchone()["envelope"]
        assert receipt["processStarted"]
    assert change(a, "clear", 1)["control"]["settled"]


def test_drain_preserves_inflight_execution_and_resume_needs_fresh_probe(remote):
    a = queued_node(remote, sleeping=True)
    with ThreadPoolExecutor(max_workers=1) as pool:
        start = pool.submit(DeliveryWorker(a.e.db, a.delivery).once, a.e.tenant)
        deadline = monotonic() + 5
        while monotonic() < deadline:
            current = container(a)
            if current and current["State"]["Running"]:
                break
            sleep(0.05)
        else:
            pytest.fail("Actual synthetic container did not start")
        change(a, "drain")
        assert ContainmentReconciler(a.e.db).once(a.e.tenant) == "idle"
        assert a.e.runs.get(a.e.tenant, a.run["runId"])["state"] == "running"
        with pytest.raises(DomainError, match="LEASE-0003"):
            change(a, "resume", 1)
        assert start.result(timeout=18) == "stopped"
    assert active(a) == 0
    # The probe's deadline failure settles deterministically in ingestion.
    for _ in range(3):
        DeliveryWorker(a.e.db, a.delivery).once(a.e.tenant)
    NodeObservation(a.e.db, a.client).poll_resources(a.node)
    assert a.ops.get(a.people["requester"], a.e.node)["nodeStatus"] == "draining"
    assert change(a, "resume", 1)["control"]["nodeStatus"] == "online"


def test_restart_reconciler_keeps_kill_active_after_operator_is_revoked(remote):
    a = queued_node(remote)
    change(a, "kill")
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            "UPDATE inv.operator_grants SET enabled=false WHERE tenant_id=%s", (a.e.tenant,)
        )
    from inv.db import Database

    restarted = Database(a.e.runtime, recovery_epoch=a.e.epoch)
    assert DeliveryWorker(restarted, a.delivery).once(a.e.tenant) == "stopped"
    with restarted.transaction(a.e.tenant) as conn:
        assert conn.execute("SELECT kill_switch FROM inv.tenant_controls").fetchone()["kill_switch"]
    assert active(a) == 0


def test_partition_keeps_resources_until_restarted_node_returns_actual_receipt(remote):
    a = queued_node(remote)
    a.daemon.terminate()
    a.daemon.communicate(timeout=12)
    change(a, "kill")
    assert DeliveryWorker(a.e.db, a.delivery).once(a.e.tenant, control_only=True) == "uncertain"
    assert active(a) == 2 and count(a, "node_stop_receipts") == 0
    with pytest.raises(DomainError, match="LEASE-0003"):
        change(a, "clear", 1)
    start(a)
    from inv.node_channels import provision_channel

    with psycopg.connect(a.e.owner) as conn:
        provision_channel(
            conn,
            a.node,
            epoch=a.e.epoch,
            endpoint=a.endpoint,
            certificate_der=a.server_cert.der,
            expected_version=1,
        )
    with a.e.db.transaction(a.e.tenant) as conn:
        conn.execute(
            "UPDATE inv.execution_deliveries SET next_attempt_at=clock_timestamp() WHERE command_id=%s",
            (a.command["commandId"],),
        )
    assert DeliveryWorker(a.e.db, a.delivery).once(a.e.tenant, control_only=True) == "stopped"
    assert active(a) == 0 and count(a, "node_stop_receipts") == 1
    assert change(a, "clear", 1)["control"]["settled"]
