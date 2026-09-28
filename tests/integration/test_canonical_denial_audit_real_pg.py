"""The canonical 403 denial audit contract against a real PostgreSQL.

What only the database can establish: that an authenticated-but-unauthorised
request through the real verifier leaves **exactly one** denial row with the
caller's tenant and actor, the presented project as the target, the bounded
template action and the response's trace id -- and no mutation; that a
revocation caught by the re-check in the write transaction writes nothing but
is audited once; and that a failing audit write is a 500 with nothing done,
not a 403.

The route is #167's release (``canApprove`` grade, live re-check in its write
transaction); the rows are read as the owner (the application role has no
SELECT on ``audit_events`` since 0047, and reading them through it would beg
the question).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from saintvision.api import app as app_module
from saintvision.api.app import create_app
from saintvision.api.audit_action import long_template_action
from saintvision.config import Settings
from saintvision.identity.principal import Principal, StaticPrincipalVerifier
from saintvision.ids import new_id
from test_model_release_real_pg import (
    DECLARATION,
    _canonical,
    _observation,
    _path,
    _seed,
    _stage,
)

pytestmark = pytest.mark.postgres

TOKEN = "denial-audit-token"
RELEASE_TEMPLATE = "/v1/projects/{project_id}/models/{model_id}/versions/{version}/release"
RELEASE_ACTION = long_template_action("POST", RELEASE_TEMPLATE, "release_model_version")


def _client(app_engine, *, tenant_id, user_id, now, observation):
    """The real verifier and the real ``get_principal``: the actor the recorder
    sees is what a verified credential pinned on the request, not an override."""
    principal = Principal(user_id=user_id, tenant_id=tenant_id, external_subject="oidc:denial-audit")
    app = create_app(
        engine=app_engine,
        settings=Settings(database_url="test-only", kernel_base_url="http://kernel.invalid"),
        verifier=StaticPrincipalVerifier({TOKEN: principal}, allow_outside_dev=True),
        clock=lambda: now,
        check_partitions_on_startup=False,
    )
    app.state.model_commitment_fetcher = lambda **_kwargs: observation
    return TestClient(app, raise_server_exceptions=False)


AUTH = {"Authorization": f"Bearer {TOKEN}"}


def _denials(owner_engine):
    with owner_engine.begin() as connection:
        return connection.execute(
            text(
                "SELECT tenant_id, actor_type, actor_id, target_type, target_id, reason_code, "
                "action, trace_id, outcome, detail FROM audit_events WHERE outcome = 'deny' "
                "ORDER BY occurred_at"
            )
        ).mappings().all()


def _no_denial_detail(row):
    detail = row["detail"]
    return detail in (None, {}, "{}") or dict(detail) == {}


def test_an_authenticated_member_without_the_grade_is_403_with_exactly_one_denial_row_and_no_write(
    owner_engine, app_engine, two_tenants, frozen_now, clean_tables
):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seeded = _seed(connection, tenant_id=tenant, now=frozen_now, project_code="deny-1", role="operator")
    observation = _observation(seeded["project_id"], seeded["model_id"], "1.0.0")
    client = _client(app_engine, tenant_id=tenant, user_id=seeded["user_id"], now=frozen_now, observation=observation)

    response = client.post(_path(seeded), json=DECLARATION, headers=AUTH)
    body = _canonical(response, code="AUTH-0030", status=403)

    rows = _denials(owner_engine)
    assert len(rows) == 1, rows
    row = rows[0]
    assert str(row["tenant_id"]) == str(tenant)
    assert row["actor_type"] == "user" and row["actor_id"] == seeded["user_id"]
    assert row["target_type"] == "project" and row["target_id"] == seeded["project_id"]
    assert row["reason_code"] == "AUTH-0030" and row["outcome"] == "deny"
    assert row["action"] == RELEASE_ACTION and len(row["action"]) <= 64
    assert row["trace_id"] == body["traceId"]
    assert _no_denial_detail(row)
    for raw in (seeded["project_id"], seeded["model_id"], seeded["user_id"]):
        assert raw not in row["action"]
    assert _stage(owner_engine, seeded["version_id"]) == "draft"


def test_a_revocation_caught_by_the_re_check_in_the_write_transaction_writes_nothing_and_is_audited_once(
    owner_engine, app_engine, two_tenants, frozen_now, clean_tables
):
    """The preflight passes; the membership is revoked while the observation is
    fetched; the write transaction's re-check refuses. Revert the re-check (or
    make the recorder a no-op) and the row counts fail."""
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seeded = _seed(connection, tenant_id=tenant, now=frozen_now, project_code="deny-2", role="approver")
    observation = _observation(seeded["project_id"], seeded["model_id"], "1.0.0")

    def revoke_then_observe(**_kwargs):
        with owner_engine.begin() as connection:
            connection.execute(
                text("DELETE FROM project_members WHERE tenant_id = :t AND project_id = :p AND user_id = :u"),
                {"t": tenant, "p": seeded["project_id"], "u": seeded["user_id"]},
            )
        return observation

    client = _client(app_engine, tenant_id=tenant, user_id=seeded["user_id"], now=frozen_now, observation=observation)
    client.app.state.model_commitment_fetcher = revoke_then_observe

    response = client.post(_path(seeded), json=DECLARATION, headers=AUTH)
    _canonical(response, code="AUTH-0030", status=403)

    assert _stage(owner_engine, seeded["version_id"]) == "draft"
    rows = _denials(owner_engine)
    assert len(rows) == 1 and rows[0]["actor_id"] == seeded["user_id"]
    assert rows[0]["action"] == RELEASE_ACTION and rows[0]["target_id"] == seeded["project_id"]


def test_a_failing_audit_write_is_a_generic_500_with_nothing_done_not_a_403(
    owner_engine, app_engine, two_tenants, frozen_now, clean_tables, monkeypatch
):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seeded = _seed(connection, tenant_id=tenant, now=frozen_now, project_code="deny-3", role="operator")
    observation = _observation(seeded["project_id"], seeded["model_id"], "1.0.0")

    def broken(_engine, **_kwargs):
        raise RuntimeError("audit_events: permission denied for relation")

    monkeypatch.setattr(app_module, "record_denial_out_of_band", broken)
    client = _client(app_engine, tenant_id=tenant, user_id=seeded["user_id"], now=frozen_now, observation=observation)

    response = client.post(_path(seeded), json=DECLARATION, headers=AUTH)
    assert response.status_code == 500, response.text
    assert "AUTH-0030" not in response.text and "permission denied" not in response.text
    assert _stage(owner_engine, seeded["version_id"]) == "draft"
    assert _denials(owner_engine) == []


def test_another_tenants_project_and_an_absent_project_keep_the_same_403_and_audit_the_callers_tenant(
    owner_engine, app_engine, two_tenants, frozen_now, clean_tables
):
    tenant_a, tenant_b = two_tenants
    with owner_engine.begin() as connection:
        mine = _seed(connection, tenant_id=tenant_a, now=frozen_now, project_code="deny-4a", role="approver")
        theirs = _seed(connection, tenant_id=tenant_b, now=frozen_now, project_code="deny-4b", role="approver")
    absent = new_id("project")
    observation = _observation(mine["project_id"], mine["model_id"], "1.0.0")
    client = _client(app_engine, tenant_id=tenant_a, user_id=mine["user_id"], now=frozen_now, observation=observation)

    first = client.post(_path(theirs), json=DECLARATION, headers=AUTH)
    second = client.post(_path(mine, project_id=absent), json=DECLARATION, headers=AUTH)
    a = _canonical(first, code="AUTH-0030", status=403)
    b = _canonical(second, code="AUTH-0030", status=403)
    assert {k: v for k, v in a.items() if k != "traceId"} == {k: v for k, v in b.items() if k != "traceId"}

    rows = _denials(owner_engine)
    assert len(rows) == 2
    for row, target in zip(rows, (theirs["project_id"], absent)):
        assert str(row["tenant_id"]) == str(tenant_a)                    # the caller's tenant, never the project's
        assert row["actor_id"] == mine["user_id"]
        assert row["target_type"] == "project" and row["target_id"] == target
        assert row["action"] == RELEASE_ACTION and _no_denial_detail(row)
    assert _stage(owner_engine, mine["version_id"]) == "draft"
    assert _stage(owner_engine, theirs["version_id"]) == "draft"


def test_without_a_credential_the_denial_is_anonymous_with_the_bounded_action(
    owner_engine, app_engine, two_tenants, frozen_now, clean_tables
):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seeded = _seed(connection, tenant_id=tenant, now=frozen_now, project_code="deny-5", role="approver")
    observation = _observation(seeded["project_id"], seeded["model_id"], "1.0.0")
    client = _client(app_engine, tenant_id=tenant, user_id=seeded["user_id"], now=frozen_now, observation=observation)

    response = client.post(_path(seeded), json=DECLARATION)
    assert response.status_code == 401, response.text
    assert response.headers.get("www-authenticate") == "Bearer"
    rows = _denials(owner_engine)
    assert len(rows) == 1
    assert rows[0]["actor_type"] == "anonymous" and rows[0]["actor_id"] is None and rows[0]["tenant_id"] is None
    assert rows[0]["reason_code"] == "AUTH-MISSING-CREDENTIAL" and rows[0]["action"] == RELEASE_ACTION
    assert _stage(owner_engine, seeded["version_id"]) == "draft"
