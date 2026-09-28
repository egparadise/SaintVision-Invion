#!/usr/bin/env python3
"""Run the opt-in S05 legacy-only hosted concurrency staircase.

Each benchmark invocation owns a fresh disposable PostgreSQL database.  Three
waves are completed at a rung before either proceeding or stopping at the
first preregistered degradation signal.
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
RUNGS = (20, 35, 50)
WAVES_PER_RUNG = 3
LOCK_TIMEOUT_MS = 500
STATEMENT_TIMEOUT_MS = 2000
P95_ALL_CUMULATIVE_THRESHOLD_MS = 2000.0


@dataclass(frozen=True)
class WaveSpec:
    concurrency: int
    ordinal: int

    @property
    def name(self) -> str:
        return f"legacy-c{self.concurrency}-{self.ordinal}"


def rung_specs(concurrency: int) -> list[WaveSpec]:
    if concurrency not in RUNGS:
        raise ValueError(f"unsupported rung: {concurrency}")
    return [WaveSpec(concurrency, ordinal) for ordinal in range(1, WAVES_PER_RUNG + 1)]


def benchmark_command(
    spec: WaveSpec, *, python: str, output_dir: Path, timeout_seconds: int
) -> list[str]:
    return [
        python,
        str(ROOT / "tools" / "placement_benchmark.py"),
        "--requests",
        str(spec.concurrency),
        "--concurrency",
        str(spec.concurrency),
        "--rounds",
        "1",
        "--timeout",
        str(timeout_seconds),
        "--report",
        str(output_dir / f"{spec.name}.json"),
        "--junit",
        str(output_dir / f"{spec.name}.xml"),
        "--mode",
        "legacy",
    ]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _database_fingerprint(report: dict[str, Any]) -> str:
    database = report.get("disposableDatabase", {})
    fingerprint = database.get("fingerprintSha256")
    _require(
        isinstance(fingerprint, str) and re.fullmatch(r"[0-9a-f]{64}", fingerprint) is not None,
        "disposable database fingerprint",
    )
    _require(database.get("nameExposed") is False, "database name must stay redacted")
    _require(
        database.get("lifecycle") == "unique-pytest-session-database",
        "disposable database lifecycle",
    )
    return fingerprint


def validate_wave_report(spec: WaveSpec, report: dict[str, Any], code_sha: str) -> None:
    _require(report.get("schemaVersion") == "1.7.0", f"{spec.name}: schemaVersion")
    _require(report.get("codeSHA") == code_sha, f"{spec.name}: codeSHA")
    _require(report.get("requestCount") == spec.concurrency, f"{spec.name}: requestCount")
    _require(report.get("concurrency") == spec.concurrency, f"{spec.name}: concurrency")
    _require(report.get("roundsRequested") == 1, f"{spec.name}: roundsRequested")
    _require(len(report.get("rounds", [])) == 1, f"{spec.name}: one wave required")
    _require(report.get("uniqueFencingTokens") is True, f"{spec.name}: fencing invariant")
    _require(report.get("noOverbooking") is True, f"{spec.name}: no-overbooking invariant")
    _require(report.get("acceptanceClaim") is False, f"{spec.name}: acceptance claim forbidden")
    _require("projectSemaphore" not in report, f"{spec.name}: semaphore evidence forbidden")
    _require(
        report.get("contentionObservation", {}).get("candidateLimitLockTimeoutMs")
        == LOCK_TIMEOUT_MS,
        f"{spec.name}: lock timeout budget",
    )
    _database_fingerprint(report)


def _wave_metrics(report: dict[str, Any]) -> dict[str, Any]:
    round_report = report["rounds"][0]
    sqlstates = round_report.get("errorsBySqlState", {})
    lock_timeout_count = int(sqlstates.get("55P03", 0))
    statement_timeout_count = int(sqlstates.get("57014", 0))
    timeout_count = lock_timeout_count + statement_timeout_count
    return {
        "successCount": round_report["successCount"],
        "failureCount": round_report["failureCount"],
        "p95AllMs": round_report["p95AllMs"],
        "p95SuccessMs": round_report["p95SuccessMs"],
        "maxRequestMs": round_report["maxMs"],
        "lockTimeout55P03Count": lock_timeout_count,
        "statementTimeout57014Count": statement_timeout_count,
        "sqlTimeoutCount": timeout_count,
        "postAcquireHoldP95Ms": report["lockHold"]["commitP95Ms"],
        "postAcquireHoldMaxMs": report["lockHold"]["commitMaxMs"],
        "legacyLockWaitP95Ms": report["legacyLockWait"]["p95Ms"],
        "legacyLockWaitMaxMs": report["legacyLockWait"]["maxMs"],
    }


def evaluate_rung(concurrency: int, waves: list[dict[str, Any]]) -> dict[str, Any]:
    _require(len(waves) == WAVES_PER_RUNG, "three completed waves required")
    _require(all(wave["concurrency"] == concurrency for wave in waves), "rung mismatch")
    maximum_timeout_count = max(wave["metrics"]["sqlTimeoutCount"] for wave in waves)
    median_p95_all = round(
        float(statistics.median(wave["metrics"]["p95AllMs"] for wave in waves)), 3
    )
    criteria = {
        "anyWaveHas55P03Or57014": maximum_timeout_count > 0,
        "medianCumulativeRequestP95AllExceeds2000Ms": (
            median_p95_all > P95_ALL_CUMULATIVE_THRESHOLD_MS
        ),
    }
    return {
        "concurrency": concurrency,
        "waveCount": len(waves),
        "maximumWaveSqlTimeoutCount": maximum_timeout_count,
        "medianRequestP95AllMs": median_p95_all,
        "criteria": criteria,
        "degraded": any(criteria.values()),
        "criterionAggregationIsIntentional": {
            "sqlTimeout": "maximum; any one wave triggers",
            "requestP95All": "median of three waves",
        },
        "cumulativeLatencyCriterion": (
            "End-to-end request latency across multiple statements; it may exceed the "
            "2000ms per-statement timeout without any individual statement timing out."
        ),
    }


def owned_disposable_count(dsn: str) -> int:
    with psycopg.connect(dsn) as connection:
        row = connection.execute(
            "SELECT count(*) FROM pg_database WHERE datname LIKE 'inv_test_%'"
        ).fetchone()
    return int(row[0])


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
        "benchmarkTransactionStatementTimeoutMs": STATEMENT_TIMEOUT_MS,
    }


def validate_code_sha(code_sha: str, checkout_sha: str) -> None:
    if re.fullmatch(r"[0-9a-f]{40}", code_sha) is None:
        raise SystemExit("INV_EVIDENCE_CODE_SHA must be a full lowercase Git SHA")
    if code_sha != checkout_sha:
        raise SystemExit("INV_EVIDENCE_CODE_SHA must match the checked-out PR head")


def write_junit(path: Path, summary: dict[str, Any]) -> None:
    suite = ET.Element(
        "testsuite", name="s05-legacy-staircase", tests="1", failures="0", errors="0", skipped="0"
    )
    case = ET.SubElement(
        suite,
        "testcase",
        classname="tools.run_s05_legacy_staircase",
        name="preregistered_legacy_staircase_completed",
    )
    properties = ET.SubElement(case, "properties")
    values = {
        "codeSha": summary["codeSha"],
        "runPurpose": summary["runPurpose"],
        "canonicalDecisionEvidenceRunId": summary["canonicalDecisionEvidenceRunId"],
        "decision": summary["evaluation"]["decision"],
        "firstDegradeConcurrency": summary["evaluation"]["firstDegradeConcurrency"],
        "semaphoreProductCodePresent": False,
        "promotionClaim": False,
        "directlyComparableWithLocal": False,
    }
    for name, value in values.items():
        ET.SubElement(properties, "property", name=name, value=str(value))
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(suite).write(path, encoding="utf-8", xml_declaration=True)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist" / "s05-legacy-staircase")
    parser.add_argument("--timeout-seconds", type=int, default=300)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    dsn = os.getenv("INV_TEST_ADMIN_DSN")
    if not dsn:
        raise SystemExit("INV_TEST_ADMIN_DSN is required")
    checkout_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    code_sha = os.getenv("INV_EVIDENCE_CODE_SHA", checkout_sha)
    validate_code_sha(code_sha, checkout_sha)
    if owned_disposable_count(dsn) != 0:
        raise SystemExit("hosted PostgreSQL service is not clean before staircase")

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    waves: list[dict[str, Any]] = []
    rung_evaluations: list[dict[str, Any]] = []
    fingerprints: set[str] = set()
    first_degrade: int | None = None

    for concurrency in RUNGS:
        rung_waves: list[dict[str, Any]] = []
        for spec in rung_specs(concurrency):
            _require(owned_disposable_count(dsn) == 0, f"{spec.name}: pre-wave residue")
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
                raise SystemExit(f"{spec.name}: unexpected exit {completed.returncode}")
            _require(owned_disposable_count(dsn) == 0, f"{spec.name}: post-wave residue")
            fingerprint = _database_fingerprint(report)
            _require(fingerprint not in fingerprints, f"{spec.name}: database was reused")
            fingerprints.add(fingerprint)
            wave = {
                "name": spec.name,
                "concurrency": spec.concurrency,
                "ordinal": spec.ordinal,
                "benchmarkExitCode": completed.returncode,
                "databaseFingerprintSha256": fingerprint,
                "reportFile": report_path.name,
                "junitFile": junit_path.name,
                "logFile": log_path.name,
                "metrics": _wave_metrics(report),
            }
            waves.append(wave)
            rung_waves.append(wave)

        rung_result = evaluate_rung(concurrency, rung_waves)
        rung_evaluations.append(rung_result)
        if rung_result["degraded"]:
            first_degrade = concurrency
            break

    decision = (
        f"DEGRADE_AT_{first_degrade}"
        if first_degrade is not None
        else "NO_DEGRADE_THROUGH_50_CLOSE_SEMAPHORE_LINE"
    )
    summary = {
        "schemaVersion": "1.0.0",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "codeSha": code_sha,
        "runPurpose": "clean-integration-base-execution-compatibility",
        "canonicalDecisionEvidenceRunId": "36362386530",
        "mayReplaceCanonicalDecision": False,
        "measurementComplete": True,
        "measurementScope": "hosted-single-runner-legacy-only-postgresql16",
        "directlyComparableWithLocalEvidence": False,
        "comparisonBoundary": (
            "Hosted staircase evidence is environment-specific and must not be numerically "
            "merged with development-PC evidence."
        ),
        "semaphoreProductCodePresent": False,
        "promotionClaim": False,
        "s05StatusAfterRun": "in_progress",
        "freshDatabasePolicy": {
            "scope": "fresh unique disposable database for every wave; stronger than per-rung",
            "fingerprintCount": len(fingerprints),
            "allFingerprintsUnique": len(fingerprints) == len(waves),
            "residueAfterRun": owned_disposable_count(dsn),
        },
        "wavePlan": {
            "rungs": list(RUNGS),
            "wavesPerRung": WAVES_PER_RUNG,
            "order": "ascending; stop only after completing the first degraded rung",
            "mode": "legacy",
            "candidateExecuted": False,
            "semaphoreProductCodePresent": False,
        },
        "runner": runner_environment(),
        "postgresql": postgres_environment(dsn),
        "waves": waves,
        "rungs": rung_evaluations,
        "evaluation": {
            "decision": decision,
            "firstDegradeConcurrency": first_degrade,
            "higherRungsNotRun": [rung for rung in RUNGS if first_degrade and rung > first_degrade],
            "criterionOneUsesMaximumAcrossWaves": True,
            "criterionTwoUsesMedianAcrossWaves": True,
            "criteriaChangedAfterMeasurement": False,
            "semaphoreLineClosed": first_degrade is None,
        },
    }
    _require(summary["freshDatabasePolicy"]["residueAfterRun"] == 0, "database residue")
    summary_path = output_dir / "s05-legacy-staircase-summary.json"
    junit_path = output_dir / "s05-legacy-staircase-summary.xml"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_junit(junit_path, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
