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
import functools
import hashlib
import json
import math
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Protocol


ROOT = Path(__file__).resolve().parents[1]
ALLOWLIST_REPO_PATH = "docs/vault/30_Development/Evidence/s11-security-allowlist-v0.json"
DEFAULT_ALLOWLIST = (
    ROOT / ALLOWLIST_REPO_PATH
)
TARGET_REGISTRY_PATH = "docs/vault/30_Development/Evidence/s11-ac11-target-registry-v0.json"
TARGET_REGISTRY_BLOB = "eeb43dc262f5de1816237ef85fc902cdca4ab6fd"
ALLOWLIST_BLOB = "ff2f9966956da677ebcdee92ec1de2292bd5ec52"
ALLOWLIST_CANONICAL_SHA256 = "b73aba8ff97443bbd1e314d5ca0375fdcbce8205a1a746bc5a73759a04083707"
SCAN_ALLOWLIST_REPO_PATH = (
    "docs/vault/30_Development/Evidence/s11-security-dependency-sast-allowlist-v1.json"
)
SCAN_ALLOWLIST_BLOB = "629e276a3de5579ead86856fb9c6d55d43aa6071"
#: The importer that may write this axis's envelopes, pinned by path here and by blob in
#: the reviewed allowlist above (#313 F-R3).
SECURITY_IMPORTER_REPO_PATH = "tools/import_ac11_security_scan.py"
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

REQUIRED_TARGET_BY_AXIS = {
    "actual-pitr-rpo-rto-retention": "s11-st-actual-pitr-archive-failure-v0",
    "long-soak": "s11-ac11-composite-long-soak-v0",
    "accessibility-e2e": "s11-accessibility-user-device-v1",
}

SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
KNOWN_OPERATORS = {"lt", "lte", "eq", "gte", "gt"}
SCAN_FRESHNESS = timedelta(days=30)
PIN_RE = re.compile(r"^([A-Za-z0-9_.-]+)(?:\[[^\]]+\])?==([^\s;]+)$")

DEFINER_FILES = [
    {"path": "tools/check_definer_functions.py", "blob": "5831f8d8806900146add2e5e7b51b934dced3952"},
    {"path": "tools/definer-policy.json", "blob": "e16ee086d5ba301d45fec4f8fac6a5333ae1a39a"},
]
RLS_FILES = [
    {"path": "tools/collect_rls_evidence.py", "blob": "684e0f4896202e112a70798ea8c01a545ffd3896"},
    {"path": "tools/rls-boundary-baseline.json", "blob": "5f6eb104fa6ca455de78423a6f678fd8fc99d6df"},
]

#: E4 may fall back to an owner-verified readable key only for these (role, table, columns)
#: triples, and the collector's own copy (``OWNER_VERIFIED_KEY_SCOPE`` in
#: tools/collect_rls_evidence.py, whose blob is pinned above) must agree.  The check below is
#: independent on purpose: a report is evidence about a tree, not a promise from the tool that
#: wrote it, so the evaluator refuses an out-of-scope or vacuous readable-key identity even if
#: some collector offered one (#322 r2).
OWNER_VERIFIED_KEY_METHOD = "owner-verified-key"
MD5_RE = re.compile(r"^[0-9a-f]{32}$")
OWNER_VERIFIED_KEY_SCOPE = frozenset(
    {("inv_cancel_bridge_owner", "public.audit_events", ("tenant_id", "event_id"))}
)

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


def _timezone_aware(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an RFC3339 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} is not RFC3339") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone")
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


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


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


def _validate_target(
    target: Any, axis: str, source: str, git: GitReader
) -> tuple[dict[str, Any], dict[str, Any]]:
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
    if blob != TARGET_REGISTRY_BLOB:
        raise ValueError("target registry blob is not the reviewed registry")
    if not git.is_ancestor(commit, source):
        raise ValueError("targetRef commit is not an ancestor of sourceHeadSha")
    if git.blob(commit, path) != blob or git.blob(source, path) != blob:
        raise ValueError("targetRef blob is not identical in target and source trees")
    registry = _load_json_from_git(git, commit, path, "target registry")
    if registry.get("schemaVersion") != SCHEMA_VERSION or not isinstance(registry.get("targets"), list):
        raise ValueError("target registry schema is unknown")
    target_id = target["targetId"]
    required_target_id = REQUIRED_TARGET_BY_AXIS.get(axis)
    if required_target_id is not None and target_id != required_target_id:
        raise ValueError("targetId is not the required target for axis")
    matches = [row for row in registry["targets"] if isinstance(row, dict) and row.get("targetId") == target_id]
    if len(matches) != 1:
        raise ValueError("targetId is absent or duplicated in target registry")
    registered = matches[0]
    if set(registered) != {
        "targetId", "axis", "sourceDocument", "criteria", "requiredEnvironment"
    } or registered["axis"] != axis:
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
    required_environment = registered["requiredEnvironment"]
    if not isinstance(required_environment, dict) or not required_environment:
        raise ValueError("target requiredEnvironment must be a non-empty object")
    return registered["criteria"], required_environment


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
    if target is None:
        criteria = None
    else:
        criteria, required_environment = _validate_target(
            target, str(envelope.get("axis", "")), source, git
        )
        for name, expected in required_environment.items():
            if name not in environment or environment[name] != expected:
                raise ValueError(f"environment does not satisfy registered requirement: {name}")
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
        if operator == "eq" and float(target) == 0.0 and float(value) != float(failure):
            raise ValueError("zero-expected count value must equal failureCount")
        failed = failed or not _compare(float(value), operator, float(target))
    if set(criteria) != metrics:
        raise ValueError("target criteria and observation metrics must match exactly")
    if skipped:
        return Verdict.NOT_OBSERVED
    return Verdict.MEASURED_FAIL if failed else Verdict.MEASURED_PASS


def _migration_reversible_segment(git: GitReader, source: str) -> tuple[str, str, int]:
    """Return (head, last irreversible barrier or ``base``, reversible tail size)."""
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
    barrier = ordered[last_irreversible] if last_irreversible >= 0 else "base"
    return head, barrier, len(ordered) - last_irreversible - 1


def _migration_reversible_tail(git: GitReader, source: str) -> tuple[str, int]:
    """Backward-compatible head/tail view used by structural N/A validation."""

    head, _barrier, tail = _migration_reversible_segment(git, source)
    return head, tail


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


