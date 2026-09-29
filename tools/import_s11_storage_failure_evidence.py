"""Validate S11-ST raw PG-free evidence and derive reference-only metrics."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Any
import xml.etree.ElementTree as ET

from run_s11_storage_failure_pg_free import (
    EXECUTION_LAYER,
    EXPECTED,
    BACKUP_VERIFIER_PATH,
    PG_FREE_CASES,
    PG_FREE_SHA256,
    PRODUCER_PATH,
    RUN_PURPOSE,
    SCHEMA_VERSION,
    UNIVERSE_SHA256,
)


SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
FORBIDDEN_KEYS = {"password", "secret", "token", "credential", "dsn", "endpoint"}
REPORT_KEYS = {
    "schemaVersion", "runPurpose", "executionLayer", "sourceRunId", "sourceHeadSha",
    "checkoutTreeSha", "cleanCheckout", "producerFile", "injectorFile", "backupVerifierFile", "startedAt", "finishedAt",
    "universeCaseIdentitiesSha256", "tierCaseIdentitiesSha256", "caseCount",
    "findingCount", "cases", "redacted",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
PROBLEM_CODE_RE = re.compile(r"^[A-Z]+-[0-9]{4}$")
CASE_KEYS = {
    "caseIdentity", "executionLayer", "provider", "injectionObserved", "attemptedCount",
    "expectedFindingCount", "observedFindingCount", "expectedSurface", "actualSurface",
    "matched", "beforeSha256", "afterSha256", "dbRowDelta", "readyTransitionCount",
    "quotaOvershootBytes", "committedObjectLossCount", "partialResidueCount",
    "tempResidueCount", "cleanupResidueCount", "redacted",
}


class EvidenceImportError(ValueError):
    pass


class RepositoryGit:
    def __init__(self, root: Path):
        self.root = root

    def _run(self, *args: str) -> str:
        completed = subprocess.run(["git", *args], cwd=self.root, text=True, capture_output=True, timeout=15)
        if completed.returncode:
            raise EvidenceImportError("Git provenance is unreachable")
        return completed.stdout.strip()

    def tree(self, commit: str) -> str:
        return self._run("rev-parse", f"{commit}^{{tree}}")

    def blob(self, commit: str, path: str) -> str:
        return self._run("rev-parse", f"{commit}:{path}")


def _reject_secret_keys(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if any(word in key.lower() for word in FORBIDDEN_KEYS):
                raise EvidenceImportError("raw evidence contains a forbidden secret-bearing key")
            _reject_secret_keys(child)
    elif isinstance(value, list):
        for child in value:
            _reject_secret_keys(child)
    elif isinstance(value, str) and (
        "://" in value or value.startswith("Bearer ") or "postgresql:" in value.lower() or "AKIA" in value
    ):
        raise EvidenceImportError("raw evidence contains a forbidden secret-like value")


def _utc(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise EvidenceImportError(f"{field} must be UTC RFC3339")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EvidenceImportError(f"{field} must be UTC RFC3339") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise EvidenceImportError(f"{field} must be UTC RFC3339")
    return parsed


def _validate_surface(surface: Any) -> None:
    if not isinstance(surface, dict):
        raise EvidenceImportError("actual surface must be an object")
    kind = surface.get("kind")
    if kind == "success" and set(surface) == {"kind"}:
        return
    if kind == "problem" and set(surface) == {"kind", "code", "status", "retryable"}:
        if not PROBLEM_CODE_RE.fullmatch(str(surface["code"])):
            raise EvidenceImportError("actual ProblemDetails code is invalid")
        if (
            isinstance(surface["status"], bool)
            or not isinstance(surface["status"], int)
            or not 100 <= surface["status"] <= 599
            or not isinstance(surface["retryable"], bool)
        ):
            raise EvidenceImportError("actual ProblemDetails status or retryable is invalid")
        return
    if kind == "failureClass" and set(surface) == {"kind", "failureClass", "retryable"}:
        allowed = {row["failureClass"] for row in EXPECTED.values() if row["kind"] == "failureClass"}
        if surface["failureClass"] not in allowed or not isinstance(surface["retryable"], bool):
            raise EvidenceImportError("actual failureClass is outside the closed tier")
        return
    if kind == "osError" and set(surface) == {"kind", "errno"}:
        if isinstance(surface["errno"], bool) or not isinstance(surface["errno"], int) or surface["errno"] <= 0:
            raise EvidenceImportError("actual errno is invalid")
        return
    if kind == "unexpected" and set(surface) == {"kind", "class"} and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", str(surface["class"])):
        return
    raise EvidenceImportError("actual surface is outside the closed tier")


def _validate_junit(xml_bytes: bytes, identities: tuple[str, ...], finding_identities: tuple[str, ...]) -> str:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise EvidenceImportError("JUnit is not well-formed XML") from exc
    if root.tag != "testsuite" or set(root.attrib) != {"name", "tests", "failures", "errors", "skipped"} or root.attrib.get("name") != "s11-storage-pg-free":
        raise EvidenceImportError("JUnit suite identity is invalid")
    try:
        counts = tuple(int(root.attrib[name]) for name in ("tests", "failures", "errors", "skipped"))
    except (KeyError, ValueError) as exc:
        raise EvidenceImportError("JUnit counts are missing or invalid") from exc
    if counts != (len(identities), len(finding_identities), 0, 0):
        raise EvidenceImportError("JUnit counts differ from raw evidence")
    names = tuple(node.attrib.get("name", "") for node in root.findall("testcase"))
    if names != identities:
        raise EvidenceImportError("JUnit case identities differ from the reviewed tier")
    for node in root.findall("testcase"):
        if set(node.attrib) != {"name", "classname"} or node.attrib["classname"] != "s11.storage.pg_free":
            raise EvidenceImportError("JUnit testcase shape is invalid")
        children = list(node)
        if len(children) > 1 or any(child.tag != "failure" for child in children):
            raise EvidenceImportError("JUnit testcase result shape is invalid")
    failed_names = {node.attrib.get("name") for node in root.findall("testcase") if node.find("failure") is not None}
    if failed_names != set(finding_identities):
        raise EvidenceImportError("JUnit failures differ from findings")
    return hashlib.sha256(xml_bytes).hexdigest()


def _raise(message: str):
    raise EvidenceImportError(message)


def import_evidence(report: dict[str, Any], junit: bytes, git: Any) -> dict[str, Any]:
    if not isinstance(report, dict) or set(report) != REPORT_KEYS:
        raise EvidenceImportError("raw report requires the exact reviewed key set")
    _reject_secret_keys(report)
    if report["schemaVersion"] != SCHEMA_VERSION or report["runPurpose"] != RUN_PURPOSE:
        raise EvidenceImportError("raw report schema or purpose is unknown")
    if report["executionLayer"] != EXECUTION_LAYER:
        raise EvidenceImportError("raw report execution layer is not PG-free")
    if report["universeCaseIdentitiesSha256"] != UNIVERSE_SHA256 or report["tierCaseIdentitiesSha256"] != PG_FREE_SHA256:
        raise EvidenceImportError("case identity hash differs from the reviewed tier")
    if not SHA1_RE.fullmatch(str(report["sourceHeadSha"])) or not SHA1_RE.fullmatch(str(report["checkoutTreeSha"])):
        raise EvidenceImportError("source provenance SHA is invalid")
    if report["cleanCheckout"] is not True or not re.fullmatch(r"[A-Za-z0-9._:-]{1,64}", str(report["sourceRunId"])):
        raise EvidenceImportError("source run or clean checkout provenance is invalid")
    if git.tree(report["sourceHeadSha"]) != report["checkoutTreeSha"]:
        raise EvidenceImportError("checkout tree differs from source head")
    expected_file = {"path": PRODUCER_PATH, "blob": git.blob(report["sourceHeadSha"], PRODUCER_PATH)}
    if report["producerFile"] != expected_file or report["injectorFile"] != expected_file:
        raise EvidenceImportError("producer or injector blob differs from source head")
    expected_verifier = {
        "path": BACKUP_VERIFIER_PATH,
        "blob": git.blob(report["sourceHeadSha"], BACKUP_VERIFIER_PATH),
    }
    if report["backupVerifierFile"] != expected_verifier:
        raise EvidenceImportError("backup verifier blob differs from source head")
    started = _utc(report["startedAt"], "startedAt")
    finished = _utc(report["finishedAt"], "finishedAt")
    if finished < started:
        raise EvidenceImportError("finishedAt precedes startedAt")
    cases = report["cases"]
    if (
        not isinstance(cases, list)
        or isinstance(report["caseCount"], bool)
        or not isinstance(report["caseCount"], int)
        or report["caseCount"] != len(PG_FREE_CASES)
        or len(cases) != len(PG_FREE_CASES)
    ):
        raise EvidenceImportError("raw report case count is invalid")
    identities = tuple(case.get("caseIdentity") for case in cases if isinstance(case, dict))
    if identities != PG_FREE_CASES or len(set(identities)) != len(identities):
        raise EvidenceImportError("raw report case identities are missing, duplicated or reordered")

    findings = 0
    finding_identities: list[str] = []
    false_success = 0
    classification_mismatch = 0
    unexpected = 0
    cleanup_residue = 0
    committed_loss = 0
    partial_residue = 0
    temp_residue = 0
    quota_overshoot = 0
    observed_counts = {name: 0 for name in (
        "quotaOvershootBytes", "committedObjectLossCount", "partialResidueCount",
        "tempResidueCount", "cleanupResidueCount",
    )}
    for case in cases:
        if set(case) != CASE_KEYS:
            raise EvidenceImportError("case receipt requires the exact reviewed key set")
        identity = case["caseIdentity"]
        if case["executionLayer"] != EXECUTION_LAYER or case["provider"] != "local":
            raise EvidenceImportError("case layer or provider differs from the reviewed tier")
        if (
            case["injectionObserved"] is not True
            or isinstance(case["attemptedCount"], bool)
            or case["attemptedCount"] != 1
            or case["redacted"] is not True
        ):
            raise EvidenceImportError("case injection, attempt or redaction receipt is invalid")
        if case["expectedSurface"] != EXPECTED[identity]:
            raise EvidenceImportError("case expected surface differs from the reviewed contract")
        _validate_surface(case["actualSurface"])
        matched = case["actualSurface"] == EXPECTED[identity]
        if (
            isinstance(case["observedFindingCount"], bool)
            or not isinstance(case["observedFindingCount"], int)
            or isinstance(case["expectedFindingCount"], bool)
            or not isinstance(case["expectedFindingCount"], int)
            or case["expectedFindingCount"] != 0
        ):
            raise EvidenceImportError("producer finding fields are invalid")
        for digest_field in ("beforeSha256", "afterSha256"):
            digest = case[digest_field]
            if digest is not None and not SHA256_RE.fullmatch(str(digest)):
                raise EvidenceImportError("case content digest is invalid")
        if case["dbRowDelta"] is not None or case["readyTransitionCount"] is not None:
            raise EvidenceImportError("PG-free receipt cannot claim database observations")
        for name in (
            "quotaOvershootBytes", "committedObjectLossCount", "partialResidueCount",
            "tempResidueCount", "cleanupResidueCount",
        ):
            value = case[name]
            if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
                raise EvidenceImportError("case numeric receipt is invalid")
            if value is not None:
                observed_counts[name] += 1
        receipt_finding = any(
            isinstance(case[name], int) and case[name] > 0
            for name in (
                "quotaOvershootBytes", "committedObjectLossCount", "partialResidueCount",
                "tempResidueCount", "cleanupResidueCount",
            )
        )
        if identity.startswith("BAK-02/") and case["beforeSha256"] != case["afterSha256"]:
            receipt_finding = True
        observed = int(not matched or receipt_finding)
        if (
            case["matched"] is not (observed == 0)
            or case["observedFindingCount"] != observed
        ):
            raise EvidenceImportError("producer finding fields do not match receipt recomputation")
        findings += observed
        if observed:
            finding_identities.append(identity)
        actual = case["actualSurface"]
        false_success += int(actual.get("kind") == "success")
        classification_mismatch += int(not matched)
        unexpected += int(actual.get("kind") == "unexpected")
        cleanup_residue += int(case["cleanupResidueCount"] or 0)
        committed_loss += int(case["committedObjectLossCount"] or 0)
        partial_residue += int(case["partialResidueCount"] or 0)
        temp_residue += int(case["tempResidueCount"] or 0)
        quota_overshoot += int(case["quotaOvershootBytes"] or 0)
    if (
        isinstance(report["findingCount"], bool)
        or not isinstance(report["findingCount"], int)
        or report["findingCount"] != findings
        or report["redacted"] is not True
    ):
        raise EvidenceImportError("report finding count or redaction marker is invalid")
    junit_sha = _validate_junit(junit, PG_FREE_CASES, tuple(finding_identities))
    verdict = "MEASURED_PASS" if findings == 0 else "MEASURED_FAIL"
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "s11-storage-reference-evidence",
        "runPurpose": "ac11-storage-reference-evidence",
        "referenceOnly": True,
        "axis": None,
        "targetRef": None,
        "executionLayer": EXECUTION_LAYER,
        "sourceRunId": report["sourceRunId"],
        "sourceHeadSha": report["sourceHeadSha"],
        "checkoutTreeSha": report["checkoutTreeSha"],
        "cleanCheckout": True,
        "caseIdentitiesSha256": PG_FREE_SHA256,
        "junitSha256": junit_sha,
        "verdict": verdict,
        "metrics": {
            "attemptedCaseCount": len(PG_FREE_CASES),
            "classificationMismatchCount": classification_mismatch,
            "falseSuccessCount": false_success,
            "unexpectedErrorCount": unexpected,
            "committedObjectLossCount": committed_loss if observed_counts["committedObjectLossCount"] else None,
            "cleanupResidueCount": cleanup_residue if observed_counts["cleanupResidueCount"] else None,
            "partialResidueCount": partial_residue if observed_counts["partialResidueCount"] else None,
            "tempResidueCount": temp_residue if observed_counts["tempResidueCount"] else None,
            "quotaOvershootBytes": quota_overshoot if observed_counts["quotaOvershootBytes"] else None,
            "observedCaseCountByMetric": observed_counts,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--junit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = json.loads(args.report.read_text(encoding="utf-8"))
        evidence = import_evidence(report, args.junit.read_bytes(), RepositoryGit(Path(__file__).resolve().parents[1]))
    except (OSError, json.JSONDecodeError, EvidenceImportError) as exc:
        print(f"INVALID_RUN: {exc}")
        return 2
    args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if evidence["verdict"] == "MEASURED_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
