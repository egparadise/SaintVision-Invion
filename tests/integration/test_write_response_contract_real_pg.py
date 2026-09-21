"""Real PostgreSQL coverage for the highest-impact write response contracts."""

from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from saintvision.api.app import create_app
from saintvision.api.deps import get_principal
from saintvision.api.schemas import MemberRoleResultResponse
from saintvision.config import Settings
from saintvision.identity.principal import Principal, StaticPrincipalVerifier
from saintvision.ids import new_id

pytestmark = pytest.mark.postgres


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
            connection.execute(
                text(
                    "INSERT INTO users (user_id, tenant_id, external_subject, display_name, "
                    "status, created_at, updated_at, version) "
                    "VALUES (:user_id, :tenant_id, :subject, :subject, 'active', :now, :now, 1)"
                ),
                {"user_id": user_id, "tenant_id": tenant_id, "subject": subject, "now": now},
            )
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
    app = create_app(
        engine=app_engine,
        settings=Settings(database_url="test-only"),
        verifier=StaticPrincipalVerifier({}, allow_outside_dev=True),
        clock=lambda: now,
        check_partitions_on_startup=False,
    )
    app.dependency_overrides[get_principal] = lambda: principal

    with TestClient(app, raise_server_exceptions=False) as client:
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
