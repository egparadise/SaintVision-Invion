"""The AC-11 aggregation's missing input, and what it refuses.

``tools/aggregate_ac11_evidence.py`` recomputes all eight axes and nothing has ever called
it -- the 48-task rescore reports the recomputed PASS count as 0/8 for that reason, which is
a statement about there being no CI path and not about the axes failing. These tests cover
the assembler that makes the call possible, and they are mostly about refusals: an
assembler that quietly dropped an axis would turn the aggregator's INVALID_RUN into a
smaller-looking verdict over fewer axes.

The one test that is not about a refusal is the shipped file: the axis map has to describe
the tree as it actually is, including the four axes that cannot be collected at all.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from tools import assemble_ac11_manifest as assembler
from tools.aggregate_ac11_evidence import AXIS_PURPOSE, REQUIRED_AXES, RUN_PURPOSE, SCHEMA_VERSION

SHA = "a" * 40
OTHER = "b" * 40
NOW = dt.datetime(2026, 10, 2, tzinfo=dt.timezone.utc)


def envelope(axis: str, **overrides):
    document = {
        "axis": axis,
        "runPurpose": AXIS_PURPOSE,
        "sourceRunId": "36851875128",
        "sourceHeadSha": SHA,
        "checkoutTreeSha": "c" * 40,
        "artifactSha256": "d" * 64,
        "artifactObservedSha256": "d" * 64,
        "artifactAvailable": True,
        "artifactExpiresAt": "2099-12-30T10:52:59Z",
        "cleanCheckout": True,
        "runConclusion": "success",
        "verdict": "MEASURED_PASS",
    }
    document.update(overrides)
    return document


def write(directory: Path, name: str, document) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / name
    target.write_text(json.dumps(document), encoding="utf-8")
    return target


def sources(**overrides):
    """A minimal valid axis map: one complete chain, the rest absent with reasons."""
    axes = []
    for index, axis in enumerate(REQUIRED_AXES):
        complete = index == 0
        axes.append({
            "axis": axis,
            "chain": "complete" if complete else "absent",
            "workflow": ".github/workflows/ac11-security-scan.yml" if complete else None,
            "producer": "tools/run_ac11_security_scan.py" if complete else None,
            "importer": "tools/import_ac11_security_scan.py" if complete else None,
            "importerArchiveFlag": "--archive" if complete else None,
            "artifactNamePrefix": "s11-ac11-security-" if complete else None,
            "envelopeMember": "s11-ac11-security-scan.json" if complete else None,
            "importerEmitsAxes": [axis] if complete else [],
            "reason": None if complete else "no producer exists",
        })
    document = {"schemaVersion": assembler.SOURCES_SCHEMA, "axes": axes}
    document.update(overrides)
    return document


def sources_file(tmp_path: Path, document=None) -> Path:
    target = tmp_path / "sources.json"
    target.write_text(json.dumps(document if document is not None else sources()), encoding="utf-8")
    return target


def assemble(tmp_path: Path, *, envelopes=None, document=None, release=SHA):
    loaded = assembler.load_sources(sources_file(tmp_path, document))
    directory = tmp_path / "envelopes"
    directory.mkdir(exist_ok=True)
    for name, body in (envelopes or {}).items():
        write(directory, name, body)
    found = assembler.read_envelopes(directory)
    return assembler.assemble(sources=loaded, envelopes=found, release_sha=release, now=NOW)


# --- what it assembles ------------------------------------------------------------------


def test_an_envelope_at_the_right_sha_goes_into_the_manifest(tmp_path):
    axis = REQUIRED_AXES[0]
    manifest, absent = assemble(tmp_path, envelopes={"one.json": envelope(axis)})
    assert manifest["schemaVersion"] == SCHEMA_VERSION
    assert manifest["runPurpose"] == RUN_PURPOSE
    assert manifest["releaseSha"] == SHA
    assert [row["axis"] for row in manifest["axes"]] == [axis]
    # Seven absent axes, each named with its reason rather than silently dropped.
    assert len(absent) == len(REQUIRED_AXES) - 1
    assert all(": " in line for line in absent)


def test_every_absent_axis_is_named_with_a_reason(tmp_path):
    manifest, absent = assemble(tmp_path)
    assert manifest["axes"] == []
    assert len(absent) == len(REQUIRED_AXES)
    for axis in REQUIRED_AXES:
        assert any(line.startswith(axis) for line in absent), axis


def test_a_complete_chain_with_no_envelope_says_what_to_dispatch(tmp_path):
    """An instruction, not a blocker: the lane simply has not collected it yet."""
    _manifest, absent = assemble(tmp_path)
    first = next(line for line in absent if line.startswith(REQUIRED_AXES[0]))
    assert "dispatch" in first and "ac11-security-scan.yml" in first


# --- what it refuses --------------------------------------------------------------------


def test_an_envelope_about_another_sha_is_refused(tmp_path):
    with pytest.raises(assembler.Refused) as refused:
        assemble(tmp_path, envelopes={"one.json": envelope(REQUIRED_AXES[0], sourceHeadSha=OTHER)})
    assert "not the SHA being aggregated" in str(refused.value)


def test_an_envelope_whose_digest_does_not_match_is_refused(tmp_path):
    with pytest.raises(assembler.Refused) as refused:
        assemble(tmp_path, envelopes={
            "one.json": envelope(REQUIRED_AXES[0], artifactObservedSha256="e" * 64)
        })
    assert "downloaded artifact digest does not match" in str(refused.value)


def test_an_expired_artifact_is_refused(tmp_path):
    with pytest.raises(assembler.Refused) as refused:
        assemble(tmp_path, envelopes={
            "one.json": envelope(REQUIRED_AXES[0], artifactExpiresAt="2020-01-01T00:00:00Z")
        })
    assert "expired" in str(refused.value)


def test_an_unavailable_artifact_is_refused(tmp_path):
    with pytest.raises(assembler.Refused) as refused:
        assemble(tmp_path, envelopes={
            "one.json": envelope(REQUIRED_AXES[0], artifactAvailable=False)
        })
    assert "unavailable" in str(refused.value)


def test_two_envelopes_for_one_axis_are_refused(tmp_path):
    axis = REQUIRED_AXES[0]
    with pytest.raises(assembler.Refused) as refused:
        assemble(tmp_path, envelopes={"one.json": envelope(axis), "two.json": envelope(axis)})
    assert "two envelopes claim axis" in str(refused.value)


def test_an_envelope_for_an_unknown_axis_is_refused(tmp_path):
    with pytest.raises(assembler.Refused) as refused:
        assemble(tmp_path, envelopes={"one.json": envelope("invented-axis")})
    assert "which AC-11 does not have" in str(refused.value)


def test_a_file_that_is_not_an_axis_envelope_is_ignored(tmp_path):
    """The directory can hold the producer's own report beside the importer's output."""
    manifest, _absent = assemble(tmp_path, envelopes={
        "report.json": {"runPurpose": "something-else", "axis": None},
        "one.json": envelope(REQUIRED_AXES[0]),
    })
    assert [row["axis"] for row in manifest["axes"]] == [REQUIRED_AXES[0]]


def test_a_duplicate_json_key_is_refused(tmp_path):
    directory = tmp_path / "envelopes"
    directory.mkdir()
    (directory / "one.json").write_text('{"axis": "a", "axis": "b"}', encoding="utf-8")
    with pytest.raises(assembler.Refused) as refused:
        assembler.read_envelopes(directory)
    assert "duplicate JSON key 'axis'" in str(refused.value)


def test_a_release_sha_that_is_not_a_commit_is_refused(tmp_path):
    with pytest.raises(assembler.Refused) as refused:
        assemble(tmp_path, release="abc")
    assert "must be a full 40-hex commit" in str(refused.value)


# --- the axis map itself ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (lambda d: d.__setitem__("schemaVersion", "ac11-axis-sources:2"), "schemaVersion"),
        (lambda d: d["axes"].__setitem__(0, {**d["axes"][0], "extra": 1}), "key set is not exact"),
        (lambda d: d["axes"][0].pop("reason"), "key set is not exact"),
        (lambda d: d["axes"].__setitem__(0, {**d["axes"][0], "axis": "invented"}), "is not an AC-11 axis"),
        (lambda d: d["axes"].append(dict(d["axes"][0])), "twice"),
        (lambda d: d["axes"][0].__setitem__("chain", "probably"), "chain is"),
        (lambda d: d["axes"][1].__setitem__("reason", "  "), "must give a reason"),
        (lambda d: d["axes"][0].__setitem__("importer", "tools/does-not-exist.py"), "is not in the tree"),
        (lambda d: d["axes"][0].__setitem__("workflow", ".github/workflows/nope.yml"), "is not in the tree"),
        (lambda d: d["axes"][0].__setitem__("importerArchiveFlag", "--zip"), "importerArchiveFlag"),
        (lambda d: d["axes"][0].__setitem__("artifactNamePrefix", ""), "needs artifactNamePrefix"),
        (lambda d: d.__setitem__("axes", []), "non-empty axes list"),
        (lambda d: d["axes"].pop(0), "do not cover"),
    ],
)
def test_an_axis_map_that_cannot_be_trusted_is_refused(tmp_path, mutate, expected):
    document = sources()
    mutate(document)
    with pytest.raises(assembler.Refused) as refused:
        assembler.load_sources(sources_file(tmp_path, document))
    assert expected in str(refused.value)


def test_a_duplicate_key_in_the_axis_map_is_refused(tmp_path):
    target = tmp_path / "sources.json"
    target.write_text('{"schemaVersion": "x", "schemaVersion": "y"}', encoding="utf-8")
    with pytest.raises(assembler.Refused) as refused:
        assembler.load_sources(target)
    assert "duplicate JSON key 'schemaVersion'" in str(refused.value)


# --- the shipped map describes this tree ------------------------------------------------


def test_the_shipped_axis_map_covers_every_axis_and_loads():
    axes = assembler.load_sources(assembler.DEFAULT_SOURCES)
    assert {entry["axis"] for entry in axes} == set(REQUIRED_AXES)


def test_the_shipped_axis_map_is_honest_about_what_cannot_be_collected():
    """Measured from the tree, not asserted: three chains are complete today.

    The security scan and the migration rehearsal have producer, workflow and importer.
    Accessibility has a producer and a workflow but no importer, so its envelope cannot
    carry the artifact binding the aggregator requires. Long-soak has producer and importer
    and no workflow. The remaining three are external.
    """
    axes = {entry["axis"]: entry for entry in assembler.load_sources(assembler.DEFAULT_SOURCES)}
    complete = {axis for axis, entry in axes.items() if entry["chain"] == "complete"}
    assert complete == {
        "migration-reversible-segment",
        "irreversible-restore-forward",
        "security-critical-high-zero",
    }
    assert axes["accessibility-e2e"]["chain"] == "incomplete"
    assert axes["accessibility-e2e"]["importer"] is None
    assert axes["long-soak"]["chain"] == "incomplete"
    assert axes["long-soak"]["workflow"] is None
    for axis in ("actual-pitr-rpo-rto-retention", "physical-five-node-ac05-placement-load",
                 "physical-five-node-failure-recovery"):
        assert axes[axis]["chain"] == "absent"
        assert axes[axis]["producer"] is None
        assert axes[axis]["reason"].strip()
    # Every incomplete or absent axis says which external thing or missing link is in the
    # way. That text is what makes the aggregator's INVALID_RUN legible.
    for entry in axes.values():
        if entry["chain"] != "complete":
            assert len(entry["reason"]) > 40, entry["axis"]


def test_the_shipped_map_names_tools_that_exist():
    for entry in assembler.load_sources(assembler.DEFAULT_SOURCES):
        for field in ("producer", "importer", "workflow"):
            value = entry[field]
            if value:
                assert (assembler.REPO_ROOT / value).is_file(), (entry["axis"], field, value)


def test_the_aggregation_of_this_tree_cannot_be_valid_yet(tmp_path):
    """The honest consequence, stated as a test rather than as a hope.

    Five axes have no admissible envelope, so the aggregator will refuse. This test exists
    so that the day someone makes it possible, this assertion is what changes.
    """
    axes = assembler.load_sources(assembler.DEFAULT_SOURCES)
    manifest, absent = assembler.assemble(
        sources=axes, envelopes={}, release_sha=SHA, now=NOW
    )
    assert manifest["axes"] == []
    assert len(absent) == 8


# --- the lane, and why it owes no landing lane ------------------------------------------


def test_the_aggregate_workflow_is_dispatch_only_and_so_owes_no_landing_lane():
    """The reverse ratchet in ``test_post_landing_verify.py`` makes this a real question.

    Every workflow that can be reached by a push to the integration ref must have a lane in
    ``tools/post_landing_verify.py``, or the landing proof silently covers fewer lanes than
    it claims. This one is dispatch-only, so it owes no lane -- and it is dispatch-only for
    a reason rather than for convenience: it reads the *other* lanes' artifacts, so it has
    nothing to say until they have run, and the aggregation is about one exact SHA.

    Asserted here rather than by adding the file to ``DISPATCH_ONLY_WORKFLOWS``, which is
    the exception list for workflows that *do* have lanes; that list warns in its own test
    against becoming a parking lot for omissions.
    """
    import yaml

    document = yaml.safe_load(
        (assembler.REPO_ROOT / ".github/workflows/ac11-aggregate.yml").read_text(encoding="utf-8")
    )
    # YAML 1.1 turns the key `on` into True, which is why this reads it by that key.
    triggers = document[True]
    assert set(triggers) == {"workflow_dispatch"}
    assert set(triggers["workflow_dispatch"]["inputs"]) == {"source_sha", "correlation_id"}
    assert triggers["workflow_dispatch"]["inputs"]["source_sha"]["required"] is True
    # Least privilege, and `actions: read` is the whole reason it is a separate lane.
    assert document["permissions"] == {"contents": "read", "actions": "read"}


def test_the_lane_reads_the_axis_map_rather_than_hardcoding_the_axes():
    """A lane with its own copy of the axis list is a second axis list."""
    text = (assembler.REPO_ROOT / ".github/workflows/ac11-aggregate.yml").read_text(encoding="utf-8")
    assert "docs/ac11-axis-sources.json" in text
    assert "tools/assemble_ac11_manifest.py" in text
    assert "tools/aggregate_ac11_evidence.py" in text
    for axis in REQUIRED_AXES:
        assert axis not in text, f"the lane names {axis} instead of reading it"
