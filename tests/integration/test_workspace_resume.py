"""Real recovery -> fresh approval -> signed Node tmpfs -> Git -> checkpoint."""

import base64
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import os
import sys
from uuid import uuid4
import pytest
import psycopg
from inv.dispatch import DeliveryWorker
from inv.errors import DomainError
from inv.leases import Allocation
from inv.output_ingestion import OutputIngestion
from inv.policy import action_digest
from inv.workspace_files import PrivateTree, RestoreGenerations, WorkingGenerations, decode_snapshot
from inv.workspace_recovery import WorkspaceRecovery
from inv.workspace_resume import WorkspaceResume
from test_approvals import approval, request, challenge, decide, dispatch, count
from test_node_runtime import node_runtime, active, container
from test_node_delivery import remote
from test_dispatch_node import prepare_queue
from test_tool_admission import gateway, inputs
from test_snapshots import storage
from test_results import result
from test_workspace_recovery import workspace
from test_workspace_checkout import checkout, publish

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(sys.platform != "linux", reason="Linux bounded Workspace execution"),
]


def freeze(a, *, resume_id=None):
    a.resume = WorkspaceResume(a.e.db, a.working)
    a.resume_id = resume_id or getattr(a, "resume_id", str(uuid4()))
    a.base_workload = getattr(a, "base_workload", deepcopy(a.workload))
    a.base_workload["workspaceId"] = a.workspace_id
    return a.resume.prepare(
        a.e.tenant,
        a.e.project,
        a.run["runId"],
        a.checkout_id,
        a.resume_id,
        "resumed-step",
        a.base_workload,
        expected_version=a.run["version"],
    )


def authorize(a, prefix="resume"):
    a.policy["actionDigest"] = action_digest(a.workload)
    row = request(a, key=prefix + "-request")
    for actor in ["alice", "bob"]:
        row = decide(a, row, actor, challenge(a, row, actor), key=prefix + "-decision:" + actor)
    a.command = dispatch(a, row, key=prefix + "-dispatch")
    return row


def enqueue(a, **overrides):
    options = {**inputs(a), "signing_key": a.key, "key": "resume-enqueue"}
    options.update(overrides)
    response = a.resume.enqueue(
        a.node,
        a.command,
        a.workload,
        [
            Allocation(a.e.resource, a.workload["resources"]["cpuMillis"]),
            Allocation(a.memory, a.workload["resources"]["memoryBytes"]),
        ],
        a.profile,
        **options,
    )
    a.leases = response["leases"]
    a.proofs = {l["leaseId"]: l["fencingToken"] for l in a.leases}
    return response


@pytest.fixture
def resumed(remote, storage, tmp_path):
    return build_resume(remote, storage, tmp_path)


def build_resume(remote, storage, tmp_path, attack=None):
    a = remote
    prepare_queue(a)
    first = a.queue.acquire(a.e.tenant)
    a.run = a.e.runs.get(a.e.tenant, a.run["runId"])
    a.workspace_id = a.workload["workspaceId"]
    source = tmp_path / "source"
    source.mkdir(mode=0o700)
    (source / "src").mkdir(mode=0o700)
    (source / "src/main.py").write_bytes(b"print('checkpoint')\n")
    (source / "src/main.py").chmod(0o600)
    root = tmp_path / "restores"
    root.mkdir(mode=0o700)
    a.recovery = WorkspaceRecovery(storage, RestoreGenerations(root))
    a.recovery.checkpoint(
        a.e.tenant,
        a.e.project,
        a.run["runId"],
        a.workspace_id,
        "files-v1",
        PrivateTree(source),
        proofs=a.proofs,
    )
    a.delivery.deliver(a.node, first.envelope)
    assert a.queue.finish(first) == "stopped" and active(a) == 0
    a.run = a.e.runs.transition(
        a.e.tenant, a.run["runId"], "recovering", expected_version=a.run["version"]
    )
    rid = str(uuid4())
    a.restored = a.recovery.restore(
        a.e.tenant,
        a.e.project,
        a.run["runId"],
        a.workspace_id,
        1,
        "files-v1",
        rid,
        expected_version=a.run["version"],
    )
    root = tmp_path / "checkouts"
    root.mkdir(mode=0o700)
    a.working = WorkingGenerations(root)
    a.checkout_id = str(uuid4())
    a.checkout = a.recovery.checkout(
        a.e.tenant,
        a.e.project,
        a.run["runId"],
        rid,
        a.checkout_id,
        a.working,
        expected_version=a.run["version"],
    )
    a.workload.update(command=["/probe", "workspace"], timeoutSeconds=10)
    if attack:
        a.workload["command"].append(attack)
    a.workload = freeze(a)["workload"]
    a.storage = storage
    return a


