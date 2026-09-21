"""Real PostgreSQL coverage for the highest-impact write response contracts."""

from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from saintvision.api.app import create_app
from saintvision.api.deps import get_principal
from saintvision.api.schemas import (
    MemberRoleResultResponse,
    ProjectCreateResponse,
    ResourceOfferResultResponse,
    WorkspaceStatusResponse,
)
from saintvision.config import Settings
from saintvision.identity.principal import Principal, StaticPrincipalVerifier
from saintvision.ids import new_id

pytestmark = pytest.mark.postgres


def _app(app_engine, now, principal):
    app = create_app(
        engine=app_engine,
        settings=Settings(database_url="test-only"),
        verifier=StaticPrincipalVerifier({}, allow_outside_dev=True),
        clock=lambda: now,
        check_partitions_on_startup=False,
    )
    app.dependency_overrides[get_principal] = lambda: principal
    return app


def _insert_user(connection, tenant_id, user_id, subject, now):
    connection.execute(
        text(
            "INSERT INTO users (user_id, tenant_id, external_subject, display_name, "
            "status, created_at, updated_at, version) "
            "VALUES (:user_id, :tenant_id, :subject, :subject, 'active', :now, :now, 1)"
        ),
        {"user_id": user_id, "tenant_id": tenant_id, "subject": subject, "now": now},
    )


def test_project_create_response_matches_real_postgres_state(owner_engine, app_engine, two_tenants):
    tenant_id, _ = two_tenants
    creator_id = new_id("user")
    now = dt.datetime.now(dt.timezone.utc)
    with owner_engine.begin() as connection:
        _insert_user(connection, tenant_id, creator_id, "project-creator", now)

    principal = Principal(
        user_id=creator_id,
        tenant_id=tenant_id,
        external_subject="synthetic-project-creator",
    )
    with TestClient(_app(app_engine, now, principal), raise_server_exceptions=False) as client:
        response = client.post(
            "/v1/projects",
            json={"code": "pg-create-contract", "displayName": "PostgreSQL created"},
        )

    assert response.status_code == 201, "real PostgreSQL project creation route must succeed"
    payload = response.json()
    parsed = ProjectCreateResponse.model_validate(payload)
    assert parsed.code == "pg-create-contract"
    assert parsed.display_name == "PostgreSQL created"
    assert parsed.status == "active"
    assert parsed.member_count == 1
    assert parsed.kernel_linked is False
    assert parsed.kernel_enabled is False
    assert "kernelNote" in payload
    with owner_engine.connect() as connection:
        saved = connection.execute(
            text(
                "SELECT p.project_id, pm.user_id, pm.role_code "
                "FROM projects p JOIN project_members pm "
                "USING (tenant_id, project_id) "
                "WHERE p.tenant_id=:tenant_id AND p.code='pg-create-contract'"
            ),
            {"tenant_id": tenant_id},
        ).mappings().one()
    assert saved["project_id"] == parsed.project_id
    assert saved["user_id"] == creator_id
    assert saved["role_code"] == "owner"


def test_member_role_write_response_matches_real_postgres_state(
    owner_engine, app_engine, two_tenants
):
    tenant_id, _ = two_tenants
    owner_id = new_id("user")
    member_id = new_id("user")
    project_id = new_id("project")
    now = dt.datetime.now(dt.timezone.utc)

    with owner_engine.begin() as connection:
        for user_id, subject in ((owner_id, "owner"), (member_id, "member")):
            _insert_user(connection, tenant_id, user_id, subject, now)
        connection.execute(
            text(
                "INSERT INTO projects (project_id, tenant_id, code, display_name, status, created_at, version) "
                "VALUES (:project_id, :tenant_id, 'pg-role-contract', 'PG role contract', 'active', :now, 1)"
            ),
            {"project_id": project_id, "tenant_id": tenant_id, "now": now},
        )
        connection.execute(
            text(
                "INSERT INTO project_members (tenant_id, project_id, user_id, role_code, granted_at) "
                "VALUES (:tenant_id, :project_id, :owner_id, 'owner', :now), "
                "(:tenant_id, :project_id, :member_id, 'viewer', :now)"
            ),
            {
                "tenant_id": tenant_id,
                "project_id": project_id,
                "owner_id": owner_id,
                "member_id": member_id,
                "now": now,
            },
        )
        connection.execute(
            text(
                "INSERT INTO inv.business_admin_grants (tenant_id, user_id, permission, enabled) "
                "VALUES (:tenant_id, :owner_id, 'resources.manage', true)"
            ),
            {"tenant_id": tenant_id, "owner_id": owner_id},
        )

    principal = Principal(
        user_id=owner_id,
        tenant_id=tenant_id,
        external_subject="synthetic-pg-role-operator",
    )
    with TestClient(_app(app_engine, now, principal), raise_server_exceptions=False) as client:
        response = client.put(
            f"/v1/projects/{project_id}/members/{member_id}",
            json={"roleCode": "maintainer"},
        )

    assert response.status_code == 200, "real PostgreSQL role update route must succeed"
    payload = response.json()
    parsed = MemberRoleResultResponse.model_validate(payload)
    assert parsed.project_id == project_id
    assert parsed.user_id == member_id
    assert parsed.role_code == "maintainer"
    assert parsed.project_status == "active"
    assert parsed.user_status == "active"
    assert parsed.can_request is True
    assert parsed.can_approve is False
    assert parsed.can_administer is False

    with owner_engine.connect() as connection:
        saved_role = connection.execute(
            text(
                "SELECT role_code FROM project_members "
                "WHERE tenant_id=:tenant_id AND project_id=:project_id AND user_id=:user_id"
            ),
            {"tenant_id": tenant_id, "project_id": project_id, "user_id": member_id},
        ).scalar_one()
    assert saved_role == parsed.role_code


