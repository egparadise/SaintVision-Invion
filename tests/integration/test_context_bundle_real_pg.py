"""G-04 PR 3 (R3) against a real PostgreSQL: the context-bundle metadata route.

What only the database establishes: the sealed record's bundle is answered
over a later-built one, the latest bundle is answered for an unsealed run, a
snapshot rewritten under the bundle is reported as ``hashVerified: false``
with 200, a sibling project's member is 404 through the workload join, and
the two denial rows (403 member, 401 anonymous) land through the shared
boundary (#195) with the bounded action.

Bundles are made through ``build_bundle`` and the seal through
``seal_run_record``: their invariants are the services', and a hand-written
row would test the fixture rather than the product.
"""

from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from saintvision.api.app import create_app
from saintvision.api.problem import CANONICAL_KEYS
from saintvision.config import Settings
from saintvision.db.session import tenant_scope
from saintvision.identity.principal import Principal, StaticPrincipalVerifier
from saintvision.services import context as context_service
from saintvision.services import records as record_service
from saintvision.services import runs as run_service
from test_run_record_real_pg import NOW, _client, _seed_project

pytestmark = pytest.mark.postgres

ACTION = "GET /v1/projects/{project_id}/runs/{run_id}/context-bundle"
TOKEN = "bundle-real-token"


def _items(*texts):
    return [
        context_service.ContextItem(item_id=f"doc-{i}", item_version=1, kind="document", content=t, redacted=True)
        for i, t in enumerate(texts)
    ]


def _finished_run(session, *, tenant_id, seed):
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
    return run