def test_fresh_approved_step_executes_real_git_and_commits_restorable_files(resumed):
    a = resumed
    local_file = a.working.root / a.checkout["generation"] / "files/src/main.py"
    local_file.write_bytes(b"editor change after frozen approval input")
    authorize(a)
    with ThreadPoolExecutor(max_workers=3) as pool:
        replies = list(pool.map(lambda _: enqueue(a), range(3)))
    assert all(r == replies[0] for r in replies)
    worker = DeliveryWorker(a.e.db, a.delivery, output_provider=a.storage.provider)
    assert worker.once(a.e.tenant) == "stopped"
    run = a.e.runs.get(a.e.tenant, a.run["runId"])
    assert run["state"] == "succeeded" and run["attempt"] == 2
    assert active(a) == 0 and container(a) is None
    assert local_file.read_bytes() == b"editor change after frozen approval input"
    raw = a.storage.restore(a.e.tenant, a.e.project, run["runId"], 2, "resumed-step")
    manifest, content = decode_snapshot(raw, a.workspace_id)
    assert content["src/main.py"] == b"print('resumed')\n"
    commit = content[".git/refs/heads/main"].strip().decode()
    assert len(commit) == 40 and int(commit, 16) > 0
    assert content[".git/HEAD"] == b"ref: refs/heads/main\n"
    assert (
        a.recovery.generations.root.joinpath(
            a.restored["generation"], "files/src/main.py"
        ).read_bytes()
        == b"print('checkpoint')\n"
    )
    with a.e.db.transaction(a.e.tenant) as conn:
        receipt = conn.execute(
            "SELECT envelope FROM inv.node_stop_receipts WHERE command_id=%s",
            (a.command["commandId"],),
        ).fetchone()["envelope"]
    artifact = json.loads(base64.b64decode(receipt["output"]["data"]))
    assert base64.b64decode(artifact["stdout"]).strip().decode() == commit
    assert count(a, "execution_attempts") == 2 and count(a, "result_completions") == 1
    assert worker.once(a.e.tenant) == "idle"
    # Replay after success observes the same completed command and cannot run again.
    assert enqueue(a, policy=None, runtime=None) == replies[0]


def test_restart_after_node_receipt_recovers_workspace_result_without_second_execution(resumed):
    a = resumed
    authorize(a)
    enqueue(a)
    assert DeliveryWorker(a.e.db, a.delivery).once(a.e.tenant) == "stopped"
    assert active(a) == 0 and a.e.runs.get(a.e.tenant, a.run["runId"])["state"] == "running"
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(
            pool.map(
                lambda _: OutputIngestion(a.e.db, a.storage.provider).once(a.e.tenant), range(3)
            )
        )
    assert a.e.runs.get(a.e.tenant, a.run["runId"])["state"] == "succeeded"
    assert count(a, "execution_attempts") == 2 and count(a, "result_completions") == 1
    raw = a.storage.restore(a.e.tenant, a.e.project, a.run["runId"], 2, "resumed-step")
    assert decode_snapshot(raw, a.workspace_id)[1]["src/main.py"] == b"print('resumed')\n"


