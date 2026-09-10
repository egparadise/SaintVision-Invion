from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4
from datetime import datetime, timezone
import hashlib
import psycopg
import pytest
from inv.db import Database
from inv.errors import DomainError
from inv.ids import new_id
from inv.leases import Allocation, active_total
from inv.runs import RunStore
from inv.outbox import Outbox

pytestmark = pytest.mark.postgres


def planned(e):
    run = e.runs.create(e.tenant, e.project)
    for state in ["validated", "planned"]:
        run = e.runs.transition(
            e.tenant, run["runId"], state, expected_version=run["version"]
        )
    return run


def reserve(e, run, amount=10, key=None):
    return e.leases.reserve(
        e.tenant,
        e.project,
        run["runId"],
        [Allocation(e.resource, amount)],
        key=key or str(uuid4()),
    )[0]


def active(e):
    with e.db.transaction(e.tenant) as conn:
        return active_total(conn, e.resource)


def release(e, lease):
    return e.leases.release(
        e.tenant,
        lease["leaseId"],
        lease["fencingToken"],
        authenticated_node_id=e.node,
        stop_receipt=str(uuid4()),
    )


def running(e):
    run = planned(e)
    lease = reserve(e, run)
    proofs = {lease["leaseId"]: lease["fencingToken"]}
    for state in ["scheduled", "running"]:
        run = e.runs.transition(
            e.tenant,
            run["runId"],
            state,
            expected_version=run["version"],
            proofs=proofs,
        )
    return run, lease, proofs


def test_fifty_concurrent_requests_never_overbook(env):
    e = env
    runs = [planned(e) for _ in range(50)]
    barrier = Barrier(50)
    with psycopg.connect(e.owner) as conn:
        conn.execute(
            "UPDATE inv.nodes SET heartbeat_at=clock_timestamp() WHERE node_id=%s",
            (e.node,),
        )

    def attempt(run):
        barrier.wait(timeout=30)
        try:
            return reserve(e, run)
        except DomainError as error:
            assert error.code in {"RES-0001", "RES-0007"}
            return None

    with ThreadPoolExecutor(max_workers=50) as pool:
        results = list(pool.map(attempt, runs))
    assert sum(r is not None for r in results) == 1
    assert active(e) == 10


def test_divisible_reservations_and_multi_resource_rollback(env):
    e = env
    reserve(e, planned(e), 4)
    reserve(e, planned(e), 6)
    with pytest.raises(DomainError):
        reserve(e, planned(e), 1)
    assert active(e) == 10
    spare = new_id("res")
    with psycopg.connect(e.owner) as conn:
        conn.execute(
            "INSERT INTO inv.resources VALUES (%s,%s,%s,'memory',10,10)",
            (e.tenant, spare, e.node),
        )
    run = planned(e)
    with pytest.raises(DomainError):
        e.leases.reserve(
            e.tenant,
            e.project,
            run["runId"],
            [Allocation(spare, 2), Allocation(e.resource, 1)],
            key="atomic",
        )
    with e.db.transaction(e.tenant) as conn:
        assert active_total(conn, spare) == 0
        assert (
            conn.execute("SELECT 1 FROM inv.idempotency WHERE key='atomic'").fetchone()
            is None
        )


def test_concurrent_idempotent_replay_and_conflict(env):
    e = env
    run = planned(e)
    barrier = Barrier(8)

    def attempt(_):
        barrier.wait(timeout=10)
        return reserve(e, run, key="same")

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt, range(8)))
    assert all(result == results[0] for result in results)
    assert active(e) == 10
    with pytest.raises(DomainError, match="IDEM-0001"):
        reserve(e, run, 9, key="same")


def test_expiration_and_cancellation_do_not_release_capacity(env):
    e = env
    run, lease, proofs = running(e)
    with psycopg.connect(e.owner) as conn:
        conn.execute(
            "UPDATE inv.resource_leases SET granted_at=clock_timestamp()-interval '2 minutes',expires_at=clock_timestamp()-interval '1 minute' WHERE lease_id=%s",
            (lease["leaseId"],),
        )
    assert active(e) == 10
    with pytest.raises(DomainError):
        e.leases.renew(e.tenant, lease["leaseId"], lease["fencingToken"])
    with pytest.raises(DomainError):
        e.runs.checkpoint(e.tenant, run["runId"], "late", {}, proofs=proofs)
    e.runs.transition(
        e.tenant, run["runId"], "cancelled", expected_version=run["version"]
    )
    assert active(e) == 10
    with pytest.raises(DomainError):
        reserve(e, planned(e))
    with pytest.raises(DomainError):
        e.leases.release(
            e.tenant,
            lease["leaseId"],
            lease["fencingToken"],
            authenticated_node_id="wrong",
            stop_receipt=str(uuid4()),
        )
    release(e, lease)
    release(e, lease)
    assert active(e) == 0
    assert reserve(e, planned(e))["fencingToken"] != lease["fencingToken"]


