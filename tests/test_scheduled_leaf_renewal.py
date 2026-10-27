from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.x509.oid import NameOID

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "scheduled_leaf_renewal.py"
INVOKER = ROOT / "deploy" / "lan" / "Invoke-ScheduledLeafRenewal.ps1"
REGISTRAR = ROOT / "deploy" / "lan" / "Register-LeafRenewalTask.ps1"

spec = importlib.util.spec_from_file_location("scheduled_leaf_renewal", TOOL)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)
SOURCE_HEAD = subprocess.run(
    ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
    capture_output=True,
    text=True,
    check=True,
).stdout.strip()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def certificate(not_after: datetime) -> bytes:
    key = Ed25519PrivateKey.generate()
    now = datetime.now(timezone.utc)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "public-test-leaf")])
    return (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(not_after)
        .sign(key, algorithm=None)
        .public_bytes(serialization.Encoding.PEM)
    )


def public_state(tmp_path: Path, not_after: datetime) -> Path:
    state = tmp_path / "state"
    (state / "public" / "nodes" / "node-a").mkdir(parents=True)
    (state / "public" / "nodes" / "node-b").mkdir(parents=True)
    raw = certificate(not_after)
    (state / "control-cert.pem").write_bytes(raw)
    (state / "public" / "nodes" / "node-a" / "node-cert.pem").write_bytes(raw)
    (state / "public" / "nodes" / "node-b" / "node-cert.pem").write_bytes(raw)
    return state


def fake_tool(tmp_path: Path) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    target = tmp_path / "fake_gate.py"
    target.write_text(
        """import json, pathlib, sys
gate, trace, failure = sys.argv[1:4]
with pathlib.Path(trace).open('a', encoding='utf-8') as stream:
    stream.write(gate + '\\n')
if failure == gate:
    raise SystemExit(9)
if gate in {'currentStatus', 'observe', 'finalObserve'}:
    from datetime import datetime, timezone
    heartbeat = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    print(json.dumps({'nodes': [
        {'nodeId': 'node-a', 'node': {'status': 'online', 'heartbeatAt': heartbeat}},
        {'nodeId': 'node-b', 'node': {'status': 'online', 'heartbeatAt': heartbeat}},
    ]}))
else:
    print('{}')
""",
        encoding="utf-8",
    )
    return target


def command(identifier: str, fake: Path, trace: Path, failure: str) -> dict:
    executable = Path(sys.executable)
    return {
        "id": identifier,
        "executable": str(executable),
        "executableSha256": sha(executable),
        "arguments": [str(fake), identifier, str(trace), failure],
        "workingDirectory": str(fake.parent),
        "inputFiles": [{"path": str(fake), "sha256": sha(fake)}],
    }


def plan_file(tmp_path: Path, state: Path, *, failure: str = "none") -> tuple[Path, dict, Path]:
    fake = fake_tool(tmp_path)
    trace = tmp_path / "trace.txt"
    groups = {
        "currentStatus": command("currentStatus", fake, trace, failure),
        "runtimePreflight": [
            command("runtimePreflight-1", fake, trace, failure),
            command("runtimePreflight-2", fake, trace, failure),
        ],
        "prepare": command("prepare", fake, trace, failure),
        "install": [
            command("install-1", fake, trace, failure),
            command("install-2", fake, trace, failure),
        ],
        "stage": [
            command("stage-1", fake, trace, failure),
            command("stage-2", fake, trace, failure),
        ],
        "commit": command("commit", fake, trace, failure),
        "transition": command("transition", fake, trace, failure),
        "observe": command("observe", fake, trace, failure),
        "finalize": [
            command("finalize-1", fake, trace, failure),
            command("finalize-2", fake, trace, failure),
        ],
        "finalObserve": command("finalObserve", fake, trace, failure),
    }
    plan = {
        "schemaVersion": module.SCHEMA,
        "sourceHeadSha": SOURCE_HEAD,
        "statePath": str(state),
        "renewalWindowSeconds": 172800,
        "heartbeatFreshnessSeconds": 120,
        "expectedNodeCount": 2,
        "notificationsEnabled": False,
        "logPath": str(tmp_path / "renewal.jsonl"),
        "statusPath": str(tmp_path / "Desktop" / "leaf-renewal-status.json"),
        "commands": groups,
    }
    target = tmp_path / "plan.json"
    target.write_text(json.dumps(plan, sort_keys=True), encoding="utf-8")
    return target, plan, trace


def load(target: Path) -> dict:
    return module.load_plan(target, sha(target))


def test_outside_window_is_noop_and_expired_is_alert(tmp_path: Path):
    now = datetime.now(timezone.utc)
    state = public_state(tmp_path / "outside", now + timedelta(days=5))
    target, _plan, trace = plan_file(tmp_path / "outside", state)
    assert module.execute(load(target), now=now) == 0
    assert not trace.exists()
    receipt = json.loads(
        (tmp_path / "outside" / "Desktop" / "leaf-renewal-status.json").read_text()
    )
    assert receipt["outcome"] == "outside-window"

    expired_state = public_state(tmp_path / "expired", now - timedelta(seconds=1))
    expired_target, _plan, expired_trace = plan_file(tmp_path / "expired", expired_state)
    assert module.execute(load(expired_target), now=now) == 3
    assert not expired_trace.exists()
    expired = json.loads(
        (tmp_path / "expired" / "Desktop" / "leaf-renewal-status.json").read_text()
    )
    assert expired["outcome"] == "expired-alert"


