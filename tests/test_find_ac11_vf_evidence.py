# -*- coding: utf-8 -*-
"""Self-tests for tools/find_ac11_vf_evidence.py (card 233).

The tool's whole job is "exactly one candidate, downloaded" -- the verification of that candidate
belongs to the importer and is tested there.  So these tests pin two things: the selection refuses
zero and refuses two (it never picks), and ``main`` writes an exact document or explains itself
with a distinguishable exit code.  ``gh`` is answered in-process (``answers`` says why that rather
than a shim on PATH), because what is being tested is this tool's reading of those answers.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import find_ac11_vf_evidence as finder  # noqa: E402
import import_ac11_security_scan as importer  # noqa: E402

SOURCE = "a" * 40
OTHER = "b" * 40
RUN_ID = 36982827634
ARTIFACT_ID = 11216720488
WORKFLOW = ".github/workflows/desktop-browser.yml"


def run_row(**overrides) -> dict:
    row = {
        "databaseId": RUN_ID,
        "headSha": SOURCE,
        "status": "completed",
        "conclusion": "success",
        "event": "workflow_dispatch",
    }
    row.update(overrides)
    return row


# ---------------------------------------------------------------- selection


def test_exactly_one_successful_run_is_selected():
    rows = [run_row(), run_row(databaseId=1, headSha=OTHER)]
    assert finder.select_run(rows, SOURCE, WORKFLOW)["databaseId"] == RUN_ID


@pytest.mark.parametrize(
    ("label", "rows"),
    [
        ("none", []),
        ("another head", [run_row(headSha=OTHER)]),
        ("still running", [run_row(status="in_progress", conclusion=None)]),
        ("failed", [run_row(conclusion="failure")]),
        ("unapproved event", [run_row(event="push")]),
        ("two candidates", [run_row(), run_row(databaseId=RUN_ID + 1)]),
        ("no usable id", [run_row(databaseId=0)]),
        ("id is a boolean", [run_row(databaseId=True)]),
    ],
)
def test_selection_refuses_anything_but_one_candidate(label, rows):
    """Zero is an answer and two is a refusal -- neither is a pick.

    The browser lane is dispatched more than once at the same head during a review round, so
    "take the first" would quietly record one of a race as the evidence for an axis.
    """

    with pytest.raises(finder.NoSingleCandidate):
        finder.select_run(rows, SOURCE, WORKFLOW)


@pytest.mark.parametrize(
    ("label", "payload"),
    [
        ("none", {"artifacts": []}),
        ("another name", {"artifacts": [{"id": ARTIFACT_ID, "name": "something-else"}]}),
        ("two of the same name",
         {"artifacts": [{"id": ARTIFACT_ID, "name": importer.VF_ARTIFACT_NAME},
                        {"id": ARTIFACT_ID + 1, "name": importer.VF_ARTIFACT_NAME}]}),
        ("no usable id",
         {"artifacts": [{"id": 0, "name": importer.VF_ARTIFACT_NAME}]}),
    ],
)
def test_artifact_selection_refuses_anything_but_one(label, payload):
    with pytest.raises(finder.NoSingleCandidate):
        finder.select_artifact(payload, importer.VF_ARTIFACT_NAME)


def test_the_artifact_name_comes_from_the_importer_not_from_this_tool():
    """One definition of the browser lane's artifact name, not two."""

    payload = {"artifacts": [{"id": ARTIFACT_ID, "name": importer.VF_ARTIFACT_NAME}]}
    assert finder.select_artifact(payload, importer.VF_ARTIFACT_NAME)["id"] == ARTIFACT_ID
    assert "desktop-browser" in importer.VF_ARTIFACT_NAME


def test_the_document_is_exactly_what_the_importer_requires():
    document = finder.document(RUN_ID, ARTIFACT_ID, WORKFLOW)
    assert set(document) == importer.VF_EVIDENCE_KEYS
    assert document["schemaVersion"] == importer.VF_EVIDENCE_SCHEMA
    assert document["repository"] == importer.REPOSITORY
    assert document["runId"] == str(RUN_ID) and document["artifactId"] == str(ARTIFACT_ID)


# ---------------------------------------------------------------- main, with gh answered in-process


def answers(**overrides) -> dict:
    """What each ``gh`` call returns.  Patched in place of the two CLI helpers.

    In-process rather than a fake executable on PATH: measured while writing this, Windows'
    ``CreateProcess`` only appends ``.exe`` when resolving a bare name, so a ``gh``/``gh.cmd``
    shim on PATH is never reached and the real ``gh.exe`` answers instead -- the run list came
    back empty because it had queried the real repository.  Patching the two helpers tests this
    tool's reading of those answers, which is what these cases are about.
    """

    state = {
        "runs": [run_row()],
        "artifacts": {"artifacts": [{"id": ARTIFACT_ID, "name": importer.VF_ARTIFACT_NAME}]},
        "runMetadata": {"id": RUN_ID, "head_sha": SOURCE},
        "artifactMetadata": {"id": ARTIFACT_ID, "name": importer.VF_ARTIFACT_NAME},
        "zip": b"PK-not-a-real-zip",
    }
    state.update(overrides)
    return state


