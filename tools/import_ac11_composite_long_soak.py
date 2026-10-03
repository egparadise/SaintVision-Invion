"""Import the AC-11 physical composite long-soak report, fail closed.

This PG-free importer does not execute a soak.  Before the operator supplies
both G-19 and G-24 it emits BLOCKED_EXTERNAL; an unregistered target emits
NOT_REGISTERED.  A measured envelope is produced only after exact case,
fault-class, child-reference, topology, Git, and target-registry checks pass.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "1.0.0"
#: The AC-11 axes this importer writes envelopes for, as string literals at module
#: level. The contract is read by tools/assemble_ac11_manifest.py with ``ast``, so the
#: axis map's claim is checked against this declaration rather than against a string
#: search over this file -- a search answers "is the name written anywhere", which a
#: comment satisfies and a constant reference defeats (#299 r3).
EMITTED_AXES: tuple[str, ...] = (
    "long-soak",
)
#: One source for the name: the envelope's axis is the axis this importer declares.
AXIS = EMITTED_AXES[0]
TARGET_ID = "s11-ac11-composite-long-soak-v0"
DRY_RUN_PURPOSE = "s11-ac11-composite-long-soak-dry-run"
REGISTRY_PATH = "docs/vault/30_Development/Evidence/s11-ac11-target-registry-v0.json"
REGISTRY_BLOB = "ef956db6ef0a68f93ba80e8ce0c8fa9571dc8fbe"
CASE_IDENTITIES_SHA256 = "d4638030330f8c2ba857e63976cc050bf2d631491d59472fab225142eccd49c3"
FAULT_CLASSES_SHA256 = "62aa166b06ac2b91adef51b5af10d2d2939da5e8a9e008e2a4104b8865cfd27b"
STORAGE_PHYSICAL_SHA256 = "f6fef83126954555b004e2ca48a34fb81fdb0bbca57b4f8147f402dcef4f90ec"
HOSTED_STORAGE_SHA256 = "0509d94a6648106868ef1ec602af2bed5bbd02b17cec3a4c5ffbf6178ef24a33"
REQUIRED_RESOURCES = frozenset({"G-19", "G-24"})
SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

CASE_IDENTITIES = (
    "HOSTED-DRIFT-01/storage/reference-only",
    "NTP-01/ubuntu-worker/source-loss",
    "NTP-02/ubuntu-worker/resync",
    "POWER-01/ubuntu-worker/controlled-source-loss",
    "POWER-02/control-plane/controlled-source-loss-external-observer",
    "STORAGE-01/eligible-four/physical-reference",
    "SWITCH-01/ubuntu-worker/uplink-loss",
    "SWITCH-02/control-plane/uplink-loss-external-observer",
    "THERM-01/eligible-four/steady-load",
    "TOP-01/all-five/registration-mtls-heartbeat",
    "WAN-01/remote-operator/path-loss",
    "WAN-02/remote-operator/latency-loss",
    "WS-01/ubuntu-workers/steady-bidirectional",
    "WS-02/ubuntu-worker/reconnect-after-wan-loss",
)
FAULT_CLASSES = (
    "CLOCK_SKEW_EXCEEDED", "CLOCK_SYNC_UNAVAILABLE", "COMMITTED_DATA_LOSS",
    "IDENTITY_DRIFT", "POWER_RECOVERY_TIMEOUT", "POWER_UNEXPECTED_LOSS",
    "PROCESS_RESTART_UNEXPECTED", "STORAGE_REFERENCE_FAILED",
    "SWITCH_PATH_UNAVAILABLE", "SWITCH_RECOVERY_TIMEOUT", "TELEMETRY_GAP",
    "THERMAL_CRITICAL", "THERMAL_THROTTLE", "UNCLASSIFIED",
    "WAN_PATH_UNAVAILABLE", "WAN_RECOVERY_TIMEOUT", "WS_CONNECT_FAILED",
    "WS_FRAME_MISMATCH", "WS_RECONNECT_TIMEOUT", "WS_REPLAY_ACCEPTED",
)
ALLOWED_FAULT_CLASSES_BY_PREFIX = {
    "HOSTED-DRIFT-01": {"STORAGE_REFERENCE_FAILED"},
    "NTP-01": {"CLOCK_SKEW_EXCEEDED", "CLOCK_SYNC_UNAVAILABLE", "TELEMETRY_GAP"},
    "NTP-02": {"CLOCK_SKEW_EXCEEDED", "CLOCK_SYNC_UNAVAILABLE", "TELEMETRY_GAP"},
    "POWER-01": {"POWER_RECOVERY_TIMEOUT", "POWER_UNEXPECTED_LOSS", "IDENTITY_DRIFT", "COMMITTED_DATA_LOSS", "TELEMETRY_GAP"},
    "POWER-02": {"POWER_RECOVERY_TIMEOUT", "POWER_UNEXPECTED_LOSS", "PROCESS_RESTART_UNEXPECTED", "COMMITTED_DATA_LOSS", "TELEMETRY_GAP"},
    "STORAGE-01": {"STORAGE_REFERENCE_FAILED", "COMMITTED_DATA_LOSS"},
    "SWITCH-01": {"SWITCH_PATH_UNAVAILABLE", "SWITCH_RECOVERY_TIMEOUT", "TELEMETRY_GAP"},
    "SWITCH-02": {"SWITCH_PATH_UNAVAILABLE", "SWITCH_RECOVERY_TIMEOUT", "TELEMETRY_GAP"},
    "THERM-01": {"THERMAL_CRITICAL", "THERMAL_THROTTLE", "TELEMETRY_GAP"},
    "TOP-01": {"IDENTITY_DRIFT", "TELEMETRY_GAP"},
    "WAN-01": {"WAN_PATH_UNAVAILABLE", "WAN_RECOVERY_TIMEOUT", "TELEMETRY_GAP"},
    "WAN-02": {"WAN_PATH_UNAVAILABLE", "WAN_RECOVERY_TIMEOUT", "TELEMETRY_GAP"},
    "WS-01": {"WS_CONNECT_FAILED", "WS_FRAME_MISMATCH", "WS_REPLAY_ACCEPTED", "TELEMETRY_GAP"},
    "WS-02": {"WS_CONNECT_FAILED", "WS_FRAME_MISMATCH", "WS_RECONNECT_TIMEOUT", "WS_REPLAY_ACCEPTED", "TELEMETRY_GAP"},
}


class EvidenceImportError(ValueError):
    """The report cannot be trusted as AC-11 evidence."""


class GitReader(Protocol):
    def tree(self, commit: str) -> str: ...
    def blob(self, commit: str, path: str) -> str: ...
    def show(self, commit: str, path: str) -> str: ...
    def is_ancestor(self, ancestor: str, descendant: str) -> bool: ...


class RepositoryGit:
    def _run(self, *args: str) -> str:
        completed = subprocess.run(
            ["git", *args], cwd=ROOT, text=True, capture_output=True,
            encoding="utf-8", timeout=15,
        )
        if completed.returncode:
            raise EvidenceImportError("Git provenance is unreachable")
        return completed.stdout.strip()

    def tree(self, commit: str) -> str:
        return self._run("rev-parse", f"{commit}^{{tree}}")

    def blob(self, commit: str, path: str) -> str:
        return self._run("rev-parse", f"{commit}:{path}")

    def show(self, commit: str, path: str) -> str:
        return self._run("show", f"{commit}:{path}")

    def is_ancestor(self, ancestor: str, descendant: str) -> bool:
        completed = subprocess.run(
            ["git", "merge-base", "--is-ancestor", ancestor, descendant],
            cwd=ROOT, capture_output=True, timeout=15,
        )
        return completed.returncode == 0


def _canonical_sha(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _utc(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise EvidenceImportError(f"{field} must be UTC RFC3339")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EvidenceImportError(f"{field} must be UTC RFC3339") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise EvidenceImportError(f"{field} must be UTC RFC3339")
    return parsed


def _load_target(git: GitReader, source: str) -> dict[str, Any] | None:
    if not SHA1_RE.fullmatch(source):
        raise EvidenceImportError("sourceHeadSha must be a full Git SHA")
    if git.blob(source, REGISTRY_PATH) != REGISTRY_BLOB:
        raise EvidenceImportError("source tree does not contain the reviewed registry blob")
    try:
        registry = json.loads(git.show(source, REGISTRY_PATH))
    except (TypeError, json.JSONDecodeError) as exc:
        raise EvidenceImportError("target registry is not valid JSON") from exc
    rows = registry.get("targets") if isinstance(registry, dict) else None
    if registry.get("schemaVersion") != SCHEMA_VERSION or not isinstance(rows, list):
        raise EvidenceImportError("target registry schema is unknown")
    matches = [row for row in rows if isinstance(row, dict) and row.get("targetId") == TARGET_ID]
    if not matches:
        return None
    if len(matches) != 1:
        raise EvidenceImportError("composite long-soak target is duplicated")
    target = matches[0]
    if set(target) != {"targetId", "axis", "sourceDocument", "criteria", "requiredEnvironment"}:
        raise EvidenceImportError("registered target has an unexpected shape")
    if target["axis"] != AXIS or not isinstance(target["criteria"], dict):
        raise EvidenceImportError("registered target does not bind long-soak")
    document = target["sourceDocument"]
    if not isinstance(document, dict) or set(document) != {"commit", "path", "blob"}:
        raise EvidenceImportError("registered target source document is malformed")
    if not git.is_ancestor(document["commit"], source):
        raise EvidenceImportError("target source document is not an ancestor")
    if git.blob(document["commit"], document["path"]) != document["blob"]:
        raise EvidenceImportError("target source document blob is invalid")
    if git.blob(source, document["path"]) != document["blob"]:
        raise EvidenceImportError("target source document drifted in source tree")
    return target


def readiness(source: str, operator_resources: set[str], git: GitReader) -> dict[str, Any]:
    target = _load_target(git, source)
    if target is None:
        return {"axis": AXIS, "verdict": "NOT_REGISTERED", "reason": "target is absent"}
    missing = sorted(REQUIRED_RESOURCES - operator_resources)
    if missing:
        return {
            "axis": AXIS,
            "verdict": "BLOCKED_EXTERNAL",
            "blocker": ",".join(missing),
        }
    return {"axis": AXIS, "verdict": "NOT_OBSERVED", "reason": "physical run not supplied"}


def _validate_child_references(
    report: dict[str, Any], storage: dict[str, Any], hosted: dict[str, Any], finished: datetime
) -> None:
    if report["storageReferenceSha256"] != _canonical_sha(storage):
        raise EvidenceImportError("storage reference digest does not match the physical report")
    if report["hostedReferenceSha256"] != _canonical_sha(hosted):
        raise EvidenceImportError("hosted reference digest does not match the physical report")
    storage_expected = {
        "kind": "s11-storage-physical-reference", "referenceOnly": True,
        "targetId": "s11-storage-soak-physical-reference-v0",
        "verdict": "MEASURED_PASS", "sourceHeadSha": report["sourceHeadSha"],
        "inventoryRevision": report["inventoryRevision"],
        "startedAt": report["startedAt"], "finishedAt": report["finishedAt"],
        "caseIdentitiesSha256": STORAGE_PHYSICAL_SHA256,
    }
    if any(storage.get(key) != value for key, value in storage_expected.items()):
        raise EvidenceImportError("storage physical reference is not bound to the same run window")
    if not SHA256_RE.fullmatch(str(storage.get("artifactSha256", ""))):
        raise EvidenceImportError("storage physical reference artifact digest is invalid")
    hosted_expected = {
        "kind": "s11-storage-reference-evidence", "referenceOnly": True,
        "executionLayer": "hosted-minio-postgresql", "verdict": "MEASURED_PASS",
        "sourceHeadSha": report["sourceHeadSha"],
        "caseIdentitiesSha256": HOSTED_STORAGE_SHA256, "artifactAvailable": True,
        "runConclusion": "success",
    }
    if any(hosted.get(key) != value for key, value in hosted_expected.items()):
        raise EvidenceImportError("hosted drift reference is not a passing same-source reference")
    digest = str(hosted.get("artifactSha256", ""))
    if not SHA256_RE.fullmatch(digest) or hosted.get("artifactObservedSha256") != digest:
        raise EvidenceImportError("hosted drift artifact digest is invalid")
    if _utc(hosted.get("artifactExpiresAt"), "hosted artifactExpiresAt") <= finished:
        raise EvidenceImportError("hosted drift artifact is unavailable at physical completion")


def _import_reference_only_dry_run(
    report: dict[str, Any], storage: dict[str, Any], hosted: dict[str, Any], git: GitReader
) -> dict[str, Any]:
    """Validate a synthetic traversal without turning it into acceptance evidence."""

    required_keys = {
        "schemaVersion", "runPurpose", "referenceOnly", "acceptanceClaim",
        "verdict", "sourceRunId", "sourceHeadSha", "checkoutTreeSha",
        "cleanCheckout", "generatedAt", "inventoryRevision", "environment",
        "operatorResources", "caseIdentities", "faultClasses", "cases", "casePlans",
        "execution", "cleanup", "storageReferenceSha256", "hostedReferenceSha256",
    }
    if set(report) != required_keys or report.get("schemaVersion") != SCHEMA_VERSION:
        raise EvidenceImportError("dry-run report requires the exact v1 key set")
    if (
        report.get("runPurpose") != DRY_RUN_PURPOSE
        or report.get("referenceOnly") is not True
        or report.get("acceptanceClaim") is not False
        or report.get("verdict") != "NOT_OBSERVED"
    ):
        raise EvidenceImportError("dry-run report cannot claim physical acceptance")
    if report.get("operatorResources") != []:
        raise EvidenceImportError("dry-run report cannot claim operator resources")
    if not str(report.get("sourceRunId", "")).strip():
        raise EvidenceImportError("dry-run sourceRunId is required")
    source = str(report.get("sourceHeadSha", ""))
    target = _load_target(git, source)
    if target is None:
        raise EvidenceImportError("dry-run source does not contain the registered target")
    if report.get("cleanCheckout") is not True or git.tree(source) != report.get("checkoutTreeSha"):
        raise EvidenceImportError("dry-run report is not bound to a clean source tree")
    generated = _utc(report.get("generatedAt"), "generatedAt")
    inventory_revision = report.get("inventoryRevision")
    if not isinstance(inventory_revision, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", inventory_revision):
        raise EvidenceImportError("dry-run inventory revision is invalid")
    expected_environment = {
        "topology": "synthetic-five-node",
        "registeredNodeCount": 5,
        "eligibleNodeCount": 4,
        "excludedNodeCount": 1,
        "cpIndependentWorkerHostCount": 4,
        "cpColocatedNodeCount": 1,
        "timedPopulation": "synthetic-cp-independent-four",
        "observer": "synthetic-monotonic-v1",
        "faultInjection": "synthetic-noop-v1",
        "windowClass": "dry-run",
        "comparableGroup": "reference-only",
    }
    if report.get("environment") != expected_environment:
        raise EvidenceImportError("dry-run environment is not the exact reference topology")
    if report.get("caseIdentities") != list(CASE_IDENTITIES) or _canonical_sha(report["caseIdentities"]) != CASE_IDENTITIES_SHA256:
        raise EvidenceImportError("dry-run case identities are not exact")
    if report.get("faultClasses") != list(FAULT_CLASSES) or _canonical_sha(report["faultClasses"]) != FAULT_CLASSES_SHA256:
        raise EvidenceImportError("dry-run fault-class identities are not exact")
    cases = report.get("cases")
    expected_cases = [
        {"caseIdentity": identity, "status": "DECLARED_ONLY", "faultClass": None}
        for identity in CASE_IDENTITIES
    ]
    if cases != expected_cases:
        raise EvidenceImportError("dry-run cases must traverse the exact case universe")
    plans = report.get("casePlans")
    if not isinstance(plans, list) or len(plans) != len(CASE_IDENTITIES):
        raise EvidenceImportError("dry-run case plans are incomplete")
    for identity, plan in zip(CASE_IDENTITIES, plans, strict=True):
        prefix = identity.split("/", 1)[0]
        expected_plan = {
            "caseIdentity": identity,
            "plannedPhases": [
                "preflight", "observe-baseline", "simulate-fault",
                "observe-recovery", "cleanup",
            ],
            "executedPhases": [],
            "candidateFaultClasses": sorted(ALLOWED_FAULT_CLASSES_BY_PREFIX[prefix]),
            "containerPlan": {
                "declaredTransitions": ["create", "start", "stop", "remove"],
                "executedTransitions": [],
            },
            "observed": False,
            "physicalActions": False,
        }
        if plan != expected_plan:
            raise EvidenceImportError("dry-run case plan is not exact")
    if report.get("execution") != {
        "driver": "synthetic-lan-pilot-v1",
        "mode": "plan-only",
        "planned": True,
        "simulationExecuted": False,
        "physicalActions": False,
        "declaredCaseCount": len(CASE_IDENTITIES),
        "observedCaseCount": 0,
    }:
        raise EvidenceImportError("dry-run execution receipt is invalid")
    if report.get("cleanup") != {"observed": False, "physicalResidueCount": None}:
        raise EvidenceImportError("dry-run cleanup receipt is invalid")

    if report.get("storageReferenceSha256") != _canonical_sha(storage):
        raise EvidenceImportError("dry-run storage reference digest does not match")
    storage_expected = {
        "kind": "s11-storage-physical-reference",
        "referenceOnly": True,
        "targetId": "s11-storage-soak-physical-reference-v0",
        "verdict": "NOT_OBSERVED",
        "sourceHeadSha": source,
        "inventoryRevision": inventory_revision,
        "caseIdentitiesSha256": STORAGE_PHYSICAL_SHA256,
    }
    if storage != storage_expected:
        raise EvidenceImportError("dry-run storage reference is not exact")
    if report.get("hostedReferenceSha256") != _canonical_sha(hosted):
        raise EvidenceImportError("dry-run hosted reference digest does not match")
    hosted_expected = {
        "kind": "s11-storage-reference-evidence",
        "referenceOnly": True,
        "executionLayer": "hosted-minio-postgresql",
        "verdict": "MEASURED_PASS",
        "sourceHeadSha": source,
        "caseIdentitiesSha256": HOSTED_STORAGE_SHA256,
        "artifactAvailable": True,
        "runConclusion": "success",
    }
    if any(hosted.get(key) != value for key, value in hosted_expected.items()):
        raise EvidenceImportError("dry-run hosted drift reference is not exact")
    digest = str(hosted.get("artifactSha256", ""))
    if not SHA256_RE.fullmatch(digest) or hosted.get("artifactObservedSha256") != digest:
        raise EvidenceImportError("dry-run hosted drift artifact digest is invalid")
    if _utc(hosted.get("artifactExpiresAt"), "hosted artifactExpiresAt") <= generated:
        raise EvidenceImportError("dry-run hosted drift artifact is unavailable")

    artifact = _canonical_sha(report)
    expires = (generated + timedelta(days=30)).isoformat().replace("+00:00", "Z")
    return {
        "schemaVersion": SCHEMA_VERSION,
        "runPurpose": "ac11-axis-evidence",
        "axis": AXIS,
        "referenceOnly": True,
        "acceptanceClaim": False,
        "sourceRunId": report["sourceRunId"],
        "sourceHeadSha": source,
        "checkoutTreeSha": report["checkoutTreeSha"],
        "artifactSha256": artifact,
        "artifactObservedSha256": artifact,
        "artifactAvailable": True,
        "artifactExpiresAt": expires,
        "cleanCheckout": True,
        "runConclusion": "success",
        "startedAt": report["generatedAt"],
        "finishedAt": report["generatedAt"],
        "environment": report["environment"],
        # The reference report says cleanup was not observed.  The axis
        # envelope also preserves the established aggregator field so the
        # honest classification remains NOT_OBSERVED rather than INVALID_RUN.
        "cleanup": {
            "residueCount": 0,
            "observed": False,
            "physicalResidueCount": None,
        },
        "verdict": "NOT_OBSERVED",
        "reason": "synthetic dry-run is reference-only and cannot satisfy the physical target",
    }


def _observation(metric: str, value: int | float, zero_expected: bool) -> dict[str, Any]:
    failure = int(value) if zero_expected else 0
    n = max(1, failure)
    return {
        "metric": metric, "value": value, "unit": "count", "n": n,
        "successCount": n - failure, "failureCount": failure, "skipCount": 0,
        "errorsByClass": {"observed": failure} if failure else {},
    }


def import_report(
    report: dict[str, Any], storage: dict[str, Any], hosted: dict[str, Any], git: GitReader
) -> dict[str, Any]:
    if not isinstance(report, dict):
        raise EvidenceImportError("physical report must be an object")
    if report.get("runPurpose") == DRY_RUN_PURPOSE:
        return _import_reference_only_dry_run(report, storage, hosted, git)
    resource_values = report.get("operatorResources")
    if (
        not isinstance(resource_values, list)
        or any(not isinstance(value, str) for value in resource_values)
        or len(set(resource_values)) != len(resource_values)
        or not set(resource_values).issubset(REQUIRED_RESOURCES)
    ):
        raise EvidenceImportError("operatorResources must be the unique registered G-19/G-24 identifiers")
    status = readiness(str(report.get("sourceHeadSha", "")), set(resource_values), git)
    if status["verdict"] != "NOT_OBSERVED":
        return status
    target = _load_target(git, report["sourceHeadSha"])
    assert target is not None
    required_keys = {
        "schemaVersion", "runPurpose", "sourceRunId", "sourceHeadSha", "checkoutTreeSha",
        "cleanCheckout", "startedAt", "finishedAt", "artifactSha256",
        "artifactObservedSha256", "artifactExpiresAt", "inventoryRevision", "environment",
        "operatorResources", "caseIdentities", "faultClasses", "cases", "metrics",
        "cleanup", "externalObserverReceipt", "storageReferenceSha256", "hostedReferenceSha256",
    }
    if set(report) != required_keys or report["schemaVersion"] != SCHEMA_VERSION:
        raise EvidenceImportError("physical report requires the exact v1 key set")
    if report["runPurpose"] != "s11-ac11-composite-long-soak" or not str(report["sourceRunId"]).strip():
        raise EvidenceImportError("physical run identity is invalid")
    if report["cleanCheckout"] is not True or git.tree(report["sourceHeadSha"]) != report["checkoutTreeSha"]:
        raise EvidenceImportError("physical report is not bound to a clean source tree")
    started, finished = _utc(report["startedAt"], "startedAt"), _utc(report["finishedAt"], "finishedAt")
    if finished - started < timedelta(hours=24):
        raise EvidenceImportError("physical observation window is shorter than 24 hours")
    if not SHA256_RE.fullmatch(str(report["artifactSha256"])) or report["artifactObservedSha256"] != report["artifactSha256"]:
        raise EvidenceImportError("physical artifact digest is invalid")
    if _utc(report["artifactExpiresAt"], "artifactExpiresAt") <= finished:
        raise EvidenceImportError("physical artifact is expired at completion")
    environment = report["environment"]
    required_environment = target["requiredEnvironment"]
    if not isinstance(environment, dict) or any(environment.get(k) != v for k, v in required_environment.items()):
        raise EvidenceImportError("physical environment does not satisfy the registered target")
    if not str(environment.get("comparableGroup", "")).strip():
        raise EvidenceImportError("environment comparableGroup is required")
    if report["caseIdentities"] != list(CASE_IDENTITIES) or _canonical_sha(report["caseIdentities"]) != CASE_IDENTITIES_SHA256:
        raise EvidenceImportError("physical case identities are not exact")
    if report["faultClasses"] != list(FAULT_CLASSES) or _canonical_sha(report["faultClasses"]) != FAULT_CLASSES_SHA256:
        raise EvidenceImportError("fault-class identities are not exact")
    cases = report["cases"]
    if not isinstance(cases, list) or len(cases) != len(CASE_IDENTITIES):
        raise EvidenceImportError("physical cases are missing or duplicated")
    seen: set[str] = set()
    unclassified = 0
    failed_case_count = 0
    for case in cases:
        if not isinstance(case, dict) or set(case) != {"caseIdentity", "verdict", "faultClass"}:
            raise EvidenceImportError("physical case shape is invalid")
        identity = case["caseIdentity"]
        if identity not in CASE_IDENTITIES or identity in seen or case["verdict"] not in {"PASS", "FAIL"}:
            raise EvidenceImportError("physical case identity or verdict is invalid")
        seen.add(identity)
        if case["verdict"] == "PASS" and case["faultClass"] is not None:
            raise EvidenceImportError("passing case cannot carry a fault class")
        if case["verdict"] == "FAIL" and case["faultClass"] not in FAULT_CLASSES:
            raise EvidenceImportError("failed case has an unknown fault class")
        prefix = str(identity).split("/", 1)[0]
        if (
            case["verdict"] == "FAIL"
            and case["faultClass"] != "UNCLASSIFIED"
            and case["faultClass"] not in ALLOWED_FAULT_CLASSES_BY_PREFIX[prefix]
        ):
            raise EvidenceImportError("failed case fault class does not match its identity")
        failed_case_count += int(case["verdict"] == "FAIL")
        unclassified += int(case["faultClass"] == "UNCLASSIFIED")
    if seen != set(CASE_IDENTITIES):
        raise EvidenceImportError("physical case universe is incomplete")
    receipt = report["externalObserverReceipt"]
    if not isinstance(receipt, dict) or set(receipt) != {"kind", "inventoryRevision", "coveragePpm", "redacted"}:
        raise EvidenceImportError("external observer receipt is malformed")
    if receipt != {
        "kind": "external-monotonic-v1", "inventoryRevision": report["inventoryRevision"],
        "coveragePpm": report["metrics"].get("externalObserverCoveragePpm"), "redacted": True,
    }:
        raise EvidenceImportError("external observer receipt is not bound to the report")
    cleanup = report["cleanup"]
    if not isinstance(cleanup, dict) or set(cleanup) != {"residueCount"} or type(cleanup["residueCount"]) is not int or cleanup["residueCount"] < 0:
        raise EvidenceImportError("cleanup residue receipt is invalid")
    _validate_child_references(report, storage, hosted, finished)
    criteria = target["criteria"]
    metrics = report["metrics"]
    if not isinstance(metrics, dict) or set(metrics) != set(criteria):
        raise EvidenceImportError("physical metrics do not exactly match registered criteria")
    derived = {
        "windowSeconds": int((finished - started).total_seconds()),
        "requiredCaseCount": len(CASE_IDENTITIES), "executedRequiredCaseCount": len(seen),
        "storagePhysicalReferencePassCount": 1, "hostedDriftReferencePassCount": 1,
        "hostedDriftReferenceFailureCount": 0, "classificationMismatchCount": 0,
        "unclassifiedFaultCount": unclassified, "cleanupResidueCount": cleanup["residueCount"],
    }
    if any(metrics.get(key) != value for key, value in derived.items()):
        raise EvidenceImportError("derived metrics differ from physical receipts")
    for name, value in metrics.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise EvidenceImportError(f"metric {name} is not finite numeric evidence")
    observations = [
        _observation(name, value, criteria[name] == {"operator": "eq", "value": 0})
        for name, value in metrics.items()
    ]
    failed = any(
        (rule["operator"] == "eq" and metrics[name] != rule["value"])
        or (rule["operator"] == "gte" and metrics[name] < rule["value"])
        or (rule["operator"] == "lte" and metrics[name] > rule["value"])
        for name, rule in criteria.items()
    )
    if failed_case_count and not failed:
        raise EvidenceImportError("failed physical case has no failed registered criterion")
    return {
        "schemaVersion": SCHEMA_VERSION, "runPurpose": "ac11-axis-evidence", "axis": AXIS,
        "sourceRunId": report["sourceRunId"], "sourceHeadSha": report["sourceHeadSha"],
        "checkoutTreeSha": report["checkoutTreeSha"], "artifactSha256": report["artifactSha256"],
        "artifactObservedSha256": report["artifactObservedSha256"], "artifactAvailable": True,
        "artifactExpiresAt": report["artifactExpiresAt"], "cleanCheckout": True,
        "runConclusion": "success", "startedAt": report["startedAt"], "finishedAt": report["finishedAt"],
        "environment": environment, "cleanup": cleanup, "verdict": "MEASURED_FAIL" if failed else "MEASURED_PASS",
        "targetRef": {
            "commit": report["sourceHeadSha"], "path": REGISTRY_PATH, "blob": REGISTRY_BLOB,
            "targetId": TARGET_ID, "criteria": criteria,
        },
        "observations": observations,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--storage-reference", type=Path, required=True)
    parser.add_argument("--hosted-reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = json.loads(args.report.read_text(encoding="utf-8"))
        storage = json.loads(args.storage_reference.read_text(encoding="utf-8"))
        hosted = json.loads(args.hosted_reference.read_text(encoding="utf-8"))
        output = import_report(report, storage, hosted, RepositoryGit())
    except (OSError, json.JSONDecodeError, EvidenceImportError) as exc:
        print(f"INVALID_RUN: {exc}")
        return 2
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if output["verdict"] == "MEASURED_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
