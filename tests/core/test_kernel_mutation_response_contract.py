"""Approval challenge/decision response fixtures stay aligned to generated provider models."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from inv.generated.models import ApprovalChallenge, ApprovalView

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "contracts/fixtures"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_shared_challenge_fixture_matches_generated_provider_model():
    payload = _fixture("approval-challenge-response.json")
    parsed = ApprovalChallenge.model_validate(payload)
    assert parsed.model_dump(by_alias=True, mode="json", exclude_unset=True) == payload


def test_shared_decision_fixture_matches_generated_provider_model():
    payload = _fixture("approval-review-response.json")["approval"]
    parsed = ApprovalView.model_validate(payload)
    assert parsed.model_dump(by_alias=True, mode="json", exclude_unset=True) == payload


@pytest.mark.parametrize(
    ("model", "payload", "damage"),
    [
        (ApprovalChallenge, "approval-challenge-response.json", "missing-expiry"),
        (ApprovalChallenge, "approval-challenge-response.json", "extra-challenge-field"),
        (ApprovalView, "approval-review-response.json", "missing-policy-version"),
        (ApprovalView, "approval-review-response.json", "extra-approval-field"),
    ],
)
def test_generated_provider_models_reject_shared_fixture_drift(model, payload, damage):
    value = _fixture(payload)
    if model is ApprovalView:
        value = value["approval"]
    if damage == "missing-expiry":
        value.pop("expiresAt")
    elif damage == "extra-challenge-field":
        value["unexpectedChallengeState"] = "approved"
    elif damage == "missing-policy-version":
        value.pop("policyVersion")
    else:
        value["unexpectedApprovalState"] = "approved"

    with pytest.raises(ValidationError):
        model.model_validate(value)
