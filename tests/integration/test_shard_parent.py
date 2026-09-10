from concurrent.futures import ThreadPoolExecutor
import pytest
from inv.control import Control
from inv.dispatch import DeliveryWorker
from inv.shards import ShardRuntime
from test_approvals import approval, count
from test_node_runtime import node_runtime
from test_node_delivery import remote
from test_snapshots import storage
from test_shards import admissions, active

pytestmark = pytest.mark.postgres


def plan(a, commands=None):
    shards = admissions(a, commands)
    runtime = ShardRuntime(a.e.db, a.profile)
    result = runtime.enqueue(
        a.e.tenant, a.e.project, "parent-plan", shards, signing_key=a.key, splittable=True
    )
    return runtime, result["parentRunId"], shards


def test_actual_shard_outputs_complete_parent_with_one_aggregate_evidence(remote, storage):
    a = remote
    runtime, parent, shards = plan(a)
    worker = DeliveryWorker(a.e.db, a.delivery, output_provider=storage.provider)
    assert worker.once(a.e.tenant, command_id=shards[0].command["commandId"]) == "stopped"
    assert a.e.runs.get(a.e.tenant, parent)["state"] == "running"
    assert worker.once(a.e.tenant, command_id=shards[1].command["commandId"]) == "stopped"
    status = runtime.status(a.e.tenant, a.e.project, "parent-plan")
    assert (
        status["parentState"] == "succeeded"
        and status["allSucceeded"]
        and status["allPhysicallyStopped"]
    )
    assert status["aggregateManifestSha256"] is not None
    assert count(a, "evidence") == 3 and count(a, "shard_completions") == 1 and active(a) == 0
    assert worker.once(a.e.tenant) == "idle"


def test_failure_reaches_parent_and_cancels_unstarted_sibling(remote, storage):
    a = remote
    runtime, parent, shards = plan(a, [["/probe", "fail"], ["/probe", "output"]])
    worker = DeliveryWorker(a.e.db, a.delivery, output_provider=storage.provider)
    assert worker.once(a.e.tenant, command_id=shards[0].command["commandId"]) == "stopped"
    assert a.e.runs.get(a.e.tenant, parent)["state"] == "failed"
    assert a.e.runs.get(a.e.tenant, shards[1].command["runId"])["state"] == "cancelled"
    assert active(a) == 2
    assert worker.once(a.e.tenant, command_id=shards[1].command["commandId"]) == "stopped"
    assert active(a) == 0 and count(a, "evidence") == 0
    assert runtime.status(a.e.tenant, a.e.project, "parent-plan")["allPhysicallyStopped"]


def test_parent_browser_cancel_is_atomic_and_reports_child_resources_pending(remote):
    a = remote
    runtime, parent, shards = plan(a)
    control = Control(a.e.db)
    prior = control.get(a.people["requester"], a.e.project, parent)
    assert prior["resourceReleasePending"]
    result = control.cancel(
        a.people["requester"], a.e.project, parent, prior["version"], "parent-cancel"
    )
    assert result["state"] == "cancelled" and result["resourceReleasePending"] and active(a) == 4
    assert (
        control.cancel(
            a.people["requester"], a.e.project, parent, prior["version"], "parent-cancel"
        )
        == result
    )
    worker = DeliveryWorker(a.e.db, a.delivery)
    for shard in shards:
        assert worker.once(a.e.tenant, command_id=shard.command["commandId"]) == "stopped"
    assert not control.get(a.people["requester"], a.e.project, parent)["resourceReleasePending"]


def test_parent_reconciliation_resumes_after_children_complete_and_is_concurrent_safe(
    remote, storage, monkeypatch
):
    a = remote
    runtime, parent, shards = plan(a)
    worker = DeliveryWorker(a.e.db, a.delivery, output_provider=storage.provider)
    monkeypatch.setattr(worker.parents, "once", lambda *a, **k: "idle")
    for shard in shards:
        assert worker.once(a.e.tenant, command_id=shard.command["commandId"]) == "stopped"
    assert a.e.runs.get(a.e.tenant, parent)["state"] == "running"
    resumed = DeliveryWorker(a.e.db, a.delivery, output_provider=storage.provider)
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: resumed.once(a.e.tenant), range(4)))
    assert a.e.runs.get(a.e.tenant, parent)["state"] == "succeeded"
    assert count(a, "shard_completions") == 1 and count(a, "evidence") == 3
