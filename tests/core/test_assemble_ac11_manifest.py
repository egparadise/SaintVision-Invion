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
from tools import import_ac11_composite_long_soak as long_soak_importer
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


#: What tools/import_ac11_migration_rehearsal.py actually writes. Hard-coded rather than
#: computed from the assembler, so that a change to the importer fails this fixture loudly
#: instead of quietly agreeing with itself (#299 r2).
MIGRATION_AXES = ["migration-reversible-segment", "irreversible-restore-forward"]


def sources(**overrides):
    """A minimal valid axis map: one complete chain, the rest absent with reasons."""
    axes = []
    for index, axis in enumerate(REQUIRED_AXES):
        # The complete chain is the migration rehearsal: its importer really does name its
        # axes, which the strict map now requires (#299 r1).
        complete = axis == "migration-reversible-segment"
        axes.append({
            "axis": axis,
            "chain": "complete" if complete else "absent",
            "workflow": ".github/workflows/ac11-migration-rehearsal.yml" if complete else None,
            "producer": "tools/run_ac11_migration_rehearsal.py" if complete else None,
            "importer": "tools/import_ac11_migration_rehearsal.py" if complete else None,
            "importerArchiveFlag": "--artifact-zip" if complete else None,
            "artifactNamePrefix": "s11-ac11-migration-" if complete else None,
            "envelopeMember": "s11-ac11-migration-rehearsal.json" if complete else None,
            # The exact set, not this row's axis alone: one importer writes both migration
            # axes, and r1's subset rule accepted a row that named only one of them.
            "importerEmitsAxes": list(MIGRATION_AXES) if complete else [],
            "envelopeShape": "axis-evidence" if complete else None,
            "reason": None if complete else "no producer exists",
        })
    document = {
        "schemaVersion": assembler.SOURCES_SCHEMA,
        "purpose": "a fixture axis map",
        "note": "one complete chain, the rest absent with reasons",
        "repository": assembler.REPOSITORY,
        "axes": axes,
    }
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
    assert "dispatch" in first and "ac11-migration-rehearsal.yml" in first


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


def test_a_file_this_tool_cannot_read_is_refused_rather_than_ignored(tmp_path):
    """Changed in r1, and the change is the finding.

    The first version skipped any document whose ``runPurpose`` it did not recognise. That is
    how the migration rehearsal's two axes went missing while its artifact sat in the
    directory: its importer writes a *bundle*, not a single envelope. Ignoring what it cannot
    read is the behaviour that hid it, so an unknown purpose is now a refusal.
    """
    with pytest.raises(assembler.Refused) as refused:
        assemble(tmp_path, envelopes={
            "report.json": {"runPurpose": "something-else", "axis": None},
            "one.json": envelope(REQUIRED_AXES[0]),
        })
    assert "neither an axis envelope nor a bundle" in str(refused.value)


def test_a_bundle_of_axis_envelopes_is_read(tmp_path):
    """The real shape ``tools/import_ac11_migration_rehearsal.py`` writes (#299 r1).

    Its output is one document with ``runPurpose: ac11-migration-rehearsal-import`` and an
    ``axes`` array whose rows are proper axis envelopes. The first version read only single
    envelopes, so an artifact that was present and correct produced nothing.
    """
    bundle = {
        "schemaVersion": "1.0.0",
        "runPurpose": "ac11-migration-rehearsal-import",
        "axes": [envelope("migration-reversible-segment"),
                 envelope("irreversible-restore-forward")],
    }
    manifest, absent = assemble(tmp_path, envelopes={"migration.json": bundle})
    assert sorted(row["axis"] for row in manifest["axes"]) == [
        "irreversible-restore-forward", "migration-reversible-segment",
    ]
    assert len(absent) == len(REQUIRED_AXES) - 2


def test_a_bundle_whose_rows_are_not_axis_envelopes_is_refused(tmp_path):
    bundle = {
        "runPurpose": "ac11-migration-rehearsal-import",
        "axes": [{**envelope(REQUIRED_AXES[0]), "runPurpose": "something-else"}],
    }
    with pytest.raises(assembler.Refused) as refused:
        assemble(tmp_path, envelopes={"migration.json": bundle})
    assert "carries an axes entry whose runPurpose" in str(refused.value)