#: The RLS report's shape, pinned here because four findings in a row (#322 r2 F-R1, F-R3,
#: F-R4, F-R5) came from reading a field that was missing, wrongly typed or quietly defaulted.
#: The evaluator now validates this exact shape **before** deriving anything: a missing key, an
#: extra key, a wrong type or a negative count is INVALID_RUN, never a zero.
#:
#: The role population is the collector's own ``DEFAULT_ROLES``; dropping a role would shrink the
#: population a verdict is about, so all of them must be present and measured.  Changing either
#: list is a reviewed change: this file pins the collector's blob in ``RLS_FILES``.
RLS_REQUIRED_ROLES = frozenset({
    "inv_app", "inv_kernel", "inv_runtime_dev", "inv_discovery_issuer",
    "inv_discovery_issuer_guard", "inv_audit_writer", "inv_audit_reader",
    "inv_cancel_bridge_owner",
})
#: The one measured role that may be reported absent, and why: ``inv_runtime_dev`` is a
#: developer login no migration creates (measured on the hosted producer's disposable database,
#: where it is absent while the other seven exist).  A role that does not exist cannot bypass
#: RLS, so its absence is a fact rather than a gap -- but it is pinned here, because
#: ``present: false`` on any of the other seven would shrink the population a verdict covers.
RLS_OPTIONAL_ROLES = frozenset({"inv_runtime_dev"})
RLS_ROLE_KEYS = frozenset({
    "present", "superuser", "bypassrls", "login", "inherit", "member_of", "tables", "functions",
})
RLS_TABLE_KEYS = frozenset({
    "tenant_scoped", "rls_enabled", "rls_forced", "privileges", "policies",
})
RLS_PRIVILEGE_KEYS = frozenset({"select", "insert", "update", "delete"})
RLS_PRIVILEGE_VALUES = frozenset({"table", "column", None})
#: Cells every readable table carries, and the two more a tenant-scoped one carries.
RLS_BASE_CELLS = frozenset({"guc_unset", "guc_tenant_a", "guc_unknown_tenant", "guc_not_uuid"})
RLS_SCOPED_CELLS = frozenset({"guc_tenant_a_foreign_rows", "identity"})
RLS_IDENTITY_METHOD_KEYS = {
    "ctid": frozenset({"method", "owner_a", "role_a", "match"}),
    "pk": frozenset({"method", "columns", "owner_a", "role_a", "match"}),
    OWNER_VERIFIED_KEY_METHOD: frozenset(
        {"method", "columns", "ownerDistinctness", "owner_a", "role_a", "match"}
    ),
    "unverifiable": frozenset({"method", "reason"}),
}
RLS_GROUND_TRUTH_KEYS = frozenset({"total", "tenant_a", "other_tenants"})
#: The report's own top-level keys, measured from the producer's output.  An extra key is a
#: refusal: it is either a field this evaluator does not understand or a field someone added to
#: carry a claim nothing checks (#322 r2 F-R6).
RLS_REPORT_KEYS = frozenset({
    "threatId", "sourceRunId", "sourceHeadSha", "checkoutTreeSha", "cleanCheckout",
    "reportAvailable", "runPurpose", "schemaVersion", "startedAt", "finishedAt",
    "toolFiles", "baselineAccepted", "exitCode", "verdict", "violations", "accepted",
    "unmeasured", "measuredRoles", "roles", "table_census", "ground_truth",
})
#: The reviewed table population.  Without it the measured population was whatever the report
#: carried, so deleting a table together with its truth row and its baseline rows left a
#: self-consistent report and a MEASURED_PASS over a smaller database (#322 r2 F-R7).  A migration
#: that adds or removes a table in ``inv``/``public`` makes this stale: regenerate with
#: ``tools/collect_rls_evidence.py --disposable`` and repin the blob in the same reviewed change.
RLS_CENSUS_REPO_PATH = "tools/rls-table-census.json"
RLS_CENSUS_BLOB = "c3db5f3edd2a12f1973aef1819dbfadaab0dec41"
#: Tables that must appear in the measured set, derived from the pinned readable-key scope (the
#: reviewed allowlist's own tables are anchored separately, because ``baselineAccepted`` has to
#: match it exactly and every table it names has to be measured).  An independent anchor against
#: a report that simply measures fewer tables -- see ``rls_report_shape`` for what that does and
#: does not close.
RLS_ANCHOR_TABLES = frozenset(table for _role, table, _columns in OWNER_VERIFIED_KEY_SCOPE)


def _rls_count_cell_schema() -> dict[str, Any]:
    """A measured count or a recorded denial, and nothing else."""

    return {
        "oneOf": [
            {
                "type": "object", "additionalProperties": False,
                "required": ["rows"],
                "properties": {"rows": {"type": "integer", "minimum": 0}},
            },
            {
                "type": "object", "additionalProperties": False,
                "required": ["denied"],
                "properties": {"denied": {"type": "string", "minLength": 1}},
            },
        ]
    }


def _rls_identity_schema() -> dict[str, Any]:
    side = {
        "type": "object", "additionalProperties": False, "required": ["rows", "fp"],
        "properties": {
            "rows": {"type": "integer", "minimum": 0},
            "fp": {"type": "string", "pattern": "^[0-9a-f]{32}$"},
        },
    }
    columns = {"type": "array", "minItems": 1, "uniqueItems": True,
               "items": {"type": "string", "minLength": 1}}
    counted = {
        "type": "object", "additionalProperties": False,
        "required": ["rows", "distinct", "nullRows"],
        "properties": {name: {"type": "integer", "minimum": 0}
                       for name in ("rows", "distinct", "nullRows")},
    }
    return {
        "oneOf": [
            {
                "type": "object", "additionalProperties": False,
                "required": ["method", "owner_a", "role_a", "match"],
                "properties": {"method": {"const": "ctid"}, "owner_a": side, "role_a": side,
                               "match": {"type": "boolean"}},
            },
            {
                "type": "object", "additionalProperties": False,
                "required": ["method", "columns", "owner_a", "role_a", "match"],
                "properties": {"method": {"const": "pk"}, "columns": columns, "owner_a": side,
                               "role_a": side, "match": {"type": "boolean"}},
            },
            {
                "type": "object", "additionalProperties": False,
                "required": ["method", "columns", "ownerDistinctness", "owner_a", "role_a",
                             "match"],
                "properties": {"method": {"const": OWNER_VERIFIED_KEY_METHOD},
                               "columns": columns, "ownerDistinctness": counted,
                               "owner_a": side, "role_a": side, "match": {"type": "boolean"}},
            },
            {
                "type": "object", "additionalProperties": False,
                "required": ["method", "reason"],
                "properties": {"method": {"const": "unverifiable"},
                               "reason": {"type": "string", "minLength": 1}},
            },
        ]
    }


def _rls_table_schema() -> dict[str, Any]:
    cell = _rls_count_cell_schema()
    base_cells = {name: cell for name in sorted(RLS_BASE_CELLS)}
    scoped_cells = {**base_cells, "guc_tenant_a_foreign_rows": cell,
                    "identity": _rls_identity_schema()}
    return {
        "type": "object", "additionalProperties": False,
        "required": sorted(RLS_TABLE_KEYS),
        "properties": {
            "tenant_scoped": {"type": "boolean"},
            "rls_enabled": {"type": "boolean"},
            "rls_forced": {"type": "boolean"},
            "privileges": {
                "type": "object", "additionalProperties": False,
                "required": sorted(RLS_PRIVILEGE_KEYS),
                "properties": {name: {"enum": ["table", "column", None]}
                               for name in sorted(RLS_PRIVILEGE_KEYS)},
            },
            "policies": {
                "type": "array", "uniqueItems": True,
                "items": {
                    "type": "object", "additionalProperties": False,
                    "required": ["name", "cmd", "permissive", "roles", "using", "with_check"],
                    "properties": {
                        "name": {"type": "string", "minLength": 1},
                        "cmd": {"type": "string", "minLength": 1},
                        "permissive": {"type": "string", "minLength": 1},
                        "roles": {"type": "array", "items": {"type": "string"},
                                  "uniqueItems": True},
                        "using": {"type": "boolean"},
                        "with_check": {"type": "boolean"},
                    },
                },
            },
            "visible": {"type": "object"},
        },
        "allOf": [
            # A readable table carries its probe and an unreadable one does not: the two halves
            # of one fact, so neither may appear without the other (#322 r2 F-R6).
            {
                "if": {"properties": {"privileges": {"properties": {"select": {"type": "null"}}}}},
                "then": {"not": {"required": ["visible"]}},
                "else": {"required": ["visible"]},
            },
            # Which cells a probe carries follows from whether the table has a tenant column.
            {
                "if": {"required": ["visible"], "properties": {"tenant_scoped": {"const": True}}},
                "then": {"properties": {"visible": {
                    "type": "object", "additionalProperties": False,
                    "required": sorted(scoped_cells), "properties": scoped_cells,
                }}},
            },
            {
                "if": {"required": ["visible"], "properties": {"tenant_scoped": {"const": False}}},
                "then": {"properties": {"visible": {
                    "type": "object", "additionalProperties": False,
                    "required": sorted(base_cells), "properties": base_cells,
                }}},
            },
        ],
    }


