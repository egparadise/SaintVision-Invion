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
import ast
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
TARGET_REGISTRY_PATH = "docs/vault/30_Development/Evidence/s11-ac11-target-registry-v0.json"
ALLOWLIST_BLOB = "ff2f9966956da677ebcdee92ec1de2292bd5ec52"
ALLOWLIST_CANONICAL_SHA256 = "b73aba8ff97443bbd1e314d5ca0375fdcbce8205a1a746bc5a73759a04083707"
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
    def show(self, commit: str, path: str) -> str: ...
    def list_paths(self, commit: str, prefix: str) -> list[str]: ...


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

    def show(self, commit: str, path: str) -> str:
        return self._run("show", f"{commit}:{path}")

    def list_paths(self, commit: str, prefix: str) -> list[str]:
        output = self._run("ls-tree", "-r", "--name-only", commit, "--", prefix)
        return [line for line in output.splitlines() if line]


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


def _load_json_from_git(git: GitReader, commit: str, path: str, label: str) -> dict[str, Any]:
    try:
        value = json.loads(git.show(commit, path))
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError(f"{label} is not valid JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _validate_target(target: Any, axis: str, source: str, git: GitReader) -> dict[str, Any]:
    if not isinstance(target, dict):
        raise ValueError("targetRef is required")
    required = {"commit", "path", "blob", "targetId", "criteria"}
    if set(target) != required:
        raise ValueError("targetRef requires exact commit/path/blob/targetId/criteria keys")
    commit, path, blob = str(target["commit"]), str(target["path"]), str(target["blob"])
    if path != TARGET_REGISTRY_PATH:
        raise ValueError("targetRef path is not the AC-11 target registry")
    if not SHA1_RE.fullmatch(commit) or not SHA1_RE.fullmatch(blob):
        raise ValueError("targetRef contains an invalid commit, path or blob")
    if not git.is_ancestor(commit, source):
        raise ValueError("targetRef commit is not an ancestor of sourceHeadSha")
    if git.blob(commit, path) != blob or git.blob(source, path) != blob:
        raise ValueError("targetRef blob is not identical in target and source trees")
    registry = _load_json_from_git(git, commit, path, "target registry")
    if registry.get("schemaVersion") != SCHEMA_VERSION or not isinstance(registry.get("targets"), list):
        raise ValueError("target registry schema is unknown")
    target_id = target["targetId"]
    matches = [row for row in registry["targets"] if isinstance(row, dict) and row.get("targetId") == target_id]
    if len(matches) != 1:
        raise ValueError("targetId is absent or duplicated in target registry")
    registered = matches[0]
    if set(registered) != {"targetId", "axis", "sourceDocument", "criteria"} or registered["axis"] != axis:
        raise ValueError("target registry entry does not bind the requested axis")
    source_document = registered["sourceDocument"]
    if not isinstance(source_document, dict) or set(source_document) != {"commit", "path", "blob"}:
        raise ValueError("target sourceDocument is malformed")
    doc_commit = str(source_document["commit"])
    doc_path = str(source_document["path"])
    doc_blob = str(source_document["blob"])
    if not SHA1_RE.fullmatch(doc_commit) or not SHA1_RE.fullmatch(doc_blob) or not doc_path:
        raise ValueError("target sourceDocument contains invalid provenance")
    if not git.is_ancestor(doc_commit, source):
        raise ValueError("target source document is not an ancestor of sourceHeadSha")
    if git.blob(doc_commit, doc_path) != doc_blob or git.blob(source, doc_path) != doc_blob:
        raise ValueError("target source document blob is not identical in source tree")
    if not isinstance(registered["criteria"], dict) or not isinstance(target["criteria"], dict):
        raise ValueError("targetRef criteria must be an object")
    if target["criteria"] != registered["criteria"]:
        raise ValueError("targetRef criteria differ from the registered Git target")
    return registered["criteria"]


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
    criteria = None if target is None else _validate_target(target, str(envelope.get("axis", "")), source, git)
    return producer, criteria, source


def _generic_observations(envelope: dict[str, Any], criteria: dict[str, Any]) -> Verdict:
    observations = envelope.get("observations")
    if not isinstance(observations, list) or not observations:
        raise ValueError("observations must be a non-empty list")
    failed = False
    skipped = False
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
        skipped = skipped or skip > 0
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
    if skipped:
        return Verdict.NOT_OBSERVED
    return Verdict.MEASURED_FAIL if failed else Verdict.MEASURED_PASS


def _migration_reversible_tail(git: GitReader, source: str) -> tuple[str, int]:
    """Read the migration graph from sourceHeadSha and return (head, reversible tail size)."""
    paths = sorted(path for path in git.list_paths(source, "migrations/versions") if path.endswith(".py"))
    if not paths:
        raise ValueError("sourceHeadSha has no migration graph")
    revisions: dict[str, tuple[tuple[str, ...], bool]] = {}
    for path in paths:
        try:
            tree = ast.parse(git.show(source, path))
            assignments: dict[str, Any] = {}
            downgrade: ast.FunctionDef | None = None
            for node in tree.body:
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id in {"revision", "down_revision"}:
                            assignments[target.id] = ast.literal_eval(node.value)
                elif isinstance(node, ast.FunctionDef) and node.name == "downgrade":
                    downgrade = node
            if set(assignments) != {"revision", "down_revision"}:
                raise ValueError("revision declarations missing")
            revision = assignments["revision"]
            down = assignments["down_revision"]
            if not isinstance(revision, str) or revision in revisions:
                raise ValueError("duplicate or invalid revision")
            parents = () if down is None else (down,) if isinstance(down, str) else tuple(down)
            if not parents and down is not None or any(not isinstance(item, str) for item in parents):
                raise ValueError("invalid down_revision")
            if downgrade is None:
                irreversible = True
            else:
                body = [
                    node for node in downgrade.body
                    if not (isinstance(node, ast.Expr) and isinstance(getattr(node, "value", None), ast.Constant))
                ]
                # A no-op ``pass`` is not an approved irreversible declaration. Treat
                # it as a reversible tail candidate so a structural N/A cannot hide
                # the stage-2 negative fixture that must reject no-op downgrades.
                irreversible = len(body) == 1 and isinstance(body[0], ast.Raise)
            revisions[revision] = (parents, irreversible or len(parents) > 1)
        except (SyntaxError, ValueError, TypeError) as exc:
            raise ValueError(f"invalid migration graph entry: {path}") from exc
    referenced = {parent for parents, _ in revisions.values() for parent in parents}
    if referenced - revisions.keys():
        raise ValueError("migration graph has an unknown parent")
    roots = [revision for revision, (parents, _) in revisions.items() if not parents]
    heads = set(revisions) - referenced
    if len(roots) != 1 or len(heads) != 1:
        raise ValueError("migration graph must have one root and one head")
    ordered: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(revision: str) -> None:
        if revision in visiting:
            raise ValueError("migration graph contains a cycle")
        if revision in visited:
            return
        visiting.add(revision)
        for parent in sorted(revisions[revision][0]):
            visit(parent)
        visiting.remove(revision)
        visited.add(revision)
        ordered.append(revision)

    head = next(iter(heads))
    visit(head)
    if len(visited) != len(revisions):
        raise ValueError("migration graph contains unreachable revisions")
    last_irreversible = max(
        (index for index, revision in enumerate(ordered) if revisions[revision][1]),
        default=-1,
    )
    return head, len(ordered) - last_irreversible - 1


def evaluate_definer(report: dict[str, Any], allowlist: dict[str, Any]) -> Verdict:
    if _files(report.get("toolFiles")) != _files(DEFINER_FILES):
        return Verdict.INVALID_RUN
    exit_code = report.get("exitCode")
    if exit_code == 2:
        return Verdict.NOT_OBSERVED if report.get("status") == "unavailable" else Verdict.INVALID_RUN
    findings = report.get("functions")
    if exit_code not in (0, 1) or not isinstance(findings, list):
        return Verdict.INVALID_RUN
    expected = set(allowlist.get("definerPolicySignatures", []))
    if len(expected) != 12:
        return Verdict.INVALID_RUN
    seen: set[str] = set()
    problems: list[str] = []
    for finding in findings:
        if (
            not isinstance(finding, dict)
            or not isinstance(finding.get("function"), str)
            or finding["function"] in seen
            or not isinstance(finding.get("problems"), list)
        ):
            return Verdict.INVALID_RUN
        seen.add(finding["function"])
        problems.extend(finding["problems"])
    if not expected.issubset(seen):
        return Verdict.INVALID_RUN
    if any(problem not in DEFINER_KNOWN for problem in problems):
        return Verdict.INVALID_RUN
    unsafe = report.get("unsafe")
    if isinstance(unsafe, bool) or not isinstance(unsafe, int) or unsafe != sum(bool(row["problems"]) for row in findings):
        return Verdict.INVALID_RUN
    if exit_code == 0:
        return (
            Verdict.MEASURED_PASS
            if report.get("status") == "matches_reviewed_policy" and unsafe == 0 and seen == expected
            else Verdict.INVALID_RUN
        )
    if not problems:
        return Verdict.INVALID_RUN
    if report.get("status") != "requires_review":
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
    canonical = json.dumps(allowlist, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if hashlib.sha256(canonical).hexdigest() != ALLOWLIST_CANONICAL_SHA256:
        raise ValueError("security allowlist does not match the reviewed content")
    if not isinstance(allowlist, dict) or set(allowlist) != {
        "schemaVersion", "verifiedAt", "definerPolicySignatures", "secVf001", "rlsAcceptedDispositions"
    }:
        raise ValueError("security allowlist requires the exact v0 top-level fields")
    if allowlist["schemaVersion"] != SCHEMA_VERSION:
        raise ValueError("security allowlist schemaVersion is unknown")
    verified = datetime.fromisoformat(str(allowlist["verifiedAt"]).replace("Z", "+00:00"))
    if verified.tzinfo is None:
        raise ValueError("security allowlist verifiedAt must include a timezone")
    signatures = allowlist["definerPolicySignatures"]
    if (
        not isinstance(signatures, list)
        or len(signatures) != 12
        or len(set(signatures)) != len(signatures)
        or any(not isinstance(item, str) or not item for item in signatures)
    ):
        raise ValueError("definerPolicySignatures must contain 12 unique signatures")
    vf = allowlist["secVf001"]
    vf_keys = {
        "runner", "workflow", "nodeDependencyResolver", "testFiles", "requiredNodeIds",
        "requiredCaseIdentitiesSha256", "expectedTests",
    }
    if not isinstance(vf, dict) or set(vf) != vf_keys:
        raise ValueError("secVf001 structure is not the reviewed v0 shape")
    _files([vf["runner"], vf["workflow"], vf["nodeDependencyResolver"], *vf["testFiles"]])
    if (
        not isinstance(vf["requiredNodeIds"], list)
        or len(vf["requiredNodeIds"]) != 5
        or len(set(vf["requiredNodeIds"])) != 5
        or not SHA256_RE.fullmatch(str(vf["requiredCaseIdentitiesSha256"]))
        or vf["expectedTests"] != {"failure": 0, "error": 0, "skipped": 0, "passed": 6}
    ):
        raise ValueError("secVf001 node and case inventory is malformed")
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
    baseline = report.get("baselineAccepted")
    if not isinstance(baseline, list):
        return Verdict.INVALID_RUN
    expected_baseline = {
        (entry["role"], entry["table"], tuple(sorted(entry["rules"])))
        for entry in allowlist["rlsAcceptedDispositions"]
    }
    observed_baseline = {
        (entry.get("role"), entry.get("table"), tuple(sorted(entry.get("rules", []))))
        for entry in baseline if isinstance(entry, dict)
    }
    if observed_baseline != expected_baseline or len(observed_baseline) != len(baseline):
        return Verdict.INVALID_RUN
    for entry in allowlist["rlsAcceptedDispositions"]:
        if entry["disposition"] == "accepted-with-expiry":
            expires = datetime.fromisoformat(str(entry["expiresAt"]).replace("Z", "+00:00"))
            if expires <= now:
                return Verdict.MEASURED_FAIL
    exit_code = report.get("exitCode")
    if exit_code == 2:
        return Verdict.NOT_OBSERVED
    violations = report.get("violations")
    accepted = report.get("accepted")
    unmeasured = report.get("unmeasured")
    roles = report.get("roles")
    ground_truth = report.get("ground_truth")
    if (
        exit_code not in (0, 1, 3)
        or not all(isinstance(value, list) for value in (violations, accepted, unmeasured))
        or not isinstance(roles, dict) or not roles
        or not isinstance(ground_truth, dict) or not ground_truth
    ):
        return Verdict.INVALID_RUN
    for row in [*violations, *accepted, *unmeasured]:
        if not isinstance(row, dict) or row.get("rule") not in RLS_RULES:
            return Verdict.INVALID_RUN
    allowed_identities = {
        (entry["role"], entry["table"], rule)
        for entry in allowlist["rlsAcceptedDispositions"] for rule in entry["rules"]
    }
    if any((row.get("role"), row.get("table"), row.get("rule")) not in allowed_identities for row in accepted):
        return Verdict.INVALID_RUN
    if exit_code == 0:
        return Verdict.MEASURED_PASS if report.get("verdict") == "PASS" and not violations and not unmeasured else Verdict.INVALID_RUN
    if exit_code == 1:
        return Verdict.MEASURED_FAIL if report.get("verdict") == "VIOLATIONS" and violations else Verdict.INVALID_RUN
    return Verdict.NOT_OBSERVED if report.get("verdict") == "UNMEASURED" and unmeasured and not violations else Verdict.INVALID_RUN


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
        return (
            Verdict.MEASURED_PASS
            if report.get("subprocessExitCode") == 0
            and report.get("evidenceStatus") == "complete"
            and report.get("caseIdentitiesSha256") == spec["requiredCaseIdentitiesSha256"]
            and report.get("tests") == spec["expectedTests"]
            else Verdict.INVALID_RUN
        )
    if exit_code in (1, 124):
        return Verdict.MEASURED_FAIL
    if exit_code in (2, 125):
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
        evaluate_definer(by_id["SEC-DEF-001"], allowlist),
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
            _, tail_count = _migration_reversible_tail(git, source)
            if tail_count != 0:
                raise ValueError("sourceHeadSha migration graph has a reversible tail")
            recomputed = Verdict.NOT_APPLICABLE
        else:
            raise ValueError("empty observations have no fail-closed classification")
        if producer is not recomputed:
            raise ValueError("producer verdict contradicts recomputed evidence")
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
    else:
        by_axis = {result.axis: result for result in results}
        reversible = by_axis.get("migration-reversible-segment")
        restore = by_axis.get("irreversible-restore-forward")
        conditional_reversible = (
            reversible is not None
            and reversible.verdict is Verdict.NOT_APPLICABLE
            and restore is not None
            and restore.verdict is Verdict.MEASURED_PASS
        )
        required_pass = all(
            result.verdict is Verdict.MEASURED_PASS
            for result in results
            if result.axis != "migration-reversible-segment"
        )
        all_pass = all(result.verdict is Verdict.MEASURED_PASS for result in results)
        if all_pass or (conditional_reversible and required_pass):
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
        allowlist_bytes = args.allowlist.read_bytes()
        actual_blob = hashlib.sha1(f"blob {len(allowlist_bytes)}\0".encode() + allowlist_bytes).hexdigest()
        if actual_blob != ALLOWLIST_BLOB:
            raise ValueError("security allowlist file does not match the reviewed Git blob")
        allowlist = json.loads(allowlist_bytes.decode("utf-8"))
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
