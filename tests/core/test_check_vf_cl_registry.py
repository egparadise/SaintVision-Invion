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


#: The blocker this project actually carried, verbatim. The regression Codex found is that
#: this exact string went back in as an open blocker and nothing objected.
RETIRED = "restore-drill-19-skips-need-CX01_CONTAINER-17-and-INV_TEST_ARCHIVER_IMAGE-2"


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
                # Rule 7 asserts nothing by default, so the tests that are about other
                # rules stay about them. The tests that are about rule 7 opt in below.
                "impliesCiVerified": None,
                "whyCiVerified": "the fixture lane runs a directory, so the tree cannot say it",
                "ciVerifiedChecks": [],
                "forbiddenBlockers": [RETIRED],
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


def local_gap(**overrides):
    gap = {
        "what": "tests/integration/test_recovery_drill.py",
        "condition": "no CX01 container on this workstation",
        "measuredIn": "hosted Core run 36521298082 at 6fc0428b: 0 skips, 20 passed",
        "blockerIdsThisReplaces": [RETIRED],
    }
    gap.update(overrides)
    return gap


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
    """The point of the exercise: the committed file re-derives from the real tree.

    The depth of the checkout is a fact about the environment, not about the registry. With
    full history every rule is re-derived and the checker must be silent. In a shallow
    checkout the two history rules cannot be re-derived and the checker says so rather than
    passing -- so this requires the shallow notice to be the **only** finding, which still
    holds every other rule to account.

    Written this way because hosted Core collects this test with the default fetch-depth 1,
    and a test that only works at one depth reports the environment as registry drift. Core
    is also given the history (see the workflow test below), so both halves are covered.
    """
    document = json.loads(checker.DEFAULT_REGISTRY.read_text(encoding="utf-8"))
    findings = checker.audit(document, checker.REPO_ROOT, checker.DEFAULT_MANIFEST)
    if checker.shallow_repository(checker.REPO_ROOT):
        assert len(findings) == 1, findings
        assert "shallow checkout" in findings[0], findings
    else:
        assert findings == []
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
    card["localUnmeasured"] = [local_gap()]
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
    document["cards"][0]["localUnmeasured"] = [local_gap()]
    assert audit(document, tmp_path) == []


# --- and the shipped pair -------------------------------------------------------


def test_the_shipped_registry_records_the_hosted_run_that_closed_the_drill():
    """The correction has to carry the evidence, not just drop the blocker.

    The run id is no longer written here. It was, and then the registry's tree moved and
    this test still passed while the recorded run described a different tree -- so the
    assertion is now the relationship rather than the value: the run that backs a claim
    about ``verifiedAgainst.tree`` has to be a run **at** that tree, and the local gap has
    to point at the same run it says the work is measured in.
    """
    document = json.loads(
        (checker.DEFAULT_REGISTRY).read_text(encoding="utf-8")
    )
    hosted = document["verifiedAgainst"]["hostedRun"]
    tree = document["verifiedAgainst"]["tree"]
    assert hosted["runId"].isdigit()
    assert hosted["headSha"].startswith(tree), (hosted["headSha"], tree)
    assert hosted["conclusion"] == "success"
    four = next(card for card in document["cards"] if card["id"] == "VF-CL-04")
    assert not [b for b in four["blockers"] if "restore-drill" in b]
    gap = next(entry for entry in four["localUnmeasured"]
               if entry["what"].endswith("test_recovery_drill.py"))
    assert hosted["runId"] in gap["measuredIn"]
    assert "collect_s12_acceptance_evidence.py" in four["ciVerifiedNote"]


# --- Codex r2 F1: the exact string that went back in unnoticed --------------------


def test_the_exact_retired_blocker_string_cannot_come_back(tmp_path):
    """The regression, verbatim.

    Rule 6 compared the gap's subject -- a file path -- against blocker text, so putting
    the real retired sentence back as an open blocker matched nothing and passed. The
    manifest now names the retired ids, and the registry cannot edit that list.
    """
    document = registry(tmp_path)
    card = document["cards"][0]
    card["blockers"] = [RETIRED]
    card["localUnmeasured"] = [local_gap()]
    findings = audit(document, tmp_path)
    assert any(f"{RETIRED} was retired by a correction and is open again" in finding
               for finding in findings), findings
    assert any("is still open" in finding for finding in findings), findings


