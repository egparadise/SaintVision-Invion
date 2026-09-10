"""Real approved execution: PostgreSQL -> Python signer -> Go -> Linux Docker.

The CI image is built FROM scratch from this repository. Never controls a user's
Docker daemon; these tests require explicit INV_RUN_NODE_TESTS=1 opt-in.
"""

from concurrent.futures import ThreadPoolExecutor
import base64
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from uuid import uuid4

import psycopg
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from inv.errors import DomainError
from inv.ids import new_id
from inv.leases import Allocation
from inv.node_execution import NodeReceiptStore, seal_permit
from inv.policy import action_digest
from inv.sandbox import SandboxProfile
from inv.tooling import ToolGateway, NodePrincipal
from test_approvals import approval, approved, dispatch, count
from test_tool_admission import gateway, claim, inputs

pytestmark = pytest.mark.postgres


def allocations(a):
    return [
        {
            "nodeId": a.e.node,
            "kind": "cpu" if lease["resourceId"] == a.e.resource else "memory",
            "lease": lease,
        }
        for lease in a.leases
    ]


@pytest.fixture
def node_runtime(approval, tmp_path):
    if os.getenv("INV_RUN_NODE_TESTS") != "1":
        if os.getenv("CI"):
            pytest.fail("CI must enable real Node execution tests")
        pytest.skip("Real Linux Docker runtime explicitly enabled only in isolated CI")
    binary = os.environ["INV_NODE_BINARY"]
    image = os.environ["INV_NODE_IMAGE"]
    assert Path(binary).is_file() and image.startswith("sha256:")
    a = approval
    a.binary = binary
    a.workload.update(
        command=["/probe", "합성-검증🙂"], imageDigest=image, timeoutSeconds=5
    )
    a.workload["resources"].update(cpuMillis=500, memoryBytes=64 * 1024 * 1024)
    a.memory = new_id("res")
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            "UPDATE inv.resources SET capacity=1000,offered=1000 WHERE tenant_id=%s AND resource_id=%s",
            (a.e.tenant, a.e.resource),
        )
        conn.execute(
            "INSERT INTO inv.resources VALUES(%s,%s,%s,'memory',268435456,268435456)",
            (a.e.tenant, a.memory, a.e.node),
        )
    a.profile = SandboxProfile(
        "restricted:node-test:1", frozenset({image}), frozenset({"/probe"})
    )
    a.gateway = ToolGateway(a.e.db, a.profile)
    a.node = NodePrincipal(a.e.tenant, a.e.node)
    a.receipts = NodeReceiptStore(a.e.db)
    a.path = tmp_path
    a.key = Ed25519PrivateKey.generate()  # Only the public key is persisted.
    (tmp_path / "public.key").write_bytes(a.key.public_key().public_bytes_raw())
    a.args = [
        binary,
        "--tenant",
        a.e.tenant,
        "--node",
        a.e.node,
        "--epoch",
        a.e.epoch,
        "--profile",
        a.profile.version,
        "--image",
        image,
        "--executable",
        "/probe",
        "--state",
        str(tmp_path / "state"),
        "--public-key",
        str(tmp_path / "public.key"),
    ]
    return a


def prepare(a):
    a.policy["actionDigest"] = action_digest(a.workload)
    a.command = dispatch(a, approved(a))
    a.leases = a.e.leases.reserve(
        a.e.tenant,
        a.e.project,
        a.run["runId"],
        [Allocation(a.e.resource, 500), Allocation(a.memory, 64 * 1024 * 1024)],
        key="node-runtime",
        ttl_seconds=60,
    )
    a.proofs = {lease["leaseId"]: lease["fencingToken"] for lease in a.leases}
    a.admitted = claim(a)
    a.permit = seal_permit(a.admitted, allocations(a), a.key)
    a.permit_file = a.path / "permit.json"
    a.permit_file.write_text(json.dumps(a.permit), "utf-8")
    return a.args + ["--permit", str(a.permit_file)]


def execute(args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=40)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def active(a):
    with a.e.db.transaction(a.e.tenant) as conn:
        return conn.execute(
            "SELECT count(*) AS n FROM inv.resource_leases WHERE run_id=%s AND released_at IS NULL",
            (a.run["runId"],),
        ).fetchone()["n"]