def test_in_window_runs_the_only_permitted_sequence(tmp_path: Path):
    now = datetime.now(timezone.utc)
    state = public_state(tmp_path, now + timedelta(days=1))
    target, _plan, trace = plan_file(tmp_path, state)
    assert module.execute(load(target), now=now) == 0
    assert trace.read_text().splitlines() == [
        "currentStatus",
        "runtimePreflight-1",
        "runtimePreflight-2",
        "prepare",
        "install-1",
        "install-2",
        "stage-1",
        "stage-2",
        "commit",
        "transition",
        "observe",
        "finalize-1",
        "finalize-2",
        "finalObserve",
    ]
    receipt = json.loads((tmp_path / "Desktop" / "leaf-renewal-status.json").read_text())
    assert receipt["outcome"] == "renewed"
    assert receipt["failedGate"] is None


@pytest.mark.parametrize(
    "failure",
    [
        "currentStatus",
        "runtimePreflight-1",
        "runtimePreflight-2",
        "prepare",
        "install-1",
        "install-2",
        "stage-1",
        "stage-2",
        "commit",
        "transition",
        "observe",
        "finalize-1",
        "finalize-2",
        "finalObserve",
    ],
)
def test_each_failed_gate_stops_without_a_later_command(tmp_path: Path, failure: str):
    now = datetime.now(timezone.utc)
    state = public_state(tmp_path, now + timedelta(days=1))
    target, _plan, trace = plan_file(tmp_path, state, failure=failure)
    with pytest.raises(RuntimeError, match="failed with exit 9"):
        module.execute(load(target), now=now)
    rows = trace.read_text().splitlines()
    assert rows[-1] == failure
    receipt = json.loads((tmp_path / "Desktop" / "leaf-renewal-status.json").read_text())
    assert receipt == {
        "failedGate": failure,
        "observedAt": now.isoformat().replace("+00:00", "Z"),
        "outcome": "failed",
        "runId": now.strftime("%Y%m%dT%H%M%SZ"),
        "schemaVersion": module.RECEIPT_SCHEMA,
        "sourceHeadSha": SOURCE_HEAD,
    }


def test_lock_and_pin_drift_fail_before_any_command(tmp_path: Path):
    now = datetime.now(timezone.utc)
    state = public_state(tmp_path, now + timedelta(days=1))
    target, plan, trace = plan_file(tmp_path, state)
    lock = Path(plan["statusPath"]).with_suffix(".lock")
    lock.parent.mkdir(parents=True)
    lock.write_text("other\n")
    with pytest.raises(RuntimeError, match="already running"):
        module.execute(load(target), now=now)
    assert not trace.exists()

    lock.unlink()
    fake = Path(plan["commands"]["prepare"]["inputFiles"][0]["path"])
    fake.write_text(fake.read_text() + "# drift\n")
    with pytest.raises(ValueError, match="Pinned input digest differs at gate currentStatus"):
        module.execute(load(target), now=now)
    assert not trace.exists()


def test_plan_rejects_extra_key_duplicate_node_group_and_changed_digest(tmp_path: Path):
    state = public_state(tmp_path, datetime.now(timezone.utc) + timedelta(days=1))
    target, plan, _trace = plan_file(tmp_path, state)
    plan["unexpected"] = True
    target.write_text(json.dumps(plan), encoding="utf-8")
    with pytest.raises(ValueError, match="keys differ"):
        load(target)

    target, plan, _trace = plan_file(tmp_path, state)
    plan["commands"]["stage"] = plan["commands"]["stage"][:1]
    target.write_text(json.dumps(plan), encoding="utf-8")
    with pytest.raises(ValueError, match="exactly two"):
        load(target)

    target, _plan, _trace = plan_file(tmp_path, state)
    with pytest.raises(ValueError, match="digest differs"):
        module.load_plan(target, "0" * 64)

    target, plan, _trace = plan_file(tmp_path, state)
    plan["sourceHeadSha"] = "0" * 40
    target.write_text(json.dumps(plan), encoding="utf-8")
    with pytest.raises(ValueError, match="source head differs"):
        load(target)


def test_registration_plan_is_current_user_limited_and_twice_daily(tmp_path: Path):
    powershell = shutil.which("powershell.exe") or shutil.which("pwsh")
    if not powershell:
        pytest.skip("PowerShell is unavailable")
    state = public_state(tmp_path, datetime.now(timezone.utc) + timedelta(days=5))
    target, _plan, _trace = plan_file(tmp_path, state)
    result = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(REGISTRAR),
            "-ConfigPath",
            str(target),
            "-PythonPath",
            sys.executable,
            "-PlanOnly",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    value = json.loads(result.stdout)
    assert value["triggers"] == ["00:15", "12:15"]
    assert value["multipleInstances"] == "IgnoreNew"
    assert value["logonType"] == "S4U"
    assert value["nonInteractive"] is True
    assert value["elevated"] is False
    assert sha(target) in value["owner"]


def test_runner_and_registration_scripts_do_not_read_private_state():
    combined = INVOKER.read_text(encoding="utf-8") + REGISTRAR.read_text(encoding="utf-8")
    assert "private-state.json" not in combined
    assert "New-ScheduledTaskPrincipal" in combined
    assert "-RunLevel Limited" in combined
    assert "-MultipleInstances IgnoreNew" in combined