def test_a_retired_blocker_is_caught_without_any_local_gap_recorded(tmp_path):
    """Deleting the gap must not delete the prohibition: the manifest holds it."""
    document = registry(tmp_path)
    document["cards"][0]["blockers"] = [RETIRED]
    document["cards"][0].pop("localUnmeasured", None)
    findings = audit(document, tmp_path)
    assert any("was retired by a correction and is open again" in finding
               for finding in findings), findings


def test_a_local_gap_must_say_which_blocker_ids_it_replaced(tmp_path):
    document = registry(tmp_path)
    document["cards"][0]["localUnmeasured"] = [local_gap(blockerIdsThisReplaces=[])]
    findings = audit(document, tmp_path)
    assert any("does not say which blocker ids it replaced" in finding
               for finding in findings), findings


def test_a_local_gap_cannot_claim_a_retirement_the_manifest_does_not_record(tmp_path):
    """Otherwise the registry writes its own permission slip."""
    document = registry(tmp_path)
    document["cards"][0]["localUnmeasured"] = [
        local_gap(blockerIdsThisReplaces=["something-i-decided-was-retired"])
    ]
    findings = audit(document, tmp_path)
    assert any("which the manifest does not list as retired" in finding
               for finding in findings), findings


@pytest.mark.parametrize("value", [["id", 7], "not-a-list", [""], [None]])
def test_a_manifest_forbidden_list_that_is_not_ids_is_unusable(tmp_path, value):
    document = registry(tmp_path)
    odd = manifest()
    odd["cards"]["VF-CL-0X"]["forbiddenBlockers"] = value
    with pytest.raises(checker.RegistryUnusable, match="forbiddenBlockers"):
        audit(document, tmp_path, odd)


# --- Codex r2 F2: True is 1 and False is 0 ---------------------------------------


@pytest.mark.parametrize("value", [False, True, "5", None, 5.0])
def test_a_count_that_is_not_a_whole_number_is_reported(tmp_path, value):
    """`acceptedCards: false` compared equal to the count 0 and produced no findings."""
    document = registry(tmp_path)
    document["acceptedCards"] = value
    findings = audit(document, tmp_path)
    assert any("acceptedCards is" in finding and "not a whole number" in finding
               for finding in findings), findings


def test_a_denominator_that_is_a_boolean_is_reported(tmp_path):
    document = registry(tmp_path)
    document["acceptanceDenominator"] = True
    findings = audit(document, tmp_path)
    assert any("acceptanceDenominator is True" in finding for finding in findings), findings


@pytest.mark.parametrize("field", checker.BOOLEAN_FIELDS)
@pytest.mark.parametrize("value", [1, 0, "true", None])
def test_a_state_field_that_is_not_a_boolean_is_reported(tmp_path, field, value):
    """`operationallyAccepted: 1` is not True by identity, so it was never counted as
    accepted -- while reading as accepted to a person. Neither half objected."""
    document = registry(tmp_path)
    document["cards"][0][field] = value
    findings = audit(document, tmp_path)
    assert any(f"{field} is {value!r}, which is not true or false" in finding
               for finding in findings), findings


def test_the_booleans_the_registry_ships_are_booleans():
    document = json.loads(checker.DEFAULT_REGISTRY.read_text(encoding="utf-8"))
    for field in checker.COUNT_FIELDS:
        assert type(document[field]) is int, field
    for card in document["cards"]:
        for field in checker.BOOLEAN_FIELDS:
            assert type(card[field]) is bool, f"{card['id']}.{field}"


def test_the_shipped_registry_records_which_ids_its_local_gap_retired():
    document = json.loads(checker.DEFAULT_REGISTRY.read_text(encoding="utf-8"))
    four = next(card for card in document["cards"] if card["id"] == "VF-CL-04")
    replaced = four["localUnmeasured"][0]["blockerIdsThisReplaces"]
    assert RETIRED in replaced
    assert "restore-drill-19-setup-skips-in-hosted-core-until-pr-126" in replaced


# --- the hosted failure: a shallow checkout cannot answer two of the rules ---------


