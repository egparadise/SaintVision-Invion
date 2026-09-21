"""Small receipt/status writes remain anchored to strict API response models."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.routing import APIRoute
from pydantic import ValidationError

from saintvision.api import schemas
from saintvision.api.v1 import nodes, pools, settings


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "contracts" / "fixtures"


CASES = [
    (nodes.router, "POST", "/v1/nodes/{node_id}/heartbeats", "heartbeat-accepted-response.json", schemas.HeartbeatAcceptedResponse),
    (nodes.router, "POST", "/v1/nodes/liveness-sweeps", "node-liveness-sweep-response.json", schemas.NodeLivenessSweepResponse),
    (pools.router, "POST", "/v1/discovery/announcements", "discovery-announcement-response.json", schemas.DiscoveryAnnouncementResponse),
    (pools.router, "DELETE", "/v1/discovery/candidates/{announcement_id}", "discovery-decline-response.json", schemas.DiscoveryDeclineResponse),
    (settings.router, "DELETE", "/v1/projects/{project_id}/members/{user_id}", "project-member-removal-response.json", schemas.ProjectMemberRemovalResponse),
    (settings.router, "PUT", "/v1/users/{user_id}/status", "user-status-response.json", schemas.UserStatusResponse),
    (settings.router, "PUT", "/v1/projects/{project_id}/status", "project-status-response.json", schemas.ProjectStatusResponse),
]


def test_all_low_risk_write_routes_keep_their_response_model_anchor():
    for router, method, path, _fixture, model in CASES:
        actual = {
            verb: route.response_model
            for route in router.routes
            if isinstance(route, APIRoute) and route.path == path
            for verb in route.methods or ()
        }
        assert actual.get(method) is model, f"missing response_model anchor: {method} {path}"


@pytest.mark.parametrize("_router,_method,_path,filename,model", CASES)
def test_low_risk_write_fixtures_roundtrip_strict_contracts(_router, _method, _path, filename, model):
    payload = json.loads((FIXTURES / filename).read_text(encoding="utf-8"))
    parsed = model.model_validate(payload)
    assert parsed.model_dump(by_alias=True, mode="json") == payload


@pytest.mark.parametrize("_router,_method,_path,filename,model", CASES)
def test_low_risk_write_fixtures_reject_unknown_response_fields(_router, _method, _path, filename, model):
    payload = json.loads((FIXTURES / filename).read_text(encoding="utf-8"))
    payload["inventedReceipt"] = True
    with pytest.raises(ValidationError):
        model.model_validate(payload)
