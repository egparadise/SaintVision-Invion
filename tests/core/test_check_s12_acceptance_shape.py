"""The gate must refuse each way a bundle can be wrong, and accept a FAIL verdict.

A gate that only ran on a good bundle would be removed the first time the real verdict was
FAIL -- which it is, and honestly so, until the external waits clear. So the first test here
is that a FAIL bundle is *accepted*: the checker judges shape and derivation, not the answer.

The second group is the hole Codex measured. The first version of this gate accepted a bundle
with ``verdict: FABRICATED_PASS``, no ``codeSha``, no ``provenance`` and all seventeen items
PASS with ``source: typed-by-human``. ``test_the_fabricated_bundle_codex_measured_is_refused``
is that exact file, so the hole cannot reopen quietly, and the tests around it take it apart
one field at a time -- a single test on the whole forgery would pass as soon as any one of the
bindings worked.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import check_s12_acceptance_shape as shape  # noqa: E402
from check_s12_acceptance_shape import (  # noqa: E402
    CI_DERIVED_CLAIM,
    CLEAN_PROVENANCE,
    EXPECTED_ITEMS,
    EXPECTED_SOURCES,
    SCHEMA,
    ShapeRefused,
    check,
    collector_digest,
    main,
)

HEAD = "a" * 40
OTHER_HEAD = "b" * 40

#: The source each item must name. Taken from the gate, except the two the registry singled
#: out, which are written here as literals: a test that read those from the thing it is
#: testing would agree with a rename it should have caught.
SOURCES = {
    **EXPECTED_SOURCES,
    "pitr-configuration-possible": "pitr_readiness",
    "pitr-rehearsal-dry-run-observed": "pitr_opt_in_dry_run",
}


def scope_of(items):
    """The scope lists, computed here rather than imported, so the fixture is independent."""

    out = {status: [] for status in ("PASS", "FAIL", "NOT_OBSERVED", "BLOCKED_EXTERNAL")}
    for name, item in items.items():
        out[item["status"]].append(name)
    return out


def statuses(default="BLOCKED_EXTERNAL", **overrides):
    """The honest shape of today's bundle: the two PITR items answered, the rest waiting."""

    out = {name: default for name in EXPECTED_ITEMS}
    out.update({"pitr-configuration-possible": "FAIL", "pitr-rehearsal-dry-run-observed": "FAIL"})
    out.update(overrides)
    return out


def provenance(**overrides):
    base = {
        "commit_sha": HEAD,
        "branch": "agent/claude/c185-vfcl-next",
        "working_tree_clean_status": True,
        "content_clean_diff": True,
        "modified_paths": [],
        "dirtyTreeAllowed": False,
        "unpushedHeadAllowed": False,
        "remoteReachable": True,
        "remoteRefCount": 1,
        "collectorSha256": collector_digest(),
        "executor": "github-actions",
        "timestamp_kst": "2026-10-01T19:00:00+09:00",
    }
    base.update(overrides)
    return base


def bundle(item_statuses=None, verdict="FAIL", **overrides):
    item_statuses = statuses() if item_statuses is None else item_statuses
    items = {
        name: {
            "status": item_statuses[name],
            "title": name,
            "source": SOURCES[name],
            "group": "restore",
        }
        for name in EXPECTED_ITEMS
    }
    document = {
        "schemaVersion": SCHEMA,
        "codeSha": HEAD,
        # The honest verdict today. The gate must accept it.
        "verdict": verdict,
        "acceptanceClaim": False,
        "items": items,
        "scope": scope_of(items),
        "provenance": provenance(),
    }
    document.update(overrides)
    return document


def accepted(document, expected_head=HEAD):
    return check(document, json.dumps(document, ensure_ascii=False), expected_head=expected_head)


# ---------------------------------------------------------------------------- the answer is not judged


