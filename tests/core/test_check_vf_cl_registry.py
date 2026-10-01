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

import datetime as dt
import hashlib
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


def test_a_path_absent_check_breaks_when_authoritative_evidence_arrives(tmp_path):
    check = {"kind": "path-absent", "path": "evidence/attestation.bundle.json"}
    assert checker.run_check(check, tmp_path) is None
    target = tmp_path / "evidence" / "attestation.bundle.json"
    target.parent.mkdir()
    target.write_text("{}", encoding="utf-8")
    assert checker.run_check(check, tmp_path) == (
        "evidence/attestation.bundle.json is already in the tree"
    )


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


# --- rule 7: the tree decides ciVerified, and the claim is bound to a receipt ----------
#
# The first version of this block tested the *shape* of the registry's run record, and
# Codex showed what that was worth: an invented run id, a different 40-hex head, a
# workflow nobody runs, invented steps, and all four at once -- five fabrications, zero
# findings. Every one of them is a case below, and each now has to die.


def receipt(tmp_path, **overrides):
    """A receipt as ``tools/record_vf_cl_ci_receipt.py`` writes one, sealed."""
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path,
                          capture_output=True, text=True, check=True).stdout.strip()
    document = {
        "schemaVersion": checker.RECEIPT_SCHEMA,
        "card": "VF-CL-0X",
        "repository": checker.RECEIPT_REPOSITORY,
        "workflowPath": ".github/workflows/fixture.yml",
        "runId": "36851875128",
        "event": "workflow_dispatch",
        "conclusion": "success",
        "headSha": head,
        "headBranch": "agent/claude/fixture",
        "claimedTree": head,
        "headRelationToClaimedTree": "same",
        "requiredSteps": ["Derive the thing", "Hold it to its shape"],
        "artifact": {
            "id": "11155274241",
            "name": f"fixture-{head}",
            "digest": "sha256:" + "1d" * 32,
            "expiresAt": "2099-12-30T10:52:59Z",
        },
        "inputDigests": {
            "artifactMetadataSha256": "a" * 64,
            "jobsMetadataSha256": "b" * 64,
            "runMetadataSha256": "c" * 64,
        },
        "recordedAt": "2026-10-02T00:00:00Z",
    }
    document.update(overrides)
    return seal(document)


def seal(document):
    body = {key: value for key, value in document.items()
            if key not in ("receiptSha256", "recordedAt")}
    document["receiptSha256"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        .encode("utf-8")
    ).hexdigest()
    return document


def with_receipt(tmp_path, document=None, path="docs/vf-cl-ci-receipts/VF-CL-0X.json"):
    target = tmp_path / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(document if document is not None else receipt(tmp_path)),
                      encoding="utf-8")
    return path


def ci_asserting(manifest_document, implies=False, path="docs/vf-cl-ci-receipts/VF-CL-0X.json"):
    """A manifest that names a receipt. ``implies`` is ``False`` by default, because rule 7c
    refuses ``true`` outright (#295 r2 F1) and the receipt is read wherever one is named."""
    entry = manifest_document["cards"]["VF-CL-0X"]
    entry["impliesCiVerified"] = implies
    entry["ciVerifiedChecks"] = [{"kind": "path-exists", "path": "src/route.py"}]
    entry["whyCiVerified"] = "the fixture names a receipt and claims nothing from it"
    entry["ciVerifiedReceipt"] = {
        "path": path,
        "workflowPath": ".github/workflows/fixture.yml",
        "requiredSteps": ["Derive the thing", "Hold it to its shape"],
        "artifactNamePrefix": "fixture-",
    }
    return manifest_document


def run_block(tmp_path, **overrides):
    """The registry's own block, agreeing with the fixture receipt."""
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path,
                          capture_output=True, text=True, check=True).stdout.strip()
    block = {
        "runId": "36851875128",
        "workflowPath": ".github/workflows/fixture.yml",
        "headSha": head,
        "conclusion": "success",
        "requiredSteps": ["Derive the thing", "Hold it to its shape"],
        "artifact": {"id": "11155274241", "digest": "sha256:" + "1d" * 32},
        "receipt": "docs/vf-cl-ci-receipts/VF-CL-0X.json",
    }
    block.update(overrides)
    return block


def bound(tmp_path, block_overrides=None, receipt_overrides=None, ci_verified=False):
    """A registry and manifest that name a receipt and agree about what it shows."""
    document = registry(tmp_path)
    document["cards"][0]["ciVerified"] = ci_verified
    with_receipt(tmp_path, receipt(tmp_path, **(receipt_overrides or {})))
    document["cards"][0]["ciVerifiedRun"] = run_block(tmp_path, **(block_overrides or {}))
    return document, ci_asserting(manifest())


def test_a_receipt_backed_claim_is_accepted(tmp_path):
    document, manifest_document = bound(tmp_path)
    assert audit(document, tmp_path, manifest_document) == []