def shallow_clone(tmp_path, document):
    """A real depth-1 clone whose registry names a commit the clone does not have.

    This is the hosted backend shape: actions/checkout@v4 defaults to fetch-depth 1, so
    `git merge-base --is-ancestor <tree> HEAD` failed for want of the commit and the
    checker said "not an ancestor" -- a wrong reason for a truncated history.
    """
    source = tmp_path / "source"
    source.mkdir()
    (source / "src").mkdir()
    (source / "src" / "route.py").write_text(
        "from ..adapters.model_import import require_exact_declaration\n"
        "require_exact_declaration(manifest, declared)\n",
        encoding="utf-8",
    )
    (source / "src" / "mount.py").write_text("route.register(router)\n", encoding="utf-8")
    git = ["git", "-c", "user.email=t@example.com", "-c", "user.name=t"]
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=source, check=True)
    subprocess.run(["git", "add", "-A"], cwd=source, check=True)
    subprocess.run([*git, "commit", "-q", "-m", "first"], cwd=source, check=True)
    first = subprocess.run(["git", "rev-parse", "HEAD"], cwd=source,
                           capture_output=True, text=True, check=True).stdout.strip()
    (source / "src" / "later.py").write_text("# a second commit\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=source, check=True)
    subprocess.run([*git, "commit", "-q", "-m", "Merge PR #126 (abc) into merge train"],
                   cwd=source, check=True)

    clone = tmp_path / "shallow"
    subprocess.run(
        ["git", "clone", "-q", "--depth", "1", source.resolve().as_uri(), str(clone)],
        check=True, capture_output=True,
    )
    is_shallow = subprocess.run(
        ["git", "rev-parse", "--is-shallow-repository"], cwd=clone,
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert is_shallow == "true", f"the fixture clone is not shallow: {is_shallow}"
    document["verifiedAgainst"] = {"tree": first}
    return clone


def test_a_shallow_checkout_is_reported_as_itself_not_as_drift(tmp_path):
    """The exact hosted failure, reproduced and renamed.

    Rule 2 is blinded too: `git log` in a shallow clone lists only the tip, so a blocker
    naming a merged pull request would go unnoticed. Neither may pass quietly, so the
    checker reports the truncation and fails.
    """
    document = registry(tmp_path)
    clone = shallow_clone(tmp_path, document)
    findings = checker.audit(document, clone, written(tmp_path, manifest()))
    assert any("shallow checkout" in finding for finding in findings), findings
    assert any("fetch-depth: 0" in finding for finding in findings), findings
    # The wrong reason must not be given: the commit is missing, not un-ancestral.
    assert not [finding for finding in findings if "is not an ancestor" in finding], findings


def test_the_shallow_finding_replaces_the_merged_pull_request_scan(tmp_path):
    """A blocker naming a merged PR is unverifiable in a shallow clone, not absolved."""
    document = registry(tmp_path)
    document["cards"][0]["blockers"] = ["until-pr-126"]
    clone = shallow_clone(tmp_path, document)
    findings = checker.audit(document, clone, written(tmp_path, manifest()))
    assert any("shallow checkout" in finding for finding in findings), findings
    # No claim is made about #126 either way; the truncation is the finding.
    assert not [f for f in findings if "records as merged" in f], findings


def test_a_full_clone_of_the_same_history_passes(tmp_path):
    """The control: with the history present, the same registry and tree agree."""
    document = registry(tmp_path)
    shallow = shallow_clone(tmp_path, document)
    full = tmp_path / "full"
    subprocess.run(
        ["git", "clone", "-q", (tmp_path / "source").resolve().as_uri(), str(full)],
        check=True, capture_output=True,
    )
    assert subprocess.run(
        ["git", "rev-parse", "--is-shallow-repository"], cwd=full,
        capture_output=True, text=True, check=True,
    ).stdout.strip() == "false"
    assert checker.shallow_repository(shallow) is True
    assert checker.shallow_repository(full) is False
    assert checker.audit(document, full, written(tmp_path, manifest())) == []


@pytest.mark.parametrize(
    ("workflow", "job", "next_job"),
    [
        ("backend.yml", "  backend:", "  mlflow-live:"),
        # Core's whole-suite pytest collects tests/core/ too, and it was left shallow: the
        # first fix covered backend.yml alone and train 4's Core run failed on this test.
        ("core.yml", "  core:", "  s01-storage-roundtrip:"),
    ],
)
def test_every_job_that_collects_this_check_has_the_history_it_needs(workflow, job, next_job):
    """The rules only run in CI if the job can answer them. Pinned per job.

    Judge the job, not the file. A job that collects this test with fetch-depth 1 gets the
    shallow notice instead of a re-derivation, which is honest but verifies nothing about
    the two history rules.
    """
    text = (checker.REPO_ROOT / ".github/workflows" / workflow).read_text(encoding="utf-8")
    section = text[text.index(job):text.index(next_job)]
    checkout = section.index("uses: actions/checkout@v4")
    setup = section.index("uses: actions/setup-python@v5")
    assert "fetch-depth: 0" in section[checkout:setup], section[checkout:setup]


# --- rule 7: the tree decides ciVerified too ------------------------------------------


def ci_asserting(manifest_document, implies=True):
    """The fixture manifest, asserting ciVerified over a file the tiny tree has."""
    entry = manifest_document["cards"]["VF-CL-0X"]
    entry["impliesCiVerified"] = implies
    entry["ciVerifiedChecks"] = [{"kind": "path-exists", "path": "src/route.py"}]
    entry.pop("whyCiVerified", None)
    return manifest_document


def ci_run(**overrides):
    run = {
        "runId": "36851875128",
        "workflow": "S12 Acceptance Evidence",
        "headSha": "40b3ec78ba63731dd94dcfdeb2d757381aee8a3b",
        "conclusion": "success",
        "steps": ["Derive the AC-12 acceptance items: success"],
    }
    run.update(overrides)
    return run


def test_a_ci_verified_claim_the_tree_contradicts_is_reported(tmp_path):
    """The drift this rule exists for, in the direction it actually happened.

    ``VF-CL-04`` said ``ciVerified: false`` with a note whose reason -- no workflow runs
    the collector -- had stopped being true. Nothing in the file could fault it, because
    nothing compared that field to anything.
    """
    document = registry(tmp_path)
    document["cards"][0]["ciVerified"] = False
    document["cards"][0]["ciVerifiedRun"] = ci_run()
    findings = audit(document, tmp_path, ci_asserting(manifest()))
    assert any("the tree shows ciVerified=True but the registry says False" in finding
               for finding in findings), findings


def test_a_ci_verified_claim_the_tree_supports_is_accepted(tmp_path):
    document = registry(tmp_path)
    document["cards"][0]["ciVerifiedRun"] = ci_run()
    assert audit(document, tmp_path, ci_asserting(manifest())) == []


def test_a_premature_ci_verified_is_reported(tmp_path):
    """The other direction: the flag up while the tree shows the lane is not there."""
    document = registry(tmp_path)
    manifest_document = ci_asserting(manifest(), implies=False)
    findings = audit(document, tmp_path, manifest_document)
    assert any("the tree shows ciVerified=False but the registry says True" in finding
               for finding in findings), findings


def test_a_ci_verified_assertion_that_stopped_holding_is_reported(tmp_path):
    document = registry(tmp_path)
    document["cards"][0]["ciVerifiedRun"] = ci_run()
    manifest_document = ci_asserting(manifest())
    manifest_document["cards"]["VF-CL-0X"]["ciVerifiedChecks"] = [
        {"kind": "path-exists", "path": "src/workflow-that-went-away.yml"}
    ]
    findings = audit(document, tmp_path, manifest_document)
    assert any("ciVerified assertion no longer holds in the tree" in finding
               for finding in findings), findings


def test_a_derived_ci_verified_must_name_the_run_that_showed_it(tmp_path):
    """This registry's own lesson as a rule: the flag does not go up before the evidence."""
    document = registry(tmp_path)
    findings = audit(document, tmp_path, ci_asserting(manifest()))
    assert any("names no ciVerifiedRun" in finding for finding in findings), findings


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"conclusion": "failure"}, "so it shows nothing"),
        ({"conclusion": None}, "so it shows nothing"),
        ({"runId": "pending"}, "which is not a run id"),
        ({"runId": 36851875128}, None),           # an int is read as its digits
        ({"steps": []}, "names no steps"),
        ({"steps": ["  "]}, "names no steps"),
        ({"steps": "one step"}, "names no steps"),
        ({"headSha": "not-a-sha"}, "ciVerifiedRun.headSha"),
    ],
)
def test_a_named_run_that_shows_nothing_is_reported(tmp_path, overrides, expected):
    document = registry(tmp_path)
    document["cards"][0]["ciVerifiedRun"] = ci_run(**overrides)
    findings = audit(document, tmp_path, ci_asserting(manifest()))
    if expected is None:
        assert findings == [], findings
    else:
        assert any(expected in finding for finding in findings), findings


