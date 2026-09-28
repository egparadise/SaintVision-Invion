"""Validate hosted S11-ST fault evidence and emit a reference-only verdict."""

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

from run_s11_storage_failure_hosted import (
    EXECUTION_LAYER,
    EXPECTED,
    EXPECTED_INVARIANTS,
    HARNESS_PATH,
    HOSTED_CASES,
    HOSTED_SHA256,
    PRODUCER_PATH,
    RECOVERY_PROBE_PATH,
    RUN_PURPOSE,
    SCHEMA_VERSION,
    UNIVERSE_SHA256,
)


SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
IMAGE_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
PROBLEM_CODE_RE = re.compile(r"^[A-Z]+-[0-9]{4}$")
FORBIDDEN_KEYS = {"password", "secret", "token", "credential", "dsn", "endpoint", "locator"}
REPORT_KEYS = {
    "schemaVersion", "runPurpose", "executionLayer", "referenceOnly", "axis", "targetRef",
    "sourceRunId", "sourceHeadSha", "checkoutTreeSha", "cleanCheckout", "producerFile",
    "injectorFile", "recoveryProbeFile", "harnessFile", "startedAt", "finishedAt",
    "universeCaseIdentitiesSha256", "tierCaseIdentitiesSha256", "caseCount",
    "findingCount", "cases", "environment", "cleanup", "redacted",
}
CASE_KEYS = {
    "caseIdentity", "executionLayer", "provider", "injectionObserved", "attemptedCount",
    "expectedFindingCount", "observedFindingCount", "expectedSurface", "actualSurface",
    "matched", "dbRowDelta", "readyTransitionCount", "quotaOvershootBytes",
    "committedObjectLossCount", "partialResidueCount", "tempResidueCount",
    "cleanupResidueCount", "sourceExitClass", "verifierExitClass", "archiveByteCount",
    "pitrVerified", "settingsSha256", "redacted",
}
ENVIRONMENT_KEYS = {
    "topology", "runnerOs", "runnerArch", "pythonVersion", "postgresqlVersion",
    "minioImageDigest", "archiveImageDigest", "minioExposure", "archiveNetworkInternal",
    "archivePublishedPortCount", "githubSecretCount", "artifactRetentionDays",
}


class HostedEvidenceImportError(ValueError):
    pass


class RepositoryGit:
    def __init__(self, root: Path):
        self.root = root

    def _run(self, *args: str) -> str:
        completed = subprocess.run(["git", *args], cwd=self.root, text=True, capture_output=True, timeout=15)
        if completed.returncode:
            raise HostedEvidenceImportError("Git provenance is unreachable")
        return completed.stdout.strip()

    def tree(self, commit: str) -> str:
        return self._run("rev-parse", f"{commit}^{{tree}}")

    def blob(self, commit: str, path: str) -> str:
        return self._run("rev-parse", f"{commit}:{path}")


