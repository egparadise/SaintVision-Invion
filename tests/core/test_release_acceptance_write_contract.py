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


ROOT = Path(__file__).resolve().parents[2]
HASH = "a" * 64
NOW = dt.datetime(2026, 10, 1, 9, 48, tzinfo=dt.timezone.utc)


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


def test_pending_proposal_can_never_report_operator_sign_off():
    body = {
        "proposalId": "proposal_01",
        "releaseId": "release_01",
        "acceptanceIdRef": "AC-12",
        "outcome": "accepted",
        "state": "pending_second_operator",
        "targetManifestSha256": HASH,
        "proposalDigest": "d" * 64,
        "requiredDistinctOperatorCount": 2,
        "confirmedOperatorCount": 1,
        "operatorSignOff": False,
        "expiresAt": (NOW + dt.timedelta(minutes=15)).isoformat(),
        "replayed": False,
    }
    schemas.ReleaseAcceptanceProposalResponse.model_validate(body)
    with pytest.raises(ValidationError):
        schemas.ReleaseAcceptanceProposalResponse.model_validate({**body, "operatorSignOff": True})


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
def test_only_a_two_person_accepted_record_can_create_sign_off(outcome, count, sign_off, valid):
    body = {
        "acceptanceId": "acceptance_01",
        "releaseId": "release_01",
        "acceptanceIdRef": "AC-12",
        "outcome": outcome,
        "state": "recorded",
        "acceptedManifestSha256": HASH,
        "manifestMatches": True,
        "operatorSignOff": sign_off,
        "confirmedOperatorCount": count,
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
        "targetManifestSha256": HASH,
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
        "targetManifestSha256": HASH,
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
        "operatorSignOff": True,
        "confirmedOperatorCount": 2,
        "decidedAt": NOW.isoformat(),
        "replayed": False,
    }
    Draft202012Validator(recorded_schema).validate(valid)
    with pytest.raises(JsonSchemaValidationError):
        Draft202012Validator(recorded_schema).validate(
            {**valid, "confirmedOperatorCount": 1, "operatorSignOff": False}
        )
