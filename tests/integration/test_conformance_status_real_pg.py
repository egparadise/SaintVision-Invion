"""Real PostgreSQL for the conformance status route (G-03 design §8, item 12).

What a stand-in session cannot establish is here, and nothing else:

* another tenant's project answering the **same** denial as a project the caller
  simply has no membership of, and as one that does not exist -- three ways to be
  refused, one body (design §8-2, items 10-12);
* the denial actually reaching ``audit_events`` -- **exactly one row**, with the
  columns the shared handler contract fixes (#195). The PG-free suite asserts the
  call; only a database can assert the row;
* a member with no grade beyond membership reading it, against real RLS.

The response shape, the check list derivation and the refusal to run the suite are
``tests/core/test_conformance_status_route.py`` and run everywhere.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from saintvision.adapters import agents
from saintvision.adapters.contract import CONTRACT_VERSION
from saintvision.api.app import create_app
from saintvision.api.problem import CANONICAL_KEYS
from saintvision.api.v1 import conformance_status
from saintvision.config import Settings
from saintvision.identity.principal import Principal, StaticPrincipalVerifier
from saintvision.ids import new_id

pytestmark = pytest.mark.postgres

TOKEN = "conformance-real-token"
#: Stage two binds every read to the process's host identity (design #218
#: §2-9); with none configured the route refuses rather than answering.
HOST = uuid.UUID("0f8fad5b-d9cb-469f-a165-70867728950e")


def _insert(connection, table_name, **values):
    """Insert through the model metadata, so a wrong column cannot reach hosted CI."""
    from saintvision.db import models  # noqa: F401  (registers the tables)
    from saintvision.db.base import Base

    table = Base.metadata.tables[table_name]
    unknown = set(values) - set(table.columns.keys())
    assert not unknown, f"{table_name} has no column(s) {sorted(unknown)}"
    required = {
        column.name
        for column in table.columns
        if not column.nullable and column.default is None and column.server_default is None
    }
    assert required <= set(values), f"{table_name} needs {sorted(required - set(values))}"
    connection.execute(table.insert().values(**values))


def _seed(connection, *, tenant_id, now, label, role="requester"):
    """One project and one member of it, with the given role.

    ``requester`` by default: reading this route needs membership and nothing
    more, so the default deliberately lacks the approval grade.
    """
    user_id = new_id("user")
    project_id = new_id("project")
    _insert(
        connection,
        "users",
        user_id=user_id,
        tenant_id=tenant_id,
        external_subject=f"conformance-{label}",
        display_name=f"conformance-{label}",
        status="active",
        created_at=now,
        updated_at=now,
        version=1,
    )
    _insert(
        connection,
        "projects",
        project_id=project_id,
        tenant_id=tenant_id,
        code=label,
        display_name=label,
        status="active",
        created_at=now,
        version=1,
    )
    _insert(
        connection,
        "project_members",
        tenant_id=tenant_id,
        project_id=project_id,
        user_id=user_id,
        role_code=role,
    )
    return {"user_id": user_id, "project_id": project_id}


def _client(app_engine, *, tenant_id, user_id, now):
    """The real verifier, so the no-credential path is the product's own."""
    principal = Principal(
        user_id=user_id, tenant_id=tenant_id, external_subject="conformance-real"
    )
    app = create_app(
        engine=app_engine,
        settings=Settings(database_url="test-only", control_plane_host_id=HOST),
        verifier=StaticPrincipalVerifier({TOKEN: principal}, allow_outside_dev=True),
        clock=lambda: now,
        check_partitions_on_startup=False,
    )
    return TestClient(app, raise_server_exceptions=False)


def _path(project_id):
    return f"/v1/projects/{project_id}/adapters/conformance"


def _get(client, project_id, *, token=TOKEN):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return client.get(_path(project_id), headers=headers)


