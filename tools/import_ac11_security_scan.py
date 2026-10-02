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
    missing = [threat for threat in REQUIRED_THREAT_IDS if threat not in present]
    if missing:
        # The aggregator reaches the same conclusion from the same absence; declaring it
        # here keeps the envelope's own verdict equal to the recomputed one, which is what
        # stops a partial scan from being read as a pass.
        verdict = "NOT_OBSERVED"
        reason = "no producer emits " + ", ".join(missing)
    else:
        verdict = str(report.get("verdict", ""))
        reason = None
        if not verdict:
            raise SecurityImportError("producer report carries no verdict")
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
        "environment": report["environment"],
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
    }
    if reason is not None:
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