def test_failed_admission_rolls_back_new_reservations_and_cancel_never_starts(resumed):
    a = resumed
    authorize(a)
    with pytest.raises(DomainError):
        enqueue(a, policy=None)
    assert active(a) == 0 and count(a, "tool_claims") == 1
    enqueue(a)
    run = a.e.runs.get(a.e.tenant, a.run["runId"])
    a.e.runs.transition(a.e.tenant, run["runId"], "cancelled", expected_version=run["version"])
    assert (
        DeliveryWorker(a.e.db, a.delivery, output_provider=a.storage.provider).once(a.e.tenant)
        == "stopped"
    )
    assert (
        active(a) == 0
        and count(a, "execution_attempts") == 1
        and count(a, "result_completions") == 0
    )
    with a.e.db.transaction(a.e.tenant) as conn:
        receipt = conn.execute(
            "SELECT envelope FROM inv.node_stop_receipts WHERE command_id=%s",
            (a.command["commandId"],),
        ).fetchone()["envelope"]
    assert receipt["reason"] == "not_started" and not receipt["processStarted"]


def test_frozen_checkout_replay_preserves_edits_and_rejects_changed_approval(checkout):
    a = checkout
    r = publish(a)
    a.workload = freeze(a)["workload"]
    path = a.working.root / r["generation"] / "files/src/main.py"
    path.write_bytes(b"later editor changes")
    assert freeze(a)["replayed"] and path.read_bytes() == b"later editor changes"
    changed = deepcopy(a.workload)
    changed["workspaceResume"]["inputSha256"] = "b" * 64
    a.workload = changed
    with pytest.raises(DomainError, match="AUTH-0044"):
        authorize(a)
    assert count(a, "workspace_resumptions") == 1


def test_resume_requires_current_attempt_scope_and_has_one_frozen_successor(checkout):
    a = checkout
    publish(a)
    freeze(a)
    with pytest.raises(DomainError, match="IDEM-0001"):
        freeze(a, resume_id=str(uuid4()))
    assert count(a, "workspace_resumptions") == 1
    run = a.e.runs.get(a.e.tenant, a.run["runId"])
    a.e.runs.transition(a.e.tenant, run["runId"], "cancelled", expected_version=run["version"])
    a.workload = deepcopy(a.base_workload)
    with pytest.raises(DomainError):
        authorize(a)


def test_recovery_approval_db_guard_requires_frozen_step(checkout):
    a = checkout
    with pytest.raises(psycopg.errors.CheckViolation):
        a.e.runs.transition(
            a.e.tenant, a.run["runId"], "awaiting_approval", expected_version=a.run["version"]
        )
    assert a.e.runs.get(a.e.tenant, a.run["runId"])["state"] == "recovering"


def test_workspace_resume_cannot_detach_a_child_from_its_shard_plan(checkout):
    a = checkout
    publish(a)
    with a.e.db.transaction(a.e.tenant) as conn:
        conn.execute(
            "INSERT INTO inv.shard_plans VALUES(%s,%s,'existing-plan',%s,1)",
            (a.e.tenant, a.e.project, "a" * 64),
        )
        conn.execute(
            "INSERT INTO inv.shard_commands VALUES(%s,%s,'existing-plan',0,%s,%s,%s)",
            (a.e.tenant, a.e.project, a.e.node, a.run["runId"], a.command["commandId"]),
        )
    with pytest.raises(DomainError, match="GRAPH-0005"):
        freeze(a)
    assert count(a, "workspace_resumptions") == 0


