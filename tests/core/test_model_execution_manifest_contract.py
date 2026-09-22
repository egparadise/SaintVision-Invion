"""Strict wire contract and serving anchor for the project-scoped manifest projection."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from inv.contracts import validate_contract
from inv.errors import DomainError
from inv.generated.models import ModelExecutionManifestObservation as GeneratedObservation
from inv.model_view import ModelExecutionManifestObservation
from inv.model_uri_resolver import ModelUriResolver


FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "contracts/fixtures/model-execution-manifest-observation.json"
)


def payload():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_model_execution_manifest_fixture_roundtrips_generated_contract():
    body = payload()
    validate_contract("ModelExecutionManifestObservation", body)
    assert GeneratedObservation.model_validate(body).model_dump(mode="json") == body
    assert body["executionAuthorized"] is False
    assert body["requiresExecutionRevalidation"] is True


@pytest.mark.parametrize(
    "change",
    [
        lambda body: body["shardLocations"][0].update(readyNodes=[]),
        lambda body: body["shardLocations"][0].update(materialisable=False),
        lambda body: body.update(executionAuthorized=True),
        lambda body: body.pop("observedAt"),
    ],
)
def test_contract_rejects_empty_success_authority_or_missing_freshness(change):
    body = deepcopy(payload())
    change(body)
    with pytest.raises(DomainError, match="ModelExecutionManifestObservation: invalid contract"):
        validate_contract("ModelExecutionManifestObservation", body)


def test_serving_class_is_bound_to_the_strict_response_contract():
    # Structural anchor: check_contract_bindings also requires this test to name
    # the response and import the module that validates it on the serving path.
    assert ModelExecutionManifestObservation.__module__ == "inv.model_view"
    assert ModelUriResolver.__module__ == "inv.model_uri_resolver"


def test_uri_resolver_serving_anchor_rejects_a_corrupt_projection():
    body = payload()
    body["executionAuthorized"] = True
    with pytest.raises(DomainError, match="ModelExecutionManifestObservation: invalid contract"):
        ModelUriResolver._checked(body)