def _run_with_bundles(app_sessionmaker, *, tenant_id, seed, seal_first=True):
    """A finished run with two bundles; the first is sealed into the record when asked."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, tenant_id):
                run = _finished_run(session, tenant_id=tenant_id, seed=seed)
                first = context_service.build_bundle(
                    session, tenant_id=tenant_id, run_id=run.run_id, items=_items("shared handbook", "unique a"),
                    now=NOW, component_versions={"retriever": "explicit-1"}, token_estimate=7,
                )
                later = context_service.build_bundle(
                    session, tenant_id=tenant_id, run_id=run.run_id, items=_items("a later bundle"),
                    now=NOW + dt.timedelta(minutes=1),
                )
                if seal_first:
                    record_service.seal_run_record(
                        session, tenant_id=tenant_id, run_id=run.run_id, now=NOW,
                        component_versions={"adapter": "reference"}, bundle_id=first.bundle_id,
                    )
                return run.run_id, first.bundle_id, later.bundle_id


def _path(project_id, run_id):
    return f"/v1/projects/{project_id}/runs/{run_id}/context-bundle"


def _canonical(response, *, code, status):
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == set(CANONICAL_KEYS), body
    assert body["code"] == code
    return body


def _denials(owner_engine):
    with owner_engine.begin() as connection:
        return connection.execute(
            text("SELECT actor_type, actor_id, tenant_id, target_id, reason_code, action FROM audit_events "
                 "WHERE outcome = 'deny' ORDER BY occurred_at")
        ).mappings().all()


def test_the_sealed_bundle_is_answered_with_its_items_and_no_content(owner_engine, app_engine, app_sessionmaker, two_tenants, clean_tables):
    tenant_a, _ = two_tenants
    with owner_engine.begin() as connection:
        mine = _seed_project(connection, tenant_id=tenant_a, code="mine")
        sibling = _seed_project(connection, tenant_id=tenant_a, code="sibling")
    run_id, first, later = _run_with_bundles(app_sessionmaker, tenant_id=tenant_a, seed=mine)

    with _client(app_engine, tenant_id=tenant_a, user_id=mine["user_id"]) as client:
        response = client.get(_path(mine["project_id"], run_id))
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["bundleId"] == first and body["runId"] == run_id
        assert body["sealed"] is True and body["hashVerified"] is True
        assert body["itemCount"] == 2 == len(body["items"]) and body["tokenEstimate"] == 7
        assert [i["ordinal"] for i in body["items"]] == [0, 1]
        assert body["items"][0]["byteSize"] == len("shared handbook") and body["items"][1]["byteSize"] == len("unique a")
        assert body["totalBytes"] == sum(i["byteSize"] for i in body["items"])
        assert "shared handbook" not in response.text and "unique a" not in response.text
        assert body["componentVersions"] == {"retriever": "explicit-1"}
        assert set(body) == {
            "bundleId", "runId", "bundleHash", "hashVerified", "sealed", "itemCount", "totalBytes",
            "retrievalStrategy", "componentVersions", "tokenEstimate", "builtAt", "items",
        }
    with _client(app_engine, tenant_id=tenant_a, user_id=sibling["user_id"]) as client:
        body = _canonical(client.get(_path(sibling["project_id"], run_id)), code="RES-0004", status=404)
        assert first not in str(body) and later not in str(body)
        _canonical(client.get(_path(mine["project_id"], run_id)), code="AUTH-0030", status=403)


def test_an_unsealed_run_answers_its_latest_bundle(owner_engine, app_engine, app_sessionmaker, two_tenants, clean_tables):
    tenant_a, _ = two_tenants
    with owner_engine.begin() as connection:
        mine = _seed_project(connection, tenant_id=tenant_a, code="mine")
    run_id, first, later = _run_with_bundles(app_sessionmaker, tenant_id=tenant_a, seed=mine, seal_first=False)
    with _client(app_engine, tenant_id=tenant_a, user_id=mine["user_id"]) as client:
        body = client.get(_path(mine["project_id"], run_id)).json()
        assert body["bundleId"] == later and body["sealed"] is False and body["itemCount"] == 1


def test_a_rewritten_snapshot_is_reported_as_hash_verified_false_with_200(owner_engine, app_engine, app_sessionmaker, two_tenants, clean_tables):
    """The record stays the account of what was given; the changed content is
    the finding. Rewritten as the owner (the application role has no UPDATE)."""
    tenant_a, _ = two_tenants
    with owner_engine.begin() as connection:
        mine = _seed_project(connection, tenant_id=tenant_a, code="mine")
    run_id, first, _ = _run_with_bundles(app_sessionmaker, tenant_id=tenant_a, seed=mine)
    with owner_engine.begin() as connection:
        changed = connection.execute(
            text("UPDATE context_snapshots SET content = 'tampered' WHERE tenant_id = :t AND content_hash IN "
                 "(SELECT content_hash FROM context_bundle_items WHERE bundle_id = :b AND ordinal = 0)"),
            {"t": tenant_a, "b": first},
        ).rowcount
    assert changed == 1
    with _client(app_engine, tenant_id=tenant_a, user_id=mine["user_id"]) as client:
        response = client.get(_path(mine["project_id"], run_id))
        assert response.status_code == 200, response.text
        assert response.json()["hashVerified"] is False and response.json()["bundleId"] == first
        assert "tampered" not in response.text


def test_a_run_without_a_bundle_is_404_and_another_tenants_run_is_invisible(owner_engine, app_engine, app_sessionmaker, two_tenants, clean_tables):
    tenant_a, tenant_b = two_tenants
    with owner_engine.begin() as connection:
        mine = _seed_project(connection, tenant_id=tenant_a, code="mine")
        theirs = _seed_project(connection, tenant_id=tenant_b, code="theirs")
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, tenant_a):
                bare = _finished_run(session, tenant_id=tenant_a, seed=mine).run_id
    their_run, their_bundle, _ = _run_with_bundles(app_sessionmaker, tenant_id=tenant_b, seed=theirs)
    with _client(app_engine, tenant_id=tenant_a, user_id=mine["user_id"]) as client:
        body = _canonical(client.get(_path(mine["project_id"], bare)), code="RES-0004", status=404)
        assert body["detail"] == "No context bundle for this run."
        _canonical(client.get(_path(theirs["project_id"], their_run)), code="AUTH-0030", status=403)
        body = _canonical(client.get(_path(mine["project_id"], their_run)), code="RES-0004", status=404)
        assert their_bundle not in str(body)


def test_the_two_denials_land_through_the_shared_boundary_with_the_bounded_action(owner_engine, app_engine, app_sessionmaker, two_tenants, clean_tables):
    """The real verifier and the real ``get_principal`` (no override): a
    non-member's 403 and an anonymous 401, one denial row each (#195)."""
    tenant_a, _ = two_tenants
    with owner_engine.begin() as connection:
        mine = _seed_project(connection, tenant_id=tenant_a, code="mine")
        outsider = _seed_project(connection, tenant_id=tenant_a, code="outsider", member=False)
    run_id, _, _ = _run_with_bundles(app_sessionmaker, tenant_id=tenant_a, seed=mine)
    principal = Principal(user_id=outsider["user_id"], tenant_id=tenant_a, external_subject="oidc:outsider")
    app = create_app(
        engine=app_engine,
        settings=Settings(database_url="test-only"),
        verifier=StaticPrincipalVerifier({TOKEN: principal}, allow_outside_dev=True),
        clock=lambda: NOW,
        check_partitions_on_startup=False,
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        forbidden = client.get(_path(mine["project_id"], run_id), headers={"Authorization": f"Bearer {TOKEN}"})
        _canonical(forbidden, code="AUTH-0030", status=403)
        anonymous = client.get(_path(mine["project_id"], run_id))
        assert anonymous.status_code == 401 and anonymous.headers.get("www-authenticate") == "Bearer"
    rows = _denials(owner_engine)
    assert len(rows) == 2, rows
    assert rows[0]["actor_type"] == "user" and rows[0]["actor_id"] == outsider["user_id"]
    assert str(rows[0]["tenant_id"]) == str(tenant_a) and rows[0]["target_id"] == mine["project_id"]
    assert rows[0]["reason_code"] == "AUTH-0030" and rows[0]["action"] == ACTION
    assert rows[1]["actor_type"] == "anonymous" and rows[1]["tenant_id"] is None
    assert rows[1]["reason_code"] == "AUTH-MISSING-CREDENTIAL" and rows[1]["action"] == ACTION
    for row in rows:
        assert run_id not in row["action"] and mine["project_id"] not in row["action"]
