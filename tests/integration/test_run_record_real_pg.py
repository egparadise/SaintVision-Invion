"""G-04 PR 1 against a real PostgreSQL: the run-record read route under RLS and real grants.

The PG-free suite fixes the order of checks and the shape of the answer; this
file establishes what only the database can: that another tenant's run is
invisible, that a project without a membership row is 403, that a run of a
sibling project in the same tenant is 404 through the workload join, and that
an unsealed run is 404 from the service.

Rows are made through the services (create_run -> complete_run -> seal), not by
hand: the record table's invariants are the services', and a hand-written row
would test the fixture rather than the product.
"""

from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from saintvision.api.app import create_app
from saintvision.api.deps import get_principal
from saintvision.api.problem import CANONICAL_KEYS
from saintvision.config import Settings
from saintvision.db.session import tenant_scope
from saintvision.identity.principal import Principal, StaticPrincipalVerifier
from saintvision.ids import new_id
from saintvision.services import records as record_service
from saintvision.services import runs as run_service
from saintvision.services.runs import workload_digest

pytestmark = pytest.mark.postgres

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 9, 28, 5, 0, tzinfo=UTC)


def _seed_project(connection, *, tenant_id, code, member=True):
    """A user, a project, an optional membership, a workspace and a workload."""
    user_id, project_id = new_id("user"), new_id("project")
    workspace_id, workload_id = new_id("workspace"), new_id("workload")
    digest = workload_digest({"objective": "train"})
    connection.execute(
        text(
            "INSERT INTO users (user_id, tenant_id, external_subject, display_name, status, "
            "created_at, updated_at, version) VALUES (:u, :t, :s, 'U', 'active', now(), now(), 1)"
        ),
        {"u": user_id, "t": tenant_id, "s": f"record-{code}"},
    )
    connection.execute(
        text(
            "INSERT INTO projects (project_id, tenant_id, code, display_name, status, created_at, version) "
            "VALUES (:p, :t, :c, :c, 'active', now(), 1)"
        ),
        {"p": project_id, "t": tenant_id, "c": code},
    )
    if member:
        connection.execute(
            text(
                "INSERT INTO project_members (tenant_id, project_id, user_id, role_code) "
                "VALUES (:t, :p, :u, 'operator')"
            ),
            {"t": tenant_id, "p": project_id, "u": user_id},
        )
    connection.execute(
        text(
            "INSERT INTO workspaces (workspace_id, tenant_id, project_id, name, status, "
            "created_by_user_id, created_at, version) VALUES (:w, :t, :p, 'ws', 'ready', :u, now(), 1)"
        ),
        {"w": workspace_id, "t": tenant_id, "p": project_id, "u": user_id},
    )
    connection.execute(
        text(
            "INSERT INTO workloads (workload_id, tenant_id, project_id, kind, objective, spec, "
            "spec_sha256, contract_version, created_by_user_id, created_at, version) "
            "VALUES (:wl, :t, :p, 'batch', 'train', '{}', :d, '1.0.0', :u, now(), 1)"
        ),
        {"wl": workload_id, "t": tenant_id, "p": project_id, "d": digest, "u": user_id},
    )
    return {"user_id": user_id, "project_id": project_id, "workspace_id": workspace_id, "workload_id": workload_id}


def _sealed_run(app_sessionmaker, *, tenant_id, seed, seal=True):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, tenant_id):
                run = run_service.create_run(
                    session, tenant_id=tenant_id, workload_id=seed["workload_id"],
                    workspace_id=seed["workspace_id"], requested_by_user_id=seed["user_id"], now=NOW,
                )
                for target in ("validated", "planned", "scheduled"):
                    run_service.advance(session, tenant_id=tenant_id, run_id=run.run_id, target=target, now=NOW)
                run_service.start_attempt(session, tenant_id=tenant_id, run_id=run.run_id, now=NOW)
                run_service.advance(session, tenant_id=tenant_id, run_id=run.run_id, target="verifying", now=NOW)
                run_service.complete_run(
                    session, tenant_id=tenant_id, run_id=run.run_id, now=NOW, actor_type="system",
                    actor_id="control-plane", action="run.complete", input_schema="RunInput@1",
                    input_payload={"objective": "train"}, output_ref=f"inv://artifacts/{run.run_id}/art_x",
                )
                record = None
                if seal:
                    record = record_service.seal_run_record(
                        session, tenant_id=tenant_id, run_id=run.run_id, now=NOW,
                        component_versions={"adapter": "reference"},
                    )
                return run.run_id, (record.record_id if record else None)


def _client(app_engine, *, tenant_id, user_id):
    app = create_app(
        engine=app_engine,
        settings=Settings(database_url="test-only"),
        verifier=StaticPrincipalVerifier({}, allow_outside_dev=True),
        clock=lambda: NOW,
        check_partitions_on_startup=False,
    )
    app.dependency_overrides[get_principal] = lambda: Principal(
        user_id=user_id, tenant_id=tenant_id, external_subject="synthetic-record"
    )
    return TestClient(app, raise_server_exceptions=False)