def record(a, result):
    receipt = result["receipt"]
    assert receipt["stopped"] and len(receipt["allocations"]) == 2
    assert a.receipts.record(a.node, receipt) == receipt
    assert a.receipts.record(a.node, receipt) == receipt
    assert active(a) == 0 and count(a, "node_stop_receipts") == 1
    assert a.e.runs.get(a.e.tenant, a.run["runId"])["state"] == "scheduled"
    with a.e.db.transaction(a.e.tenant) as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM inv.outbox WHERE event_type='inv.execution.stopped'"
            ).fetchone()["n"]
            == 1
        )
    return receipt


def test_real_isolation_unicode_permit_and_durable_replay(node_runtime):
    a = node_runtime
    args = prepare(a)
    result = execute(args)
    assert result["receipt"]["processStarted"] and result["receipt"]["exitCode"] == 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        receipts = list(
            pool.map(lambda _: a.receipts.record(a.node, result["receipt"]), range(8))
        )
    assert all(r == result["receipt"] for r in receipts)
    receipt = record(a, result)
    again = execute(args)
    assert again["duplicate"] and again["receipt"] == receipt
    # Application command arguments never enter durable journal or events.
    assert all(
        "합성" not in p.read_text("utf-8")
        for p in (a.path / "state").iterdir()
        if p.is_file()
    )
    changed = deepcopy(receipt)
    changed["receiptId"] = str(uuid4())
    with pytest.raises(DomainError, match="IDEM-0001"):
        a.receipts.record(a.node, changed)


def test_real_nonzero_exit_does_not_mark_application_success(node_runtime):
    a = node_runtime
    a.workload["command"] = ["/probe", "fail"]
    result = execute(prepare(a))
    assert result["receipt"]["exitCode"] == 7
    record(a, result)


def test_real_timeout_stops_before_resource_release(node_runtime):
    a = node_runtime
    a.workload.update(command=["/probe", "sleep"], timeoutSeconds=1)
    started = time.monotonic()
    result = execute(prepare(a))
    assert time.monotonic() - started < 10
    assert result["receipt"]["exitCode"] != 0
    assert result["receipt"]["reason"] in {"timeout", "exited"}
    assert active(a) == 2
    record(a, result)


