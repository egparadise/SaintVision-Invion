# -*- coding: utf-8 -*-
"""Self-tests for tools/find_ac11_vf_evidence.py (card 233).

The tool's whole job is "one piece of evidence, downloaded" -- the verification of that candidate
belongs to the importer and is tested there.  So these tests pin two things: the selection never
picks between candidates that disagree (and never calls a missing field agreement), and ``main``
writes an exact document or explains itself with a distinguishable exit code.  ``gh`` is answered
in-process (``answers`` says why that rather than a shim on PATH), because what is being tested is
this tool's reading of those answers.
"""

from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from io import BytesIO
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
    """One run as ``GET /repos/{repo}/actions/runs`` returns it, including its ``path``."""

    row = {
        "id": RUN_ID,
        "head_sha": SOURCE,
        "path": WORKFLOW,
        "status": "completed",
        "conclusion": "success",
        "event": "workflow_dispatch",
    }
    row.update(overrides)
    return row


def runs_payload(*rows, total=None, **overrides) -> dict:
    """One page of that listing: the rows plus the ``total_count`` GitHub states."""

    rows = list(rows)
    if not rows and total is None:
        rows = [run_row()]
    payload = {"total_count": total if total is not None else len(rows), "workflow_runs": rows}
    payload.update(overrides)
    return payload


def one_page(*rows, total=None):
    """A ``fetch(page)`` that serves those rows as page 1 and nothing afterwards."""

    def fetch(page: int):
        if page == 1:
            return runs_payload(*rows, total=total)
        return {"total_count": total if total is not None else len(rows), "workflow_runs": []}

    return fetch


# ---------------------------------------------------------------- population (#332 r3 F2)


def test_the_population_is_every_run_at_that_commit_paged_to_the_end():
    """Two pages, and the candidate is on the second one.

    This is the case the previous call could not see: ``gh run list --limit 50`` returned the
    repository's most recent fifty runs of one workflow and the SHA filter came after, so an older
    conflicting run at the same commit sat outside the window while a newer one sat inside.
    """

    filler = [run_row(id=RUN_ID + 100 + index, path=".github/workflows/core.yml")
              for index in range(100)]
    second_page = [run_row(id=RUN_ID + 1, event="pull_request"), run_row()]

    def fetch(page: int):
        rows = filler if page == 1 else second_page
        return runs_payload(*rows, total=len(filler) + len(second_page))

    rows = finder.runs_at_head(SOURCE, fetch)
    assert len(rows) == 102
    assert finder.candidate_runs(rows, SOURCE, WORKFLOW) == [RUN_ID, RUN_ID + 1], (
        "the conflicting candidate outside the first page is still in the population"
    )


def test_a_population_that_cannot_be_listed_whole_is_a_refusal():
    """GitHub says there are more runs than were listed: a short list is not "no other candidate"."""

    with pytest.raises(finder.NoSingleCandidate, match="could be listed"):
        finder.runs_at_head(SOURCE, one_page(run_row(), total=4))


def test_a_population_larger_than_the_listing_endpoint_is_a_refusal():
    """Past 1000 results the endpoint stops answering, so completeness cannot be proved."""

    total = finder.RUNS_PER_PAGE * finder.MAX_RUN_PAGES + 1
    with pytest.raises(finder.NoSingleCandidate, match="more than the"):
        finder.runs_at_head(SOURCE, one_page(run_row(), total=total))


def test_a_population_that_changes_while_it_is_listed_is_a_refusal():
    """A new run landing mid-listing would make the pages describe two different populations."""

    def fetch(page: int):
        rows = [run_row(id=RUN_ID + index) for index in range(100)]
        return runs_payload(*rows, total=150 if page == 1 else 151)

    with pytest.raises(finder.NoSingleCandidate, match="changed while"):
        finder.runs_at_head(SOURCE, fetch)


