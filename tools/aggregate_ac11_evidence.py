"""Fail-closed AC-11 evidence aggregator (stage 1, PG-free).

This tool implements the evidence and release-gate rules approved in PR #157
at a793f258.  It never runs migrations or PostgreSQL.  Producers' verdicts are
inputs for consistency checks only; observations, target provenance and the
reviewed security allowlist are independently evaluated here.

Exit 0: all eight required axes were recomputed MEASURED_PASS.
Exit 1: valid evidence exists but AC-11 is not done.
Exit 2: the manifest or one of its current-schema envelopes is invalid.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Protocol


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ALLOWLIST = (
    ROOT / "docs/vault/30_Development/Evidence/s11-security-allowlist-v0.json"
)
SCHEMA_VERSION = "1.0.0"
RUN_PURPOSE = "ac11-release-gate"
AXIS_PURPOSE = "ac11-axis-evidence"
DESIGN_HEAD = "a793f258"


class Verdict(str, Enum):
    MEASURED_PASS = "MEASURED_PASS"
    MEASURED_FAIL = "MEASURED_FAIL"
    NOT_OBSERVED = "NOT_OBSERVED"
    BLOCKED_EXTERNAL = "BLOCKED_EXTERNAL"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_REGISTERED = "NOT_REGISTERED"
    INVALID_RUN = "INVALID_RUN"


REQUIRED_AXES = (
    "migration-reversible-segment",
    "irreversible-restore-forward",
    "actual-pitr-rpo-rto-retention",
    "physical-five-node-ac05-placement-load",
    "physical-five-node-failure-recovery",
    "long-soak",
    "security-critical-high-zero",
    "accessibility-e2e",
)

SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
KNOWN_OPERATORS = {"lt", "lte", "eq", "gte", "gt"}

DEFINER_FILES = [
    {"path": "tools/check_definer_functions.py", "blob": "5831f8d8806900146add2e5e7b51b934dced3952"},
    {"path": "tools/definer-policy.json", "blob": "c1581f1ff2cd9ea23ea1a30849df90679087f70e"},
]
RLS_FILES = [
    {"path": "tools/collect_rls_evidence.py", "blob": "329da31a6c989d5eed7f7b64135c211994a2a932"},
    {"path": "tools/rls-boundary-baseline.json", "blob": "698a5b55d3f7ca5042d2760b0d8b448ea0143404"},
]

DEFINER_CRITICAL = {
    "unrecognized_privileged_function",
    "runtime_role_bypasses_rls",
    "runtime_can_create_in_trusted_schema",
    "runtime_can_assume_function_owner",
}
DEFINER_HIGH = {
    "definition_differs_from_policy",
    "execute_grants_differ_from_policy",
    "expected_privileged_function_missing",
}
DEFINER_INVALID = {"migration_revision_mismatch"}
DEFINER_UNOBSERVED = {"runtime_role_missing"}
DEFINER_KNOWN = DEFINER_CRITICAL | DEFINER_HIGH | DEFINER_INVALID | DEFINER_UNOBSERVED
RLS_RULES = {f"E{number}" for number in range(1, 7)}


class GitReader(Protocol):
    def tree(self, commit: str) -> str: ...
    def is_ancestor(self, ancestor: str, descendant: str) -> bool: ...
    def blob(self, commit: str, path: str) -> str: ...


class RepositoryGit:
    def __init__(self, root: Path):
        self.root = root

    def _run(self, *args: str) -> str:
        result = subprocess.run(
            ["git", *args], cwd=self.root, text=True, capture_output=True, timeout=15
        )
        if result.returncode:
            raise ValueError("git provenance is unreachable")
        return result.stdout.strip()

    def tree(self, commit: str) -> str:
        return self._run("rev-parse", f"{commit}^{{tree}}")

    def is_ancestor(self, ancestor: str, descendant: str) -> bool:
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", ancestor, descendant],
            cwd=self.root,
            text=True,
            capture_output=True,
            timeout=15,
        )
        if result.returncode not in (0, 1):
            raise ValueError("git ancestry is unreachable")
        return result.returncode == 0

    def blob(self, commit: str, path: str) -> str:
        return self._run("rev-parse", f"{commit}:{path}")


@dataclass(frozen=True)
class AxisResult:
    axis: str
    verdict: Verdict
    reasons: tuple[str, ...]
    reference_only: bool = False

    def json(self) -> dict[str, Any]:
        return {
            "axis": self.axis,
            "verdict": self.verdict.value,
            "reasons": list(self.reasons),
            "referenceOnly": self.reference_only,
        }


def _utc(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a UTC RFC3339 string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError(f"{field} must be UTC")
    return parsed


def _files(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise ValueError("toolFiles must be a list")
    normalized = []
    for item in value:
        if not isinstance(item, dict) or set(item) != {"path", "blob"}:
            raise ValueError("toolFiles entries require exact path/blob keys")
        if not SHA1_RE.fullmatch(str(item["blob"])):
            raise ValueError("toolFiles blob must be a full Git blob SHA")
        normalized.append({"path": str(item["path"]), "blob": str(item["blob"])})
    return sorted(normalized, key=lambda row: row["path"])


def _producer_verdict(value: Any) -> Verdict:
    try:
        return Verdict(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("producer verdict is outside the closed enum") from exc


def _compare(value: float, operator: str, target: float) -> bool:
    if operator == "lt":
        return value < target
    if operator == "lte":
        return value <= target
    if operator == "eq":
        return value == target
    if operator == "gte":
        return value >= target
    if operator == "gt":
        return value > target
    raise ValueError("target operator is unknown")


def _validate_target(target: Any, source: str, git: GitReader) -> dict[str, Any]:
    if not isinstance(target, dict):
        raise ValueError("targetRef is required")
    required = {"commit", "path", "blob", "criteria"}
    if not required.issubset(target):
        raise ValueError("targetRef requires commit/path/blob/criteria")
    commit, path, blob = str(target["commit"]), str(target["path"]), str(target["blob"])
    if not SHA1_RE.fullmatch(commit) or not SHA1_RE.fullmatch(blob) or not path:
        raise ValueError("targetRef contains an invalid commit, path or blob")
    if not git.is_ancestor(commit, source):
        raise ValueError("targetRef commit is not an ancestor of sourceHeadSha")
    if git.blob(commit, path) != blob or git.blob(source, path) != blob:
        raise ValueError("targetRef blob is not identical in target and source trees")
    if not isinstance(target["criteria"], dict):
        raise ValueError("targetRef criteria must be an object")
    return target["criteria"]


def _validate_common(
    envelope: dict[str, Any], git: GitReader, now: datetime
) -> tuple[Verdict, dict[str, Any] | None, str]:
    producer = _producer_verdict(envelope.get("verdict"))
    required = {
        "runPurpose", "sourceRunId", "sourceHeadSha", "checkoutTreeSha",
        "artifactSha256", "artifactObservedSha256", "artifactAvailable", "artifactExpiresAt", "cleanCheckout",
        "runConclusion", "environment", "startedAt", "finishedAt", "cleanup",
    }
    missing = sorted(required - envelope.keys())
    if missing:
        raise ValueError("missing envelope fields: " + ", ".join(missing))
    if envelope["runPurpose"] != AXIS_PURPOSE or not str(envelope["sourceRunId"]).strip():
        raise ValueError("unknown runPurpose or empty sourceRunId")
    source, checkout_tree = str(envelope["sourceHeadSha"]), str(envelope["checkoutTreeSha"])
    if not SHA1_RE.fullmatch(source) or not SHA1_RE.fullmatch(checkout_tree):
        raise ValueError("sourceHeadSha and checkoutTreeSha must be full Git SHAs")
    if git.tree(source) != checkout_tree:
        raise ValueError("checkoutTreeSha does not equal sourceHeadSha tree")
    if envelope["cleanCheckout"] is not True:
        raise ValueError("cleanCheckout must be true")
    if envelope["runConclusion"] != "success":
        raise ValueError("failed or cancelled hosted run is not evidence")
    if not SHA256_RE.fullmatch(str(envelope["artifactSha256"])):
        raise ValueError("artifactSha256 must be a full SHA-256")
    if envelope["artifactObservedSha256"] != envelope["artifactSha256"]:
        raise ValueError("downloaded artifact digest does not match artifactSha256")
    if envelope["artifactAvailable"] is not True:
        raise ValueError("artifact is unavailable")
    if _utc(envelope["artifactExpiresAt"], "artifactExpiresAt") <= now:
        raise ValueError("artifact is expired")
    started = _utc(envelope["startedAt"], "startedAt")
    finished = _utc(envelope["finishedAt"], "finishedAt")
    if finished < started:
        raise ValueError("finishedAt precedes startedAt")
    environment = envelope["environment"]
    if not isinstance(environment, dict) or not str(environment.get("comparableGroup", "")).strip():
        raise ValueError("environment.comparableGroup is required")
    cleanup = envelope["cleanup"]
    residue = cleanup.get("residueCount") if isinstance(cleanup, dict) else None
    if isinstance(residue, bool) or not isinstance(residue, int) or residue < 0:
        raise ValueError("cleanup.residueCount must be a non-negative integer")
    target = envelope.get("targetRef")
    criteria = None if target is None else _validate_target(target, source, git)
    return producer, criteria, source


def _generic_observations(envelope: dict[str, Any], criteria: dict[str, Any]) -> Verdict:
    observations = envelope.get("observations")
    if not isinstance(observations, list) or not observations:
        raise ValueError("observations must be a non-empty list")
    failed = False
    metrics: set[str] = set()
    for item in observations:
        if not isinstance(item, dict):
            raise ValueError("observation must be an object")
        metric = item.get("metric")
        if not isinstance(metric, str) or not metric or metric in metrics:
            raise ValueError("observation metrics must be unique non-empty strings")
        metrics.add(metric)
        n = item.get("n")
        success, failure, skip = item.get("successCount"), item.get("failureCount"), item.get("skipCount")
        if not all(
            isinstance(value, int) and not isinstance(value, bool) and value >= 0
            for value in (n, success, failure, skip)
        ):
            raise ValueError("observation counts must be non-negative integers")
        if n == 0 or success + failure + skip != n:
            raise ValueError("observation denominator is empty or inconsistent")
        errors = item.get("errorsByClass", {})
        if failure:
            if not isinstance(errors, dict) or not errors or any(
                not isinstance(value, int) or value < 0 for value in errors.values()
            ) or sum(errors.values()) != failure:
                raise ValueError("failureCount must equal errorsByClass sum")
        elif errors not in ({}, None):
            raise ValueError("errorsByClass must be empty when failureCount is zero")
        if "p95" in metric.lower() and item.get("population") != "all":
            raise ValueError("P95 must use the all-request population")
        rule = criteria.get(metric)
        if not isinstance(rule, dict) or set(rule) != {"operator", "value"}:
            raise ValueError(f"target criterion is missing or malformed for {metric}")
        operator = rule["operator"]
        if operator not in KNOWN_OPERATORS:
            raise ValueError("target operator is unknown")
        value, target = item.get("value"), rule["value"]
        if (
            isinstance(value, bool)
            or isinstance(target, bool)
            or not isinstance(value, (int, float))
            or not isinstance(target, (int, float))
        ):
            raise ValueError("observation and target values must be numeric")
        if not math.isfinite(float(value)) or not math.isfinite(float(target)):
            raise ValueError("observation and target values must be finite")
        failed = failed or not _compare(float(value), operator, float(target))
    if set(criteria) != metrics:
        raise ValueError("target criteria and observation metrics must match exactly")
    return Verdict.MEASURED_FAIL if failed else Verdict.MEASURED_PASS


def evaluate_definer(report: dict[str, Any]) -> Verdict:
    if _files(report.get("toolFiles")) != _files(DEFINER_FILES):
        return Verdict.INVALID_RUN
    exit_code = report.get("exitCode")
    findings = report.get("findings")
    if exit_code == 2:
        return Verdict.NOT_OBSERVED
    if exit_code not in (0, 1) or not isinstance(findings, list):
        return Verdict.INVALID_RUN
    problems = []
    for finding in findings:
        if not isinstance(finding, dict) or not isinstance(finding.get("problems"), list):
            return Verdict.INVALID_RUN
        problems.extend(finding["problems"])
    if any(problem not in DEFINER_KNOWN for problem in problems):
        return Verdict.INVALID_RUN
    if exit_code == 0:
        return Verdict.MEASURED_PASS if not problems else Verdict.INVALID_RUN
    if not problems:
        return Verdict.INVALID_RUN
    if DEFINER_INVALID.intersection(problems):
        return Verdict.INVALID_RUN
    if DEFINER_CRITICAL.intersection(problems) or DEFINER_HIGH.intersection(problems):
        return Verdict.MEASURED_FAIL
    return Verdict.NOT_OBSERVED


def _accepted_disposition(violation: dict[str, Any], allowlist: dict[str, Any], now: datetime) -> Verdict | None:
    rule, role, table = violation.get("rule"), violation.get("role"), violation.get("table")
    for entry in allowlist.get("rlsAcceptedDispositions", []):
        if entry.get("role") == role and entry.get("table") == table and rule in entry.get("rules", []):
            proof = entry.get("proof")
            if not isinstance(proof, str) or not proof.strip():
                return Verdict.INVALID_RUN
            disposition = entry.get("disposition")
            if disposition == "accepted-with-expiry":
                try:
                    expires = datetime.fromisoformat(str(entry["expiresAt"]).replace("Z", "+00:00"))
                except (KeyError, ValueError):
                    return Verdict.INVALID_RUN
                return Verdict.MEASURED_PASS if expires > now else Verdict.MEASURED_FAIL
            if disposition == "false-positive-with-proof":
                return Verdict.MEASURED_PASS
            return Verdict.INVALID_RUN
    return None


def validate_allowlist(allowlist: Any) -> None:
    if not isinstance(allowlist, dict) or set(allowlist) != {
        "schemaVersion", "verifiedAt", "secVf001", "rlsAcceptedDispositions"
    }:
        raise ValueError("security allowlist requires the exact v0 top-level fields")
    if allowlist["schemaVersion"] != SCHEMA_VERSION:
        raise ValueError("security allowlist schemaVersion is unknown")
    verified = datetime.fromisoformat(str(allowlist["verifiedAt"]).replace("Z", "+00:00"))
    if verified.tzinfo is None:
        raise ValueError("security allowlist verifiedAt must include a timezone")
    entries = allowlist["rlsAcceptedDispositions"]
    if not isinstance(entries, list):
        raise ValueError("rlsAcceptedDispositions must be a list")
    identities: set[tuple[str, str, str]] = set()
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("rules"), list):
            raise ValueError("RLS disposition entries require a rules list")
        if entry.get("disposition") not in {"accepted-with-expiry", "false-positive-with-proof"}:
            raise ValueError("RLS disposition kind is unknown")
        if not str(entry.get("proof", "")).strip():
            raise ValueError("RLS disposition proof is required")
        for rule in entry["rules"]:
            identity = (str(entry.get("role")), str(entry.get("table")), str(rule))
            if rule not in RLS_RULES or identity in identities:
                raise ValueError("RLS disposition rule is unknown or duplicated")
            identities.add(identity)
        if entry["disposition"] == "accepted-with-expiry":
            expires = datetime.fromisoformat(str(entry.get("expiresAt", "")).replace("Z", "+00:00"))
            if expires.tzinfo is None:
                raise ValueError("accepted-with-expiry requires a timezone-aware expiry")


def evaluate_rls(report: dict[str, Any], allowlist: dict[str, Any], now: datetime) -> Verdict:
    if _files(report.get("toolFiles")) != _files(RLS_FILES):
        return Verdict.INVALID_RUN
    if report.get("baselineDispositions") != allowlist.get("rlsAcceptedDispositions"):
        return Verdict.INVALID_RUN
    for entry in allowlist["rlsAcceptedDispositions"]:
        if entry["disposition"] == "accepted-with-expiry":
            expires = datetime.fromisoformat(str(entry["expiresAt"]).replace("Z", "+00:00"))
            if expires <= now:
                return Verdict.MEASURED_FAIL
    exit_code, violations = report.get("exitCode"), report.get("violations")
    if exit_code in (2, 3):
        return Verdict.NOT_OBSERVED
    if exit_code not in (0, 1) or not isinstance(violations, list):
        return Verdict.INVALID_RUN
    if exit_code == 0:
        return Verdict.MEASURED_PASS if not violations else Verdict.INVALID_RUN
    if not violations:
        return Verdict.INVALID_RUN
    unresolved = False
    for violation in violations:
        if not isinstance(violation, dict) or violation.get("rule") not in RLS_RULES:
            return Verdict.INVALID_RUN
        disposition = _accepted_disposition(violation, allowlist, now)
        if disposition is Verdict.INVALID_RUN:
            return Verdict.INVALID_RUN
        if disposition is Verdict.MEASURED_FAIL:
            return Verdict.MEASURED_FAIL
        if disposition is None:
            unresolved = True
    return Verdict.MEASURED_FAIL if unresolved else Verdict.MEASURED_PASS


def evaluate_vf(report: dict[str, Any], allowlist: dict[str, Any]) -> Verdict:
    spec = allowlist.get("secVf001")
    if not isinstance(spec, dict):
        return Verdict.INVALID_RUN
    expected_files = [spec.get("runner"), spec.get("workflow"), spec.get("nodeDependencyResolver")]
    expected_files.extend(spec.get("testFiles", []))
    if _files(report.get("toolFiles")) != _files(expected_files):
        return Verdict.INVALID_RUN
    if sorted(report.get("nodeIds", [])) != sorted(spec.get("requiredNodeIds", [])):
        return Verdict.INVALID_RUN
    exit_code = report.get("exitCode")
    if exit_code == 0:
        return Verdict.MEASURED_PASS
    if exit_code == 1:
        return Verdict.MEASURED_FAIL
    if exit_code == 2:
        return Verdict.NOT_OBSERVED
    return Verdict.INVALID_RUN


def _security_observations(
    envelope: dict[str, Any], allowlist: dict[str, Any], now: datetime, git: GitReader, source: str
) -> Verdict:
    reports = envelope.get("observations")
    if not isinstance(reports, list) or not reports:
        raise ValueError("security observations must be a non-empty list")
    by_id: dict[str, dict[str, Any]] = {}
    for report in reports:
        if not isinstance(report, dict) or report.get("threatId") in by_id:
            raise ValueError("security threat IDs must be unique")
        by_id[report.get("threatId")] = report
    expected = {"SEC-DEF-001", "SEC-RLS-001", "SEC-VF-001"}
    if set(by_id) - expected:
        raise ValueError("unregistered security threat ID")
    if set(by_id) != expected:
        return Verdict.NOT_OBSERVED
    for report in by_id.values():
        for item in _files(report.get("toolFiles")):
            if git.blob(source, item["path"]) != item["blob"]:
                return Verdict.INVALID_RUN
    verdicts = [
        evaluate_definer(by_id["SEC-DEF-001"]),
        evaluate_rls(by_id["SEC-RLS-001"], allowlist, now),
        evaluate_vf(by_id["SEC-VF-001"], allowlist),
    ]
    if Verdict.INVALID_RUN in verdicts:
        return Verdict.INVALID_RUN
    if Verdict.MEASURED_FAIL in verdicts:
        return Verdict.MEASURED_FAIL
    if Verdict.NOT_OBSERVED in verdicts:
        return Verdict.NOT_OBSERVED
    return Verdict.MEASURED_PASS


def evaluate_axis(envelope: dict[str, Any], git: GitReader, allowlist: dict[str, Any], now: datetime) -> AxisResult:
    axis = str(envelope.get("axis", ""))
    if axis not in REQUIRED_AXES:
        return AxisResult(axis or "<missing>", Verdict.INVALID_RUN, ("unknown axis",))
    if envelope.get("schemaVersion") != SCHEMA_VERSION:
        return AxisResult(axis, Verdict.NOT_OBSERVED, ("pre-schema evidence is reference-only",), True)
    try:
        producer, criteria, source = _validate_common(envelope, git, now)
        cleanup = envelope["cleanup"]
        if cleanup["residueCount"] > 0:
            recomputed = Verdict.MEASURED_FAIL
        elif axis == "security-critical-high-zero":
            if criteria is None:
                raise ValueError("security targetRef is required")
            recomputed = _security_observations(envelope, allowlist, now, git, source)
        elif envelope.get("observations"):
            if criteria is None:
                recomputed = Verdict.NOT_REGISTERED
            else:
                recomputed = _generic_observations(envelope, criteria)
        elif producer is Verdict.BLOCKED_EXTERNAL and str(envelope.get("blocker", "")).strip():
            recomputed = Verdict.BLOCKED_EXTERNAL
        elif producer is Verdict.NOT_OBSERVED and str(envelope.get("reason", "")).strip():
            recomputed = Verdict.NOT_OBSERVED
        elif producer is Verdict.NOT_REGISTERED and criteria is None:
            recomputed = Verdict.NOT_REGISTERED
        elif producer is Verdict.NOT_APPLICABLE:
            exception = envelope.get("structuralException")
            if axis != "migration-reversible-segment" or exception != {
                "reason": "no-reversible-tail", "reversibleTailCount": 0
            }:
                raise ValueError("NOT_APPLICABLE lacks the sole approved structural proof")
            recomputed = Verdict.NOT_APPLICABLE
        else:
            raise ValueError("empty observations have no fail-closed classification")
        if producer is Verdict.MEASURED_PASS and recomputed is not Verdict.MEASURED_PASS:
            raise ValueError("producer MEASURED_PASS contradicts recomputed evidence")
        return AxisResult(axis, recomputed, ())
    except (KeyError, TypeError, ValueError) as exc:
        return AxisResult(axis, Verdict.INVALID_RUN, (str(exc),))


def aggregate(manifest: dict[str, Any], git: GitReader, allowlist: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    invalid_top = []
    try:
        validate_allowlist(allowlist)
    except (KeyError, TypeError, ValueError) as exc:
        invalid_top.append(str(exc))
    if manifest.get("schemaVersion") != SCHEMA_VERSION:
        invalid_top.append("unknown release manifest schemaVersion")
    if manifest.get("runPurpose") != RUN_PURPOSE:
        invalid_top.append("unknown release manifest runPurpose")
    rows = manifest.get("axes")
    if not isinstance(rows, list):
        invalid_top.append("axes must be a list")
        rows = []
    results = [evaluate_axis(row, git, allowlist, now) for row in rows if isinstance(row, dict)]
    names = [result.axis for result in results]
    if len(names) != len(set(names)):
        invalid_top.append("duplicate required axis")
    missing = sorted(set(REQUIRED_AXES) - set(names))
    if missing:
        invalid_top.append("missing required axes: " + ", ".join(missing))
    if len(results) != len(rows):
        invalid_top.append("axis entries must be objects")
    if invalid_top:
        overall = Verdict.INVALID_RUN
    elif any(result.verdict is Verdict.INVALID_RUN for result in results):
        overall = Verdict.INVALID_RUN
    elif any(result.verdict is Verdict.MEASURED_FAIL for result in results):
        overall = Verdict.MEASURED_FAIL
    elif all(result.verdict is Verdict.MEASURED_PASS for result in results):
        overall = Verdict.MEASURED_PASS
    else:
        overall = Verdict.NOT_OBSERVED
    done = overall is Verdict.MEASURED_PASS and len(results) == len(REQUIRED_AXES)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "designHead": DESIGN_HEAD,
        "verdict": overall.value,
        "done": done,
        "reasons": invalid_top,
        "axes": [result.json() for result in results],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--allowlist", type=Path, default=DEFAULT_ALLOWLIST)
    parser.add_argument("--repo", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        allowlist = json.loads(args.allowlist.read_text(encoding="utf-8"))
        result = aggregate(manifest, RepositoryGit(args.repo), allowlist)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        result = {
            "schemaVersion": SCHEMA_VERSION,
            "designHead": DESIGN_HEAD,
            "verdict": Verdict.INVALID_RUN.value,
            "done": False,
            "reasons": [str(exc)],
            "axes": [],
        }
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    if result["done"]:
        return 0
    return 2 if result["verdict"] == Verdict.INVALID_RUN.value else 1


if __name__ == "__main__":
    raise SystemExit(main())