def test_a_failing_verdict_is_accepted_because_the_verdict_is_the_measurement():
    summary = accepted(bundle())
    assert summary["verdict"] == "FAIL"
    assert summary["verdictRecomputedFromItems"] == "FAIL"
    assert summary["items"] == len(EXPECTED_ITEMS)
    assert set(summary["ciDerived"]) == set(CI_DERIVED_CLAIM)


@pytest.mark.parametrize(
    "item_statuses,verdict",
    [
        (statuses(), "FAIL"),
        (statuses(default="PASS", **{"pitr-configuration-possible": "PASS",
                                     "pitr-rehearsal-dry-run-observed": "PASS"}), "PASS"),
        (statuses(default="PASS", **{"pitr-configuration-possible": "PASS",
                                     "pitr-rehearsal-dry-run-observed": "NOT_OBSERVED"}),
         "PASS_MEASURED_PARTIAL"),
        (statuses(default="BLOCKED_EXTERNAL", **{"pitr-configuration-possible": "NOT_OBSERVED",
                                                 "pitr-rehearsal-dry-run-observed": "NOT_OBSERVED"}),
         "NOT_OBSERVED"),
    ],
)
def test_every_verdict_the_collector_can_produce_is_accepted(item_statuses, verdict):
    """Each of the four, with items that actually add up to it.

    The parameters are written out rather than computed: the point is that the gate agrees
    with the collector's rule, and a test that derived the expected verdict from that rule
    would agree with any rule.
    """
    assert accepted(bundle(item_statuses, verdict=verdict))["verdict"] == verdict


# ---------------------------------------------------------------------------- the measured forgery


def fabricated():
    """Codex's probe, field for field: a bundle a person could type.

    Seventeen items all PASS, a verdict nothing produced, no commit, no provenance. The first
    version of this gate printed "shape accepted" for it.
    """
    items = {
        name: {"status": "PASS", "title": name, "source": "typed-by-human", "group": "restore"}
        for name in EXPECTED_ITEMS
    }
    return {
        "schemaVersion": SCHEMA,
        "verdict": "FABRICATED_PASS",
        "acceptanceClaim": False,
        "items": items,
        "scope": scope_of(items),
    }


def test_the_fabricated_bundle_codex_measured_is_refused():
    with pytest.raises(ShapeRefused):
        accepted(fabricated())


@pytest.mark.parametrize(
    "verdict",
    ["FABRICATED_PASS", "MEASURED_PASS", "ACCEPTED", "pass", "PASS_MEASURED", "", None, True],
)
def test_a_verdict_the_collector_cannot_emit_is_refused(verdict):
    """The set comes from the collector's exit table, so "could be emitted" is not a guess."""
    with pytest.raises(ShapeRefused, match="not one the collector can emit"):
        accepted(bundle(verdict=verdict))


def test_a_good_verdict_over_failing_items_is_refused():
    """``PASS`` is in the enum. Over two FAILs it is still a bundle nothing produced."""
    with pytest.raises(ShapeRefused, match="these items produce"):
        accepted(bundle(verdict="PASS"))


def test_a_worse_verdict_than_the_items_is_also_refused():
    """Equality, not a floor: under-reporting is a different false statement, not a safe one."""
    passing = statuses(default="PASS", **{"pitr-configuration-possible": "PASS",
                                          "pitr-rehearsal-dry-run-observed": "PASS"})
    with pytest.raises(ShapeRefused, match="these items produce"):
        accepted(bundle(passing, verdict="FAIL"))


def test_an_item_moved_between_the_scope_lists_is_refused():
    """The lists a summary quotes have to be the statuses they claim to summarise."""
    document = bundle()
    document["scope"]["FAIL"].remove("pitr-configuration-possible")
    document["scope"]["PASS"].append("pitr-configuration-possible")
    with pytest.raises(ShapeRefused, match="scope lists disagree"):
        accepted(document)


@pytest.mark.parametrize("value", [None, {}, [], "FAIL"])
def test_a_bundle_without_usable_scope_lists_is_refused(value):
    with pytest.raises(ShapeRefused, match="scope"):
        accepted(bundle(scope=value))


