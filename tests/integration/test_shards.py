from concurrent.futures import ThreadPoolExecutor
from copy import copy, deepcopy
from dataclasses import replace
from uuid import uuid4
import pytest
from inv.dispatch import DeliveryWorker
from inv.dispatch import DeliveryQueue
from inv.approvals import Principal
from inv.errors import DomainError
from inv.leases import Allocation
from inv.policy import action_digest
from inv.shards import ShardAdmission, ShardRuntime
from inv.results import ResultStore
from test_approvals import approval, request, decide, challenge, dispatch, count
from test_node_runtime import node_runtime
from test_node_delivery import remote
from test_postgres import planned
from test_tool_admission import inputs
from test_snapshots import storage
from test_results import output

pytestmark = pytest.mark.postgres


def active(a):
    with a.e.db.transaction(a.e.tenant) as conn:
        return conn.execute(
            "SELECT count(*) AS n FROM inv.resource_leases WHERE released_at IS NULL"
        ).fetchone()["n"]


def admissions(a):
    shards = []
    for index in range(2):
        child = copy(a)
        child.run = planned(a.e)
        child.workload = deepcopy(a.workload)
        child.workload["command"] = ["/probe", "shard", str(index), "of", "2"]
        child.policy = {**a.policy, "actionDigest": action_digest(child.workload)}
        row = request(child, key="request:" + child.run["runId"])
        for actor in ("alice", "bob"):
            row = decide(
                child,
                row,
                actor,
                challenge(child, row, actor),
                key=child.run["runId"] + ":" + actor,
            )
        command = dispatch(child, row, key="dispatch:" + child.run["runId"])
        leases = a.e.leases.reserve(
            a.e.tenant,
            a.e.project,
            child.run["runId"],
            [Allocation(a.e.resource, 500), Allocation(a.memory, 64 * 1024 * 1024)],
            key="resources:" + child.run["runId"],
            ttl_seconds=60,
        )
        fresh = inputs(child)
        shards.append(
            ShardAdmission(
                a.node,
                command,
                child.workload,
                {l["leaseId"]: l["fencingToken"] for l in leases},
                **fresh,
            )
        )
    return shards


def test_plan_starts_two_real_isolated_shards_once_and_reports_receipts(remote):
    a = remote
    shards = admissions(a)
    runtime = ShardRuntime(a.e.db, a.profile)
    options = dict(signing_key=a.key, splittable=True)
    assert (
        runtime.enqueue(a.e.tenant, a.e.project, "plan-fixture", shards, **options)["queued"] == 2
    )
    assert runtime.enqueue(a.e.tenant, a.e.project, "plan-fixture", shards, **options)["replayed"]
    assert not runtime.status(a.e.tenant, a.e.project, "plan-fixture")["allPhysicallyStopped"]
    worker = DeliveryWorker(a.e.db, a.delivery)
    assert worker.once(a.e.tenant) == "stopped"
    assert worker.once(a.e.tenant) == "stopped"
    assert worker.once(a.e.tenant) == "idle"
    assert runtime.status(a.e.tenant, a.e.project, "plan-fixture")["allPhysicallyStopped"]
    assert count(a, "node_stop_receipts") == 2 and active(a) == 0
    status = runtime.status(a.e.tenant, a.e.project, "plan-fixture")
    assert not status["allSucceeded"] and status["resultManifest"] is None


def test_second_shard_failure_rolls_back_first_permit_and_plan(remote):
    a = remote
    shards = admissions(a)
    bad = deepcopy(shards[1].workload)
    bad["command"].append("changed-after-approval")
    shards[1] = replace(shards[1], workload=bad)
    with pytest.raises(DomainError):
        ShardRuntime(a.e.db, a.profile).enqueue(
            a.e.tenant,
            a.e.project,
            "bad-plan",
            shards,
            signing_key=a.key,
            splittable=True,
        )
    assert (
        count(a, "tool_claims") == count(a, "execution_deliveries") == count(a, "shard_plans") == 0
    )
    assert active(a) == 0
    assert count(a, "reservation_aborts") == 2
    assert all(a.e.runs.get(a.e.tenant, s.command["runId"])["state"] == "cancelled" for s in shards)


def test_conflicting_plan_replay_cannot_reclaim_committed_claims(remote):
    a = remote
    shards = admissions(a)
    runtime = ShardRuntime(a.e.db, a.profile)
    runtime.enqueue(a.e.tenant, a.e.project, "stable", shards, signing_key=a.key, splittable=True)
    bad = deepcopy(shards[1].workload)
    bad["command"].append("conflict")
    shards[1] = replace(shards[1], workload=bad)
    with pytest.raises(DomainError):
        runtime.enqueue(
            a.e.tenant, a.e.project, "stable", shards, signing_key=a.key, splittable=True
        )
    assert active(a) == 4 and count(a, "reservation_aborts") == 0
    assert count(a, "execution_deliveries") == 2


def test_concurrent_plan_submission_creates_one_set_of_claims(remote):
    a = remote
    shards = admissions(a)
    runtime = ShardRuntime(a.e.db, a.profile)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(
            pool.map(
                lambda _: runtime.enqueue(
                    a.e.tenant,
                    a.e.project,
                    "concurrent-plan",
                    shards,
                    signing_key=a.key,
                    splittable=True,
                ),
                range(4),
            )
        )
    assert sum(not r["replayed"] for r in results) == 1 and count(a, "execution_deliveries") == 2


