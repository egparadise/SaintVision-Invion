"""Actual queue -> mTLS -> Go -> Docker -> receipt/lease closure in isolated CI."""

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import pytest
from inv.dispatch import DeliveryQueue, DeliveryWorker
from inv.leases import Allocation
from inv.policy import action_digest
from test_approvals import approval, approved, dispatch, count
from test_tool_admission import claim
from test_node_delivery import remote
from test_node_runtime import node_runtime, active, container
from test_dispatch_queue import row, expire_worker, cancel

pytestmark = pytest.mark.postgres


def prepare_queue(a):
    a.policy["actionDigest"] = action_digest(a.workload)
    a.command = dispatch(a, approved(a))
    a.leases = a.e.leases.reserve(
        a.e.tenant,
        a.e.project,
        a.run["runId"],
        [Allocation(a.e.resource, 500), Allocation(a.memory, 64 * 1024 * 1024)],
        key="queued-runtime",
        ttl_seconds=60,
    )
    a.proofs = {lease["leaseId"]: lease["fencingToken"] for lease in a.leases}
    result = claim(a, queue_signing_key=a.key)
    assert not result.may_start
    a.queue = DeliveryQueue(a.e.db)
    return DeliveryWorker(a.e.db, a.delivery)


def test_queued_execution_commits_one_physical_receipt_and_closes_once(remote):
    a = remote
    worker = prepare_queue(a)
    assert worker.once(a.e.tenant) == "stopped"
    assert active(a) == 0 and row(a)["phase"] == "stopped"
    assert count(a, "node_stop_receipts") == 1 and container(a) is None
    assert worker.once(a.e.tenant) == "idle"
    run = a.e.runs.get(a.e.tenant, a.run["runId"])
    assert run["state"] == "running" and run["attempt"] == 1


def test_restart_recovers_lost_tls_response_by_observation_without_new_execution(
    remote,
):
    a = remote
    worker = prepare_queue(a)
    first = a.queue.acquire(a.e.tenant)
    channel = a.delivery.channels.snapshot(a.node)
    physical = a.client.exchange(channel, first.envelope)
    assert physical["receipt"]["stopped"] and active(a) == 2
    # Simulate CP crash after Node committed receipt but before receiving/storing it.
    expire_worker(a)
    recovered = DeliveryQueue(a.e.db).acquire(a.e.tenant)
    assert recovered.operation == "observe"
    result = a.delivery.deliver(a.node, recovered.envelope, observation_only=True)
    assert result["receipt"] == physical["receipt"] and result["duplicate"]
    assert a.queue.finish(recovered) == "stopped" and active(a) == 0
    assert worker.once(a.e.tenant) == "idle"


def test_worker_cancel_interrupts_inflight_execution_without_waiting_for_worker_lease(
    remote,
):
    a = remote
    a.workload.update(command=["/probe", "sleep", "10"], timeoutSeconds=15)
    worker = prepare_queue(a)
    with ThreadPoolExecutor(max_workers=2) as pool:
        running = pool.submit(worker.once, a.e.tenant)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            observed = container(a)
            if observed and observed["State"]["Running"]:
                break
            time.sleep(0.05)
        else:
            pytest.fail("Synthetic queued container did not start")
        cancel(a)
        started = time.monotonic()
        assert DeliveryWorker(a.e.db, a.delivery).once(a.e.tenant) == "stopped"
        assert running.result(timeout=10) in {"superseded", "stopped"}
        assert time.monotonic() - started < 10
    assert active(a) == 0 and container(a) is None and row(a)["phase"] == "stopped"
    assert a.e.runs.get(a.e.tenant, a.run["runId"])["state"] == "cancelled"


def test_crash_before_transmission_and_pre_cancel_do_not_execute_or_release(remote):
    a = remote
    worker = prepare_queue(a)
    first = a.queue.acquire(a.e.tenant)
    assert first.operation == "execute"
    expire_worker(a)
    assert worker.once(a.e.tenant) == "uncertain"
    assert active(a) == 2 and container(a) is None and count(a, "node_stop_receipts") == 0
    assert not list((a.path / "state").glob("*.intent"))


def test_explicit_worker_cli_processes_existing_queue_once(remote):
    a = remote
    prepare_queue(a)
    config = a.path / "worker.json"
    config.write_text(
        json.dumps({"tenantId": a.e.tenant, "tls": a.client_files}, default=str),
        "utf-8",
    )
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "-m", "inv.worker", "--once"],
        cwd=root,
        env={
            **os.environ,
            "PYTHONPATH": str(root / "services/control-plane/src"),
            "INV_WORKER_CONFIG": str(config),
            "INV_RUNTIME_DSN": a.e.runtime,
            "INV_RECOVERY_EPOCH": a.e.epoch,
        },
        capture_output=True,
        text=True,
        timeout=45,
    )
    assert result.returncode == 0  # Never print configuration or credential-bearing diagnostics.
    assert result.stdout.strip() == "stopped" and not result.stderr
    assert row(a)["phase"] == "stopped" and active(a) == 0


@pytest.mark.parametrize("reserved", [False, True])
def test_prestart_cancel_reclaims_only_after_node_tombstone(remote, reserved):
    a = remote
    worker = prepare_queue(a)
    envelope = row(a)["envelope"] if "envelope" in row(a) else None
    if reserved:
        attempt = a.queue.acquire(a.e.tenant)
        envelope = attempt.envelope
    cancel(a)
    assert active(a) == 2 and count(a, "node_stop_receipts") == 0
    assert worker.once(a.e.tenant) == "stopped"
    assert active(a) == 0 and count(a, "node_stop_receipts") == 1
    with a.e.db.transaction(a.e.tenant) as conn:
        receipt = conn.execute(
            "SELECT envelope FROM inv.node_stop_receipts WHERE command_id=%s",
            (a.command["commandId"],),
        ).fetchone()["envelope"]
    assert receipt["reason"] == "not_started" and receipt["containerId"] == ""
    assert not receipt["processStarted"] and container(a) is None
    if reserved:
        channel = a.delivery.channels.snapshot(a.node)
        delayed = a.client.exchange(channel, envelope)
        assert delayed["receipt"] == receipt and delayed["duplicate"]
        assert container(a) is None