def test_a_ci_verified_claim_the_tree_contradicts_is_reported(tmp_path):
    """The comparison itself, in the direction the tree can assert today.

    ``VF-CL-04`` said ``ciVerified: false`` with a reason that had stopped being true, and
    nothing compared that field to anything. Now the manifest's value and the registry's
    have to agree -- and since rule 7c refuses ``true``, the direction a card can get wrong
    is claiming ``true`` while the tree implies ``false``.
    """
    document, manifest_document = bound(tmp_path, ci_verified=True)
    findings = audit(document, tmp_path, manifest_document)
    assert any("the tree shows ciVerified=False but the registry says True" in finding
               for finding in findings), findings


def test_the_manifest_may_not_derive_a_true_ci_verified_at_all(tmp_path):
    """Rule 7c now opens only for an exact, cryptographically verified attestation."""
    manifest_document = ci_asserting(manifest(), implies=True)
    with pytest.raises(checker.RegistryUnusable) as unusable:
        audit(registry(tmp_path), tmp_path, manifest_document)
    assert "requires an exact ciVerifiedAttestation" in str(unusable.value)


def attestation_expectation(tmp_path):
    del tmp_path
    head = "a" * 40
    return {
        "receiptPath": "docs/vf-cl-ci-attestations/VF-CL-0X.json",
        "bundlePath": "docs/vf-cl-ci-attestations/VF-CL-0X.bundle.json",
        "repository": checker.RECEIPT_REPOSITORY,
        "workflowPath": ".github/workflows/fixture.yml",
        "headSha": head,
        "headRef": "refs/heads/fixture",
    }


def attested_receipt(tmp_path):
    expectation = attestation_expectation(tmp_path)
    return {
        "runId": "36930000000",
        "headSha": expectation["headSha"],
        "headRef": expectation["headRef"],
        "evidenceArtifact": {
            "id": "11190000000",
            "digest": "sha256:" + "d" * 64,
            "expiresAt": "2099-12-31T00:00:00Z",
        },
    }


def test_a_verified_attestation_can_derive_true(tmp_path, monkeypatch):
    document = registry(tmp_path)
    expectation = attestation_expectation(tmp_path)
    recorded_receipt = attested_receipt(tmp_path)
    document["cards"][0]["ciVerifiedAttestation"] = {
        **recorded_receipt,
        "receipt": expectation["receiptPath"],
        "bundle": expectation["bundlePath"],
    }
    manifest_document = ci_asserting(manifest(), implies=True)
    manifest_document["cards"]["VF-CL-0X"].pop("ciVerifiedReceipt", None)
    manifest_document["cards"]["VF-CL-0X"]["ciVerifiedAttestation"] = expectation
    monkeypatch.setattr(checker, "verify_ci_attestation", lambda *_args: recorded_receipt)
    assert audit(document, tmp_path, manifest_document) == []


def test_a_missing_or_invalid_attestation_is_fail_closed(tmp_path, monkeypatch):
    document = registry(tmp_path)
    expectation = attestation_expectation(tmp_path)
    document["cards"][0]["ciVerifiedAttestation"] = {}
    manifest_document = ci_asserting(manifest(), implies=True)
    manifest_document["cards"]["VF-CL-0X"].pop("ciVerifiedReceipt", None)
    manifest_document["cards"]["VF-CL-0X"]["ciVerifiedAttestation"] = expectation

    def refuse(*_args):
        raise checker.verify_vf_cl_ci_attestation.AttestationError("attestation bundle is missing")

    monkeypatch.setattr(checker, "verify_ci_attestation", refuse)
    findings = audit(document, tmp_path, manifest_document)
    assert any("authoritative CI attestation refused" in finding for finding in findings)


def test_an_expired_attested_artifact_cannot_derive_ci_verified(tmp_path, monkeypatch):
    expectation = attestation_expectation(tmp_path)
    receipt = attested_receipt(tmp_path)
    receipt["evidenceArtifact"]["expiresAt"] = "2026-10-01T00:00:00Z"
    recorded = {
        **receipt,
        "receipt": expectation["receiptPath"],
        "bundle": expectation["bundlePath"],
    }
    monkeypatch.setattr(checker, "verify_ci_attestation", lambda *_args: receipt)

    findings = checker.ci_attestation_findings(
        "VF-CL-0X",
        recorded,
        expectation,
        tmp_path,
        now=dt.datetime(2026, 10, 2, tzinfo=dt.timezone.utc),
    )

    assert any("expired at 2026-10-01T00:00:00Z" in finding for finding in findings)


def test_recorded_attestation_must_copy_the_artifact_expiry(tmp_path, monkeypatch):
    expectation = attestation_expectation(tmp_path)
    receipt = attested_receipt(tmp_path)
    recorded = {
        **receipt,
        "receipt": expectation["receiptPath"],
        "bundle": expectation["bundlePath"],
    }
    recorded["evidenceArtifact"] = dict(recorded["evidenceArtifact"])
    recorded["evidenceArtifact"].pop("expiresAt")
    monkeypatch.setattr(checker, "verify_ci_attestation", lambda *_args: receipt)

    findings = checker.ci_attestation_findings(
        "VF-CL-0X", recorded, expectation, tmp_path,
    )

    assert any("evidenceArtifact.expiresAt differs" in finding for finding in findings)


