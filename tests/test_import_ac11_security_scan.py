"""PG-free trust-boundary tests for the AC-11 security artifact importer."""

from __future__ import annotations

import copy
import hashlib
import io
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import import_ac11_security_scan as tool  # noqa: E402


SOURCE = "a" * 40
RUN_ID = "36443057935"
ARTIFACT_ID = "10978439158"
NOW = datetime(2026, 9, 29, 0, 30, tzinfo=timezone.utc)


def archive(report: dict | None = None, extra: str | None = None) -> bytes:
    # What the producer actually writes: the report *is* the SEC-SCAN-001 threat report, so
    # it carries threatId with the fields the aggregator reads (card 216).  The stub used to
    # stop at the provenance fields, which the importer no longer accepts: an adapter that
    # cannot find a threat report must say so rather than emit an envelope with none.
    report = report or {
        "schemaVersion": "1.0.0",
        "runPurpose": "s11-ac11-security-scan",
        "threatId": "SEC-SCAN-001",
        "sourceRunId": RUN_ID,
        "sourceHeadSha": SOURCE,
        "checkoutTreeSha": "b" * 40,
        "cleanCheckout": True,
        "startedAt": "2026-09-28T15:20:00Z",
        "finishedAt": "2026-09-28T15:22:46Z",
        "environment": {"comparableGroup": "ac11-security-scan-v1"},
        "verdict": "MEASURED_PASS",
        "criticalCount": 0,
        "highCount": 0,
        "unallowlistedFindingIds": [],
        "expiredFindingIds": [],
        "staleAllowlistFindingIds": [],
        "cleanup": {"residueCount": 0},
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as bundle:
        for name, content in (
            (tool.REPORT_MEMBER, json.dumps(report).encode()),
            (tool.JUNIT_MEMBER, b'<testsuite tests="4" failures="0"/>'),
        ):
            info = zipfile.ZipInfo(name, (2026, 9, 28, 15, 22, 46))
            bundle.writestr(info, content)
        if extra is not None:
            bundle.writestr(extra, b"unexpected")
    return output.getvalue()


def metadata(payload: bytes) -> tuple[dict, dict]:
    run = {
        "id": int(RUN_ID),
        "status": "completed",
        "conclusion": "success",
        "head_sha": SOURCE,
        "event": "pull_request",
        "path": f"{tool.WORKFLOW_PATH}@refs/pull/226/merge",
        "repository": {"full_name": tool.REPOSITORY},
    }
    artifact = {
        "id": int(ARTIFACT_ID),
        "name": f"s11-ac11-security-{SOURCE}",
        "expired": False,
        "expires_at": "2026-10-28T15:22:46Z",
        "digest": "sha256:" + hashlib.sha256(payload).hexdigest(),
        "workflow_run": {"id": int(RUN_ID), "head_sha": SOURCE},
    }
    return run, artifact


def test_import_binds_run_artifact_digest_and_member_hashes():
    payload = archive()
    run, artifact = metadata(payload)
    result = tool.import_evidence(payload, run, artifact, now=NOW)
    binding = result["scanArtifact"]
    assert binding["runId"] == RUN_ID
    assert binding["artifactId"] == ARTIFACT_ID
    assert binding["digest"] == hashlib.sha256(payload).hexdigest()
    assert binding["observedDigest"] == binding["digest"]
    assert len(binding["producerReportSha256"]) == 64
    assert len(binding["junitSha256"]) == 64


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda run, artifact: artifact.update(digest="sha256:" + "0" * 64), "digest"),
        (lambda run, artifact: artifact.update(expired=True), "expired"),
        (lambda run, artifact: run.update(conclusion="failure"), "successfully"),
        (lambda run, artifact: run.update(head_sha="f" * 40), "sourceHeadSha"),
        (lambda run, artifact: run.update(id=1), "sourceRunId"),
        (
            lambda run, artifact: run["repository"].update(full_name="fork/example"),
            "canonical",
        ),
        (lambda run, artifact: run.update(path=".github/workflows/other.yml"), "workflow"),
    ],
)
def test_import_rejects_untrusted_github_metadata(mutate, message):
    payload = archive()
    run, artifact = metadata(payload)
    mutate(run, artifact)
    with pytest.raises(tool.SecurityImportError, match=message):
        tool.import_evidence(payload, run, artifact, now=NOW)