def test_a_bundle_with_no_axes_array_is_refused(tmp_path):
    with pytest.raises(assembler.Refused) as refused:
        assemble(tmp_path, envelopes={
            "migration.json": {"runPurpose": "ac11-migration-rehearsal-import", "axes": []}
        })
    assert "bundle with no axes array" in str(refused.value)


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
        # The four #299 r1 named, each of which passed before.
        (lambda d: d.__setitem__("unexpected", 1), "top-level key set is not exact"),
        (lambda d: d.__setitem__("repository", "attacker/repo"), "name repository"),
        (lambda d: d["axes"][0].__setitem__("importerEmitsAxes", ["invented-axis"]),
         "names something that is not an axis"),
        (lambda d: d["axes"][0].__setitem__("envelopeMember", "does-not-exist.json"),
         "does not name"),
        # And four more of the same shape.
        (lambda d: d["axes"][0].__setitem__("envelopeShape", "whatever"), "envelopeShape is"),
        (lambda d: d["axes"][0].__setitem__("importerEmitsAxes", ["long-soak"]),
         "does not include this axis"),
        (lambda d: d.__setitem__("purpose", "  "), "must be a non-empty string"),
        (lambda d: d["axes"][0].__setitem__("envelopeShape", "not-an-axis-envelope"),
         "needs an admissible envelopeShape"),
        # The two #299 r2 named: the migration row left with one axis. Both passed r1's
        # subset rule, and each describes half a chain whose importer writes both -- so a
        # bundle carrying two envelopes would be read as if one axis were never claimed.
        (lambda d: d["axes"][0].__setitem__("importerEmitsAxes", ["migration-reversible-segment"]),
         "writes ['irreversible-restore-forward', 'migration-reversible-segment']"),
        (lambda d: d["axes"][0].__setitem__("importerEmitsAxes", ["irreversible-restore-forward"]),
         "does not include this axis"),
        # And two of the same shape: a repeat that would game a length comparison, and a row
        # with no importer claiming its axis is emitted. Nothing emits it -- that is what
        # "no importer" means.
        (lambda d: d["axes"][0].__setitem__(
            "importerEmitsAxes", ["migration-reversible-segment", "migration-reversible-segment"]),
         "repeats an axis"),
        (lambda d: d["axes"][1].__setitem__("importerEmitsAxes", [d["axes"][1]["axis"]]),
         "no importer, so the set must be empty"),
        # #299 r3: a row pointing at a file that exists and is not an AC-11 importer. The
        # path check passes because the file is in the tree; the contract is absent, so this
        # fails closed instead of reading as "emits nothing".
        (lambda d: d["axes"][0].__setitem__("importer", "tools/check_docs.py"),
         "declares no module-level EMITTED_AXES"),
    ],
)
def test_an_axis_map_that_cannot_be_trusted_is_refused(tmp_path, mutate, expected):
    document = sources()
    mutate(document)
    with pytest.raises(assembler.Refused) as refused:
        assembler.load_sources(sources_file(tmp_path, document))
    assert expected in str(refused.value)


def test_emitted_axes_reads_each_importers_declaration():
    """Measured from the three importers' EMITTED_AXES, which is the binding (#299 r3).

    The migration importer declares both of its axes; the security importer declares ``()``
    -- and that emptiness is the finding, not a gap in this check -- which is why that chain
    cannot be complete however many files exist (#299 r1). A row with no importer at all
    emits nothing.
    """
    assert assembler.emitted_axes("tools/import_ac11_migration_rehearsal.py") == set(MIGRATION_AXES)
    # Card 216: this was ``set()`` while the importer returned the producer's report
    # unchanged.  It now adapts that report into an axis envelope, so it declares its axis.
    assert assembler.emitted_axes("tools/import_ac11_security_scan.py") == {
        "security-critical-high-zero"
    }
    assert assembler.emitted_axes("tools/import_ac11_composite_long_soak.py") == {"long-soak"}
    assert assembler.emitted_axes(None) == set()


