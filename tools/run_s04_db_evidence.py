#!/usr/bin/env python3
"""Run the S04 HTTP+PostgreSQL acceptance evidence case.

The measured case binds existing approval, cancellation, idempotency and
outbox invariants into one disposable-PostgreSQL report. It never claims the
physical Node delivery-resumption acceptance item, which remains UNMEASURED.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

from tools.provenance import collect

ROOT = Path(__file__).resolve().parents[1]
CASE_FILE = ROOT / "tests" / "integration" / "s04_db_runner_case.py"
EXPECTED_CASES = {
    "http-run-idempotency-cancel",
    "approval-before-execution-and-expiry",
    "outbox-publisher-crash-retry",
    "outbox-consumer-rollback-dedup",
}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--json-out", type=Path, required=True)
    result.add_argument("--junit-out", type=Path, required=True)
    return result


def validated_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    json_out = args.json_out.resolve()
    junit_out = args.junit_out.resolve()
    if json_out == junit_out:
        raise ValueError("JSON and JUnit outputs must be different files")
    return json_out, junit_out


def measurement_provenance() -> dict[str, Any]:
    captured = collect(executor=os.environ.get("INV_S04_EXECUTOR") or "Codex")
    return {
        "codeSha": captured["commit_sha"],
        "integrationSha": captured["integration_sha"],
        "integrationInSync": captured["in_sync"],
        "workingTreeClean": captured["working_tree_clean_status"],
        "contentClean": captured["content_clean_diff"],
        "capturedAtKst": captured["timestamp_kst"],
        "executor": captured["executor"],
    }


def validate_report(report: dict[str, Any]) -> None:
    if report.get("schemaVersion") != 1:
        raise ValueError("S04 report schemaVersion must be 1")
    cases = report.get("cases")
    if not isinstance(cases, list):
        raise ValueError("S04 report cases must be a list")
    case_ids = {item.get("id") for item in cases if isinstance(item, dict)}
    if case_ids != EXPECTED_CASES:
        raise ValueError("S04 report case inventory does not match the approved scope")
    if any(item.get("status") != "PASS" for item in cases):
        raise ValueError("S04 measured cases must all pass")
    if report.get("physicalNodeDeliveryResumption") != "UNMEASURED":
        raise ValueError("physical Node delivery resumption must remain UNMEASURED")
    if report.get("publicContractChanged") is not False:
        raise ValueError("runner must not claim a public contract change")
    if report.get("migrationChanged") is not False:
        raise ValueError("runner must not claim a migration change")
    serialized = json.dumps(report, sort_keys=True).lower()
    for forbidden in ("postgres://", "postgresql://", "password=", "inv_test_", "inv_app_"):
        if forbidden in serialized:
            raise ValueError("S04 report contains a database credential or disposable identifier")


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        json_out, junit_out = validated_paths(args)
    except ValueError as exc:
        parser().error(str(exc))

    if not os.environ.get("INV_TEST_ADMIN_DSN"):
        print("INV_TEST_ADMIN_DSN is required for disposable PostgreSQL", file=sys.stderr)
        return 2

    json_out.parent.mkdir(parents=True, exist_ok=True)
    junit_out.parent.mkdir(parents=True, exist_ok=True)
    # A failed rerun cannot leave old green evidence at the requested paths.
    json_out.unlink(missing_ok=True)
    junit_out.unlink(missing_ok=True)

    provenance = measurement_provenance()
    environment = os.environ.copy()
    environment["PYTHONUTF8"] = "1"
    environment["INV_S04_DB_EVIDENCE_JSON"] = str(json_out)
    environment["INV_S04_DB_PROVENANCE"] = json.dumps(provenance, separators=(",", ":"))
    python_paths = [str(ROOT / "src"), str(ROOT / "services" / "control-plane" / "src")]
    if environment.get("PYTHONPATH"):
        python_paths.append(environment["PYTHONPATH"])
    environment["PYTHONPATH"] = os.pathsep.join(python_paths)

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            str(CASE_FILE.relative_to(ROOT)),
            f"--junitxml={junit_out}",
        ],
        cwd=ROOT,
        env=environment,
        check=False,
    )
    if not json_out.is_file():
        print("S04 runner did not produce JSON evidence", file=sys.stderr)
        return completed.returncode or 2
    try:
        report = json.loads(json_out.read_text(encoding="utf-8"))
        validate_report(report)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"invalid S04 evidence: {exc}", file=sys.stderr)
        return completed.returncode or 2
    print(
        json.dumps(
            {
                "json": str(json_out),
                "junit": str(junit_out),
                "pytestExitCode": completed.returncode,
                "measuredCases": len(report["cases"]),
                "physicalNodeDeliveryResumption": report["physicalNodeDeliveryResumption"],
            },
            separators=(",", ":"),
        )
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
