"""Reproducible concurrent placement benchmark and evidence writer.

The default command runs the real-PostgreSQL integration adapter.  The core
runner is deliberately adapter-neutral so the same concurrency, determinism,
latency, and JUnit logic can be reused by the five-node lab adapter later.
"""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import as_completed, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
from threading import Barrier
from time import perf_counter_ns
from typing import Any, Callable
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
FIVE_NODE_INVENTORY_SCHEMA_VERSION = "1.0.0"
FIVE_NODE_PROFILE = "lan-workspace-v1"
FIVE_NODE_FRESHNESS_SECONDS = 15.0
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_NODE_ID_RE = re.compile(r"^nod_[A-Za-z0-9][A-Za-z0-9_-]{0,126}$")


@dataclass(frozen=True)
class PlacementSample:
    request_index: int
    completion_order: int
    latency_ms: float
    result: dict | None
    error_code: str | None
    error_type: str | None
    error_status: int | None
    error_retryable: bool | None
    cause_type: str | None
    sqlstate: str | None
    timeout_kind: str | None
    arrival_offset_ms: float
    completion_offset_ms: float


@dataclass(frozen=True)
class RoundEvidence:
    name: str
    request_count: int
    concurrency: int
    success_count: int
    failure_count: int
    p95_all_ms: float
    p95_success_ms: float | None
    p95_failure_ms: float | None
    max_ms: float
    explain_signatures: tuple[str, ...]
    snapshot_ids: tuple[str, ...]
    node_ids: tuple[str, ...]
    fencing_tokens: tuple[str, ...]
    failure_request_indexes: tuple[int, ...]
    first_failure_completion_order: int | None
    errors_by_code: dict[str, int]
    errors_by_sqlstate: dict[str, int]
    samples: tuple[PlacementSample, ...]


def percentile_nearest_rank(values: list[float], percentile: float) -> float:
    """Return the nearest-rank percentile used by the acceptance report."""

    if not values or not 0 < percentile <= 1:
        raise ValueError("A non-empty sample and percentile in (0, 1] are required")
    ordered = sorted(values)
    return ordered[math.ceil(percentile * len(ordered)) - 1]