@pytest.mark.parametrize(
    ("label", "payload"),
    [
        ("not an object", [run_row()]),
        ("no total", {"workflow_runs": [run_row()]}),
        ("boolean total", {"total_count": True, "workflow_runs": []}),
        ("negative total", {"total_count": -1, "workflow_runs": []}),
        ("no rows list", {"total_count": 1, "workflow_runs": {}}),
    ],
)
def test_a_runs_response_this_tool_cannot_read_is_an_environment_failure(label, payload):
    """Exit 2, not exit 3: an unreadable answer is not the same as "no evidence at this SHA"."""

    with pytest.raises(RuntimeError):
        finder.runs_at_head(SOURCE, lambda _page: payload)


def test_runs_of_another_workflow_at_the_same_commit_are_not_candidates():
    """Every lane runs at this commit; only the reviewed workflow's runs are evidence for it."""

    rows = [run_row(id=RUN_ID + 1, path=".github/workflows/core.yml"), run_row()]
    assert finder.candidate_runs(rows, SOURCE, WORKFLOW) == [RUN_ID]


# ---------------------------------------------------------------- selection

DIGEST = "sha256:" + "1" * 64
OTHER_DIGEST = "sha256:" + "2" * 64


def artifact_row(**overrides) -> dict:
    row = {"id": ARTIFACT_ID, "name": importer.VF_ARTIFACT_NAME, "digest": DIGEST}
    row.update(overrides)
    return row


def artifacts_payload(*rows) -> dict:
    return {"artifacts": list(rows) or [artifact_row()]}


def test_the_successful_runs_at_that_sha_are_the_candidates():
    rows = [run_row(), run_row(id=1, head_sha=OTHER), run_row(id=RUN_ID + 1)]
    assert finder.candidate_runs(rows, SOURCE, WORKFLOW) == sorted([RUN_ID, RUN_ID + 1])


@pytest.mark.parametrize(
    ("label", "rows"),
    [
        ("none", []),
        ("another head", [run_row(head_sha=OTHER)]),
        ("still running", [run_row(status="in_progress", conclusion=None)]),
        ("failed", [run_row(conclusion="failure")]),
        ("unapproved event", [run_row(event="push")]),
    ],
)
def test_no_candidate_at_this_sha_is_an_answer(label, rows):
    """Zero is "there is no evidence here" -- the lane continues and the report is named absent."""

    with pytest.raises(finder.NoSingleCandidate, match="no successful"):
        finder.candidate_runs(rows, SOURCE, WORKFLOW)


@pytest.mark.parametrize("bad", [0, True, "36982827634", None])
def test_a_run_without_a_usable_id_is_refused(bad):
    with pytest.raises(finder.NoSingleCandidate):
        finder.candidate_runs([run_row(id=bad)], SOURCE, WORKFLOW)


@pytest.mark.parametrize(
    ("label", "payload"),
    [
        ("none", {"artifacts": []}),
        ("another name", {"artifacts": [artifact_row(name="something-else")]}),
        ("two of the same name",
         {"artifacts": [artifact_row(), artifact_row(id=ARTIFACT_ID + 1)]}),
        ("no usable id", {"artifacts": [artifact_row(id=0)]}),
    ],
)
def test_artifact_selection_refuses_anything_but_one(label, payload):
    with pytest.raises(finder.NoSingleCandidate):
        finder.select_artifact(payload, importer.VF_ARTIFACT_NAME)