@functools.lru_cache(maxsize=1)
def rls_report_schema() -> dict[str, Any]:
    """The RLS report's exact shape, declared rather than hand-walked.

    Cached because a hosted report carries a thousand table objects and the validator is called
    per report; building the document each time was measurable in the suite.

    ``additionalProperties: false`` everywhere and ``uniqueItems`` on the role list are the two
    things F-R6 asked for: four of the five findings on this PR were the evaluator reading a
    field that was missing, mistyped or quietly defaulted, and the fifth was the shape being
    checked for *absence* only -- an extra key, a duplicate entry or a ghost row still passed.
    """

    role_present = {
        "type": "object", "additionalProperties": False, "required": sorted(RLS_ROLE_KEYS),
        "properties": {
            "present": {"const": True},
            "superuser": {"type": "boolean"},
            "bypassrls": {"type": "boolean"},
            "login": {"type": "boolean"},
            "inherit": {"type": "boolean"},
            "member_of": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
            "functions": {
                "type": "object",
                "additionalProperties": {
                    "type": "object", "additionalProperties": False, "required": ["execute"],
                    "properties": {"execute": {"type": "boolean"}},
                },
            },
            "tables": {"type": "object", "minProperties": 1,
                       "additionalProperties": _rls_table_schema()},
        },
    }
    role_absent = {
        "type": "object", "additionalProperties": False, "required": ["present"],
        "properties": {"present": {"const": False}},
    }
    # The rows the collector writes: a rule plus where it was observed, and nothing else.  The
    # optional members are what each rule actually carries (E1 has no table, E6 names a function,
    # an accepted row carries its reviewed reason), and an extra key is refused (#322 r2 F-R6).
    rule_row = {
        "type": "object", "additionalProperties": False, "required": ["rule"],
        "properties": {
            "rule": {"enum": sorted(RLS_RULES)},
            "role": {"type": "string", "minLength": 1},
            "table": {"type": "string", "minLength": 1},
            "function": {"type": "string", "minLength": 1},
            "detail": {"type": "string"},
            "reason": {"type": "string"},
            "since": {"type": "string"},
        },
    }
    truth = {
        "oneOf": [
            {"type": "object", "additionalProperties": False,
             "required": sorted(RLS_GROUND_TRUTH_KEYS),
             "properties": {name: _rls_count_cell_schema()
                            for name in sorted(RLS_GROUND_TRUTH_KEYS)}},
            {"type": "object", "additionalProperties": False, "required": ["total"],
             "properties": {"total": _rls_count_cell_schema()}},
        ]
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": sorted(RLS_REPORT_KEYS),
        "properties": {
            "threatId": {"const": "SEC-RLS-001"},
            "sourceRunId": {"type": "string", "pattern": "^[0-9]+$"},
            "sourceHeadSha": {"type": "string", "pattern": "^[0-9a-f]{40}$"},
            "checkoutTreeSha": {"type": "string", "pattern": "^[0-9a-f]{40}$"},
            "cleanCheckout": {"type": "boolean"},
            "reportAvailable": {"type": "boolean"},
            "runPurpose": {"type": "string", "minLength": 1},
            "schemaVersion": {"type": "string", "minLength": 1},
            "startedAt": {"type": "string", "minLength": 1},
            "finishedAt": {"type": "string", "minLength": 1},
            "exitCode": {"enum": [0, 1, 2, 3]},
            "verdict": {"enum": ["PASS", "VIOLATIONS", "UNMEASURED"]},
            "toolFiles": {
                "type": "array", "minItems": 1, "uniqueItems": True,
                "items": {
                    "type": "object", "additionalProperties": False,
                    "required": ["path", "blob"],
                    "properties": {"path": {"type": "string", "minLength": 1},
                                   "blob": {"type": "string", "pattern": "^[0-9a-f]{40}$"}},
                },
            },
            "baselineAccepted": {
                "type": "array", "uniqueItems": True,
                "items": {
                    "type": "object", "additionalProperties": False,
                    "required": ["role", "table", "rules"],
                    "properties": {
                        "role": {"type": "string", "minLength": 1},
                        "table": {"type": "string", "minLength": 1},
                        "rules": {"type": "array", "minItems": 1, "uniqueItems": True,
                                  "items": {"enum": sorted(RLS_RULES)}},
                    },
                },
            },
            "violations": {"type": "array", "uniqueItems": True, "items": rule_row},
            "accepted": {"type": "array", "uniqueItems": True, "items": rule_row},
            "unmeasured": {"type": "array", "uniqueItems": True, "items": rule_row},
            "measuredRoles": {
                "type": "array", "uniqueItems": True,
                "minItems": len(RLS_REQUIRED_ROLES), "maxItems": len(RLS_REQUIRED_ROLES),
                "items": {"enum": sorted(RLS_REQUIRED_ROLES)},
            },
            "roles": {
                "type": "object", "additionalProperties": False,
                "required": sorted(RLS_REQUIRED_ROLES),
                "properties": {
                    name: ({"oneOf": [role_present, role_absent]}
                           if name in RLS_OPTIONAL_ROLES else role_present)
                    for name in sorted(RLS_REQUIRED_ROLES)
                },
            },
            "table_census": {
                "type": "object", "additionalProperties": False,
                "required": ["schemas", "count", "sha256", "tables"],
                "properties": {
                    "schemas": {"type": "array", "minItems": 1, "uniqueItems": True,
                                "items": {"type": "string", "minLength": 1}},
                    "count": {"type": "integer", "minimum": 1},
                    "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                    "tables": {"type": "array", "minItems": 1, "uniqueItems": True,
                               "items": {"type": "string", "minLength": 1}},
                },
            },
            "ground_truth": {"type": "object", "minProperties": 1,
                             "additionalProperties": truth},
        },
    }


def _rls_census_digest(tables) -> str:
    """The digest both the reviewed file and the report state over their sorted names."""

    return hashlib.sha256(chr(10).join(sorted(tables)).encode("utf-8")).hexdigest()