def test_every_ac11_importer_in_the_tree_declares_the_contract():
    """The contract is shared with other pull requests' importers, so check the tree.

    Any tools/import_ac11_*.py has to declare EMITTED_AXES. A new importer that forgets it
    fails here rather than being read as emitting nothing.
    """
    importers = sorted((assembler.REPO_ROOT / "tools").glob("import_ac11_*.py"))
    assert importers, "no AC-11 importers found, so this test proves nothing"
    for importer in importers:
        assert assembler.emitted_axes(f"tools/{importer.name}") <= set(REQUIRED_AXES), importer.name


# A comment and a docstring are not code. r1/r2 searched the source text for quoted axis
# names, so either of these invented an axis -- and an importer that takes the name from a
# constant, which is the shape #302's accessibility importer uses, read as emitting nothing
# (#299 r3).
DECOYS = [
    ("a comment", '# "accessibility-e2e"\nEMITTED_AXES = ()\n', set()),
    (
        "a docstring",
        '"""This importer writes "long-soak" envelopes."""\nEMITTED_AXES = ()\n',
        set(),
    ),
    (
        "a name the axis comes from",
        'from collector import AXIS\n'
        'EMITTED_AXES: tuple[str, ...] = ("accessibility-e2e",)\n'
        'envelope = {"axis": AXIS}\n',
        {"accessibility-e2e"},
    ),
]


@pytest.mark.parametrize("source,expected", [row[1:] for row in DECOYS],
                         ids=[row[0] for row in DECOYS])
def test_the_declaration_is_what_counts_not_the_text_around_it(source, expected):
    assert assembler.declared_axes(source, "fixture.py") == expected


@pytest.mark.parametrize(
    "source,expected",
    [
        ('# "accessibility-e2e"\nx = 1\n', "declares no module-level EMITTED_AXES"),
        ("def f():\n    EMITTED_AXES = ()\n", "declares no module-level EMITTED_AXES"),
        ('EMITTED_AXES = ()\nEMITTED_AXES = ("long-soak",)\n', "declares EMITTED_AXES 2 times"),
        ("EMITTED_AXES = AXIS\n", "must be a literal tuple or list"),
        ("EMITTED_AXES: tuple[str, ...]\n", "must be a literal tuple or list"),
        ('AXIS = "long-soak"\nEMITTED_AXES = (AXIS,)\n', "must be a string literal"),
        ('EMITTED_AXES = ("nope",)\n', "which AC-11 does not have"),
        ('EMITTED_AXES = ("long-soak", "long-soak")\n', "repeats 'long-soak'"),
        ("EMITTED_AXES = (\n", "does not parse"),
    ],
)
def test_an_unreadable_declaration_is_refused_rather_than_read_as_empty(source, expected):
    """Empty is a legitimate answer here -- security declares ``()`` -- so "I could not read
    the contract" must never collapse into it."""
    with pytest.raises(assembler.Refused) as refused:
        assembler.declared_axes(source, "m.py")
    assert expected in str(refused.value)