def test_recovery_blocks_until_stop_and_old_checkpoint_cannot_win(env):
    e = env
    run, lease, proofs = running(e)
    e.runs.checkpoint(e.tenant, run["runId"], "step1", {"value": 1}, proofs=proofs)
    with pytest.raises(DomainError):
        e.runs.checkpoint(e.tenant, run["runId"], "step1", {"value": 2}, proofs=proofs)
    run = e.runs.transition(
        e.tenant, run["runId"], "recovering", expected_version=run["version"]
    )
    with pytest.raises(DomainError):
        e.runs.transition(
            e.tenant, run["runId"], "scheduled", expected_version=run["version"]
        )
    release(e, lease)
    run = e.runs.transition(
        e.tenant, run["runId"], "scheduled", expected_version=run["version"]
    )
    new = reserve(e, run)
    new_proofs = {new["leaseId"]: new["fencingToken"]}
    run = e.runs.transition(
        e.tenant,
        run["runId"],
        "running",
        expected_version=run["version"],
        proofs=new_proofs,
    )
    assert run["attempt"] == 2
    with pytest.raises(DomainError):
        e.runs.checkpoint(e.tenant, run["runId"], "late", {}, proofs=proofs)
    restarted = RunStore(Database(e.runtime, recovery_epoch=e.epoch))
    assert restarted.checkpoints(e.tenant, run["runId"])[0]["checkpoint"] == {
        "value": 1
    }


def test_rls_scope_composite_fk_and_runtime_role(env):
    e = env
    run = planned(e)
    with e.db.transaction(e.other) as conn:
        assert conn.execute("SELECT * FROM inv.runs").fetchall() == []
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with e.db.transaction(e.other) as conn:
            conn.execute(
                "INSERT INTO inv.projects VALUES (%s,%s)", (e.tenant, new_id("prj"))
            )
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        with e.db.transaction(e.other) as conn:
            conn.execute(
                "INSERT INTO inv.runs(tenant_id,project_id,run_id) VALUES (%s,%s,%s)",
                (e.other, e.project, new_id("run")),
            )
    with psycopg.connect(e.runtime) as conn:
        assert conn.execute("SELECT * FROM inv.runs").fetchall() == []
    with pytest.raises(DomainError, match="AUTH-0020"):
        with Database(e.owner, recovery_epoch=e.epoch).transaction(e.tenant):
            pass
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with e.db.transaction(e.tenant) as conn:
            conn.execute("UPDATE inv.control_epoch SET epoch=%s", (str(uuid4()),))


def test_offer_and_lock_timeout_roll_back(env):
    e = env
    run = planned(e)
    lease = reserve(e, run, 4)
    with pytest.raises(DomainError):
        e.leases.set_offer(e.tenant, e.resource, offered=3)
    with psycopg.connect(e.owner) as blocker:
        blocker.execute(
            "SELECT * FROM inv.nodes WHERE node_id=%s FOR UPDATE", (e.node,)
        )
        with pytest.raises(DomainError, match="RES-0007"):
            reserve(e, planned(e), 1, key="contention")
    assert active(e) == 4
    with e.db.transaction(e.tenant) as conn:
        assert (
            conn.execute(
                "SELECT 1 FROM inv.idempotency WHERE key='contention'"
            ).fetchone()
            is None
        )


@pytest.mark.parametrize("skew", [None, 6, -6])
def test_unmeasured_or_skewed_node_rejected(env, skew):
    e = env
    with psycopg.connect(e.owner) as conn:
        conn.execute(
            "UPDATE inv.nodes SET clock_skew_seconds=%s WHERE node_id=%s",
            (skew, e.node),
        )
    with pytest.raises(DomainError):
        reserve(e, planned(e))


