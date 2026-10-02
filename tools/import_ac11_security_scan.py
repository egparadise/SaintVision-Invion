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
from aggregate_ac11_evidence import (
    DEFAULT_ALLOWLIST,
    Verdict,
    evaluate_definer,
    evaluate_rls,
    evaluate_vf,
    scan_payload_invariants,
    validate_allowlist,
)


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
#: The two database threat reports ``run_ac11_security_threat_reports.py`` adds to the lane's
#: artifact.  They are optional members: an artifact from before that producer existed carries
#: neither, and this importer says which reports are absent rather than inventing them.
DEFINER_MEMBER = "s11-ac11-security-definer.json"
RLS_MEMBER = "s11-ac11-security-rls.json"
#: The exact member set, in both admissible shapes.  An unexpected member is still refused:
#: a file nobody validates is a file nobody measured.
BASE_MEMBERS = {REPORT_MEMBER, JUNIT_MEMBER}
DATABASE_MEMBERS = {DEFINER_MEMBER, RLS_MEMBER}
MEMBERS = BASE_MEMBERS
MEMBER_SETS = (BASE_MEMBERS, BASE_MEMBERS | DATABASE_MEMBERS)
#: SEC-VF-001 is produced by a different lane (the reviewed allowlist pins that workflow as one
#: of its tool files), so its evidence arrives as a child reference bound by digest and head --
#: the same shape the long-soak importer uses for its two references.
VF_THREAT_ID = "SEC-VF-001"
#: The browser lane's artifact: its fixed name and the one member that carries the proof.  The
#: name is not head-bound, so the head binding comes from the run metadata rather than from it.
VF_ARTIFACT_NAME = "desktop-browser-safe-evidence"
VF_PROOF_MEMBER = "vf-desktop-browser-ci.json"
#: What SEC-VF-001 is *about*: every value ``vf_report`` reads out of that proof and either
#: checks against the reviewed allowlist or records in the report.  Two runs of the browser lane
#: at one head are never byte-identical -- measured on runs 36993192700 and 36993193630, whose
#: artifacts differ by a fresh run uuid, two timestamps, the paths built from that uuid and the
#: digest of a JUnit file whose durations differ -- so "do two candidates carry the same
#: evidence?" is a question about these fields and nothing else.  Declared here so the finder
#: asks it with this list rather than a second one of its own (card 233).
VF_DECISIVE_FIELDS = (
    "caseIdentitiesSha256", "evidenceStatus", "exitCode", "subprocessExitCode", "tests",
)
#: The document ``--vf-evidence`` takes: the three inputs the browser-lane binding needs, named
#: once so the AC-11 aggregate lane can pass them as one argument (card 233).  It is validated as
#: an **exact** key set with no defaults -- a missing key is a binding the caller dropped and an
#: unexpected one is a field nothing checks -- and every value is cross-checked against the
#: metadata it claims to describe, so the document cannot say one run and carry another.
VF_EVIDENCE_SCHEMA = "ac11-vf-evidence:1"
VF_EVIDENCE_KEYS = frozenset({
    "schemaVersion", "repository", "workflowPath", "runId", "artifactId",
    "archive", "runMetadata", "artifactMetadata",
})
DEFINER_THREAT_ID = "SEC-DEF-001"
RLS_THREAT_ID = "SEC-RLS-001"
#: Verdicts a threat report may carry into the envelope.  A report the canonical evaluator
#: calls INVALID_RUN is not carried at all: an envelope whose own verdict would then have to be
#: INVALID_RUN is not evidence, and omitting it with its reason is what this importer can
#: honestly say (card 221).
ADMISSIBLE_REPORT_VERDICTS = (
    Verdict.MEASURED_PASS, Verdict.MEASURED_FAIL, Verdict.NOT_OBSERVED,
)
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