# The run-local halves of a real proof: a fresh uuid, two timestamps, the paths built from that
# uuid and the digest of a JUnit file whose durations differ.  Taken from the two runs this rule was
# measured on (36993192700 and 36993193630 at one head), where every decisive field was identical.
RUN_LOCAL = {
    "runId": "bde012dd9bef487b85393885ae2e1251",
    "startedAt": "2026-10-02T10:03:21.600212+00:00",
    "finishedAt": "2026-10-02T10:04:05.428799+00:00",
    "xmlSha256": "921a9c30c25cf3eec1c03aa551a55a5118684808e6d95f97cd004debf4be4c4a",
}
OTHER_RUN_LOCAL = {
    "runId": "f600d69e34dd4083ab879ffe06da6881",
    "startedAt": "2026-10-02T10:03:16.401809+00:00",
    "finishedAt": "2026-10-02T10:04:02.464747+00:00",
    "xmlSha256": "eafd1a45f87c29389b37780d6adab3a290ef3209f3702c9110745458755308ef",
}
DECISIVE = {
    "caseIdentitiesSha256": "c" * 64,
    "tests": {"failure": 0, "error": 0, "skipped": 0, "passed": 6},
    "evidenceStatus": "complete",
    "exitCode": 0,
    "subprocessExitCode": 0,
}
OTHER_DECISIVE = {
    "caseIdentitiesSha256": "d" * 64,
    "tests": {"failure": 1, "error": 0, "skipped": 0, "passed": 5},
    "evidenceStatus": "partial",
    "exitCode": 1,
    "subprocessExitCode": 1,
}


def vf_archive(run_local: dict | None = None, drop: str | None = None, **decisive) -> bytes:
    """A browser-lane artifact carrying one proof, shaped like the real member."""

    proof = {**DECISIVE, **(run_local or RUN_LOCAL), **decisive}
    proof["evidencePath"] = f".work/vf-runs/vf-desktop-browser-ci-{proof['runId']}/proof.json"
    if drop is not None:
        proof.pop(drop)
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as bundle:
        bundle.writestr(importer.VF_PROOF_MEMBER, json.dumps(proof))
    return buffer.getvalue()


def two_candidates(second: bytes, first: bytes | None = None):
    """``(artifacts_of, archive_of)`` for two runs, each with its own artifact and archive."""

    archives = {RUN_ID: first if first is not None else vf_archive(), RUN_ID + 1: second}

    def artifacts_of(run_id: int):
        return artifacts_payload(
            artifact_row(
                id=ARTIFACT_ID + (run_id - RUN_ID),
                digest="sha256:" + hashlib.sha256(archives[run_id]).hexdigest(),
            )
        )

    return artifacts_of, archives.__getitem__


def test_two_runs_that_say_the_same_thing_are_one_piece_of_evidence():
    """Several runs at one head are ordinary; the question is whether they disagree.

    A branch push and a dispatch both run the browser lane, so an "exactly one run" rule dropped
    SEC-VF-001 from the envelope whenever both existed (measured on aggregate run 36993502607).
    Comparing the artifacts' *bytes* would not have helped either -- these two archives have
    different digests, as the real ones do -- so what is compared is what the report asserts, and
    the lowest run id is taken whichever order the candidates arrive in.
    """

    artifacts_of, archive_of = two_candidates(vf_archive(OTHER_RUN_LOCAL))
    assert archive_of(RUN_ID) != archive_of(RUN_ID + 1), "a digest rule would have refused these"
    for order in ([RUN_ID + 1, RUN_ID], [RUN_ID, RUN_ID + 1]):
        run_id, artifact = finder.select_evidence(
            order, artifacts_of, archive_of, importer.VF_ARTIFACT_NAME
        )
        assert run_id == RUN_ID, "the lowest id, so both orderings give one answer"
        assert artifact["id"] == ARTIFACT_ID


@pytest.mark.parametrize("field", sorted(importer.VF_DECISIVE_FIELDS))
def test_two_runs_that_disagree_about_any_decisive_field_are_a_refusal(field):
    """The sweep over what the report asserts: one differing field at a time, each a refusal.

    Each of these is a real disagreement about the browser lane's observation, and picking one
    would be choosing which observation to believe.
    """

    artifacts_of, archive_of = two_candidates(
        vf_archive(OTHER_RUN_LOCAL, **{field: OTHER_DECISIVE[field]})
    )
    with pytest.raises(finder.NoSingleCandidate, match=f"disagree about {field}"):
        finder.select_evidence(
            [RUN_ID, RUN_ID + 1], artifacts_of, archive_of, importer.VF_ARTIFACT_NAME
        )