def test_restore_epoch_blocks_old_service_and_old_proofs(env):
    e = env
    run, lease, proofs = running(e)
    epoch = str(uuid4())
    with psycopg.connect(e.owner) as conn:
        conn.execute("UPDATE inv.control_epoch SET epoch=%s", (epoch,))
    with pytest.raises(DomainError, match="LEASE-0004"):
        e.runs.get(e.tenant, run["runId"])
    fresh = Database(e.runtime, recovery_epoch=epoch)
    with pytest.raises(DomainError):
        RunStore(fresh).checkpoint(e.tenant, run["runId"], "stale", {}, proofs=proofs)
    # A new service still cannot place onto a Node that has not enrolled in this epoch.
    from inv.leases import LeaseStore

    with pytest.raises(DomainError):
        LeaseStore(fresh).reserve(
            e.tenant,
            e.project,
            planned_for(RunStore(fresh), e)["runId"],
            [Allocation(e.resource, 1)],
            key="epoch",
        )


def planned_for(store, e):
    run = store.create(e.tenant, e.project)
    for state in ["validated", "planned"]:
        run = store.transition(
            e.tenant, run["runId"], state, expected_version=run["version"]
        )
    return run


def test_evidence_state_outbox_atomic_and_immutable(env, tmp_path):
    e = env
    run, lease, proofs = running(e)
    run = e.runs.transition(
        e.tenant,
        run["runId"],
        "verifying",
        expected_version=run["version"],
        proofs=proofs,
    )
    output = tmp_path / "artifact"
    output.write_bytes(b"verified")
    evidence = {
        "evidenceId": new_id("evd"),
        "tenantId": e.tenant,
        "runId": run["runId"],
        "traceId": "a" * 32,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actorId": "test-worker",
        "action": "verify",
        "policyDecisionId": "p1",
        "inputSha256": "0" * 64,
        "outputSha256": hashlib.sha256(b"verified").hexdigest(),
        "result": "succeeded",
    }
    # An exception after Evidence and state writes must roll back all three records.
    import inv.runs as module
    from unittest.mock import patch

    original = module.event

    def crash(*args):
        original(*args)
        raise RuntimeError("simulated process failure")

    with patch.object(module, "event", crash), pytest.raises(RuntimeError):
        e.runs.complete(
            e.tenant,
            run["runId"],
            expected_version=run["version"],
            evidence=evidence,
            artifact_path=output,
            expected_size=8,
            proofs=proofs,
        )
    assert e.runs.get(e.tenant, run["runId"])["state"] == "verifying"
    with e.db.transaction(e.tenant) as conn:
        assert (
            conn.execute(
                "SELECT 1 FROM inv.evidence WHERE evidence_id=%s",
                (evidence["evidenceId"],),
            ).fetchone()
            is None
        )
        assert (
            conn.execute(
                "SELECT 1 FROM inv.outbox WHERE run_id=%s AND payload->>'state'='succeeded'",
                (run["runId"],),
            ).fetchone()
            is None
        )
    e.runs.complete(
        e.tenant,
        run["runId"],
        expected_version=run["version"],
        evidence=evidence,
        artifact_path=output,
        expected_size=8,
        proofs=proofs,
    )
    assert active(e) == 10  # successful computation is not a physical stop ACK
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with e.db.transaction(e.tenant) as conn:
            conn.execute("DELETE FROM inv.evidence")


def test_outbox_crash_duplicate_and_consumer_rollback(env):
    e = env
    planned(e)
    box = Outbox(e.db)
    sent = []

    def crash(payload):
        sent.append(payload)
        raise RuntimeError("broker ACK then process crash")

    with pytest.raises(RuntimeError):
        box.publish_batch(e.tenant, crash, limit=1)
    box.publish_batch(e.tenant, sent.append, limit=100)
    assert sum(p["eventId"] == sent[0]["eventId"] for p in sent) == 2
    event_id = sent[0]["eventId"]
    effects = []

    def fail(conn):
        raise RuntimeError("consumer fails before commit")

    with pytest.raises(RuntimeError):
        box.consume(e.tenant, "test", event_id, fail)
    assert box.consume(e.tenant, "test", event_id, lambda conn: effects.append(1))
    assert not box.consume(e.tenant, "test", event_id, lambda conn: effects.append(1))
    assert effects == [1]