def container(a):
    result = subprocess.run(
        [
            "docker",
            "ps",
            "-a",
            "--no-trunc",
            "--filter",
            "label=ai.saintvision.command=" + a.command["commandId"],
            "--format",
            "{{.ID}}",
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=5,
    )
    ids = result.stdout.split()
    assert len(ids) <= 1
    if not ids:
        return None
    value = json.loads(
        subprocess.check_output(["docker", "inspect", ids[0]], text=True, timeout=5)
    )[0]
    assert value["Config"]["Labels"]["ai.saintvision.node"] == a.e.node
    return value


def await_running(a, process):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        value = container(a)
        if value and value["State"]["Running"]:
            return value
        if process.poll() is not None:
            out, err = process.communicate()
            pytest.fail("Node exited before container start: " + err)
        time.sleep(0.05)
    pytest.fail("Synthetic container did not start")


def test_real_node_cancellation_verifies_stop(node_runtime):
    a = node_runtime
    a.workload.update(command=["/probe", "sleep"], timeoutSeconds=10)
    process = subprocess.Popen(
        prepare(a), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    try:
        await_running(a, process)
        process.send_signal(signal.SIGTERM)
        out, err = process.communicate(timeout=12)
        assert process.returncode == 0, err
        result = json.loads(out)
        assert result["receipt"]["reason"] == "cancelled"
        record(a, result)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)


def test_real_agent_crash_watchdog_and_recovery(node_runtime):
    a = node_runtime
    a.workload.update(command=["/probe", "sleep"], timeoutSeconds=3)
    process = subprocess.Popen(
        prepare(a), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    try:
        initial = await_running(a, process)
        process.kill()  # Only our synthetic CLI process; no daemon or host restart.
        process.communicate(timeout=5)
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            value = container(a)
            if value and not value["State"]["Running"]:
                break
            time.sleep(0.1)
        else:
            pytest.fail("Independent PID 1 deadline failed after Node-agent death")
        assert value["Id"] == initial["Id"] and value["State"]["ExitCode"] == 124
        assert active(a) == 2  # Timer alone cannot release a lease.
        recovered = execute(a.args + ["--recover"])
        assert len(recovered) == 1 and recovered[0]["receipt"]["reason"] == "recovered"
        record(a, recovered[0])
        assert execute(a.args + ["--recover"]) == []
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)


def test_real_tampered_signature_has_no_execution_effect(node_runtime):
    a = node_runtime
    args = prepare(a)
    a.permit["signature"] = base64.b64encode(bytes(64)).decode()
    a.permit_file.write_text(json.dumps(a.permit), "utf-8")
    result = subprocess.run(args, capture_output=True, text=True, timeout=10)
    assert result.returncode == 1 and "NODE-0006" in result.stderr
    assert not list((a.path / "state").glob("*.intent")) and container(a) is None
    assert active(a) == 2 and count(a, "node_stop_receipts") == 0


def test_stop_receipt_and_all_lease_releases_rollback_together(
    node_runtime, monkeypatch
):
    import inv.node_execution as module

    a = node_runtime
    result = execute(prepare(a))
    original = module.event

    def fail(*args):
        raise RuntimeError("synthetic outbox failure")

    monkeypatch.setattr(module, "event", fail)
    with pytest.raises(RuntimeError, match="synthetic outbox"):
        a.receipts.record(a.node, result["receipt"])
    assert active(a) == 2 and count(a, "node_stop_receipts") == 0
    monkeypatch.setattr(module, "event", original)
    record(a, result)


@pytest.mark.parametrize(
    "change",
    [
        "node",
        "tenant",
        "epoch",
        "plan",
        "claim",
        "missing-allocation",
        "wrong-fence",
        "wrong-kind",
    ],
)
def test_stop_receipt_rejects_scope_and_fence_change(node_runtime, change):
    a = node_runtime
    result = execute(prepare(a))
    bad = deepcopy(result["receipt"])
    if change == "node":
        bad["nodeId"] = new_id("nod")
    elif change == "tenant":
        bad["tenantId"] = a.e.other
    elif change == "epoch":
        bad["recoveryEpoch"] = str(uuid4())
    elif change == "plan":
        bad["planDigest"] = "b" * 64
    elif change == "claim":
        bad["claimId"] = str(uuid4())
    elif change == "missing-allocation":
        bad["allocations"].pop()
    elif change == "wrong-fence":
        bad["allocations"][0]["lease"]["fencingToken"] = a.e.epoch + ":999999"
    elif change == "wrong-kind":
        bad["allocations"][0]["kind"] = (
            "memory" if bad["allocations"][0]["kind"] == "cpu" else "cpu"
        )
    with pytest.raises(DomainError):
        a.receipts.record(a.node, bad)
    assert active(a) == 2 and count(a, "node_stop_receipts") == 0
    record(a, result)


def test_expired_lease_still_requires_and_accepts_actual_stop_receipt(node_runtime):
    a = node_runtime
    result = execute(prepare(a))
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            "UPDATE inv.resource_leases SET granted_at=clock_timestamp()-interval '2 minutes',expires_at=clock_timestamp()-interval '1 minute' WHERE tenant_id=%s",
            (a.e.tenant,),
        )
    assert active(a) == 2
    record(a, result)


def test_signer_never_reissues_from_claim_replay(gateway):
    a = gateway
    first = claim(a)
    key = Ed25519PrivateKey.generate()
    signed = seal_permit(first, allocations(a), key)
    raw = base64.b64decode(signed["payload"])
    key.public_key().verify(
        base64.b64decode(signed["signature"]), b"SaintVision.NodePermit.v1\x00" + raw
    )
    with pytest.raises(DomainError, match="NODE-0001"):
        seal_permit(claim(a), allocations(a), key)


@pytest.mark.parametrize(
    "change", ["launch", "node", "duplicate", "lease-expiry", "expired"]
)
def test_signer_rejects_unbound_or_expired_execution(gateway, change):
    a = gateway
    result = claim(a)
    proof = allocations(a)
    now = datetime.now(timezone.utc)
    if change == "launch":
        result.launch["argv"].append("changed")
    elif change == "node":
        proof[0]["nodeId"] = new_id("nod")
    elif change == "duplicate":
        proof.append(proof[0])
    elif change == "lease-expiry":
        proof[0]["lease"]["expiresAt"] = now.isoformat()
    elif change == "expired":
        now += timedelta(minutes=1)
    with pytest.raises(DomainError, match="NODE-0001"):
        seal_permit(result, proof, Ed25519PrivateKey.generate(), now=now)
