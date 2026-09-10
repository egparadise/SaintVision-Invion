"""Actual DB, immutable files, fenced preparation and physical-release ordering."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import sys
from uuid import uuid4
import psycopg
import pytest
from inv.db import Database
from inv.dispatch import DeliveryQueue
from inv.errors import DomainError
from inv.ids import new_id
from inv.node_execution import NodeReceiptStore
from inv.results import ResultStore
from inv.snapshots import object_key
from test_approvals import approval, count
from test_tool_admission import gateway
from test_dispatch_queue import queued, expire_worker, cancel
from test_node_runtime import allocations, active, node_runtime
from test_node_delivery import remote
from test_dispatch_node import prepare_queue
from test_snapshots import storage, published

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(sys.platform != "linux", reason="Linux private storage"),
]


def output(a, s):
    data = b"synthetic verifier output"
    oid = published(a.e, s, data)
    with a.e.db.transaction(a.e.tenant) as conn:
        claim = conn.execute(
            "SELECT * FROM inv.tool_claims WHERE command_id=%s",
            (a.command["commandId"],),
        ).fetchone()
    evidence = {
        "evidenceId": new_id("evd"),
        "tenantId": a.e.tenant,
        "runId": a.run["runId"],
        "traceId": "a" * 32,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actorId": "trusted-synthetic-verifier",
        "action": "verify-output",
        "policyDecisionId": claim["policy_decision_id"],
        "inputSha256": claim["action_digest"],
        "outputSha256": hashlib.sha256(data).hexdigest(),
        "result": "succeeded",
    }
    return oid, evidence


@pytest.fixture
def result(gateway, storage):
    a, s = gateway, storage
    queued(a)
    a.delivery_attempt = a.queue.acquire(a.e.tenant)
    assert a.delivery_attempt.operation == "execute"
    a.results = ResultStore(a.e.db, s.provider)
    a.oid, a.evidence = output(a, s)
    a.storage = s
    a.run = a.e.runs.get(a.e.tenant, a.run["runId"])
    return a


def prepare(a, **changes):
    return a.results.prepare(
        a.e.tenant,
        a.e.project,
        a.run["runId"],
        a.command["commandId"],
        changes.get("oid", a.oid),
        changes.get("evidence", a.evidence),
        proofs=changes.get("proofs", a.proofs),
    )


def stopped(a, **changes):
    with a.e.db.transaction(a.e.tenant) as conn:
        claim = conn.execute(
            "SELECT * FROM inv.tool_claims WHERE command_id=%s",
            (a.command["commandId"],),
        ).fetchone()
    receipt = {
        "receiptId": str(uuid4()),
        "claimId": str(claim["claim_id"]),
        "commandId": a.command["commandId"],
        "tenantId": a.e.tenant,
        "projectId": a.e.project,
        "runId": a.run["runId"],
        "nodeId": a.e.node,
        "recoveryEpoch": a.e.epoch,
        "planDigest": claim["plan_digest"],
        "containerId": "b" * 64,
        "stopped": True,
        "processStarted": True,
        "exitCode": 0,
        "reason": "exited",
        "finishedAt": datetime.now(timezone.utc).isoformat(),
        "allocations": allocations(a),
        **changes,
    }
    # Synthetic trusted Node transport in DB tests; real mTLS exercised below.
    NodeReceiptStore(a.e.db).record(a.node, receipt)
    assert active(a) == 0


def complete(a):
    return a.results.complete(
        a.e.tenant,
        a.e.project,
        a.run["runId"],
        a.command["commandId"],
        expected_version=a.run["version"],
    )


def test_released_resources_allow_only_prepared_verified_result_and_one_commit(result):
    a = result
    assert a.run["attempt"] == 1
    prepare(a)
    assert count(a, "evidence") == count(a, "result_completions") == 0
    stopped(a)
    with ThreadPoolExecutor(max_workers=5) as pool:
        outcomes = list(pool.map(lambda _: complete(a), range(5)))
    assert all(r == outcomes[0] and r["state"] == "succeeded" for r in outcomes)
    assert count(a, "evidence") == count(a, "result_completions") == 1
    assert prepare(a)["replayed"]
    with pytest.raises(DomainError, match="STORE-0007"):
        a.storage.collect(a.e.tenant, a.e.project, a.oid)


def test_crash_after_reservation_has_one_attempt_and_cannot_reexecute(result):
    a = result
    expire_worker(a)
    observed = DeliveryQueue(a.e.db).acquire(a.e.tenant)
    assert observed.operation == "observe" and count(a, "execution_attempts") == 1
    assert a.e.runs.get(a.e.tenant, a.run["runId"])["attempt"] == 1


@pytest.mark.parametrize("missing", ["output", "receipt"])
def test_missing_output_or_receipt_never_succeeds(result, missing):
    a = result
    if missing == "output":
        stopped(a)
    else:
        prepare(a)
    with pytest.raises(DomainError, match="VERIFY-0021"):
        complete(a)
    assert count(a, "evidence") == 0


def test_stop_before_prepare_cannot_introduce_late_output(result):
    a = result
    stopped(a)
    with pytest.raises(DomainError, match="LEASE-0002"):
        prepare(a)
    assert count(a, "result_commitments") == 0


@pytest.mark.parametrize(
    "outcome",
    [
        {"exitCode": 7},
        {"reason": "cancelled"},
        {"reason": "timeout"},
        {"reason": "recovered"},
        {"processStarted": False},
    ],
)
def test_unconfirmed_or_failed_application_never_succeeds(result, outcome):
    prepare(result)
    stopped(result, **outcome)
    with pytest.raises(DomainError, match="VERIFY-0022"):
        complete(result)
    assert count(result, "evidence") == 0


@pytest.mark.parametrize("state", ["cancelled", "failed", "recovering"])
def test_cancel_and_recovery_revoke_prepared_completion(result, state):
    a = result
    prepare(a)
    a.e.runs.transition(
        a.e.tenant, a.run["runId"], state, expected_version=a.run["version"]
    )
    stopped(a)
    with pytest.raises(DomainError, match="GRAPH-0003"):
        complete(a)
    assert count(a, "evidence") == 0


def test_output_identity_scope_policy_and_fence_are_bound(result):
    a = result
    for field, value in [
        ("inputSha256", "f" * 64),
        ("policyDecisionId", "forged"),
        ("outputSha256", "f" * 64),
        ("tenantId", a.e.other),
    ]:
        with pytest.raises(DomainError):
            prepare(a, evidence={**a.evidence, field: value})
    with pytest.raises(DomainError):
        prepare(a, proofs={k: a.e.epoch + ":999999" for k in a.proofs})
    prepare(a)
    with pytest.raises(DomainError, match="IDEM-0001"):
        prepare(a, evidence={**a.evidence, "evidenceId": new_id("evd")})


def test_result_commit_failure_rolls_back_evidence_state_and_event(result, monkeypatch):
    import inv.results as module

    a = result
    prepare(a)
    stopped(a)
    original = module.event

    def crash(*args):
        raise RuntimeError("synthetic result commit failure")

    monkeypatch.setattr(module, "event", crash)
    with pytest.raises(RuntimeError):
        complete(a)
    assert count(a, "evidence") == count(a, "result_completions") == 0
    assert a.e.runs.get(a.e.tenant, a.run["runId"])["state"] == "running"
    assert count(a, "result_commitments") == 1 and active(a) == 0
    monkeypatch.setattr(module, "event", original)
    assert complete(a)["state"] == "succeeded"


def test_preparation_rollback_does_not_leave_a_pin(result, monkeypatch):
    import inv.results as module

    def crash(*args):
        raise RuntimeError("synthetic preparation failure")

    monkeypatch.setattr(module, "event", crash)
    with pytest.raises(RuntimeError):
        prepare(result)
    assert count(result, "result_commitments") == 0
    result.storage.collect(result.e.tenant, result.e.project, result.oid)


def test_corruption_after_prepare_blocks_completion(result):
    a = result
    prepare(a)
    stopped(a)
    path = a.storage.provider.root / object_key(a.oid)
    path.chmod(0o600)
    path.write_bytes(b"tampered")
    path.chmod(0o400)
    with pytest.raises(DomainError):
        complete(a)
    assert count(a, "evidence") == 0


def test_result_pin_has_database_guard_and_tenant_isolation(result):
    a = result
    prepare(a)
    with pytest.raises(psycopg.errors.CheckViolation):
        with a.e.db.transaction(a.e.tenant) as conn:
            conn.execute(
                "UPDATE inv.storage_objects SET state='deleting' WHERE object_id=%s",
                (a.oid,),
            )
    with a.e.db.transaction(a.e.other) as conn:
        for table in ["execution_attempts", "result_commitments", "result_completions"]:
            assert not conn.execute(
                psycopg.sql.SQL("SELECT 1 FROM inv.{}").format(
                    psycopg.sql.Identifier(table)
                )
            ).fetchall()


def test_epoch_change_rejects_old_prepared_result(result):
    a = result
    prepare(a)
    stopped(a)
    epoch = str(uuid4())
    with psycopg.connect(a.e.owner) as conn:
        conn.execute("UPDATE inv.control_epoch SET epoch=%s", (epoch,))
    a.results = ResultStore(
        Database(a.e.runtime, recovery_epoch=epoch), a.storage.provider
    )
    with pytest.raises(DomainError, match="LEASE-0004"):
        complete(a)


def test_gc_and_result_prepare_serialize_without_dangling_pin(result):
    a = result

    def seal():
        try:
            prepare(a)
            return "sealed"
        except DomainError:
            return "unavailable"

    def collect():
        try:
            a.storage.collect(a.e.tenant, a.e.project, a.oid)
            return "deleted"
        except DomainError:
            return "pinned"

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.submit(seal), pool.submit(collect)
        assert (first.result(), second.result()) in {
            ("sealed", "pinned"),
            ("unavailable", "deleted"),
        }


def test_real_mtls_stop_then_verifier_evidence_completion(remote, storage):
    a = remote
    prepare_queue(a)
    attempt = a.queue.acquire(a.e.tenant)
    a.run = a.e.runs.get(a.e.tenant, a.run["runId"])
    a.results = ResultStore(a.e.db, storage.provider)
    a.oid, a.evidence = output(a, storage)
    # The test verifier supplies synthetic bytes before stop. This does not
    # claim container output extraction or a real business verifier integration.
    prepare(a)
    delivered = a.delivery.deliver(a.node, attempt.envelope)
    assert delivered["receipt"]["exitCode"] == 0 and active(a) == 0
    assert a.queue.finish(attempt) == "stopped"
    assert complete(a)["state"] == "succeeded"
