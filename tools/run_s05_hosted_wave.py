#!/usr/bin/env python3
"""Run the opt-in S05 legacy/candidate-B hosted measurement lane.

The six PostgreSQL waves run strictly one at a time.  Request-level benchmark
failures are evidence, not an infrastructure failure, so the aggregate JUnit
reports measurement completeness while the JSON records the three promotion
gates independently.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import statistics
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg

ROOT = Path(__file__).resolve().parents[1]
WAVE_COUNT = 3
REQUEST_COUNT = 20
SEMAPHORE_LIMIT = 4
LOCK_TIMEOUT_MS = 500


@dataclass(frozen=True)
class WaveSpec:
    mode: str
    ordinal: int

    @property
    def name(self) -> str:
        return f"{self.mode}-{self.ordinal}"

    @property
    def candidate(self) -> bool:
        return self.mode == "candidate-b"


def wave_specs() -> list[WaveSpec]:
    return [
        *(WaveSpec("legacy", ordinal) for ordinal in range(1, WAVE_COUNT + 1)),
        *(WaveSpec("candidate-b", ordinal) for ordinal in range(1, WAVE_COUNT + 1)),
    ]


def benchmark_command(
    spec: WaveSpec,
    *,
    python: str,
    output_dir: Path,
    timeout_seconds: int,
) -> list[str]:
    command = [
        python,
        str(ROOT / "tools" / "placement_benchmark.py"),
        "--requests",
        str(REQUEST_COUNT),
        "--concurrency",
        str(REQUEST_COUNT),
        "--rounds",
        "1",
        "--timeout",
        str(timeout_seconds),
        "--report",
        str(output_dir / f"{spec.name}.json"),
        "--junit",
        str(output_dir / f"{spec.name}.xml"),
    ]
    if spec.candidate:
        command.extend(
            [
                "--mode",
                "short-commit",
                "--candidate-limit-lock-timeout-ms",
                str(LOCK_TIMEOUT_MS),
                "--project-semaphore",
                "--project-semaphore-limit",
                str(SEMAPHORE_LIMIT),
            ]
        )
    else:
        command.extend(["--mode", "legacy"])
    return command


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_wave_report(spec: WaveSpec, report: dict[str, Any], code_sha: str) -> None:
    _require(report.get("schemaVersion") == "1.8.0", f"{spec.name}: schemaVersion")
    _require(report.get("codeSHA") == code_sha, f"{spec.name}: codeSHA")
    _require(report.get("requestCount") == REQUEST_COUNT, f"{spec.name}: requestCount")
    _require(report.get("concurrency") == REQUEST_COUNT, f"{spec.name}: concurrency")
    _require(report.get("roundsRequested") == 1, f"{spec.name}: roundsRequested")
    _require(len(report.get("rounds", [])) == 1, f"{spec.name}: one completed wave required")
    _require(report.get("uniqueFencingTokens") is True, f"{spec.name}: fencing invariant")
    _require(report.get("noOverbooking") is True, f"{spec.name}: no-overbooking invariant")
    _require(report.get("acceptanceClaim") is False, f"{spec.name}: acceptance claim forbidden")

    semaphore = report.get("projectSemaphore", {})
    _require(semaphore.get("enabled") is spec.candidate, f"{spec.name}: semaphore mode")
    _require(
        semaphore.get("registryEntryCountAfterWave") == 0,
        f"{spec.name}: semaphore registry entry residue",
    )
    _require(
        semaphore.get("registryPermitCountAfterWave") == 0,
        f"{spec.name}: semaphore permit residue",
    )
    if spec.candidate:
        _require(semaphore.get("limit") == SEMAPHORE_LIMIT, f"{spec.name}: semaphore limit")
        _require(
            semaphore.get("permitWaitBudgetMs") == 0,
            f"{spec.name}: permit wait budget",
        )
    _require(
        report.get("contentionObservation", {}).get("candidateLimitLockTimeoutMs")
        == LOCK_TIMEOUT_MS,
        f"{spec.name}: lock timeout budget",
    )


def _wave_metrics(report: dict[str, Any]) -> dict[str, Any]:
    round_report = report["rounds"][0]
    return {
        "successCount": round_report["successCount"],
        "failureCount": round_report["failureCount"],
        "p95AllMs": round_report["p95AllMs"],
        "p95SuccessMs": round_report["p95SuccessMs"],
        "externalFailureCount": report["externalFailure"]["count"],
        "semaphoreRejectCount": report["externalFailure"]["semaphoreRejectCount"],
        "sqlTimeoutCount": report["externalFailure"]["sqlTimeoutCount"],
        "postAcquireHoldP95Ms": report["lockHold"]["commitP95Ms"],
        "permitHoldP95Ms": report["projectSemaphore"]["permitHoldP95Ms"],
        "registryEntryCountAfterWave": report["projectSemaphore"]["registryEntryCountAfterWave"],
        "registryPermitCountAfterWave": report["projectSemaphore"]["registryPermitCountAfterWave"],
    }


def _median(waves: list[dict[str, Any]], key: str) -> float:
    values = [wave["metrics"][key] for wave in waves]
    _require(all(value is not None for value in values), f"missing metric: {key}")
    return round(float(statistics.median(values)), 3)


def evaluate(waves: list[dict[str, Any]]) -> dict[str, Any]:
    legacy = [wave for wave in waves if wave["mode"] == "legacy"]
    candidate = [wave for wave in waves if wave["mode"] == "candidate-b"]
    _require(len(legacy) == WAVE_COUNT, "three legacy waves required")
    _require(len(candidate) == WAVE_COUNT, "three candidate-B waves required")

    legacy_external = sum(wave["metrics"]["externalFailureCount"] for wave in legacy)
    candidate_external = sum(wave["metrics"]["externalFailureCount"] for wave in candidate)
    legacy_all_p95 = _median(legacy, "p95AllMs")
    candidate_all_p95 = _median(candidate, "p95AllMs")
    legacy_hold_p95 = _median(legacy, "postAcquireHoldP95Ms")
    candidate_hold_p95 = _median(candidate, "postAcquireHoldP95Ms")
    gates = {
        "externalFailureNonIncrease": candidate_external <= legacy_external,
        "allRequestP95MedianNonWorse": candidate_all_p95 <= legacy_all_p95,
        "successfulPostAcquireHoldP95MedianNonWorse": candidate_hold_p95 <= legacy_hold_p95,
    }
    return {
        "legacy": {
            "externalFailureTotal": legacy_external,
            "allRequestP95MedianMs": legacy_all_p95,
            "successfulPostAcquireHoldP95MedianMs": legacy_hold_p95,
        },
        "candidateB": {
            "externalFailureTotal": candidate_external,
            "allRequestP95MedianMs": candidate_all_p95,
            "successfulPostAcquireHoldP95MedianMs": candidate_hold_p95,
        },
        "gates": gates,
        "candidateDecision": "GATES_PASSED" if all(gates.values()) else "GATES_FAILED",
        "promotionClaim": False,
        "s05StatusAfterRun": "in_progress",
    }


def runner_environment() -> dict[str, Any]:
    memory_kib = None
    meminfo = Path("/proc/meminfo")
    if meminfo.is_file():
        for line in meminfo.read_text(encoding="utf-8").splitlines():
            if line.startswith("MemTotal:"):
                memory_kib = int(line.split()[1])
                break
    return {
        "runnerOS": os.getenv("RUNNER_OS", platform.system()),
        "runnerArch": os.getenv("RUNNER_ARCH", platform.machine()),
        "runnerName": os.getenv("RUNNER_NAME", "unknown"),
        "imageOS": os.getenv("ImageOS", "unknown"),
        "imageVersion": os.getenv("ImageVersion", "unknown"),
        "cpuCount": os.cpu_count(),
        "memoryTotalKiB": memory_kib,
        "pythonVersion": platform.python_version(),
        "githubRunId": os.getenv("GITHUB_RUN_ID", "local-unset"),
        "githubRunAttempt": os.getenv("GITHUB_RUN_ATTEMPT", "local-unset"),
    }


def validate_product_sha(product_sha: str, checkout_sha: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{40}", product_sha):
        raise SystemExit("INV_MEASUREMENT_TARGET_PRODUCT_SHA must be a full lowercase Git SHA")
    completed = subprocess.run(
        ["git", "merge-base", "--is-ancestor", product_sha, checkout_sha],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if completed.returncode != 0:
        raise SystemExit("measurement target product SHA must be an ancestor of the checkout")


def postgres_environment(dsn: str) -> dict[str, Any]:
    with psycopg.connect(dsn) as connection:
        row = connection.execute(
            "SELECT current_setting('server_version'), current_setting('server_version_num'), "
            "current_setting('lock_timeout'), current_setting('statement_timeout'), "
            "current_setting('max_connections')"
        ).fetchone()
    return {
        "serverVersion": row[0],
        "serverVersionNum": row[1],
        "serviceDefaultLockTimeout": row[2],
        "serviceDefaultStatementTimeout": row[3],
        "maxConnections": int(row[4]),
        "benchmarkTransactionLockTimeoutMs": LOCK_TIMEOUT_MS,
        "benchmarkTransactionStatementTimeoutMs": 2000,
    }


def write_junit(path: Path, summary: dict[str, Any]) -> None:
    suite = ET.Element(
        "testsuite",
        name="s05-hosted-wave",
        tests="1",
        failures="0",
        errors="0",
        skipped="0",
    )
    case = ET.SubElement(
        suite,
        "testcase",
        classname="tools.run_s05_hosted_wave",
        name="six_sequential_waves_produced_complete_evidence",
    )
    properties = ET.SubElement(case, "properties")
    values = {
        "codeSha": summary["codeSha"],
        "measurementTargetProductSha": summary["measurementTargetProductSha"],
        "candidateDecision": summary["evaluation"]["candidateDecision"],
        **summary["evaluation"]["gates"],
        "promotionClaim": False,
        "s05StatusAfterRun": "in_progress",
        "directlyComparableWithLocal": False,
    }
    for name, value in values.items():
        ET.SubElement(properties, "property", name=name, value=str(value))
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(suite).write(path, encoding="utf-8", xml_declaration=True)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist" / "s05-hosted-wave")
    parser.add_argument("--timeout-seconds", type=int, default=240)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    dsn = os.getenv("INV_TEST_ADMIN_DSN")
    if not dsn:
        raise SystemExit("INV_TEST_ADMIN_DSN is required")
    code_sha = (
        os.getenv("INV_EVIDENCE_CODE_SHA")
        or subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    )
    checkout_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    if code_sha != checkout_sha:
        raise SystemExit("INV_EVIDENCE_CODE_SHA must match the checked-out PR head")
    product_sha = os.getenv("INV_MEASUREMENT_TARGET_PRODUCT_SHA", "")
    validate_product_sha(product_sha, checkout_sha)

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    waves: list[dict[str, Any]] = []
    for spec in wave_specs():
        command = benchmark_command(
            spec,
            python=sys.executable,
            output_dir=output_dir,
            timeout_seconds=args.timeout_seconds,
        )
        log_path = output_dir / f"{spec.name}.log"
        with log_path.open("w", encoding="utf-8") as log:
            completed = subprocess.run(
                command,
                cwd=ROOT,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=args.timeout_seconds + 30,
                check=False,
            )
        report_path = output_dir / f"{spec.name}.json"
        junit_path = output_dir / f"{spec.name}.xml"
        if not report_path.is_file() or not junit_path.is_file():
            raise SystemExit(f"{spec.name}: benchmark did not produce JSON and JUnit")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        validate_wave_report(spec, report, code_sha)
        if completed.returncode not in (0, 1):
            raise SystemExit(
                f"{spec.name}: unexpected benchmark process exit {completed.returncode}"
            )
        waves.append(
            {
                "name": spec.name,
                "mode": spec.mode,
                "ordinal": spec.ordinal,
                "benchmarkExitCode": completed.returncode,
                "reportFile": report_path.name,
                "junitFile": junit_path.name,
                "logFile": log_path.name,
                "metrics": _wave_metrics(report),
            }
        )

    summary = {
        "schemaVersion": "1.0.0",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "codeSha": code_sha,
        "measurementTargetProductSha": product_sha,
        "measurementComplete": True,
        "measurementScope": "hosted-single-runner-synthetic-node-postgresql16",
        "directlyComparableWithLocalEvidence": False,
        "comparisonBoundary": (
            "Hosted runner results are an independent calibration and must not be numerically "
            "merged with development-PC evidence."
        ),
        "flagDefaultOff": True,
        "wavePlan": {
            "order": "legacy-1..3 then candidate-b-1..3; strictly sequential",
            "requestsPerWave": REQUEST_COUNT,
            "concurrency": REQUEST_COUNT,
            "candidateSemaphoreLimit": SEMAPHORE_LIMIT,
            "candidateLockTimeoutMs": LOCK_TIMEOUT_MS,
        },
        "runner": runner_environment(),
        "postgresql": postgres_environment(dsn),
        "waves": waves,
        "evaluation": evaluate(waves),
    }
    summary_path = output_dir / "s05-hosted-wave-summary.json"
    junit_path = output_dir / "s05-hosted-wave-summary.xml"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_junit(junit_path, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
