#!/usr/bin/env python3
"""Run the S07 node-loss/recovery measurement against disposable PostgreSQL.

The subprocess is a pytest integration test so the repository's normal
random-database/random-login-role fixture creates and removes every measured
row. JSON carries distributions and semantic limitations; JUnit carries the
executable pass/fail result. This is deliberately not physical-five-node
acceptance: replacement bytes are represented by a verified synthetic fixture
only after the product liveness and repair-planning paths have run.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

KERNEL_FRESHNESS_SECONDS = 15.0
PHYSICAL_ACCEPTANCE_NODES = 5
PHYSICAL_LIVENESS_SECONDS = 60.0


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return parsed


def probability(value: str) -> float:
    parsed = float(value)
    if not 0 <= parsed <= 1:
        raise argparse.ArgumentTypeError("must be between 0 and 1")
    return parsed


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, int(len(ordered) * fraction + 0.999999999))
    return round(ordered[min(rank, len(ordered)) - 1], 6)


def summarize(config: dict[str, Any], rounds: list[dict[str, Any]]) -> dict[str, Any]:
    delays = [float(item["detectionDelaySeconds"]) for item in rounds if item["detected"]]
    attempted = sum(int(item["shardsAttempted"]) for item in rounds)
    recovered = sum(int(item["shardsRecovered"]) for item in rounds)
    success_rate = recovered / attempted if attempted else 0.0
    acceptance_shape = (
        config["nodes"] == PHYSICAL_ACCEPTANCE_NODES
        and config["livenessTimeoutSeconds"] == PHYSICAL_LIVENESS_SECONDS
    )
    findings: list[dict[str, str]] = [
        {
            "id": "F-S07-02",
            "severity": "acceptance-boundary",
            "summary": (
                "Current replica repair code plans and marks state; the harness fixture "
                "does not prove physical byte transfer or execution-shard replay."
            ),
        },
        {
            "id": "F-S07-03",
            "severity": "slo-boundary",
            "summary": (
                "The liveness predicate is last_seen < now-timeout, so an exact 60.000s "
                "upper bound has no scheduling margin; polling adds further delay."
            ),
        },
    ]
    if any(int(item.get("freshReplacementCandidates", 0)) == 0 for item in rounds):
        findings.append(
            {
                "id": "F-S07-01",
                "severity": "kernel-boundary",
                "summary": (
                    "No survivor had a fresh replacement observation. The 15s kernel "
                    "window must be refreshed independently during the 60s departure "
                    "wait; recovery must not reuse the departure-time snapshot."
                ),
            }
        )
    return {
        "schemaVersion": 1,
        "measurementScope": "disposable-postgresql-synthetic-measured-nodes",
        "nodesPerRound": config["nodes"],
        "repetitions": config["repetitions"],
        "livenessTimeoutSeconds": config["livenessTimeoutSeconds"],
        "pollIntervalSeconds": config["pollIntervalSeconds"],
        "maxDetectionSeconds": config["maxDetectionSeconds"],
        "targetRecoverySuccessRate": config["targetRecoverySuccessRate"],
        "acceptanceShapeRequested": acceptance_shape,
        "operationalAcceptanceAssessed": False,
        "projectLockContentionMeasured": False,
        "kernelFreshnessSeconds": KERNEL_FRESHNESS_SECONDS,
        "syntheticRecoveryMode": "verified-owner-fixture-after-product-repair-plan",
        "detectionDelaySeconds": {
            "min": round(min(delays), 6) if delays else None,
            "p50": percentile(delays, 0.50),
            "p95": percentile(delays, 0.95),
            "max": round(max(delays), 6) if delays else None,
        },
        "shardsAttempted": attempted,
        "shardsRecovered": recovered,
        "syntheticShardRecoverySuccessRate": round(success_rate, 6),
        "detectionSloMet": bool(delays) and max(delays) <= config["maxDetectionSeconds"],
        "recoveryTargetMet": attempted > 0 and success_rate >= config["targetRecoverySuccessRate"],
        "findings": findings,
        "rounds": rounds,
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--nodes", type=positive_int, required=True)
    result.add_argument("--repetitions", type=positive_int, required=True)
    result.add_argument("--liveness-timeout-seconds", type=positive_float, required=True)
    result.add_argument("--poll-interval-seconds", type=positive_float, default=0.1)
    result.add_argument("--max-detection-seconds", type=positive_float, required=True)
    result.add_argument("--target-recovery-success-rate", type=probability, default=0.95)
    result.add_argument("--json-out", type=Path, required=True)
    result.add_argument("--junit-out", type=Path, required=True)
    return result


def validated_config(args: argparse.Namespace) -> dict[str, Any]:
    if not 3 <= args.nodes <= 50:
        raise ValueError("nodes must be between 3 and 50")
    if args.repetitions > 100:
        raise ValueError("repetitions must not exceed 100")
    if args.liveness_timeout_seconds > 300:
        raise ValueError("liveness timeout must not exceed 300 seconds")
    if args.poll_interval_seconds > args.liveness_timeout_seconds:
        raise ValueError("poll interval must not exceed liveness timeout")
    if args.max_detection_seconds < args.liveness_timeout_seconds:
        raise ValueError("max detection must not be below the configured timeout")
    if args.json_out.resolve() == args.junit_out.resolve():
        raise ValueError("JSON and JUnit outputs must be different files")
    return {
        "nodes": args.nodes,
        "repetitions": args.repetitions,
        "livenessTimeoutSeconds": args.liveness_timeout_seconds,
        "pollIntervalSeconds": args.poll_interval_seconds,
        "maxDetectionSeconds": args.max_detection_seconds,
        "targetRecoverySuccessRate": args.target_recovery_success_rate,
    }


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        config = validated_config(args)
    except ValueError as exc:
        parser().error(str(exc))
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.junit_out.parent.mkdir(parents=True, exist_ok=True)
    # A failed rerun must never leave an earlier green artifact looking current.
    args.json_out.unlink(missing_ok=True)
    args.junit_out.unlink(missing_ok=True)
    environment = os.environ.copy()
    environment["INV_S07_MEASUREMENT_CONFIG"] = json.dumps(config, separators=(",", ":"))
    environment["INV_S07_MEASUREMENT_JSON"] = str(args.json_out.resolve())
    environment["PYTHONUTF8"] = "1"
    root = Path(__file__).resolve().parents[1]
    python_paths = [str(root / "src"), str(root / "services" / "control-plane" / "src")]
    if environment.get("PYTHONPATH"):
        python_paths.append(environment["PYTHONPATH"])
    environment["PYTHONPATH"] = os.pathsep.join(python_paths)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/integration/s07_recovery_measurement_case.py",
            f"--junitxml={args.junit_out.resolve()}",
        ],
        cwd=root,
        env=environment,
        check=False,
    )
    if not args.json_out.is_file():
        print("S07 measurement did not produce JSON", file=sys.stderr)
        return completed.returncode or 2
    print(
        json.dumps(
            {
                "json": str(args.json_out.resolve()),
                "junit": str(args.junit_out.resolve()),
                "pytestExitCode": completed.returncode,
            },
            separators=(",", ":"),
        )
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
