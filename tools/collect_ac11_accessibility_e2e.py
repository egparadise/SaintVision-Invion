"""Collect fail-closed AC-11 accessibility/E2E evidence from hosted browser runs.

This producer binds two existing real-browser reports to one clean source tree.  It
does not claim user acceptance: until a separately reviewed same-SHA manual
keyboard/screen-reader importer exists, the completeness metric remains failed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "1.1.0"
RUN_PURPOSE = "s11-ac11-accessibility-e2e-hosted"
AXIS = "accessibility-e2e"
TARGET_COMMIT = "4b6d4fab2925bb422f1deb6db2794fac0ccaa54f"
TARGET_PATH = "docs/vault/30_Development/S11_AC11_accessibility_e2e_hosted_target_v0.md"
TARGET_BLOB = "30bc37df03e1568f4af126843ab1fefb71b23de0"
SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
RUN_ID_RE = re.compile(r"^[0-9]+$")
EXPECTED_JOURNEYS = {
    "test_actual_browser_quorum_snapshot_and_no_duplicate_vote",
    "test_actual_browser_stale_run_and_revoked_review_are_rejected",
    "test_browser_real_catalogue_owner_scope_and_revocation",
    "test_browser_real_committed_model_and_current_permission",
    "test_full_studio_login_project_approval_and_logout",
}
EXPECTED_JOURNEY_MULTIPLICITY = {
    journey: (2 if journey == "test_full_studio_login_project_approval_and_logout" else 1)
    for journey in EXPECTED_JOURNEYS
}
EXPECTED_INVARIANTS = {f"inv{number:02d}" for number in range(1, 10)}
EXPECTED_CONTRAST = {
    "Top System Menu Bar Text",
    "Window Active Title Text",
    "Window Inactive Title Text",
}
CRITERIA = {
    "canonicalJourneyFailureCount": {"operator": "eq", "value": 0},
    "desktopInvariantFailureCount": {"operator": "eq", "value": 0},
    "contrastFailureCount": {"operator": "eq", "value": 0},
    "keyboardFailureCount": {"operator": "eq", "value": 0},
    "manualAcceptanceMissingCount": {"operator": "eq", "value": 0},
}


class AccessibilityEvidenceError(RuntimeError):
    """A redacted producer validation error."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, text=True, capture_output=True, encoding="utf-8"
    )
    if result.returncode:
        raise AccessibilityEvidenceError(f"git {args[0]} failed")
    return result.stdout.strip()


def validate_checkout(source_head_sha: str) -> tuple[str, bool]:
    if not SHA1_RE.fullmatch(source_head_sha):
        raise AccessibilityEvidenceError("source head must be a full lowercase Git SHA")
    if _git("rev-parse", "HEAD") != source_head_sha:
        raise AccessibilityEvidenceError("checkout is not the declared source head")
    tree = _git("rev-parse", "HEAD^{tree}")
    if not SHA1_RE.fullmatch(tree):
        raise AccessibilityEvidenceError("checkout tree is not a full Git object ID")
    if _git("status", "--porcelain"):
        raise AccessibilityEvidenceError("checkout is dirty before accessibility evidence generation")
    if _git("rev-parse", f"{TARGET_COMMIT}:{TARGET_PATH}") != TARGET_BLOB:
        raise AccessibilityEvidenceError("pre-registered target blob is unavailable")
    if _git("rev-parse", f"HEAD:{TARGET_PATH}") != TARGET_BLOB:
        raise AccessibilityEvidenceError("source tree changed the pre-registered target")
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", TARGET_COMMIT, source_head_sha],
        cwd=ROOT,
        capture_output=True,
    )
    if ancestor.returncode != 0:
        raise AccessibilityEvidenceError("pre-registered target is not an ancestor of source head")
    return tree, True


def _load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AccessibilityEvidenceError(f"{label} is unreadable: {type(exc).__name__}") from None
    if not isinstance(value, dict):
        raise AccessibilityEvidenceError(f"{label} must be a JSON object")
    return value


