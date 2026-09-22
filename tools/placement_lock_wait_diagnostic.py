"""Run and classify the approved S05 PostgreSQL lock-wait confirmation waves."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

import psycopg
from psycopg.conninfo import conninfo_to_dict

ROOT = Path(__file__).resolve().parents[1]


def _local_test_server(admin_dsn: str, container: str) -> None:
    info = conninfo_to_dict(admin_dsn)
    if info.get("host") not in {"127.0.0.1", "localhost"}:
        raise SystemExit("diagnostic refuses a non-local PostgreSQL host")
    with psycopg.connect(admin_dsn) as conn:
        if not conn.execute(
            "SELECT current_setting('server_version_num')::int BETWEEN 160000 AND 169999"
        ).fetchone()[0]:
            raise SystemExit("diagnostic requires PostgreSQL 16")
    inspected = subprocess.run(
        ["docker", "inspect", "--format", "{{.State.Running}}", container],
        capture_output=True,
        text=True,
        timeout=15,
    )
    if inspected.returncode or inspected.stdout.strip().lower() != "true":
        raise SystemExit("diagnostic PostgreSQL container is not running")
    published = subprocess.run(
        ["docker", "port", container, "5432/tcp"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    expected_port = str(info.get("port", "5432"))
    if published.returncode or not any(
        line.rsplit(":", 1)[-1].strip() == expected_port
        for line in published.stdout.splitlines()
    ):
        raise SystemExit("admin DSN port does not match the approved PostgreSQL container")


def _owned_disposables(admin_dsn: str) -> tuple[frozenset[str], frozenset[str]]:
    with psycopg.connect(admin_dsn) as conn:
        databases = frozenset(
            row[0]
            for row in conn.execute(
                "SELECT datname FROM pg_database WHERE datname LIKE 'inv_test_%'"
            ).fetchall()
        )
        roles = frozenset(
            row[0]
            for row in conn.execute(
                "SELECT rolname FROM pg_roles WHERE rolname LIKE 'inv_app_%'"
            ).fetchall()
        )
    return databases, roles


def _run_phase(args: argparse.Namespace) -> int:
    if not os.getenv("INV_TEST_ADMIN_DSN"):
        raise SystemExit("INV_TEST_ADMIN_DSN is required")
    _local_test_server(os.environ["INV_TEST_ADMIN_DSN"], args.container)
    before = _owned_disposables(os.environ["INV_TEST_ADMIN_DSN"])
    code_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    env = {
        **os.environ,
        "INV_S05_LOCK_WAIT_DIAGNOSTIC": "1",
        "INV_S05_LOCK_WAIT_PHASE": args.phase,
        "INV_S05_PG_CONTAINER": args.container,
        "INV_S05_LOCK_WAIT_REPORT": str(args.report.resolve()),
        "INV_S05_CODE_SHA": code_sha,
        "INV_PLACEMENT_BENCHMARK_REQUESTS": "20",
        "INV_PLACEMENT_BENCHMARK_CONCURRENCY": "20",
        "INV_PLACEMENT_BENCHMARK_ROUNDS": "1",
        "INV_PLACEMENT_SHORT_COMMIT": "0",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.junit.parent.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "tests/integration/test_placement_lock_wait_diagnostic.py",
        "-o",
        "junit_family=xunit1",
        "--junitxml",
        str(args.junit.resolve()),
    ]
    completed = subprocess.run(command, cwd=ROOT, env=env, timeout=args.timeout)
    after = _owned_disposables(os.environ["INV_TEST_ADMIN_DSN"])
    leaked_databases = after[0] - before[0]
    leaked_roles = after[1] - before[1]
    if leaked_databases or leaked_roles:
        print("diagnostic disposable cleanup failed", file=sys.stderr)
        return 4
    return completed.returncode


def classify(legacy: dict, control: dict) -> tuple[str, list[str]]:
    reasons = []
    legacy_queue = legacy["queueObservation"]
    legacy_log = legacy["serverLockWaits"]
    control_queue = control["queueObservation"]
    control_log = control["serverLockWaits"]
    baseline_signature = (
        any(
            mode in {"Key Share", "For Key Share"}
            for mode in legacy_queue["pgrowlocksModes"]
        )
        and "For No Key Update" in legacy_queue["pgrowlocksModes"]
        and legacy_log["transactionSegmentCount"] > 0
        and legacy_log["tupleSegmentCount"] == 0
        and int(legacy["errorsBySqlstate"].get("55P03", 0)) == 0
    )
    control_signature = (
        control_log["tupleSegmentCount"] > 0
        and control_queue["maxBlockingChainDepth"] >= 2
        and int(control["errorsBySqlstate"].get("55P03", 0)) > 0
        and any(
            450 <= event["reportedWaitMs"] <= 650
            for event in control_log["events"]
        )
    )
    contradicted = (
        control_queue["maxBlockingChainDepth"] <= 1
        and control_log["tupleSegmentCount"] == 0
        and int(control["errorsBySqlstate"].get("55P03", 0)) == 0
    )
    reasons.append(f"legacySignature={baseline_signature}")
    reasons.append(f"fkDroppedControlSignature={control_signature}")
    reasons.append(f"fkDroppedDepth={control_queue['maxBlockingChainDepth']}")
    reasons.append(
        f"fkDropped55P03={int(control['errorsBySqlstate'].get('55P03', 0))}"
    )
    if baseline_signature and control_signature:
        return "HYPOTHESIS_SUPPORTED", reasons
    if baseline_signature and contradicted:
        return "HYPOTHESIS_CONTRADICTED", reasons
    return "NOT_OBSERVED", reasons


def _write_junit(path: Path, result: dict) -> None:
    suite = ET.Element(
        "testsuite",
        name="s05-lock-wait-diagnostic",
        tests="1",
        failures="0",
        errors="0",
        skipped="0",
        time="0",
    )
    case = ET.SubElement(
        suite,
        "testcase",
        classname="tools.placement_lock_wait_diagnostic",
        name="legacy_fk_causality_is_observed",
        time="0",
    )
    props = ET.SubElement(case, "properties")
    ET.SubElement(props, "property", name="verdict", value=result["verdict"])
    ET.SubElement(props, "property", name="requestCountPerWave", value="20")
    ET.SubElement(props, "property", name="waveCount", value="2")
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(suite).write(path, encoding="utf-8", xml_declaration=True)


def _combine(args: argparse.Namespace) -> int:
    legacy = json.loads(args.legacy_report.read_text(encoding="utf-8"))
    control = json.loads(args.control_report.read_text(encoding="utf-8"))
    if legacy.get("phase") != "legacy" or control.get("phase") != "fk-dropped":
        raise SystemExit("reports do not form a legacy/fk-dropped pair")
    if legacy.get("codeSha") != control.get("codeSha"):
        raise SystemExit("reports use different code SHAs")
    verdict, reasons = classify(legacy, control)
    result = {
        "schemaVersion": "1.0.0",
        "verdict": verdict,
        "codeSha": legacy["codeSha"],
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "scope": "development-PC; two disposable PostgreSQL databases; 20x1 each",
        "policyDecisionIndependent": True,
        "policyOrder": [
            "B-prime: candidate limits lock_timeout budget 500ms to about 1500ms",
            "B: project-scoped bounded semaphore fail-fast cap",
        ],
        "optionA": "mechanism-only; not a product policy candidate",
        "reasons": reasons,
        "legacy": legacy,
        "fkDroppedControl": control,
        "ac05": "NOT_EVALUATED",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    _write_junit(args.junit, result)
    print(json.dumps({"verdict": verdict, "report": str(args.report)}, sort_keys=True))
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--phase", choices=("legacy", "fk-dropped"), required=True)
    run.add_argument("--container", required=True)
    run.add_argument("--report", type=Path, required=True)
    run.add_argument("--junit", type=Path, required=True)
    run.add_argument("--timeout", type=int, default=300)
    combine = sub.add_parser("combine")
    combine.add_argument("--legacy-report", type=Path, required=True)
    combine.add_argument("--control-report", type=Path, required=True)
    combine.add_argument("--report", type=Path, required=True)
    combine.add_argument("--junit", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return _run_phase(args) if args.command == "run" else _combine(args)


if __name__ == "__main__":
    raise SystemExit(main())
