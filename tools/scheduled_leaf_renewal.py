#!/usr/bin/env python3
"""Fail-closed executor for a pinned, operator-reviewed LAN leaf-renewal plan.

The plan contains paths and public command arguments, never credential values.  Its
SHA-256 is pinned by the Windows scheduled task.  Command output is used only for
strict gate evaluation and is never copied to the append-only operational log.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from cryptography import x509

SCHEMA = "saintvision-scheduled-leaf-renewal:1"
WINDOW_SCHEMA = "saintvision-leaf-renewal-window:1"
RECEIPT_SCHEMA = "saintvision-scheduled-leaf-renewal-receipt:1"
COMMAND_KEYS = {
    "id",
    "executable",
    "executableSha256",
    "arguments",
    "workingDirectory",
    "inputFiles",
}
FILE_KEYS = {"path", "sha256"}
PLAN_KEYS = {
    "schemaVersion",
    "sourceHeadSha",
    "statePath",
    "renewalWindowSeconds",
    "heartbeatFreshnessSeconds",
    "expectedNodeCount",
    "notificationsEnabled",
    "logPath",
    "statusPath",
    "commands",
}
COMMAND_GROUP_KEYS = {
    "currentStatus",
    "runtimePreflight",
    "prepare",
    "install",
    "stage",
    "commit",
    "transition",
    "observe",
    "finalize",
    "finalObserve",
}
SHA256 = re.compile(r"[a-f0-9]{64}")
HEAD = re.compile(r"[a-f0-9]{40}")
ROOT = Path(__file__).resolve().parents[1]
LOCK_SCHEMA = "saintvision-renewal-lock:1"
ATTEMPT_SCHEMA = "saintvision-renewal-attempt:1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _regular(path: Path) -> Path:
    resolved = path.resolve(strict=True)
    if path.is_symlink() or not resolved.is_file():
        raise ValueError("Pinned input is not a regular file")
    return resolved


def _strict_json(path: Path) -> dict[str, Any]:
    def pairs(rows: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in rows:
            if key in result:
                raise ValueError("Configuration contains a duplicate key")
            result[key] = value
        return result

    raw = _regular(path).read_bytes()
    if not raw or len(raw) > 1024 * 1024 or raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError("Configuration bytes are invalid")
    value = json.loads(raw, object_pairs_hook=pairs)
    if not isinstance(value, dict):
        raise ValueError("Configuration root must be an object")
    return value


def _exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise ValueError(f"{label} keys differ")


def _command(value: Any, expected_id: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"Command {expected_id} must be an object")
    _exact_keys(value, COMMAND_KEYS, f"Command {expected_id}")
    if value["id"] != expected_id:
        raise ValueError(f"Command id differs for {expected_id}")
    if not isinstance(value["arguments"], list) or not all(
        isinstance(item, str)
        and len(item) <= 4096
        and "\x00" not in item
        and "\n" not in item
        and "\r" not in item
        and "-----BEGIN" not in item
        and "password=" not in item.lower()
        and not re.search(r"://[^/@:]+:[^/@]+@", item)
        for item in value["arguments"]
    ):
        raise ValueError(f"Command arguments differ for {expected_id}")
    if not isinstance(value["inputFiles"], list):
        raise ValueError(f"Command input files differ for {expected_id}")
    for pinned in value["inputFiles"]:
        if not isinstance(pinned, dict):
            raise ValueError(f"Command input pin differs for {expected_id}")
        _exact_keys(pinned, FILE_KEYS, f"Command input pin for {expected_id}")
        if not SHA256.fullmatch(str(pinned["sha256"])):
            raise ValueError(f"Command input digest differs for {expected_id}")
    if not SHA256.fullmatch(str(value["executableSha256"])):
        raise ValueError(f"Executable digest differs for {expected_id}")
    return value


def load_plan(path: Path, expected_sha256: str) -> dict[str, Any]:
    if not SHA256.fullmatch(expected_sha256) or _sha256(_regular(path)) != expected_sha256:
        raise ValueError("Scheduled renewal configuration digest differs")
    plan = _strict_json(path)
    _exact_keys(plan, PLAN_KEYS, "Scheduled renewal configuration")
    if (
        plan["schemaVersion"] != SCHEMA
        or not HEAD.fullmatch(str(plan["sourceHeadSha"]))
        or plan["renewalWindowSeconds"] != 172800
        or not isinstance(plan["heartbeatFreshnessSeconds"], int)
        or not 30 <= plan["heartbeatFreshnessSeconds"] <= 600
        or plan["expectedNodeCount"] != 2
        or not isinstance(plan["notificationsEnabled"], bool)
    ):
        raise ValueError("Scheduled renewal configuration contract differs")
    source = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    if source.returncode or source.stdout.strip() != plan["sourceHeadSha"]:
        raise ValueError("Scheduled renewal source head differs")
    commands = plan["commands"]
    if not isinstance(commands, dict):
        raise ValueError("Scheduled renewal commands must be an object")
    _exact_keys(commands, COMMAND_GROUP_KEYS, "Scheduled renewal command groups")
    for name in ("runtimePreflight", "install", "stage", "finalize"):
        group = commands[name]
        if not isinstance(group, list) or len(group) != 2:
            raise ValueError(f"Command group {name} must contain exactly two Nodes")
        for index, item in enumerate(group, 1):
            _command(item, f"{name}-{index}")
    for name in COMMAND_GROUP_KEYS - {"runtimePreflight", "install", "stage", "finalize"}:
        _command(commands[name], name)
    return plan


def renewal_window(state: Path, window_seconds: int, now: datetime) -> dict[str, Any]:
    public = state / "public" / "nodes"
    paths = [state / "control-cert.pem"]
    if not public.is_dir() or public.is_symlink():
        raise ValueError("Public Node certificate directory is missing or unsafe")
    paths.extend(sorted(public.glob("*/node-cert.pem")))
    if len(paths) < 3:
        raise ValueError("At least two public Node certificates are required")
    certificates = []
    for path in paths:
        target = _regular(path)
        if target.stat().st_size > 65536:
            raise ValueError("Public certificate exceeds limit")
        certificate = x509.load_pem_x509_certificate(target.read_bytes())
        if certificate.not_valid_before_utc > now:
            raise ValueError("A public leaf is not valid yet")
        certificates.append(certificate)
    earliest = min(item.not_valid_after_utc for item in certificates)
    renew_at = earliest - timedelta(seconds=window_seconds)
    expired = now >= earliest
    return {
        "schemaVersion": WINDOW_SCHEMA,
        "observedAt": now.isoformat().replace("+00:00", "Z"),
        "earliestNotAfter": earliest.isoformat().replace("+00:00", "Z"),
        "renewAt": renew_at.isoformat().replace("+00:00", "Z"),
        "expired": expired,
        "inWindow": not expired and now >= renew_at,
        "certificateCount": len(certificates),
        "nodeCertificateCount": len(certificates) - 1,
        "leafSetSHA256": _leaf_set(state),
    }


def _paths(plan: dict[str, Any]) -> tuple[Path, Path]:
    state = Path(plan["statePath"])
    if state.is_symlink() or not state.is_dir():
        raise ValueError("Renewal state directory is missing or unsafe")
    return state / "scheduled-leaf-renewal.lock", state / "scheduled-leaf-renewal-attempt.json"


def _state_binding(plan: dict[str, Any]) -> str:
    return hashlib.sha256(str(Path(plan["statePath"]).resolve()).encode()).hexdigest()


def _plan_binding(plan: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@contextmanager
def _guard(path: Path) -> Iterator[None]:
    """Kernel ownership proof, held across every child command; never unlink this inode.

    A killed owner releases the OS lock, not the durable intent/latch. This alone
    says nothing about orphaned commands or remote effects and never permits retry.
    """
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError("Renewal guard is not a regular file")
    fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    locked = False
    try:
        if os.name == "nt":
            import msvcrt
            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            except OSError as error:
                raise RuntimeError("Scheduled renewal owner still holds the kernel guard") from error
        else:
            import fcntl
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise RuntimeError("Scheduled renewal owner still holds the kernel guard") from error
        locked = True
        yield
    finally:
        if locked:
            if os.name == "nt":
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


@contextmanager
def _lock(path: Path, owner: dict[str, Any]) -> Iterator[None]:
    with _guard(path.with_suffix(".guard")):
        raw = (json.dumps(owner, sort_keys=True) + "\n").encode()
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as error:
            raise RuntimeError("Stale renewal lock requires explicit ownership-proven recovery") from error
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            yield
        finally:
            if _regular(path).read_bytes() != raw:
                raise RuntimeError("Renewal lock owner record changed; preserving it")
            path.unlink()


def _owner(plan: dict[str, Any], run_id: str) -> dict[str, Any]:
    return dict(schemaVersion=LOCK_SCHEMA, statePathSHA256=_state_binding(plan),
                planSHA256=_plan_binding(plan), runId=run_id, token=uuid.uuid4().hex, pid=os.getpid())


def _leaf_set(state: Path) -> str:
    paths = [state / "control-cert.pem", *sorted((state / "public/nodes").glob("*/node-cert.pem"))]
    return hashlib.sha256(json.dumps([
        [path.relative_to(state).as_posix(), _sha256(_regular(path))] for path in paths
    ], separators=(",", ":")).encode()).hexdigest()


def _attempt(path: Path, plan: dict[str, Any]) -> dict[str, Any] | None:
    if not path.exists() and not path.is_symlink():
        return None
    value = _strict_json(path)
    _exact_keys(value, {"schemaVersion", "statePathSHA256", "planSHA256", "runId",
                        "leafSetSHA256", "phase", "failedGate"}, "Renewal attempt")
    if (value["schemaVersion"] != ATTEMPT_SCHEMA
        or value["statePathSHA256"] != _state_binding(plan)
        or not SHA256.fullmatch(str(value["planSHA256"]))
        or not isinstance(value["runId"], str) or not value["runId"]
        or (value["leafSetSHA256"] is not None and not SHA256.fullmatch(str(value["leafSetSHA256"])))
        or value["phase"] not in {"in-progress", "failed", "completed"}):
        raise ValueError("Renewal attempt authority differs")
    return value


def _archive(path: Path, value: dict[str, Any], digest: str) -> None:
    target = path.parent / "scheduled-leaf-renewal-history" / f"{digest}.json"
    if target.exists():
        if _strict_json(target) != value:
            raise ValueError("Renewal recovery archive differs")
    else:
        _atomic_json(target, value)


def recover_stale_lock(plan: dict[str, Any], expected_sha256: str) -> None:
    """Explicitly retire exact stale metadata; retain the uncertain-attempt latch."""
    lock, _latch = _paths(plan)
    with _guard(lock.with_suffix(".guard")):
        if not SHA256.fullmatch(expected_sha256) or _sha256(_regular(lock)) != expected_sha256:
            raise ValueError("Stale lock digest differs")
        value = _strict_json(lock)
        _exact_keys(value, {"schemaVersion", "statePathSHA256", "planSHA256", "runId", "token", "pid"}, "Renewal lock")
        if (value["schemaVersion"] != LOCK_SCHEMA
            or value["statePathSHA256"] != _state_binding(plan)
            or not SHA256.fullmatch(str(value["planSHA256"]))
            or not isinstance(value["runId"], str) or not value["runId"]
            or not re.fullmatch(r"[a-f0-9]{32}", str(value["token"]))
            or type(value["pid"]) is not int or value["pid"] <= 0):
            raise ValueError("Stale lock ownership differs")
        _archive(lock, value, expected_sha256)
        lock.unlink()


def reset_failure_latch(plan: dict[str, Any], expected_sha256: str, reviewed_leaf_sha256: str) -> None:
    """A reviewed fresh, outside-window generation is required; never resume an old batch."""
    lock, latch = _paths(plan)
    with _lock(lock, _owner(plan, "reviewed-latch-reset")):
        if not SHA256.fullmatch(expected_sha256) or _sha256(_regular(latch)) != expected_sha256:
            raise ValueError("Failure latch digest differs")
        value = _attempt(latch, plan)
        window = renewal_window(Path(plan["statePath"]), plan["renewalWindowSeconds"], datetime.now(timezone.utc))
        leaves = _leaf_set(Path(plan["statePath"]))
        if (value is None or value["phase"] == "completed"
            or window["expired"] or window["inWindow"]
            or window["nodeCertificateCount"] != plan["expectedNodeCount"]
            or not SHA256.fullmatch(reviewed_leaf_sha256) or leaves != reviewed_leaf_sha256
            or leaves == value["leafSetSHA256"]):
            raise ValueError("Latch reset requires the exact reviewed fresh leaf generation")
        _archive(latch, value, expected_sha256)
        latch.unlink()


def _expand(value: str, run_id: str) -> str:
    expanded = value.replace("{runId}", run_id)
    if "{" in expanded or "}" in expanded:
        raise ValueError("Unknown command argument placeholder")
    return expanded


def _run(command: dict[str, Any], run_id: str) -> str:
    executable = _regular(Path(command["executable"]))
    if _sha256(executable) != command["executableSha256"]:
        raise ValueError(f"Executable digest differs at gate {command['id']}")
    for pinned in command["inputFiles"]:
        if _sha256(_regular(Path(pinned["path"]))) != pinned["sha256"]:
            raise ValueError(f"Pinned input digest differs at gate {command['id']}")
    working = Path(command["workingDirectory"]).resolve(strict=True)
    if not working.is_dir() or Path(command["workingDirectory"]).is_symlink():
        raise ValueError(f"Working directory differs at gate {command['id']}")
    result = subprocess.run(
        [str(executable), *[_expand(item, run_id) for item in command["arguments"]]],
        cwd=working,
        capture_output=True,
        timeout=900,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(f"Gate {command['id']} failed with exit {result.returncode}")
    if len(result.stdout) > 1024 * 1024:
        raise ValueError(f"Gate {command['id']} output exceeds limit")
    return result.stdout.decode("utf-8", errors="strict").strip()


def _json_output(raw: str, gate: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, UnicodeError) as error:
        raise ValueError(f"Gate {gate} did not emit one JSON object") from error
    if not isinstance(value, dict):
        raise ValueError(f"Gate {gate} did not emit one JSON object")
    return value


def _online_fresh(raw: str, expected: int, freshness: int, not_before: datetime) -> None:
    value = _json_output(raw, "observation")
    nodes = value.get("nodes")
    if not isinstance(nodes, list) or len(nodes) != expected:
        raise ValueError("Observation does not contain the exact Node set")
    identities: set[str] = set()
    now = datetime.now(timezone.utc)
    for row in nodes:
        node = row.get("node") if isinstance(row, dict) else None
        node_id = row.get("nodeId") if isinstance(row, dict) else None
        if not isinstance(node, dict) or not isinstance(node_id, str) or node_id in identities:
            raise ValueError("Observation Node identity differs")
        identities.add(node_id)
        heartbeat = node.get("heartbeat_at", node.get("heartbeatAt"))
        status = node.get("status")
        try:
            observed = datetime.fromisoformat(str(heartbeat).replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError("Observation heartbeat differs") from error
        if (
            status != "online"
            or observed.tzinfo is None
            or observed < not_before
            or now - observed.astimezone(timezone.utc) > timedelta(seconds=freshness)
        ):
            raise ValueError("Observation is not online and fresh")


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError("Renewal record path is unsafe")
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _record(plan: dict[str, Any], value: dict[str, Any]) -> None:
    receipt = {"schemaVersion": RECEIPT_SCHEMA, **value}
    log = Path(plan["logPath"])
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("ab") as stream:
        stream.write((json.dumps(receipt, sort_keys=True) + "\n").encode("utf-8"))
        stream.flush()
        os.fsync(stream.fileno())
    _atomic_json(Path(plan["statusPath"]), receipt)
    if (
        os.name == "nt"
        and plan["notificationsEnabled"]
        and receipt["outcome"] in {"renewed", "failed", "expired-alert"}
    ):
        # Best effort only: the durable status file is authoritative.  The
        # notification contains no path, identity, certificate, or diagnostic.
        try:
            subprocess.run(
                [
                    "msg.exe",
                    os.environ.get("USERNAME", "*"),
                    f"SaintVision leaf renewal: {receipt['outcome']}",
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            pass


def execute(plan: dict[str, Any], now: datetime | None = None) -> int:
    current = now or datetime.now(timezone.utc)
    run_id = current.strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:12]
    base = {
        "runId": run_id,
        "sourceHeadSha": plan["sourceHeadSha"],
        "observedAt": current.isoformat().replace("+00:00", "Z"),
    }
    # Expiry observation must remain available even with an abandoned or busy lock.
    window = None
    try:
        window = renewal_window(Path(plan["statePath"]), plan["renewalWindowSeconds"], current)
        if window["nodeCertificateCount"] != plan["expectedNodeCount"]:
            raise ValueError("Public certificate set does not match the exact Node set")
    except Exception:
        window = None
    if window is not None and window["expired"]:
        _record(plan, {**base, "outcome": "expired-alert", "failedGate": "window"})
        return 3

    active_gate = "lock"
    failure_recorded = False
    attempt = None
    try:
        lock, latch = _paths(plan)
        # Old executors never held the kernel guard. Do not infer their death from age/PID.
        if Path(plan["statusPath"]).with_suffix(".lock").exists():
            raise RuntimeError("Legacy renewal lock requires manual ownership disposition")
        with _lock(lock, _owner(plan, run_id)):
            try:
                active_gate = "attempt-latch"
                previous = _attempt(latch, plan)
                if previous is not None and previous["phase"] != "completed":
                    _record(plan, {**base, "outcome": "recovery-required", "failedGate": "attempt-latch"})
                    return 2
                active_gate = "window"
                # Revalidate after acquiring ownership; another completed run may have
                # changed public material between the initial expiry probe and here.
                try:
                    window = renewal_window(Path(plan["statePath"]), plan["renewalWindowSeconds"], current)
                    if window["nodeCertificateCount"] != plan["expectedNodeCount"]:
                        window = None
                except Exception:
                    window = None
                if window is None:
                    if previous is not None:
                        _archive(latch, previous, _sha256(latch))
                    attempt = dict(schemaVersion=ATTEMPT_SCHEMA, statePathSHA256=_state_binding(plan),
                                   planSHA256=_plan_binding(plan), runId=run_id, leafSetSHA256=None,
                                   phase="failed", failedGate="window")
                    _atomic_json(latch, attempt)
                    raise ValueError("Public certificate preflight failed")
                if not window["inWindow"]:
                    _record(plan, {**base, "outcome": "outside-window", "failedGate": None})
                    return 0
                leaves = _leaf_set(Path(plan["statePath"]))
                if previous is not None and previous["leafSetSHA256"] == leaves:
                    _record(plan, {**base, "outcome": "already-renewed", "failedGate": None})
                    return 0
                attempt = dict(schemaVersion=ATTEMPT_SCHEMA, statePathSHA256=_state_binding(plan),
                               planSHA256=_plan_binding(plan), runId=run_id, leafSetSHA256=leaves,
                               phase="in-progress", failedGate="currentStatus")
                if previous is not None:
                    _archive(latch, previous, _sha256(latch))
                _atomic_json(latch, attempt)
                _record(plan, {**base, "outcome": "started", "failedGate": None})
                commands = plan["commands"]
                active_gate = "currentStatus"
                started = datetime.now(timezone.utc)
                def gate_run(command: dict[str, Any], identifier: str) -> str:
                    attempt["failedGate"] = command["id"]
                    _atomic_json(latch, attempt)
                    return _run(command, identifier)
                _online_fresh(
                    gate_run(commands["currentStatus"], run_id),
                    plan["expectedNodeCount"],
                    plan["heartbeatFreshnessSeconds"],
                    started - timedelta(seconds=plan["heartbeatFreshnessSeconds"]),
                )
                for group in ("runtimePreflight",):
                    for command in commands[group]:
                        active_gate = command["id"]
                        gate_run(command, run_id)
                active_gate = "prepare"
                gate_run(commands["prepare"], run_id)
                for group in ("install", "stage"):
                    for command in commands[group]:
                        active_gate = command["id"]
                        gate_run(command, run_id)
                active_gate = "commit"
                gate_run(commands["commit"], run_id)
                active_gate = "transition"
                gate_run(commands["transition"], run_id)
                active_gate = "observe"
                _online_fresh(
                    gate_run(commands["observe"], run_id),
                    plan["expectedNodeCount"],
                    plan["heartbeatFreshnessSeconds"],
                    started,
                )
                for command in commands["finalize"]:
                    active_gate = command["id"]
                    gate_run(command, run_id)
                active_gate = "finalObserve"
                _online_fresh(
                    gate_run(commands["finalObserve"], run_id),
                    plan["expectedNodeCount"],
                    plan["heartbeatFreshnessSeconds"],
                    started,
                )
                attempt.update(phase="completed", failedGate=None)
                _atomic_json(latch, attempt)
                _record(plan, {**base, "outcome": "renewed", "failedGate": None})
                return 0
            except Exception:
                if attempt is not None:
                    attempt.update(phase="failed", failedGate=active_gate)
                    _atomic_json(latch, attempt)
                _record(plan, {**base, "outcome": "failed", "failedGate": active_gate})
                failure_recorded = True
                raise
    except Exception:
        if not failure_recorded:
            _record(plan, {**base, "outcome": "failed", "failedGate": active_gate})
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--expected-config-sha256", required=True)
    recovery = parser.add_mutually_exclusive_group()
    recovery.add_argument("--window-only", action="store_true")
    recovery.add_argument("--recover-stale-lock", action="store_true")
    recovery.add_argument("--reset-failure-latch", action="store_true")
    parser.add_argument("--expected-lock-sha256")
    parser.add_argument("--expected-latch-sha256")
    parser.add_argument("--reviewed-fresh-leaf-sha256")
    args = parser.parse_args()
    plan = load_plan(args.config, args.expected_config_sha256)
    if args.window_only:
        print(
            json.dumps(renewal_window(Path(plan["statePath"]), 172800, datetime.now(timezone.utc)))
        )
        return 0
    try:
        if args.recover_stale_lock or args.reset_failure_latch:
            if args.window_only:
                raise ValueError("Recovery and window observation must be separate")
            action = "stale-lock-recovery" if args.recover_stale_lock else "latch-reset"
            base = dict(runId="reviewed-" + uuid.uuid4().hex, sourceHeadSha=plan["sourceHeadSha"],
                        observedAt=datetime.now(timezone.utc).isoformat())
            try:
                if args.recover_stale_lock:
                    recover_stale_lock(plan, args.expected_lock_sha256 or "")
                else:
                    reset_failure_latch(plan, args.expected_latch_sha256 or "",
                                        args.reviewed_fresh_leaf_sha256 or "")
            except Exception:
                _record(plan, {**base, "outcome": "failed", "failedGate": action})
                raise
            _record(plan, {**base, "outcome": action, "failedGate": None})
            return 0
        return execute(plan)
    except Exception as error:
        print(
            f"Scheduled leaf renewal stopped ({type(error).__name__}); diagnostics and secrets suppressed.",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