@pytest.mark.parametrize("field", checker.ATTESTATION_EXPECTATION_KEYS)
def test_a_true_claim_requires_every_attestation_expectation_field(tmp_path, field):
    manifest_document = ci_asserting(manifest(), implies=True)
    manifest_document["cards"]["VF-CL-0X"].pop("ciVerifiedReceipt", None)
    expectation = attestation_expectation(tmp_path)
    expectation.pop(field)
    manifest_document["cards"]["VF-CL-0X"]["ciVerifiedAttestation"] = expectation
    with pytest.raises(checker.RegistryUnusable, match="exact ciVerifiedAttestation"):
        audit(registry(tmp_path), tmp_path, manifest_document)


def test_a_registry_run_id_cannot_differ_from_the_attested_receipt(tmp_path, monkeypatch):
    document = registry(tmp_path)
    expectation = attestation_expectation(tmp_path)
    receipt = attested_receipt(tmp_path)
    document["cards"][0]["ciVerifiedAttestation"] = {
        **receipt,
        "runId": "99999999999",
        "receipt": expectation["receiptPath"],
        "bundle": expectation["bundlePath"],
    }
    manifest_document = ci_asserting(manifest(), implies=True)
    manifest_document["cards"]["VF-CL-0X"].pop("ciVerifiedReceipt", None)
    manifest_document["cards"]["VF-CL-0X"]["ciVerifiedAttestation"] = expectation
    monkeypatch.setattr(checker, "verify_ci_attestation", lambda *_args: receipt)
    findings = audit(document, tmp_path, manifest_document)
    assert any("runId is '99999999999'" in finding for finding in findings)


def test_a_forged_and_resealed_receipt_is_why_true_is_refused(tmp_path):
    """The survival this rule is a response to, kept as a test rather than as a claim.

    This asserts that the binding does **not** catch a receipt forged together with the
    registry. It is the justification for rule 7c, and if someone ever makes it fail -- by
    adding verifiable attestation -- that is the moment rule 7c can be relaxed.
    """
    document, manifest_document = bound(
        tmp_path,
        block_overrides={"runId": "99999999999"},
        receipt_overrides={"runId": "99999999999"},
    )
    assert audit(document, tmp_path, manifest_document) == [], (
        "a forged-and-resealed pair still agrees with itself; that is why true is refused"
    )


def test_a_ci_verified_assertion_that_stopped_holding_is_reported(tmp_path):
    document, manifest_document = bound(tmp_path)
    manifest_document["cards"]["VF-CL-0X"]["ciVerifiedChecks"] = [
        {"kind": "path-exists", "path": "src/workflow-that-went-away.yml"}
    ]
    findings = audit(document, tmp_path, manifest_document)
    assert any("ciVerified assertion no longer holds in the tree" in finding
               for finding in findings), findings


# --- the five fabrications Codex got past the first version ---------------------------


@pytest.mark.parametrize(
    ("label", "overrides", "expected"),
    [
        ("an invented run id", {"runId": "99999999999"}, "runId is '99999999999'"),
        ("another 40-hex head", {"headSha": "0" * 40}, "headSha is"),
        ("a workflow nobody runs", {"workflowPath": ".github/workflows/nope.yml"},
         "workflowPath is"),
        ("invented steps", {"requiredSteps": ["Everything"]}, "requiredSteps differs"),
        ("a fabricated artifact digest",
         {"artifact": {"id": "11155274241", "digest": "sha256:" + "0" * 64}},
         "artifact.digest differs"),
        ("no receipt named", {"receipt": None}, "receipt is None"),
    ],
)
def test_a_fabricated_run_record_no_longer_passes(tmp_path, label, overrides, expected):
    document, manifest_document = bound(tmp_path, block_overrides=overrides)
    findings = audit(document, tmp_path, manifest_document)
    assert any(expected in finding for finding in findings), (label, findings)


def test_all_four_fabrications_at_once_are_each_reported(tmp_path):
    document, manifest_document = bound(tmp_path, block_overrides={
        "runId": "1", "headSha": "f" * 40,
        "workflowPath": "x", "requiredSteps": ["y"],
    })
    findings = audit(document, tmp_path, manifest_document)
    assert len(findings) >= 4, findings


# --- the receipt itself ---------------------------------------------------------------


def test_a_missing_receipt_is_reported(tmp_path):
    document, manifest_document = bound(tmp_path)
    (tmp_path / "docs/vf-cl-ci-receipts/VF-CL-0X.json").unlink()
    findings = audit(document, tmp_path, manifest_document)
    assert any("not readable JSON: FileNotFoundError" in finding for finding in findings), findings


def test_a_receipt_edited_after_it_was_built_is_reported(tmp_path):
    """The digest is not a signature -- anybody who can edit can reseal. What it closes is
    the *silent* edit, a value changed in one place and not the other."""
    document, manifest_document = bound(tmp_path)
    target = tmp_path / "docs/vf-cl-ci-receipts/VF-CL-0X.json"
    edited = json.loads(target.read_text(encoding="utf-8"))
    edited["runId"] = "99999999999"
    target.write_text(json.dumps(edited), encoding="utf-8")
    findings = audit(document, tmp_path, manifest_document)
    assert any("edited after it was built" in finding for finding in findings), findings