def _explain_signature(result: dict) -> str:
    """Canonicalize the complete Explain, including its snapshot identity."""

    return json.dumps(
        result["placement"], ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def run_round(
    *,
    name: str,
    request_count: int,
    concurrency: int,
    reserve: Callable[[int], dict],
    on_wave_start: Callable[[], None] | None = None,
) -> tuple[RoundEvidence, list[PlacementSample]]:
    """Start all requests together and retain latency plus decision evidence."""

    if request_count < 1 or request_count > 200:
        raise ValueError("request_count must be between 1 and 200")
    if concurrency != request_count:
        raise ValueError("concurrency must equal request_count for one simultaneous wave")
    wave_origin_ns: list[int] = []

    def mark_wave_start() -> None:
        wave_origin_ns.append(perf_counter_ns())
        if on_wave_start is not None:
            on_wave_start()

    barrier = Barrier(request_count, action=mark_wave_start)

    def attempt(index: int) -> tuple:
        barrier.wait(timeout=30)
        started = perf_counter_ns()
        arrival_offset_ms = (started - wave_origin_ns[0]) / 1_000_000
        try:
            result = reserve(index)
            finished = perf_counter_ns()
            return (
                index,
                (finished - started) / 1_000_000,
                result,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                arrival_offset_ms,
                (finished - wave_origin_ns[0]) / 1_000_000,
            )
        except Exception as error:  # Evidence must retain every concurrent outcome.
            finished = perf_counter_ns()
            cause = getattr(error, "__cause__", None)
            sqlstate = getattr(cause, "sqlstate", None) or getattr(error, "sqlstate", None)
            return (
                index,
                (finished - started) / 1_000_000,
                None,
                getattr(error, "code", None) or "UNCLASSIFIED",
                type(error).__name__,
                getattr(error, "status", None),
                getattr(error, "retryable", None),
                type(cause).__name__ if cause is not None else None,
                sqlstate,
                (
                    "lock_timeout"
                    if sqlstate == "55P03"
                    else "statement_timeout" if sqlstate == "57014" else None
                ),
                arrival_offset_ms,
                (finished - wave_origin_ns[0]) / 1_000_000,
            )

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(attempt, index) for index in range(request_count)]
        samples = []
        for completion_order, future in enumerate(as_completed(futures), start=1):
            (
                index,
                latency,
                result,
                error_code,
                error_type,
                error_status,
                error_retryable,
                cause_type,
                sqlstate,
                timeout_kind,
                arrival_offset_ms,
                completion_offset_ms,
            ) = future.result()
            samples.append(
                PlacementSample(
                    index,
                    completion_order,
                    round(latency, 3),
                    result,
                    error_code,
                    error_type,
                    error_status,
                    error_retryable,
                    cause_type,
                    sqlstate,
                    timeout_kind,
                    round(arrival_offset_ms, 3),
                    round(completion_offset_ms, 3),
                )
            )

    latencies = [sample.latency_ms for sample in samples]
    successes = [sample for sample in samples if sample.result is not None]
    failures = [sample for sample in samples if sample.result is None]
    signatures = tuple(sorted(_explain_signature(sample.result) for sample in successes))
    snapshots = tuple(sorted(sample.result["placement"]["snapshotId"] for sample in successes))
    nodes = tuple(sorted(sample.result["placement"]["nodeId"] for sample in successes))
    fences = tuple(
        sorted(lease["fencingToken"] for sample in successes for lease in sample.result["leases"])
    )
    return (
        RoundEvidence(
            name=name,
            request_count=request_count,
            concurrency=concurrency,
            success_count=len(successes),
            failure_count=len(failures),
            p95_all_ms=round(percentile_nearest_rank(latencies, 0.95), 3),
            p95_success_ms=(
                round(percentile_nearest_rank([s.latency_ms for s in successes], 0.95), 3)
                if successes
                else None
            ),
            p95_failure_ms=(
                round(percentile_nearest_rank([s.latency_ms for s in failures], 0.95), 3)
                if failures
                else None
            ),
            max_ms=round(max(latencies), 3),
            explain_signatures=signatures,
            snapshot_ids=snapshots,
            node_ids=nodes,
            fencing_tokens=fences,
            failure_request_indexes=tuple(sorted(s.request_index for s in failures)),
            first_failure_completion_order=(
                min(s.completion_order for s in failures) if failures else None
            ),
            errors_by_code=dict(Counter(s.error_code for s in failures)),
            errors_by_sqlstate=dict(Counter(s.sqlstate or "none" for s in failures)),
            samples=tuple(sorted(samples, key=lambda sample: sample.request_index)),
        ),
        samples,
    )


