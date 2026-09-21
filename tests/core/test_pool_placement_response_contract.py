"""Pool, placement and mutation responses use repository-owned wire fixtures."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from saintvision.api import schemas
from saintvision.api.v1 import pools
from saintvision.identity.principal import Principal


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "contracts" / "fixtures"
NOW = datetime(2026, 9, 21, 9, 0, tzinfo=timezone.utc)
PRINCIPAL = Principal(
    user_id="usr_contract_fixture",
    tenant_id=uuid.UUID("00000000-0000-4000-8000-000000000041"),
    external_subject="pool-contract-fixture",
)


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def client() -> TestClient:
    app = FastAPI()
    app.include_router(pools.router)
    app.dependency_overrides[pools.get_principal] = lambda: PRINCIPAL
    app.dependency_overrides[pools.get_session] = lambda: object()
    app.dependency_overrides[pools.get_now] = lambda: NOW
    return TestClient(app)


@pytest.mark.parametrize(
    ("filename", "model"),
    [
        ("pool-capacity-response.json", schemas.PoolCapacityResponse),
        ("placement-preview-response.json", schemas.PlacementPreviewResponse),
        ("pool-created-response.json", schemas.PoolCreatedResponse),
        ("pool-member-response.json", schemas.PoolMemberResponse),
        ("pool-member-removal-response.json", schemas.PoolMemberRemovalResponse),
        ("distributed-plan-response.json", schemas.DistributedPlanResponse),
    ],
)
def test_shared_fixture_roundtrips_through_strict_response_model(filename, model):
    payload = fixture(filename)
    parsed = model.model_validate(payload)
    assert parsed.model_dump(by_alias=True, mode="json") == payload


@pytest.mark.parametrize(
    ("filename", "model", "path", "value"),
    [
        ("pool-capacity-response.json", schemas.PoolCapacityResponse, ("units",), None),
        ("placement-preview-response.json", schemas.PlacementPreviewResponse, ("candidates", 0, "spare"), None),
        ("pool-created-response.json", schemas.PoolCreatedResponse, ("poolId",), None),
        ("pool-member-response.json", schemas.PoolMemberResponse, ("member",), False),
        ("pool-member-removal-response.json", schemas.PoolMemberRemovalResponse, ("removed",), "not-a-bool"),
        ("distributed-plan-response.json", schemas.DistributedPlanResponse, ("placements", 0, "shardIndex"), -1),
    ],
)
def test_contract_fixture_mutations_are_rejected(filename, model, path, value):
    payload = fixture(filename)
    target = payload
    for key in path[:-1]:
        target = target[key]
    if value is None:
        target.pop(path[-1])
    else:
        target[path[-1]] = value
    with pytest.raises(ValidationError):
        model.model_validate(payload)


def test_pool_capacity_route_serializes_the_shared_contract(monkeypatch):
    payload = fixture("pool-capacity-response.json")
    monkeypatch.setattr(pools.pool_service, "pool_capacity", lambda *_args, **_kwargs: payload)
    response = client().get("/v1/pools/pool_contract_training/capacity")
    assert response.status_code == 200
    assert response.json() == payload


def test_placement_preview_route_serializes_the_shared_contract(monkeypatch):
    payload = fixture("placement-preview-response.json")
    monkeypatch.setattr(
        pools.pool_service,
        "rank_idle_first",
        lambda *_args, **_kwargs: payload["candidates"],
    )
    response = client().get(
        "/v1/pools/pool_contract_training/placement-preview",
        params={"cpuMillicores": 1200, "ramBytes": 1024, "gpuDevices": 1},
    )
    assert response.status_code == 200
    assert response.json() == payload


def test_zero_requirement_preview_has_finite_stable_headroom(monkeypatch):
    node = pools.pool_service.NodeSpare(
        node_id="nod_contract_worker",
        hostname="worker-contract",
        offered={"cpu": 4000, "ram": 8589934592, "gpu": 1},
        used={"cpu": 1000, "ram": 0, "gpu": 0},
        spare={"cpu": 3000, "ram": 8589934592, "gpu": 1},
        measured=True,
    )

    class Rows:
        def all(self):
            return ["nod_contract_worker"]

    class Session:
        def scalars(self, _query):
            return Rows()

    monkeypatch.setattr(pools.pool_service, "pool_members", lambda *_args, **_kwargs: ["nod_contract_worker"])
    monkeypatch.setattr(pools.pool_service, "node_spare", lambda *_args, **_kwargs: [node])
    ranked = pools.pool_service.rank_idle_first(
        Session(),
        tenant_id=PRINCIPAL.tenant_id,
        pool_id="pool_contract_training",
        requirement=pools.pool_service.ShardRequirement(),
        now=NOW,
    )
    assert ranked[0]["headroom"] == 0.0


def test_pool_mutation_routes_serialize_the_shared_contracts(monkeypatch):
    created = fixture("pool-created-response.json")
    monkeypatch.setattr(pools.project_service, "require_project_access", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        pools.pool_service,
        "create_pool",
        lambda *_args, **_kwargs: SimpleNamespace(pool_id=created["poolId"], name=created["name"]),
    )
    response = client().post(
        "/v1/pools",
        json={"projectId": "prj_contract", "name": created["name"]},
    )
    assert response.status_code == 201
    assert response.json() == created

    added = fixture("pool-member-response.json")
    monkeypatch.setattr(pools.pool_service, "add_member", lambda *_args, **_kwargs: None)
    response = client().put(
        f"/v1/pools/{added['poolId']}/members/{added['nodeId']}"
    )
    assert response.status_code == 200
    assert response.json() == added

    removed = fixture("pool-member-removal-response.json")
    monkeypatch.setattr(pools.pool_service, "remove_member", lambda *_args, **_kwargs: True)
    response = client().delete(
        f"/v1/pools/{removed['poolId']}/members/{removed['nodeId']}"
    )
    assert response.status_code == 200
    assert response.json() == removed


def test_plan_route_serializes_all_shard_assignments(monkeypatch):
    payload = fixture("distributed-plan-response.json")
    plan = SimpleNamespace(
        plan_id=payload["planId"],
        run_id=payload["runId"],
        strategy=payload["strategy"],
        shard_count=payload["shardCount"],
    )
    placements = [
        SimpleNamespace(
            shard_index=row["shardIndex"],
            node_id=row["nodeId"],
            assigned_cpu_millicores=row["assignedCpuMillicores"],
            assigned_ram_bytes=row["assignedRamBytes"],
            assigned_gpu_devices=row["assignedGpuDevices"],
        )
        for row in payload["placements"]
    ]
    monkeypatch.setattr(pools.pool_service, "plan_distributed_run", lambda *_args, **_kwargs: (plan, placements))
    response = client().post(
        "/v1/pools/pool_contract_training/plans",
        json={
            "runId": payload["runId"],
            "strategy": payload["strategy"],
            "shardCount": payload["shardCount"],
            "splittableDeclared": True,
        },
    )
    assert response.status_code == 201
    assert response.json() == payload
