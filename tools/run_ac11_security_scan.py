"""Normalize hosted dependency/SAST scanners into redacted AC-11 evidence.

The opt-in workflow runs pinned ``pip-audit`` and ``bandit`` binaries.  This
producer does not trust their prose, does not serialize source snippets or
dependency descriptions, and never turns a missing scanner result into a
zero-finding report.  It records only stable finding identities and Git
objects for the pre-registered scan scope.
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
DEFAULT_ALLOWLIST = (
    ROOT
    / "docs"
    / "vault"
    / "30_Development"
    / "Evidence"
    / "s11-security-dependency-sast-allowlist-v1.json"
)
SCHEMA_VERSION = "1.0.0"
RUN_PURPOSE = "s11-ac11-security-scan"
THREAT_ID = "SEC-SCAN-001"
SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
RUN_ID_RE = re.compile(r"^[0-9]+$")
ALLOWED_SEVERITIES = {"CRITICAL", "HIGH"}
SCANNER_IDS = {"bandit", "pip-audit"}
PIN_RE = re.compile(r"^([A-Za-z0-9_.-]+)(?:\[[^\]]+\])?==([^\s;]+)$")


class SecurityScanError(RuntimeError):
    """A redacted, fail-closed producer validation error."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, text=True, capture_output=True, encoding="utf-8"
    )
    if result.returncode:
        raise SecurityScanError(f"git {args[0]} failed")
    return result.stdout.strip()


def validate_checkout(source_head_sha: str) -> tuple[str, bool]:
    if not SHA1_RE.fullmatch(source_head_sha):
        raise SecurityScanError("source head must be a full lowercase Git SHA")
    if _git("rev-parse", "HEAD") != source_head_sha:
        raise SecurityScanError("checkout is not the declared source head")
    tree = _git("rev-parse", "HEAD^{tree}")
    clean = _git("status", "--porcelain") == ""
    if not clean:
        raise SecurityScanError("checkout is dirty before security evidence generation")
    return tree, clean