def _denials(owner_engine, tenant_id=None):
    """Denial rows, read as the owner so RLS does not hide the evidence."""
    with owner_engine.begin() as connection:
        if tenant_id is None:
            rows = connection.execute(
                text(
                    "SELECT tenant_id, actor_type, actor_id, action, outcome, "
                    "reason_code, target_type, target_id, trace_id, detail "
                    "FROM audit_events WHERE outcome = 'deny' ORDER BY occurred_at"
                )
            )
        else:
            rows = connection.execute(
                text(
                    "SELECT tenant_id, actor_type, actor_id, action, outcome, "
                    "reason_code, target_type, target_id, trace_id, detail "
                    "FROM audit_events WHERE outcome = 'deny' AND tenant_id = :t "
                    "ORDER BY occurred_at"
                ),
                {"t": tenant_id},
            )
        return rows.mappings().all()


def _canonical(response, *, code, status):
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == set(CANONICAL_KEYS), body
    assert body["type"] == "about:blank"
    assert body["code"] == code
    return body


# --------------------------------------------------------------------------
# A member is told the truth
# --------------------------------------------------------------------------


def test_a_member_without_any_grade_beyond_membership_is_told_not_observed(
    owner_engine, app_engine, two_tenants, frozen_now
):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seeded = _seed(connection, tenant_id=tenant, now=frozen_now, label="conf-ok")

    client = _client(app_engine, tenant_id=tenant, user_id=seeded["user_id"], now=frozen_now)
    response = _get(client, seeded["project_id"])

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "NOT_OBSERVED"
    assert body["recordedAt"] is None
    assert body["scope"] == "control-plane-host"
    assert body["contractVersion"] == CONTRACT_VERSION
    assert body["adapters"] == [tool.name for tool in agents.TOOLS]
    assert len(body["checks"]) == len(conformance_status.CHECKLIST)
    # No counts, and nothing that could be read as a measurement.
    assert not {"total", "passed", "failed", "skipped", "conformant"} & set(body)
    # A read that succeeds is not a denial.
    assert _denials(owner_engine) == []


# --------------------------------------------------------------------------
# Three ways to be refused, one body -- and one audit row each
# --------------------------------------------------------------------------


def test_a_non_member_is_refused_and_the_denial_is_recorded_once(
    owner_engine, app_engine, two_tenants, frozen_now
):
    """The shared handler contract (#195), observed on a real database."""
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        theirs = _seed(connection, tenant_id=tenant, now=frozen_now, label="conf-own")
        outsider = _seed(connection, tenant_id=tenant, now=frozen_now, label="conf-out")

    client = _client(app_engine, tenant_id=tenant, user_id=outsider["user_id"], now=frozen_now)
    body = _canonical(_get(client, theirs["project_id"]), code="AUTH-0030", status=403)

    rows = _denials(owner_engine)
    assert len(rows) == 1, rows
    row = rows[0]
    assert row["tenant_id"] == tenant
    assert row["actor_type"] == "user"
    assert row["actor_id"] == outsider["user_id"]
    assert row["outcome"] == "deny"
    assert row["reason_code"] == "AUTH-0030"
    # The path carried a well-formed project id, so it is the target; the tenant
    # is the caller's, never the project's.
    assert row["target_type"] == "project"
    assert row["target_id"] == theirs["project_id"]
    assert row["trace_id"] == body["traceId"]
    assert row["detail"] == {}
    # The action is the bounded template: no identifier in the trail.
    assert theirs["project_id"] not in row["action"]
    assert "adapters/conformance" in row["action"]


def test_an_absent_project_and_another_tenants_are_the_same_denial(
    owner_engine, app_engine, two_tenants, frozen_now
):
    """Items 11 and 12: the two remaining ways to be refused answer identically.

    The comparison is against the non-member case as well, so the route cannot be
    used to tell "no membership" from "does not exist" from "another tenant".
    """
    tenant_a, tenant_b = two_tenants
    with owner_engine.begin() as connection:
        mine = _seed(connection, tenant_id=tenant_a, now=frozen_now, label="conf-a")
        others = _seed(connection, tenant_id=tenant_a, now=frozen_now, label="conf-a2")
        theirs = _seed(connection, tenant_id=tenant_b, now=frozen_now, label="conf-b")

    client = _client(app_engine, tenant_id=tenant_a, user_id=mine["user_id"], now=frozen_now)
    absent = new_id("project")

    shapes, actions = [], []
    for project_id in (others["project_id"], absent, theirs["project_id"]):
        body = _canonical(_get(client, project_id), code="AUTH-0030", status=403)
        shapes.append({k: v for k, v in body.items() if k != "traceId"})
        actions.append(project_id)

    assert shapes[0] == shapes[1] == shapes[2], shapes
    # Every refusal is audited, and always under the caller's tenant -- never the
    # other tenant's, which the caller has no relationship with.
    rows = _denials(owner_engine)
    assert len(rows) == 3, rows
    assert {row["tenant_id"] for row in rows} == {tenant_a}
    assert {row["actor_id"] for row in rows} == {mine["user_id"]}
    assert {row["action"] for row in rows} == {rows[0]["action"]}
    assert _denials(owner_engine, tenant_b) == []