def test_import_rejects_missing_source_run_and_non_exact_archive():
    payload = archive({"sourceHeadSha": SOURCE})
    run, artifact = metadata(payload)
    with pytest.raises(tool.SecurityImportError, match="sourceRunId"):
        tool.import_evidence(payload, run, artifact, now=NOW)

    payload = archive(extra="../outside")
    run, artifact = metadata(payload)
    with pytest.raises(tool.SecurityImportError, match="member set"):
        tool.import_evidence(payload, run, artifact, now=NOW)


def test_the_envelope_is_admissible_and_names_the_threat_reports_it_lacks():
    """Card 216: the adapter's verdict is the one the aggregator will recompute.

    Only SEC-SCAN-001 has a producer in this repository.  The aggregator requires four
    threat reports and answers NOT_OBSERVED when any is missing, so the envelope says the
    same thing -- otherwise a partial scan would be read as a pass and the run would be
    INVALID_RUN for contradicting itself.
    """

    payload = archive()
    run_metadata, artifact_metadata = metadata(payload)
    envelope = tool.import_evidence(payload, run_metadata, artifact_metadata, now=NOW)
    assert envelope["runPurpose"] == "ac11-axis-evidence"
    assert envelope["axis"] == "security-critical-high-zero"
    assert envelope["verdict"] == "NOT_OBSERVED"
    assert envelope["reason"] == "no producer emits SEC-DEF-001, SEC-RLS-001, SEC-VF-001"
    assert [row["threatId"] for row in envelope["observations"]] == ["SEC-SCAN-001"]
    assert envelope["targetRef"]["targetId"] == "s11-security-critical-high-zero-v0"
    assert envelope["artifactSha256"] == envelope["artifactObservedSha256"]
    assert envelope["artifactAvailable"] is True


def test_all_four_threat_reports_let_the_producer_verdict_through():
    base = {
        "schemaVersion": "1.0.0",
        "runPurpose": "s11-ac11-security-scan",
        "sourceRunId": RUN_ID,
        "sourceHeadSha": SOURCE,
        "checkoutTreeSha": "b" * 40,
        "cleanCheckout": True,
        "startedAt": "2026-09-28T15:20:00Z",
        "finishedAt": "2026-09-28T15:22:46Z",
        "environment": {"comparableGroup": "ac11-security-scan-v1"},
        "verdict": "MEASURED_PASS",
        "cleanup": {"residueCount": 0},
        "observations": [
            {"threatId": "SEC-DEF-001"}, {"threatId": "SEC-RLS-001"},
            {"threatId": "SEC-VF-001"}, {"threatId": "SEC-SCAN-001"},
        ],
    }
    payload = archive(base)
    run_metadata, artifact_metadata = metadata(payload)
    envelope = tool.import_evidence(payload, run_metadata, artifact_metadata, now=NOW)
    assert envelope["verdict"] == "MEASURED_PASS"
    assert "reason" not in envelope


def test_an_unregistered_threat_id_is_refused_rather_than_carried():
    base = {
        "schemaVersion": "1.0.0",
        "runPurpose": "s11-ac11-security-scan",
        "sourceRunId": RUN_ID,
        "sourceHeadSha": SOURCE,
        "checkoutTreeSha": "b" * 40,
        "cleanCheckout": True,
        "startedAt": "2026-09-28T15:20:00Z",
        "finishedAt": "2026-09-28T15:22:46Z",
        "environment": {"comparableGroup": "ac11-security-scan-v1"},
        "verdict": "MEASURED_PASS",
        "observations": [{"threatId": "SEC-INVENTED-001"}],
    }
    payload = archive(base)
    run_metadata, artifact_metadata = metadata(payload)
    with pytest.raises(tool.SecurityImportError, match="unregistered security threat id"):
        tool.import_evidence(payload, run_metadata, artifact_metadata, now=NOW)