def test_a_resealed_receipt_still_cannot_move_the_head(tmp_path):
    """Resealing does not help: the artifact name is bound to the head, and the ancestry is
    re-measured here rather than read from the file."""
    head = "0" * 40
    document, manifest_document = bound(
        tmp_path,
        block_overrides={"headSha": head},
        receipt_overrides={"headSha": head, "claimedTree": head},
    )
    findings = audit(document, tmp_path, manifest_document)
    assert any("is not fixture-<the run's head>" in finding or
               "cannot tell whether the run's head is in the claimed tree" in finding
               for finding in findings), findings


def test_a_receipt_for_another_card_is_reported(tmp_path):
    document, manifest_document = bound(tmp_path, receipt_overrides={"card": "VF-CL-99"})
    findings = audit(document, tmp_path, manifest_document)
    assert any("the receipt is for 'VF-CL-99'" in finding for finding in findings), findings


def test_an_expired_artifact_is_reported(tmp_path):
    """A claim whose evidence can no longer be fetched has stopped being re-checkable --
    the standard ``aggregate_ac11_evidence.py`` applies with its freshness window."""
    document, manifest_document = bound(
        tmp_path,
        receipt_overrides={"artifact": {
            "id": "11155274241", "name": "fixture-x", "digest": "sha256:" + "1d" * 32,
            "expiresAt": "2020-01-01T00:00:00Z",
        }},
    )
    findings = audit(document, tmp_path, manifest_document)
    assert any("is no longer re-checkable" in finding for finding in findings), findings


@pytest.mark.parametrize("field", ["schemaVersion", "repository", "conclusion"])
def test_a_receipt_that_does_not_declare_itself_is_reported(tmp_path, field):
    document, manifest_document = bound(tmp_path, receipt_overrides={field: "something else"})
    findings = audit(document, tmp_path, manifest_document)
    assert findings, field


def test_a_receipt_of_a_different_workflow_is_reported(tmp_path):
    document, manifest_document = bound(
        tmp_path, receipt_overrides={"workflowPath": ".github/workflows/other.yml"})
    findings = audit(document, tmp_path, manifest_document)
    assert any("is a run of" in finding for finding in findings), findings


# --- the manifest holds the standard --------------------------------------------------


def test_a_receipt_expectation_that_is_not_an_object_is_unusable(tmp_path):
    manifest_document = ci_asserting(manifest())
    manifest_document["cards"]["VF-CL-0X"]["ciVerifiedReceipt"] = "docs/receipt.json"
    with pytest.raises(checker.RegistryUnusable) as unusable:
        audit(registry(tmp_path), tmp_path, manifest_document)
    assert "ciVerifiedReceipt is not an object" in str(unusable.value)


@pytest.mark.parametrize("field", ["path", "workflowPath", "artifactNamePrefix"])
def test_a_receipt_expectation_missing_a_field_is_unusable(tmp_path, field):
    manifest_document = ci_asserting(manifest())
    manifest_document["cards"]["VF-CL-0X"]["ciVerifiedReceipt"].pop(field)
    with pytest.raises(checker.RegistryUnusable) as unusable:
        audit(registry(tmp_path), tmp_path, manifest_document)
    assert field in str(unusable.value)


@pytest.mark.parametrize("value", [[], "Derive the thing", [""], [3]])
def test_a_receipt_expectation_without_steps_is_unusable(tmp_path, value):
    manifest_document = ci_asserting(manifest())
    manifest_document["cards"]["VF-CL-0X"]["ciVerifiedReceipt"]["requiredSteps"] = value
    with pytest.raises(checker.RegistryUnusable) as unusable:
        audit(registry(tmp_path), tmp_path, manifest_document)
    assert "requiredSteps must name at least one step" in str(unusable.value)


def test_a_null_ci_verified_assertion_does_not_require_a_receipt(tmp_path):
    assert audit(registry(tmp_path), tmp_path) == []


def test_a_manifest_that_asserts_nothing_about_ci_verified_has_to_say_why(tmp_path):
    manifest_document = manifest()
    manifest_document["cards"]["VF-CL-0X"].pop("whyCiVerified")
    with pytest.raises(checker.RegistryUnusable) as unusable:
        audit(registry(tmp_path), tmp_path, manifest_document)
    assert "asserts nothing about ciVerified and does not say why" in str(unusable.value)


def test_a_manifest_that_omits_the_ci_verified_field_entirely_is_unusable(tmp_path):
    manifest_document = manifest()
    manifest_document["cards"]["VF-CL-0X"].pop("impliesCiVerified")
    with pytest.raises(checker.RegistryUnusable) as unusable:
        audit(registry(tmp_path), tmp_path, manifest_document)
    assert "does not say impliesCiVerified" in str(unusable.value)


@pytest.mark.parametrize("value", ["partial", "true", 1, 0])
def test_an_implies_ci_verified_outside_the_three_is_unusable(tmp_path, value):
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


# --- rule 8: a candidate tree does not inherit its verification ----------------------


