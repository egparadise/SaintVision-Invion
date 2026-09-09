from concurrent.futures import ThreadPoolExecutor
from copy import copy, deepcopy
from dataclasses import replace
from uuid import uuid4
import pytest
from inv.dispatch import DeliveryWorker
from inv.errors import DomainError
from inv.leases import Allocation
from inv.policy import action_digest
from inv.shards import ShardAdmission, ShardRuntime
from test_approvals import approval, request, decide, challenge, dispatch, count
from test_node_runtime import node_runtime
from test_node_delivery import remote
from test_postgres import planned
from test_tool_admission import inputs

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
                **fresh
            )
        )
    return shards


def test_plan_starts_two_real_isolated_shards_once_and_reports_receipts(remote):
    a = remote
    shards = admissions(a)
    runtime = ShardRuntime(a.e.db, a.profile)
    options = dict(signing_key=a.key, splittable=True)
    assert (
        runtime.enqueue(a.e.tenant, a.e.project, "plan-fixture", shards, **options)[
            "queued"
        ]
        == 2
    )
    assert runtime.enqueue(a.e.tenant, a.e.project, "plan-fixture", shards, **options)[
        "replayed"
    ]
    assert not runtime.status(a.e.tenant, a.e.project, "plan-fixture")[
        "allPhysicallyStopped"
    ]
    worker = DeliveryWorker(a.e.db, a.delivery)
    assert worker.once(a.e.tenant) == "stopped"
    assert worker.once(a.e.tenant) == "stopped"
    assert worker.once(a.e.tenant) == "idle"
    assert runtime.status(a.e.tenant, a.e.project, "plan-fixture")[
        "allPhysicallyStopped"
    ]
    assert count(a, "node_stop_receipts") == 2 and active(a) == 0


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
        count(a, "tool_claims")
        == count(a, "execution_deliveries")
        == count(a, "shard_plans")
        == 0
    )
    assert active(a) == 4


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
    assert (
        sum(not r["replayed"] for r in results) == 1
        and count(a, "execution_deliveries") == 2
    )


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