@functools.lru_cache(maxsize=1)
def rls_table_census() -> frozenset[str] | None:
    """The reviewed table population, or None when the file is missing or not the reviewed one.

    Verified by blob, like every other reviewed sidecar in this chain, and re-derived from its own
    contents: the file states a count and a digest over its sorted names, and both are recomputed
    here so the file cannot disagree with itself either.
    """

    path = ROOT / RLS_CENSUS_REPO_PATH
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    blob = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
    if blob != RLS_CENSUS_BLOB:
        return None
    try:
        document = json.loads(raw.decode("utf-8"))
        tables = document["tables"]
        if (
            not isinstance(tables, list)
            or len(tables) != len(set(tables))
            or document["count"] != len(tables)
            or document["sha256"] != _rls_census_digest(tables)
        ):
            return None
    except (UnicodeError, json.JSONDecodeError, KeyError, TypeError):
        return None
    return frozenset(tables)


@functools.lru_cache(maxsize=1)
def _rls_validator():
    """One compiled validator, because compiling it per report was the whole cost.

    ``jsonschema.validate`` rebuilds the validator on every call, and this schema describes a
    thousand table objects through ``if``/``then`` and ``oneOf``; the suite measured the
    difference in minutes.
    """

    try:
        import jsonschema
    except ImportError:  # pragma: no cover - requirements-core pins jsonschema for both lanes
        return None
    return jsonschema.Draft202012Validator(rls_report_schema())


def rls_report_shape(report: Any) -> str | None:
    """The exact shape the RLS evaluator requires, or the first reason it is refused.

    Two halves, because neither alone is enough:

    * the declared schema (``rls_report_schema``) -- ``additionalProperties: false`` at every
      level and ``uniqueItems`` on the lists, so a **missing**, **extra**, **mistyped**,
      **negative** or **duplicated** field is refused rather than defaulted;
    * the correspondences a schema cannot state, because they relate one part of the report to
      another: the measured table set is the same for every role present, ``ground_truth`` covers
      exactly that set (no ghost rows, no gaps), each truth row has the shape its table's tenant
      column implies, every row the report judges names something it measured, and the tables the
      reviewed allowlist anchors on are among them.

    What this still does not close, stated rather than implied: the evaluator cannot know how
    many tables the migrated database has, so a report that drops a table **together with** its
    ground-truth row and its rows in every list is internally consistent and is accepted.  The
    anchors below catch that for the tables the reviewed allowlist names; closing it in general
    needs the expected table set to come from the reviewed source, which is an AC-11 definition
    change and is not made here (#322 r2 F-R6).
    """

    if not isinstance(report, dict):
        return "the report must be an object"
    validator = _rls_validator()
    if validator is None:  # pragma: no cover - requirements-core pins jsonschema for both lanes
        return "jsonschema is unavailable, so the report's shape cannot be checked"
    error = next(iter(validator.iter_errors(report)), None)
    if error is not None:
        where = "/".join(str(part) for part in error.absolute_path) or "<root>"
        return f"{where}: {error.message}"

    roles: dict[str, Any] = report["roles"]
    ground_truth: dict[str, Any] = report["ground_truth"]
    if set(report["measuredRoles"]) != set(roles):
        return "measuredRoles must name exactly the measured population"

    # The population a verdict covers comes from the reviewed census, not from the report.
    reviewed = rls_table_census()
    if reviewed is None:
        return f"{RLS_CENSUS_REPO_PATH} is missing, unpinned or inconsistent with itself"
    census = report["table_census"]
    observed = set(census["tables"])
    if census["count"] != len(census["tables"]):
        return "table_census.count does not match the names it lists"
    if census["sha256"] != _rls_census_digest(census["tables"]):
        return "table_census.sha256 does not cover the names it lists"
    if observed != reviewed:
        unexpected = sorted(observed - reviewed)
        absent = sorted(reviewed - observed)
        return (f"the collector's catalogue census does not match the reviewed population "
                f"(unreviewed {unexpected[:3]}, missing {absent[:3]})")

    measured: set[str] | None = None
    scoped: set[str] = set()
    for role_name, role_report in roles.items():
        if role_report.get("present") is False:
            continue
        tables = set(role_report["tables"])
        if measured is None:
            measured = tables
        elif tables != measured:
            missing = sorted(measured - tables)
            extra = sorted(tables - measured)
            return (f"roles[{role_name}] measures a different table set than the others "
                    f"(missing {missing[:3]}, extra {extra[:3]})")
        for table_name, table in role_report["tables"].items():
            if table["tenant_scoped"]:
                scoped.add(table_name)
    if not measured:
        return "no role measured any table"
    if measured != reviewed:
        unexpected = sorted(measured - reviewed)
        absent = sorted(reviewed - measured)
        return (f"the measured tables are not the reviewed population "
                f"(unreviewed {unexpected[:3]}, missing {absent[:3]})")
    if set(ground_truth) != measured:
        ghosts = sorted(set(ground_truth) - measured)
        gaps = sorted(measured - set(ground_truth))
        return (f"ground_truth does not correspond to the measured tables "
                f"(truth for unmeasured {ghosts[:3]}, no truth for {gaps[:3]})")
    for table_name, truth in ground_truth.items():
        expected = RLS_GROUND_TRUTH_KEYS if table_name in scoped else frozenset({"total"})
        if set(truth) != expected:
            return (f"ground_truth[{table_name}] carries {sorted(truth)}, but that table is "
                    f"{'tenant-scoped' if table_name in scoped else 'not tenant-scoped'}")
    missing_anchors = sorted(RLS_ANCHOR_TABLES - measured)
    if missing_anchors:
        return f"the reviewed allowlist anchors on {missing_anchors}, which this report omits"
    for field in ("violations", "accepted", "unmeasured"):
        for row in report[field]:
            role_name, table_name = row.get("role"), row.get("table")
            if row["rule"] == "E6":
                continue  # a definer-function row: SEC-DEF-001's territory, not measured here
            if role_name not in roles or roles[role_name].get("present") is not True:
                return f"{field} names {role_name}, which this report does not measure"
            if row["rule"] == "E1":
                continue  # role-scoped rule, no table
            if table_name not in roles[role_name]["tables"]:
                return f"{field} names {role_name}/{table_name}, which this report does not measure"
    for row in report["baselineAccepted"]:
        if not isinstance(row, dict):
            return "baselineAccepted rows must be objects"
        if row.get("table") not in measured:
            return f"baselineAccepted names {row.get('table')}, which this report does not measure"
    return None


#: E1..E5 are re-derived from the observations the RLS report carries.  E6 is about SECURITY
#: DEFINER functions, which this report does not observe (SEC-DEF-001 does), so an E6 row is
#: carried as reported and left out of the comparison -- stated rather than silently ignored.
RLS_RECOMPUTED_RULES = ("E1", "E2", "E3", "E4", "E5")