def landed_candidate(tmp_path):
    """A registry whose candidate tree is reachable from a remote ref this clone knows."""
    document = registry(tmp_path)
    head = document["verifiedAgainst"]["tree"]
    subprocess.run(["git", "update-ref", "refs/remotes/origin/integration/all-agents-unified",
                    head], cwd=tmp_path, check=True)
    document["verifiedAgainst"]["candidate"] = True
    document["verifiedAgainst"]["reverifyAt"] = "integration/all-agents-unified"
    return document


def test_a_candidate_that_has_landed_must_be_re_verified(tmp_path):
    findings = audit(landed_candidate(tmp_path), tmp_path)
    assert any("is no longer a candidate: re-verify at the landed SHA" in finding
               for finding in findings), findings


def test_a_candidate_that_has_not_landed_is_left_alone(tmp_path):
    document = registry(tmp_path)
    subprocess.run(
        ["git", "-c", "user.email=t@example.com", "-c", "user.name=t",
         "commit", "-q", "--allow-empty", "-m", "a later commit"],
        cwd=tmp_path, check=True,
    )
    later = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path,
                           capture_output=True, text=True, check=True).stdout.strip()
    # The remote ref is BEHIND the candidate: the candidate has not landed.
    subprocess.run(["git", "update-ref", "refs/remotes/origin/integration/all-agents-unified",
                    document["verifiedAgainst"]["tree"]], cwd=tmp_path, check=True)
    document["verifiedAgainst"]["tree"] = later
    document["verifiedAgainst"]["candidate"] = True
    document["verifiedAgainst"]["reverifyAt"] = "integration/all-agents-unified"
    assert [f for f in audit(document, tmp_path) if "candidate" in f] == []


def test_a_candidate_without_a_reverify_target_is_reported(tmp_path):
    document = landed_candidate(tmp_path)
    document["verifiedAgainst"].pop("reverifyAt")
    findings = audit(document, tmp_path)
    assert any("does not say reverifyAt" in finding for finding in findings), findings


@pytest.mark.parametrize("value", ["yes", 1, 0, "true"])
def test_a_candidate_flag_that_is_not_a_boolean_is_reported(tmp_path, value):
    document = landed_candidate(tmp_path)
    document["verifiedAgainst"]["candidate"] = value
    findings = audit(document, tmp_path)
    assert any("which is not true or absent" in finding for finding in findings), findings


def test_a_reverify_target_this_clone_does_not_know_is_reported_as_itself(tmp_path):
    """Not knowing is not "has not landed". The shallow rule exists for the same reason."""
    document = landed_candidate(tmp_path)
    document["verifiedAgainst"]["reverifyAt"] = "no/such/ref"
    findings = audit(document, tmp_path)
    assert any("cannot be judged: this clone does not know origin/no/such/ref" in finding
               for finding in findings), findings


# --- the shipped pair ----------------------------------------------------------------


# --- r2 F2: the receipt's shape is exact -------------------------------------------------


def test_an_unknown_top_level_key_is_reported_however_it_is_sealed(tmp_path):
    """Codex added ``unexpected`` and re-hashed, and the first version exited 0.

    A document that may carry extra keys has a digest that covers fields nobody reads.
    """
    document, manifest_document = bound(tmp_path, receipt_overrides={"unexpected": "whatever"})
    findings = audit(document, tmp_path, manifest_document)
    assert any("key set is not exact" in finding and "unexpected" in finding
               for finding in findings), findings


def test_a_missing_top_level_key_is_reported(tmp_path):
    document, manifest_document = bound(tmp_path)
    target = tmp_path / "docs/vf-cl-ci-receipts/VF-CL-0X.json"
    partial = json.loads(target.read_text(encoding="utf-8"))
    partial.pop("headBranch")
    target.write_text(json.dumps(seal(partial)), encoding="utf-8")
    findings = audit(document, tmp_path, manifest_document)
    assert any("missing ['headBranch']" in finding for finding in findings), findings


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (lambda r: r["artifact"].__setitem__("extra", 1), "artifact key set is not exact"),
        (lambda r: r["artifact"].pop("expiresAt"), "artifact key set is not exact"),
        (lambda r: r["inputDigests"].pop("jobsMetadataSha256"), "inputDigests key set"),
        (lambda r: r["inputDigests"].__setitem__("extraSha256", "a" * 64), "inputDigests key set"),
        (lambda r: r["inputDigests"].__setitem__("jobsMetadataSha256", "nope"), "not a sha256"),
    ],
)
def test_a_nested_key_set_that_is_not_exact_is_reported(tmp_path, mutate, expected):
    document, manifest_document = bound(tmp_path)
    target = tmp_path / "docs/vf-cl-ci-receipts/VF-CL-0X.json"
    edited = json.loads(target.read_text(encoding="utf-8"))
    mutate(edited)
    target.write_text(json.dumps(seal(edited)), encoding="utf-8")
    findings = audit(document, tmp_path, manifest_document)
    assert any(expected in finding for finding in findings), findings


