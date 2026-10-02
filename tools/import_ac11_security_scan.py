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


REPOSITORY = "egparadise/SaintVision-Invion"
#: Empty on purpose, and the emptiness is the finding. This importer returns the
#: producer's report with runPurpose "s11-ac11-security-scan" and no axis field, so the
#: aggregator -- which requires runPurpose "ac11-axis-evidence" and an axis in
#: REQUIRED_AXES -- cannot take its output. Something has to adapt that report into an
#: axis envelope and nothing does; declaring () says so in the code rather than leaving
#: a reader to infer it from the absence of a name (#299 r1, r3).
EMITTED_AXES: tuple[str, ...] = ()
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

    report["scanArtifact"] = {
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
    return report


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