# ---------------------------------------------------------------------------- sources


@pytest.mark.parametrize("name", CI_DERIVED_CLAIM)
def test_a_named_observation_without_a_source_is_refused(name):
    """The registry's claim is that CI derives these two, not that they merely appear.

    An item with no ``source`` could have been written by hand, which is the state the
    ``ciVerified`` note described. The gate refuses it.
    """
    document = bundle()
    document["items"][name]["source"] = ""
    with pytest.raises(ShapeRefused, match="names no source tool"):
        accepted(document)


@pytest.mark.parametrize("name", CI_DERIVED_CLAIM)
@pytest.mark.parametrize("source", ["typed-by-human", "operational_readiness", "pitr", "CI"])
def test_a_named_observation_from_the_wrong_tool_is_refused(name, source):
    """A non-empty string is not the claim. The claim is which program answered."""
    document = bundle()
    document["items"][name]["source"] = source
    with pytest.raises(ShapeRefused, match="somebody's word for it"):
        accepted(document)


def test_a_named_source_that_is_not_a_tool_in_this_tree_is_refused(monkeypatch):
    """The source has to name a program that exists here, or it cannot have run here."""
    monkeypatch.setitem(shape.CI_DERIVED_CLAIM, "pitr-configuration-possible", "no_such_tool")
    document = bundle()
    document["items"]["pitr-configuration-possible"]["source"] = "no_such_tool"
    with pytest.raises(ShapeRefused, match="not a tool in this tree"):
        accepted(document)


def test_the_two_named_sources_are_the_tools_the_registry_meant():
    """Literals on both sides, so a rename in the collector's catalogue is seen, not followed."""
    assert CI_DERIVED_CLAIM == {
        "pitr-configuration-possible": "pitr_readiness",
        "pitr-rehearsal-dry-run-observed": "pitr_opt_in_dry_run",
    }
    for name, tool in CI_DERIVED_CLAIM.items():
        assert EXPECTED_SOURCES[name] == tool, "the collector's catalogue renamed a source"
        assert (ROOT / "tools" / f"{tool}.py").exists()


@pytest.mark.parametrize("name", ["offer-agreement", "verified-off-site-backup", "web-smoke-journeys"])
def test_any_items_source_must_be_the_one_the_catalogue_names(name):
    """Not only the two named items: every answer says which tool produced it."""
    document = bundle()
    document["items"][name]["source"] = "typed-by-human"
    with pytest.raises(ShapeRefused, match="catalogue names"):
        accepted(document)


def test_an_external_item_that_claims_a_source_is_refused():
    """Nothing in this repository can observe five physical nodes.

    A source string on an external item would say something had, which is the kind of
    sentence this whole bundle exists to avoid.
    """
    document = bundle()
    document["items"]["five-node-full-journey"]["source"] = "operational_readiness.probe"
    with pytest.raises(ShapeRefused, match="catalogue names"):
        accepted(document)


# ---------------------------------------------------------------------------- the head


@pytest.mark.parametrize("code_sha", [None, "", "a" * 39, "A" * 40, "deadbeef", 123, True])
def test_a_bundle_that_does_not_say_which_commit_it_describes_is_refused(code_sha):
    """Codex's probe had no ``codeSha`` at all. An upper-case or short one is no better."""
    document = bundle()
    document["codeSha"] = code_sha
    with pytest.raises(ShapeRefused, match="codeSha"):
        accepted(document)


def test_a_bundle_describing_another_commit_is_refused():
    document = bundle(codeSha=OTHER_HEAD, provenance=provenance(commit_sha=OTHER_HEAD))
    with pytest.raises(ShapeRefused, match="head under test"):
        accepted(document)


def test_codeSha_and_provenance_naming_different_heads_is_refused():
    with pytest.raises(ShapeRefused, match="two different heads"):
        accepted(bundle(provenance=provenance(commit_sha=OTHER_HEAD)))