def patched(monkeypatch, state: dict) -> list[tuple]:
    calls: list[tuple] = []

    def fake_gh(*args: str) -> str:
        calls.append(args)
        if args[:2] == ("run", "list"):
            return json.dumps(state["runs"])
        if args[0] == "api" and args[1].endswith("/artifacts"):
            return json.dumps(state["artifacts"])
        if args[0] == "api" and "/actions/runs/" in args[1]:
            return json.dumps(state["runMetadata"])
        if args[0] == "api" and "/actions/artifacts/" in args[1]:
            return json.dumps(state["artifactMetadata"])
        raise AssertionError(f"unexpected gh call {args}")

    def fake_gh_bytes(*args: str) -> bytes:
        calls.append(args)
        if state["zip"] is None:
            raise RuntimeError("gh returned no bytes")
        return state["zip"]

    monkeypatch.setattr(finder, "_gh", fake_gh)
    monkeypatch.setattr(finder, "_gh_bytes", fake_gh_bytes)
    return calls


def test_main_writes_the_document_and_the_three_files(tmp_path, monkeypatch):
    calls = patched(monkeypatch, answers())
    out = tmp_path / "out"
    assert finder.main(["--source-sha", SOURCE, "--out-dir", str(out)]) == 0
    document = json.loads((out / finder.DOCUMENT_NAME).read_text(encoding="utf-8"))
    assert set(document) == importer.VF_EVIDENCE_KEYS
    assert document["runId"] == str(RUN_ID) and document["artifactId"] == str(ARTIFACT_ID)
    for name in (finder.ARCHIVE_NAME, finder.RUN_METADATA_NAME, finder.ARTIFACT_METADATA_NAME):
        assert (out / name).exists(), name
    # And the importer accepts its own document, which is the point of writing one.
    archive, run_metadata, artifact_metadata = importer.vf_evidence_inputs(
        out / finder.DOCUMENT_NAME
    )
    assert archive == answers()["zip"]
    assert run_metadata["id"] == RUN_ID and artifact_metadata["id"] == ARTIFACT_ID
    assert calls[0][:2] == ("run", "list")


@pytest.mark.parametrize(
    ("label", "overrides"),
    [
        ("no run at this sha", {"runs": [run_row(headSha=OTHER)]}),
        ("two runs at this sha", {"runs": [run_row(), run_row(databaseId=RUN_ID + 1)]}),
        ("no artifact of that name", {"artifacts": {"artifacts": []}}),
        ("two artifacts of that name",
         {"artifacts": {"artifacts": [{"id": ARTIFACT_ID, "name": importer.VF_ARTIFACT_NAME},
                                      {"id": ARTIFACT_ID + 1,
                                       "name": importer.VF_ARTIFACT_NAME}]}}),
    ],
)
def test_main_reports_no_single_candidate_with_exit_3(tmp_path, monkeypatch, label, overrides,
                                                     capsys):
    """Exit 3 is "there is no evidence at this SHA", which the lane continues past.

    The distinction matters: the lane treats 3 as an answer to record and anything else as a tool
    failure worth shouting about, so collapsing them would hide a broken finder behind a missing
    artifact (card 233).
    """

    patched(monkeypatch, answers(**overrides))
    out = tmp_path / "out"
    assert finder.main(["--source-sha", SOURCE, "--out-dir", str(out)]) == 3
    assert "no browser lane evidence" in capsys.readouterr().err
    assert not (out / finder.DOCUMENT_NAME).exists()


def test_a_download_that_fails_is_exit_2_not_a_missing_candidate(tmp_path, monkeypatch, capsys):
    """A broken download is this tool failing, not GitHub having nothing."""

    patched(monkeypatch, answers(zip=None))
    assert finder.main(["--source-sha", SOURCE, "--out-dir", str(tmp_path / "out")]) == 2
    assert "download failed" in capsys.readouterr().err


def test_a_malformed_source_sha_never_reaches_gh(tmp_path, monkeypatch, capsys):
    calls = patched(monkeypatch, answers())
    assert finder.main(["--source-sha", "deadbeef", "--out-dir", str(tmp_path / "out")]) == 2
    assert "40-character lowercase" in capsys.readouterr().err
    assert calls == []