@pytest.mark.parametrize(
    "communication,splittable", [("mpi", True), ("nccl", True), ("none", False)]
)
def test_unsupported_collectives_or_implicit_splitting_never_queue(
    remote, communication, splittable
):
    a = remote
    with pytest.raises(DomainError, match="NODE-0062"):
        ShardRuntime(a.e.db, a.profile).enqueue(
            a.e.tenant,
            a.e.project,
            "bad",
            [],
            signing_key=a.key,
            splittable=splittable,
            communication=communication,
        )
    assert count(a, "shard_plans") == 0 and count(a, "execution_deliveries") == 0


def test_shard_manifest_requires_each_committed_evidence_and_physical_result(remote, storage):
    a = remote
    shards = admissions(a)
    runtime = ShardRuntime(a.e.db, a.profile)
    runtime.enqueue(a.e.tenant, a.e.project, "results", shards, signing_key=a.key, splittable=True)
    queue = DeliveryQueue(a.e.db)
    results = ResultStore(a.e.db, storage.provider)
    for shard in shards:
        attempt = queue.acquire(a.e.tenant, command_id=shard.command["commandId"])
        child = copy(a)
        child.command = shard.command
        child.run = a.e.runs.get(a.e.tenant, shard.command["runId"])
        oid, evidence = output(child, storage)
        results.prepare(
            a.e.tenant,
            a.e.project,
            child.run["runId"],
            shard.command["commandId"],
            oid,
            evidence,
            proofs=shard.proofs,
        )
        a.delivery.deliver(a.node, attempt.envelope)
        queue.finish(attempt)
        assert runtime.status(a.e.tenant, a.e.project, "results")["resultManifest"] is None
        results.complete(
            a.e.tenant,
            a.e.project,
            child.run["runId"],
            shard.command["commandId"],
            expected_version=child.run["version"],
        )
    status = runtime.status(a.e.tenant, a.e.project, "results")
    assert status["allSucceeded"] and status["allPhysicallyStopped"]
    assert len(status["resultManifest"]) == 2 and len(status["resultManifestSha256"]) == 64
    assert all(s["evidenceId"] for s in status["shards"])
    assert runtime.reconcile_failures(a.e.tenant, a.e.project, "results")["failedRuns"] == []


def test_plan_cancel_checks_current_permission_and_rolls_back_all_members(remote, monkeypatch):
    import inv.shards as module

    a = remote
    shards = admissions(a)
    runtime = ShardRuntime(a.e.db, a.profile)
    runtime.enqueue(
        a.e.tenant,
        a.e.project,
        "cancel-all",
        shards,
        signing_key=a.key,
        splittable=True,
    )
    with pytest.raises(DomainError, match="AUTH-0030"):
        runtime.cancel(Principal(a.e.tenant, "outsider"), a.e.project, "cancel-all", key="denied")
    original = module.event

    def crash(*args):
        raise RuntimeError("synthetic plan cancellation failure")

    monkeypatch.setattr(module, "event", crash)
    with pytest.raises(RuntimeError):
        runtime.cancel(a.people["requester"], a.e.project, "cancel-all", key="cancel")
    assert all(
        s["state"] == "scheduled"
        for s in runtime.status(a.e.tenant, a.e.project, "cancel-all")["shards"]
    )
    monkeypatch.setattr(module, "event", original)
    first = runtime.cancel(a.people["requester"], a.e.project, "cancel-all", key="cancel")
    assert len(first["cancelledRuns"]) == 2
    assert runtime.cancel(a.people["requester"], a.e.project, "cancel-all", key="cancel") == first
    assert active(a) == 4  # Request is not a physical stop acknowledgement.
    queue = DeliveryQueue(a.e.db)
    assert queue.acquire(a.e.tenant).operation == "cancel"


def test_nonzero_shard_result_is_reconciled_without_retry(remote):
    a = remote
    shards = admissions(a)
    runtime = ShardRuntime(a.e.db, a.profile)
    runtime.enqueue(a.e.tenant, a.e.project, "failure", shards, signing_key=a.key, splittable=True)
    attempt = DeliveryQueue(a.e.db).acquire(a.e.tenant, command_id=shards[0].command["commandId"])
    # Trusted receipt fixture isolates failure reconciliation. Real nonzero
    # process -> mTLS receipts are separately tested by test_node_runtime.
    import base64, json
    from datetime import datetime, timezone
    from inv.node_execution import NodeReceiptStore

    payload = json.loads(base64.b64decode(attempt.envelope["payload"]))
    c = payload["claim"]
    receipt = {
        k: c[k]
        for k in [
            "claimId",
            "commandId",
            "tenantId",
            "projectId",
            "runId",
            "nodeId",
            "recoveryEpoch",
            "planDigest",
        ]
    }
    receipt.update(
        receiptId=str(uuid4()),
        containerId="f" * 64,
        stopped=True,
        processStarted=True,
        exitCode=7,
        reason="exited",
        finishedAt=datetime.now(timezone.utc).isoformat(),
        allocations=payload["allocations"],
    )
    NodeReceiptStore(a.e.db).record(a.node, receipt)
    first = runtime.reconcile_failures(a.e.tenant, a.e.project, "failure")
    assert first["failedRuns"] == [c["runId"]]
    assert runtime.reconcile_failures(a.e.tenant, a.e.project, "failure")["failedRuns"] == []
    assert count(a, "execution_attempts") == 1
    assert not runtime.status(a.e.tenant, a.e.project, "failure")["allSucceeded"]
