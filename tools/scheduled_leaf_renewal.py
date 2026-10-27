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
    }


@contextmanager
def _lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise RuntimeError("Scheduled leaf renewal is already running") from error
    try:
        os.write(descriptor, f"{os.getpid()}\n".encode("ascii"))
        os.close(descriptor)
        yield
    finally:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


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
    run_id = current.strftime("%Y%m%dT%H%M%SZ")
    base = {
        "runId": run_id,
        "sourceHeadSha": plan["sourceHeadSha"],
        "observedAt": current.isoformat().replace("+00:00", "Z"),
    }
    lock_path = Path(plan["statusPath"]).with_suffix(".lock")
    with _lock(lock_path):
        window = renewal_window(Path(plan["statePath"]), plan["renewalWindowSeconds"], current)
        if window["nodeCertificateCount"] != plan["expectedNodeCount"]:
            raise ValueError("Public certificate set does not match the exact Node set")
        if window["expired"]:
            _record(plan, {**base, "outcome": "expired-alert", "failedGate": "window"})
            return 3
        if not window["inWindow"]:
            _record(plan, {**base, "outcome": "outside-window", "failedGate": None})
            return 0
        commands = plan["commands"]
        active_gate = "currentStatus"
        started = datetime.now(timezone.utc)
        try:
            _online_fresh(
                _run(commands["currentStatus"], run_id),
                plan["expectedNodeCount"],
                plan["heartbeatFreshnessSeconds"],
                started - timedelta(seconds=plan["heartbeatFreshnessSeconds"]),
            )
            for group in ("runtimePreflight",):
                for command in commands[group]:
                    active_gate = command["id"]
                    _run(command, run_id)
            active_gate = "prepare"
            _run(commands["prepare"], run_id)
            for group in ("install", "stage"):
                for command in commands[group]:
                    active_gate = command["id"]
                    _run(command, run_id)
            active_gate = "commit"
            _run(commands["commit"], run_id)
            active_gate = "transition"
            _run(commands["transition"], run_id)
            active_gate = "observe"
            _online_fresh(
                _run(commands["observe"], run_id),
                plan["expectedNodeCount"],
                plan["heartbeatFreshnessSeconds"],
                started,
            )
            for command in commands["finalize"]:
                active_gate = command["id"]
                _run(command, run_id)
            active_gate = "finalObserve"
            _online_fresh(
                _run(commands["finalObserve"], run_id),
                plan["expectedNodeCount"],
                plan["heartbeatFreshnessSeconds"],
                started,
            )
        except Exception:
            _record(plan, {**base, "outcome": "failed", "failedGate": active_gate})
            raise
        _record(plan, {**base, "outcome": "renewed", "failedGate": None})
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--expected-config-sha256", required=True)
    parser.add_argument("--window-only", action="store_true")
    args = parser.parse_args()
    plan = load_plan(args.config, args.expected_config_sha256)
    if args.window_only:
        print(
            json.dumps(renewal_window(Path(plan["statePath"]), 172800, datetime.now(timezone.utc)))
        )
        return 0
    try:
        return execute(plan)
    except Exception as error:
        print(
            f"Scheduled leaf renewal stopped ({type(error).__name__}); diagnostics and secrets suppressed.",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
