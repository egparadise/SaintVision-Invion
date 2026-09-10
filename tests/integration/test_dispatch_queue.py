"""Durable transmission reservations and recovery against actual PostgreSQL."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier
from types import SimpleNamespace
from uuid import UUID, uuid4
import psycopg
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from inv.control import Control
from inv.dispatch import DeliveryQueue, DeliveryWorker
from inv.errors import DomainError
from inv.leases import Allocation
from inv.node_execution import seal_permit
from test_approvals import approval, request, challenge, decide, dispatch, count
from test_tool_admission import gateway, claim

pytestmark = pytest.mark.postgres


def queued(a):
    a.key = Ed25519PrivateKey.generate()
    result = claim(a, queue_signing_key=a.key)
    a.queue = DeliveryQueue(a.e.db)
    return result


def row(a):
    with a.e.db.transaction(a.e.tenant) as conn:
        return conn.execute(
            "SELECT * FROM inv.execution_deliveries WHERE command_id=%s",
            (a.command["commandId"],),
        ).fetchone()


def expire_worker(a):
    with a.e.db.transaction(a.e.tenant) as conn:
        conn.execute(
            "UPDATE inv.execution_deliveries SET lease_until=clock_timestamp()-interval '1 second',next_attempt_at=clock_timestamp() WHERE command_id=%s",
            (a.command["commandId"],),
        )


def cancel(a):
    run = a.e.runs.get(a.e.tenant, a.run["runId"])
    return Control(a.e.db).cancel(
        a.people["requester"],
        a.e.project,
        a.run["runId"],
        run["version"],
        "cancel-queued",
    )


def test_claim_and_permit_commit_together_and_never_return_transient_permission(
    gateway,
):
    a = gateway
    result = queued(a)
    assert not result.may_start and result.launch is None
    with pytest.raises(DomainError):
        seal_permit(result, [], a.key)
    assert count(a, "tool_claims") == count(a, "execution_deliveries") == 1
    assert row(a)["phase"] == "queued"
    replay = claim(a, queue_signing_key=a.key)
    assert replay.claim == result.claim and not replay.may_start
    assert count(a, "execution_deliveries") == 1


def test_legacy_transient_claim_cannot_be_resealed_into_a_queue(gateway):
    a = gateway
    assert claim(a).may_start
    with pytest.raises(DomainError, match="NODE-0061"):
        queued(a)
    assert count(a, "execution_deliveries") == 0


def test_enqueue_event_failure_rolls_back_claim_permit_and_audit(gateway, monkeypatch):
    import inv.dispatch

    a = gateway
    original = inv.dispatch.event

    def fail(*args):
        raise RuntimeError("synthetic enqueue publication failure")

    monkeypatch.setattr(inv.dispatch, "event", fail)
    with pytest.raises(RuntimeError):
        queued(a)
    assert count(a, "tool_claims") == count(a, "execution_deliveries") == 0
    monkeypatch.setattr(inv.dispatch, "event", original)
    queued(a)
    assert count(a, "tool_claims") == count(a, "execution_deliveries") == 1


def test_concurrent_workers_get_only_one_start_reservation(gateway):
    a = gateway
    queued(a)
    barrier = Barrier(8)

    def take(_):
        barrier.wait(timeout=10)
        return a.queue.acquire(a.e.tenant)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(take, range(8)))
    attempts = [r for r in results if r is not None]
    assert len(attempts) == 1 and attempts[0].operation == "execute"
    assert row(a)["phase"] == "uncertain"


def test_two_runs_cannot_reserve_the_same_node_execution_slot(gateway):
    a = gateway
    queued(a)
    second = SimpleNamespace(**vars(a))
    second.workload = deepcopy(a.workload)
    second.run = a.e.runs.create(a.e.tenant, a.e.project)
    for state in ["validated", "planned"]:
        second.run = a.e.runs.transition(
            a.e.tenant,
            second.run["runId"],
            state,
            expected_version=second.run["version"],
        )
    pending = request(second, key="second-request")
    for actor in ["alice", "bob"]:
        pending = decide(
            second,
            pending,
            actor,
            challenge(second, pending, actor),
            key="second-vote-" + actor,
        )
    second.command = dispatch(second, pending, key="second-dispatch")
    leases = a.e.leases.reserve(
        a.e.tenant,
        a.e.project,
        second.run["runId"],
        [Allocation(a.e.resource, 1), Allocation(a.memory, 1)],
        key="second-queued-run",
        ttl_seconds=60,
    )
    second.proofs = {lease["leaseId"]: lease["fencingToken"] for lease in leases}
    queued(second)
    first = a.queue.acquire(a.e.tenant, command_id=a.command["commandId"])
    assert first.operation == "execute"
    assert a.queue.acquire(a.e.tenant, command_id=second.command["commandId"]) is None
    assert row(second)["phase"] == "queued"


def test_crash_before_network_and_stale_completion_never_issue_second_start(gateway):
    a = gateway
    queued(a)
    first = a.queue.acquire(a.e.tenant)
    expire_worker(a)
    recovered = DeliveryQueue(a.e.db).acquire(a.e.tenant)
    assert first.operation == "execute" and recovered.operation == "observe"
    assert first.envelope == recovered.envelope
    assert a.queue.finish(first) == "superseded"
    assert row(a)["worker_token"] == UUID(recovered.token)
    assert a.queue.finish(recovered) == "uncertain"


@pytest.mark.parametrize("actor", ["requester", "alice"])
def test_grant_revocation_after_enqueue_blocks_start(gateway, actor):
    a = gateway
    queued(a)
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            "UPDATE inv.project_grants SET enabled=false WHERE tenant_id=%s AND subject_id=%s",
            (a.e.tenant, actor),
        )
    attempt = a.queue.acquire(a.e.tenant)
    assert attempt.operation == "cancel"
    assert a.e.runs.get(a.e.tenant, a.run["runId"])["state"] == "failed"
    assert a.queue.finish(attempt) == "uncertain"


def test_cancel_preempts_active_delivery_but_never_issues_second_start(gateway):
    a = gateway
    queued(a)
    first = a.queue.acquire(a.e.tenant)
    cancel(a)
    second = a.queue.acquire(a.e.tenant)
    assert first.operation == "execute" and second.operation == "cancel"
    assert a.queue.acquire(a.e.tenant) is None
    assert a.queue.finish(first) == "superseded"
    assert a.queue.finish(second) == "uncertain"
    assert row(a)["phase"] == "uncertain"


def test_cancelled_queue_cannot_start_even_on_first_worker(gateway):
    a = gateway
    queued(a)
    cancel(a)
    assert a.queue.acquire(a.e.tenant).operation == "cancel"


def test_transport_success_without_persisted_physical_receipt_cannot_release(gateway):
    a = gateway
    queued(a)
    delivery = SimpleNamespace(deliver=lambda *args, **kwargs: {"success": True})
    assert DeliveryWorker(a.e.db, delivery).once(a.e.tenant) == "uncertain"
    assert count(a, "node_stop_receipts") == 0
    with a.e.db.transaction(a.e.tenant) as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM inv.resource_leases WHERE run_id=%s AND released_at IS NULL",
                (a.run["runId"],),
            ).fetchone()["n"]
            == 2
        )


def test_queue_failures_keep_only_safe_error_code_and_back_off(gateway):
    a = gateway
    queued(a)

    def fail(*args, **kwargs):
        raise RuntimeError("secret-credential-never-persist")

    assert (
        DeliveryWorker(a.e.db, SimpleNamespace(deliver=fail)).once(a.e.tenant)
        == "uncertain"
    )
    current = row(a)
    assert current["last_error_code"] == "SYS-0001" and current["lease_until"] is None
    assert a.queue.acquire(a.e.tenant) is None


def test_rls_and_queue_state_guards_reject_content_change_reexecution_and_false_stop(
    gateway,
):
    a = gateway
    queued(a)
    foreign = str(uuid4())
    with a.e.db.transaction(foreign) as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM inv.execution_deliveries"
            ).fetchone()["n"]
            == 0
        )
    a.queue.acquire(a.e.tenant)
    for statement in [
        "UPDATE inv.execution_deliveries SET envelope='{}'::jsonb",
        "UPDATE inv.execution_deliveries SET phase='queued'",
        "UPDATE inv.execution_deliveries SET phase='stopped'",
        "UPDATE inv.execution_deliveries SET worker_token=gen_random_uuid()",
        "DELETE FROM inv.execution_deliveries",
    ]:
        with pytest.raises(psycopg.errors.CheckViolation):
            with a.e.db.transaction(a.e.tenant) as conn:
                conn.execute(statement)