def test_a_null_ci_verified_assertion_does_not_require_a_run(tmp_path):
    """Asserting nothing must not become a back door for requiring nothing *and* saying
    nothing: the manifest has to say why, which the next test pins."""
    document = registry(tmp_path)
    assert audit(document, tmp_path) == []


def test_a_manifest_that_asserts_nothing_about_ci_verified_has_to_say_why(tmp_path):
    manifest_document = manifest()
    manifest_document["cards"]["VF-CL-0X"].pop("whyCiVerified")
    with pytest.raises(checker.RegistryUnusable) as unusable:
        audit(registry(tmp_path), tmp_path, manifest_document)
    assert "asserts nothing about ciVerified and does not say why" in str(unusable.value)


def test_a_manifest_that_omits_the_ci_verified_field_entirely_is_unusable(tmp_path):
    """Deleting an entry is a failure, not a silence -- the same rule as the rest."""
    manifest_document = manifest()
    manifest_document["cards"]["VF-CL-0X"].pop("impliesCiVerified")
    with pytest.raises(checker.RegistryUnusable) as unusable:
        audit(registry(tmp_path), tmp_path, manifest_document)
    assert "does not say impliesCiVerified" in str(unusable.value)


@pytest.mark.parametrize("value", ["partial", "true", 1, 0])
def test_an_implies_ci_verified_outside_the_three_is_unusable(tmp_path, value):
    """``implemented`` has a third value; this field does not. ``1`` is not ``True`` by
    identity, and that is how a count read as a boolean once already."""
    manifest_document = manifest()
    manifest_document["cards"]["VF-CL-0X"]["impliesCiVerified"] = value
    with pytest.raises(checker.RegistryUnusable) as unusable:
        audit(registry(tmp_path), tmp_path, manifest_document)
    assert "impliesCiVerified is" in str(unusable.value)