@pytest.mark.parametrize("field", sorted(importer.VF_DECISIVE_FIELDS))
def test_a_candidate_whose_proof_omits_a_decisive_field_is_a_refusal(field):
    """A field neither candidate states is not agreement -- that is the default-value fail-open."""

    for dropped_from_first in (False, True):
        missing = vf_archive(OTHER_RUN_LOCAL, drop=field)
        artifacts_of, archive_of = (
            two_candidates(vf_archive(OTHER_RUN_LOCAL), first=missing)
            if dropped_from_first
            else two_candidates(missing)
        )
        with pytest.raises(finder.NoSingleCandidate, match=f"states no {field}"):
            finder.select_evidence(
                [RUN_ID, RUN_ID + 1], artifacts_of, archive_of, importer.VF_ARTIFACT_NAME
            )


def test_every_candidate_is_compared_not_just_the_second():
    """Three runs at one head: the third is compared too, so a disagreement there is a refusal.

    Found by mutation -- comparing only ``ordered[1]`` left every later candidate unread, which on
    three runs would have accepted a disagreement the tool had downloaded and never looked at.
    """

    archives = {
        RUN_ID: vf_archive(),
        RUN_ID + 1: vf_archive(OTHER_RUN_LOCAL),
        RUN_ID + 2: vf_archive(OTHER_RUN_LOCAL, evidenceStatus="partial"),
    }

    def artifacts_of(run_id: int):
        return artifacts_payload(artifact_row(id=ARTIFACT_ID + (run_id - RUN_ID)))

    with pytest.raises(finder.NoSingleCandidate, match="disagree about evidenceStatus"):
        finder.select_evidence(
            sorted(archives), artifacts_of, archives.__getitem__, importer.VF_ARTIFACT_NAME
        )

    # ... and when all three agree, the lowest id is still the answer.
    archives[RUN_ID + 2] = vf_archive(OTHER_RUN_LOCAL, **{"runId": "a" * 32})
    run_id, artifact = finder.select_evidence(
        sorted(archives), artifacts_of, archives.__getitem__, importer.VF_ARTIFACT_NAME
    )
    assert (run_id, artifact["id"]) == (RUN_ID, ARTIFACT_ID)


def test_a_later_candidate_must_also_carry_exactly_one_artifact_of_that_name():
    """A candidate whose run holds two artifacts of the reviewed name is not comparable evidence.

    Found by mutation: the first candidate's artifact was selected but the later ones' were not, so
    an ambiguous run reached the comparison through its archive alone.
    """

    def artifacts_of(run_id: int):
        if run_id == RUN_ID:
            return artifacts_payload(artifact_row())
        return artifacts_payload(artifact_row(id=ARTIFACT_ID + 1), artifact_row(id=ARTIFACT_ID + 2))

    archives = {RUN_ID: vf_archive(), RUN_ID + 1: vf_archive(OTHER_RUN_LOCAL)}
    with pytest.raises(finder.NoSingleCandidate, match="exactly 1 artifact"):
        finder.select_evidence(
            [RUN_ID, RUN_ID + 1], artifacts_of, archives.__getitem__, importer.VF_ARTIFACT_NAME
        )


def test_a_single_candidate_is_not_downloaded_to_be_compared_with_itself():
    """The ordinary case stays one list call and one artifacts call; the comparison has no subject."""

    def archive_of(run_id: int):
        raise AssertionError("a single candidate needs no comparison")

    run_id, artifact = finder.select_evidence(
        [RUN_ID], lambda _run: artifacts_payload(), archive_of, importer.VF_ARTIFACT_NAME
    )
    assert (run_id, artifact["id"]) == (RUN_ID, ARTIFACT_ID)