def summarize(
    first: RoundEvidence,
    second: RoundEvidence | None,
    *,
    topology: str,
    code_sha: str,
    active_after_first: dict[str, int],
    active_after_rounds: list[dict[str, int]],
    expected_active_rounds: list[dict[str, int]],
    snapshot_replay_stable: bool | None,
    rounds_requested: int = 2,
) -> dict:
    deterministic = (
        bool(
            second
            and not first.failure_count
            and not second.failure_count
            and first.explain_signatures == second.explain_signatures
        )
        if rounds_requested > 1
        else None
    )
    rounds = [first] + ([second] if second else [])
    fences = tuple(token for item in rounds for token in item.fencing_tokens)
    unique_fences = len(set(fences)) == len(fences)
    no_overbooking = active_after_rounds == expected_active_rounds
    benchmark_complete = bool(
        len(rounds) == rounds_requested and all(item.failure_count == 0 for item in rounds)
    )

    def round_json(item: RoundEvidence) -> dict:
        return {
            "name": item.name,
            "successCount": item.success_count,
            "failureCount": item.failure_count,
            "p95AllMs": item.p95_all_ms,
            "p95SuccessMs": item.p95_success_ms,
            "p95FailureMs": item.p95_failure_ms,
            "maxMs": item.max_ms,
            "failureRequestIndexes": list(item.failure_request_indexes),
            "firstFailureCompletionOrder": item.first_failure_completion_order,
            "errorsByCode": item.errors_by_code,
            "errorsBySqlState": item.errors_by_sqlstate,
            "snapshotIds": list(item.snapshot_ids),
            "nodeIds": list(item.node_ids),
            "samples": [
                {
                    "requestIndex": sample.request_index,
                    "completionOrder": sample.completion_order,
                    "latencyMs": sample.latency_ms,
                    "arrivalOffsetMs": sample.arrival_offset_ms,
                    "completionOffsetMs": sample.completion_offset_ms,
                    "lockWaitInclusiveLatencyMs": sample.latency_ms,
                    "lockWaitSeparatelyMeasured": False,
                    "status": "success" if sample.result is not None else "failure",
                    "errorCode": sample.error_code,
                    "errorType": sample.error_type,
                    "errorStatus": sample.error_status,
                    "errorRetryable": sample.error_retryable,
                    "causeType": sample.cause_type,
                    "sqlState": sample.sqlstate,
                    "timeoutKind": sample.timeout_kind,
                    "snapshotId": (
                        sample.result["placement"]["snapshotId"]
                        if sample.result is not None
                        else None
                    ),
                    "nodeId": (
                        sample.result["placement"]["nodeId"] if sample.result is not None else None
                    ),
                }
                for sample in item.samples
            ],
        }

    successful_p95s = [item.p95_success_ms for item in rounds if item.p95_success_ms is not None]
    return {
        "schemaVersion": "1.1.0",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "codeSHA": code_sha,
        "scope": topology,
        "acceptanceClaim": False,
        "requestCount": first.request_count,
        "concurrency": first.concurrency,
        "roundsRequested": rounds_requested,
        "contentionObservation": {
            "databaseLockTimeoutMs": 500,
            "databaseStatementTimeoutMs": 2000,
            "requestLatencyIncludesLockWait": True,
            "serverSideLockWaitSeparatelyMeasured": False,
        },
        "rounds": [round_json(item) for item in rounds],
        "secondRoundStatus": (
            "completed"
            if second
            else "not_requested" if rounds_requested == 1 else "not_run_due_to_first_round_failure"
        ),
        "p95SuccessfulMsWorstRound": max(successful_p95s) if successful_p95s else None,
        "benchmarkComplete": benchmark_complete,
        "deterministicExplainAndSnapshot": deterministic,
        "snapshotIdStableOnIdempotentReplay": snapshot_replay_stable,
        "uniqueFencingTokens": unique_fences,
        "noOverbooking": no_overbooking,
        "expectedActiveAfterRounds": expected_active_rounds,
        "activeAfterRounds": active_after_rounds,
        "finding": (
            "F-S05-01"
            if any({"RES-0003", "RES-0007"}.intersection(item.errors_by_code) for item in rounds)
            else None
        ),
        "fiveNodeAC05": "not_evaluated",
    }


def write_junit(path: Path, report: dict, *, elapsed_seconds: float = 0.0) -> None:
    """Write one portable testcase for adapters that do not run through pytest."""

    failures = [
        name
        for name in (
            "benchmarkComplete",
            "deterministicExplainAndSnapshot",
            "snapshotIdStableOnIdempotentReplay",
            "uniqueFencingTokens",
            "noOverbooking",
        )
        if report[name] is False
    ]
    suite = ET.Element(
        "testsuite",
        name="placement-benchmark",
        tests="1",
        failures=str(bool(failures)).lower().replace("true", "1").replace("false", "0"),
        errors="0",
        skipped="0",
        time=f"{elapsed_seconds:.6f}",
    )
    case = ET.SubElement(
        suite,
        "testcase",
        classname="tools.placement_benchmark",
        name="concurrent_placement_is_deterministic_and_bounded",
        time=f"{elapsed_seconds:.6f}",
    )
    properties = ET.SubElement(case, "properties")
    for key in (
        "scope",
        "requestCount",
        "concurrency",
        "p95SuccessfulMsWorstRound",
        "benchmarkComplete",
        "deterministicExplainAndSnapshot",
        "snapshotIdStableOnIdempotentReplay",
        "uniqueFencingTokens",
        "noOverbooking",
        "fiveNodeAC05",
    ):
        ET.SubElement(properties, "property", name=key, value=str(report[key]))
    if failures:
        failure = ET.SubElement(case, "failure", message=";".join(failures))
        failure.text = "Benchmark invariant failure; inspect the paired JSON report."
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(suite).write(path, encoding="utf-8", xml_declaration=True)