def test_a_bundle_with_no_provenance_is_refused():
    document = bundle()
    del document["provenance"]
    with pytest.raises(ShapeRefused, match="provenance is absent"):
        accepted(document)


# ---------------------------------------------------------------------------- the checkout


@pytest.mark.parametrize("key,required", sorted(CLEAN_PROVENANCE.items()))
def test_every_clean_checkout_flag_is_required(key, required):
    """Each flag on its own: the collector records an opt-out, and CI is where none is allowed."""
    with pytest.raises(ShapeRefused, match=key):
        accepted(bundle(provenance=provenance(**{key: not required})))


@pytest.mark.parametrize("key", sorted(CLEAN_PROVENANCE))
def test_a_missing_clean_checkout_flag_is_refused(key):
    """Absent is not false. ``dict.get`` returning ``None`` must not read as "no opt-out"."""
    values = provenance()
    del values[key]
    with pytest.raises(ShapeRefused, match=key):
        accepted(bundle(provenance=values))


def test_a_tree_with_modified_paths_is_refused():
    document = bundle(provenance=provenance(modified_paths=["tools/pitr_readiness.py"]))
    with pytest.raises(ShapeRefused, match="not the tree at that commit"):
        accepted(document)


@pytest.mark.parametrize("key", ["executor", "timestamp_kst"])
def test_provenance_without_who_or_when_is_refused(key):
    with pytest.raises(ShapeRefused, match=key):
        accepted(bundle(provenance=provenance(**{key: ""})))


@pytest.mark.parametrize("digest", [None, "", "0" * 64, "not-a-digest"])
def test_a_bundle_that_names_another_collector_is_refused(digest):
    """The bundle names the bytes that produced it, and the gate reads those bytes."""
    with pytest.raises(ShapeRefused, match="collectorSha256"):
        accepted(bundle(provenance=provenance(collectorSha256=digest)))


def test_the_digest_is_the_collector_in_this_tree():
    import hashlib

    expected = hashlib.sha256((ROOT / "tools" / "collect_s12_acceptance_evidence.py").read_bytes())
    assert collector_digest() == expected.hexdigest()


# ---------------------------------------------------------------------------- the item set


def test_a_dropped_item_is_refused_because_it_reads_as_progress():
    """The failure mode the gate exists for.

    Removing a FAIL item takes it out of the scope lists, so the verdict improves because
    the question disappeared. Nothing in the bundle says so.
    """
    document = bundle()
    del document["items"]["verified-off-site-backup"]
    with pytest.raises(ShapeRefused, match="reads"):
        accepted(document)


def test_every_single_item_removal_is_refused():
    """All seventeen, not a sample: a gate that covered most of them would be a lottery."""
    for name in EXPECTED_ITEMS:
        document = bundle()
        del document["items"][name]
        with pytest.raises(ShapeRefused):
            accepted(document)


def test_an_unrecognised_status_is_refused():
    document = bundle()
    document["items"]["offer-agreement"]["status"] = "OK"
    with pytest.raises(ShapeRefused, match="recognised status"):
        accepted(document)


def test_an_item_that_is_not_an_object_is_refused():
    document = bundle()
    document["items"]["offer-agreement"] = "PASS"
    with pytest.raises(ShapeRefused, match="recognised status"):
        accepted(document)


def test_an_extra_item_is_refused_so_completeness_stays_decidable():
    document = bundle()
    document["items"]["invented-item"] = {"status": "PASS", "source": "x"}
    with pytest.raises(ShapeRefused, match="not in the expected set"):
        accepted(document)


@pytest.mark.parametrize("claim", [True, None, "false", 0, 1])
def test_anything_but_exactly_false_for_acceptanceClaim_is_refused(claim):
    """``0 == False`` in Python, so the comparison is by identity, not equality."""
    with pytest.raises(ShapeRefused, match="acceptanceClaim"):
        accepted(bundle(acceptanceClaim=claim))