class DuplicateKey(ValueError):
    """A JSON object stated the same key twice."""


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Refuse a repeated key instead of keeping the last one.

    ``json.loads`` keeps the last value silently, so ``{"schemaVersion": "…:0", "schemaVersion":
    "…:1"}`` parsed as the second one -- a document could carry a value for review and another for
    the evaluator (#332 r2 F1).  Every exact-key check in this file reads the dict *after* parsing,
    so the duplicate had already been resolved before any of them looked.  The sibling
    ``assemble_ac11_manifest`` has refused this since #299; this is the same rule, applied to every
    JSON input here.
    """

    seen: dict[str, Any] = {}
    for key, value in pairs:
        if key in seen:
            raise DuplicateKey(f"duplicate JSON key {key!r}")
        seen[key] = value
    return seen


def _loads(raw: str, label: str) -> dict[str, Any]:
    """The only JSON parser in this file: strict about duplicates, and objects only."""

    try:
        value = json.loads(raw, object_pairs_hook=_no_duplicates)
    except DuplicateKey as duplicate:
        raise SecurityImportError(f"{label}: {duplicate}") from None
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise SecurityImportError(f"{label} unreadable: {type(exc).__name__}") from None
    if not isinstance(value, dict):
        raise SecurityImportError(f"{label} must be an object")
    return value


def _json(path: Path, label: str) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise SecurityImportError(f"{label} unreadable: {type(exc).__name__}") from None
    return _loads(raw, label)


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
            if set(names) not in MEMBER_SETS or len(names) != len(set(names)):
                raise SecurityImportError("artifact member set is not exact")
            for name in names:
                path = PurePosixPath(name)
                info = bundle.getinfo(name)
                if path.is_absolute() or ".." in path.parts or info.is_dir():
                    raise SecurityImportError("artifact member path is unsafe")
            return {name: bundle.read(name) for name in names}
    except (OSError, zipfile.BadZipFile, KeyError) as exc:
        raise SecurityImportError(f"artifact archive unreadable: {type(exc).__name__}") from None


def _head_commit_tree(run_metadata: dict[str, Any], label: str, source: str) -> str:
    """The tree GitHub recorded for that run's head commit -- not a value a report chose.

    ``head_commit`` is part of the run metadata GitHub keeps for the workflow run that produced
    the artifact, so its ``tree_id`` is an independent statement about which tree ran.  Checking
    only ``head_sha`` left ``checkoutTreeSha`` free: the producer report could name any tree and
    the VF report copied whatever the scan report said, so changing one field to ``f`` * 40
    still imported as MEASURED_PASS (#319 r2 F2).  Strict object, exact commit, canonical tree.
    """

    commit = run_metadata.get("head_commit")
    if not isinstance(commit, dict):
        raise SecurityImportError(f"{label} run metadata carries no head_commit object")
    if commit.get("id") != source:
        raise SecurityImportError(f"{label} run head_commit is about another commit")
    tree = commit.get("tree_id")
    if not isinstance(tree, str) or not SHA1_RE.fullmatch(tree):
        raise SecurityImportError(f"{label} run head_commit has no canonical tree id")
    return tree


def vf_evidence_inputs(path: Path) -> tuple[bytes, dict[str, Any], dict[str, Any]]:
    """Read the ``--vf-evidence`` document and return the three inputs it names.

    Nothing here re-implements the browser-lane verification: that lives in ``vf_report`` and
    stays the single definition (card 233).  What this adds is the document's own strictness --
    exact keys, the reviewed repository and workflow path, and the two ids it states having to
    equal the ids in the metadata files it points at.  A document that names a run and carries
    another run's metadata is refused here rather than silently importing the latter.
    """

    document = _json(path, "browser lane evidence document")
    if set(document) != VF_EVIDENCE_KEYS:
        missing = sorted(VF_EVIDENCE_KEYS - set(document))
        extra = sorted(set(document) - VF_EVIDENCE_KEYS)
        raise SecurityImportError(
            f"browser lane evidence document is missing {missing} and carries unexpected {extra}"
        )
    if document["schemaVersion"] != VF_EVIDENCE_SCHEMA:
        raise SecurityImportError("browser lane evidence document has another schemaVersion")
    if document["repository"] != REPOSITORY:
        raise SecurityImportError("browser lane evidence document names another repository")
    expected_workflow = _reviewed_allowlist()["secVf001"]["workflow"]["path"]
    if document["workflowPath"] != expected_workflow:
        raise SecurityImportError("browser lane evidence document names another workflow")
    run_id = _numeric(document["runId"], "browser lane evidence runId")
    artifact_id = _numeric(document["artifactId"], "browser lane evidence artifactId")
    base = path.parent
    try:
        archive = (base / str(document["archive"])).read_bytes()
    except OSError:
        raise SecurityImportError("browser lane evidence archive is unreadable") from None
    run_metadata = _json(base / str(document["runMetadata"]), "browser lane run metadata")
    artifact_metadata = _json(
        base / str(document["artifactMetadata"]), "browser lane artifact metadata"
    )
    if run_id != _numeric(run_metadata.get("id"), "browser lane run metadata id"):
        raise SecurityImportError("browser lane evidence document names another run")
    if artifact_id != _numeric(artifact_metadata.get("id"), "browser lane artifact metadata id"):
        raise SecurityImportError("browser lane evidence document names another artifact")
    return archive, run_metadata, artifact_metadata


def import_evidence(
    archive: bytes,
    run_metadata: dict[str, Any],
    artifact_metadata: dict[str, Any],
    *,
    now: datetime | None = None,
    vf_archive: bytes | None = None,
    vf_run_metadata: dict[str, Any] | None = None,
    vf_artifact_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    observed_now = now or datetime.now(timezone.utc)
    if observed_now.tzinfo is None:
        raise SecurityImportError("import clock must be timezone-aware")
    members = _members(archive)
    try:
        report_text = members[REPORT_MEMBER].decode("utf-8")
    except UnicodeError as exc:
        raise SecurityImportError(f"producer report unreadable: {type(exc).__name__}") from None
    report = _loads(report_text, "producer report")
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
    checkout_tree = _head_commit_tree(run_metadata, "security scan", source)
    if report.get("checkoutTreeSha") != checkout_tree:
        raise SecurityImportError("checkoutTreeSha differs from the run head_commit tree")
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
    extra = list(_database_reports(members, report))
    vf_inputs = (vf_archive, vf_run_metadata, vf_artifact_metadata)
    if any(value is not None for value in vf_inputs):
        if any(value is None for value in vf_inputs):
            # Two of the three would let a caller drop the binding it finds inconvenient.
            raise SecurityImportError(
                "SEC-VF-001 needs the browser lane archive with its run and artifact metadata"
            )
        extra.append(
            vf_report(
                vf_archive,
                vf_run_metadata,
                vf_artifact_metadata,
                _reviewed_allowlist(),
                report,
                observed_now,
            )
        )
    return axis_envelope(
        report,
        expected_digest=expected_digest,
        observed_digest=observed_digest,
        expires_at=expires_at,
        scan_artifact=scan_artifact,
        extra_reports=tuple(extra),
        now=observed_now,
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


def _reviewed_allowlist() -> dict[str, Any]:
    """The reviewed security allowlist, loaded the way the aggregator loads it.

    ``validate_allowlist`` refuses content whose canonical digest is not the reviewed one, so
    a tampered or drifted allowlist stops this importer here rather than producing an envelope
    that the aggregator would later refuse for the same reason.
    """

    try:
        value = _json(DEFAULT_ALLOWLIST, "reviewed security allowlist")
        validate_allowlist(value)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise SecurityImportError(
            f"reviewed security allowlist is unusable: {type(exc).__name__}"
        ) from None
    return value


def _database_reports(members: dict[str, bytes], report: dict[str, Any]) -> list[dict[str, Any]]:
    """The SEC-DEF-001 and SEC-RLS-001 reports the lane's artifact carries, if any.

    Both must be about the same run and the same source head as the scan: the envelope has one
    ``sourceRunId`` and one artifact digest, so a report from another run would make the
    envelope's own provenance a statement about evidence it does not contain.
    """

    reports: list[dict[str, Any]] = []
    for member, threat_id in ((DEFINER_MEMBER, DEFINER_THREAT_ID), (RLS_MEMBER, RLS_THREAT_ID)):
        raw = members.get(member)
        if raw is None:
            continue
        try:
            member_text = raw.decode("utf-8")
        except UnicodeError as exc:
            raise SecurityImportError(
                f"{member} unreadable: {type(exc).__name__}"
            ) from None
        document = _loads(member_text, member)
        if not isinstance(document, dict) or document.get("threatId") != threat_id:
            raise SecurityImportError(f"{member} does not carry {threat_id}")
        for field in ("sourceRunId", "sourceHeadSha", "checkoutTreeSha"):
            if document.get(field) != report.get(field):
                raise SecurityImportError(
                    f"{threat_id} {field} differs from the scan report in the same artifact"
                )
        reports.append(document)
    return reports


def vf_required(spec: dict[str, Any]) -> dict[str, Any]:
    """What the reviewed allowlist requires of the proof, keyed by :data:`VF_DECISIVE_FIELDS`.

    One mapping, used by ``vf_report`` to judge a proof and by the finder to compare two
    candidates.  The key-set guard is the point: adding a reviewed field here without adding it
    to ``VF_DECISIVE_FIELDS`` would leave the comparison blind to it, so the two cannot drift.
    """

    required = {
        "caseIdentitiesSha256": spec["requiredCaseIdentitiesSha256"],
        "tests": spec["expectedTests"],
        "evidenceStatus": "complete",
        "exitCode": 0,
        "subprocessExitCode": 0,
    }
    if set(required) != set(VF_DECISIVE_FIELDS):
        raise SecurityImportError(
            "the reviewed browser-lane fields and VF_DECISIVE_FIELDS disagree"
        )
    return required


def vf_decisive(proof: dict[str, Any], label: str) -> dict[str, Any]:
    """The decisive fields of one proof, every one of them actually stated.

    A missing field is not "equal by absence": calling two candidates the same evidence on a
    field neither of them states would be a verdict about nothing observed, which is the
    default-value class of fail-open this file has already had to close four times.
    """

    missing = [field for field in VF_DECISIVE_FIELDS if field not in proof]
    if missing:
        raise SecurityImportError(f"{label} proof states no {', '.join(missing)}")
    return {field: proof[field] for field in VF_DECISIVE_FIELDS}


def vf_proof_of_archive(archive: bytes) -> dict[str, Any]:
    """The proof document, read out of the browser lane's artifact rather than from a file.

    A loose JSON is exactly what r1 of this card accepted: the five reviewed values it compares
    are all public (they are in the reviewed allowlist), so anyone could write a passing file.
    The proof has to come from inside the archive whose digest GitHub signed for (#319 F1).
    """

    try:
        with zipfile.ZipFile(BytesIO(archive)) as bundle:
            names = bundle.namelist()
            if VF_PROOF_MEMBER not in names:
                raise SecurityImportError("browser lane artifact carries no proof member")
            for name in names:
                path = PurePosixPath(name)
                if path.is_absolute() or ".." in path.parts or bundle.getinfo(name).is_dir():
                    raise SecurityImportError("browser lane artifact member path is unsafe")
            raw = bundle.read(VF_PROOF_MEMBER)
    except (OSError, zipfile.BadZipFile, KeyError) as exc:
        raise SecurityImportError(
            f"browser lane artifact unreadable: {type(exc).__name__}"
        ) from None
    try:
        proof_text = raw.decode("utf-8")
    except UnicodeError as exc:
        raise SecurityImportError(
            f"browser lane proof unreadable: {type(exc).__name__}"
        ) from None
    return _loads(proof_text, "browser lane proof")


def vf_report(
    archive: bytes,
    run_metadata: dict[str, Any],
    artifact_metadata: dict[str, Any],
    allowlist: dict[str, Any],
    report: dict[str, Any],
    observed_now: datetime,
) -> dict[str, Any]:
    """Adapt the browser lane's own artifact into SEC-VF-001.

    The reviewed allowlist pins the five files that lane runs and the identity hash of the case
    set it must execute, and r1 of this card checked only those -- so a synthetic dict with five
    public values became MEASURED_PASS and the report then *copied the security scan's*
    provenance (#319 F1).  This version binds the report to the browser run and artifact the way
    the scan report is bound to its own: the canonical repository and workflow path, an approved
    opt-in event, a completed successful run, the exact same source head as the scan, the
    artifact's name, its unexpired GitHub digest recomputed over the bytes, and the proof read
    from inside that archive.  ``nodeIds`` is still entailed rather than observed (the
    aggregator compares it with ``requiredNodeIds``, which is a tautology on its own), so the
    binding that matters is the identity hash -- now on top of a verified artifact.
    """

    spec = allowlist["secVf001"]
    source = report["sourceHeadSha"]

    run_id = _numeric(run_metadata.get("id"), "browser lane run id")
    workflow_run = artifact_metadata.get("workflow_run")
    if not isinstance(workflow_run, dict):
        raise SecurityImportError("browser lane artifact workflow_run metadata is missing")
    if run_id != _numeric(workflow_run.get("id"), "browser lane artifact run id"):
        raise SecurityImportError("browser lane artifact belongs to another run")
    repository = run_metadata.get("repository")
    if not isinstance(repository, dict) or repository.get("full_name") != REPOSITORY:
        raise SecurityImportError("browser lane run repository is not canonical")
    workflow = str(run_metadata.get("path", "")).split("@", 1)[0]
    if workflow != spec["workflow"]["path"]:
        raise SecurityImportError("browser lane run is not the reviewed workflow")
    if run_metadata.get("event") not in {"pull_request", "workflow_dispatch"}:
        raise SecurityImportError("browser lane run event is not an approved opt-in trigger")
    if run_metadata.get("status") != "completed" or run_metadata.get("conclusion") != "success":
        raise SecurityImportError("browser lane run did not complete successfully")
    if run_metadata.get("head_sha") != source or workflow_run.get("head_sha") != source:
        raise SecurityImportError("browser lane run is about another source head")
    # The browser run's own head_commit is the second, independent witness of the tree: the
    # scan report's claim was already checked against the scan run's head_commit, and this one
    # must agree with it.  Nothing here is copied from the scan report (#319 r2 F2).
    checkout_tree = _head_commit_tree(run_metadata, "browser lane", source)
    if report["checkoutTreeSha"] != checkout_tree:
        raise SecurityImportError("browser lane run head_commit tree differs from the scan tree")
    if artifact_metadata.get("name") != VF_ARTIFACT_NAME:
        raise SecurityImportError("browser lane artifact name is not the reviewed one")
    if artifact_metadata.get("expired") is not False:
        raise SecurityImportError("browser lane artifact is expired or its state is unknown")
    expires_at = _utc(artifact_metadata.get("expires_at"), "browser lane artifact expiresAt")
    if expires_at <= observed_now.astimezone(timezone.utc):
        raise SecurityImportError("browser lane artifact is expired")
    expected_digest = _digest(artifact_metadata.get("digest"))
    observed_digest = hashlib.sha256(archive).hexdigest()
    if observed_digest != expected_digest:
        raise SecurityImportError("browser lane artifact digest differs from GitHub metadata")

    proof = vf_proof_of_archive(archive)
    decisive = vf_decisive(proof, "browser lane")
    for field, expected in vf_required(spec).items():
        if decisive[field] != expected:
            raise SecurityImportError(
                f"browser lane evidence does not satisfy the reviewed {field}"
            )
    files = [spec["runner"], spec["workflow"], spec["nodeDependencyResolver"], *spec["testFiles"]]
    return {
        "threatId": VF_THREAT_ID,
        # This report's provenance is the browser run's own, not the scan's: the only thing the
        # two share is the source head, and that is checked above rather than copied.
        "sourceRunId": run_id,
        "sourceHeadSha": source,
        # Recorded from the verified head_commit tree, not from the scan report.
        "checkoutTreeSha": checkout_tree,
        "vfArtifact": {
            "repository": REPOSITORY,
            "workflowPath": spec["workflow"]["path"],
            "runId": run_id,
            "artifactId": _numeric(artifact_metadata.get("id"), "browser lane artifact id"),
            "artifactName": VF_ARTIFACT_NAME,
            "digest": expected_digest,
            "observedDigest": observed_digest,
            "expiresAt": expires_at.isoformat().replace("+00:00", "Z"),
            "runConclusion": "success",
            "proofSha256": hashlib.sha256(
                json.dumps(proof, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
        },
        "toolFiles": [dict(row) for row in files],
        "nodeIds": list(spec["requiredNodeIds"]),
        "exitCode": decisive["exitCode"],
        "subprocessExitCode": decisive["subprocessExitCode"],
        "evidenceStatus": decisive["evidenceStatus"],
        "caseIdentitiesSha256": decisive["caseIdentitiesSha256"],
        "tests": dict(decisive["tests"]),
    }


def admissible_reports(
    reports: list[dict[str, Any]], allowlist: dict[str, Any], now: datetime
) -> tuple[list[dict[str, Any]], list[str]]:
    """Keep the reports the canonical evaluators can admit, and name the ones they cannot.

    The evaluators are the aggregator's own -- this importer does not keep a second opinion
    about what a threat report means (#313 r2).  A report the evaluator calls INVALID_RUN is
    dropped with its name: carrying it would force the envelope's verdict to INVALID_RUN, and
    an envelope that refuses itself tells an operator less than an envelope that says which
    report could not be admitted and why.
    """

    evaluators = {
        DEFINER_THREAT_ID: lambda row: evaluate_definer(row, allowlist),
        RLS_THREAT_ID: lambda row: evaluate_rls(row, allowlist, now),
        VF_THREAT_ID: lambda row: evaluate_vf(row, allowlist),
    }
    kept: list[dict[str, Any]] = []
    refused: list[str] = []
    for row in reports:
        threat_id = str(row.get("threatId"))
        evaluate = evaluators.get(threat_id)
        if evaluate is None:
            kept.append(row)
            continue
        try:
            verdict = evaluate(row)
        except Exception:  # noqa: BLE001 - an evaluator refusal is a refusal, not a crash
            verdict = Verdict.INVALID_RUN
        if verdict in ADMISSIBLE_REPORT_VERDICTS:
            kept.append(row)
        else:
            refused.append(f"{threat_id} ({verdict.value})")
    return kept, refused


def axis_envelope(
    report: dict[str, Any],
    *,
    expected_digest: str,
    observed_digest: str,
    expires_at: datetime,
    scan_artifact: dict[str, Any],
    extra_reports: tuple[dict[str, Any], ...] = (),
    now: datetime | None = None,
) -> dict[str, Any]:
    """Adapt the validated producer reports into an admissible AC-11 axis envelope.

    Everything the aggregator binds -- the artifact digests, the clean checkout, the run
    conclusion, the reviewed target registry -- is already measured above; this function
    arranges it in the shape ``aggregate_ac11_evidence`` accepts and decides the one thing the
    arrangement cannot borrow: the verdict.

    Card 221 changes where that verdict comes from.  Until now this importer could recompute
    SEC-SCAN-001 only and refused to carry any other threat report, because guessing a verdict
    for a measurement it could not check is how an empty scan becomes a pass (#313 F-R2).  The
    other three reports now exist, and the right answer is not a second opinion about them but
    **the aggregator's own evaluators**: ``evaluate_definer``, ``evaluate_rls`` and
    ``evaluate_vf`` decide what each report means, exactly as they will when the aggregator
    reads the envelope, and a report they refuse is dropped by name rather than carried.
    """

    reports = _threat_reports(report)
    reports = [*reports, *extra_reports]
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
    allowlist = _reviewed_allowlist()
    observed_now = now or datetime.now(timezone.utc)
    reports, refused = admissible_reports(reports, allowlist, observed_now)
    present = {str(row["threatId"]) for row in reports}
    missing = [threat for threat in REQUIRED_THREAT_IDS if threat not in present]
    verdicts = {SCAN_THREAT_ID: Verdict(scan_verdict)}
    for row in reports:
        threat_id = str(row["threatId"])
        if threat_id == SCAN_THREAT_ID:
            continue
        if threat_id == DEFINER_THREAT_ID:
            verdicts[threat_id] = evaluate_definer(row, allowlist)
        elif threat_id == RLS_THREAT_ID:
            verdicts[threat_id] = evaluate_rls(row, allowlist, observed_now)
        elif threat_id == VF_THREAT_ID:
            verdicts[threat_id] = evaluate_vf(row, allowlist)
    # The aggregator's own order of precedence: a missing report is an unobserved axis however
    # well the present ones did, and a measured failure outranks an unobserved one.
    if missing:
        verdict = Verdict.NOT_OBSERVED
    elif Verdict.MEASURED_FAIL in verdicts.values():
        verdict = Verdict.MEASURED_FAIL
    elif Verdict.NOT_OBSERVED in verdicts.values():
        verdict = Verdict.NOT_OBSERVED
    else:
        verdict = Verdict.MEASURED_PASS
    details = []
    if missing:
        details.append("no admissible report for " + ", ".join(missing))
    if refused:
        details.append("refused by the canonical evaluator: " + ", ".join(refused))
    for threat_id, value in sorted(verdicts.items()):
        if value is not Verdict.MEASURED_PASS:
            line = f"{threat_id} recomputes {value.value}"
            if threat_id == SCAN_THREAT_ID and scan_detail:
                line += f" ({scan_detail})"
            details.append(line)
    verdict = verdict.value
    reason = "; ".join(details) if details else None
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
        "threatReportVerdicts": {key: value.value for key, value in sorted(verdicts.items())},
        "cleanup": report.get("cleanup", {"residueCount": 0}),
        "scanArtifact": scan_artifact,
        "importerFile": _bound_importer(report),
        "scanRecomputed": scan_verdict,
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
    parser.add_argument(
        "--vf-archive",
        type=Path,
        default=None,
        help="the browser lane's artifact zip, for SEC-VF-001",
    )
    parser.add_argument("--vf-run-metadata", type=Path, default=None)
    parser.add_argument("--vf-artifact-metadata", type=Path, default=None)
    parser.add_argument(
        "--vf-evidence",
        type=Path,
        default=None,
        help=(
            "an ac11-vf-evidence:1 document naming the browser lane archive and its two "
            "metadata files; what the AC-11 aggregate lane passes (card 233)"
        ),
    )
    args = parser.parse_args(argv)
    try:
        individual = (args.vf_archive, args.vf_run_metadata, args.vf_artifact_metadata)
        if args.vf_evidence is not None and any(value is not None for value in individual):
            # Two ways to say the same thing, differing: the caller would not know which one
            # was used, and neither would the envelope.
            raise SecurityImportError(
                "--vf-evidence and the individual --vf-* inputs are alternatives, not both"
            )
        if args.vf_evidence is not None:
            vf_archive, vf_run, vf_artifact = vf_evidence_inputs(args.vf_evidence)
        else:
            vf_archive = args.vf_archive.read_bytes() if args.vf_archive is not None else None
            vf_run = (
                _json(args.vf_run_metadata, "browser lane run metadata")
                if args.vf_run_metadata is not None
                else None
            )
            vf_artifact = (
                _json(args.vf_artifact_metadata, "browser lane artifact metadata")
                if args.vf_artifact_metadata is not None
                else None
            )
        archive = args.archive.read_bytes()
        result = import_evidence(
            archive,
            _json(args.run_metadata, "run metadata"),
            _json(args.artifact_metadata, "artifact metadata"),
            vf_archive=vf_archive,
            vf_run_metadata=vf_run,
            vf_artifact_metadata=vf_artifact,
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
