"""The registry is how work gets picked, so a stale entry sends someone somewhere wrong.

Two entries had gone stale before this existed. One said an implementation was partial
when its request path had landed, and one said a drill was waiting for a pull request
that had already merged -- anyone waiting for it would have waited forever. Nothing
validated the file, which is why neither was noticed.

These tests pin the drift classes that actually happened, plus the ones the same shape
allows. The first two are the historical mistakes, reproduced.

A review then found four edits that passed the first version of the checker while making
the registry say something false: a stated ``acceptedCards`` nobody counted, every card
declared accepted with its blockers still open, and two cards reverted to an earlier state
that was internally consistent and no longer true. The last two are why the per-card
assertions moved into a manifest the registry cannot edit -- each of the four is pinned
below as a probe.
"""

from __future__ import annotations

import json
import subprocess

import pytest

from tools import check_vf_cl_registry as checker


def registry(tmp_path, **overrides):
    """A registry that agrees with a tiny tree built under tmp_path."""
    (tmp_path / "src").mkdir(exist_ok=True)
    (tmp_path / "src" / "route.py").write_text(
        "from ..adapters.model_import import require_exact_declaration\n"
        "require_exact_declaration(manifest, declared)\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "mount.py").write_text("route.register(router)\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@example.com", "-c", "user.name=t",
         "commit", "-q", "-m", "Merge PR #126 (abc) into merge train"],
        cwd=tmp_path, check=True,
    )
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path,
                          capture_output=True, text=True, check=True).stdout.strip()
    document = {
        "version": "1.0.0",
        "acceptanceDenominator": 1,
        "acceptedCards": 0,
        "verifiedAgainst": {"tree": head},
        "cards": [
            {
                "id": "VF-CL-0X",
                "implemented": True,
                "locallyVerified": True,
                "ciVerified": True,
                "independentlyReviewed": False,
                "operationallyAccepted": False,
                "blockers": ["waiting-on-a-reviewer"],
                "state": "review",
                "closedBlockers": [
                    {
                        "blocker": "the-request-path-was-missing",
                        "checksIn": "manifest.json",
                    }
                ],
            }
        ],
    }
    document.update(overrides)
    return document


#: The checks that used to live inside each closedBlockers entry. They are here because
#: the registry must not be able to edit what it is judged against.
def manifest(**overrides):
    document = {
        "schemaVersion": checker.MANIFEST_SCHEMA,
        "cards": {
            "VF-CL-0X": {
                "impliesImplemented": True,
                "checks": [{"kind": "path-exists", "path": "src/route.py"}],
                "closedBlockers": {
                    "the-request-path-was-missing": [
                        {"kind": "path-exists", "path": "src/route.py"},
                        {"kind": "references", "path": "src/route.py",
                         "text": "require_exact_declaration(manifest, declared)"},
                        {"kind": "references", "path": "src/mount.py",
                         "text": "route.register(router)"},
                    ]
                },
            }
        },
    }
    document.update(overrides)
    return document


def written(tmp_path, document, name="manifest.json"):
    target = tmp_path / name
    target.write_text(json.dumps(document), encoding="utf-8")
    return target


def audit(document, tmp_path, manifest_document=None):
    return checker.audit(
        document, tmp_path,
        written(tmp_path, manifest() if manifest_document is None else manifest_document),
    )


def checks_for(manifest_document, blocker="the-request-path-was-missing"):
    return manifest_document["cards"]["VF-CL-0X"]["closedBlockers"][blocker]


def test_a_registry_that_matches_the_tree_reports_nothing(tmp_path):
    assert audit(registry(tmp_path), tmp_path) == []


# --- the two mistakes that actually happened --------------------------------------


def test_a_blocker_naming_a_merged_pull_request_is_reported(tmp_path):
    """VF-CL-04 said the drill skipped "until-pr-126" after #126 had merged.

    This is the rule that generalises that mistake: if the history records the pull
    request as merged, the blocker is describing a wait that is over.
    """
    document = registry(tmp_path)
    document["cards"][0]["blockers"] = ["restore-drill-skips-until-pr-126"]
    findings = audit(document, tmp_path)
    assert any("#126" in finding and "merged" in finding for finding in findings), findings