def _path(project_id, run_id):
    return f"/v1/projects/{project_id}/runs/{run_id}/record"


def _canonical(response, *, code, status):
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == set(CANONICAL_KEYS), body
    assert body["code"] == code
    return body


def test_a_member_reads_the_record_and_a_sibling_project_cannot_see_it_by_path(
    owner_engine, app_engine, app_sessionmaker, two_tenants, clean_tables
):
    tenant_a, _ = two_tenants
    with owner_engine.begin() as connection:
        mine = _seed_project(connection, tenant_id=tenant_a, code="mine")
        sibling = _seed_project(connection, tenant_id=tenant_a, code="sibling")
    run_id, record_id = _sealed_run(app_sessionmaker, tenant_id=tenant_a, seed=mine)

    with _client(app_engine, tenant_id=tenant_a, user_id=mine["user_id"]) as client:
        response = client.get(_path(mine["project_id"], run_id))
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["recordId"] == record_id and body["runId"] == run_id
        assert body["finalState"] == "succeeded" and body["terminationReason"] == "completed"
        assert body["componentVersions"] == {"adapter": "reference"}
        assert set(body) == {
            "recordId", "runId", "finalState", "terminationReason", "evidenceId", "bundleId",
            "bundleHash", "workloadSpecSha256", "componentVersions", "attemptCount", "sealedAt",
        }
    # The sibling project's member is a member of *that* project only: the path
    # names their project, the run belongs to mine -> 404 through the workload join.
    with _client(app_engine, tenant_id=tenant_a, user_id=sibling["user_id"]) as client:
        body = _canonical(client.get(_path(sibling["project_id"], run_id)), code="RES-0004", status=404)
        assert record_id not in str(body)
        # And my project by path, where they hold no membership -> 403, no row read.
        _canonical(client.get(_path(mine["project_id"], run_id)), code="AUTH-0030", status=403)


def test_another_tenants_run_is_invisible_under_rls(owner_engine, app_engine, app_sessionmaker, two_tenants, clean_tables):
    tenant_a, tenant_b = two_tenants
    with owner_engine.begin() as connection:
        theirs = _seed_project(connection, tenant_id=tenant_b, code="theirs")
        mine = _seed_project(connection, tenant_id=tenant_a, code="mine")
    their_run, their_record = _sealed_run(app_sessionmaker, tenant_id=tenant_b, seed=theirs)
    with _client(app_engine, tenant_id=tenant_a, user_id=mine["user_id"]) as client:
        _canonical(client.get(_path(theirs["project_id"], their_run)), code="AUTH-0030", status=403)
        body = _canonical(client.get(_path(mine["project_id"], their_run)), code="RES-0004", status=404)
        assert their_record not in str(body)


def test_a_finished_but_unsealed_run_is_404_from_the_service(owner_engine, app_engine, app_sessionmaker, two_tenants, clean_tables):
    tenant_a, _ = two_tenants
    with owner_engine.begin() as connection:
        mine = _seed_project(connection, tenant_id=tenant_a, code="mine")
    run_id, _ = _sealed_run(app_sessionmaker, tenant_id=tenant_a, seed=mine, seal=False)
    with _client(app_engine, tenant_id=tenant_a, user_id=mine["user_id"]) as client:
        body = _canonical(client.get(_path(mine["project_id"], run_id)), code="RES-0004", status=404)
        assert body["detail"] == "No sealed record for this run."


def test_without_a_credential_the_route_is_401_before_any_row_is_read(owner_engine, app_engine, app_sessionmaker, two_tenants, clean_tables):
    tenant_a, _ = two_tenants
    with owner_engine.begin() as connection:
        mine = _seed_project(connection, tenant_id=tenant_a, code="mine")
    run_id, _ = _sealed_run(app_sessionmaker, tenant_id=tenant_a, seed=mine)
    app = create_app(
        engine=app_engine,
        settings=Settings(database_url="test-only"),
        verifier=StaticPrincipalVerifier({}, allow_outside_dev=True),
        clock=lambda: NOW,
        check_partitions_on_startup=False,
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(_path(mine["project_id"], run_id))
        assert response.status_code == 401, response.text
        assert run_id not in response.text


def test_a_non_member_of_an_existing_project_is_403_not_404(owner_engine, app_engine, app_sessionmaker, two_tenants, clean_tables):
    tenant_a, _ = two_tenants
    with owner_engine.begin() as connection:
        mine = _seed_project(connection, tenant_id=tenant_a, code="mine")
        outsider = _seed_project(connection, tenant_id=tenant_a, code="outsider", member=False)
    run_id, _ = _sealed_run(app_sessionmaker, tenant_id=tenant_a, seed=mine)
    with _client(app_engine, tenant_id=tenant_a, user_id=outsider["user_id"]) as client:
        _canonical(client.get(_path(mine["project_id"], run_id)), code="AUTH-0030", status=403)
