import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import sys
import pytest
from inv.dispatch import DeliveryWorker
from inv.errors import DomainError
from inv.output_ingestion import OutputIngestion, output_bytes
from inv.snapshots import SnapshotStore, object_key
from test_approvals import approval, count
from test_node_runtime import node_runtime, active, container
from test_node_delivery import remote
from test_dispatch_node import prepare_queue
from test_snapshots import storage

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(sys.platform != "linux", reason="Linux private provider"),
]


def prepare(a, s):
    a.workload["command"] = ["/probe", "output"]
    prepare_queue(a)
    return DeliveryWorker(a.e.db, a.delivery, output_provider=s.provider)


def force_due(a):
    with a.e.db.transaction(a.e.tenant) as conn:
        conn.execute(
            "UPDATE inv.output_ingestions SET next_attempt_at=clock_timestamp() WHERE command_id=%s",
            (a.command["commandId"],),
        )


def test_real_stdout_stderr_hashes_reach_evidence_and_success(remote, storage):
    a = remote
    worker = prepare(a, storage)
    assert worker.once(a.e.tenant) == "stopped"
    assert a.e.runs.get(a.e.tenant, a.run["runId"])["state"] == "succeeded"
    assert active(a) == 0 and container(a) is None
    with a.e.db.transaction(a.e.tenant) as conn:
        receipt = conn.execute(
            "SELECT envelope FROM inv.node_stop_receipts WHERE command_id=%s",
            (a.command["commandId"],),
        ).fetchone()["envelope"]
        committed = conn.execute(
            "SELECT object_id,envelope FROM inv.result_commitments WHERE command_id=%s",
            (a.command["commandId"],),
        ).fetchone()
    data = output_bytes(receipt)
    artifact = json.loads(data)
    assert base64.b64decode(artifact["stdout"]) == b"actual-node-output\n"
    assert base64.b64decode(artifact["stderr"]) == b"actual-node-stderr\n"
    with storage.provider.locked() as files:
        assert (
            files.read(
                object_key(committed["object_id"]), hashlib.sha256(data).hexdigest(), len(data)
            )
            == data
        )
    assert committed["envelope"]["outputSha256"] == hashlib.sha256(data).hexdigest()
    assert count(a, "result_completions") == count(a, "evidence") == 1
    assert worker.once(a.e.tenant) == "idle"


def test_restart_after_receipt_before_publication_finishes_without_execution(remote, storage):
    a = remote
    prepare(a, storage)
    legacy = DeliveryWorker(a.e.db, a.delivery)
    assert legacy.once(a.e.tenant) == "stopped" and active(a) == 0
    assert a.e.runs.get(a.e.tenant, a.run["runId"])["state"] == "running"
    resumed = DeliveryWorker(a.e.db, a.delivery, output_provider=storage.provider)
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: resumed.once(a.e.tenant), range(4)))
    assert a.e.runs.get(a.e.tenant, a.run["runId"])["state"] == "succeeded"
    assert count(a, "tool_claims") == count(a, "result_completions") == count(a, "evidence") == 1
    assert container(a) is None


def test_publication_crash_reuses_ready_object(remote, storage, monkeypatch):
    a = remote
    worker = prepare(a, storage)
    original = SnapshotStore.finalize

    def crash(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("synthetic crash after publication")

    monkeypatch.setattr(SnapshotStore, "finalize", crash)
    assert worker.once(a.e.tenant) == "stopped"
    assert active(a) == 0 and count(a, "result_completions") == 0
    monkeypatch.setattr(SnapshotStore, "finalize", original)
    force_due(a)
    assert worker.once(a.e.tenant) == "completed"
    assert count(a, "result_completions") == 1 and count(a, "storage_objects") == 1


def test_output_retry_budget_stops_at_three_and_never_reexecutes(remote, storage, monkeypatch):
    a = remote
    worker = prepare(a, storage)

    def unavailable(*args, **kwargs):
        raise DomainError("STORE-0001", "synthetic unavailable provider")

    monkeypatch.setattr(SnapshotStore, "begin", unavailable)
    assert worker.once(a.e.tenant) == "stopped"
    for expected in ("retry", "failed"):
        force_due(a)
        assert worker.once(a.e.tenant) == expected
    assert worker.once(a.e.tenant) == "idle"
    assert a.e.runs.get(a.e.tenant, a.run["runId"])["state"] == "failed"
    assert count(a, "tool_claims") == 1 and active(a) == 0 and count(a, "evidence") == 0
    with a.e.db.transaction(a.e.tenant) as conn:
        assert (
            conn.execute(
                "SELECT attempts FROM inv.output_ingestions WHERE command_id=%s",
                (a.command["commandId"],),
            ).fetchone()["attempts"]
            == 3
        )


def test_output_overflow_is_a_failed_process_without_success_evidence(remote, storage):
    a = remote
    a.workload["command"] = ["/probe", "overflow"]
    prepare_queue(a)
    worker = DeliveryWorker(a.e.db, a.delivery, output_provider=storage.provider)
    assert worker.once(a.e.tenant) == "stopped"
    assert a.e.runs.get(a.e.tenant, a.run["runId"])["state"] == "failed"
    assert count(a, "evidence") == 0 and active(a) == 0