@pytest.mark.parametrize("spelling", ["until-pr-126", "blocked-on-#126", "pr-126-not-landed"])
def test_the_pull_request_is_found_however_it_is_written(tmp_path, spelling):
    document = registry(tmp_path)
    document["cards"][0]["blockers"] = [spelling]
    assert any("#126" in finding for finding in audit(document, tmp_path))


def test_a_pull_request_that_has_not_merged_is_left_alone(tmp_path):
    """A real wait must not be reported as drift, or the check becomes noise."""
    document = registry(tmp_path)
    document["cards"][0]["blockers"] = ["waiting-on-pr-9999"]
    assert audit(document, tmp_path) == []


def test_a_blocker_listed_as_both_open_and_closed_is_reported(tmp_path):
    """VF-CL-03 kept an open blocker whose work had landed."""
    document = registry(tmp_path)
    document["cards"][0]["blockers"].append("the-request-path-was-missing")
    findings = audit(document, tmp_path)
    assert any("both open and closed" in finding for finding in findings), findings


# --- a closed blocker has to stay closed ------------------------------------------


def test_a_closed_blocker_the_manifest_does_not_cover_is_unusable(tmp_path):
    """Prose is how the earlier entries went stale without anyone noticing.

    Dropping the manifest entry is the same move as leaving prose alone, so it is refused
    rather than passed: a check that is not there does not fail.
    """
    document = registry(tmp_path)
    empty = manifest()
    empty["cards"]["VF-CL-0X"]["closedBlockers"] = {}
    with pytest.raises(checker.RegistryUnusable, match="carries no checks for closed blocker"):
        audit(document, tmp_path, empty)


def test_a_manifest_closed_blocker_with_an_empty_check_list_is_unusable(tmp_path):
    document = registry(tmp_path)
    hollow = manifest()
    checks_for(hollow).clear()
    with pytest.raises(checker.RegistryUnusable, match="has no checks"):
        audit(document, tmp_path, hollow)


def test_evidence_that_stopped_holding_is_reported(tmp_path):
    document = registry(tmp_path)
    stale = manifest()
    checks_for(stale)[0]["path"] = "src/gone.py"
    findings = audit(document, tmp_path, stale)
    assert any("not in the tree" in finding for finding in findings), findings


def test_a_reference_that_disappeared_is_reported(tmp_path):
    document = registry(tmp_path)
    (tmp_path / "src" / "route.py").write_text("# the call was removed\n", encoding="utf-8")
    findings = audit(document, tmp_path)
    assert any("no longer contains" in finding for finding in findings), findings


def test_an_absent_check_catches_something_coming_back(tmp_path):
    """The mirror of `references`: some closures are "this is no longer there"."""
    document = registry(tmp_path)
    mirrored = manifest()
    mirrored["cards"]["VF-CL-0X"]["closedBlockers"]["the-request-path-was-missing"] = [
        {"kind": "absent", "path": "src/route.py", "text": "require_exact_declaration"}
    ]
    findings = audit(document, tmp_path, mirrored)
    assert any("now contains" in finding for finding in findings), findings
    (tmp_path / "src" / "route.py").write_text("# removed\n", encoding="utf-8")
    # The card-level check names the same file, which still exists, so only the blocker
    # check changes meaning.
    assert audit(document, tmp_path, mirrored) == []


def test_an_unknown_check_kind_is_unusable_not_silently_skipped(tmp_path):
    """A check nobody runs is worse than no check: it reads as verified."""
    document = registry(tmp_path)
    invented = manifest()
    invented["cards"]["VF-CL-0X"]["closedBlockers"]["the-request-path-was-missing"] = [
        {"kind": "looks-fine-to-me", "path": "src/route.py"}
    ]
    with pytest.raises(checker.RegistryUnusable, match="unknown check kind"):
        audit(document, tmp_path, invented)


# --- shape ------------------------------------------------------------------------


@pytest.mark.parametrize("field", checker.STATE_FIELDS)
def test_a_card_that_omits_a_state_field_is_reported(tmp_path, field):
    document = registry(tmp_path)
    document["cards"][0].pop(field)
    findings = audit(document, tmp_path)
    assert any(field in finding for finding in findings), findings