@pytest.mark.parametrize(
    ("label", "forged"),
    [
        ("exitCode false", {"exitCode": False}),
        ("subprocessExitCode false", {"subprocessExitCode": False}),
        ("exitCode 0.0", {"exitCode": 0.0}),
        ("exitCode \"0\"", {"exitCode": "0"}),
        ("tests.failure false", {"tests": {"error": 0, "failure": False, "passed": 6,
                                          "skipped": 0}}),
        ("tests.passed 6.0", {"tests": {"error": 0, "failure": 0, "passed": 6.0, "skipped": 0}}),
        ("evidenceStatus true", {"evidenceStatus": True}),
        ("caseIdentitiesSha256 not a sha", {"caseIdentitiesSha256": "complete"}),
        ("tests not an object", {"tests": [0, 0, 6, 0]}),
        ("tests with an extra key", {"tests": {"error": 0, "failure": 0, "passed": 6,
                                              "skipped": 0, "flaky": 0}}),
    ],
)
def test_a_candidate_whose_decisive_field_has_the_wrong_json_type_is_a_refusal(label, forged):
    """``0 == False`` in Python, so a boolean where a count belongs was "the same evidence".

    Measured by Codex's probe on the previous head: ``ACCEPTED_TYPE_DISAGREEMENT ... 0 == False:
    True`` -- two candidates disagreeing about a field's *type* passed as agreement, and the proof
    that was then chosen carried the boolean into the envelope (#332 r3 F1).  The type is part of
    the value now, checked in the importer's one validator before anything is compared.
    """

    artifacts_of, archive_of = two_candidates(vf_archive(OTHER_RUN_LOCAL, **forged))
    with pytest.raises(finder.NoSingleCandidate, match="not a JSON integer|not a non-empty string"
                                                      "|not a 64-character|not an object"
                                                      "|keys are not exactly"):
        finder.select_evidence(
            [RUN_ID, RUN_ID + 1], artifacts_of, archive_of, importer.VF_ARTIFACT_NAME
        )


def test_a_candidate_whose_archive_carries_no_proof_is_a_refusal():
    """An archive without the proof member is not evidence to compare, and not a crash either."""

    artifacts_of, archive_of = two_candidates(BytesIO(b"PK-not-a-zip").getvalue())
    with pytest.raises(finder.NoSingleCandidate, match="unreadable|no proof member"):
        finder.select_evidence(
            [RUN_ID, RUN_ID + 1], artifacts_of, archive_of, importer.VF_ARTIFACT_NAME
        )


def test_the_artifact_name_comes_from_the_importer_not_from_this_tool():
    """One definition of the browser lane's artifact name, not two."""

    assert finder.select_artifact(artifacts_payload(), importer.VF_ARTIFACT_NAME)["id"] == ARTIFACT_ID
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
        "runs": runs_payload(),
        "artifacts": {"artifacts": [{"id": ARTIFACT_ID, "name": importer.VF_ARTIFACT_NAME,
                                     "digest": DIGEST}]},
        # Optional per-run and per-artifact answers, for the two-candidate case.
        "artifactsByRun": {},
        "zipByArtifact": {},
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
        if args[0] == "api" and args[1] == "-X":
            page = int([arg for arg in args if arg.startswith("page=")][0].split("=", 1)[1])
            payload = state["runs"]
            if page == 1:
                return json.dumps(payload)
            return json.dumps({"total_count": payload["total_count"], "workflow_runs": []})
        if args[0] == "api" and args[1].endswith("/artifacts"):
            run = int(args[1].rsplit("/", 2)[-2])
            return json.dumps(state["artifactsByRun"].get(run, state["artifacts"]))
        if args[0] == "api" and "/actions/runs/" in args[1]:
            return json.dumps(state["runMetadata"])
        if args[0] == "api" and "/actions/artifacts/" in args[1]:
            return json.dumps(state["artifactMetadata"])
        raise AssertionError(f"unexpected gh call {args}")

    def fake_gh_bytes(*args: str) -> bytes:
        calls.append(args)
        artifact = int(args[1].rsplit("/", 2)[-2])
        archive = state["zipByArtifact"].get(artifact, state["zip"])
        if archive is None:
            raise RuntimeError("gh returned no bytes")
        return archive

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
    # The call contract: the source SHA is in the *query*, not a filter applied to a short window.
    assert calls[0][:4] == ("api", "-X", "GET", f"repos/{importer.REPOSITORY}/actions/runs")
    assert f"head_sha={SOURCE}" in calls[0]
    assert f"per_page={finder.RUNS_PER_PAGE}" in calls[0]