def test_a_different_schema_is_refused():
    with pytest.raises(ShapeRefused, match="schemaVersion"):
        accepted(bundle(schemaVersion="s12-db-acceptance-evidence:2"))


def test_items_that_are_not_an_object_are_refused():
    with pytest.raises(ShapeRefused, match="keyed by item id"):
        accepted(bundle(items=[{"id": "offer-agreement", "status": "PASS"}]))


# ---------------------------------------------------------------------------- secrets


@pytest.mark.parametrize(
    "leak",
    [
        "postgresql://invowner:ci_local_only@localhost:5432/postgres",
        "postgres://u:p@h/db",
        "password=hunter2",
        "PASSWORD=Hunter2",
    ],
)
def test_a_connection_string_in_the_file_is_refused(leak):
    """Re-read independently of the collector's own redaction.

    The collector redacts before serialising and re-checks its own text. This is the second
    pair of eyes on the file that actually shipped -- the artifact is uploaded, so a leak
    here is a leak into a downloadable place.
    """
    document = bundle()
    document["items"]["offer-agreement"]["note"] = leak
    with pytest.raises(ShapeRefused, match="connection string"):
        accepted(document)


def test_a_leak_escaped_by_json_is_still_refused():
    """A value with quotes or backslashes must not hide the pattern from the re-read."""
    document = bundle()
    document["items"]["offer-agreement"]["note"] = 'x" postgresql://u:p@h/db "y'
    with pytest.raises(ShapeRefused, match="connection string"):
        accepted(document)


# ---------------------------------------------------------------------------- the command line


def written(tmp_path, document, name=None):
    path = tmp_path / (name or f"s12-acceptance-{HEAD[:12]}-20261001T100000Z.json")
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    return path


def test_the_command_line_refuses_to_run_without_a_head(tmp_path, capsys):
    """Fail closed: a check with nothing to check against is the state Codex found."""
    path = written(tmp_path, bundle())
    assert main([str(path)]) == 2
    assert "--expected-head is required" in capsys.readouterr().err


def test_the_command_line_accepts_the_bundle_it_is_bound_to(tmp_path, capsys):
    path = written(tmp_path, bundle())
    assert main([str(path), "--expected-head", HEAD]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["expectedHead"] == HEAD
    assert summary["verdict"] == "FAIL"
    assert summary["status"].startswith("shape accepted")


def test_the_command_line_refuses_a_file_named_for_another_head(tmp_path):
    """The workflow finds the bundle with a glob, so the file itself is part of the binding."""
    path = written(tmp_path, bundle(), name=f"s12-acceptance-{OTHER_HEAD[:12]}-20261001T100000Z.json")
    with pytest.raises(ShapeRefused, match="not named for"):
        main([str(path), "--expected-head", HEAD])


def test_the_command_line_refuses_a_head_that_is_not_a_commit(tmp_path, capsys):
    path = written(tmp_path, bundle())
    assert main([str(path), "--expected-head", "HEAD~1"]) == 2
    assert "not a 40-hex commit" in capsys.readouterr().err


def test_the_opt_out_is_explicit_and_says_so_in_the_output(tmp_path, capsys):
    """A person checking an archived bundle may have no head; the output records that."""
    path = written(tmp_path, bundle(), name="whatever.json")
    assert main([str(path), "--allow-unbound-head"]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["expectedHead"] is None
    assert summary["status"].startswith("head binding NOT checked")


# ---------------------------------------------------------------------------- the summary


def test_the_summary_groups_every_item_by_status():
    summary = accepted(bundle())
    grouped = sum(len(names) for names in summary["byStatus"].values())
    assert grouped == len(EXPECTED_ITEMS)
    assert summary["status"].startswith("shape accepted")
    assert summary["ciDerivedSources"] == {
        "pitr-configuration-possible": "pitr_readiness",
        "pitr-rehearsal-dry-run-observed": "pitr_opt_in_dry_run",
    }
    assert summary["provenance"]["remoteReachable"] is True