def test_the_shipped_receipt_has_the_exact_key_sets():
    shipped = json.loads(
        (checker.REPO_ROOT / "docs/vf-cl-ci-receipts/VF-CL-04.json").read_text(encoding="utf-8")
    )
    assert set(shipped) == checker.RECEIPT_KEYS
    assert set(shipped["artifact"]) == checker.RECEIPT_ARTIFACT_KEYS
    assert set(shipped["inputDigests"]) == checker.RECEIPT_INPUT_KEYS


def test_the_shipped_pair_derives_the_card_whose_workflow_names_its_own_tools():
    """The shipped assertion, read rather than assumed.

    ``VF-CL-04`` is the one card rule 7 asserts, and the chain is literal: the workflow
    runs this card's collector and then the gate over what it produced, and the collector
    is where the two named observations come from. The other cards state ``null`` and say
    why -- a lane that runs a whole directory cannot distinguish them.
    """
    manifest_document = json.loads(checker.DEFAULT_MANIFEST.read_text(encoding="utf-8"))
    cards = manifest_document["cards"]
    # False, and derived: the implementation exists, but no authoritative bundle is committed
    # yet. Adding one breaks this assertion and forces a cryptographically verified true claim.
    assert cards["VF-CL-04"]["impliesCiVerified"] is False
    assert any(
        check["kind"] == "path-absent"
        and check["path"] == "docs/vf-cl-ci-attestations/VF-CL-04.bundle.json"
        for check in cards["VF-CL-04"]["ciVerifiedChecks"]
    )
    texts = [check.get("text") or check["path"]
             for check in cards["VF-CL-04"]["ciVerifiedChecks"]]
    assert "python tools/collect_s12_acceptance_evidence.py" in texts
    assert "python tools/check_s12_acceptance_shape.py" in texts
    assert "uses: actions/attest@v4" in texts
    assert "python tools/verify_vf_cl_ci_attestation.py" in texts
    assert "pitr-configuration-possible" in texts
    assert "pitr-rehearsal-dry-run-observed" in texts
    for name in ("VF-CL-01", "VF-CL-02", "VF-CL-03", "VF-CL-05"):
        assert cards[name]["impliesCiVerified"] is None, name
        assert cards[name]["whyCiVerified"].strip(), name

    registry_document = json.loads(checker.DEFAULT_REGISTRY.read_text(encoding="utf-8"))
    four = next(card for card in registry_document["cards"] if card["id"] == "VF-CL-04")
    assert four["ciVerified"] is False
    # The run block stays -- as a measurement record bound to the receipt, not as a basis.
    assert four["ciVerifiedRun"]["runId"].isdigit()
    assert four["ciVerifiedRun"]["conclusion"] == "success"
    assert "MEASUREMENT RECORD" in four["ciVerifiedNote"]
    # The note may recount why it *was* false -- that is history -- but it must not still
    # state it as the present, and it has to name the workflow that changed the answer.
    assert "s12-acceptance-evidence.yml" in four["ciVerifiedNote"]
    assert "stays false" not in four["ciVerifiedNote"]


def test_the_shipped_receipt_is_the_one_the_manifest_expects():
    """The receipt is a committed file, so its agreement with the pair is checkable here."""
    manifest_document = json.loads(checker.DEFAULT_MANIFEST.read_text(encoding="utf-8"))
    expectation = manifest_document["cards"]["VF-CL-04"]["ciVerifiedReceipt"]
    shipped = json.loads(
        (checker.REPO_ROOT / expectation["path"]).read_text(encoding="utf-8")
    )
    assert shipped["schemaVersion"] == checker.RECEIPT_SCHEMA
    assert shipped["card"] == "VF-CL-04"
    assert shipped["workflowPath"] == expectation["workflowPath"]
    assert sorted(shipped["requiredSteps"]) == sorted(expectation["requiredSteps"])
    assert shipped["artifact"]["name"] == expectation["artifactNamePrefix"] + shipped["headSha"]
    body = {key: value for key, value in shipped.items()
            if key not in ("receiptSha256", "recordedAt")}
    assert shipped["receiptSha256"] == hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        .encode("utf-8")
    ).hexdigest()


def test_the_shipped_registry_marks_its_tree_as_a_pre_landing_candidate():
    """Rule 8's half of the shipped pair: the tree is a train candidate, and says so."""
    registry_document = json.loads(checker.DEFAULT_REGISTRY.read_text(encoding="utf-8"))
    verified = registry_document["verifiedAgainst"]
    assert verified["candidate"] is True
    assert verified["reverifyAt"] == "integration/all-agents-unified"
    assert verified["ref"].startswith("coord/")


# --- r3 F1: an exact key set says nothing about what is in the keys ---------------------


