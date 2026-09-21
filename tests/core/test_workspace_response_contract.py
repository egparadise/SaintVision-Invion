"""Workspace picker/readiness responses serialize the fixtures shared with the web UI."""

from __future__ import annotations

import json
import datetime as dt
from pathlib import Path
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from saintvision.api import schemas
from saintvision.api.deps import get_now, get_principal, get_session
from saintvision.api.v1 import projects, readiness
from saintvision.identity.principal import Principal

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "contracts/fixtures"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("filename", "model"),
    [
        ("project-list-response.json", schemas.ProjectListResponse),
        ("project-workspaces-response.json", schemas.ProjectWorkspacesResponse),
        ("workspace-execution-readiness-response.json", schemas.WorkspaceExecutionReadinessResponse),
    ],
)
def test_shared_workspace_fixture_matches_strict_response_model(filename, model):
    payload = _fixture(filename)
    parsed = model.model_validate(payload)
    assert parsed.model_dump(by_alias=True, mode="json", exclude_unset=True) == payload


@pytest.mark.parametrize(
    ("filename", "model", "mutate"),
    [
        ("project-list-response.json", schemas.ProjectListResponse, "missing-project-name"),
        ("project-list-response.json", schemas.ProjectListResponse, "extra-project-field"),
        ("project-workspaces-response.json", schemas.ProjectWorkspacesResponse, "missing-page-count"),
        ("project-workspaces-response.json", schemas.ProjectWorkspacesResponse, "extra-page-field"),
        ("project-workspaces-response.json", schemas.ProjectWorkspacesResponse, "missing-workspace-field"),
        ("project-workspaces-response.json", schemas.ProjectWorkspacesResponse, "extra-workspace-field"),
        ("workspace-execution-readiness-response.json", schemas.WorkspaceExecutionReadinessResponse, "missing-workspace-id"),
        ("workspace-execution-readiness-response.json", schemas.WorkspaceExecutionReadinessResponse, "extra-response-field"),
        ("workspace-execution-readiness-response.json", schemas.WorkspaceExecutionReadinessResponse, "missing-check-field"),
        ("workspace-execution-readiness-response.json", schemas.WorkspaceExecutionReadinessResponse, "extra-check-field"),
    ],
)
def test_workspace_contract_rejects_shared_fixture_shape_drift(filename, model, mutate):
    payload = _fixture(filename)
    if mutate == "missing-project-name":
        payload["projects"][0].pop("displayName")
    elif mutate == "extra-project-field":
        payload["projects"][0]["inventedStatus"] = "ready"
    elif mutate == "missing-page-count":
        payload.pop("count")
    elif mutate == "extra-page-field":
        payload["fakeCount"] = 2
    elif mutate == "missing-workspace-field":
        payload["workspaces"][0].pop("allowedNext")
    elif mutate == "extra-workspace-field":
        payload["workspaces"][0]["inventedReady"] = True
    elif mutate == "missing-workspace-id":
        payload.pop("workspaceId")
    elif mutate == "extra-response-field":
        payload["inventedAdmission"] = True
    elif mutate == "missing-check-field":
        payload["checks"][0].pop("satisfied")
    else:
        payload["checks"][0]["inventedPass"] = True

    with pytest.raises(ValidationError):
        model.model_validate(payload)