def test_main_takes_the_lower_of_two_agreeing_runs_and_downloads_its_archive_once(
    tmp_path, monkeypatch
):
    """End to end on the case the lane actually hit: a push run and a dispatch run at one head.

    Both are successful runs of the reviewed workflow at the same SHA, their proofs agree on every
    decisive field, and their archives differ byte-wise as the real ones do.  The document names the
    lower run, and the archive it compared is the archive it writes -- one download, not two.
    """

    first, second = vf_archive(), vf_archive(OTHER_RUN_LOCAL)
    state = answers(
        runs=runs_payload(run_row(event="pull_request", id=RUN_ID + 1), run_row()),
        artifactsByRun={
            RUN_ID: {"artifacts": [{"id": ARTIFACT_ID, "name": importer.VF_ARTIFACT_NAME}]},
            RUN_ID + 1: {"artifacts": [{"id": ARTIFACT_ID + 1,
                                        "name": importer.VF_ARTIFACT_NAME}]},
        },
        zipByArtifact={ARTIFACT_ID: first, ARTIFACT_ID + 1: second},
    )
    calls = patched(monkeypatch, state)
    out = tmp_path / "out"
    assert finder.main(["--source-sha", SOURCE, "--out-dir", str(out)]) == 0
    document = json.loads((out / finder.DOCUMENT_NAME).read_text(encoding="utf-8"))
    assert document["runId"] == str(RUN_ID) and document["artifactId"] == str(ARTIFACT_ID)
    assert (out / finder.ARCHIVE_NAME).read_bytes() == first
    downloads = [args for args in calls if args[1].endswith("/zip")]
    assert len(downloads) == 2, "one per candidate, and the chosen one is not fetched twice"


def test_main_refuses_two_runs_that_disagree_without_losing_the_reason(tmp_path, monkeypatch, capsys):
    """Exit 3 with the reason: the lane records SEC-VF-001 as NOT_OBSERVED rather than guessing."""

    state = answers(
        runs=runs_payload(run_row(event="pull_request", id=RUN_ID + 1), run_row()),
        artifactsByRun={
            RUN_ID: {"artifacts": [{"id": ARTIFACT_ID, "name": importer.VF_ARTIFACT_NAME}]},
            RUN_ID + 1: {"artifacts": [{"id": ARTIFACT_ID + 1,
                                        "name": importer.VF_ARTIFACT_NAME}]},
        },
        zipByArtifact={
            ARTIFACT_ID: vf_archive(),
            ARTIFACT_ID + 1: vf_archive(OTHER_RUN_LOCAL, exitCode=1),
        },
    )
    patched(monkeypatch, state)
    out = tmp_path / "out"
    assert finder.main(["--source-sha", SOURCE, "--out-dir", str(out)]) == 3
    assert "disagree about exitCode" in capsys.readouterr().err
    assert not (out / finder.DOCUMENT_NAME).exists()


@pytest.mark.parametrize(
    ("label", "overrides"),
    [
        ("no run at this sha", {"runs": runs_payload(run_row(head_sha=OTHER))}),
        ("no run at all", {"runs": runs_payload(total=0)}),
        ("no artifact of that name", {"artifacts": {"artifacts": []}}),
        ("two artifacts of that name",
         {"artifacts": {"artifacts": [{"id": ARTIFACT_ID, "name": importer.VF_ARTIFACT_NAME,
                                      "digest": DIGEST},
                                      {"id": ARTIFACT_ID + 1,
                                       "name": importer.VF_ARTIFACT_NAME,
                                       "digest": DIGEST}]}}),
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