def test_every_receipt_key_is_typed():
    """A key added to the schema without a rule is a key nobody typed.

    Held as set equality rather than as a count: the two lists drift apart silently
    otherwise, and the drift would read as coverage.
    """
    typed = {key for key, _check, _message in checker.RECEIPT_FIELD_RULES}
    assert typed == checker.RECEIPT_KEYS
    artifact_typed = {key for key, _check, _message in checker.RECEIPT_ARTIFACT_RULES}
    assert artifact_typed == checker.RECEIPT_ARTIFACT_KEYS


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        # The one Codex found: outside the canonical digest, so no re-hash is needed.
        ("recordedAt", 123, "must be a UTC RFC3339 timestamp"),
        ("recordedAt", "2026-10-02", "must be a UTC RFC3339 timestamp"),
        ("schemaVersion", "vf-cl-ci-receipt:2", "must be 'vf-cl-ci-receipt:1'"),
        ("card", "VF-CL-4", "must be a VF-CL card id"),
        ("repository", "someone/else", "must be the canonical repository"),
        ("workflowPath", "tools/whatever.py", "must be a workflow file path"),
        ("runId", 36851875128, "must be a run id written as digits in a string"),
        ("runId", "36851875128x", "must be a run id written as digits in a string"),
        ("event", "schedule", "must be an opt-in event"),
        ("conclusion", "failure", "must be 'success'"),
        ("headSha", "40b3ec78", "must be a full 40-hex commit"),
        ("headBranch", ["main"], "must be a branch name"),
        ("headBranch", "", "must be a branch name"),
        ("claimedTree", None, "must be a full 40-hex commit"),
        ("headRelationToClaimedTree", "descendant", "must be 'same' or 'ancestor'"),
        ("requiredSteps", [], "must be a non-empty list of non-empty strings"),
        ("requiredSteps", ["ok", "  "], "must be a non-empty list of non-empty strings"),
        ("requiredSteps", "Derive the thing", "must be a non-empty list of non-empty strings"),
        ("artifact", ["id"], "must be an object"),
        ("inputDigests", "none", "must be an object"),
    ],
)
def test_a_receipt_field_of_the_wrong_type_is_reported(tmp_path, field, value, expected):
    document, manifest_document = bound(tmp_path, receipt_overrides={field: value})
    findings = audit(document, tmp_path, manifest_document)
    assert any(expected in finding for finding in findings), (field, findings)


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("id", 11155274241, "artifact.id must be an artifact id"),
        ("id", "", "artifact.id must be an artifact id"),
        ("name", "dir/name", "artifact.name must be an artifact name"),
        ("digest", "0" * 64, "artifact.digest must be 'sha256:<64 hex>'"),
        ("digest", "sha256:zz", "artifact.digest must be 'sha256:<64 hex>'"),
        ("expiresAt", 0, "artifact.expiresAt must be a UTC RFC3339 timestamp"),
        ("expiresAt", "2099-12-30 10:52:59", "artifact.expiresAt must be a UTC RFC3339"),
    ],
)
def test_an_artifact_field_of_the_wrong_type_is_reported(tmp_path, field, value, expected):
    # The repository has to exist before a receipt can name its HEAD, so the fixture runs
    # first and the artifact is edited in the file it wrote.
    document, manifest_document = bound(tmp_path)
    target = tmp_path / "docs/vf-cl-ci-receipts/VF-CL-0X.json"
    edited = json.loads(target.read_text(encoding="utf-8"))
    edited["artifact"][field] = value
    target.write_text(json.dumps(seal(edited)), encoding="utf-8")
    findings = audit(document, tmp_path, manifest_document)
    assert any(expected in finding for finding in findings), (field, findings)


def test_a_receipt_whose_own_digest_is_not_a_digest_is_reported(tmp_path):
    """Written unsealed on purpose: the fixture re-seals, and this field is the seal."""
    document, manifest_document = bound(tmp_path)
    target = tmp_path / "docs/vf-cl-ci-receipts/VF-CL-0X.json"
    edited = json.loads(target.read_text(encoding="utf-8"))
    edited["receiptSha256"] = "nope"
    target.write_text(json.dumps(edited), encoding="utf-8")
    findings = audit(document, tmp_path, manifest_document)
    assert any("receiptSha256 must be a sha256" in finding for finding in findings), findings


def test_the_shipped_receipt_has_no_field_of_the_wrong_type():
    shipped = json.loads(
        (checker.REPO_ROOT / "docs/vf-cl-ci-receipts/VF-CL-04.json").read_text(encoding="utf-8")
    )
    assert checker.receipt_field_findings(shipped) == []


# --- r3 F2: json.loads keeps the last of two identical keys -----------------------------


def test_a_duplicate_key_in_the_manifest_is_unusable(tmp_path):
    """The mistake this closes, reproduced.

    An edit added ``whyCiVerified`` to an entry that already had one, and ``json.loads``
    kept the **last** -- so the new reason was replaced by the old one and nothing said so.
    """
    target = tmp_path / "manifest.json"
    target.write_text(
        '{"schemaVersion": "%s", "cards": {"VF-CL-0X": {"why": "new", "why": "old"}}}'
        % checker.MANIFEST_SCHEMA,
        encoding="utf-8",
    )
    with pytest.raises(checker.RegistryUnusable) as unusable:
        checker.load_manifest(target, ["VF-CL-0X"])
    assert "duplicate JSON key 'why'" in str(unusable.value)


def test_a_duplicate_key_in_the_registry_is_unusable(tmp_path):
    target = tmp_path / "registry.json"
    target.write_text('{"version": "1", "version": "2"}', encoding="utf-8")
    with pytest.raises(checker.RegistryUnusable) as unusable:
        checker.load_json_strictly(target, "the registry")
    assert "duplicate JSON key 'version'" in str(unusable.value)


