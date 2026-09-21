"""High-risk write responses are validated by FastAPI before being served."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from types import SimpleNamespace
import uuid
from contextlib import nullcontext

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from saintvision.api import schemas
from saintvision.api.deps import get_now, get_principal, get_session, get_settings
from saintvision.api.v1 import (
    nodes as node_routes,
    pools,
    projects,
    settings as settings_routes,
)
from saintvision.api.v1 import storage as storage_routes
from saintvision.identity.principal import Principal

FIXTURES = Path(__file__).resolve().parents[2] / "contracts" / "fixtures"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


CASES = [
    ("project", "project-create-response.json", schemas.ProjectCreateResponse),
    ("admission", "discovery-admission-response.json", schemas.DiscoveryAdmissionResponse),
    ("member", "member-role-result-response.json", schemas.MemberRoleResultResponse),
    ("offer", "resource-offer-result-response.json", schemas.ResourceOfferResultResponse),
    ("workspace-status", "workspace-status-response.json", schemas.WorkspaceStatusResponse),
    ("node-enroll", "node-enroll-response.json", schemas.NodeEnrollResponse),
    (
        "contribution-registration",
        "storage-contribution-registration-response.json",
        schemas.ContributionRegistrationResponse,
    ),
    (
        "contribution-activation",
        "storage-contribution-registration-response.json",
        schemas.ContributionRegistrationResponse,
    ),
    (
        "contribution-revoke",
        "storage-contribution-registration-response.json",
        schemas.ContributionRegistrationResponse,
    ),
]


def _client(monkeypatch, kind: str, service_result: dict) -> tuple[TestClient, str, str, dict]:
    principal = Principal(
        user_id="usr_contract_actor",
        tenant_id=uuid.UUID("00000000-0000-4000-8000-000000000041"),
        external_subject="write-response-contract",
    )
    app = FastAPI()
    app.dependency_overrides[get_principal] = lambda: principal
    app.dependency_overrides[get_session] = lambda: object()
    app.dependency_overrides[get_now] = lambda: dt.datetime(
        2026, 9, 22, 9, 0, tzinfo=dt.timezone.utc
    )
    app.dependency_overrides[get_settings] = lambda: SimpleNamespace(
        bootstrap_token_ttl_seconds=900,
        idempotency_ttl_seconds=600,
    )

    if kind == "project":
        monkeypatch.setattr(projects.project_service, "create_project", lambda *_a, **_k: service_result)
        monkeypatch.setattr(projects, "record_event", lambda *_a, **_k: None)
        app.include_router(projects.router)
        return TestClient(app, raise_server_exceptions=False), "POST", "/v1/projects", {"code": "contract-create", "displayName": "Contract Create"}
    if kind == "admission":
        monkeypatch.setattr(
            pools.discovery_service,
            "admit_candidate",
            lambda *_a, **_k: SimpleNamespace(
                secret=service_result["bootstrapToken"],
                expires_at=dt.datetime.fromisoformat(service_result["expiresAt"]),
            ),
        )
        monkeypatch.setattr(pools, "record_event", lambda *_a, **_k: None)
        app.include_router(pools.router)
        return TestClient(app, raise_server_exceptions=False), "POST", "/v1/discovery/candidates/ann_contract_candidate/admission", {}

    monkeypatch.setattr(settings_routes.settings_service, "require_global_administrator", lambda *_a, **_k: None)
    monkeypatch.setattr(settings_routes, "_audit", lambda *_a, **_k: None)
    if kind == "member":
        monkeypatch.setattr(settings_routes.settings_service, "set_member_role", lambda *_a, **_k: service_result)
        app.include_router(settings_routes.router)
        return TestClient(app, raise_server_exceptions=False), "PUT", "/v1/projects/prj_contract_create/members/usr_contract_member", {"roleCode": "operator"}
    if kind == "workspace-status":
        monkeypatch.setattr(
            settings_routes.settings_service,
            "set_workspace_status",
            lambda *_a, **_k: SimpleNamespace(
                workspace_id="wsp_contract_status", status=service_result["status"]
            ),
        )
        app.include_router(settings_routes.router)
        request_status = service_result.get("_request_status", "ready")
        return TestClient(app, raise_server_exceptions=False), "PUT", "/v1/workspaces/wsp_contract_status/status", {"status": request_status}

    if kind == "node-enroll":
        node_data = service_result["node"]
        node = SimpleNamespace(
            node_id=node_data["nodeId"],
            hostname=node_data["hostname"],
            os_type=node_data["osType"],
            os_version=node_data["osVersion"],
            agent_version=node_data["agentVersion"],
            status=node_data["status"],
            enrolled_at=dt.datetime.fromisoformat(
                node_data["enrolledAt"].replace("Z", "+00:00")
            ),
            last_heartbeat_at=(
                dt.datetime.fromisoformat(
                    node_data["lastHeartbeatAt"].replace("Z", "+00:00")
                )
                if node_data["lastHeartbeatAt"] is not None
                else None
            ),
            heartbeat_sequence=node_data["heartbeatSequence"],
            labels=node_data["labels"],
        )

        class FakeSession:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def begin(self):
                return nullcontext()

        monkeypatch.setattr(
            node_routes, "make_session_factory", lambda _engine: FakeSession
        )
        monkeypatch.setattr(node_routes, "tenant_scope", lambda *_args: nullcontext())
        monkeypatch.setattr(
            node_routes.node_service, "enroll_node", lambda *_a, **_k: node
        )
        monkeypatch.setattr(node_routes, "record_event", lambda *_a, **_k: None)
        if service_result.get("_invalid_nested_node") or "unexpected" in service_result:
            valid_node = dict(node_data)
            valid_node["unexpected"] = "must be rejected"
            monkeypatch.setattr(node_routes, "_node_body", lambda _node: valid_node)
        app.state.engine = object()
        app.include_router(node_routes.router)
        request_body = {
            "bootstrapToken": "synthetic-bootstrap-token",
            "hostname": "worker-contract",
            "osType": "linux",
            "osVersion": "test-os",
            "agentVersion": "test-agent",
            "capabilities": [],
            "labels": {},
        }
        return (
            TestClient(app, raise_server_exceptions=False),
            "POST",
            "/v1/nodes",
            request_body,
        )

    if kind in {"contribution-registration", "contribution-activation", "contribution-revoke"}:
        contribution_data = service_result["contribution"]
        if service_result.get("_invalid_nested_contribution"):
            contribution_data = {**contribution_data, "unexpected": "must be rejected"}
        contribution = SimpleNamespace(
            contribution_id=contribution_data["contributionId"],
            node_id=contribution_data["nodeId"],
            declared_path=contribution_data["declaredPath"],
            normalized_path=contribution_data["normalizedPath"],
            mode=contribution_data["mode"],
            status=contribution_data["status"],
            capacity_bytes=contribution_data["capacityBytes"],
            available_bytes=contribution_data["availableBytes"],
            registered_at=dt.datetime.fromisoformat(
                contribution_data["registeredAt"].replace("Z", "+00:00")
            ),
        )
        monkeypatch.setattr(
            storage_routes, "_contribution_body", lambda _value: contribution_data
        )
        app.include_router(storage_routes.router)
        if kind == "contribution-registration":
            replay = service_result.get("_replay")
            if replay is None and "unexpected" in service_result:
                replay = {
                    "contribution": contribution_data,
                    "unexpected": service_result["unexpected"],
                }
            monkeypatch.setattr(
                storage_routes, "replay_or_reserve", lambda *_a, **_k: replay
            )
            monkeypatch.setattr(
                storage_routes.storage_service,
                "register_contribution",
                lambda *_a, **_k: contribution,
            )
            monkeypatch.setattr(storage_routes, "record_event", lambda *_a, **_k: None)
            monkeypatch.setattr(storage_routes, "store_idempotent_response", lambda *_a, **_k: None)
            method, path = "POST", "/v1/storage/contributions"
        elif kind == "contribution-activation":
            monkeypatch.setattr(
                storage_routes.storage_service,
                "activate_contribution",
                lambda *_a, **_k: contribution,
            )
            method, path = "POST", "/v1/storage/contributions/stc_contract/activation"
        else:
            monkeypatch.setattr(
                storage_routes.storage_service,
                "revoke_contribution",
                lambda *_a, **_k: contribution,
            )
            method, path = "DELETE", "/v1/storage/contributions/stc_contract"
        request_body = (
            {
                "nodeId": contribution_data["nodeId"],
                "declaredPath": contribution_data["declaredPath"],
                "mode": contribution_data["mode"],
                "capacityBytes": contribution_data["capacityBytes"],
                "availableBytes": contribution_data["availableBytes"],
            }
            if kind == "contribution-registration"
            else {}
        )
        return (
            TestClient(app, raise_server_exceptions=False),
            method,
            path,
            request_body,
        )

    monkeypatch.setattr(settings_routes.settings_service, "set_resource_offer", lambda *_a, **_k: service_result)
    app.include_router(settings_routes.router)
    return (
        TestClient(app, raise_server_exceptions=False),
        "PUT",
        "/v1/capabilities/cap_contract_cpu/offer",
        {"offeredQuantity": 4000, "unit": "millicores"},
    )


def _request(client: TestClient, method: str, path: str, body: dict):
    headers = (
        {"X-Inv-Tenant": "00000000-0000-4000-8000-000000000041"}
        if path == "/v1/nodes"
        else None
    )
    return client.request(method, path, json=body, headers=headers)


@pytest.mark.parametrize("kind,filename,model", CASES)
def test_high_risk_write_response_fixtures_match_strict_models(kind, filename, model):
    payload = _fixture(filename)
    parsed = model.model_validate(payload)
    assert parsed.model_dump(by_alias=True, mode="json", exclude_unset=True) == payload


def test_nullable_write_response_fields_match_observed_service_states():
    project = _fixture("project-create-response.json")
    project["kernelNote"] = None
    schemas.ProjectCreateResponse.model_validate(project)

    member = _fixture("member-role-result-response.json")
    member["roleCode"] = None
    with pytest.raises(ValidationError):
        schemas.MemberRoleResultResponse.model_validate(member)
    member = _fixture("member-role-result-response.json")
    member["userStatus"] = None
    with pytest.raises(ValidationError):
        schemas.MemberRoleResultResponse.model_validate(member)

    offer = _fixture("resource-offer-result-response.json")
    offer.update(
        previousOfferedQuantity=None,
        kernelResourceId=None,
        kernelCapacity=None,
        kernelReasonCode=None,
    )
    schemas.ResourceOfferResultResponse.model_validate(offer)


@pytest.mark.parametrize("kind,filename,model", CASES)
def test_high_risk_write_route_serves_the_measured_fixture(monkeypatch, kind, filename, model):
    payload = _fixture(filename)
    client, method, path, request_body = _client(monkeypatch, kind, payload)
    response = _request(client, method, path, request_body)
    expected_status = (
        201
        if kind in {"project", "admission", "node-enroll", "contribution-registration"}
        else 200
    )
    assert response.status_code == expected_status
    assert response.json() == payload
    model.model_validate(response.json())


@pytest.mark.parametrize("kind,filename,model", CASES)
def test_high_risk_write_route_refuses_invalid_service_response(monkeypatch, kind, filename, model):
    broken = _fixture(filename)
    invalid_field = {
        "project": ("memberCount", "one"),
        "admission": ("bootstrapToken", 9),
        "member": ("canApprove", "yes"),
        "offer": ("previousOfferedQuantity", "unknown"),
        "workspace-status": ("status", "made-up"),
        "node-enroll": ("unexpected", "must be rejected"),
        "contribution-registration": ("unexpected", "must be rejected"),
        "contribution-activation": ("_invalid_nested_contribution", True),
        "contribution-revoke": ("_invalid_nested_contribution", True),
    }[kind]
    broken[invalid_field[0]] = invalid_field[1]
    client, method, path, request_body = _client(monkeypatch, kind, broken)
    response = _request(client, method, path, request_body)
    assert response.status_code == 500


def test_project_create_preserves_conditional_absence_of_kernel_note(monkeypatch):
    payload = _fixture("project-create-response.json")
    payload.pop("kernelNote")
    client, method, path, request_body = _client(monkeypatch, "project", payload)
    response = _request(client, method, path, request_body)
    assert response.status_code == 201
    assert response.json() == payload
    assert "kernelNote" not in response.json()


@pytest.mark.parametrize(
    ("linked", "enabled", "note_expected"),
    [(False, False, True), (True, False, True), (True, True, False)],
)
def test_project_create_model_accepts_each_kernel_link_producer_branch(
    monkeypatch, linked, enabled, note_expected
):
    """The note is emitted for both blocked states and omitted when executable."""
    project = SimpleNamespace(
        project_id="prj_branch_contract",
        code="branch-contract",
        display_name="Branch contract",
        status="active",
        created_at=dt.datetime(2026, 9, 22, 9, 0, tzinfo=dt.timezone.utc),
    )
    session = SimpleNamespace(
        execute=lambda *_args, **_kwargs: SimpleNamespace(scalar_one=lambda: 1)
    )
    monkeypatch.setattr(
        projects.project_service,
        "kernel_link",
        lambda *_args, **_kwargs: {
            "kernelLinked": linked,
            "kernelEnabled": enabled,
        },
    )

    body = projects.project_service.project_body(
        session, project, tenant_id=uuid.UUID("00000000-0000-4000-8000-000000000041")
    )
    schemas.ProjectCreateResponse.model_validate(body)
    assert ("kernelNote" in body) is note_expected


@pytest.mark.parametrize("status", ["pending", "active", "revoked"])
@pytest.mark.parametrize(
    ("capacity_bytes", "available_bytes"),
    [(None, None), (1024, None), (None, 512), (1024, 512)],
)
def test_contribution_body_serializes_every_nullable_status_shape(
    status, capacity_bytes, available_bytes
):
    contribution = SimpleNamespace(
        contribution_id="stc_shape_contract",
        node_id="node_shape_contract",
        declared_path="C:\\data",
        normalized_path="C:/data",
        mode="read_only",
        status=status,
        capacity_bytes=capacity_bytes,
        available_bytes=available_bytes,
        registered_at=dt.datetime(2026, 9, 22, 9, 0, tzinfo=dt.timezone.utc),
    )

    body = storage_routes._contribution_body(contribution)
    parsed = schemas.ContributionRegistrationResponse.model_validate(
        {"contribution": body}
    )
    assert parsed.contribution.status == status
    assert parsed.contribution.capacity_bytes == capacity_bytes
    assert parsed.contribution.available_bytes == available_bytes
    assert "capacityBytes" in body and "availableBytes" in body


@pytest.mark.parametrize(
    "filename,model,field,value",
    [
        ("project-create-response.json", schemas.ProjectCreateResponse, "memberCount", "one"),
        ("discovery-admission-response.json", schemas.DiscoveryAdmissionResponse, "bootstrapToken", 9),
        ("member-role-result-response.json", schemas.MemberRoleResultResponse, "canApprove", "yes"),
        ("resource-offer-result-response.json", schemas.ResourceOfferResultResponse, "previousOfferedQuantity", "unknown"),
    ],
)
def test_high_risk_write_contract_rejects_wrong_field_types(filename, model, field, value):
    payload = _fixture(filename)
    payload[field] = value
    with pytest.raises(ValidationError):
        model.model_validate(payload)


def test_workspace_status_allowed_next_matches_the_lifecycle_graph():
    from saintvision.services.settings import WORKSPACE_TRANSITIONS

    expected = {
        "provisioning": {"ready", "deleting"},
        "ready": {"suspended", "deleting"},
        "suspended": {"ready", "deleting"},
        "deleting": {"deleted"},
        "deleted": set(),
    }
    observed = {state: set(next_states) for state, next_states in WORKSPACE_TRANSITIONS.items()}
    assert observed == expected
    assert set(observed) == {"provisioning", "ready", "suspended", "deleting", "deleted"}
    assert all(target in observed for targets in observed.values() for target in targets)


@pytest.mark.parametrize(
    "status,expected_allowed_next",
    [
        ("provisioning", ["deleting", "ready"]),
        ("ready", ["deleting", "suspended"]),
        ("suspended", ["deleting", "ready"]),
        ("deleting", ["deleted"]),
        ("deleted", []),
    ],
)
def test_workspace_status_route_reports_exact_allowed_next_for_each_state(
    monkeypatch, status, expected_allowed_next
):
    payload = _fixture("workspace-status-response.json")
    payload["status"] = status
    payload["_request_status"] = status
    client, method, path, request_body = _client(monkeypatch, "workspace-status", payload)

    response = _request(client, method, path, request_body)

    assert response.status_code == 200
    assert response.json() == {
        "workspaceId": "wsp_contract_status",
        "status": status,
        "allowedNext": expected_allowed_next,
    }
