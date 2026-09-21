"""Node inventory/detail responses are anchored to shared wire contracts."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
import uuid

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from pydantic import ValidationError

from saintvision.api import schemas
from saintvision.api.v1 import nodes
from saintvision.config import Settings
from saintvision.identity.principal import Principal
from saintvision.services.pagination import Page


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "contracts" / "fixtures"
PRINCIPAL = Principal(
    user_id="usr_node_contract",
    tenant_id=uuid.UUID("00000000-0000-4000-8000-000000000041"),
    external_subject="node-contract",
)


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def client(*, raise_server_exceptions: bool = True) -> TestClient:
    app = FastAPI()
    app.include_router(nodes.router)
    app.dependency_overrides[nodes.get_principal] = lambda: PRINCIPAL
    app.dependency_overrides[nodes.get_session] = lambda: object()
    app.dependency_overrides[nodes.get_settings] = lambda: Settings(database_url="test-only")
    return TestClient(app, raise_server_exceptions=raise_server_exceptions)


def node_from(payload: dict) -> SimpleNamespace:
    return SimpleNamespace(
        node_id=payload["nodeId"], hostname=payload["hostname"],
        os_type=payload["osType"], os_version=payload["osVersion"],
        agent_version=payload["agentVersion"], status=payload["status"],
        enrolled_at=datetime.fromisoformat(payload["enrolledAt"].replace("Z", "+00:00")),
        last_heartbeat_at=datetime.fromisoformat(payload["lastHeartbeatAt"].replace("Z", "+00:00")),
        heartbeat_sequence=payload["heartbeatSequence"], labels=payload["labels"],
    )


def test_node_serving_routes_declare_response_contracts():
    actual = {
        (method, route.path): route.response_model
        for route in nodes.router.routes if isinstance(route, APIRoute)
        for method in route.methods or ()
    }
    assert actual[("GET", "/v1/nodes")] is schemas.NodePageResponse
    assert actual[("GET", "/v1/nodes/{node_id}")] is schemas.NodeDetailResponse


@pytest.mark.parametrize(
    ("filename", "model"),
    [
        ("node-page-response.json", schemas.NodePageResponse),
        ("node-detail-response.json", schemas.NodeDetailResponse),
    ],
)
def test_shared_node_fixtures_roundtrip_strict_contracts(filename, model):
    payload = fixture(filename)
    assert model.model_validate(payload).model_dump(by_alias=True, mode="json") == payload


@pytest.mark.parametrize("filename,model", [
    ("node-page-response.json", schemas.NodePageResponse),
    ("node-detail-response.json", schemas.NodeDetailResponse),
])
@pytest.mark.parametrize("mutation", ["missing", "extra"])
def test_node_fixture_shape_drift_is_rejected(filename, model, mutation):
    payload = fixture(filename)
    node = payload["items"][0] if "items" in payload else payload["node"]
    if mutation == "missing":
        node.pop("heartbeatSequence")
    else:
        node["fabricatedTelemetry"] = {"cpu": 0}
    with pytest.raises(ValidationError):
        model.model_validate(payload)


def test_node_routes_serialize_shared_fixtures(monkeypatch):
    page = fixture("node-page-response.json")
    detail = fixture("node-detail-response.json")
    monkeypatch.setattr(
        nodes.node_service, "list_nodes",
        lambda *_args, **_kwargs: Page(
            items=[node_from(page["items"][0])], next_cursor=page["nextCursor"]
        ),
    )
    monkeypatch.setattr(nodes.node_service, "get_node", lambda *_args, **_kwargs: node_from(detail["node"]))
    monkeypatch.setattr(
        nodes.node_service, "list_capabilities",
        lambda *_args, **_kwargs: [SimpleNamespace(
            capability_id=detail["capabilities"][0]["capabilityId"], kind="cpu",
            device_index=None, vendor=None, model=None, total_quantity=8,
            unit="cores", divisible=True,
        )],
    )

    app = client()
    assert app.get("/v1/nodes").json() == page
    assert app.get("/v1/nodes/nod_contract_worker").json() == detail


def test_node_route_response_model_rejects_invalid_capability(monkeypatch):
    detail = fixture("node-detail-response.json")
    monkeypatch.setattr(nodes.node_service, "get_node", lambda *_args, **_kwargs: node_from(detail["node"]))
    bad = SimpleNamespace(
        capability_id="cap_contract_cpu", kind="cpu", device_index=None,
        vendor=None, model=None, total_quantity=-1, unit="cores", divisible=True,
    )
    monkeypatch.setattr(nodes.node_service, "list_capabilities", lambda *_args, **_kwargs: [bad])
    response = client(raise_server_exceptions=False).get("/v1/nodes/nod_contract_worker")
    assert response.status_code == 500
