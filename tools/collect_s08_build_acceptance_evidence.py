"""Create and independently evaluate fixed-SHA S08 build acceptance evidence.

The collector does not execute product logic.  It extracts a fixed set of existing
product tests from the Core workflow's JUnit files.  The evaluator distrusts the
collector: it validates exact JSON shapes, re-reads both JUnit artifacts and the
redacted worker configuration, recomputes every count and digest, and then derives
the verdict from those observations.

This is hosted evidence, not physical-builder acceptance.  It never changes the
default-off product flag and never claims an S08-BE score change.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable
import xml.etree.ElementTree as ET


SCHEMA_VERSION = "s08-build-acceptance-evidence:1"
EVALUATION_VERSION = "s08-build-acceptance-evaluation:1"
WORKER_SCHEMA_VERSION = "s08-build-acceptance-worker:1"
EXPECTED_WORKER_CONFIG_SHA256 = "53bfeeba087e6ef5f060fea6c2cd2a20073fbf85ad63c03978887c8839b44cc7"
REPOSITORY = "egparadise/SaintVision-Invion"
WORKFLOW = ".github/workflows/core.yml"
EXPECTED_JUNIT_NAMES = {"core-tests.xml", "build-product-runtime-real-pg.xml"}
SHA40 = re.compile(r"[0-9a-f]{40}")
SHA256 = re.compile(r"[0-9a-f]{64}")
UTC_TIMESTAMP = re.compile(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")

CASE_SPECS: tuple[dict[str, str], ...] = (
    {
        "caseId": "prepare-approve-enqueue-dispatch-once",
        "classname": "tests.integration.test_build_preparations_real_pg",
        "name": "test_build_request_to_worker_is_one_server_owned_chain",
        "requirement": "prepare -> two-person approval -> enqueue -> admission -> intent -> dispatch exactly once",
    },
    {
        "caseId": "flag-off-dispatch-zero",
        "classname": "tests.integration.test_build_product_runtime_real_pg",
        "name": "test_flag_off_preserves_admission_without_intent_or_dispatch",
        "requirement": "default-off runtime preserves a ready admission and creates no intent or dispatch",
    },
    {
        "caseId": "flag-off-enqueue-admission-zero",
        "classname": "tests.core.test_build_preparations",
        "name": "test_flag_off_refuses_before_quota_approval_or_storage",
        "requirement": "default-off enqueue touches no database or storage and creates no admission",
    },
    {
        "caseId": "raw-authority-rejected",
        "classname": "tests.core.test_build_preparations",
        "name": "test_public_inputs_are_strict_and_raw_authority_is_rejected",
        "requirement": "public input rejects caller-supplied BuildPlan, provider and authority fields",
    },
    {
        "caseId": "foreign-tenant-plan-rejected",
        "classname": "tests.integration.test_build_product_runtime_real_pg",
        "name": "test_build_dispatch_rejects_foreign_tenant_plan_and_rolls_back",
        "requirement": "tenant mismatch rolls back without an admission",
    },
    {
        "caseId": "forged-approved-by-rejected",
        "classname": "tests.integration.test_build_product_runtime_real_pg",
        "name": "test_committed_admission_rejects_forged_approved_by_without_changing_receipt",
        "requirement": "approvedBy is server-derived and cannot be forged",
    },
    {
        "caseId": "admission-idempotent-and-tenant-isolated",
        "classname": "tests.integration.test_build_product_runtime_real_pg",
        "name": "test_committed_admission_promotes_atomically_and_is_tenant_isolated",
        "requirement": "exact replay is idempotent and another tenant cannot consume the row",
    },
    {
        "caseId": "two-worker-dispatch-once",
        "classname": "tests.integration.test_build_product_runtime_real_pg",
        "name": "test_two_product_loops_promote_and_dispatch_exactly_once",
        "requirement": "concurrent product loops dispatch exactly once",
    },
    {
        "caseId": "intent-claim-completes-once",
        "classname": "tests.integration.test_build_execution_intents_real_pg",
        "name": "test_internal_product_worker_calls_service_once_and_completes",
        "requirement": "the product worker claims one intent, calls the service once and completes it",
    },
    {
        "caseId": "project-permission-rejected",
        "classname": "tests.integration.test_build_product_runtime_real_pg",
        "name": "test_missing_project_permission_records_no_admission",
        "requirement": "missing project permission records no admission",
    },
    {
        "caseId": "quota-rate-limit-enforced",
        "classname": "tests.integration.test_build_preparations_real_pg",
        "name": "test_prepare_rate_limit_is_enforced_before_repeated_failed_work",
        "requirement": "repeated failed preparation cannot bypass quota",
    },
    {
        "caseId": "source-drift-terminal",
        "classname": "tests.integration.test_build_preparations_real_pg",
        "name": "test_source_drift_before_enqueue_expires_approval_without_admission",
        "requirement": "post-quorum source drift terminalizes without admission",
    },
    {
        "caseId": "legacy-build-no-regression",
        "classname": "tests.integration.test_build_preparations_real_pg",
        "name": "test_legacy_build_quorum_and_approved_drift_terminalize_without_invalid_transition",
        "requirement": "legacy direct build quorum remains valid and drift remains terminal",
    },
)

TOP_KEYS = {
    "schemaVersion", "generatedAt", "source", "workerConfiguration",
    "junitArtifacts", "observations", "claims",
}
SOURCE_KEYS = {
    "codeSha", "checkoutTreeSha", "cleanCheckout", "repository", "workflow",
    "job", "runId", "runAttempt",
}
WORKER_ENVELOPE_KEYS = {"sha256", "configuration"}
WORKER_KEYS = {
    "builderAuthority", "database", "externalBuilderRequired", "nodeRuntime",
    "productFlagCoverage", "schemaVersion", "secretsIncluded",
}
JUNIT_KEYS = {
    "name", "sha256", "testCount", "passedCount", "failureCount", "errorCount",
    "skippedCount",
}
OBSERVATION_KEYS = {"caseId", "nodeId", "requirement", "junitArtifact", "outcome"}
CLAIM_KEYS = {"physicalBuilderAcceptance", "productFlagDefaultOff", "scoreChangeClaim"}


class InvalidEvidence(ValueError):
    """The evidence cannot support any measured verdict."""


def _exact_keys(value: Any, expected: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        actual = sorted(value) if isinstance(value, dict) else type(value).__name__
        raise InvalidEvidence(f"{label} exact keys differ: {actual}")
    return value


def _strict_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise InvalidEvidence(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"), object_pairs_hook=_strict_pairs)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise InvalidEvidence(f"cannot read strict JSON {path.name}") from exc


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _junit_outcome(case: ET.Element) -> str:
    if case.find("failure") is not None:
        return "failed"
    if case.find("error") is not None:
        return "error"
    if case.find("skipped") is not None:
        return "skipped"
    return "passed"


def read_junit(path: Path) -> tuple[dict[str, Any], dict[tuple[str, str], str]]:
    raw = path.read_bytes()
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise InvalidEvidence(f"{path.name} is not JUnit XML") from exc
    if root.tag not in {"testsuite", "testsuites"}:
        raise InvalidEvidence(f"{path.name} has an unexpected root")
    cases: dict[tuple[str, str], str] = {}
    counts = {"passed": 0, "failed": 0, "error": 0, "skipped": 0}
    for case in root.findall(".//testcase"):
        identity = (case.get("classname") or "", case.get("name") or "")
        if identity in cases:
            raise InvalidEvidence(f"{path.name} repeats testcase {identity!r}")
        outcome = _junit_outcome(case)
        cases[identity] = outcome
        counts[outcome] += 1
    if not cases:
        raise InvalidEvidence(f"{path.name} has no testcase")
    summary = {
        "name": path.name,
        "sha256": sha256(raw),
        "testCount": len(cases),
        "passedCount": counts["passed"],
        "failureCount": counts["failed"],
        "errorCount": counts["error"],
        "skippedCount": counts["skipped"],
    }
    return summary, cases


def _read_inputs(junit_paths: Iterable[Path], worker_path: Path):
    paths = list(junit_paths)
    if {path.name for path in paths} != EXPECTED_JUNIT_NAMES or len(paths) != 2:
        raise InvalidEvidence("the two canonical JUnit artifact names are required exactly once")
    junit_summaries = []
    case_sources: dict[tuple[str, str], tuple[str, str]] = {}
    for path in sorted(paths, key=lambda item: item.name):
        summary, cases = read_junit(path)
        junit_summaries.append(summary)
        for identity, outcome in cases.items():
            if identity in case_sources:
                raise InvalidEvidence(f"testcase appears in two JUnit artifacts: {identity!r}")
            case_sources[identity] = (path.name, outcome)
    worker = _exact_keys(load_json(worker_path), WORKER_KEYS, "worker configuration")
    if worker["schemaVersion"] != WORKER_SCHEMA_VERSION:
        raise InvalidEvidence("worker configuration schemaVersion differs")
    if worker["secretsIncluded"] is not False or worker["externalBuilderRequired"] is not False:
        raise InvalidEvidence("hosted worker configuration must be redacted and self-contained")
    worker_digest = sha256(canonical_bytes(worker))
    if worker_digest != EXPECTED_WORKER_CONFIG_SHA256:
        raise InvalidEvidence("worker configuration differs from the reviewed fixed-SHA lane")
    return junit_summaries, case_sources, worker, worker_digest


def _observations(case_sources: dict[tuple[str, str], tuple[str, str]]) -> list[dict[str, str]]:
    observations = []
    for spec in CASE_SPECS:
        identity = (spec["classname"], spec["name"])
        if identity not in case_sources:
            raise InvalidEvidence(f"required testcase is absent: {identity!r}")
        artifact, outcome = case_sources[identity]
        observations.append(
            {
                "caseId": spec["caseId"],
                "nodeId": f"{spec['classname'].replace('.', '/')}.py::{spec['name']}",
                "requirement": spec["requirement"],
                "junitArtifact": artifact,
                "outcome": outcome,
            }
        )
    return observations


def collect(
    *, junit_paths: Iterable[Path], worker_path: Path, code_sha: str,
    checkout_tree_sha: str, clean_checkout: bool, run_id: int, run_attempt: int,
) -> dict[str, Any]:
    if not SHA40.fullmatch(code_sha) or not SHA40.fullmatch(checkout_tree_sha):
        raise InvalidEvidence("codeSha and checkoutTreeSha must be lowercase 40-character SHAs")
    if clean_checkout is not True:
        raise InvalidEvidence("evidence collection requires a clean checkout")
    junit, cases, worker, worker_digest = _read_inputs(junit_paths, worker_path)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source": {
            "codeSha": code_sha,
            "checkoutTreeSha": checkout_tree_sha,
            "cleanCheckout": True,
            "repository": REPOSITORY,
            "workflow": WORKFLOW,
            "job": "core",
            "runId": run_id,
            "runAttempt": run_attempt,
        },
        "workerConfiguration": {"sha256": worker_digest, "configuration": worker},
        "junitArtifacts": junit,
        "observations": _observations(cases),
        "claims": {
            "physicalBuilderAcceptance": "NOT_OBSERVED",
            "productFlagDefaultOff": True,
            "scoreChangeClaim": False,
        },
    }


def evaluate(
    evidence: dict[str, Any], *, junit_paths: Iterable[Path], worker_path: Path,
    expected_source_sha: str, expected_checkout_tree_sha: str,
    expected_run_id: int, expected_run_attempt: int,
) -> dict[str, Any]:
    _exact_keys(evidence, TOP_KEYS, "evidence")
    if evidence["schemaVersion"] != SCHEMA_VERSION:
        raise InvalidEvidence("evidence schemaVersion differs")
    if not isinstance(evidence["generatedAt"], str) or not UTC_TIMESTAMP.fullmatch(evidence["generatedAt"]):
        raise InvalidEvidence("generatedAt must be whole-second UTC RFC3339")
    source = _exact_keys(evidence["source"], SOURCE_KEYS, "source")
    if not SHA40.fullmatch(expected_source_sha) or source["codeSha"] != expected_source_sha:
        raise InvalidEvidence("source codeSha differs from the expected checkout")
    if (
        not SHA40.fullmatch(expected_checkout_tree_sha)
        or source["checkoutTreeSha"] != expected_checkout_tree_sha
    ):
        raise InvalidEvidence("checkoutTreeSha differs from the expected checkout tree")
    if (
        source["cleanCheckout"] is not True
        or source["repository"] != REPOSITORY
        or source["workflow"] != WORKFLOW
        or source["job"] != "core"
    ):
        raise InvalidEvidence("source provenance differs")
    if (
        type(expected_run_id) is not int or expected_run_id <= 0
        or type(source["runId"]) is not int or source["runId"] != expected_run_id
    ):
        raise InvalidEvidence("runId differs from the expected workflow run")
    if (
        type(expected_run_attempt) is not int or expected_run_attempt <= 0
        or type(source["runAttempt"]) is not int
        or source["runAttempt"] != expected_run_attempt
    ):
        raise InvalidEvidence("runAttempt differs from the expected workflow attempt")

    expected_junit, case_sources, worker, worker_digest = _read_inputs(junit_paths, worker_path)
    worker_envelope = _exact_keys(evidence["workerConfiguration"], WORKER_ENVELOPE_KEYS, "workerConfiguration")
    _exact_keys(worker_envelope["configuration"], WORKER_KEYS, "workerConfiguration.configuration")
    if worker_envelope != {"sha256": worker_digest, "configuration": worker}:
        raise InvalidEvidence("worker configuration or digest differs from the canonical input")

    junit = evidence["junitArtifacts"]
    if not isinstance(junit, list) or len(junit) != 2:
        raise InvalidEvidence("junitArtifacts must contain exactly two artifacts")
    for index, item in enumerate(junit):
        _exact_keys(item, JUNIT_KEYS, f"junitArtifacts[{index}]")
        for count in ("testCount", "passedCount", "failureCount", "errorCount", "skippedCount"):
            if type(item[count]) is not int or item[count] < 0:
                raise InvalidEvidence(f"junitArtifacts[{index}].{count} must be a non-negative integer")
        if item["testCount"] != sum(item[key] for key in ("passedCount", "failureCount", "errorCount", "skippedCount")):
            raise InvalidEvidence(f"junitArtifacts[{index}] counts disagree")
        if not SHA256.fullmatch(item["sha256"]):
            raise InvalidEvidence(f"junitArtifacts[{index}].sha256 differs")
    if junit != expected_junit:
        raise InvalidEvidence("JUnit summaries differ from the uploaded XML bytes")
    summaries = {item["name"]: item for item in expected_junit}
    runtime_summary = summaries["build-product-runtime-real-pg.xml"]
    if runtime_summary["testCount"] != 13 or runtime_summary["skippedCount"] != 0:
        raise InvalidEvidence("build product real-PG artifact must execute exactly 13 cases with no skip")

    expected_observations = _observations(case_sources)
    observations = evidence["observations"]
    if not isinstance(observations, list) or len(observations) != len(CASE_SPECS):
        raise InvalidEvidence("observations must contain the exact required case set")
    for index, item in enumerate(observations):
        _exact_keys(item, OBSERVATION_KEYS, f"observations[{index}]")
    if observations != expected_observations:
        raise InvalidEvidence("observations differ from the canonical case registry or JUnit bytes")
    if len({item["caseId"] for item in observations}) != len(observations):
        raise InvalidEvidence("observations repeat a caseId")

    claims = _exact_keys(evidence["claims"], CLAIM_KEYS, "claims")
    if claims != {
        "physicalBuilderAcceptance": "NOT_OBSERVED",
        "productFlagDefaultOff": True,
        "scoreChangeClaim": False,
    }:
        raise InvalidEvidence("claims exceed the hosted evidence boundary")

    outcomes = [item["outcome"] for item in expected_observations]
    artifact_failures = sum(
        item["failureCount"] + item["errorCount"] for item in expected_junit
    )
    verdict = (
        "MEASURED_PASS"
        if set(outcomes) == {"passed"} and artifact_failures == 0
        else "MEASURED_FAIL"
    )
    return {
        "schemaVersion": EVALUATION_VERSION,
        "evidenceSha256": sha256(canonical_bytes(evidence)),
        "sourceSha": source["codeSha"],
        "checkoutTreeSha": source["checkoutTreeSha"],
        "runId": source["runId"],
        "runAttempt": source["runAttempt"],
        "job": source["job"],
        "workerConfigSha256": worker_digest,
        "verdict": verdict,
        "requiredCaseCount": len(CASE_SPECS),
        "passedCaseCount": outcomes.count("passed"),
        "failedCaseCount": len(outcomes) - outcomes.count("passed"),
        "scoreChangeClaim": False,
    }


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", "utf-8")


def _paths(values: list[str]) -> list[Path]:
    return [Path(value) for value in values]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    collect_parser = sub.add_parser("collect")
    evaluate_parser = sub.add_parser("evaluate")
    for child in (collect_parser, evaluate_parser):
        child.add_argument("--junit", action="append", required=True)
        child.add_argument("--worker-config", required=True)
        child.add_argument("--expected-source-sha", required=True)
        child.add_argument("--output", required=True)
    collect_parser.add_argument("--checkout-tree-sha", required=True)
    collect_parser.add_argument("--clean-checkout", action="store_true")
    collect_parser.add_argument("--run-id", required=True, type=int)
    collect_parser.add_argument("--run-attempt", required=True, type=int)
    evaluate_parser.add_argument("--evidence", required=True)
    evaluate_parser.add_argument("--checkout-tree-sha", required=True)
    evaluate_parser.add_argument("--run-id", required=True, type=int)
    evaluate_parser.add_argument("--run-attempt", required=True, type=int)
    args = parser.parse_args(argv)
    try:
        if args.command == "collect":
            value = collect(
                junit_paths=_paths(args.junit), worker_path=Path(args.worker_config),
                code_sha=args.expected_source_sha, checkout_tree_sha=args.checkout_tree_sha,
                clean_checkout=args.clean_checkout, run_id=args.run_id, run_attempt=args.run_attempt,
            )
            _write(Path(args.output), value)
            return 0
        evidence = load_json(Path(args.evidence))
        result = evaluate(
            evidence, junit_paths=_paths(args.junit), worker_path=Path(args.worker_config),
            expected_source_sha=args.expected_source_sha,
            expected_checkout_tree_sha=args.checkout_tree_sha,
            expected_run_id=args.run_id,
            expected_run_attempt=args.run_attempt,
        )
        _write(Path(args.output), result)
        return 0 if result["verdict"] == "MEASURED_PASS" else 1
    except (InvalidEvidence, OSError, ET.ParseError) as exc:
        print(f"INVALID_RUN: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