def _rls_recomputation(
    roles: dict[str, Any], ground_truth: dict[str, Any]
) -> tuple[set[tuple[str, str, str | None]], set[tuple[str, str, str | None]]] | None:
    """Re-derive (violations, unmeasured) from the recorded observations, or None to refuse.

    Three findings in a row (#322 r2 F-R1, F-R3, F-R4) were the same shape: the evaluator read
    one field of the report and trusted the conclusion beside it.  This function stops reading
    conclusions.  It applies E1..E5 to the rows, counts and fingerprints the report carries, in
    the collector's own precedence, and the caller compares the result with what the report
    claims -- so a forged report has to forge an observation that produces its own verdict, and
    every number it carries is then cross-checked by that derivation.

    None means the report does not carry enough observation to be checked, which is a refusal:
    a report that omits what it concluded from cannot be evidence about a tree.
    """

    violations: set[tuple[str, str, str | None]] = set()
    unmeasured: set[tuple[str, str, str | None]] = set()
    for role_name, role_report in roles.items():
        if not isinstance(role_report, dict):
            return None
        if role_report.get("present") is not True:
            continue
        for field in ("superuser", "bypassrls"):
            if not isinstance(role_report.get(field), bool):
                return None
        if role_report["superuser"] or role_report["bypassrls"]:
            violations.add(("E1", role_name, None))
        tables = role_report.get("tables")
        if not isinstance(tables, dict):
            return None
        for table_name, table_report in tables.items():
            if not isinstance(table_report, dict):
                return None
            privileges = table_report.get("privileges")
            if not isinstance(privileges, dict) or "select" not in privileges:
                return None
            if table_report.get("tenant_scoped") is not True or privileges["select"] is None:
                continue
            for field in ("rls_enabled", "rls_forced"):
                if not isinstance(table_report.get(field), bool):
                    return None
            visible = table_report.get("visible")
            if not isinstance(visible, dict):
                return None
            if not (table_report["rls_enabled"] and table_report["rls_forced"]):
                violations.add(("E2", role_name, table_name))

            def cell(name: str) -> int | None:
                value = visible.get(name)
                if value is None:
                    return 0
                if not isinstance(value, dict):
                    return None
                if "denied" in value:
                    return 0
                rows = value.get("rows")
                return rows if isinstance(rows, int) and not isinstance(rows, bool) else None

            unset, foreign, unknown = cell("guc_unset"), cell("guc_tenant_a_foreign_rows"), cell("guc_unknown_tenant")
            if unset is None or foreign is None or unknown is None:
                return None
            if unset > 0:
                violations.add(("E3", role_name, table_name))
            identity = visible.get("identity")
            if identity is not None and not isinstance(identity, dict):
                return None
            seen_a = (visible.get("guc_tenant_a") or {}).get("rows")
            truth_a = ((ground_truth.get(table_name) or {}).get("tenant_a") or {}).get("rows")
            if foreign > 0:
                violations.add(("E4", role_name, table_name))
            elif identity is not None and identity.get("match") is False:
                violations.add(("E4", role_name, table_name))
            elif (
                identity is None
                and isinstance(seen_a, int)
                and isinstance(truth_a, int)
                and seen_a > truth_a
            ):
                violations.add(("E4", role_name, table_name))
            if unknown > 0:
                violations.add(("E5", role_name, table_name))
            if isinstance(identity, dict) and identity.get("method") == "unverifiable":
                unmeasured.add(("E4", role_name, table_name))
    return violations, unmeasured


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
    identity_mismatches: list[tuple[str, str]] = []
    for role_name, role_report in roles.items():
        tables = role_report.get("tables") if isinstance(role_report, dict) else None
        if not isinstance(tables, dict):
            continue
        for table_name, table_report in tables.items():
            visible = table_report.get("visible") if isinstance(table_report, dict) else None
            identity = visible.get("identity") if isinstance(visible, dict) else None
            if not isinstance(identity, dict):
                continue
            if identity.get("method") != OWNER_VERIFIED_KEY_METHOD:
                continue
            columns = identity.get("columns")
            measured = identity.get("ownerDistinctness")
            if (
                not isinstance(columns, list)
                or (role_name, table_name, tuple(columns)) not in OWNER_VERIFIED_KEY_SCOPE
                or not isinstance(measured, dict)
                or not isinstance(measured.get("rows"), int)
                or measured["rows"] < 1
                or measured.get("distinct") != measured["rows"]
                or measured.get("nullRows") != 0
            ):
                # An unregistered pair, an empty comparison (every projection is injective and
                # every fingerprint matches over zero rows), a repeated key or a NULL-bearing
                # key: none of these is a row identity, so the report is not admissible.
                return Verdict.INVALID_RUN
            # ``match`` is a conclusion, so it is recomputed here from the two fingerprints the
            # report carries, and the owner side has to be the same observation the distinctness
            # was measured on.  Trusting the field let a report state a conclusion its own
            # numbers contradict -- a synthesised PASS with ``match: false``, or an owner
            # observation of zero rows beside a distinctness claiming two (#322 r2 F-R3).
            owner, role_side = identity.get("owner_a"), identity.get("role_a")
            if (
                not isinstance(owner, dict)
                or not isinstance(role_side, dict)
                or owner.get("rows") != measured["rows"]
                or not isinstance(role_side.get("rows"), int)
                or not MD5_RE.fullmatch(str(owner.get("fp")))
                or not MD5_RE.fullmatch(str(role_side.get("fp")))
                or identity.get("match") is not (owner["fp"] == role_side["fp"])
            ):
                return Verdict.INVALID_RUN
            if identity["match"] is True and role_side["rows"] != owner["rows"]:
                # Equal fingerprints over a different number of rows is impossible: the
                # fingerprint is taken over the row set.  Requiring it here forces
                # ``role_a.rows == owner_a.rows == ownerDistinctness.rows`` for every claimed
                # match, which a synthesised report had been able to contradict (#322 r2 F-R4).
                return Verdict.INVALID_RUN
            if identity["match"] is not True:
                # The role saw a different row set.  That is an E4 violation, so a report that
                # calls itself a pass is inconsistent with its own observation.
                identity_mismatches.append((role_name, table_name))
    # Shape first, numbers second: nothing below may read a field this did not check.
    if rls_report_shape(report) is not None:
        return Verdict.INVALID_RUN
    recomputed = _rls_recomputation(roles, ground_truth)
    if recomputed is None:
        return Verdict.INVALID_RUN
    derived_violations, derived_unmeasured = recomputed

    def rows_of(entries: list[Any]) -> set[tuple[str, str, str | None]]:
        return {
            (str(row.get("rule")), str(row.get("role")), row.get("table"))
            for row in entries
            if isinstance(row, dict) and row.get("rule") in RLS_RECOMPUTED_RULES
        }

    reported_violations, reported_unmeasured = rows_of(violations), rows_of(unmeasured)
    reported_accepted = rows_of(accepted)
    # Neither direction may drift: a row the observations do not produce was invented, and a row
    # they do produce that the report does not list (nor accept with a reviewed reason) was
    # hidden.  ``accepted`` may hold either kind, so it counts for both.
    if (
        not reported_violations <= derived_violations
        or not derived_violations <= reported_violations | reported_accepted
        or not reported_unmeasured <= derived_unmeasured
        or not derived_unmeasured <= reported_unmeasured | reported_accepted
        or not reported_accepted <= derived_violations | derived_unmeasured
    ):
        return Verdict.INVALID_RUN
    allowed_identities = {
        (entry["role"], entry["table"], rule)
        for entry in allowlist["rlsAcceptedDispositions"] for rule in entry["rules"]
    }
    if any((row.get("role"), row.get("table"), row.get("rule")) not in allowed_identities for row in accepted):
        return Verdict.INVALID_RUN
    if exit_code == 0:
        if identity_mismatches:
            return Verdict.INVALID_RUN
        return Verdict.MEASURED_PASS if report.get("verdict") == "PASS" and not violations and not unmeasured else Verdict.INVALID_RUN
    if exit_code == 1:
        return Verdict.MEASURED_FAIL if report.get("verdict") == "VIOLATIONS" and violations else Verdict.INVALID_RUN
    if identity_mismatches:
        # A recomputed mismatch is a measured violation, not something an UNMEASURED report may
        # carry quietly: that report would be read as "nothing was observed to be wrong".
        return Verdict.INVALID_RUN
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