def five_node_inventory_revision(payload: dict[str, Any]) -> str:
    """Return the revision for an inventory, excluding its self-reference."""

    revision_body = {key: value for key, value in payload.items() if key != "revision"}
    canonical = json.dumps(
        revision_body,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def _require_exact_keys(value: dict[str, Any], expected: set[str], *, where: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValueError(f"{where} keys mismatch: missing={missing}, extra={extra}")


def load_five_node_inventory(path: Path) -> dict[str, Any]:
    """Load and strictly validate the revision-fixed physical-node inventory."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot read five-node inventory: {error}") from None
    if not isinstance(payload, dict):
        raise ValueError("five-node inventory root must be an object")
    _require_exact_keys(
        payload,
        {"schemaVersion", "revision", "controlPlaneHostId", "nodes"},
        where="inventory",
    )
    if payload["schemaVersion"] != FIVE_NODE_INVENTORY_SCHEMA_VERSION:
        raise ValueError(f"inventory schemaVersion must be {FIVE_NODE_INVENTORY_SCHEMA_VERSION}")
    if (
        not isinstance(payload["controlPlaneHostId"], str)
        or not payload["controlPlaneHostId"].strip()
    ):
        raise ValueError("inventory controlPlaneHostId must be a non-empty string")
    if not isinstance(payload["nodes"], list) or not 1 <= len(payload["nodes"]) <= 5:
        raise ValueError("inventory nodes must contain between 1 and 5 physical nodes")

    revision = payload["revision"]
    expected_revision = five_node_inventory_revision(payload)
    if revision != expected_revision:
        raise ValueError(
            "inventory revision mismatch: " f"expected {expected_revision}, got {revision!r}"
        )

    seen: dict[str, set[str]] = {
        "nodeId": set(),
        "ip": set(),
        "certificateSHA256": set(),
        "hostId": set(),
    }
    colocated_count = 0
    for index, node in enumerate(payload["nodes"]):
        where = f"inventory.nodes[{index}]"
        if not isinstance(node, dict):
            raise ValueError(f"{where} must be an object")
        _require_exact_keys(
            node,
            {
                "nodeId",
                "ip",
                "certificateSHA256",
                "profile",
                "hostId",
                "failureDomainId",
                "coLocatedWithControlPlane",
                "measurementEligible",
                "exclusionReason",
            },
            where=where,
        )
        for field in ("nodeId", "ip", "certificateSHA256", "profile", "hostId", "failureDomainId"):
            if not isinstance(node[field], str) or not node[field].strip():
                raise ValueError(f"{where}.{field} must be a non-empty string")
        if not _NODE_ID_RE.fullmatch(node["nodeId"]):
            raise ValueError(f"{where}.nodeId is not a valid node identifier")
        try:
            address = ipaddress.ip_address(node["ip"])
        except ValueError:
            raise ValueError(f"{where}.ip must be an IPv4 address") from None
        if address.version != 4 or not address.is_private:
            raise ValueError(f"{where}.ip must be a private IPv4 address")
        if not _SHA256_RE.fullmatch(node["certificateSHA256"]):
            raise ValueError(f"{where}.certificateSHA256 must be 64 lowercase hex characters")
        if not isinstance(node["coLocatedWithControlPlane"], bool):
            raise ValueError(f"{where}.coLocatedWithControlPlane must be boolean")
        eligible = node["measurementEligible"]
        if not isinstance(eligible, dict):
            raise ValueError(f"{where}.measurementEligible must be an object")
        _require_exact_keys(eligible, {"s05", "s07"}, where=f"{where}.measurementEligible")
        if not all(isinstance(eligible[key], bool) for key in ("s05", "s07")):
            raise ValueError(f"{where}.measurementEligible values must be boolean")

        derived_colocation = node["hostId"] == payload["controlPlaneHostId"]
        if node["coLocatedWithControlPlane"] != derived_colocation:
            raise ValueError(f"{where}.coLocatedWithControlPlane disagrees with host identity")
        if derived_colocation:
            colocated_count += 1
            if colocated_count > 1:
                raise ValueError("inventory can contain at most one CP-colocated node")
            if eligible != {"s05": False, "s07": False}:
                raise ValueError(f"{where} CP-colocated node cannot join timed waves")
            if node["exclusionReason"] != "cp-host-colocation":
                raise ValueError(f"{where}.exclusionReason must be cp-host-colocation")
        else:
            if eligible != {"s05": True, "s07": True}:
                raise ValueError(f"{where} independent node must be eligible for S05 and S07")
            if node["exclusionReason"] is not None:
                raise ValueError(f"{where}.exclusionReason must be null")

        for field in seen:
            value = node[field]
            if value in seen[field]:
                raise ValueError(f"{where}.{field} duplicates another physical node")
            seen[field].add(value)
    return payload


_FIVE_NODE_PREFLIGHT_SQL = """
SELECT
    n.tenant_id::text AS tenant_id,
    n.node_id,
    n.status,
    n.heartbeat_at,
    n.recovery_epoch::text AS node_recovery_epoch,
    n.clock_skew_seconds,
    c.recovery_epoch::text AS channel_recovery_epoch,
    c.version AS channel_version,
    c.endpoint,
    c.certificate_sha256,
    c.certificate_not_after,
    c.enabled AS channel_enabled,
    s.recovery_epoch::text AS snapshot_recovery_epoch,
    s.channel_version AS snapshot_channel_version,
    s.received_at AS snapshot_received_at,
    s.snapshot,
    statement_timestamp() AS database_now
FROM inv.nodes AS n
LEFT JOIN inv.node_channels AS c
  ON c.tenant_id = n.tenant_id AND c.node_id = n.node_id
LEFT JOIN inv.node_resource_snapshots AS s
  ON s.tenant_id = n.tenant_id AND s.node_id = n.node_id
WHERE n.node_id = ANY(%s)
ORDER BY n.node_id, n.tenant_id
"""


def _seconds_since(value: datetime | None, now: datetime) -> float | None:
    if value is None:
        return None
    return (now - value).total_seconds()


def _endpoint_ip(endpoint: str | None) -> str | None:
    if not endpoint:
        return None
    try:
        parsed = urlsplit(endpoint)
        if parsed.scheme != "https":
            return None
        return parsed.hostname
    except ValueError:
        return None


def _assert_database_identity(node: dict[str, Any], row: dict[str, Any]) -> None:
    """Reject identity drift; readiness failures are reported separately."""

    node_id = node["nodeId"]
    if (
        row["certificate_sha256"] is not None
        and row["certificate_sha256"] != node["certificateSHA256"]
    ):
        raise ValueError(f"{node_id}: database certificate fingerprint differs from inventory")
    if row["endpoint"] is not None and _endpoint_ip(row["endpoint"]) != node["ip"]:
        raise ValueError(f"{node_id}: database mTLS endpoint differs from inventory IP")
    epochs = {
        row["node_recovery_epoch"],
        row["channel_recovery_epoch"],
        row["snapshot_recovery_epoch"],
    } - {None}
    if len(epochs) > 1:
        raise ValueError(f"{node_id}: node/channel/snapshot recovery epochs differ")
    if (
        row["channel_version"] is not None
        and row["snapshot_channel_version"] is not None
        and row["channel_version"] != row["snapshot_channel_version"]
    ):
        raise ValueError(f"{node_id}: channel and resource snapshot versions differ")
    snapshot = row["snapshot"]
    if snapshot is None:
        return
    if not isinstance(snapshot, dict):
        raise ValueError(f"{node_id}: resource snapshot is not an object")
    expected = {
        "tenantId": row["tenant_id"],
        "nodeId": node_id,
        "recoveryEpoch": row["node_recovery_epoch"],
        "profileVersion": node["profile"],
    }
    for field, value in expected.items():
        if snapshot.get(field) != value:
            raise ValueError(
                f"{node_id}: resource snapshot {field} differs from registered identity"
            )


def _resource_snapshot_complete(snapshot: dict[str, Any] | None) -> bool:
    if not isinstance(snapshot, dict):
        return False
    values = [
        snapshot.get("cpuCapacityMillis"),
        snapshot.get("memoryCapacityBytes"),
        snapshot.get("memoryAvailableBytes"),
    ]
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
        return False
    cpu_capacity, memory_capacity, memory_available = values
    return cpu_capacity > 0 and memory_capacity > 0 and 0 <= memory_available <= memory_capacity


def _node_preflight(node: dict[str, Any], row: dict[str, Any] | None) -> dict[str, Any]:
    reasons: list[str] = []
    if row is None:
        reasons.append("not-registered")
        readiness = {
            "registered": False,
            "statusOnline": False,
            "heartbeatFresh": False,
            "channelReady": False,
            "snapshotFresh": False,
            "resourceSnapshotComplete": False,
            "clockSkewAcceptable": False,
            "profileReady": node["profile"] == FIVE_NODE_PROFILE,
            "ready": False,
            "reasons": reasons,
        }
    else:
        _assert_database_identity(node, row)
        now = row["database_now"]
        heartbeat_age = _seconds_since(row["heartbeat_at"], now)
        snapshot_age = _seconds_since(row["snapshot_received_at"], now)
        status_online = row["status"] == "online"
        heartbeat_fresh = (
            heartbeat_age is not None and 0 <= heartbeat_age <= FIVE_NODE_FRESHNESS_SECONDS
        )
        channel_ready = bool(
            row["channel_enabled"]
            and row["certificate_not_after"] is not None
            and row["certificate_not_after"] > now
            and row["endpoint"] is not None
            and row["certificate_sha256"] is not None
        )
        snapshot_fresh = (
            snapshot_age is not None and 0 <= snapshot_age <= FIVE_NODE_FRESHNESS_SECONDS
        )
        snapshot_complete = _resource_snapshot_complete(row["snapshot"])
        clock_ok = row["clock_skew_seconds"] is not None and abs(row["clock_skew_seconds"]) <= 5
        profile_ready = node["profile"] == FIVE_NODE_PROFILE
        if not status_online:
            reasons.append("status-not-online")
        if not heartbeat_fresh:
            reasons.append("heartbeat-stale-or-missing")
        if not channel_ready:
            reasons.append("mtls-channel-not-ready")
        if not snapshot_fresh:
            reasons.append("resource-snapshot-stale-or-missing")
        if not snapshot_complete:
            reasons.append("resource-snapshot-incomplete")
        if not clock_ok:
            reasons.append("clock-skew-unacceptable")
        if not profile_ready:
            reasons.append("profile-not-lan-workspace-v1")
        readiness = {
            "registered": True,
            "statusOnline": status_online,
            "heartbeatFresh": heartbeat_fresh,
            "heartbeatAgeSeconds": round(heartbeat_age, 3) if heartbeat_age is not None else None,
            "channelReady": channel_ready,
            "snapshotFresh": snapshot_fresh,
            "resourceSnapshotComplete": snapshot_complete,
            "snapshotAgeSeconds": round(snapshot_age, 3) if snapshot_age is not None else None,
            "clockSkewAcceptable": clock_ok,
            "profileReady": profile_ready,
            "ready": not reasons,
            "reasons": reasons,
        }
    return {
        "nodeId": node["nodeId"],
        "ip": node["ip"],
        "certificateSHA256": node["certificateSHA256"],
        "profile": node["profile"],
        "hostId": node["hostId"],
        "failureDomainId": node["failureDomainId"],
        "coLocatedWithControlPlane": node["coLocatedWithControlPlane"],
        "coLocationValidation": "matched",
        "measurementEligible": node["measurementEligible"],
        "exclusionReason": node["exclusionReason"],
        "readiness": readiness,
        "selectedForAllFiveSmoke": readiness["ready"],
        "selectedForTimedWave": readiness["ready"] and node["measurementEligible"]["s05"],
    }


def five_node_lab_dry_run(
    inventory: dict[str, Any],
    dsn: str,
    *,
    connect: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Read physical registration state without creating or refreshing it."""

    if connect is None:
        from psycopg import connect as psycopg_connect
        from psycopg.rows import dict_row

        connect = lambda value: psycopg_connect(value, row_factory=dict_row)
    node_ids = [node["nodeId"] for node in inventory["nodes"]]
    try:
        with connect(dsn) as connection:
            connection.execute("SET TRANSACTION READ ONLY")
            read_only_row = connection.execute("SHOW transaction_read_only").fetchone()
            read_only_value = (
                next(iter(read_only_row.values()))
                if isinstance(read_only_row, dict)
                else read_only_row[0]
            )
            if str(read_only_value).lower() != "on":
                raise RuntimeError("database did not confirm a read-only transaction")
            rows = connection.execute(_FIVE_NODE_PREFLIGHT_SQL, (node_ids,)).fetchall()
    except ValueError:
        raise
    except Exception as error:
        raise RuntimeError(
            f"five-node-lab database preflight failed: {type(error).__name__}"
        ) from None

    rows_by_node: dict[str, dict[str, Any]] = {}
    tenants: set[str] = set()
    for row in rows:
        node_id = row["node_id"]
        if node_id in rows_by_node:
            raise ValueError(f"{node_id}: registered under more than one tenant")
        rows_by_node[node_id] = row
        tenants.add(row["tenant_id"])
    missing_node_ids = sorted(set(node_ids) - set(rows_by_node))
    if missing_node_ids:
        raise ValueError(
            "inventory nodes are not registered in PostgreSQL: " + ", ".join(missing_node_ids)
        )
    if len(tenants) > 1:
        raise ValueError("inventory nodes are registered under different tenants")

    nodes = [_node_preflight(node, rows_by_node.get(node["nodeId"])) for node in inventory["nodes"]]
    ready_nodes = [node for node in nodes if node["readiness"]["ready"]]
    timed_nodes = [node for node in nodes if node["selectedForTimedWave"]]
    colocated_count = sum(node["coLocatedWithControlPlane"] for node in nodes)
    eligible_count = sum(node["measurementEligible"]["s05"] for node in nodes)
    all_five_ready = (
        len(nodes) == 5 and len(ready_nodes) == 5 and colocated_count == 1 and eligible_count == 4
    )
    return {
        "schemaVersion": "five-node-lab-preflight:1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "adapter": "five-node-lab",
        "dryRun": True,
        "inventoryRevision": inventory["revision"],
        "databaseReadOnly": True,
        "syntheticRowsCreated": False,
        "heartbeatUpdated": False,
        "loadExecuted": False,
        "tenantId": next(iter(tenants), None),
        "nodes": nodes,
        "counts": {
            "inventory": len(nodes),
            "physicalExecutionHosts": len({node["hostId"] for node in nodes}),
            "registered": sum(node["readiness"]["registered"] for node in nodes),
            "ready": len(ready_nodes),
            "cpColocated": colocated_count,
            "cpIndependent": len(nodes) - colocated_count,
            "timedWaveEligible": eligible_count,
            "timedWaveSelected": len(timed_nodes),
        },
        "allFiveSmokeNodeIds": [node["nodeId"] for node in ready_nodes],
        "timedWaveNodeIds": [node["nodeId"] for node in timed_nodes],
        "allFiveSmokeReady": all_five_ready,
        "timedWaveReady": all_five_ready and len(timed_nodes) == 4,
    }


def _run_five_node_adapter(args: argparse.Namespace) -> int:
    if args.inventory is None:
        raise SystemExit("--inventory is required for --adapter five-node-lab")
    if not args.dry_run:
        raise SystemExit(
            "--adapter five-node-lab currently requires --dry-run; load execution is not enabled"
        )
    dsn = os.environ.get("INV_TEST_ADMIN_DSN")
    if not dsn:
        raise SystemExit("INV_TEST_ADMIN_DSN is required for --adapter five-node-lab")
    try:
        inventory = load_five_node_inventory(args.inventory)
        report = five_node_lab_dry_run(inventory, dsn)
    except (ValueError, RuntimeError) as error:
        raise SystemExit(str(error)) from None
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


def _run_pytest_adapter(args: argparse.Namespace) -> int:
    code_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    env = {
        **os.environ,
        "INV_PLACEMENT_BENCHMARK_REQUESTS": str(args.requests),
        "INV_PLACEMENT_BENCHMARK_CONCURRENCY": str(args.concurrency),
        "INV_PLACEMENT_BENCHMARK_ROUNDS": str(args.rounds),
        "INV_PLACEMENT_BENCHMARK_REPORT": str(args.report.resolve()),
        "INV_PLACEMENT_BENCHMARK_CODE_SHA": code_sha,
        "INV_PLACEMENT_SHORT_COMMIT": "1" if args.mode == "short-commit" else "0",
        "INV_PLACEMENT_CANDIDATE_LIMIT_LOCK_TIMEOUT_MS": str(args.candidate_limit_lock_timeout_ms),
        "INV_PLACEMENT_QUEUE_DIAGNOSTIC": "1" if args.queue_diagnostic else "0",
        "INV_PLACEMENT_SQL_DIAGNOSTIC": "1" if args.queue_diagnostic else "0",
    }
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-s",
        "tests/integration/test_placement_benchmark.py",
        "-o",
        "junit_family=xunit1",
        "--junitxml",
        str(args.junit.resolve()),
    ]
    completed = subprocess.run(command, cwd=ROOT, env=env, timeout=args.timeout)
    return completed.returncode


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requests", type=int, default=50)
    parser.add_argument("--concurrency", type=int, default=50)
    parser.add_argument("--rounds", type=int, choices=(1, 2), default=2)
    parser.add_argument("--junit", type=Path, default=ROOT / ".work/placement-benchmark.xml")
    parser.add_argument("--report", type=Path, default=ROOT / ".work/placement-benchmark.json")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument(
        "--adapter",
        choices=("synthetic", "five-node-lab"),
        default="synthetic",
        help="benchmark state adapter (default: existing synthetic PostgreSQL fixture)",
    )
    parser.add_argument(
        "--inventory",
        type=Path,
        help="revision-fixed physical-node inventory for the five-node-lab adapter",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="read and classify physical nodes without running a placement wave",
    )
    parser.add_argument(
        "--mode",
        choices=("legacy", "short-commit"),
        default="legacy",
        help="placement feature-flag mode (default: legacy/off)",
    )
    parser.add_argument(
        "--candidate-limit-lock-timeout-ms",
        type=int,
        default=500,
        help=(
            "transaction-local lock_timeout for the candidate limits-row statement "
            "only (1..1900; default: 500)"
        ),
    )
    parser.add_argument(
        "--queue-diagnostic",
        action="store_true",
        help=(
            "sample pg_stat_activity wait events and retain request arrival offsets; "
            "also enables parameter-free SQL diagnostics"
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.adapter == "five-node-lab":
        return _run_five_node_adapter(args)
    if args.inventory is not None or args.dry_run:
        raise SystemExit("--inventory/--dry-run are only valid with --adapter five-node-lab")
    if not 1 <= args.requests <= 200:
        raise SystemExit("--requests must be between 1 and 200")
    if args.concurrency != args.requests:
        raise SystemExit("--concurrency must equal --requests for a simultaneous wave")
    if not 1 <= args.candidate_limit_lock_timeout_ms <= 1900:
        raise SystemExit("--candidate-limit-lock-timeout-ms must be between 1 and 1900")
    if args.mode != "short-commit" and args.candidate_limit_lock_timeout_ms != 500:
        raise SystemExit("--candidate-limit-lock-timeout-ms is only valid with --mode short-commit")
    args.junit.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    return _run_pytest_adapter(args)


if __name__ == "__main__":
    raise SystemExit(main())
