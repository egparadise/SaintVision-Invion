"""PG-free contract guards for S12 release acceptance writes (card 184).

The implementation deliberately comes later.  These tests pin the public body
before a route or migration exists, and make the security boundary visible:
the body contains a manifest target and Evidence references, never a user id,
bearer token, reauthentication proof, or free-form operator note.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError
from pydantic import ValidationError

from saintvision.api import schemas
from saintvision.api.problem import SYS_PREREQUISITES_UNAVAILABLE


ROOT = Path(__file__).resolve().parents[2]
HASH = "a" * 64
NOW = dt.datetime(2026, 10, 1, 9, 48, tzinfo=dt.timezone.utc)


def test_disabled_write_surface_has_a_distinct_nonretryable_prerequisite_code():
    assert SYS_PREREQUISITES_UNAVAILABLE == "SYS-0003"


def decision(**changes):
    body = {
        "acceptanceIdRef": "AC-12",
        "outcome": "accepted",
        "targetManifestSha256": HASH,
        "reasonCode": "RELEASE_ACCEPTANCE",
        "targetRefs": [{"targetId": "AC-12", "targetSha256": "b" * 64}],
        "measurementRefs": [
            {
                "evidenceId": "evidence:ac12:physical-lane",
                "evidenceSha256": "c" * 64,
                "observedAt": NOW.isoformat(),
            }
        ],
        "knownLimitations": [],
    }
    body.update(changes)
    return body


def test_decision_separates_targets_from_measurements_and_accepts_no_identity_input():
    parsed = schemas.ReleaseAcceptanceDecisionRequest.model_validate(decision())
    assert parsed.target_refs[0].target_id == "AC-12"
    assert parsed.measurement_refs[0].evidence_id == "evidence:ac12:physical-lane"

    forbidden = ("acceptedByUserId", "accessToken", "reauthenticationProof", "notes")
    for field in forbidden:
        with pytest.raises(ValidationError):
            schemas.ReleaseAcceptanceDecisionRequest.model_validate(
                {**decision(), field: "must-never-cross-the-wire"}
            )


@pytest.mark.parametrize(
    ("outcome", "limitations", "valid"),
    [
        ("accepted", [], True),
        ("accepted", ["not allowed"], False),
        ("conditional", ["physical restore remains blocked"], True),
        ("conditional", [], False),
        ("rejected", [], True),
        ("rejected", ["not allowed"], False),
    ],
)
def test_known_limitations_belong_only_to_a_conditional_decision(outcome, limitations, valid):
    body = decision(outcome=outcome, knownLimitations=limitations)
    if valid:
        schemas.ReleaseAcceptanceDecisionRequest.model_validate(body)
    else:
        with pytest.raises(ValidationError):
            schemas.ReleaseAcceptanceDecisionRequest.model_validate(body)


@pytest.mark.parametrize("field", ["targetRefs", "measurementRefs"])
def test_a_decision_requires_both_a_target_and_a_measurement(field):
    with pytest.raises(ValidationError):
        schemas.ReleaseAcceptanceDecisionRequest.model_validate(decision(**{field: []}))


@pytest.mark.parametrize(
    ("field", "duplicate"),
    [
        ("targetRefs", {"targetId": "AC-12", "targetSha256": "d" * 64}),
        (
            "measurementRefs",
            {
                "evidenceId": "evidence:ac12:physical-lane",
                "evidenceSha256": "d" * 64,
                "observedAt": NOW.isoformat(),
            },
        ),
    ],
)
def test_reference_identity_cannot_be_duplicated_with_different_content(field, duplicate):
    body = decision()
    body[field] = [*body[field], duplicate]
    with pytest.raises(ValidationError):
        schemas.ReleaseAcceptanceDecisionRequest.model_validate(body)


def test_second_operator_confirms_the_exact_proposal_and_manifest_only():
    parsed = schemas.ReleaseAcceptanceConfirmationRequest.model_validate(
        {"proposalDigest": "d" * 64, "targetManifestSha256": HASH}
    )
    assert parsed.proposal_digest == "d" * 64
    with pytest.raises(ValidationError):
        schemas.ReleaseAcceptanceConfirmationRequest.model_validate(
            {
                "proposalDigest": "d" * 64,
                "targetManifestSha256": HASH,
                "acceptedByUserId": "usr_forged",
            }
        )


def test_pending_proposal_can_never_have_decision_sign_off():
    body = {
        "proposalId": "proposal_01",
        "releaseId": "release_01",
        "acceptanceIdRef": "AC-12",
        "outcome": "accepted",
        "state": "pending_second_operator",
        "targetManifestSha256": HASH,
        "proposalDigest": "d" * 64,
        "requiredDistinctOperatorCount": 2,
        "proposalConfirmationCount": 1,
        "decisionSignOff": False,
        "expiresAt": (NOW + dt.timedelta(minutes=15)).isoformat(),
        "replayed": False,
    }
    schemas.ReleaseAcceptanceProposalResponse.model_validate(body)
    with pytest.raises(ValidationError):
        schemas.ReleaseAcceptanceProposalResponse.model_validate(
            {**body, "decisionSignOff": True}
        )


def test_distinct_operator_can_read_the_exact_pending_content_without_identity_data():
    body = {
        "proposalId": "proposal_01",
        "releaseId": "release_01",
        "acceptanceIdRef": "AC-12",
        "outcome": "accepted",
        "state": "pending_second_operator",
        "targetManifestSha256": HASH,
        "proposalDigest": "d" * 64,
        "reasonCode": "RELEASE_ACCEPTANCE",
        "targetRefs": decision()["targetRefs"],
        "measurementRefs": decision()["measurementRefs"],
        "knownLimitations": [],
        "requiredDistinctOperatorCount": 2,
        "proposalConfirmationCount": 1,
        "decisionSignOff": False,
        "expiresAt": (NOW + dt.timedelta(minutes=5)).isoformat(),
    }
    parsed = schemas.ReleaseAcceptanceProposalReviewResponse.model_validate(body)
    assert parsed.target_refs[0].target_sha256 == "b" * 64
    assert parsed.measurement_refs[0].evidence_sha256 == "c" * 64
    assert "acceptedByUserId" not in parsed.model_dump(by_alias=True)

    with pytest.raises(ValidationError):
        schemas.ReleaseAcceptanceProposalReviewResponse.model_validate(
            {**body, "acceptedByUserId": "must-not-become-a-directory"}
        )
    with pytest.raises(ValidationError):
        schemas.ReleaseAcceptanceProposalReviewResponse.model_validate(
            {**body, "knownLimitations": ["accepted cannot hide a limitation"]}
        )
    with pytest.raises(ValidationError):
        schemas.ReleaseAcceptanceProposalReviewResponse.model_validate(
            {**body, "decisionSignOff": True}
        )
    page = schemas.ReleaseAcceptanceProposalReviewPageResponse.model_validate(
        {"items": [body], "nextCursor": None}
    )
    assert page.items[0].proposal_id == "proposal_01"
    with pytest.raises(ValidationError):
        schemas.ReleaseAcceptanceProposalReviewPageResponse.model_validate(
            {"items": [body] * 101, "nextCursor": None}
        )
    with pytest.raises(ValidationError):
        schemas.ReleaseAcceptanceProposalReviewPageResponse.model_validate(
            {"items": [{**body, "decisionSignOff": True}]}
        )


@pytest.mark.parametrize(
    ("outcome", "count", "sign_off", "valid"),
    [
        ("accepted", 2, True, True),
        ("accepted", 1, False, False),
        ("accepted", 2, False, False),
        ("conditional", 1, False, True),
        ("conditional", 2, True, False),
        ("rejected", 1, False, True),
    ],
)
def test_only_a_two_person_accepted_record_has_decision_sign_off(
    outcome, count, sign_off, valid
):
    body = {
        "acceptanceId": "acceptance_01",
        "releaseId": "release_01",
        "acceptanceIdRef": "AC-12",
        "outcome": outcome,
        "state": "recorded",
        "acceptedManifestSha256": HASH,
        "manifestMatches": True,
        "decisionSignOff": sign_off,
        "decisionConfirmationCount": count,
        "decidedAt": NOW.isoformat(),
        "replayed": False,
    }
    if valid:
        schemas.ReleaseAcceptanceRecordedResponse.model_validate(body)
    else:
        with pytest.raises(ValidationError):
            schemas.ReleaseAcceptanceRecordedResponse.model_validate(body)


def test_withdrawal_is_a_closed_reason_and_the_withdrawn_row_can_never_sign():
    request = {
        "acceptedManifestSha256": HASH,
        "reasonCode": "security-concern",
    }
    schemas.ReleaseAcceptanceWithdrawalRequest.model_validate(request)
    with pytest.raises(ValidationError):
        schemas.ReleaseAcceptanceWithdrawalRequest.model_validate(
            {**request, "reasonCode": "free text explains too much"}
        )

    response = {
        "withdrawalId": "withdrawal_01",
        "acceptanceId": "acceptance_01",
        "releaseId": "release_01",
        "state": "withdrawn",
        "acceptedManifestSha256": HASH,
        "withdrawnAcceptanceCountsTowardSignOff": False,
        "operatorSignOff": False,
        "reasonCode": "security-concern",
        "withdrawnAt": NOW.isoformat(),
        "replayed": False,
    }
    schemas.ReleaseAcceptanceWithdrawalResponse.model_validate(response)
    # Another criterion may still have a valid accepted record.  The release
    # aggregate may therefore remain true, but this withdrawn row never counts.
    schemas.ReleaseAcceptanceWithdrawalResponse.model_validate(
        {**response, "operatorSignOff": True}
    )
    with pytest.raises(ValidationError):
        schemas.ReleaseAcceptanceWithdrawalResponse.model_validate(
            {**response, "withdrawnAcceptanceCountsTowardSignOff": True}
        )


def test_exported_contracts_are_closed_and_do_not_publish_identity_or_secret_fields():
    names = (
        "release-acceptance-decision-request",
        "release-acceptance-confirmation-request",
        "release-acceptance-proposal-response",
        "release-acceptance-proposal-review-response",
        "release-acceptance-proposal-review-page-response",
        "release-acceptance-recorded-response",
        "release-acceptance-withdrawal-request",
        "release-acceptance-withdrawal-response",
    )
    forbidden = {"acceptedByUserId", "accessToken", "reauthenticationProof", "notes"}
    for name in names:
        document = json.loads((ROOT / "contracts" / f"{name}.schema.json").read_text())
        assert document["additionalProperties"] is False
        assert forbidden.isdisjoint(document.get("properties", {}))
        for definition in document.get("$defs", {}).values():
            if definition.get("type") == "object":
                assert definition["additionalProperties"] is False


def test_exported_json_schema_enforces_decision_and_quorum_semantics():
    decision_schema = json.loads(
        (ROOT / "contracts/release-acceptance-decision-request.schema.json").read_text()
    )
    Draft202012Validator(decision_schema).validate(decision())
    with pytest.raises(JsonSchemaValidationError):
        Draft202012Validator(decision_schema).validate(
            decision(outcome="conditional", knownLimitations=[])
        )
    with pytest.raises(JsonSchemaValidationError):
        Draft202012Validator(decision_schema).validate(
            decision(outcome="accepted", knownLimitations=["must not be accepted"])
        )

    recorded_schema = json.loads(
        (ROOT / "contracts/release-acceptance-recorded-response.schema.json").read_text()
    )
    valid = {
        "acceptanceId": "acceptance_01",
        "releaseId": "release_01",
        "acceptanceIdRef": "AC-12",
        "outcome": "accepted",
        "state": "recorded",
        "acceptedManifestSha256": HASH,
        "manifestMatches": True,
        "decisionSignOff": True,
        "decisionConfirmationCount": 2,
        "decidedAt": NOW.isoformat(),
        "replayed": False,
    }
    Draft202012Validator(recorded_schema).validate(valid)
    with pytest.raises(JsonSchemaValidationError):
        Draft202012Validator(recorded_schema).validate(
            {
                **valid,
                "decisionConfirmationCount": 1,
                "decisionSignOff": False,
            }
        )
    page_schema = json.loads(
        (ROOT / "contracts/release-acceptance-proposal-review-page-response.schema.json").read_text()
    )
    assert page_schema["properties"]["items"]["maxItems"] == 100


EXPECTED_REQUIRED = {
    "release-acceptance-decision-request": {
        "acceptanceIdRef", "outcome", "targetManifestSha256", "reasonCode",
        "targetRefs", "measurementRefs", "knownLimitations",
    },
    "release-acceptance-confirmation-request": {
        "proposalDigest", "targetManifestSha256",
    },
    "release-acceptance-proposal-response": {
        "proposalId", "releaseId", "acceptanceIdRef", "outcome", "state",
        "targetManifestSha256", "proposalDigest", "requiredDistinctOperatorCount",
        "proposalConfirmationCount", "decisionSignOff", "expiresAt", "replayed",
    },
    "release-acceptance-proposal-review-response": {
        "proposalId", "releaseId", "acceptanceIdRef", "outcome", "state",
        "targetManifestSha256", "proposalDigest", "reasonCode", "targetRefs",
        "measurementRefs", "knownLimitations", "requiredDistinctOperatorCount",
        "proposalConfirmationCount", "decisionSignOff", "expiresAt",
    },
    "release-acceptance-proposal-review-page-response": {"items"},
    "release-acceptance-recorded-response": {
        "acceptanceId", "releaseId", "acceptanceIdRef", "outcome", "state",
        "acceptedManifestSha256", "manifestMatches", "decisionSignOff",
        "decisionConfirmationCount", "decidedAt", "replayed",
    },
    "release-acceptance-withdrawal-request": {
        "acceptedManifestSha256", "reasonCode",
    },
    "release-acceptance-withdrawal-response": {
        "withdrawalId", "acceptanceId", "releaseId", "state",
        "acceptedManifestSha256", "withdrawnAcceptanceCountsTowardSignOff",
        "operatorSignOff", "reasonCode", "withdrawnAt", "replayed",
    },
}


def test_exported_contract_required_sets_are_exact():
    for name, expected in EXPECTED_REQUIRED.items():
        document = json.loads((ROOT / "contracts" / f"{name}.schema.json").read_text())
        assert set(document["required"]) == expected, name
    decision_schema = json.loads(
        (ROOT / "contracts/release-acceptance-decision-request.schema.json").read_text()
    )
    assert set(decision_schema["$defs"]["ReleaseAcceptanceTargetRef"]["required"]) == {
        "targetId", "targetSha256",
    }
    assert set(decision_schema["$defs"]["ReleaseAcceptanceMeasurementRef"]["required"]) == {
        "evidenceId", "evidenceSha256", "observedAt",
    }


@pytest.mark.parametrize("bad", ["A" * 64, "a" * 63, "a" * 64 + "\n"])
def test_digests_are_exact_lowercase_hex_before_whitespace_normalisation(bad):
    review = {
        "proposalId": "proposal_01",
        "releaseId": "release_01",
        "acceptanceIdRef": "AC-12",
        "outcome": "accepted",
        "state": "pending_second_operator",
        "targetManifestSha256": HASH,
        "proposalDigest": "d" * 64,
        "reasonCode": "RELEASE_ACCEPTANCE",
        "targetRefs": decision()["targetRefs"],
        "measurementRefs": decision()["measurementRefs"],
        "knownLimitations": [],
        "requiredDistinctOperatorCount": 2,
        "proposalConfirmationCount": 1,
        "decisionSignOff": False,
        "expiresAt": (NOW + dt.timedelta(minutes=5)).isoformat(),
    }
    recorded = {
        "acceptanceId": "acceptance_01",
        "releaseId": "release_01",
        "acceptanceIdRef": "AC-12",
        "outcome": "accepted",
        "state": "recorded",
        "acceptedManifestSha256": bad,
        "manifestMatches": True,
        "decisionSignOff": True,
        "decisionConfirmationCount": 2,
        "decidedAt": NOW.isoformat(),
        "replayed": False,
    }
    withdrawal = {
        "acceptedManifestSha256": bad,
        "reasonCode": "security-concern",
    }
    cases = [
        (
            schemas.ReleaseAcceptanceDecisionRequest,
            "release-acceptance-decision-request",
            decision(targetManifestSha256=bad),
        ),
        (
            schemas.ReleaseAcceptanceDecisionRequest,
            "release-acceptance-decision-request",
            decision(targetRefs=[{"targetId": "AC-12", "targetSha256": bad}]),
        ),
        (
            schemas.ReleaseAcceptanceDecisionRequest,
            "release-acceptance-decision-request",
            decision(measurementRefs=[{
                "evidenceId": "evidence:ac12:physical-lane",
                "evidenceSha256": bad,
                "observedAt": NOW.isoformat(),
            }]),
        ),
        (
            schemas.ReleaseAcceptanceConfirmationRequest,
            "release-acceptance-confirmation-request",
            {"proposalDigest": bad, "targetManifestSha256": HASH},
        ),
        (
            schemas.ReleaseAcceptanceProposalReviewResponse,
            "release-acceptance-proposal-review-response",
            {**review, "proposalDigest": bad},
        ),
        (
            schemas.ReleaseAcceptanceRecordedResponse,
            "release-acceptance-recorded-response",
            recorded,
        ),
        (
            schemas.ReleaseAcceptanceWithdrawalRequest,
            "release-acceptance-withdrawal-request",
            withdrawal,
        ),
    ]
    for model, contract_name, payload in cases:
        with pytest.raises(ValidationError):
            model.model_validate(payload)
        document = json.loads((ROOT / "contracts" / f"{contract_name}.schema.json").read_text())
        with pytest.raises(JsonSchemaValidationError):
            Draft202012Validator(document).validate(payload)
