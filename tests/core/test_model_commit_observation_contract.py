"""Bind the kernel ModelCommitObservation response to the shared fixture the frontend validates.

Why this matters: model_view returns the model-version commitment observation and validates its own
output with validate_contract("ModelCommitObservation", result) (services/control-plane/src/inv/
model_view.py) before serving /v1/projects/{p}/models/{m}/versions/{v}/commitment. The frontend fetches
it in apps/web/src/shared/api/fabricObservation.ts, typed by the GENERATED contracts-ts type (no
hand-type drift here -- the recommended pattern). Without a shared fixture, a backend shape change would
still slip: the backend's validate_contract and the frontend's compile-time type are checked against
different sources with no single shared example tying them. This fixture is that example -- the backend
validates its live response against core.schema.json and the frontend can validate this same fixture
against the mirrored contracts/v1alpha1/core.schema.json#/$defs/ModelCommitObservation.
"""
import json
from pathlib import Path

import pytest

from inv.contracts import validate_contract
from inv.errors import DomainError

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "contracts" / "fixtures" / "model-commit-observation-response.json"


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_shared_fixture_matches_kernel_contract():
    # The exact validator model_view runs on the live commitment response.
    validate_contract("ModelCommitObservation", _fixture())


def test_every_field_is_load_bearing():
    # All fifteen fields are required (additionalProperties:false); dropping any must be rejected --
    # otherwise the fixture could pass while the served commitment silently lost a field.
    value = _fixture()
    for field in list(value):
        broken = {k: v for k, v in value.items() if k != field}
        with pytest.raises(DomainError, match="VAL-0002"):
            validate_contract("ModelCommitObservation", broken)


def test_classification_enum_is_enforced():
    # classification is a closed enum (public|internal|restricted); an out-of-set value must be rejected.
    value = _fixture()
    value["classification"] = "top-secret"
    with pytest.raises(DomainError, match="VAL-0002"):
        validate_contract("ModelCommitObservation", value)
