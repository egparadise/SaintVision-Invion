"""Bind a downloaded AC-11 security artifact to GitHub run metadata.

This importer is intentionally offline: callers fetch the artifact zip and
the two GitHub API JSON documents, then pass those bytes here.  The output is
the only SEC-SCAN-001 shape accepted by the AC-11 aggregator.  Metadata inputs
remain an authenticated-caller trust boundary and must be acquired from the
canonical repository with ``gh api``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Any

# The canonical recomputation of a security-scan payload lives with the aggregator, which is
# the validator the evidence has to satisfy.  Calling it here rather than keeping a shorter
# list of checks is what stops the two from drifting again (#313 r2 N1); the sibling
# migration importer reads the aggregator the same way.
from aggregate_ac11_evidence import scan_payload_invariants


#: The AC-11 axes this importer writes envelopes for, as string literals at module level
#: (#299 r3).  It was ``()`` while this importer returned the producer's report unchanged;
#: it now adapts that report into an axis envelope, which is what card 216 closes.
EMITTED_AXES: tuple[str, ...] = (
    "security-critical-high-zero",
)
#: The reviewed AC-11 target registry, pinned the same way the accessibility importer pins
#: it: the aggregator refuses a targetRef whose blob is not the reviewed one.
REGISTRY_COMMIT = "0ee9542a4f9b8c640a68545ff83a28370c94152c"
REGISTRY_PATH = "docs/vault/30_Development/Evidence/s11-ac11-target-registry-v0.json"
REGISTRY_BLOB = "eeb43dc262f5de1816237ef85fc902cdca4ab6fd"
TARGET_ID = "s11-security-critical-high-zero-v0"
#: The four threat reports the aggregator requires for this axis.  Only SEC-SCAN-001 has a
#: producer in this repository, so an envelope built from the security-scan artifact alone
#: is admissible and recomputes NOT_OBSERVED -- which is the honest answer, and a different
#: thing from the "no admissible envelope" this importer used to leave behind.
REQUIRED_THREAT_IDS = ("SEC-DEF-001", "SEC-RLS-001", "SEC-VF-001", "SEC-SCAN-001")
SCAN_THREAT_ID = "SEC-SCAN-001"
#: The one threat report this importer can recompute for itself.  The aggregator owns the
#: canonical recomputation of all four (``evaluate_definer``, ``evaluate_rls``,
#: ``evaluate_vf``, ``evaluate_security_scan``); this importer is handed one artifact, so a
#: verdict about the other three would be a verdict about measurements it has never seen.
#: Rows that merely carry a threat ID are exactly that, and r1 accepted four of them as a
#: pass (#313 F-R2), so the importer now refuses to answer instead of guessing.
RECOMPUTABLE_THREAT_IDS = (SCAN_THREAT_ID,)
#: The comparability group this importer declares for the hosted dependency/SAST lane.  The
#: aggregator requires one on every axis envelope (``aggregate_ac11_evidence.py:334``) and
#: the producer does not write one, so the adapter writes it the way the accessibility and
#: migration importers already do (``import_ac11_accessibility_evidence.py:488``,
#: ``import_ac11_migration_rehearsal.py:354``).  A name on its own would be a claim rather
#: than a measurement, so it is only ever stamped on a report whose environment matches the
#: environment the reviewed registry requires for this target: membership is checked, never
#: asserted (#313 F-R1).
COMPARABLE_GROUP = "ac11-security-dependency-sast-hosted-v1"
#: ``requiredEnvironment`` of TARGET_ID in the reviewed registry.  The aggregator re-reads it
#: from Git and refuses an environment that does not satisfy it; keeping it here lets the
#: importer refuse a run from another lane *before* it labels that run comparable.
REGISTERED_ENVIRONMENT = {"topology": "hosted", "evidenceClass": "security-tools-v0"}
#: This file's own repository path.  The producer copies the reviewed scan allowlist's three
#: pins into ``toolFiles``, so the importer pin in a report is the source tree's statement
#: about which importer may write this axis envelope -- and an importer whose own blob is a
#: different one is not that importer, however similar (#313 F-R3).
IMPORTER_REPO_PATH = "tools/import_ac11_security_scan.py"
SCAN_ALLOWLIST_REPO_PATH = (
    "docs/vault/30_Development/Evidence/s11-security-dependency-sast-allowlist-v1.json"
)
SCANNER_IDS = ("bandit", "pip-audit")
#: Finding inventories the producer reports.  A non-empty one is a measured failure, so an
#: envelope may not call it a pass.
FAILURE_INVENTORIES = (
    "unallowlistedFindingIds",
    "expiredFindingIds",
    "staleAllowlistFindingIds",
    "severityMismatchFindingIds",
)
REPOSITORY = "egparadise/SaintVision-Invion"
WORKFLOW_PATH = ".github/workflows/ac11-security-scan.yml"
REPORT_MEMBER = "s11-ac11-security-scan.json"
JUNIT_MEMBER = "s11-ac11-security-scan.xml"
MEMBERS = {REPORT_MEMBER, JUNIT_MEMBER}
SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
RUN_ID_RE = re.compile(r"^[0-9]+$")


class SecurityImportError(RuntimeError):
    """Fail-closed, redacted evidence import failure."""


def _canonical_sha256(value: Any) -> str:
    """The producer's canonicalisation, byte for byte (``run_ac11_security_scan.py:51``)."""

    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def importer_blob() -> str:
    """The Git blob of the importer that is executing, computed from its own bytes.

    The aggregator verifies the reviewed allowlist the same way: sha1 over Git's object
    header and the file's bytes (``aggregate_ac11_evidence.py:1232``).  Reading ``__file__``
    rather than Git keeps this importer offline, and it answers the right question: which
    code wrote this envelope, not which code the checkout happens to contain.
    """

    data = Path(__file__).resolve().read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def _json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SecurityImportError(f"{label} unreadable: {type(exc).__name__}") from None
    if not isinstance(value, dict):
        raise SecurityImportError(f"{label} must be an object")
    return value


