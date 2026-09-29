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
    report = report or {
        "sourceRunId": RUN_ID,
        "sourceHeadSha": SOURCE,
        "checkoutTreeSha": "b" * 40,
        "cleanCheckout": True,
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
