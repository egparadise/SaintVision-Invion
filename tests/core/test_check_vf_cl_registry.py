"""The registry is how work gets picked, so a stale entry sends someone somewhere wrong.

Two entries had gone stale before this existed. One said an implementation was partial
when its request path had landed, and one said a drill was waiting for a pull request
that had already merged -- anyone waiting for it would have waited forever. Nothing
validated the file, which is why neither was noticed.

These tests pin the drift classes that actually happened, plus the ones the same shape
allows. The first two are the historical mistakes, reproduced.
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
                "closedBlockers": [
                    {
                        "blocker": "the-request-path-was-missing",
                        "checks": [
                            {"kind": "path-exists", "path": "src/route.py"},
                            {"kind": "references", "path": "src/route.py",
                             "text": "require_exact_declaration(manifest, declared)"},
                            {"kind": "references", "path": "src/mount.py",
                             "text": "route.register(router)"},
                        ],
                    }
                ],
            }
        ],
    }
    document.update(overrides)
    return document


def audit(document, tmp_path):
    return checker.audit(document, tmp_path)


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


def test_a_closed_blocker_with_prose_only_is_reported(tmp_path):
    """Prose is how the earlier entries went stale without anyone noticing."""
    document = registry(tmp_path)
    document["cards"][0]["closedBlockers"][0].pop("checks")
    findings = audit(document, tmp_path)
    assert any("carries no checks" in finding for finding in findings), findings


def test_evidence_that_stopped_holding_is_reported(tmp_path):
    document = registry(tmp_path)
    document["cards"][0]["closedBlockers"][0]["checks"][0]["path"] = "src/gone.py"
    findings = audit(document, tmp_path)
    assert any("not in the tree" in finding for finding in findings), findings


def test_a_reference_that_disappeared_is_reported(tmp_path):
    document = registry(tmp_path)
    (tmp_path / "src" / "route.py").write_text("# the call was removed\n", encoding="utf-8")
    findings = audit(document, tmp_path)
    assert any("no longer contains" in finding for finding in findings), findings


def test_an_absent_check_catches_something_coming_back(tmp_path):
    """The mirror of `references`: some closures are "this is no longer there"."""
    document = registry(tmp_path)
    document["cards"][0]["closedBlockers"][0]["checks"] = [
        {"kind": "absent", "path": "src/route.py", "text": "require_exact_declaration"}
    ]
    findings = audit(document, tmp_path)
    assert any("now contains" in finding for finding in findings), findings
    (tmp_path / "src" / "route.py").write_text("# removed\n", encoding="utf-8")
    assert audit(document, tmp_path) == []


def test_an_unknown_check_kind_is_unusable_not_silently_skipped(tmp_path):
    """A check nobody runs is worse than no check: it reads as verified."""
    document = registry(tmp_path)
    document["cards"][0]["closedBlockers"][0]["checks"] = [
        {"kind": "looks-fine-to-me", "path": "src/route.py"}
    ]
    with pytest.raises(checker.RegistryUnusable, match="unknown check kind"):
        audit(document, tmp_path)


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
    document = registry(tmp_path)
    document["cards"][0]["implemented"] = value
    assert audit(document, tmp_path) == []


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
    good = tmp_path / "good.json"
    good.write_text(json.dumps(registry(tmp_path)), encoding="utf-8")
    assert checker.main(["--registry", str(good), "--root", str(tmp_path)]) == 0

    drifted = registry(tmp_path)
    drifted["cards"][0]["blockers"] = ["until-pr-126"]
    path = tmp_path / "drift.json"
    path.write_text(json.dumps(drifted), encoding="utf-8")
    assert checker.main(["--registry", str(path), "--root", str(tmp_path)]) == 1

    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    assert checker.main(["--registry", str(broken), "--root", str(tmp_path)]) == 2
