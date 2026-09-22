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
import json
import math
import os
from pathlib import Path
import subprocess
import sys
from threading import Barrier
from time import perf_counter_ns
from typing import Callable
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


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
                    else "statement_timeout"
                    if sqlstate == "57014"
                    else None
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
            else "not_requested"
            if rounds_requested == 1
            else "not_run_due_to_first_round_failure"
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
            if any(
                {"RES-0003", "RES-0007"}.intersection(item.errors_by_code)
                for item in rounds
            )
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
        "--mode",
        choices=("legacy", "short-commit"),
        default="legacy",
        help="placement feature-flag mode (default: legacy/off)",
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
    if not 1 <= args.requests <= 200:
        raise SystemExit("--requests must be between 1 and 200")
    if args.concurrency != args.requests:
        raise SystemExit("--concurrency must equal --requests for a simultaneous wave")
    args.junit.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    return _run_pytest_adapter(args)


if __name__ == "__main__":
    raise SystemExit(main())