def _utc(value: Any, label: str) -> datetime:
    if not isinstance(value, str):
        raise SecurityImportError(f"{label} must be RFC3339")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise SecurityImportError(f"{label} must be RFC3339") from None
    if parsed.tzinfo is None:
        raise SecurityImportError(f"{label} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _numeric(value: Any, label: str) -> str:
    text = str(value)
    if isinstance(value, bool) or not RUN_ID_RE.fullmatch(text):
        raise SecurityImportError(f"{label} must contain digits only")
    return text


def _digest(value: Any) -> str:
    if not isinstance(value, str) or not value.startswith("sha256:"):
        raise SecurityImportError("artifact digest must use sha256")
    digest = value.removeprefix("sha256:")
    if not SHA256_RE.fullmatch(digest):
        raise SecurityImportError("artifact digest is malformed")
    return digest


def _members(archive: bytes) -> dict[str, bytes]:
    try:
        with zipfile.ZipFile(BytesIO(archive)) as bundle:
            names = bundle.namelist()
            if set(names) != MEMBERS or len(names) != len(MEMBERS):
                raise SecurityImportError("artifact member set is not exact")
            for name in names:
                path = PurePosixPath(name)
                info = bundle.getinfo(name)
                if path.is_absolute() or ".." in path.parts or info.is_dir():
                    raise SecurityImportError("artifact member path is unsafe")
            return {name: bundle.read(name) for name in names}
    except (OSError, zipfile.BadZipFile, KeyError) as exc:
        raise SecurityImportError(f"artifact archive unreadable: {type(exc).__name__}") from None


def import_evidence(
    archive: bytes,
    run_metadata: dict[str, Any],
    artifact_metadata: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    observed_now = now or datetime.now(timezone.utc)
    if observed_now.tzinfo is None:
        raise SecurityImportError("import clock must be timezone-aware")
    members = _members(archive)
    try:
        report = json.loads(members[REPORT_MEMBER].decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise SecurityImportError(f"producer report unreadable: {type(exc).__name__}") from None
    if not isinstance(report, dict):
        raise SecurityImportError("producer report must be an object")
    source = report.get("sourceHeadSha")
    source_run_id = report.get("sourceRunId")
    if not isinstance(source, str) or not SHA1_RE.fullmatch(source):
        raise SecurityImportError("sourceHeadSha is malformed")
    if not isinstance(source_run_id, str) or not RUN_ID_RE.fullmatch(source_run_id):
        raise SecurityImportError("sourceRunId must contain digits only")

    run_id = _numeric(run_metadata.get("id"), "run metadata id")
    workflow_run = artifact_metadata.get("workflow_run")
    if not isinstance(workflow_run, dict):
        raise SecurityImportError("artifact workflow_run metadata is missing")
    artifact_run_id = _numeric(workflow_run.get("id"), "artifact workflow run id")
    artifact_id = _numeric(artifact_metadata.get("id"), "artifact id")
    if source_run_id != run_id or source_run_id != artifact_run_id:
        raise SecurityImportError("sourceRunId differs from GitHub metadata")
    if run_metadata.get("status") != "completed" or run_metadata.get("conclusion") != "success":
        raise SecurityImportError("GitHub run did not complete successfully")
    if run_metadata.get("head_sha") != source or workflow_run.get("head_sha") != source:
        raise SecurityImportError("GitHub run or artifact head differs from sourceHeadSha")
    repository = run_metadata.get("repository")
    if not isinstance(repository, dict) or repository.get("full_name") != REPOSITORY:
        raise SecurityImportError("run repository is not canonical")
    workflow = str(run_metadata.get("path", "")).split("@", 1)[0]
    if workflow != WORKFLOW_PATH:
        raise SecurityImportError("run workflow path is not canonical")
    if run_metadata.get("event") not in {"pull_request", "workflow_dispatch"}:
        raise SecurityImportError("run event is not an approved opt-in trigger")
    expected_name = f"s11-ac11-security-{source}"
    if artifact_metadata.get("name") != expected_name:
        raise SecurityImportError("artifact name is not bound to sourceHeadSha")
    if artifact_metadata.get("expired") is not False:
        raise SecurityImportError("artifact is expired or expiration state is unknown")
    expires_at = _utc(artifact_metadata.get("expires_at"), "artifact expiresAt")
    if expires_at <= observed_now.astimezone(timezone.utc):
        raise SecurityImportError("artifact is expired")
    expected_digest = _digest(artifact_metadata.get("digest"))
    observed_digest = hashlib.sha256(archive).hexdigest()
    if observed_digest != expected_digest:
        raise SecurityImportError("downloaded artifact digest differs from GitHub metadata")

    scan_artifact = {
        "repository": REPOSITORY,
        "workflowPath": WORKFLOW_PATH,
        "runId": run_id,
        "artifactId": artifact_id,
        "artifactName": expected_name,
        "digest": expected_digest,
        "observedDigest": observed_digest,
        "expiresAt": expires_at.isoformat().replace("+00:00", "Z"),
        "runConclusion": "success",
        "producerReportSha256": hashlib.sha256(members[REPORT_MEMBER]).hexdigest(),
        "junitSha256": hashlib.sha256(members[JUNIT_MEMBER]).hexdigest(),
    }
    report["scanArtifact"] = scan_artifact
    return axis_envelope(
        report,
        expected_digest=expected_digest,
        observed_digest=observed_digest,
        expires_at=expires_at,
        scan_artifact=scan_artifact,
    )


def _threat_reports(report: dict[str, Any]) -> list[dict[str, Any]]:
    """The threat reports this artifact carries, as the aggregator reads them.

    The producer reports the scan; it does not report the definer policy, the RLS probes
    or the VF observations, and nothing else in this repository emits them either.  So the
    list is whatever the producer actually gave plus nothing invented: a missing report is
    reported as missing, never defaulted to a pass.
    """

    observations = report.get("observations")
    if isinstance(observations, list) and observations:
        reports = [row for row in observations if isinstance(row, dict) and row.get("threatId")]
        if len(reports) != len(observations):
            raise SecurityImportError("producer observations contain a report without a threatId")
        return reports
    if report.get("threatId"):
        # The producer's report *is* the scan threat report: it carries ``threatId`` at the
        # top level together with the counts and allowlist fields the aggregator reads.
        # Nothing is synthesised here; the report is listed as the one report it is.
        return [report]
    raise SecurityImportError("producer report carries no threat report to adapt")


def _environment(report: dict[str, Any]) -> dict[str, Any]:
    """The producer's environment plus the comparability group this lane belongs to.

    The group is a constant because the lane is: the registry pins the environment this
    target is measured in, and a report that does not match it is refused rather than
    relabelled.  So the name describes a set this function has checked membership of, which
    is the difference between declaring comparability and assuming it.
    """

    environment = report.get("environment")
    if not isinstance(environment, dict):
        raise SecurityImportError("producer report carries no environment")
    for name, expected in REGISTERED_ENVIRONMENT.items():
        if environment.get(name) != expected:
            raise SecurityImportError(
                f"producer environment does not satisfy the registered requirement: {name}"
            )
    declared = environment.get("comparableGroup")
    if declared is not None and declared != COMPARABLE_GROUP:
        raise SecurityImportError("producer declares a different comparability group")
    return {**environment, "comparableGroup": COMPARABLE_GROUP}


def _bound_importer(report: dict[str, Any]) -> dict[str, str]:
    """Bind this envelope to the importer the source tree pins, or refuse to write one.

    ``toolFiles`` is the reviewed allowlist's three pins, copied by the producer out of the
    tree the run checked out.  If the pinned importer blob is not this file's blob, then the
    envelope is being written by code the source tree does not pin -- which is how the r1
    measurement came to describe an importer that does not exist at its own
    ``sourceHeadSha`` (#313 F-R3).  The aggregator applies the same rule to all three pins,
    but only once four threat reports exist, so the check belongs here as well as there.
    """

    reference = report.get("allowlist")
    if not isinstance(reference, dict) or reference.get("path") != SCAN_ALLOWLIST_REPO_PATH:
        raise SecurityImportError("producer report does not name the reviewed scan allowlist")
    files = report.get("toolFiles")
    if not isinstance(files, list):
        raise SecurityImportError("producer report carries no toolFiles")
    pinned = [
        row for row in files if isinstance(row, dict) and row.get("path") == IMPORTER_REPO_PATH
    ]
    if len(pinned) != 1:
        raise SecurityImportError("toolFiles does not pin this importer exactly once")
    blob = importer_blob()
    if pinned[0].get("blob") != blob:
        raise SecurityImportError(
            "the source tree pins a different importer blob than the importer writing this "
            "envelope; re-run the lane at the head that carries this importer"
        )
    return {"path": IMPORTER_REPO_PATH, "blob": blob}


def _recompute_scan(report: dict[str, Any]) -> tuple[str, str | None]:
    """Recompute SEC-SCAN-001 from the payload the artifact carries.

    The aggregator recomputes this axis in full and refuses an envelope whose verdict
    disagrees with it.  The payload arithmetic is shared with it rather than restated here --
    the finding rows against the two counts, the counts against the per-scanner summaries, the
    exit codes against those summaries, and the two coverage inventories against the files and
    dependencies the scanners actually read.  What stays here is what the artifact alone can
    answer: whether the report is complete, whether its digest covers its payload, and what
    the inventories say.  The allowlist comparison and the Git provenance remain the
    aggregator's, because only it can ask them.
    """

    status = report.get("status")
    if status != "complete" or report.get("reportAvailable") is not True:
        return "NOT_OBSERVED", f"the producer reports the scan as {status!r}"
    payload = report.get("payload")
    if not isinstance(payload, dict):
        raise SecurityImportError("a complete scan report carries no payload to recompute")
    if _canonical_sha256(payload) != report.get("payloadSha256"):
        raise SecurityImportError("payloadSha256 does not cover the payload it travels with")
    findings, broken = scan_payload_invariants(payload)
    if broken:
        # A complete report whose payload disagrees with itself is not an unobserved scan --
        # the producer's own unavailable path above is what "not observed" means -- it is
        # evidence nobody can read, and reading it anyway is how a finding row with no count
        # and a scanner that read no files both became MEASURED_PASS (#313 r2 N1).
        raise SecurityImportError(
            "the scan payload contradicts itself: " + ", ".join(broken)
        )
    # The invariants bind these to the finding rows, so reading them is reading the rows.
    measured = {
        "criticalCount": payload["criticalCount"],
        "highCount": payload["highCount"],
        "criticalHighFindings": len(findings),
    }
    for name in FAILURE_INVENTORIES:
        measured[name] = len(payload[name])
    failures = {name: count for name, count in measured.items() if count}
    if failures:
        return "MEASURED_FAIL", ", ".join(f"{name}={count}" for name, count in sorted(failures.items()))
    return "MEASURED_PASS", None


def axis_envelope(
    report: dict[str, Any],
    *,
    expected_digest: str,
    observed_digest: str,
    expires_at: datetime,
    scan_artifact: dict[str, Any],
) -> dict[str, Any]:
    """Adapt the validated producer report into an admissible AC-11 axis envelope.

    Everything the aggregator binds -- the artifact digests, the clean checkout, the run
    conclusion, the reviewed target registry -- is already measured above; this function
    only arranges it in the shape ``aggregate_ac11_evidence`` accepts, and decides the one
    thing the arrangement cannot borrow: the verdict.
    """

    reports = _threat_reports(report)
    present = {str(row["threatId"]) for row in reports}
    unregistered = sorted(present - set(REQUIRED_THREAT_IDS))
    if unregistered:
        raise SecurityImportError(f"unregistered security threat id: {unregistered[0]}")
    scans = [row for row in reports if str(row["threatId"]) == SCAN_THREAT_ID]
    if len(scans) != 1:
        raise SecurityImportError("the artifact carries no SEC-SCAN-001 report")
    scan_verdict, scan_detail = _recompute_scan(scans[0])
    claimed = str(scans[0].get("verdict", ""))
    if not claimed:
        raise SecurityImportError("the scan report carries no verdict")
    if claimed != scan_verdict:
        raise SecurityImportError(
            f"the scan report claims {claimed} while its own payload recomputes {scan_verdict}"
        )
    unrecomputable = [
        threat
        for threat in REQUIRED_THREAT_IDS
        if threat in present and threat not in RECOMPUTABLE_THREAT_IDS
    ]
    if unrecomputable:
        raise SecurityImportError(
            "this importer recomputes SEC-SCAN-001 only, so it cannot say what "
            + ", ".join(unrecomputable)
            + " measured; that verdict belongs to the path that combines those producers' "
            "verified results"
        )
    missing = [threat for threat in REQUIRED_THREAT_IDS if threat not in present]
    # The aggregator reaches the same conclusion from the same absence; declaring it here
    # keeps the envelope's own verdict equal to the recomputed one, which is what stops a
    # partial scan from being read as a pass.  It is always reached today: three of the four
    # threat reports have no producer anywhere in this repository, and a report this
    # importer cannot recompute is refused above rather than carried.
    verdict = "NOT_OBSERVED"
    reason = "no producer emits " + ", ".join(missing)
    if scan_verdict != "MEASURED_PASS":
        # A failing or unmeasured scan must not disappear into "not observed" without
        # saying so: the aggregator cannot see past the missing reports either.
        reason += f"; the SEC-SCAN-001 report itself recomputes {scan_verdict}"
        if scan_detail:
            reason += f" ({scan_detail})"
    envelope = {
        "schemaVersion": report.get("schemaVersion", "1.0.0"),
        "runPurpose": "ac11-axis-evidence",
        "axis": EMITTED_AXES[0],
        "verdict": verdict,
        "sourceRunId": report["sourceRunId"],
        "sourceHeadSha": report["sourceHeadSha"],
        "checkoutTreeSha": report["checkoutTreeSha"],
        "artifactSha256": expected_digest,
        "artifactObservedSha256": observed_digest,
        "artifactAvailable": True,
        "artifactExpiresAt": expires_at.isoformat().replace("+00:00", "Z"),
        "cleanCheckout": report["cleanCheckout"],
        "runConclusion": "success",
        "startedAt": report["startedAt"],
        "finishedAt": report["finishedAt"],
        "environment": _environment(report),
        "targetRef": {
            "commit": REGISTRY_COMMIT,
            "path": REGISTRY_PATH,
            "blob": REGISTRY_BLOB,
            "targetId": TARGET_ID,
            "criteria": {},
        },
        "observations": reports,
        "cleanup": report.get("cleanup", {"residueCount": 0}),
        "scanArtifact": scan_artifact,
        "importerFile": _bound_importer(report),
        "scanRecomputed": scan_verdict,
    }
    envelope["reason"] = reason
    return envelope


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--run-metadata", type=Path, required=True)
    parser.add_argument("--artifact-metadata", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        archive = args.archive.read_bytes()
        result = import_evidence(
            archive,
            _json(args.run_metadata, "run metadata"),
            _json(args.artifact_metadata, "artifact metadata"),
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    except SecurityImportError as exc:
        print(f"AC-11 security import refused: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - type-only redacted failure
        print(f"AC-11 security import errored: {type(exc).__name__}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