@pytest.mark.parametrize("value", ["yes", None, 1, "done"])
def test_an_implemented_value_outside_the_three_is_reported(tmp_path, value):
    document = registry(tmp_path)
    document["cards"][0]["implemented"] = value
    findings = audit(document, tmp_path)
    assert any("implemented" in finding for finding in findings), findings


@pytest.mark.parametrize("value", [True, False, "partial"])
def test_the_three_permitted_implemented_values_are_accepted(tmp_path, value):
    """Accepted when the manifest says the same thing: the tree decides which it is."""
    document = registry(tmp_path)
    document["cards"][0]["implemented"] = value
    agreeing = manifest()
    agreeing["cards"]["VF-CL-0X"]["impliesImplemented"] = value
    assert audit(document, tmp_path, agreeing) == []


def test_a_duplicate_card_id_is_reported(tmp_path):
    document = registry(tmp_path)
    document["cards"].append(json.loads(json.dumps(document["cards"][0])))
    findings = audit(document, tmp_path)
    assert any("more than once" in finding for finding in findings), findings


def test_an_empty_blocker_is_reported(tmp_path):
    document = registry(tmp_path)
    document["cards"][0]["blockers"] = ["   "]
    findings = audit(document, tmp_path)
    assert any("empty blocker" in finding for finding in findings), findings


# --- the tree the claim is about ---------------------------------------------------


def test_a_registry_that_names_no_tree_is_reported(tmp_path):
    document = registry(tmp_path)
    document.pop("verifiedAgainst")
    findings = audit(document, tmp_path)
    assert any("which tree" in finding for finding in findings), findings


def test_a_tree_this_branch_does_not_contain_is_reported(tmp_path):
    """Numbers may be right and still be about somewhere else."""
    document = registry(tmp_path)
    document["verifiedAgainst"]["tree"] = "0" * 40
    findings = audit(document, tmp_path)
    assert any("not an ancestor" in finding for finding in findings), findings


def test_a_registry_that_is_not_an_object_is_unusable(tmp_path):
    for value in ([], {"cards": {}}, {"no": "cards"}):
        with pytest.raises(checker.RegistryUnusable):
            audit(value, tmp_path)


def test_a_card_without_an_id_is_unusable(tmp_path):
    document = registry(tmp_path)
    document["cards"][0].pop("id")
    with pytest.raises(checker.RegistryUnusable, match="string id"):
        audit(document, tmp_path)


# --- the shipped registry itself ---------------------------------------------------


def test_the_shipped_registry_agrees_with_this_tree():
    """The point of the exercise: the committed file re-derives from the real tree."""
    assert checker.main([]) == 0


def test_the_cli_separates_drift_from_an_unusable_file(tmp_path):
    book = str(written(tmp_path, manifest()))
    good = tmp_path / "good.json"
    good.write_text(json.dumps(registry(tmp_path)), encoding="utf-8")
    assert checker.main(["--registry", str(good), "--root", str(tmp_path),
                         "--manifest", book]) == 0

    drifted = registry(tmp_path)
    drifted["cards"][0]["blockers"] = ["until-pr-126"]
    path = tmp_path / "drift.json"
    path.write_text(json.dumps(drifted), encoding="utf-8")
    assert checker.main(["--registry", str(path), "--root", str(tmp_path),
                         "--manifest", book]) == 1

    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    assert checker.main(["--registry", str(broken), "--root", str(tmp_path),
                         "--manifest", book]) == 2

    assert checker.main(["--registry", str(good), "--root", str(tmp_path),
                         "--manifest", str(tmp_path / "absent.json")]) == 2


# --- the four probes that passed the first version --------------------------------


def test_probe_one_a_stated_accepted_count_is_counted(tmp_path):
    """`acceptedCards: 5` beside five cards, none of them accepted."""
    document = registry(tmp_path)
    document["acceptedCards"] = 5
    findings = audit(document, tmp_path)
    assert any("acceptedCards says 5" in finding for finding in findings), findings
    assert any("0 card(s) are operationallyAccepted" in finding for finding in findings)


def test_the_denominator_must_match_the_number_of_cards(tmp_path):
    document = registry(tmp_path)
    document["acceptanceDenominator"] = 9
    findings = audit(document, tmp_path)
    assert any("acceptanceDenominator says 9" in finding for finding in findings), findings