def test_a_request_without_a_credential_is_refused_and_recorded_as_anonymous(
    owner_engine, app_engine, two_tenants, frozen_now
):
    """No credential: the real verifier refuses before the route runs.

    #184 reported this path returning 500 under the application role because the
    anonymous denial could not be written; #195 is the fix, so this asserts the
    401 and the row rather than recording a gap. If hosted disagrees, the result
    is reported as observed -- not worked around with a stub.
    """
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seeded = _seed(connection, tenant_id=tenant, now=frozen_now, label="conf-anon")

    client = _client(app_engine, tenant_id=tenant, user_id=seeded["user_id"], now=frozen_now)
    response = _get(client, seeded["project_id"], token=None)

    assert response.status_code == 401, response.text
    assert response.headers.get("WWW-Authenticate") == "Bearer"

    rows = _denials(owner_engine)
    assert len(rows) == 1, rows
    row = rows[0]
    assert row["actor_type"] == "anonymous"
    assert row["actor_id"] is None
    # No verified credential, so no tenant is claimed for the row.
    assert row["tenant_id"] is None
    assert row["outcome"] == "deny"
    assert "adapters/conformance" in row["action"]
    assert seeded["project_id"] not in row["action"]


def test_an_unusable_credential_is_refused_and_recorded(
    owner_engine, app_engine, two_tenants, frozen_now
):
    """A bearer the verifier does not know is a different code from a missing one,
    and both are denials."""
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seeded = _seed(connection, tenant_id=tenant, now=frozen_now, label="conf-bad")

    client = _client(app_engine, tenant_id=tenant, user_id=seeded["user_id"], now=frozen_now)
    response = _get(client, seeded["project_id"], token="not-a-known-token")

    assert response.status_code in (401, 403), response.text
    rows = _denials(owner_engine)
    assert len(rows) == 1, rows
    assert rows[0]["actor_type"] == "anonymous"
    assert rows[0]["outcome"] == "deny"


# --------------------------------------------------------------------------
# The route reports; it never measures
# --------------------------------------------------------------------------


def test_the_route_writes_nothing_at_all(
    owner_engine, app_engine, two_tenants, frozen_now
):
    """Phase one is a read of static facts. Nothing is recorded, not even an
    allow: there is no measurement to attribute and no row to point at."""
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seeded = _seed(connection, tenant_id=tenant, now=frozen_now, label="conf-ro")

    client = _client(app_engine, tenant_id=tenant, user_id=seeded["user_id"], now=frozen_now)
    assert _get(client, seeded["project_id"]).status_code == 200
    assert _get(client, seeded["project_id"]).status_code == 200

    with owner_engine.begin() as connection:
        events = connection.execute(
            text("SELECT count(*) FROM audit_events WHERE tenant_id = :t"),
            {"t": tenant},
        ).scalar_one()
    assert events == 0


def test_two_reads_answer_identically(
    owner_engine, app_engine, two_tenants, frozen_now
):
    """Nothing about the answer depends on the request or on time: there is no
    measurement whose age could differ between them."""
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seeded = _seed(connection, tenant_id=tenant, now=frozen_now, label="conf-same")

    client = _client(app_engine, tenant_id=tenant, user_id=seeded["user_id"], now=frozen_now)
    first = _get(client, seeded["project_id"]).json()
    second = _get(client, seeded["project_id"]).json()
    assert first == second