def test_the_shipped_map_claims_exactly_what_each_importer_writes():
    """Every row, against its own importer's source. No subsets, no extras."""
    for entry in assembler.load_sources(assembler.DEFAULT_SOURCES):
        assert set(entry["importerEmitsAxes"]) == assembler.emitted_axes(entry["importer"]), (
            entry["axis"]
        )


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
    """Measured from the tree, not asserted: four axes have complete chains today.

    Migration, accessibility and -- since card 216 -- security have admissible importers.
    Long-soak has no workflow and three axes are external.
    """
    axes = {entry["axis"]: entry for entry in assembler.load_sources(assembler.DEFAULT_SOURCES)}
    complete = {axis for axis, entry in axes.items() if entry["chain"] == "complete"}
    # #299 r1 called security complete because producer, workflow and importer all existed,
    # which was wrong: the importer returned the producer's report with no axis field, so
    # there was no admissible envelope. Card 216 wrote that adapter, so security is complete
    # again -- this time because an envelope exists, not because three files do. The axis
    # still does not pass; "complete" is about the chain, not the verdict.
    assert complete == {
        "migration-reversible-segment", "irreversible-restore-forward", "accessibility-e2e",
        "security-critical-high-zero",
    }
    assert all(
        axes[axis]["envelopeShape"] == "axes-bundle"
        for axis in {"migration-reversible-segment", "irreversible-restore-forward"}
    )
    accessibility = axes["accessibility-e2e"]
    assert accessibility["envelopeShape"] == "axis-evidence"
    assert accessibility["importer"] == "tools/import_ac11_accessibility_evidence.py"
    assert accessibility["importerEmitsAxes"] == ["accessibility-e2e"]
    security = axes["security-critical-high-zero"]
    assert security["chain"] == "complete"
    assert security["envelopeShape"] == "axis-evidence"
    assert security["importer"] == "tools/import_ac11_security_scan.py"
    assert security["importerEmitsAxes"] == ["security-critical-high-zero"]
    assert security["reason"] is None
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


def test_the_aggregate_workflow_is_not_reachable_by_a_push_and_so_owes_no_landing_lane():
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
    # No `push`: that is what the reverse ratchet cares about, and it is why this lane owes
    # no entry in LANES. The label-gated `pull_request` trigger exists because a
    # dispatch-only workflow that has never run is not in GitHub's workflow index and cannot
    # be dispatched at all -- measured as `HTTP 404: ... not found on the default branch`
    # (#299 r1). It stays opt-in, so no ordinary pull request spends a runner on it.
    assert set(triggers) == {"workflow_dispatch", "pull_request"}
    assert "push" not in triggers
    assert set(triggers["pull_request"]["types"]) == {"labeled", "synchronize", "reopened"}
    assert set(triggers["workflow_dispatch"]["inputs"]) == {"source_sha", "correlation_id"}
    assert triggers["workflow_dispatch"]["inputs"]["source_sha"]["required"] is True
    job = document["jobs"]["ac11-aggregate"]
    assert "run-ac11-aggregate" in job["if"], "the pull-request path must stay label-gated"
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


#: The registered long-soak target, read from the canonical registry rather than restated.
LONG_SOAK_TARGET = "s11-ac11-composite-long-soak-v0"
REPO = Path(__file__).resolve().parents[2]
TARGET_REGISTRY = REPO / "docs/vault/30_Development/Evidence/s11-ac11-target-registry-v0.json"


def registered_target(target_id: str) -> dict:
    registry = json.loads(TARGET_REGISTRY.read_text(encoding="utf-8"))
    matches = [row for row in registry["targets"] if row["targetId"] == target_id]
    assert len(matches) == 1, target_id
    return matches[0]


def test_the_registered_long_soak_target_is_not_lowered_to_fit_a_hosted_runner():
    """Card 217: the axis stays incomplete because the target is what it is.

    Checking the row's prose is not enough -- a change that lowered ``windowSeconds`` or
    softened ``requiredEnvironment`` would leave every sentence in this repository true while
    making the axis measurable on a hosted runner, which is the one outcome the card forbids
    (#315 F-R3).  So the values are read from the registry the aggregator itself reads.
    """

    target = registered_target(LONG_SOAK_TARGET)
    criteria = target["criteria"]
    assert target["axis"] == "long-soak"
    # The whole criteria set, not a sample: a criterion that disappears is a criterion
    # nobody has to satisfy.
    assert len(criteria) == 48
    assert criteria["windowSeconds"] == {"operator": "gte", "value": 86400}
    assert criteria["requiredCaseCount"] == {"operator": "eq", "value": 14}
    assert criteria["executedRequiredCaseCount"] == {"operator": "eq", "value": 14}
    assert criteria["externalObserverCoveragePpm"] == {"operator": "gte", "value": 990000}
    for name, value in (
        ("plannedPowerFaultCaseCount", 2), ("switchFaultCaseCount", 2), ("wanFaultCaseCount", 2),
        ("powerRecoveryPassCount", 2), ("switchRecoveryPassCount", 2), ("wanRecoveryPassCount", 2),
    ):
        assert criteria[name] == {"operator": "gte", "value": value}, name
    for name, value in (
        ("maxPowerRecoverySeconds", 900), ("maxSwitchRecoverySeconds", 300),
        ("maxWanRecoverySeconds", 120),
    ):
        assert criteria[name] == {"operator": "lte", "value": value}, name
    assert criteria["minThermalHeadroomMilliC"] == {"operator": "gte", "value": 5000}
    assert criteria["thermalThrottleSeconds"] == {"operator": "eq", "value": 0}
    assert target["requiredEnvironment"] == {
        "topology": "physical-five-node",
        "registeredNodeCount": 5,
        "eligibleNodeCount": 4,
        "excludedNodeCount": 1,
        "cpIndependentWorkerHostCount": 4,
        "cpColocatedNodeCount": 1,
        "timedPopulation": "cp-independent-ubuntu-four",
        "observer": "external-monotonic-v1",
        "faultInjection": "controlled-v1",
        "windowClass": "physical-24h",
    }