def _utc(value: str, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise AccessibilityEvidenceError(f"{label} must be RFC3339") from exc
    if parsed.tzinfo is None:
        raise AccessibilityEvidenceError(f"{label} must include a timezone")
    return parsed


def _junit_cases(path: Path) -> list[dict[str, str]]:
    try:
        root = ET.fromstring(path.read_bytes())
    except (OSError, ET.ParseError) as exc:
        raise AccessibilityEvidenceError(
            f"browser JUnit is unreadable: {type(exc).__name__}"
        ) from None
    if root.tag not in {"testsuite", "testsuites"}:
        raise AccessibilityEvidenceError("browser JUnit root is unsupported")
    result: list[dict[str, str]] = []
    for case in root.findall(".//testcase"):
        classname = case.get("classname")
        name = case.get("name")
        if not isinstance(classname, str) or not isinstance(name, str):
            raise AccessibilityEvidenceError("browser JUnit case identity is malformed")
        statuses = [tag for tag in ("failure", "error", "skipped") if case.find(tag) is not None]
        if len(statuses) > 1:
            raise AccessibilityEvidenceError("browser JUnit case has multiple outcomes")
        result.append({"classname": classname, "name": name, "outcome": statuses[0] if statuses else "passed"})
    if not result:
        raise AccessibilityEvidenceError("browser JUnit has no cases")
    return result


def _journey_result(
    proof: dict[str, Any], identities: Any, browser_junit_path: Path, case_identities_path: Path
) -> tuple[int, list[str], int]:
    if not isinstance(identities, list) or not identities:
        raise AccessibilityEvidenceError("browser case identities are empty or malformed")
    journeys: list[str] = []
    for row in identities:
        if not isinstance(row, dict) or set(row) != {"classname", "name"}:
            raise AccessibilityEvidenceError("browser case identity shape is unsupported")
        name = row["name"]
        if not isinstance(name, str):
            raise AccessibilityEvidenceError("browser case name is not a string")
        journeys.append(re.sub(r"\[.*\]$", "", name))
    multiplicity = {journey: journeys.count(journey) for journey in set(journeys)}
    if multiplicity != EXPECTED_JOURNEY_MULTIPLICITY:
        raise AccessibilityEvidenceError("canonical browser journey identity set drifted")
    if proof.get("caseIdentitiesSha256") != file_sha256(case_identities_path):
        raise AccessibilityEvidenceError("browser case identity digest drifted")
    if proof.get("xmlSha256") != file_sha256(browser_junit_path):
        raise AccessibilityEvidenceError("browser JUnit digest drifted")
    junit_cases = _junit_cases(browser_junit_path)
    junit_identities = [
        {"classname": case["classname"], "name": case["name"]} for case in junit_cases
    ]
    if junit_identities != identities:
        raise AccessibilityEvidenceError("browser JUnit identities differ from private identities")
    tests = proof.get("tests")
    if not isinstance(tests, dict) or set(tests) != {"failure", "error", "skipped", "passed"}:
        raise AccessibilityEvidenceError("browser proof test counts are malformed")
    if any(isinstance(tests[key], bool) or not isinstance(tests[key], int) or tests[key] < 0 for key in tests):
        raise AccessibilityEvidenceError("browser proof test counts are invalid")
    recomputed_counts = {
        outcome: sum(case["outcome"] == outcome for case in junit_cases)
        for outcome in ("failure", "error", "skipped", "passed")
    }
    if tests != recomputed_counts:
        raise AccessibilityEvidenceError("browser proof counts differ from JUnit")
    physical_failures = tests["failure"] + tests["error"] + tests["skipped"]
    if tests["passed"] + physical_failures != len(journeys):
        raise AccessibilityEvidenceError("browser proof counts differ from case identities")
    if proof.get("browserOptIn") is not True or proof.get("isolatedContainerRemoved") is not True:
        raise AccessibilityEvidenceError("browser proof isolation is incomplete")
    pytest_failures = tests["failure"] + tests["error"]
    expected_exit = 0 if pytest_failures == 0 else 1
    expected_status = "complete" if pytest_failures == 0 else "partial"
    if (
        proof.get("exitCode") != expected_exit
        or proof.get("subprocessExitCode") != expected_exit
        or proof.get("evidenceStatus") != expected_status
    ):
        raise AccessibilityEvidenceError("browser proof outcome differs from recomputed failures")
    failed_journeys = {
        re.sub(r"\[.*\]$", "", case["name"])
        for case in junit_cases
        if case["outcome"] != "passed"
    }
    return len(failed_journeys), sorted(EXPECTED_JOURNEYS), len(junit_cases)


def _invariant_result(report: dict[str, Any], source_head_sha: str) -> tuple[int, int, int, list[str]]:
    if report.get("gitCommitSha") != source_head_sha or report.get("verified") is not True:
        raise AccessibilityEvidenceError("desktop invariant report is not bound to source head")
    summary = report.get("summary")
    invariants = report.get("invariants")
    accessibility = report.get("accessibility")
    if not isinstance(summary, dict) or not isinstance(invariants, dict) or not isinstance(accessibility, dict):
        raise AccessibilityEvidenceError("desktop invariant report shape is unsupported")
    rows = {key: value for key, value in invariants.items() if re.fullmatch(r"inv\d{2}_.+", key)}
    identities = {key.split("_", 1)[0] for key in rows}
    if identities != EXPECTED_INVARIANTS or len(rows) != 9:
        raise AccessibilityEvidenceError("desktop invariant identity set drifted")
    statuses: list[bool] = []
    for key in sorted(rows):
        row = rows[key]
        if not isinstance(row, dict) or row.get("pass") not in (True, False, "PARTIAL"):
            raise AccessibilityEvidenceError("desktop invariant status is malformed")
        statuses.append(row["pass"] is True)
    invariant_failures = sum(not passed for passed in statuses)
    if (
        summary.get("totalChecks") != 9
        or summary.get("passedChecks") != 9 - invariant_failures
        or summary.get("partialChecks") != sum(row.get("pass") == "PARTIAL" for row in rows.values())
        or summary.get("failedChecks") != sum(row.get("pass") is False for row in rows.values())
    ):
        raise AccessibilityEvidenceError("desktop invariant summary differs from recomputed rows")
    contrast = accessibility.get("contrastChecks")
    if not isinstance(contrast, list) or len(contrast) != 3:
        raise AccessibilityEvidenceError("contrast check set is incomplete")
    elements = {row.get("element") for row in contrast if isinstance(row, dict)}
    if elements != EXPECTED_CONTRAST:
        raise AccessibilityEvidenceError("contrast check identity set drifted")
    contrast_failures = 0
    for row in contrast:
        ratio = row.get("numericalRatio")
        if isinstance(ratio, bool) or not isinstance(ratio, (int, float)):
            raise AccessibilityEvidenceError("contrast ratio is not numeric")
        recomputed_pass = float(ratio) >= 4.5
        if row.get("pass") is not recomputed_pass:
            raise AccessibilityEvidenceError("contrast pass flag differs from ratio")
        contrast_failures += not recomputed_pass
    inv05 = next(value for key, value in rows.items() if key.startswith("inv05_"))
    inv06 = next(value for key, value in rows.items() if key.startswith("inv06_"))
    keyboard_checks = [
        inv05.get("pass") is True,
        inv06.get("modalDismissed") is True and inv06.get("triggerFocusRestored") is True,
    ]
    keyboard_failures = sum(not passed for passed in keyboard_checks)
    if accessibility.get("keyboardNavigationPass") is not all(keyboard_checks):
        raise AccessibilityEvidenceError("keyboard navigation summary differs from measured checks")
    return invariant_failures, contrast_failures, keyboard_failures, sorted(rows)


def _observation(metric: str, n: int, failures: int, error: str) -> dict[str, Any]:
    return {
        "metric": metric,
        "n": n,
        "successCount": n - failures,
        "failureCount": failures,
        "skipCount": 0,
        "value": failures,
        "errorsByClass": {error: failures} if failures else {},
    }


def build_report(
    *,
    source_run_id: str,
    source_head_sha: str,
    runner_image: str,
    browser_version: str,
    browser_proof_path: Path,
    case_identities_path: Path,
    browser_junit_path: Path,
    invariant_path: Path,
    started_at: str,
) -> dict[str, Any]:
    if not RUN_ID_RE.fullmatch(source_run_id):
        raise AccessibilityEvidenceError("source run ID must be numeric")
    if not runner_image.strip() or not browser_version.strip():
        raise AccessibilityEvidenceError("runner image and browser version are required")
    started = _utc(started_at, "startedAt")
    if started > datetime.now(timezone.utc):
        raise AccessibilityEvidenceError("startedAt is in the future")
    tree, clean = validate_checkout(source_head_sha)
    proof = _load_object(browser_proof_path, "browser proof")
    identities = json.loads(case_identities_path.read_text(encoding="utf-8"))
    invariants = _load_object(invariant_path, "desktop invariant report")
    if invariants.get("browser") != browser_version:
        raise AccessibilityEvidenceError("declared browser version differs from invariant report")
    if invariants.get("frontendTransport") != "vite-dev-server-with-browser-node-fixture":
        raise AccessibilityEvidenceError("desktop invariant frontend transport is unsupported")
    journey_failures, journey_ids, physical_case_count = _journey_result(
        proof, identities, browser_junit_path, case_identities_path
    )
    invariant_failures, contrast_failures, keyboard_failures, invariant_ids = _invariant_result(
        invariants, source_head_sha
    )
    observations = [
        _observation("canonicalJourneyFailureCount", 5, journey_failures, "browser-journey-failed"),
        _observation("desktopInvariantFailureCount", 9, invariant_failures, "desktop-invariant-failed"),
        _observation("contrastFailureCount", 3, contrast_failures, "wcag-aa-contrast-failed"),
        _observation("keyboardFailureCount", 2, keyboard_failures, "keyboard-or-focus-failed"),
        _observation("manualAcceptanceMissingCount", 1, 1, "manual-acceptance-not-supplied"),
    ]
    failed = any(row["failureCount"] for row in observations)
    payload = {
        "journeyIds": journey_ids,
        "browserPhysicalCaseCount": physical_case_count,
        "invariantIds": invariant_ids,
        "inputDigests": {
            "browserProofSha256": file_sha256(browser_proof_path),
            "caseIdentitiesSha256": file_sha256(case_identities_path),
            "browserJunitSha256": file_sha256(browser_junit_path),
            "desktopInvariantSha256": file_sha256(invariant_path),
        },
        "observations": observations,
    }
    return {
        "schemaVersion": SCHEMA_VERSION,
        "runPurpose": RUN_PURPOSE,
        "axis": AXIS,
        "sourceRunId": source_run_id,
        "sourceHeadSha": source_head_sha,
        "checkoutTreeSha": tree,
        "cleanCheckout": clean,
        "startedAt": started_at,
        "finishedAt": utc_now(),
        "environment": {
            "topology": "github-hosted-single-runner",
            "runnerImage": runner_image,
            "browser": browser_version,
            "frontendTransport": invariants.get("frontendTransport"),
            "credentialsRequired": False,
            "physicalFiveNodeComparable": False,
        },
        "targetRef": {
            "commit": TARGET_COMMIT,
            "path": TARGET_PATH,
            "blob": TARGET_BLOB,
            "criteria": CRITERIA,
        },
        "verdict": "MEASURED_FAIL" if failed else "MEASURED_PASS",
        "acceptanceClaim": False,
        "artifactSha256": None,
        "artifactStatus": "PENDING_UPLOAD",
        "artifactUnit": "github-actions-uploaded-zip",
        "cleanup": {
            "isolatedBrowserContainerRemoved": True,
            "producerTempResidueCount": None,
        },
        "limitation": "hosted automatic measurement; same-SHA user-device keyboard/screen-reader acceptance absent",
        "payload": payload,
        "payloadSha256": canonical_sha256(payload),
    }


def write_junit(report: dict[str, Any], path: Path) -> None:
    observations = report["payload"]["observations"]
    suite = ET.Element(
        "testsuite",
        name="ac11-accessibility-e2e",
        tests=str(len(observations)),
        failures=str(sum(row["failureCount"] > 0 for row in observations)),
        errors="0",
        skipped="0",
    )
    for row in observations:
        case = ET.SubElement(suite, "testcase", name=row["metric"], classname="ac11.accessibility")
        if row["failureCount"]:
            failure = ET.SubElement(case, "failure", message=next(iter(row["errorsByClass"])))
            failure.text = "pre-registered accessibility criterion not met"
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(suite).write(path, encoding="utf-8", xml_declaration=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-run-id", required=True)
    parser.add_argument("--source-head-sha", required=True)
    parser.add_argument("--runner-image", required=True)
    parser.add_argument("--browser-version", required=True)
    parser.add_argument("--browser-proof", type=Path, required=True)
    parser.add_argument("--case-identities", type=Path, required=True)
    parser.add_argument("--browser-junit", type=Path, required=True)
    parser.add_argument("--desktop-invariants", type=Path, required=True)
    parser.add_argument("--started-at", required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--junit", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = build_report(
            source_run_id=args.source_run_id,
            source_head_sha=args.source_head_sha,
            runner_image=args.runner_image,
            browser_version=args.browser_version,
            browser_proof_path=args.browser_proof,
            case_identities_path=args.case_identities,
            browser_junit_path=args.browser_junit,
            invariant_path=args.desktop_invariants,
            started_at=args.started_at,
        )
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        write_junit(report, args.junit)
    except (AccessibilityEvidenceError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"accessibility evidence unavailable: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"verdict": report["verdict"], "report": str(args.report)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
