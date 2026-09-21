"""Unknown external values stay rejected until their semantics are implemented.

These are intentional change sentinels. Supporting a new capability kind, node
OS, or placement strategy must update the contract, DB/unit/path behavior, and
these assertions together. Silently accepting an unknown control value is not
forward compatibility.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from saintvision.api.schemas import (
    CapabilityPayload,
    DistributedPlanRequest,
    DistributedPlanResponse,
    NodeEnrollRequest,
    ResourceOfferResultResponse,
)

ROOT = Path(__file__).resolve().parents[2]


def fixture(name: str) -> dict:
    return json.loads((ROOT / "contracts" / "fixtures" / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("kind", ["cpu", "gpu", "ram", "disk"])
def test_current_node_capability_kinds_remain_accepted(kind):
    CapabilityPayload.model_validate({"kind": kind, "totalQuantity": 1, "unit": "fixture"})


@pytest.mark.parametrize("kind", ["npu", "tpu", "future-accelerator"])
def test_unknown_node_capability_kind_is_rejected(kind):
    with pytest.raises(ValidationError):
        CapabilityPayload.model_validate(
            {"kind": kind, "totalQuantity": 1, "unit": "devices"}
        )


@pytest.mark.parametrize("kind", ["cpu", "gpu", "ram", "disk"])
def test_resource_offer_response_keeps_the_supported_capability_kind_domain(kind):
    payload = fixture("resource-offer-result-response.json")
    payload["kind"] = kind
    ResourceOfferResultResponse.model_validate(payload)


@pytest.mark.parametrize("kind", ["npu", "future-accelerator"])
def test_resource_offer_response_rejects_unknown_capability_kind(kind):
    payload = fixture("resource-offer-result-response.json")
    payload["kind"] = kind
    with pytest.raises(ValidationError):
        ResourceOfferResultResponse.model_validate(payload)


@pytest.mark.parametrize("os_type", ["windows", "linux"])
def test_current_node_operating_systems_remain_accepted(os_type):
    NodeEnrollRequest.model_validate(
        {
            "bootstrapToken": "synthetic-bootstrap-token-long-enough",
            "hostname": "node-contract-fixture",
            "osType": os_type,
            "osVersion": "fixture",
            "agentVersion": "fixture",
            "capabilities": [],
        }
    )


@pytest.mark.parametrize("os_type", ["freebsd", "macos", "future-os"])
def test_unknown_node_os_is_rejected_before_path_semantics_are_assumed(os_type):
    with pytest.raises(ValidationError):
        NodeEnrollRequest.model_validate(
            {
                "bootstrapToken": "synthetic-bootstrap-token-long-enough",
                "hostname": "node-contract-fixture",
                "osType": os_type,
                "osVersion": "fixture",
                "agentVersion": "fixture",
                "capabilities": [],
            }
        )


@pytest.mark.parametrize("strategy", ["single_node", "data_parallel", "sharded"])
def test_current_placement_strategies_remain_accepted(strategy):
    DistributedPlanRequest.model_validate(
        {"runId": "run_contract_fixture", "strategy": strategy}
    )


@pytest.mark.parametrize("strategy", ["automatic", "pipeline", "future-strategy"])
def test_unknown_placement_strategy_is_rejected_before_execution_plan_creation(strategy):
    with pytest.raises(ValidationError):
        DistributedPlanRequest.model_validate(
            {"runId": "run_contract_fixture", "strategy": strategy}
        )


@pytest.mark.parametrize("strategy", ["single_node", "data_parallel", "sharded"])
def test_distributed_plan_response_keeps_the_supported_strategy_domain(strategy):
    payload = fixture("distributed-plan-response.json")
    payload["strategy"] = strategy
    DistributedPlanResponse.model_validate(payload)


@pytest.mark.parametrize("strategy", ["automatic", "future-strategy"])
def test_distributed_plan_response_rejects_unknown_strategy(strategy):
    payload = fixture("distributed-plan-response.json")
    payload["strategy"] = strategy
    with pytest.raises(ValidationError):
        DistributedPlanResponse.model_validate(payload)
