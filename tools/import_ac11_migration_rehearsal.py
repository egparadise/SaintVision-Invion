"""Import a downloaded migration rehearsal artifact into AC-11 axis envelopes.

The rehearsal cannot include the GitHub artifact digest in the artifact whose
digest is being computed.  This importer therefore runs after download and
cross-checks caller-supplied GitHub run/artifact metadata against the redacted
producer report and downloaded zip.

Trust boundary: this tool does not call or authenticate the GitHub API.  The
operator must obtain the JSON and zip from the canonical repository with
``gh api repos/egparadise/SaintVision-Invion/actions/runs/<run-id>``,
``gh api repos/egparadise/SaintVision-Invion/actions/artifacts/<artifact-id>``,
and ``gh api repos/egparadise/SaintVision-Invion/actions/artifacts/<artifact-id>/zip``.
The importer detects inconsistencies among those inputs; it cannot prove that
coherently forged inputs originated from GitHub.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aggregate_ac11_evidence import RepositoryGit, _migration_reversible_segment


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = "docs/vault/30_Development/Evidence/s11-ac11-target-registry-v0.json"
REGISTRY_BLOB = "e80b252a39c0842dfc58004a41e1ac328390ab08"
TARGET_ID = "s11-irreversible-restore-forward-v0"
REVERSIBLE_TARGET_ID = "s11-migration-reversible-roundtrip-v1"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
RUN_ID = re.compile(r"^[0-9]+$")
REPORT_NAME = "s11-ac11-migration-rehearsal.json"
JUNIT_NAME = "s11-ac11-migration-rehearsal.xml"
MAX_ARCHIVE_BYTES = 10 * 1024 * 1024
MAX_MEMBER_BYTES = 2 * 1024 * 1024


class EvidenceImportError(ValueError):
    """Fail-closed artifact import error."""


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, text=True, capture_output=True, encoding="utf-8"
    )
    if result.returncode:
        raise EvidenceImportError("Git provenance is unreachable")
    return result.stdout.strip()


def _utc(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise EvidenceImportError(f"{field} must be a UTC RFC3339 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EvidenceImportError(f"{field} must be a UTC RFC3339 string") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise EvidenceImportError(f"{field} must be UTC")
    return parsed.isoformat().replace("+00:00", "Z")


def _artifact_digest(value: Any) -> str:
    if not isinstance(value, str):
        raise EvidenceImportError("artifact digest must be a full SHA-256")
    normalized = value.removeprefix("sha256:")
    if not HEX64.fullmatch(normalized):
        raise EvidenceImportError("artifact digest must be a full SHA-256")
    return normalized


def _metadata_id(value: Any, field: str) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise EvidenceImportError(f"{field} must be a positive numeric ID")
    rendered = str(value)
    if not RUN_ID.fullmatch(rendered) or int(rendered) < 1:
        raise EvidenceImportError(f"{field} must be a positive numeric ID")
    return rendered


def _read_bundle(archive: bytes) -> tuple[dict[str, Any], bytes, bytes, bool]:
    if not isinstance(archive, bytes) or not 0 < len(archive) <= MAX_ARCHIVE_BYTES:
        raise EvidenceImportError("artifact zip is missing or exceeds the import bound")
    try:
        with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
            members = [item for item in bundle.infolist() if not item.is_dir()]
            by_name: dict[str, zipfile.ZipInfo] = {}
            for member in members:
                name = Path(member.filename).name
                if name in by_name:
                    raise EvidenceImportError("artifact zip contains duplicate evidence names")
                by_name[name] = member
            if set(by_name) != {REPORT_NAME, JUNIT_NAME}:
                raise EvidenceImportError("artifact zip must contain only the report and JUnit")
            if any(item.file_size > MAX_MEMBER_BYTES for item in by_name.values()):
                raise EvidenceImportError("artifact evidence member exceeds the import bound")
            report_bytes = bundle.read(by_name[REPORT_NAME])
            junit_bytes = bundle.read(by_name[JUNIT_NAME])
    except (zipfile.BadZipFile, RuntimeError) as exc:
        raise EvidenceImportError("artifact zip is unreadable") from exc
    try:
        report = json.loads(report_bytes.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise EvidenceImportError("producer report is not valid UTF-8 JSON") from exc
    if not isinstance(report, dict):
        raise EvidenceImportError("producer report must be a JSON object")
    try:
        root = ET.fromstring(junit_bytes)
    except ET.ParseError as exc:
        raise EvidenceImportError("producer JUnit is not valid XML") from exc
    if (
        root.tag != "testsuite"
        or set(root.attrib) != {"name", "tests", "failures", "errors", "skipped"}
        or root.attrib.get("name") != "s11-ac11-migration-rehearsal"
        or root.attrib.get("tests") != "7"
        or root.attrib.get("failures") != "0"
        or root.attrib.get("errors") != "0"
        or root.attrib.get("skipped") not in {"0", "1"}
    ):
        raise EvidenceImportError("producer JUnit summary is not the reviewed passing shape")
    cases = {case.attrib.get("name"): case for case in root.findall("testcase")}
    expected_cases = {
        "fixture-manifest",
        "reversible-segment",
        "irreversible-restore-forward",
        "negative-existing-object-deletion",
        "negative-0009-duplicate-key",
        "negative-ellipsis-noop",
        "negative-0053-scoped-row-refusal",
    }
    if set(cases) != expected_cases:
        raise EvidenceImportError("producer JUnit cases are missing or duplicated")
    reversible_skipped = cases["reversible-segment"].find("skipped") is not None
    if root.attrib["skipped"] != ("1" if reversible_skipped else "0") or any(
        case.find("failure") is not None or case.find("error") is not None
        for case in cases.values()
    ):
        raise EvidenceImportError("producer JUnit does not prove the passing rehearsal")
    if any(
        case.find("skipped") is not None
        for name, case in cases.items()
        if name != "reversible-segment"
    ):
        raise EvidenceImportError("producer JUnit skips an executable case")
    return report, report_bytes, junit_bytes, reversible_skipped


def _source_migration_segment(source: str) -> tuple[str, str, int]:
    try:
        return _migration_reversible_segment(RepositoryGit(ROOT), source)
    except (OSError, ValueError) as exc:
        raise EvidenceImportError("source migration graph is invalid or unreachable") from exc


def _observation(metric: str, value: int) -> dict[str, Any]:
    return {
        "metric": metric,
        "value": value,
        "unit": "count",
        "n": 1,
        "successCount": 1,
        "failureCount": 0,
        "skipCount": 0,
        "errorsByClass": {},
    }


def import_artifact(
    archive: bytes,
    *,
    run_metadata: dict[str, Any],
    artifact_metadata: dict[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    report, report_bytes, junit_bytes, reversible_skipped = _read_bundle(archive)
    if not isinstance(run_metadata, dict) or not isinstance(artifact_metadata, dict):
        raise EvidenceImportError("run and artifact metadata must be JSON objects")
    if report.get("schemaVersion") != "1.0.0" or report.get("runPurpose") != (
        "s11-ac11-migration-rehearsal"
    ):
        raise EvidenceImportError("producer report schema or purpose is unknown")
    if report.get("verdict") != "MEASURED_PASS" or report.get("failureType") is not None:
        raise EvidenceImportError("a failed rehearsal cannot become AC-11 evidence")
    source = report.get("sourceHeadSha")
    tree = report.get("checkoutTreeSha")
    if not isinstance(source, str) or not HEX40.fullmatch(source):
        raise EvidenceImportError("sourceHeadSha is invalid")
    if not isinstance(tree, str) or not HEX40.fullmatch(tree):
        raise EvidenceImportError("checkoutTreeSha is invalid")
    if _git("rev-parse", f"{source}^{{tree}}") != tree or report.get("cleanCheckout") is not True:
        raise EvidenceImportError("producer checkout provenance is invalid")
    reversible_head, reversible_barrier, reversible_tail = _source_migration_segment(source)
    if reversible_skipped != (reversible_tail == 0):
        raise EvidenceImportError("producer JUnit reversible result differs from the source graph")
    if _git("rev-parse", f"{source}:{REGISTRY_PATH}") != REGISTRY_BLOB:
        raise EvidenceImportError("source tree does not contain the reviewed target registry")
    registry = json.loads(_git("show", f"{source}:{REGISTRY_PATH}"))
    targets = registry.get("targets", [])
    if not isinstance(targets, list):
        raise EvidenceImportError("target registry has no target list")

    def registered_target(target_id: str, axis: str, expected: dict[str, Any]) -> dict[str, Any]:
        matches = [row for row in targets if isinstance(row, dict) and row.get("targetId") == target_id]
        if len(matches) != 1 or matches[0].get("axis") != axis:
            raise EvidenceImportError(f"{axis} target is absent, duplicated, or misbound")
        if matches[0].get("criteria") != expected:
            raise EvidenceImportError(f"{axis} target criteria differ from the importer contract")
        return matches[0]

    expected_criteria = {
        "catalogMismatchCount": {"operator": "eq", "value": 0},
        "negativeFixturePassCount": {"operator": "eq", "value": 4},
        "restoreForwardPassCount": {"operator": "eq", "value": 1},
    }
    registered_target(TARGET_ID, "irreversible-restore-forward", expected_criteria)
    reversible_criteria = {
        "catalogMismatchCount": {"operator": "eq", "value": 0},
        "reversibleRoundtripPassCount": {"operator": "eq", "value": 1},
        "sentinelMismatchCount": {"operator": "eq", "value": 0},
    }
    if reversible_tail:
        registered_target(
            REVERSIBLE_TARGET_ID, "migration-reversible-segment", reversible_criteria
        )
    axes = report.get("axes")
    if not isinstance(axes, list) or len(axes) != 2:
        raise EvidenceImportError("producer axes are missing or duplicated")
    by_name = {row.get("axis"): row for row in axes if isinstance(row, dict)}
    reversible = by_name.get("migration-reversible-segment")
    restore = by_name.get("irreversible-restore-forward")
    if set(by_name) != {"migration-reversible-segment", "irreversible-restore-forward"}:
        raise EvidenceImportError("producer axes are missing or duplicated")
    expected_reversible = (
        {
            "axis": "migration-reversible-segment",
            "verdict": "MEASURED_PASS",
            "observationCount": 1,
            "details": {
                "startingRevision": reversible_head,
                "endingRevision": reversible_barrier,
                "catalogEquivalent": True,
                "sentinelPreserved": True,
            },
        }
        if reversible_tail
        else {
            "axis": "migration-reversible-segment",
            "verdict": "NOT_APPLICABLE",
            "structuralException": {
                "reason": "no-reversible-tail",
                "reversibleTailCount": 0,
            },
        }
    )
    if reversible != expected_reversible:
        raise EvidenceImportError(
            "reversible tail roundtrip does not match the source migration graph"
        )
    if not isinstance(restore, dict) or restore.get("verdict") != "MEASURED_PASS":
        raise EvidenceImportError("restore axis did not pass")
    details = restore.get("details")
    negative = details.get("negativeFixtures") if isinstance(details, dict) else None
    if (
        not isinstance(negative, dict)
        or negative.get("passedCount") != 4
        or sorted(row.get("case") for row in negative.get("cases", []) if isinstance(row, dict))
        != [
            "0009-duplicate-key",
            "0053-scoped-row-refusal",
            "ellipsis-noop",
            "existing-object-deletion",
        ]
        or any(row.get("verdict") != "EXPECTED_FINDING" for row in negative.get("cases", []))
    ):
        raise EvidenceImportError("negative fixture evidence is incomplete")
    cleanup = report.get("cleanup")
    if not isinstance(cleanup, dict) or cleanup.get("residueCount") != 0:
        raise EvidenceImportError("producer cleanup is incomplete")

    source_run_id = report.get("sourceRunId")
    if not isinstance(source_run_id, str) or not RUN_ID.fullmatch(source_run_id):
        raise EvidenceImportError("sourceRunId must be present and contain digits only")
    run_id = _metadata_id(run_metadata.get("id"), "run metadata id")
    workflow_run = artifact_metadata.get("workflow_run")
    if not isinstance(workflow_run, dict):
        raise EvidenceImportError("artifact workflow_run metadata is missing")
    artifact_run_id = _metadata_id(workflow_run.get("id"), "artifact workflow run id")
    if source_run_id != run_id or source_run_id != artifact_run_id:
        raise EvidenceImportError("sourceRunId differs from GitHub run metadata")
    if run_metadata.get("status") != "completed" or run_metadata.get("conclusion") != "success":
        raise EvidenceImportError("GitHub run did not complete successfully")
    if run_metadata.get("head_sha") != source or workflow_run.get("head_sha") != source:
        raise EvidenceImportError("GitHub run or artifact head differs from sourceHeadSha")
    expected_name = f"s11-ac11-migration-{source}"
    if artifact_metadata.get("name") != expected_name:
        raise EvidenceImportError("artifact name is not bound to sourceHeadSha")
    if artifact_metadata.get("expired") is not False:
        raise EvidenceImportError("artifact is expired or expiration state is unknown")
    digest = _artifact_digest(artifact_metadata.get("digest"))
    observed_digest = hashlib.sha256(archive).hexdigest()
    if digest != observed_digest:
        raise EvidenceImportError("downloaded artifact digest does not match GitHub metadata")
    expiry = _utc(artifact_metadata.get("expires_at"), "artifactExpiresAt")
    observed_now = now or datetime.now(timezone.utc)
    if observed_now.tzinfo is None:
        raise EvidenceImportError("import clock must be timezone-aware")
    expires_at = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
    if expires_at <= observed_now.astimezone(timezone.utc):
        raise EvidenceImportError("artifact is expired")
    junit_sha = hashlib.sha256(junit_bytes).hexdigest()
    if report.get("junitSha256") != junit_sha:
        raise EvidenceImportError("producer JUnit digest does not match the artifact")
    started = _utc(report.get("startedAt"), "startedAt")
    finished = _utc(report.get("finishedAt"), "finishedAt")
    environment = report.get("environment")
    if not isinstance(environment, dict):
        raise EvidenceImportError("producer environment is missing")
    report_sha = hashlib.sha256(report_bytes).hexdigest()
    common = {
        "schemaVersion": "1.0.0",
        "runPurpose": "ac11-axis-evidence",
        "sourceRunId": source_run_id,
        "sourceHeadSha": source,
        "checkoutTreeSha": tree,
        "artifactSha256": digest,
        "artifactObservedSha256": observed_digest,
        "artifactAvailable": True,
        "artifactExpiresAt": expiry,
        "cleanCheckout": True,
        "runConclusion": run_metadata["conclusion"],
        "producerReportSha256": report_sha,
        "junitSha256": junit_sha,
        "environment": {
            **environment,
            "comparableGroup": "hosted-ubuntu-postgres16-migration-rehearsal",
        },
        "startedAt": started,
        "finishedAt": finished,
        "cleanup": cleanup,
    }
    def target_ref(target_id: str, criteria: dict[str, Any]) -> dict[str, Any]:
        return {
            "commit": source,
            "path": REGISTRY_PATH,
            "blob": REGISTRY_BLOB,
            "targetId": target_id,
            "criteria": criteria,
        }

    reversible_axis = (
        {
            **common,
            "axis": "migration-reversible-segment",
            "targetRef": target_ref(REVERSIBLE_TARGET_ID, reversible_criteria),
            "verdict": "MEASURED_PASS",
            "reversibleSegment": {
                "startingRevision": reversible_head,
                "endingRevision": reversible_barrier,
                "reversibleTailCount": reversible_tail,
            },
            "observations": [
                _observation("catalogMismatchCount", 0),
                _observation("reversibleRoundtripPassCount", 1),
                _observation("sentinelMismatchCount", 0),
            ],
        }
        if reversible_tail
        else {
            **common,
            "axis": "migration-reversible-segment",
            "verdict": "NOT_APPLICABLE",
            "structuralException": reversible["structuralException"],
        }
    )
    imported_axes = [
        reversible_axis,
        {
            **common,
            "axis": "irreversible-restore-forward",
            "targetRef": target_ref(TARGET_ID, expected_criteria),
            "verdict": "MEASURED_PASS",
            "observations": [
                _observation("catalogMismatchCount", 0),
                _observation("negativeFixturePassCount", 4),
                _observation("restoreForwardPassCount", 1),
            ],
        },
    ]
    return {
        "schemaVersion": "1.0.0",
        "runPurpose": "ac11-migration-rehearsal-import",
        "producerReportSha256": report_sha,
        "junitSha256": junit_sha,
        "axes": imported_axes,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-zip", type=Path, required=True)
    parser.add_argument("--run-metadata", type=Path, required=True)
    parser.add_argument("--artifact-metadata", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        imported = import_artifact(
            args.artifact_zip.read_bytes(),
            run_metadata=json.loads(args.run_metadata.read_text(encoding="utf-8")),
            artifact_metadata=json.loads(
                args.artifact_metadata.read_text(encoding="utf-8")
            ),
        )
    except (OSError, json.JSONDecodeError, EvidenceImportError) as exc:
        print(f"AC-11 migration import refused: {exc}")
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(imported, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