def validate_scan_allowlist(value: Any) -> dict[str, Any]:
    expected = {
        "schemaVersion", "verifiedAt", "producer", "workflow", "importer",
        "scanners", "acceptedFindings"
    }
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError("dependency/SAST allowlist shape is not reviewed")
    if value["schemaVersion"] != SCHEMA_VERSION:
        raise ValueError("dependency/SAST allowlist schema is unknown")
    _timezone_aware(value["verifiedAt"], "dependency/SAST verifiedAt")
    _files([value["producer"], value["workflow"], value["importer"]])
    scanners = value["scanners"]
    if not isinstance(scanners, list) or len(scanners) != 2:
        raise ValueError("dependency/SAST scanner inventory must contain exactly two rows")
    by_id: dict[str, dict[str, Any]] = {}
    for scanner in scanners:
        if not isinstance(scanner, dict) or set(scanner) != {
            "id", "version", "scopePaths", "severityPolicy"
        }:
            raise ValueError("dependency/SAST scanner row is malformed")
        scanner_id = scanner["id"]
        if scanner_id not in {"bandit", "pip-audit"} or scanner_id in by_id:
            raise ValueError("dependency/SAST scanner ID is unknown or duplicated")
        scope = scanner["scopePaths"]
        if (
            not isinstance(scanner["version"], str)
            or not scanner["version"]
            or not isinstance(scope, list)
            or not scope
            or len(scope) != len(set(scope))
            or any(not isinstance(path, str) or not path for path in scope)
        ):
            raise ValueError("dependency/SAST scanner version or scope is malformed")
        policy = "HIGH_ONLY" if scanner_id == "bandit" else "ANY_VULNERABILITY_AS_HIGH"
        if scanner["severityPolicy"] != policy:
            raise ValueError("dependency/SAST severity policy is not fail-closed")
        by_id[scanner_id] = scanner
    entries = value["acceptedFindings"]
    if not isinstance(entries, list):
        raise ValueError("dependency/SAST acceptedFindings must be a list")
    identities: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {
            "findingId", "severity", "reason", "expiresAt"
        }:
            raise ValueError("dependency/SAST accepted finding is malformed")
        finding_id = entry["findingId"]
        if not isinstance(finding_id, str) or not finding_id or finding_id in identities:
            raise ValueError("dependency/SAST accepted finding ID is empty or duplicated")
        identities.add(finding_id)
        if entry["severity"] not in {"CRITICAL", "HIGH"}:
            raise ValueError("dependency/SAST accepted finding severity is unknown")
        if not isinstance(entry["reason"], str) or not entry["reason"].strip():
            raise ValueError("dependency/SAST accepted finding reason is required")
        _timezone_aware(entry["expiresAt"], "dependency/SAST accepted finding expiry")
    return value