def test_the_long_soak_row_stays_incomplete_and_says_why():
    """The row describes the tree: the chain is open and no workflow claims to close it."""

    axes = {entry["axis"]: entry for entry in assembler.load_sources(assembler.DEFAULT_SOURCES)}
    long_soak = axes["long-soak"]
    assert long_soak["chain"] == "incomplete"
    assert long_soak["workflow"] is None
    reason = long_soak["reason"]
    for fragment in ("86400", "physical-five-node", "external-monotonic-v1", "G-24"):
        assert fragment in reason, fragment
    assert assembler.emitted_axes(long_soak["importer"]) == {"long-soak"}


class _RegistryGit:
    """Enough Git to answer the importer's provenance questions about this checkout."""

    def __init__(self):
        target = registered_target(LONG_SOAK_TARGET)
        self.document = target["sourceDocument"]

    def tree(self, commit: str) -> str:
        return "e" * 40

    def blob(self, commit: str, path: str) -> str:
        if path == long_soak_importer.REGISTRY_PATH:
            return long_soak_importer.REGISTRY_BLOB
        assert path == self.document["path"], path
        return self.document["blob"]

    def show(self, commit: str, path: str) -> str:
        assert path == long_soak_importer.REGISTRY_PATH, path
        return TARGET_REGISTRY.read_text(encoding="utf-8")

    def is_ancestor(self, ancestor: str, descendant: str) -> bool:
        return True


def test_the_physical_import_path_exists_and_both_operator_resources_are_required():
    """#315 F-R3: the gap is the run, not the import path.

    r1 of this card claimed the importer had no physical branch.  It has one, and it binds
    this target: ``readiness`` answers BLOCKED_EXTERNAL naming *both* missing operator
    resources, and once they are declared it says the run itself is what is missing.  If
    somebody weakens that to a single resource, or lets the physical path through without
    them, this test fails -- and so does the claim in the runbook that the only thing left is
    the measurement.
    """

    git = _RegistryGit()
    blocked = long_soak_importer.readiness(SHA, set(), git)
    assert blocked["verdict"] == "BLOCKED_EXTERNAL"
    assert blocked["blocker"] == "G-19,G-24"
    assert long_soak_importer.readiness(SHA, {"G-19"}, git)["blocker"] == "G-24"
    ready = long_soak_importer.readiness(SHA, {"G-19", "G-24"}, git)
    assert ready == {
        "axis": "long-soak",
        "verdict": "NOT_OBSERVED",
        "reason": "physical run not supplied",
    }
    # The physical report is bound to this target, and only the dry-run is reference-only.
    assert long_soak_importer.TARGET_ID == LONG_SOAK_TARGET
    assert long_soak_importer.REQUIRED_RESOURCES == frozenset({"G-19", "G-24"})
    assert long_soak_importer.DRY_RUN_PURPOSE == "s11-ac11-composite-long-soak-dry-run"
    assert long_soak_importer.EMITTED_AXES == ("long-soak",)