def test_a_duplicate_key_in_the_receipt_is_reported_as_drift(tmp_path):
    """A finding rather than unusable: a bad receipt is one card's drift, and the rest of
    the registry can still be judged."""
    document, manifest_document = bound(tmp_path)
    (tmp_path / "docs/vf-cl-ci-receipts/VF-CL-0X.json").write_text(
        '{"card": "VF-CL-0X", "card": "VF-CL-0X"}', encoding="utf-8"
    )
    findings = audit(document, tmp_path, manifest_document)
    assert any("duplicate JSON key 'card'" in finding for finding in findings), findings


@pytest.mark.parametrize(
    "path",
    ["docs/vf-cl-task-registry.json", "docs/vf-cl-registry-manifest.json",
     "docs/vf-cl-ci-receipts/VF-CL-04.json"],
)
def test_the_shipped_files_have_no_duplicate_keys(path):
    """The regression for F2 itself: read the shipped pair the strict way."""
    checker.load_json_strictly(checker.REPO_ROOT / path, path)


def test_the_shipped_manifest_keeps_the_reason_the_last_edit_wrote():
    """The value that vanished, pinned by content.

    The duplicate meant VF-CL-04's ``whyCiVerified`` read as the older sentence. The reason
    this card remains false now is the missing authoritative bundle, not missing machinery.
    """
    manifest_document = checker.load_json_strictly(checker.DEFAULT_MANIFEST, "manifest")
    why = manifest_document["cards"]["VF-CL-04"]["whyCiVerified"]
    assert "support a GitHub/Sigstore-attested" in why
    assert "no authoritative bundle yet" in why
    assert "implementation-only commit cannot attest" in why


# --- r4: a timestamp that parses is not a timestamp in UTC -------------------------------


@pytest.mark.parametrize(
    "value",
    [
        "2026-12-30T10:52:59Z",
        "2026-10-01T18:23:14.418939Z",
        "2026-10-01T18:23:14+00:00",
    ],
)
def test_the_utc_forms_this_registry_writes_are_accepted(value):
    assert checker._is_utc_timestamp(value)


@pytest.mark.parametrize(
    ("value", "why"),
    [
        ("2026-10-01T18:23:14+09:00", "an offset that is not UTC"),
        ("2026-10-01 18:23:14Z", "a space separator fromisoformat happens to accept"),
        ("2026-10-01T18:23:14", "no offset at all"),
        ("2026-10-01T18:23:14-00:00", "RFC3339's 'offset unknown', which is not UTC"),
        ("2026-10-01t18:23:14z", "lower case"),
        ("2026-13-01T10:00:00Z", "a month that does not exist"),
        ("2026-10-32T10:00:00Z", "a day that does not exist"),
        ("2026-10-01T18:23:14.1234567890Z", "more fractional digits than the form allows"),
        (123, "not a string"),
        (None, "not a string"),
    ],
)
def test_a_timestamp_that_is_not_utc_rfc3339_is_refused(value, why):
    """``fromisoformat`` is far more generous than RFC3339 (#295 r4).

    Checking only that a timezone *exists* accepted ``+09:00`` and a space separator. These
    values are compared and sorted across machines, so the form and the offset are both
    pinned -- and the parse still runs, because a pattern alone admits month 13.
    """
    assert not checker._is_utc_timestamp(value), why


@pytest.mark.parametrize("field", ["recordedAt"])
@pytest.mark.parametrize(
    "value", ["2026-10-01T18:23:14+09:00", "2026-10-01 18:23:14Z"]
)
def test_a_receipt_timestamp_that_is_not_utc_is_reported(tmp_path, field, value):
    document, manifest_document = bound(tmp_path, receipt_overrides={field: value})
    findings = audit(document, tmp_path, manifest_document)
    assert any(f"{field} must be a UTC RFC3339 timestamp" in finding
               for finding in findings), findings


@pytest.mark.parametrize(
    "value", ["2099-12-30T10:52:59+09:00", "2099-12-30 10:52:59Z"]
)
def test_an_artifact_expiry_that_is_not_utc_is_reported(tmp_path, value):
    document, manifest_document = bound(tmp_path)
    target = tmp_path / "docs/vf-cl-ci-receipts/VF-CL-0X.json"
    edited = json.loads(target.read_text(encoding="utf-8"))
    edited["artifact"]["expiresAt"] = value
    target.write_text(json.dumps(seal(edited)), encoding="utf-8")
    findings = audit(document, tmp_path, manifest_document)
    assert any("artifact.expiresAt must be a UTC RFC3339 timestamp" in finding
               for finding in findings), findings


def test_the_shipped_receipt_timestamps_are_utc():
    shipped = json.loads(
        (checker.REPO_ROOT / "docs/vf-cl-ci-receipts/VF-CL-04.json").read_text(encoding="utf-8")
    )
    assert checker._is_utc_timestamp(shipped["recordedAt"])
    assert checker._is_utc_timestamp(shipped["artifact"]["expiresAt"])
