"""Decision 6a: the HTTP contract exposes model retry, never generic Run retry."""

import json
from pathlib import Path

import pytest
from inv.contracts import validate_contract
from inv.errors import DomainError


FIXTURE = Path(__file__).resolve().parents[2] / "contracts/fixtures/model-retry-prepare-result.json"


def test_model_retry_prepare_result_fixture_is_bound():
    validate_contract("ModelRetryPrepareResult", json.loads(FIXTURE.read_text("utf-8")))


def test_model_retry_never_claims_automatic_input_or_approval_reuse():
    value = json.loads(FIXTURE.read_text("utf-8"))
    value["requiresFrozenInputAndApproval"] = False
    with pytest.raises(DomainError, match="invalid contract"):
        validate_contract("ModelRetryPrepareResult", value)


def test_model_retry_input_allows_the_bounded_server_ttl_default():
    validate_contract(
        "ModelRetryPrepareInput",
        {
            "cpuMillis": 500,
            "memoryBytes": 1073741824,
            "gpuCount": 0,
            "minVramBytes": 0,
            "requiredBytes": 12,
            "maxHostLoad": 0.8,
            "runtime": "container",
            "policyVersion": "model-retry:1",
        },
    )