def _reject_secret_material(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key != "githubSecretCount" and any(word in key.lower() for word in FORBIDDEN_KEYS):
                raise HostedEvidenceImportError("evidence contains a forbidden secret-bearing key")
            _reject_secret_material(child)
    elif isinstance(value, list):
        for child in value:
            _reject_secret_material(child)
    elif isinstance(value, str) and (
        "://" in value or value.startswith("Bearer ") or "postgresql:" in value.lower() or "AKIA" in value
    ):
        raise HostedEvidenceImportError("evidence contains a forbidden secret-like value")


def _utc(value: Any, name: str) -> datetime:
    if not isinstance(value, str):
        raise HostedEvidenceImportError(f"{name} must be UTC RFC3339")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HostedEvidenceImportError(f"{name} must be UTC RFC3339") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise HostedEvidenceImportError(f"{name} must be UTC RFC3339")
    return parsed


def _validate_surface(surface: Any) -> None:
    if not isinstance(surface, dict):
        raise HostedEvidenceImportError("actual surface must be an object")
    if surface.get("kind") == "success" and set(surface) == {"kind"}:
        return
    if surface.get("kind") == "problem" and set(surface) == {"kind", "code", "status", "retryable"}:
        if not PROBLEM_CODE_RE.fullmatch(str(surface["code"])):
            raise HostedEvidenceImportError("ProblemDetails code is invalid")
        if type(surface["status"]) is not int or not 100 <= surface["status"] <= 599 or type(surface["retryable"]) is not bool:
            raise HostedEvidenceImportError("ProblemDetails status or retryable is invalid")
        return
    if surface.get("kind") == "failureClass" and set(surface) == {"kind", "failureClass", "retryable"}:
        if surface["failureClass"] not in {"WAL_ARCHIVE_FAILED", "WAL_ARCHIVE_EMPTY"} or type(surface["retryable"]) is not bool:
            raise HostedEvidenceImportError("failureClass is outside the closed hosted tier")
        return
    if surface.get("kind") == "unexpected" and set(surface) == {"kind", "class"}:
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", str(surface["class"])):
            return
    raise HostedEvidenceImportError("actual surface is outside the closed hosted tier")


def _validate_environment(value: Any) -> None:
    if not isinstance(value, dict) or set(value) != ENVIRONMENT_KEYS:
        raise HostedEvidenceImportError("hosted environment requires the exact reviewed key set")
    if value["topology"] != "hosted-single-runner" or value["runnerOs"] != "linux":
        raise HostedEvidenceImportError("hosted topology or runner OS is invalid")
    if not re.fullmatch(r"[a-z0-9_.-]{2,32}", str(value["runnerArch"])):
        raise HostedEvidenceImportError("runner architecture is invalid")
    if not re.fullmatch(r"3\.[0-9]+\.[0-9]+", str(value["pythonVersion"])):
        raise HostedEvidenceImportError("Python version is invalid")
    if not re.match(r"^16(?:\.|$)", str(value["postgresqlVersion"])):
        raise HostedEvidenceImportError("PostgreSQL 16 was not observed")
    if not IMAGE_DIGEST_RE.fullmatch(str(value["minioImageDigest"])) or not IMAGE_DIGEST_RE.fullmatch(str(value["archiveImageDigest"])):
        raise HostedEvidenceImportError("container image digest is invalid")
    if (
        value["minioExposure"] != "loopback-only"
        or value["archiveNetworkInternal"] is not True
        or value["archivePublishedPortCount"] != 0
        or value["githubSecretCount"] != 0
        or value["artifactRetentionDays"] != 30
    ):
        raise HostedEvidenceImportError("hosted isolation or retention receipt is invalid")


def _validate_junit(xml_bytes: bytes, finding_identities: tuple[str, ...]) -> str:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise HostedEvidenceImportError("JUnit is not well-formed XML") from exc
    expected_attrs = {
        "name": "s11-storage-hosted-reference",
        "tests": str(len(HOSTED_CASES)),
        "failures": str(len(finding_identities)),
        "errors": "0",
        "skipped": "0",
    }
    if root.tag != "testsuite" or root.attrib != expected_attrs:
        raise HostedEvidenceImportError("JUnit suite identity or counts are invalid")
    nodes = root.findall("testcase")
    if tuple(node.attrib.get("name") for node in nodes) != HOSTED_CASES:
        raise HostedEvidenceImportError("JUnit case identities differ from the frozen tier")
    failed: list[str] = []
    for node in nodes:
        if set(node.attrib) != {"name", "classname"} or node.attrib["classname"] != "s11.storage.hosted":
            raise HostedEvidenceImportError("JUnit testcase shape is invalid")
        children = list(node)
        if len(children) > 1 or any(child.tag != "failure" for child in children):
            raise HostedEvidenceImportError("JUnit result shape is invalid")
        if children:
            failed.append(node.attrib["name"])
    if tuple(failed) != finding_identities:
        raise HostedEvidenceImportError("JUnit failures differ from raw findings")
    return hashlib.sha256(xml_bytes).hexdigest()


def import_evidence(report: dict[str, Any], junit: bytes, git: Any) -> dict[str, Any]:
    _reject_secret_material(report)
    if not isinstance(report, dict) or set(report) != REPORT_KEYS:
        raise HostedEvidenceImportError("raw report requires the exact reviewed key set")
    if report["schemaVersion"] != SCHEMA_VERSION or report["runPurpose"] != RUN_PURPOSE:
        raise HostedEvidenceImportError("raw report schema or purpose is unknown")
    if report["executionLayer"] != EXECUTION_LAYER:
        raise HostedEvidenceImportError("raw report execution layer is invalid")
    if report["referenceOnly"] is not True or report["axis"] is not None or report["targetRef"] is not None:
        raise HostedEvidenceImportError("hosted storage evidence must remain reference-only")
    if report["universeCaseIdentitiesSha256"] != UNIVERSE_SHA256 or report["tierCaseIdentitiesSha256"] != HOSTED_SHA256:
        raise HostedEvidenceImportError("case identity hash differs from the frozen tier")
    if not SHA1_RE.fullmatch(str(report["sourceHeadSha"])) or not SHA1_RE.fullmatch(str(report["checkoutTreeSha"])):
        raise HostedEvidenceImportError("source provenance SHA is invalid")
    if report["cleanCheckout"] is not True or not re.fullmatch(r"[0-9]+(?:-[0-9]+)?", str(report["sourceRunId"])):
        raise HostedEvidenceImportError("source run or clean checkout provenance is invalid")
    if git.tree(report["sourceHeadSha"]) != report["checkoutTreeSha"]:
        raise HostedEvidenceImportError("checkout tree differs from source head")
    expected_files = {
        "producerFile": PRODUCER_PATH,
        "injectorFile": PRODUCER_PATH,
        "recoveryProbeFile": RECOVERY_PROBE_PATH,
        "harnessFile": HARNESS_PATH,
    }
    for field, path in expected_files.items():
        if report[field] != {"path": path, "blob": git.blob(report["sourceHeadSha"], path)}:
            raise HostedEvidenceImportError(f"{field} differs from source head")
    started = _utc(report["startedAt"], "startedAt")
    finished = _utc(report["finishedAt"], "finishedAt")
    if finished < started:
        raise HostedEvidenceImportError("finishedAt precedes startedAt")
    _validate_environment(report["environment"])
    cleanup = report["cleanup"]
    if not isinstance(cleanup, dict) or cleanup != {
        "performed": True,
        "residueCount": sum(int(case.get("cleanupResidueCount") or 0) for case in report.get("cases", []) if isinstance(case, dict)),
    }:
        raise HostedEvidenceImportError("cleanup receipt differs from case receipts")

    cases = report["cases"]
    if type(report["caseCount"]) is not int or report["caseCount"] != len(HOSTED_CASES) or not isinstance(cases, list) or len(cases) != len(HOSTED_CASES):
        raise HostedEvidenceImportError("raw report case count is invalid")
    identities = tuple(case.get("caseIdentity") for case in cases if isinstance(case, dict))
    if identities != HOSTED_CASES or len(set(identities)) != len(identities):
        raise HostedEvidenceImportError("raw case identities are missing, duplicated or reordered")

    findings = 0
    finding_identities: list[str] = []
    false_success = 0
    classification_mismatch = 0
    unexpected = 0
    metric_names = (
        "quotaOvershootBytes", "committedObjectLossCount", "partialResidueCount",
        "tempResidueCount", "cleanupResidueCount",
    )
    metric_totals = {name: 0 for name in metric_names}
    observed_counts = {name: 0 for name in metric_names}
    for case in cases:
        if set(case) != CASE_KEYS:
            raise HostedEvidenceImportError("case receipt requires the exact reviewed key set")
        identity = case["caseIdentity"]
        expected_provider = "postgresql" if "/postgresql/" in identity else "s3"
        expected_attempts = 8 if identity.endswith("concurrent-8") else 1
        if case["executionLayer"] != EXECUTION_LAYER or case["provider"] != expected_provider:
            raise HostedEvidenceImportError("case layer or provider differs from the frozen tier")
        if case["injectionObserved"] is not True or case["attemptedCount"] != expected_attempts or case["redacted"] is not True:
            raise HostedEvidenceImportError("case injection, attempt or redaction receipt is invalid")
        if case["expectedSurface"] != EXPECTED[identity]:
            raise HostedEvidenceImportError("case expected surface differs from the frozen target")
        _validate_surface(case["actualSurface"])
        for name in ("dbRowDelta", "readyTransitionCount", *metric_names, "archiveByteCount"):
            value = case[name]
            if value is not None and (type(value) is not int or value < 0):
                raise HostedEvidenceImportError("case numeric receipt is invalid")
        if case["sourceExitClass"] not in {None, "zero-observed", "nonzero-observed"} or case["verifierExitClass"] not in {None, "nonzero-observed"}:
            raise HostedEvidenceImportError("case process-exit receipt is invalid")
        if case["pitrVerified"] not in {None, False}:
            raise HostedEvidenceImportError("hosted evidence cannot claim PITR verification")
        if case["settingsSha256"] is not None and not SHA256_RE.fullmatch(str(case["settingsSha256"])):
            raise HostedEvidenceImportError("settings receipt digest is invalid")
        if identity.startswith("BAK-") != (case["settingsSha256"] is not None):
            raise HostedEvidenceImportError("archive settings receipt is missing or misplaced")
        invariant_match = all(case[name] == value for name, value in EXPECTED_INVARIANTS[identity].items())
        matched = case["actualSurface"] == EXPECTED[identity] and invariant_match
        observed = int(not matched)
        if (
            case["expectedFindingCount"] != 0
            or case["observedFindingCount"] != observed
            or case["matched"] is not (observed == 0)
        ):
            raise HostedEvidenceImportError("case finding fields differ from independent recomputation")
        findings += observed
        if observed:
            finding_identities.append(identity)
        false_success += int(case["actualSurface"].get("kind") == "success")
        classification_mismatch += int(case["actualSurface"] != EXPECTED[identity])
        unexpected += int(case["actualSurface"].get("kind") == "unexpected")
        for name in metric_names:
            value = case[name]
            if value is not None:
                observed_counts[name] += 1
                metric_totals[name] += value
    if type(report["findingCount"]) is not int or report["findingCount"] != findings or report["redacted"] is not True:
        raise HostedEvidenceImportError("report finding count or redaction marker is invalid")
    junit_sha = _validate_junit(junit, tuple(finding_identities))
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
        "caseIdentitiesSha256": HOSTED_SHA256,
        "junitSha256": junit_sha,
        "verdict": verdict,
        "metrics": {
            "attemptedCaseCount": len(HOSTED_CASES),
            "classificationMismatchCount": classification_mismatch,
            "falseSuccessCount": false_success,
            "unexpectedErrorCount": unexpected,
            **{
                name: metric_totals[name] if observed_counts[name] else None
                for name in metric_names
            },
            "observedCaseCountByMetric": observed_counts,
        },
        "environment": report["environment"],
        "cleanup": report["cleanup"],
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
    except (OSError, json.JSONDecodeError, HostedEvidenceImportError) as exc:
        print(f"INVALID_RUN: {exc}")
        return 2
    args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # A product finding is preserved as MEASURED_FAIL inside a successful,
    # complete reference run.  Only malformed/incomplete evidence exits 2.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