def _canonical_package(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _registered_pins(content: str) -> dict[str, str]:
    pins: dict[str, str] = {}
    for raw in content.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = PIN_RE.fullmatch(line)
        if match is None:
            raise ValueError("registered requirements contain a non-exact pin")
        name, version = _canonical_package(match.group(1)), match.group(2)
        if name in pins:
            raise ValueError("registered requirements contain a duplicate package")
        pins[name] = version
    if not pins:
        raise ValueError("registered requirements contain no exact pins")
    return pins


def evaluate_security_scan(
    report: dict[str, Any], scan_allowlist: dict[str, Any], now: datetime, git: GitReader, source: str
) -> Verdict:
    if report.get("reportAvailable") is not True or report.get("status") != "complete":
        return Verdict.NOT_OBSERVED
    payload = report.get("payload")
    payload_sha = report.get("payloadSha256")
    if not isinstance(payload, dict) or not SHA256_RE.fullmatch(str(payload_sha)):
        return Verdict.NOT_OBSERVED
    if _canonical_sha256(payload) != payload_sha:
        return Verdict.NOT_OBSERVED
    if report.get("runPurpose") != "s11-ac11-security-scan":
        return Verdict.INVALID_RUN
    if report.get("schemaVersion") != SCHEMA_VERSION or report.get("threatId") != "SEC-SCAN-001":
        return Verdict.INVALID_RUN
    source_run_id = report.get("sourceRunId")
    if not isinstance(source_run_id, str) or not source_run_id.isdigit():
        return Verdict.INVALID_RUN
    if report.get("sourceHeadSha") != source:
        return Verdict.NOT_OBSERVED
    if report.get("checkoutTreeSha") != git.tree(source) or report.get("cleanCheckout") is not True:
        return Verdict.NOT_OBSERVED
    environment = report.get("environment")
    if (
        not isinstance(environment, dict)
        or set(environment) != {
            "runnerImage", "topology", "evidenceClass", "credentialsRequired",
            "externalServicesRequired",
        }
        or not isinstance(environment["runnerImage"], str)
        or not environment["runnerImage"]
        or environment["topology"] != "hosted"
        or environment["evidenceClass"] != "security-tools-v0"
        or environment["credentialsRequired"] is not False
        or environment["externalServicesRequired"] is not True
    ):
        return Verdict.INVALID_RUN
    try:
        started = _utc(report.get("startedAt"), "security scan startedAt")
        finished = _utc(report.get("finishedAt"), "security scan finishedAt")
    except ValueError:
        return Verdict.INVALID_RUN
    if finished < started or finished > now or now - finished > SCAN_FRESHNESS:
        return Verdict.NOT_OBSERVED
    artifact = report.get("scanArtifact")
    artifact_keys = {
        "repository", "workflowPath", "runId", "artifactId", "artifactName",
        "digest", "observedDigest", "expiresAt", "runConclusion",
        "producerReportSha256", "junitSha256",
    }
    if not isinstance(artifact, dict) or set(artifact) != artifact_keys:
        return Verdict.NOT_OBSERVED
    if (
        artifact["repository"] != "egparadise/SaintVision-Invion"
        or artifact["workflowPath"] != ".github/workflows/ac11-security-scan.yml"
        or artifact["runId"] != source_run_id
        or not str(artifact["artifactId"]).isdigit()
        or artifact["artifactName"] != f"s11-ac11-security-{source}"
        or artifact["runConclusion"] != "success"
        or not SHA256_RE.fullmatch(str(artifact["digest"]))
        or artifact["observedDigest"] != artifact["digest"]
        or not SHA256_RE.fullmatch(str(artifact["producerReportSha256"]))
        or not SHA256_RE.fullmatch(str(artifact["junitSha256"]))
    ):
        return Verdict.NOT_OBSERVED
    try:
        if _utc(artifact["expiresAt"], "security scan artifact expiry") <= now:
            return Verdict.NOT_OBSERVED
    except ValueError:
        return Verdict.INVALID_RUN
    allowlist_ref = report.get("allowlist")
    if allowlist_ref != {"path": SCAN_ALLOWLIST_REPO_PATH, "blob": SCAN_ALLOWLIST_BLOB}:
        return Verdict.INVALID_RUN
    expected_files = [
        scan_allowlist["producer"], scan_allowlist["workflow"], scan_allowlist["importer"]
    ]
    if _files(report.get("toolFiles")) != _files(expected_files):
        return Verdict.INVALID_RUN
    for item in _files(expected_files):
        if git.blob(source, item["path"]) != item["blob"]:
            return Verdict.INVALID_RUN
    scanner_specs = {row["id"]: row for row in scan_allowlist["scanners"]}
    expected_versions = {key: scanner_specs[key]["version"] for key in sorted(scanner_specs)}
    if payload.get("scannerVersions") != expected_versions:
        return Verdict.INVALID_RUN
    # Everything the payload says about itself -- the finding rows, the two counts, the
    # per-scanner summaries, the two scanner exit codes and the two coverage inventories --
    # is recomputed by one function that the security importer calls as well, so the two
    # recomputations of "critical and high are zero" cannot drift (#313 r2 N1).
    actual, broken = scan_payload_invariants(payload)
    if broken:
        return Verdict.INVALID_RUN
    summaries = payload["summaries"]
    audited = payload["auditedDependencies"]
    audited_map = {row["name"]: row["version"] for row in audited}
    inputs = payload["scanInputs"]
    expected_scope = sorted(
        {path for scanner in scanner_specs.values() for path in scanner["scopePaths"]}
    )
    # Which paths had to be scanned, and whether the objects scanned are the source tree's:
    # both questions belong to the allowlist and to Git, so they stay here.
    if [str(row["path"]) for row in inputs] != expected_scope:
        return Verdict.INVALID_RUN
    if any(git.blob(source, str(row["path"])) != row["objectId"] for row in inputs):
        return Verdict.INVALID_RUN
    requirements_path = scanner_specs["pip-audit"]["scopePaths"][0]
    try:
        required_pins = _registered_pins(git.show(source, requirements_path))
    except ValueError:
        return Verdict.INVALID_RUN
    if any(audited_map.get(name) != version for name, version in required_pins.items()):
        return Verdict.INVALID_RUN
    scanned_files = payload["scannedPythonFiles"]
    expected_python_files = sorted(
        path
        for prefix in scanner_specs["bandit"]["scopePaths"]
        for path in git.list_paths(source, prefix)
        if path.endswith(".py")
    )
    if scanned_files != expected_python_files:
        return Verdict.INVALID_RUN
    accepted = {row["findingId"]: row for row in scan_allowlist["acceptedFindings"]}
    stale = sorted(set(accepted) - set(actual))
    unallowlisted = sorted(set(actual) - set(accepted))
    expired = sorted(
        finding_id
        for finding_id in set(actual) & set(accepted)
        if _timezone_aware(
            accepted[finding_id]["expiresAt"], "dependency/SAST finding expiry"
        ) <= now
    )
    severity_mismatch = sorted(
        finding_id
        for finding_id in set(actual) & set(accepted)
        if accepted[finding_id]["severity"] != actual[finding_id]["severity"]
    )
    expected_lists = {
        "unallowlistedFindingIds": unallowlisted,
        "expiredFindingIds": expired,
        "staleAllowlistFindingIds": stale,
        "severityMismatchFindingIds": severity_mismatch,
    }
    if any(payload[key] != value for key, value in expected_lists.items()):
        return Verdict.INVALID_RUN
    if stale:
        failure_class = "STALE_ALLOWLIST"
    elif severity_mismatch:
        failure_class = "ALLOWLIST_SEVERITY_MISMATCH"
    elif expired:
        failure_class = "EXPIRED_ALLOWLIST"
    elif unallowlisted:
        failure_class = "UNALLOWLISTED_CRITICAL_HIGH"
    else:
        failure_class = "NONE"
    computed = Verdict.MEASURED_PASS if failure_class == "NONE" else Verdict.MEASURED_FAIL
    if report.get("failureClass") != failure_class or report.get("verdict") != computed.value:
        return Verdict.INVALID_RUN
    return computed


#: The exact payload of a SEC-SCAN-001 report.  A key nobody validates is a measurement
#: nobody made, so the set is compared rather than sampled.
SCAN_PAYLOAD_KEYS = {
    "scannerVersions", "scannerExitCodes", "scanInputs", "summaries",
    "auditedDependencies", "scannedPythonFiles",
    "criticalHighFindings", "criticalCount", "highCount",
    "unallowlistedFindingIds", "expiredFindingIds", "staleAllowlistFindingIds",
    "severityMismatchFindingIds",
}
#: A critical/high finding row, exactly.
SCAN_FINDING_KEYS = {"findingId", "scanner", "severity", "ruleId", "component", "location"}
SCAN_SCANNER_IDS = ("bandit", "pip-audit")
SCAN_BANDIT_SEVERITY_KEYS = ("lowFindingCount", "mediumFindingCount", "highFindingCount")


def scan_payload_invariants(payload: Any) -> tuple[dict[str, dict[str, Any]], tuple[str, ...]]:
    """Recompute what a security-scan payload says about itself.

    Returns the finding rows by ID and the names of the invariants that do not hold.  An
    empty second element means the payload agrees with itself: the finding rows, the two
    counts, the per-scanner summaries, the two exit codes and the two coverage inventories
    all describe the same scan.  It does not mean the scan passed -- the allowlist comparison
    and the Git provenance are separate questions, and they stay with ``evaluate_security_scan``
    because only the aggregator can ask them.

    This exists because two validators of the same claim will drift: the importer read only
    the two counts and the four inventory lengths, so a payload with a HIGH finding row and
    ``highCount: 0``, or one whose scanners read nothing at all, recomputed MEASURED_PASS
    (#313 r2 N1).  Both callers now read these invariants instead of each keeping its own
    shorter list.
    """

    broken: list[str] = []

    def fails(name: str) -> None:
        if name not in broken:
            broken.append(name)

    if not isinstance(payload, dict) or set(payload) != SCAN_PAYLOAD_KEYS:
        return {}, ("payload-keys",)

    versions = payload["scannerVersions"]
    if not isinstance(versions, dict) or set(versions) != set(SCAN_SCANNER_IDS):
        fails("scanner-versions")
    inputs = payload["scanInputs"]
    if not isinstance(inputs, list) or not inputs:
        fails("scan-inputs")
    else:
        for row in inputs:
            if (
                not isinstance(row, dict)
                or set(row) != {"path", "objectId"}
                or not isinstance(row["path"], str)
                or not row["path"]
                or not SHA1_RE.fullmatch(str(row["objectId"]))
            ):
                fails("scan-inputs")
                break

    summaries = payload["summaries"]
    if (
        not isinstance(summaries, dict)
        or set(summaries) != set(SCAN_SCANNER_IDS)
        or set(summaries["bandit"]) != {*SCAN_BANDIT_SEVERITY_KEYS, "scannedFileCount"}
        or set(summaries["pip-audit"]) != {"dependencyCount", "findingCount"}
        or any(
            isinstance(count, bool) or not isinstance(count, int) or count < 0
            for summary in summaries.values()
            for count in summary.values()
        )
    ):
        return {}, tuple(broken + ["summaries"])

    audited = payload["auditedDependencies"]
    audited_map: dict[str, str] = {}
    if not isinstance(audited, list) or not audited:
        # A scan that audited nothing measured nothing: an empty inventory is not a pass.
        fails("audited-dependencies")
    else:
        for row in audited:
            if (
                not isinstance(row, dict)
                or set(row) != {"name", "version"}
                or not isinstance(row["name"], str)
                or not row["name"]
                or not isinstance(row["version"], str)
                or not row["version"]
                or row["name"] in audited_map
            ):
                fails("audited-dependencies")
                break
            audited_map[row["name"]] = row["version"]
        else:
            if audited != [
                {"name": name, "version": audited_map[name]} for name in sorted(audited_map)
            ]:
                fails("audited-dependencies")
    if "audited-dependencies" not in broken:
        if summaries["pip-audit"]["dependencyCount"] != len(audited):
            fails("dependency-count")

    scanned = payload["scannedPythonFiles"]
    if (
        not isinstance(scanned, list)
        or not scanned
        or scanned != sorted(scanned)
        or len(scanned) != len(set(scanned))
        or any(not isinstance(path, str) or not path.endswith(".py") for path in scanned)
    ):
        # Likewise: a bandit run over zero files is coverage nobody has.
        fails("scanned-python-files")
    elif summaries["bandit"]["scannedFileCount"] != len(scanned):
        fails("scanned-file-count")

    findings = payload["criticalHighFindings"]
    actual: dict[str, dict[str, Any]] = {}
    if not isinstance(findings, list):
        return actual, tuple(broken + ["findings"])
    for finding in findings:
        if not isinstance(finding, dict) or set(finding) != SCAN_FINDING_KEYS:
            fails("findings")
            break
        finding_id = finding["findingId"]
        if (
            not isinstance(finding_id, str)
            or not finding_id
            or finding_id in actual
            or finding["scanner"] not in SCAN_SCANNER_IDS
            or finding["severity"] not in {"CRITICAL", "HIGH"}
            or any(
                not isinstance(finding[key], str) or not finding[key]
                for key in SCAN_FINDING_KEYS - {"findingId", "scanner", "severity"}
            )
        ):
            fails("findings")
            break
        if finding["scanner"] == "pip-audit" and finding["severity"] != "HIGH":
            fails("findings")
            break
        actual[finding_id] = finding
    else:
        if findings != sorted(findings, key=lambda row: row["findingId"]):
            fails("findings")
    if "findings" in broken:
        return actual, tuple(broken)

    critical = sum(row["severity"] == "CRITICAL" for row in findings)
    high = sum(row["severity"] == "HIGH" for row in findings)
    if payload["criticalCount"] != critical or payload["highCount"] != high:
        # The counts are the axis's own claim, so they are recomputed from the rows rather
        # than believed: a row with no count is a finding the verdict never saw.
        fails("counts")
    if summaries["bandit"]["highFindingCount"] != sum(
        row["scanner"] == "bandit" for row in findings
    ) or summaries["pip-audit"]["findingCount"] != sum(
        row["scanner"] == "pip-audit" for row in findings
    ):
        fails("summary-finding-counts")

    exits = payload["scannerExitCodes"]
    bandit_total = sum(summaries["bandit"][key] for key in SCAN_BANDIT_SEVERITY_KEYS)
    expected_exits = {
        "pip-audit": 1 if summaries["pip-audit"]["findingCount"] else 0,
        "bandit": 1 if bandit_total else 0,
    }
    if not isinstance(exits, dict) or exits != expected_exits:
        fails("exit-codes")

    for key in (
        "unallowlistedFindingIds", "expiredFindingIds",
        "staleAllowlistFindingIds", "severityMismatchFindingIds",
    ):
        value = payload[key]
        if (
            not isinstance(value, list)
            or value != sorted(value)
            or len(value) != len(set(value))
            or any(not isinstance(item, str) or not item for item in value)
        ):
            fails("finding-inventories")
            break

    return actual, tuple(broken)


def _security_observations(
    envelope: dict[str, Any], allowlist: dict[str, Any], now: datetime, git: GitReader, source: str
) -> Verdict:
    reports = envelope.get("observations")
    if git.blob(source, ALLOWLIST_REPO_PATH) != ALLOWLIST_BLOB:
        return Verdict.INVALID_RUN
    # The envelope must name the importer that wrote it, bound to the source tree.  The
    # allowlist's three pins are checked below, but only once all four threat reports exist,
    # so an adapter that the run's own tree does not contain could otherwise write evidence
    # about that tree and nothing would notice (#313 F-R3).
    importer = envelope.get("importerFile")
    if (
        not isinstance(importer, dict)
        or set(importer) != {"path", "blob"}
        or importer["path"] != SECURITY_IMPORTER_REPO_PATH
        or not SHA1_RE.fullmatch(str(importer["blob"]))
        or git.blob(source, SECURITY_IMPORTER_REPO_PATH) != importer["blob"]
    ):
        return Verdict.INVALID_RUN
    if not isinstance(reports, list) or not reports:
        raise ValueError("security observations must be a non-empty list")
    by_id: dict[str, dict[str, Any]] = {}
    for report in reports:
        if not isinstance(report, dict) or report.get("threatId") in by_id:
            raise ValueError("security threat IDs must be unique")
        by_id[report.get("threatId")] = report
    expected = {"SEC-DEF-001", "SEC-RLS-001", "SEC-VF-001", "SEC-SCAN-001"}
    if set(by_id) - expected:
        raise ValueError("unregistered security threat ID")
    if set(by_id) != expected:
        return Verdict.NOT_OBSERVED
    for report in by_id.values():
        for item in _files(report.get("toolFiles")):
            if git.blob(source, item["path"]) != item["blob"]:
                return Verdict.INVALID_RUN
    if git.blob(source, SCAN_ALLOWLIST_REPO_PATH) != SCAN_ALLOWLIST_BLOB:
        return Verdict.INVALID_RUN
    try:
        scan_allowlist = validate_scan_allowlist(
            json.loads(git.show(source, SCAN_ALLOWLIST_REPO_PATH))
        )
    except (json.JSONDecodeError, TypeError, ValueError):
        return Verdict.INVALID_RUN
    verdicts = [
        evaluate_definer(by_id["SEC-DEF-001"], allowlist),
        evaluate_rls(by_id["SEC-RLS-001"], allowlist, now),
        evaluate_vf(by_id["SEC-VF-001"], allowlist),
        evaluate_security_scan(by_id["SEC-SCAN-001"], scan_allowlist, now, git, source),
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
        elif axis == "migration-reversible-segment" and envelope.get("observations"):
            head, barrier, tail_count = _migration_reversible_segment(git, source)
            if tail_count < 1 or envelope.get("reversibleSegment") != {
                "startingRevision": head,
                "endingRevision": barrier,
                "reversibleTailCount": tail_count,
            }:
                raise ValueError("reversible evidence differs from the source migration graph")
            if criteria is None:
                recomputed = Verdict.NOT_REGISTERED
            else:
                recomputed = _generic_observations(envelope, criteria)
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
    release_sha = manifest.get("releaseSha")
    if not isinstance(release_sha, str) or not SHA1_RE.fullmatch(release_sha):
        invalid_top.append("releaseSha must be a full Git SHA")
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
    if isinstance(release_sha, str) and SHA1_RE.fullmatch(release_sha):
        mismatched = sorted(
            str(row.get("axis", "<missing>"))
            for row in rows
            if isinstance(row, dict) and row.get("sourceHeadSha") != release_sha
        )
        if mismatched:
            invalid_top.append(
                "axis sourceHeadSha differs from releaseSha: " + ", ".join(mismatched)
            )
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