def test_resume_rejects_foreign_scope_and_stale_epoch(checkout):
    a = checkout
    publish(a)
    a.workload = freeze(a)["workload"]
    with pytest.raises(DomainError):
        a.resume.prepare(
            a.e.other,
            a.e.project,
            a.run["runId"],
            a.checkout_id,
            str(uuid4()),
            "foreign-step",
            a.base_workload,
            expected_version=a.run["version"],
        )
    with psycopg.connect(a.e.owner) as conn:
        conn.execute("UPDATE inv.control_epoch SET epoch=%s WHERE singleton", (str(uuid4()),))
    with pytest.raises(DomainError, match="LEASE-0004"):
        authorize(a)


@pytest.mark.parametrize("attack", ["symlink", "overflow"])
def test_bad_node_workspace_cannot_be_success_or_checkpoint(remote, storage, tmp_path, attack):
    a = build_resume(remote, storage, tmp_path, attack)
    authorize(a)
    enqueue(a)
    assert (
        DeliveryWorker(a.e.db, a.delivery, output_provider=a.storage.provider).once(a.e.tenant)
        == "stopped"
    )
    assert a.e.runs.get(a.e.tenant, a.run["runId"])["state"] == "failed"
    assert active(a) == 0 and count(a, "result_completions") == 0
    with pytest.raises(DomainError, match="RES-0004"):
        a.storage.restore(a.e.tenant, a.e.project, a.run["runId"], 2, "resumed-step")


def test_older_checkpoint_can_recover_failed_attempt_but_fourth_execution_is_denied(
    remote, storage, tmp_path
):
    a = build_resume(remote, storage, tmp_path, "overflow")
    authorize(a)
    enqueue(a)
    second = a.queue.acquire(a.e.tenant)
    second_result = a.delivery.deliver(a.node, second.envelope)
    assert (
        second_result["receipt"]["exitCode"] == 122 and second_result["receipt"]["processStarted"]
    )
    assert a.queue.finish(second) == "stopped" and active(a) == 0
    a.run = a.e.runs.get(a.e.tenant, a.run["runId"])
    assert a.run["attempt"] == 2
    a.run = a.e.runs.transition(
        a.e.tenant, a.run["runId"], "recovering", expected_version=a.run["version"]
    )
    rid = str(uuid4())
    a.recovery.restore(
        a.e.tenant,
        a.e.project,
        a.run["runId"],
        a.workspace_id,
        1,
        "files-v1",
        rid,
        expected_version=a.run["version"],
    )
    a.checkout_id = str(uuid4())
    checkout = a.recovery.checkout(
        a.e.tenant,
        a.e.project,
        a.run["runId"],
        rid,
        a.checkout_id,
        a.working,
        expected_version=a.run["version"],
    )
    assert checkout["sourceAttempt"] == 2 and checkout["checkpointAttempt"] == 1
    a.workload = a.resume.prepare(
        a.e.tenant,
        a.e.project,
        a.run["runId"],
        a.checkout_id,
        str(uuid4()),
        "retry-step",
        a.base_workload,
        expected_version=a.run["version"],
    )["workload"]
    assert a.workload["workspaceResume"]["checkpointAttempt"] == 1
    authorize(a, prefix="third")
    enqueue(a, key="third-enqueue")
    third = a.queue.acquire(a.e.tenant)
    third_result = a.delivery.deliver(a.node, third.envelope)
    assert third_result["receipt"]["exitCode"] == 122 and third_result["receipt"]["processStarted"]
    assert a.queue.finish(third) == "stopped" and active(a) == 0
    a.run = a.e.runs.get(a.e.tenant, a.run["runId"])
    assert a.run["attempt"] == 3 and count(a, "execution_attempts") == 3
    a.run = a.e.runs.transition(
        a.e.tenant, a.run["runId"], "recovering", expected_version=a.run["version"]
    )
    with pytest.raises(DomainError, match="GRAPH-0005"):
        a.resume.prepare(
            a.e.tenant,
            a.e.project,
            a.run["runId"],
            a.checkout_id,
            str(uuid4()),
            "fourth-step",
            a.base_workload,
            expected_version=a.run["version"],
        )
    assert active(a) == 0 and count(a, "workspace_resumptions") == 2