def test_probe_two_acceptance_cannot_be_declared_over_open_blockers(tmp_path):
    """Every card `operationallyAccepted: true` while its blockers were still open.

    Acceptance is the one claim nothing downstream re-checks, so it is the one that has to
    disagree loudly with the rest of its own card.
    """
    document = registry(tmp_path)
    card = document["cards"][0]
    card["operationallyAccepted"] = True
    document["acceptedCards"] = 1
    findings = audit(document, tmp_path)
    assert any("1 open blocker(s)" in finding for finding in findings), findings
    assert any("state is 'review'" in finding for finding in findings), findings
    assert any("independentlyReviewed is False" in finding for finding in findings), findings


def test_acceptance_over_a_named_not_applicable_field_is_allowed(tmp_path):
    """A review card has no CI to verify it; saying so in notApplicable is the way."""
    document = registry(tmp_path)
    card = document["cards"][0]
    card.update(operationallyAccepted=True, state="accepted", blockers=[],
                independentlyReviewed=False,
                notApplicable=["independentlyReviewed: this card IS the review function"])
    document["acceptedCards"] = 1
    assert audit(document, tmp_path) == []


def test_probe_three_a_card_reverted_to_an_earlier_state_is_caught(tmp_path):
    """VF-CL-03 back to `implemented: "partial"` with its blocker re-opened.

    Nothing inside the registry can fault this: the file is internally consistent, and it
    is what the file said before it was corrected. Only something outside it can, which is
    what the manifest is.
    """
    document = registry(tmp_path)
    card = document["cards"][0]
    card["implemented"] = "partial"
    card["blockers"] = ["the-request-path-was-missing"]
    card["closedBlockers"] = []
    findings = audit(document, tmp_path)
    assert any("the tree shows implemented=True but the registry says 'partial'" in finding
               for finding in findings), findings
    assert any("is listed open but the tree still shows it closed" in finding
               for finding in findings), findings
    assert any("no longer records it" in finding for finding in findings), findings


def test_probe_four_a_closed_blocker_reopened_is_caught(tmp_path):
    """VF-CL-04's retention blocker, re-opened after being closed against the tree."""
    document = registry(tmp_path)
    document["cards"][0]["blockers"] = ["the-request-path-was-missing"]
    findings = audit(document, tmp_path)
    assert any("both open and closed" in finding for finding in findings), findings
    assert any("is listed open but the tree still shows it closed" in finding
               for finding in findings), findings


def test_an_implemented_claim_the_tree_contradicts_is_reported(tmp_path):
    """The mirror: the registry says done and the manifest's checks do not hold."""
    document = registry(tmp_path)
    (tmp_path / "src" / "route.py").unlink()
    findings = audit(document, tmp_path)
    assert any("no longer holds in the tree" in finding for finding in findings), findings


# --- the manifest cannot be deleted, emptied or narrowed -------------------------


def test_a_missing_manifest_is_unusable(tmp_path):
    with pytest.raises(checker.RegistryUnusable, match="manifest is missing"):
        checker.audit(registry(tmp_path), tmp_path, tmp_path / "nowhere.json")


def test_a_manifest_that_does_not_cover_a_card_is_unusable(tmp_path):
    document = registry(tmp_path)
    narrowed = manifest()
    narrowed["cards"] = {}
    with pytest.raises(checker.RegistryUnusable, match="does not cover VF-CL-0X"):
        audit(document, tmp_path, narrowed)


def test_a_manifest_naming_a_card_the_registry_does_not_have_is_unusable(tmp_path):
    document = registry(tmp_path)
    extra = manifest()
    extra["cards"]["VF-CL-99"] = {"impliesImplemented": True, "checks": [], "closedBlockers": {}}
    with pytest.raises(checker.RegistryUnusable, match="does not have"):
        audit(document, tmp_path, extra)


def test_a_manifest_with_the_wrong_schema_version_is_unusable(tmp_path):
    document = registry(tmp_path)
    old = manifest()
    old["schemaVersion"] = "vf-cl-registry-manifest:0"
    with pytest.raises(checker.RegistryUnusable, match="schemaVersion"):
        audit(document, tmp_path, old)


def test_an_assertion_with_no_checks_is_unusable(tmp_path):
    """An entry that claims something and checks nothing reads as coverage."""
    document = registry(tmp_path)
    hollow = manifest()
    hollow["cards"]["VF-CL-0X"]["checks"] = []
    with pytest.raises(checker.RegistryUnusable, match="with no checks"):
        audit(document, tmp_path, hollow)