def test_an_asserted_ci_verified_with_no_checks_is_unusable(tmp_path):
    manifest_document = manifest()
    manifest_document["cards"]["VF-CL-0X"]["impliesCiVerified"] = True
    with pytest.raises(checker.RegistryUnusable) as unusable:
        audit(registry(tmp_path), tmp_path, manifest_document)
    assert "with no ciVerifiedChecks" in str(unusable.value)


def test_a_ci_verified_checks_value_that_is_not_a_list_is_unusable(tmp_path):
    manifest_document = manifest()
    manifest_document["cards"]["VF-CL-0X"]["ciVerifiedChecks"] = "src/route.py"
    with pytest.raises(checker.RegistryUnusable) as unusable:
        audit(registry(tmp_path), tmp_path, manifest_document)
    assert "ciVerifiedChecks array" in str(unusable.value)


def test_the_shipped_pair_derives_the_card_whose_workflow_names_its_own_tools():
    """The shipped assertion, read rather than assumed.

    ``VF-CL-04`` is the one card rule 7 asserts, and the chain is literal: the workflow
    runs this card's collector and then the gate over what it produced, and the collector
    is where the two named observations come from. The other cards state ``null`` and say
    why -- a lane that runs a whole directory cannot distinguish them.
    """
    manifest_document = json.loads(checker.DEFAULT_MANIFEST.read_text(encoding="utf-8"))
    cards = manifest_document["cards"]
    assert cards["VF-CL-04"]["impliesCiVerified"] is True
    texts = [check.get("text") or check["path"]
             for check in cards["VF-CL-04"]["ciVerifiedChecks"]]
    assert "python tools/collect_s12_acceptance_evidence.py" in texts
    assert "python tools/check_s12_acceptance_shape.py" in texts
    assert "pitr-configuration-possible" in texts
    assert "pitr-rehearsal-dry-run-observed" in texts
    for name in ("VF-CL-01", "VF-CL-02", "VF-CL-03", "VF-CL-05"):
        assert cards[name]["impliesCiVerified"] is None, name
        assert cards[name]["whyCiVerified"].strip(), name

    registry_document = json.loads(checker.DEFAULT_REGISTRY.read_text(encoding="utf-8"))
    four = next(card for card in registry_document["cards"] if card["id"] == "VF-CL-04")
    assert four["ciVerified"] is True
    assert four["ciVerifiedRun"]["runId"].isdigit()
    assert four["ciVerifiedRun"]["conclusion"] == "success"
    # The note may recount why it *was* false -- that is history -- but it must not still
    # state it as the present, and it has to name the workflow that changed the answer.
    assert "s12-acceptance-evidence.yml" in four["ciVerifiedNote"]
    assert "stays false" not in four["ciVerifiedNote"]