@pytest.mark.parametrize(
    ("path", "filename", "service"),
    [
        ("/v1/projects", "project-list-response.json", "project-list"),
        ("/v1/projects/prj_contract/workspaces", "project-workspaces-response.json", "workspaces"),
        ("/v1/workspaces/wsp_contract/execution-readiness", "workspace-execution-readiness-response.json", "readiness"),
    ],
)
def test_fastapi_workspace_routes_serialize_the_shared_fixture(monkeypatch, path, filename, service):
    payload = _fixture(filename)
    if service == "project-list":
        monkeypatch.setattr(projects.project_service, "list_projects", lambda *_args, **_kwargs: payload["projects"])
    elif service == "workspaces":
        monkeypatch.setattr(projects.project_service, "list_workspaces", lambda *_args, **_kwargs: payload["workspaces"])
    else:
        monkeypatch.setattr(readiness.readiness_service, "workspace_readiness", lambda *_args, **_kwargs: payload)

    principal = Principal(
        user_id="usr_workspace_contract",
        tenant_id=uuid.UUID("00000000-0000-4000-8000-000000000041"),
        external_subject="workspace-contract",
    )
    app = FastAPI()
    app.include_router(projects.router)
    app.include_router(readiness.router)
    app.dependency_overrides[get_principal] = lambda: principal
    app.dependency_overrides[get_session] = lambda: object()

    response = TestClient(app).get(path)

    assert response.status_code == 200
    assert response.json() == payload
    model = {
        "project-list": schemas.ProjectListResponse,
        "workspaces": schemas.ProjectWorkspacesResponse,
        "readiness": schemas.WorkspaceExecutionReadinessResponse,
    }[service]
    model.model_validate(response.json())


# --- Workspace CREATE response: bound to WorkspaceSummaryResponse (added 2026-09-21) ---
def test_create_response_fixture_matches_strict_summary_model():
    payload = _fixture("workspace-create-response.json")
    parsed = schemas.WorkspaceSummaryResponse.model_validate(payload)
    assert parsed.model_dump(by_alias=True, mode="json", exclude_unset=True) == payload


@pytest.mark.parametrize(
    "mutate",
    ["missing-workspace-id", "extra-field", "wrong-type-nodeId", "allowedNext-not-strings"],
)
def test_create_response_rejects_shape_drift(mutate):
    payload = _fixture("workspace-create-response.json")
    if mutate == "missing-workspace-id":
        payload.pop("workspaceId")
    elif mutate == "extra-field":
        payload["inventedReady"] = True
    elif mutate == "wrong-type-nodeId":
        payload["nodeId"] = 123
    else:
        payload["allowedNext"] = [1, 2]
    with pytest.raises(ValidationError):
        schemas.WorkspaceSummaryResponse.model_validate(payload)


def _create_app(monkeypatch, service_return):
    monkeypatch.setattr(
        projects.project_service, "create_workspace", lambda *_a, **_k: service_return
    )
    monkeypatch.setattr(projects, "record_event", lambda *_a, **_k: None)
    principal = Principal(
        user_id="usr_workspace_contract",
        tenant_id=uuid.UUID("00000000-0000-4000-8000-000000000041"),
        external_subject="workspace-contract",
    )
    app = FastAPI()
    app.include_router(projects.router)
    app.dependency_overrides[get_principal] = lambda: principal
    app.dependency_overrides[get_session] = lambda: object()
    app.dependency_overrides[get_now] = lambda: dt.datetime(2026, 9, 21, 12, 0, 0, tzinfo=dt.timezone.utc)
    return app


def test_create_workspace_route_serializes_the_shared_fixture(monkeypatch):
    """Valid side: a real provisioning body serializes exactly the shared fixture."""
    payload = _fixture("workspace-create-response.json")
    app = _create_app(monkeypatch, payload)
    response = TestClient(app).post(
        "/v1/projects/prj_contract/workspaces", json={"name": "Contract Create Workspace"}
    )
    assert response.status_code == 201
    assert response.json() == payload
    assert response.headers["Location"] == "/v1/workspaces/wsp_contract_create"


def test_create_workspace_response_model_rejects_contract_violation(monkeypatch):
    """Weight side: a service dict that violates the contract is refused at runtime.

    response_model existing is not the same as it bearing weight. Break the body
    the service returns (nodeId as an int) and the route must fail to serve it
    rather than pass a shape the screen cannot trust.
    """
    broken = {**_fixture("workspace-create-response.json"), "nodeId": 123}
    app = _create_app(monkeypatch, broken)
    response = TestClient(app, raise_server_exceptions=False).post(
        "/v1/projects/prj_contract/workspaces", json={"name": "Contract Create Workspace"}
    )
    assert response.status_code == 500  # FastAPI ResponseValidationError, not a 201