def test_an_entry_that_asserts_nothing_has_to_say_why(tmp_path):
    document = registry(tmp_path)
    silent = manifest()
    silent["cards"]["VF-CL-0X"] = {"impliesImplemented": None, "checks": [],
                                   "closedBlockers": {}}
    with pytest.raises(checker.RegistryUnusable, match="asserts nothing and does not say why"):
        audit(document, tmp_path, silent)

    spoken = manifest()
    spoken["cards"]["VF-CL-0X"].update(
        impliesImplemented=None,
        why="a review card ships documents whose existence re-derives nothing",
        checks=[],
    )
    # The closed blocker keeps its checks: saying nothing about implemented is not
    # permission to say nothing about what was closed.
    assert audit(document, tmp_path, spoken) == []


@pytest.mark.parametrize("value", [1, "done", "yes"])
def test_an_implies_value_outside_the_four_is_unusable(tmp_path, value):
    document = registry(tmp_path)
    odd = manifest()
    odd["cards"]["VF-CL-0X"]["impliesImplemented"] = value
    with pytest.raises(checker.RegistryUnusable, match="impliesImplemented"):
        audit(document, tmp_path, odd)


def test_one_is_not_true_when_the_tree_is_compared(tmp_path):
    """`1 == True` in Python. A registry saying 1 must not read as done."""
    document = registry(tmp_path)
    document["cards"][0]["implemented"] = 1
    findings = audit(document, tmp_path)
    assert any("implemented is 1" in finding for finding in findings), findings


# --- a local gap is not a blocker -------------------------------------------------


def test_a_local_gap_filed_as_a_blocker_is_reported(tmp_path):
    """The restore drill was filed as an external precondition for two rounds.

    It was measured in hosted CI the whole time. A gap in one machine's measurement is not
    a gap in the work, and the registry has to keep the two apart.
    """
    document = registry(tmp_path)
    card = document["cards"][0]
    card["blockers"] = ["tests/integration/test_recovery_drill.py"]
    card["localUnmeasured"] = [{
        "what": "tests/integration/test_recovery_drill.py",
        "condition": "no CX01 container on this workstation",
        "measuredIn": "hosted Core run 36521298082 at 6fc0428b: 0 skips, 20 passed",
    }]
    findings = audit(document, tmp_path)
    assert any("both a local gap and a blocker" in finding for finding in findings), findings


def test_a_local_gap_must_say_where_it_is_measured(tmp_path):
    document = registry(tmp_path)
    document["cards"][0]["localUnmeasured"] = [
        {"what": "tests/integration/test_recovery_drill.py", "condition": "no container"}
    ]
    findings = audit(document, tmp_path)
    assert any("where it is measured instead" in finding for finding in findings), findings


def test_a_local_gap_that_names_where_it_is_measured_is_accepted(tmp_path):
    document = registry(tmp_path)
    document["cards"][0]["localUnmeasured"] = [{
        "what": "tests/integration/test_recovery_drill.py",
        "condition": "no CX01 container on this workstation",
        "measuredIn": "hosted Core run 36521298082 at 6fc0428b: 0 skips, 20 passed",
    }]
    assert audit(document, tmp_path) == []


# --- and the shipped pair -------------------------------------------------------


def test_the_shipped_registry_records_the_hosted_run_that_closed_the_drill():
    """The correction has to carry the evidence, not just drop the blocker."""
    document = json.loads(
        (checker.DEFAULT_REGISTRY).read_text(encoding="utf-8")
    )
    hosted = document["verifiedAgainst"]["hostedRun"]
    assert hosted["runId"] == "36521298082"
    assert hosted["headSha"].startswith("6fc0428b")
    assert hosted["conclusion"] == "success"
    four = next(card for card in document["cards"] if card["id"] == "VF-CL-04")
    assert not [b for b in four["blockers"] if "restore-drill" in b]
    gap = next(entry for entry in four["localUnmeasured"]
               if entry["what"].endswith("test_recovery_drill.py"))
    assert "36521298082" in gap["measuredIn"]
    assert "collect_s12_acceptance_evidence.py" in four["ciVerifiedNote"]
