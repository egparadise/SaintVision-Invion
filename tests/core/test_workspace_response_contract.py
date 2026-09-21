"""Workspace picker/readiness responses serialize the fixtures shared with the web UI."""

from __future__ import annotations

import json
from pathlib import Path
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from saintvision.api import schemas
from saintvision.api.deps import get_principal, get_session
from saintvision.api.v1 import projects, readiness
from saintvision.identity.principal import Principal

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "contracts/fixtures"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("filename", "model"),
    [
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
    if mutate == "missing-page-count":
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
        ("/v1/projects/prj_contract/workspaces", "project-workspaces-response.json", "workspaces"),
        ("/v1/workspaces/wsp_contract/execution-readiness", "workspace-execution-readiness-response.json", "readiness"),
    ],
)
def test_fastapi_workspace_routes_serialize_the_shared_fixture(monkeypatch, path, filename, service):
    payload = _fixture(filename)
    if service == "workspaces":
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
    model = (
        schemas.ProjectWorkspacesResponse
        if service == "workspaces"
        else schemas.WorkspaceExecutionReadinessResponse
    )
    model.model_validate(response.json())
