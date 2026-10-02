"""The AC-11 security allowlist is generated only from exact reviewed inputs."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import write_ac11_security_allowlist as tool  # noqa: E402


def loaded(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def inputs():
    return (
        loaded(tool.DEFAULT_SOURCE),
        loaded(tool.DEFAULT_POLICY),
        loaded(tool.DEFAULT_BASELINE),
    )


def test_committed_allowlist_is_exact_generated_output():
    source, policy, baseline = inputs()
    expected = tool.build_allowlist(source, policy, baseline)
    assert tool.render(expected) == tool.DEFAULT_OUTPUT.read_text(encoding="utf-8")
    assert set(expected["definerPolicySignatures"]) == set(policy["functions"])
    assert len(expected["definerPolicySignatures"]) == 15


@pytest.mark.parametrize("mutation", ["missing", "extra", "duplicate", "revision"])
def test_definer_review_cannot_shrink_expand_duplicate_or_change_revision(mutation):
    source, policy, baseline = inputs()
    if mutation == "missing":
        source["definerReview"]["signatures"].pop()
    elif mutation == "extra":
        source["definerReview"]["signatures"].append("public.unreviewed()")
    elif mutation == "duplicate":
        source["definerReview"]["signatures"].append(
            source["definerReview"]["signatures"][-1]
        )
    else:
        source["definerReview"]["policyRevision"] = "0058_release_acceptance_evidence"
    with pytest.raises(ValueError):
        tool.build_allowlist(source, policy, baseline)


@pytest.mark.parametrize("mutation", ["missing", "invented", "rules", "duplicate"])
def test_rls_decisions_must_exactly_cover_the_collector_baseline(mutation):
    source, policy, baseline = inputs()
    rows = source["rlsAcceptedDispositions"]
    if mutation == "missing":
        rows.pop()
    elif mutation == "invented":
        rows.append(
            {
                "role": "inv_app",
                "table": "public.projects",
                "rules": ["E4"],
                "disposition": "false-positive-with-proof",
                "proof": "invented",
            }
        )
    elif mutation == "rules":
        rows[-1]["rules"] = ["E3", "E4"]
    else:
        rows.append(copy.deepcopy(rows[-1]))
    with pytest.raises(ValueError):
        tool.build_allowlist(source, policy, baseline)


def test_inv_audit_reader_visibility_is_expiring_not_a_false_positive():
    source, policy, baseline = inputs()
    generated = tool.build_allowlist(source, policy, baseline)
    reader = next(
        row
        for row in generated["rlsAcceptedDispositions"]
        if row["role"] == "inv_audit_reader"
    )
    assert reader["table"] == "public.audit_events"
    assert reader["rules"] == ["E3", "E4", "E5"]
    assert reader["disposition"] == "accepted-with-expiry"
    assert reader["expiresAt"] == "2026-10-31T23:59:59+09:00"