def test_workspace_status_response_allowed_next_matches_real_lifecycle_state(
    owner_engine, app_engine, two_tenants
):
    tenant_id, _ = two_tenants
    owner_id = new_id("user")
    project_id = new_id("project")
    workspace_id = new_id("workspace")
    now = dt.datetime.now(dt.timezone.utc)
    with owner_engine.begin() as connection:
        _insert_user(connection, tenant_id, owner_id, "workspace-owner", now)
        connection.execute(
            text(
                "INSERT INTO projects (project_id, tenant_id, code, display_name, status, created_at, version) "
                "VALUES (:project_id, :tenant_id, 'pg-workspace-contract', 'PG workspace contract', 'active', :now, 1)"
            ),
            {"project_id": project_id, "tenant_id": tenant_id, "now": now},
        )
        connection.execute(
            text(
                "INSERT INTO project_members (tenant_id, project_id, user_id, role_code, granted_at) "
                "VALUES (:tenant_id, :project_id, :owner_id, 'owner', :now)"
            ),
            {"tenant_id": tenant_id, "project_id": project_id, "owner_id": owner_id, "now": now},
        )
        connection.execute(
            text(
                "INSERT INTO workspaces (workspace_id, tenant_id, project_id, name, status, "
                "created_by_user_id, created_at, version) "
                "VALUES (:workspace_id, :tenant_id, :project_id, 'pg-workspace', "
                "'provisioning', :owner_id, :now, 1)"
            ),
            {
                "workspace_id": workspace_id,
                "tenant_id": tenant_id,
                "project_id": project_id,
                "owner_id": owner_id,
                "now": now,
            },
        )

    principal = Principal(
        user_id=owner_id,
        tenant_id=tenant_id,
        external_subject="synthetic-workspace-owner",
    )
    with TestClient(_app(app_engine, now, principal), raise_server_exceptions=False) as client:
        response = client.put(
            f"/v1/workspaces/{workspace_id}/status", json={"status": "ready"}
        )

    assert response.status_code == 200, "real PostgreSQL workspace transition route must succeed"
    payload = response.json()
    parsed = WorkspaceStatusResponse.model_validate(payload)
    assert parsed.workspace_id == workspace_id
    assert parsed.status == "ready"
    assert parsed.allowed_next == ["deleting", "suspended"]
    with owner_engine.connect() as connection:
        saved_status = connection.execute(
            text("SELECT status FROM workspaces WHERE tenant_id=:tenant_id AND workspace_id=:workspace_id"),
            {"tenant_id": tenant_id, "workspace_id": workspace_id},
        ).scalar_one()
    assert saved_status == parsed.status


def test_resource_offer_write_response_matches_real_postgres_state(
    owner_engine, app_engine, two_tenants
):
    tenant_id, _ = two_tenants
    owner_id = new_id("user")
    node_id = new_id("node")
    capability_id = new_id("capability")
    now = dt.datetime.now(dt.timezone.utc)
    with owner_engine.begin() as connection:
        _insert_user(connection, tenant_id, owner_id, "offer-owner", now)
        connection.execute(
            text(
                "INSERT INTO inv.business_admin_grants (tenant_id, user_id, permission, enabled) "
                "VALUES (:tenant_id, :owner_id, 'resources.manage', true)"
            ),
            {"tenant_id": tenant_id, "owner_id": owner_id},
        )
        connection.execute(
            text(
                "INSERT INTO nodes (node_id, tenant_id, hostname, os_type, os_version, "
                "agent_version, status, enrolled_at, heartbeat_sequence, version) "
                "VALUES (:node_id, :tenant_id, 'offer-host', 'linux', 'test', 'test', "
                "'active', :now, 0, 1)"
            ),
            {"node_id": node_id, "tenant_id": tenant_id, "now": now},
        )
        connection.execute(
            text(
                "INSERT INTO node_capabilities (capability_id, tenant_id, node_id, kind, "
                "device_index, total_quantity, unit, divisible, detected_at, version) "
                "VALUES (:capability_id, :tenant_id, :node_id, 'cpu', NULL, 16000, "
                "'millicores', true, :now, 1)"
            ),
            {
                "capability_id": capability_id,
                "tenant_id": tenant_id,
                "node_id": node_id,
                "now": now,
            },
        )

    principal = Principal(
        user_id=owner_id,
        tenant_id=tenant_id,
        external_subject="synthetic-offer-operator",
    )
    with TestClient(_app(app_engine, now, principal), raise_server_exceptions=False) as client:
        response = client.put(
            f"/v1/capabilities/{capability_id}/offer",
            json={"offeredQuantity": 8000.0, "unit": "millicores"},
        )

    assert response.status_code == 200, "real PostgreSQL capability offer route must succeed"
    payload = response.json()
    parsed = ResourceOfferResultResponse.model_validate(payload)
    assert parsed.capability_id == capability_id
    assert parsed.node_id == node_id
    assert parsed.kind == "cpu"
    assert parsed.unit == "millicores"
    assert parsed.offered_quantity == 8000
    assert parsed.total_quantity == 16000
    assert parsed.previous_offered_quantity is None
    assert parsed.applied_to_kernel is False
    assert parsed.kernel_reason_code == "resource_not_registered"
    assert "kernelReason" in payload
    with owner_engine.connect() as connection:
        saved = connection.execute(
            text(
                "SELECT offered_quantity, effective_to FROM resource_offers "
                "WHERE tenant_id=:tenant_id AND capability_id=:capability_id"
            ),
            {"tenant_id": tenant_id, "capability_id": capability_id},
        ).mappings().one()
    assert saved["offered_quantity"] == parsed.offered_quantity
    assert saved["effective_to"] is None
