"""The canonical 403 denial audit contract against a real PostgreSQL.

What only the database can establish: that an authenticated-but-unauthorised
request through the real verifier leaves **exactly one** denial row with the
caller's tenant and actor, the presented project as the target, the bounded
template action and the response's trace id -- and no mutation and no
idempotency row; that a revocation caught by the re-check after the row lock
writes nothing but is audited once; and that a failing audit write is a 500
with nothing done, not a 403.

Rows are read as the owner (the application role has no SELECT on
``audit_events`` since 0047, and reading them through it would beg the
question).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from saintvision.api import app as app_module
from saintvision.api.app import create_app
from saintvision.api.v1 import model_versions
from saintvision.config import Settings
from saintvision.identity.principal import Principal, StaticPrincipalVerifier
from saintvision.ids import new_id
from test_model_version_register_real_pg import (
    _body,
    _canonical,
    _headers,
    _insert,
    _ledger,
    _path,
    _rows,
    _seed,
)

pytestmark = pytest.mark.postgres

TOKEN = "denial-audit-token"
REGISTER_ACTION = "POST /v1/projects/{project_id}/models/{model_id}/versions"


def _client(app_engine, *, tenant_id, user_id, now):
    """The real verifier and the real ``get_principal``: the actor the recorder
    sees is what a verified credential pinned on the request, not an override."""
    principal = Principal(user_id=user_id, tenant_id=tenant_id, external_subject="oidc:denial-audit")
    app = create_app(
        engine=app_engine,
        settings=Settings(database_url="test-only", idempotency_ttl_seconds=600),
        verifier=StaticPrincipalVerifier({TOKEN: principal}, allow_outside_dev=True),
        clock=lambda: now,
        check_partitions_on_startup=False,
    )
    return TestClient(app, raise_server_exceptions=False)


def _auth(key):
    return {**_headers(key), "Authorization": f"Bearer {TOKEN}"}


def _denials(owner_engine):
    with owner_engine.begin() as connection:
        return connection.execute(
            text(
                "SELECT tenant_id, actor_type, actor_id, target_type, target_id, reason_code, "
                "action, trace_id, outcome, detail FROM audit_events WHERE outcome = 'deny' "
                "ORDER BY occurred_at"
            )
        ).mappings().all()


def test_an_authenticated_member_without_the_grade_is_403_with_exactly_one_denial_row_and_no_write(
    owner_engine, app_engine, two_tenants, frozen_now, clean_tables
):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seeded = _seed(connection, tenant_id=tenant, now=frozen_now, label="deny-1", role="operator")
    client = _client(app_engine, tenant_id=tenant, user_id=seeded["user_id"], now=frozen_now)

    response = client.post(_path(seeded), json=_body(), headers=_auth("k-deny-1"))
    body = _canonical(response, code="AUTH-0030", status=403)

    rows = _denials(owner_engine)
    assert len(rows) == 1, rows
    row = rows[0]
    assert str(row["tenant_id"]) == str(tenant)
    assert row["actor_type"] == "user" and row["actor_id"] == seeded["user_id"]
    assert row["target_type"] == "project" and row["target_id"] == seeded["project_id"]
    assert row["reason_code"] == "AUTH-0030" and row["outcome"] == "deny"
    assert row["action"] == REGISTER_ACTION
    assert row["trace_id"] == body["traceId"]
    assert row["detail"] in ({}, "{}") or dict(row["detail"]) == {}
    assert seeded["project_id"] not in row["action"] and seeded["model_id"] not in row["action"]
    assert _rows(owner_engine, tenant) == [] and _ledger(owner_engine, tenant) == []


def test_a_revocation_caught_after_the_lock_writes_nothing_and_is_audited_once(
    owner_engine, app_engine, two_tenants, frozen_now, clean_tables, monkeypatch
):
    """The first permission check passes; the membership is revoked while the
    request holds the idempotency lock; the re-check refuses. Revert the
    re-check (or make the recorder a no-op) and the row counts fail."""
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seeded = _seed(connection, tenant_id=tenant, now=frozen_now, label="deny-2", role="approver")

    real = model_versions.serialise_idempotent_write

    def revoke_after_the_lock(session, **kwargs):
        key = real(session, **kwargs)
        with owner_engine.begin() as connection:
            connection.execute(
                text("DELETE FROM project_members WHERE tenant_id = :t AND project_id = :p AND user_id = :u"),
                {"t": tenant, "p": seeded["project_id"], "u": seeded["user_id"]},
            )
        return key

    monkeypatch.setattr(model_versions, "serialise_idempotent_write", revoke_after_the_lock)
    client = _client(app_engine, tenant_id=tenant, user_id=seeded["user_id"], now=frozen_now)

    response = client.post(_path(seeded), json=_body(), headers=_auth("k-deny-2"))
    _canonical(response, code="AUTH-0030", status=403)

    assert _rows(owner_engine, tenant) == [] and _ledger(owner_engine, tenant) == []
    rows = _denials(owner_engine)
    assert len(rows) == 1 and rows[0]["actor_id"] == seeded["user_id"]
    assert rows[0]["action"] == REGISTER_ACTION and rows[0]["target_id"] == seeded["project_id"]


def test_a_failing_audit_write_is_a_generic_500_with_nothing_done_not_a_403(
    owner_engine, app_engine, two_tenants, frozen_now, clean_tables, monkeypatch
):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seeded = _seed(connection, tenant_id=tenant, now=frozen_now, label="deny-3", role="operator")

    def broken(_engine, **_kwargs):
        raise RuntimeError("audit_events: permission denied for relation")

    monkeypatch.setattr(app_module, "record_denial_out_of_band", broken)
    client = _client(app_engine, tenant_id=tenant, user_id=seeded["user_id"], now=frozen_now)

    response = client.post(_path(seeded), json=_body(), headers=_auth("k-deny-3"))
    assert response.status_code == 500, response.text
    assert "AUTH-0030" not in response.text and "permission denied" not in response.text
    assert _rows(owner_engine, tenant) == [] and _ledger(owner_engine, tenant) == []
    assert _denials(owner_engine) == []


def test_another_tenants_project_and_an_absent_project_keep_the_same_403_and_audit_the_callers_tenant(
    owner_engine, app_engine, two_tenants, frozen_now, clean_tables
):
    tenant_a, tenant_b = two_tenants
    with owner_engine.begin() as connection:
        mine = _seed(connection, tenant_id=tenant_a, now=frozen_now, label="deny-4a", role="approver")
        theirs = _seed(connection, tenant_id=tenant_b, now=frozen_now, label="deny-4b", role="approver")
    absent = new_id("project")
    client = _client(app_engine, tenant_id=tenant_a, user_id=mine["user_id"], now=frozen_now)

    first = client.post(_path(theirs), json=_body(), headers=_auth("k-deny-4a"))
    second = client.post(_path(mine, project_id=absent), json=_body(), headers=_auth("k-deny-4b"))
    a = _canonical(first, code="AUTH-0030", status=403)
    b = _canonical(second, code="AUTH-0030", status=403)
    assert {k: v for k, v in a.items() if k != "traceId"} == {k: v for k, v in b.items() if k != "traceId"}

    rows = _denials(owner_engine)
    assert len(rows) == 2
    for row, target in zip(rows, (theirs["project_id"], absent)):
        assert str(row["tenant_id"]) == str(tenant_a)                    # the caller's tenant, never the project's
        assert row["actor_id"] == mine["user_id"]
        assert row["target_type"] == "project" and row["target_id"] == target
        assert row["action"] == REGISTER_ACTION
    assert _rows(owner_engine, tenant_a) == [] and _rows(owner_engine, tenant_b) == []


def test_without_a_credential_the_denial_is_anonymous_with_the_template_action(
    owner_engine, app_engine, two_tenants, frozen_now, clean_tables
):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seeded = _seed(connection, tenant_id=tenant, now=frozen_now, label="deny-5", role="approver")
    client = _client(app_engine, tenant_id=tenant, user_id=seeded["user_id"], now=frozen_now)

    response = client.post(_path(seeded), json=_body(), headers=_headers("k-deny-5"))
    assert response.status_code == 401, response.text
    assert response.headers.get("www-authenticate") == "Bearer"
    rows = _denials(owner_engine)
    assert len(rows) == 1
    assert rows[0]["actor_type"] == "anonymous" and rows[0]["actor_id"] is None and rows[0]["tenant_id"] is None
    assert rows[0]["reason_code"] == "AUTH-MISSING-CREDENTIAL" and rows[0]["action"] == REGISTER_ACTION
    assert _rows(owner_engine, tenant) == [] and _ledger(owner_engine, tenant) == []