def _utc(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise SecurityScanError(f"{field} must be an RFC3339 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SecurityScanError(f"{field} is not RFC3339") from exc
    if parsed.tzinfo is None:
        raise SecurityScanError(f"{field} must include a timezone")
    return parsed


def load_allowlist(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SecurityScanError(f"scan allowlist unreadable: {type(exc).__name__}") from None
    expected = {
        "schemaVersion",
        "verifiedAt",
        "producer",
        "workflow",
        "importer",
        "scanners",
        "acceptedFindings",
    }
    if not isinstance(value, dict) or set(value) != expected:
        raise SecurityScanError("scan allowlist top-level shape is not reviewed")
    if value["schemaVersion"] != SCHEMA_VERSION:
        raise SecurityScanError("scan allowlist schemaVersion is unsupported")
    _utc(value["verifiedAt"], "verifiedAt")
    for field in ("producer", "workflow", "importer"):
        row = value[field]
        if (
            not isinstance(row, dict)
            or set(row) != {"path", "blob"}
            or not isinstance(row["path"], str)
            or not SHA1_RE.fullmatch(str(row["blob"]))
        ):
            raise SecurityScanError(f"scan allowlist {field} provenance is malformed")
    scanners = value["scanners"]
    if not isinstance(scanners, list) or len(scanners) != 2:
        raise SecurityScanError("scan allowlist must register exactly two scanners")
    seen: set[str] = set()
    for scanner in scanners:
        if not isinstance(scanner, dict) or set(scanner) != {
            "id",
            "version",
            "scopePaths",
            "severityPolicy",
        }:
            raise SecurityScanError("scanner registration shape is malformed")
        scanner_id = scanner["id"]
        if scanner_id not in SCANNER_IDS or scanner_id in seen:
            raise SecurityScanError("scanner ID is unknown or duplicated")
        seen.add(scanner_id)
        if not isinstance(scanner["version"], str) or not scanner["version"]:
            raise SecurityScanError("scanner version is empty")
        scope = scanner["scopePaths"]
        if (
            not isinstance(scope, list)
            or not scope
            or len(scope) != len(set(scope))
            or any(not isinstance(item, str) or not item for item in scope)
        ):
            raise SecurityScanError("scanner scope is empty or duplicated")
        expected_policy = (
            "HIGH_ONLY" if scanner_id == "bandit" else "ANY_VULNERABILITY_AS_HIGH"
        )
        if scanner["severityPolicy"] != expected_policy:
            raise SecurityScanError("scanner severity policy is not fail-closed")
    entries = value["acceptedFindings"]
    if not isinstance(entries, list):
        raise SecurityScanError("acceptedFindings must be a list")
    identities: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {
            "findingId",
            "severity",
            "reason",
            "expiresAt",
        }:
            raise SecurityScanError("accepted finding shape is malformed")
        finding_id = entry["findingId"]
        if not isinstance(finding_id, str) or not finding_id or finding_id in identities:
            raise SecurityScanError("accepted finding ID is empty or duplicated")
        identities.add(finding_id)
        if entry["severity"] not in ALLOWED_SEVERITIES:
            raise SecurityScanError("accepted finding severity is unsupported")
        if not isinstance(entry["reason"], str) or not entry["reason"].strip():
            raise SecurityScanError("accepted finding reason is required")
        _utc(entry["expiresAt"], "accepted finding expiresAt")
    return value


def _canonical_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _required_pins(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise SecurityScanError(
            f"registered requirements unreadable: {type(exc).__name__}"
        ) from None
    pins: dict[str, str] = {}
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = PIN_RE.fullmatch(line)
        if match is None:
            raise SecurityScanError("registered requirements contain a non-exact pin")
        name, version = _canonical_name(match.group(1)), match.group(2)
        if name in pins:
            raise SecurityScanError("registered requirements contain a duplicate package")
        pins[name] = version
    if not pins:
        raise SecurityScanError("registered requirements contain no exact pins")
    return pins


def parse_pip_audit(
    value: Any, required_pins: dict[str, str]
) -> tuple[list[dict[str, Any]], dict[str, int], list[dict[str, str]]]:
    if not isinstance(value, dict) or not isinstance(value.get("dependencies"), list):
        raise SecurityScanError("pip-audit JSON shape is unsupported")
    findings: list[dict[str, Any]] = []
    dependencies: dict[str, str] = {}
    for dependency in value["dependencies"]:
        if not isinstance(dependency, dict):
            raise SecurityScanError("pip-audit dependency row is malformed")
        if dependency.get("skip_reason") is not None:
            raise SecurityScanError("pip-audit skipped a registered dependency")
        name, version, vulns = dependency.get("name"), dependency.get("version"), dependency.get("vulns")
        if not isinstance(name, str) or not isinstance(version, str) or not isinstance(vulns, list):
            raise SecurityScanError("pip-audit dependency identity is malformed")
        package = _canonical_name(name)
        if not package or not version or package in dependencies:
            raise SecurityScanError("pip-audit dependency identity is empty or duplicated")
        dependencies[package] = version
        for vuln in vulns:
            if not isinstance(vuln, dict) or not isinstance(vuln.get("id"), str):
                raise SecurityScanError("pip-audit vulnerability identity is malformed")
            vuln_id = vuln["id"].strip()
            if not vuln_id:
                raise SecurityScanError("pip-audit vulnerability ID is empty")
            findings.append(
                {
                    "findingId": f"pip-audit:{package}:{version}:{vuln_id}",
                    "scanner": "pip-audit",
                    "severity": "HIGH",
                    "ruleId": vuln_id,
                    "component": package,
                    "location": version,
                }
            )
    if not dependencies:
        raise SecurityScanError("pip-audit returned no dependencies")
    missing = sorted(
        name for name, version in required_pins.items() if dependencies.get(name) != version
    )
    if missing:
        raise SecurityScanError("pip-audit omitted or changed a registered direct pin")
    audited = [
        {"name": name, "version": dependencies[name]} for name in sorted(dependencies)
    ]
    return findings, {"dependencyCount": len(audited), "findingCount": len(findings)}, audited


def _relative_repo_path(value: str) -> str:
    candidate = Path(value)
    if candidate.is_absolute():
        try:
            candidate = candidate.resolve().relative_to(ROOT.resolve())
        except ValueError as exc:
            raise SecurityScanError("bandit path is outside the source checkout") from exc
    normalized = candidate.as_posix().lstrip("./")
    if not normalized or normalized.startswith("../"):
        raise SecurityScanError("bandit path is outside the registered scope")
    return normalized


def parse_bandit(
    value: Any, scope_paths: list[str], expected_files: list[str] | None = None
) -> tuple[list[dict[str, Any]], dict[str, int], list[str]]:
    if (
        not isinstance(value, dict)
        or not isinstance(value.get("results"), list)
        or not isinstance(value.get("errors"), list)
        or not isinstance(value.get("metrics"), dict)
    ):
        raise SecurityScanError("bandit JSON shape is unsupported")
    if value["errors"]:
        raise SecurityScanError("bandit did not parse every registered source file")
    scanned_files: list[str] = []
    for raw_path in value["metrics"]:
        if raw_path == "_totals":
            continue
        path = _relative_repo_path(str(raw_path))
        if not path.endswith(".py") or not any(
            path == scope or path.startswith(scope.rstrip("/") + "/")
            for scope in scope_paths
        ):
            raise SecurityScanError("bandit metrics contain an out-of-scope file")
        scanned_files.append(path)
    scanned_files.sort()
    if not scanned_files or len(scanned_files) != len(set(scanned_files)):
        raise SecurityScanError("bandit scanned-file inventory is empty or duplicated")
    if expected_files is not None and scanned_files != expected_files:
        raise SecurityScanError("bandit scanned-file inventory differs from the source tree")
    counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
    findings: list[dict[str, Any]] = []
    for finding in value["results"]:
        if not isinstance(finding, dict):
            raise SecurityScanError("bandit result row is malformed")
        severity = finding.get("issue_severity")
        if severity not in counts:
            raise SecurityScanError("bandit severity is unsupported")
        counts[severity] += 1
        if severity != "HIGH":
            continue
        path = _relative_repo_path(str(finding.get("filename", "")))
        if not any(path == scope or path.startswith(scope.rstrip("/") + "/") for scope in scope_paths):
            raise SecurityScanError("bandit result is outside the registered scope")
        test_id = finding.get("test_id")
        line = finding.get("line_number")
        if not isinstance(test_id, str) or not test_id or isinstance(line, bool) or not isinstance(line, int) or line < 1:
            raise SecurityScanError("bandit finding identity is malformed")
        findings.append(
            {
                "findingId": f"bandit:{test_id}:{path}:{line}",
                "scanner": "bandit",
                "severity": "HIGH",
                "ruleId": test_id,
                "component": path,
                "location": str(line),
            }
        )
    return findings, {
        "lowFindingCount": counts["LOW"],
        "mediumFindingCount": counts["MEDIUM"],
        "highFindingCount": counts["HIGH"],
        "scannedFileCount": len(scanned_files),
    }, scanned_files


def _read_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SecurityScanError(f"{label} report unreadable: {type(exc).__name__}") from None


def _junit(report: dict[str, Any]) -> bytes:
    passed = report["verdict"] == "MEASURED_PASS"
    suite = ET.Element(
        "testsuite",
        name="s11-ac11-security-scan",
        tests="4",
        failures="0" if passed else "1",
        errors="0",
        skipped="0",
    )
    ET.SubElement(suite, "testcase", classname="ac11.security", name="provenance")
    ET.SubElement(suite, "testcase", classname="ac11.security", name="pip-audit")
    ET.SubElement(suite, "testcase", classname="ac11.security", name="bandit")
    gate = ET.SubElement(suite, "testcase", classname="ac11.security", name="critical-high-gate")
    if not passed:
        ET.SubElement(gate, "failure", message=report["failureClass"])
    return ET.tostring(suite, encoding="utf-8", xml_declaration=True)


def build_report(
    *,
    source_run_id: str,
    source_head_sha: str,
    runner_image: str,
    pip_audit_path: Path,
    bandit_path: Path,
    pip_audit_exit: int,
    bandit_exit: int,
    pip_audit_version: str,
    bandit_version: str,
    scan_started_at: str,
    allowlist_path: Path,
) -> dict[str, Any]:
    if not RUN_ID_RE.fullmatch(source_run_id):
        raise SecurityScanError("source run ID must contain digits only")
    checkout_tree, clean = validate_checkout(source_head_sha)
    allowlist = load_allowlist(allowlist_path)
    allowlist_repo_path = allowlist_path.resolve().relative_to(ROOT.resolve()).as_posix()
    allowlist_blob = _git("rev-parse", f"HEAD:{allowlist_repo_path}")
    scanner_specs = {row["id"]: row for row in allowlist["scanners"]}
    versions = {"pip-audit": pip_audit_version, "bandit": bandit_version}
    if versions != {key: scanner_specs[key]["version"] for key in sorted(SCANNER_IDS)}:
        raise SecurityScanError("installed scanner versions differ from the reviewed allowlist")
    started_at_value = _utc(scan_started_at, "scan startedAt").astimezone(timezone.utc)
    started_at = started_at_value.isoformat().replace("+00:00", "Z")
    complete = pip_audit_exit in (0, 1) and bandit_exit in (0, 1)
    failure_class = "NONE"
    findings: list[dict[str, Any]] = []
    summaries: dict[str, Any] = {}
    if complete:
        required_pins = _required_pins(
            ROOT / scanner_specs["pip-audit"]["scopePaths"][0]
        )
        pip_findings, summaries["pip-audit"], audited_dependencies = parse_pip_audit(
            _read_json(pip_audit_path, "pip-audit"), required_pins
        )
        bandit_scopes = scanner_specs["bandit"]["scopePaths"]
        expected_python_files = sorted(
            path.relative_to(ROOT).as_posix()
            for scope in bandit_scopes
            for path in (ROOT / scope).rglob("*.py")
        )
        bandit_findings, summaries["bandit"], scanned_python_files = parse_bandit(
            _read_json(bandit_path, "bandit"), bandit_scopes, expected_python_files
        )
        findings = sorted(pip_findings + bandit_findings, key=lambda row: row["findingId"])
        if len({row["findingId"] for row in findings}) != len(findings):
            raise SecurityScanError("normalized finding identities are duplicated")
        accepted = {row["findingId"]: row for row in allowlist["acceptedFindings"]}
        actual = {row["findingId"]: row for row in findings}
        stale = sorted(set(accepted) - set(actual))
        unallowlisted = sorted(set(actual) - set(accepted))
        expired = sorted(
            finding_id
            for finding_id in set(actual) & set(accepted)
            if _utc(accepted[finding_id]["expiresAt"], "accepted finding expiresAt")
            <= datetime.now(timezone.utc)
        )
        severity_mismatch = sorted(
            finding_id
            for finding_id in set(actual) & set(accepted)
            if accepted[finding_id]["severity"] != actual[finding_id]["severity"]
        )
        if stale:
            failure_class = "STALE_ALLOWLIST"
        elif severity_mismatch:
            failure_class = "ALLOWLIST_SEVERITY_MISMATCH"
        elif expired:
            failure_class = "EXPIRED_ALLOWLIST"
        elif unallowlisted:
            failure_class = "UNALLOWLISTED_CRITICAL_HIGH"
        verdict = "MEASURED_PASS" if failure_class == "NONE" else "MEASURED_FAIL"
    else:
        stale, unallowlisted, expired, severity_mismatch = [], [], [], []
        audited_dependencies, scanned_python_files = [], []
        verdict = "NOT_OBSERVED"
        failure_class = "SCANNER_UNAVAILABLE"
    scope_paths = sorted(
        {path for scanner in scanner_specs.values() for path in scanner["scopePaths"]}
    )
    scan_inputs = [
        {"path": path, "objectId": _git("rev-parse", f"HEAD:{path}")}
        for path in scope_paths
    ]
    payload = {
        "scannerVersions": versions,
        "scannerExitCodes": {"pip-audit": pip_audit_exit, "bandit": bandit_exit},
        "scanInputs": scan_inputs,
        "auditedDependencies": audited_dependencies,
        "scannedPythonFiles": scanned_python_files,
        "summaries": summaries,
        "criticalHighFindings": findings,
        "criticalCount": sum(row["severity"] == "CRITICAL" for row in findings),
        "highCount": sum(row["severity"] == "HIGH" for row in findings),
        "unallowlistedFindingIds": unallowlisted,
        "expiredFindingIds": expired,
        "staleAllowlistFindingIds": stale,
        "severityMismatchFindingIds": severity_mismatch,
    }
    finished_at = utc_now()
    if _utc(finished_at, "scan finishedAt") < started_at_value:
        raise SecurityScanError("scan finishedAt precedes startedAt")
    return {
        "schemaVersion": SCHEMA_VERSION,
        "runPurpose": RUN_PURPOSE,
        "threatId": THREAT_ID,
        "sourceRunId": source_run_id,
        "sourceHeadSha": source_head_sha,
        "checkoutTreeSha": checkout_tree,
        "cleanCheckout": clean,
        "environment": {
            "runnerImage": runner_image,
            "topology": "hosted",
            "evidenceClass": "security-tools-v0",
            "credentialsRequired": False,
            "externalServicesRequired": True,
        },
        "startedAt": started_at,
        "finishedAt": finished_at,
        "reportAvailable": complete,
        "status": "complete" if complete else "unavailable",
        "allowlist": {"path": allowlist_repo_path, "blob": allowlist_blob},
        "toolFiles": [
            allowlist["producer"], allowlist["workflow"], allowlist["importer"]
        ],
        "payloadSha256": canonical_sha256(payload),
        "payload": payload,
        "verdict": verdict,
        "failureClass": failure_class,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-run-id", required=True)
    parser.add_argument("--source-head-sha", required=True)
    parser.add_argument("--runner-image", required=True)
    parser.add_argument("--pip-audit-json", type=Path, required=True)
    parser.add_argument("--bandit-json", type=Path, required=True)
    parser.add_argument("--pip-audit-exit", type=int, required=True)
    parser.add_argument("--bandit-exit", type=int, required=True)
    parser.add_argument("--pip-audit-version", required=True)
    parser.add_argument("--bandit-version", required=True)
    parser.add_argument("--scan-started-at", required=True)
    parser.add_argument("--allowlist", type=Path, default=DEFAULT_ALLOWLIST)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--junit", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = build_report(
            source_run_id=args.source_run_id,
            source_head_sha=args.source_head_sha,
            runner_image=args.runner_image,
            pip_audit_path=args.pip_audit_json,
            bandit_path=args.bandit_json,
            pip_audit_exit=args.pip_audit_exit,
            bandit_exit=args.bandit_exit,
            pip_audit_version=args.pip_audit_version,
            bandit_version=args.bandit_version,
            scan_started_at=args.scan_started_at,
            allowlist_path=args.allowlist,
        )
    except SecurityScanError as exc:
        print(f"AC-11 security scan refused: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - type-only redacted failure
        print(f"AC-11 security scan errored: {type(exc).__name__}", file=sys.stderr)
        return 3
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.junit.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    args.junit.write_bytes(_junit(report))
    if report["verdict"] == "MEASURED_PASS":
        return 0
    if report["verdict"] == "MEASURED_FAIL":
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
