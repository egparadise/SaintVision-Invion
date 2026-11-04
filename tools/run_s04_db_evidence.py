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
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.provenance import collect  # noqa: E402

CASE_FILE = ROOT / "tests" / "integration" / "s04_db_runner_case.py"
EXPECTED_CASES = {
    "http-run-idempotency-cancel",
    "approval-before-execution-and-expiry",
    "outbox-publisher-crash-retry",
    "outbox-consumer-rollback-dedup",
}
EXPECTED_TEST = "test_http_pg_expiry_cancel_idempotency_and_outbox_crash_retry"


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
    if not isinstance(report, dict):
        raise ValueError("S04 report must be an object")
    if type(report.get("schemaVersion")) is not int or report["schemaVersion"] != 1:
        raise ValueError("S04 report schemaVersion must be 1")
    if (
        report.get("taskId") != "S04-DB"
        or report.get("measurementScope") != "disposable-postgresql-http-kernel"
    ):
        raise ValueError("S04 report measurement scope does not match this runner")
    cases = report.get("cases")
    if not isinstance(cases, list):
        raise ValueError("S04 report cases must be a list")
    if len(cases) != len(EXPECTED_CASES) or any(
        not isinstance(item, dict) or not isinstance(item.get("id"), str) for item in cases
    ):
        raise ValueError("S04 report case inventory does not match the approved scope")
    if {item["id"] for item in cases} != EXPECTED_CASES:
        raise ValueError("S04 report case inventory does not match the approved scope")
    if any(item.get("status") != "PASS" for item in cases):
        raise ValueError("S04 measured cases must all pass")
    if report.get("physicalNodeDeliveryResumption") != "UNMEASURED":
        raise ValueError("physical Node delivery resumption must remain UNMEASURED")
    if report.get("operationalAcceptanceAssessed") is not False:
        raise ValueError("runner must not claim operational acceptance")
    if report.get("publicContractChanged") is not False:
        raise ValueError("runner must not claim a public contract change")
    if report.get("migrationChanged") is not False:
        raise ValueError("runner must not claim a migration change")
    serialized = json.dumps(report, sort_keys=True).lower()
    for forbidden in ("postgres://", "postgresql://", "password=", "inv_test_", "inv_app_"):
        if forbidden in serialized:
            raise ValueError("S04 report contains a database credential or disposable identifier")


def validate_junit(path: Path) -> None:
    """A zero pytest exit alone cannot substitute for execution of this exact case."""
    root = ET.parse(path).getroot()
    cases = list(root.iter("testcase"))
    if len(cases) != 1 or cases[0].get("name") != EXPECTED_TEST:
        raise ValueError("S04 JUnit must contain the one approved executable case")
    if any(list(case) for case in cases):
        raise ValueError("S04 JUnit case must not fail, error or skip")
    suites = list(root.iter("testsuite"))
    if len(suites) != 1 or int(suites[0].get("tests", "0")) != 1:
        raise ValueError("S04 JUnit summary does not match its executable case")
    if any(int(suites[0].get(key, "0")) != 0 for key in ("errors", "failures", "skipped")):
        raise ValueError("S04 JUnit summary records failures or skips")


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        json_out, junit_out = validated_paths(args)
    except ValueError as exc:
        parser().error(str(exc))

    # A failed rerun cannot leave old green evidence at the requested paths.
    json_out.unlink(missing_ok=True)
    junit_out.unlink(missing_ok=True)
    if not os.environ.get("INV_TEST_ADMIN_DSN"):
        print(json.dumps({"status": "BLOCKED", "physicalNodeDeliveryResumption": "UNMEASURED"}))
        print("INV_TEST_ADMIN_DSN is required for disposable PostgreSQL", file=sys.stderr)
        return 2

    json_out.parent.mkdir(parents=True, exist_ok=True)
    junit_out.parent.mkdir(parents=True, exist_ok=True)

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
    if completed.returncode != 0:
        json_out.unlink(missing_ok=True)
        print("S04 executable case did not complete successfully", file=sys.stderr)
        return completed.returncode
    if not json_out.is_file():
        print("S04 runner did not produce JSON evidence", file=sys.stderr)
        return completed.returncode or 2
    try:
        report = json.loads(json_out.read_text(encoding="utf-8"))
        validate_report(report)
        validate_junit(junit_out)
    except (OSError, ET.ParseError, ValueError) as exc:
        json_out.unlink(missing_ok=True)
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
