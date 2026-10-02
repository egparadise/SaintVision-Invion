"""The approval review wire fixture stays aligned with the generated provider model."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from inv.generated.models import ApprovalReviewView

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = (
    ROOT / "contracts/fixtures/approval-review-response.json",
    ROOT / "contracts/fixtures/approval-review-build-response.json",
)


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda path: path.stem)
def test_shared_approval_review_fixture_matches_generated_provider_model(fixture):
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    parsed = ApprovalReviewView.model_validate(payload)
    assert parsed.model_dump(by_alias=True, mode="json", exclude_unset=True) == payload


@pytest.mark.parametrize("damage", ["missing-policy-digest", "extra-review-field"])
def test_generated_provider_model_rejects_approval_review_fixture_drift(damage):
    payload = json.loads(FIXTURES[0].read_text(encoding="utf-8"))
    if damage == "missing-policy-digest":
        payload.pop("policyDigest")
    else:
        payload["inventedApprovalState"] = "approved"

    with pytest.raises(ValidationError):
        ApprovalReviewView.model_validate(payload)
