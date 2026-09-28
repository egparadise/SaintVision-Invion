"""G-04 PR 2 (R2) against a real PostgreSQL: pinned-artifact list and pin verification.

Builds on the PR 1 fixtures (``test_run_record_real_pg``): a project with a
member, a run driven through the services to ``succeeded``, a verified artifact
inserted the way ``tests/test_context_eval.py`` does it, and a record sealed
with pins. What only the database can establish is here: the pin rows a
sibling project cannot see by path, RLS across tenants, the role filter on
real rows, and a pin whose object was changed after sealing reporting
``verified: false`` while the record row stays what it was.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from saintvision.api.problem import CANONICAL_KEYS
from saintvision.db.session import tenant_scope
from saintvision.ids import new_id
from saintvision.services import records as record_service
from saintvision.services import runs as run_service
from test_run_record_real_pg import NOW, _client, _seed_project

pytestmark = pytest.mark.postgres


def _verified_artifact(session, *, tenant_id, run_id, name, checksum="b" * 64):
    artifact_id = new_id("artifact")
    session.execute(
        text(
            "INSERT INTO artifacts (artifact_id, tenant_id, run_id, name, media_type, "
            "status, byte_size, checksum_sha256, verified_at, object_version, created_at, version) "
            "VALUES (:a, :t, :r, :n, 'text/plain', 'active', 12, :c, now(), 'v1', now(), 1)"
        ),
        {"a": artifact_id, "t": tenant_id, "r": run_id, "n": name, "c": checksum},
    )
    return artifact_id


def _sealed_with_pins(app_sessionmaker, *, tenant_id, seed):
    run_id, record_id, ids = _sealed_with(
        app_sessionmaker, tenant_id=tenant_id, seed=seed, pins=[("changes.patch", "diff"), ("otel.json", "trace")]
    )
    return run_id, record_id, ids[0], ids[1]


def _sealed_with(app_sessionmaker, *, tenant_id, seed, pins):
    """A sealed record pinning one verified artifact per ``(name, role)``; ids in pin order."""
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
                ids = [
                    _verified_artifact(session, tenant_id=tenant_id, run_id=run.run_id, name=name)
                    for name, _role in pins
                ]
                record = record_service.seal_run_record(
                    session, tenant_id=tenant_id, run_id=run.run_id, now=NOW,
                    artifacts=[record_service.ArtifactPin(a, role) for a, (_n, role) in zip(ids, pins)],
                )
                return run.run_id, record.record_id, ids


def _artifacts_path(project_id, run_id, role=None):
    path = f"/v1/projects/{project_id}/runs/{run_id}/record/artifacts"
    return path + (f"?role={role}" if role else "")


def _verify_path(project_id, run_id, artifact_id):
    return f"/v1/projects/{project_id}/runs/{run_id}/record/artifacts/{artifact_id}/verify"


def _canonical(response, *, code, status):
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == set(CANONICAL_KEYS), body
    assert body["code"] == code
    return body


def test_a_member_lists_and_filters_real_pins_and_a_sibling_project_cannot(
    owner_engine, app_engine, app_sessionmaker, two_tenants, clean_tables
):
    tenant_a, _ = two_tenants
    with owner_engine.begin() as connection:
        mine = _seed_project(connection, tenant_id=tenant_a, code="mine")
        sibling = _seed_project(connection, tenant_id=tenant_a, code="sibling")
    run_id, record_id, diff, trace = _sealed_with_pins(app_sessionmaker, tenant_id=tenant_a, seed=mine)

    with _client(app_engine, tenant_id=tenant_a, user_id=mine["user_id"]) as client:
        body = client.get(_artifacts_path(mine["project_id"], run_id)).json()
        assert body["recordId"] == record_id and body["runId"] == run_id and body["count"] == 2
        assert sorted(i["artifactId"] for i in body["items"]) == sorted([diff, trace])
        assert {i["role"] for i in body["items"]} == {"diff", "trace"}
        assert all(i["checksumSha256"] == "b" * 64 and i["byteSize"] == 12 for i in body["items"])
        only = client.get(_artifacts_path(mine["project_id"], run_id, "trace")).json()
        assert [i["artifactId"] for i in only["items"]] == [trace] and only["role"] == "trace"
        _canonical(client.get(_artifacts_path(mine["project_id"], run_id, "screenshot")), code="VAL-0003", status=422)
    with _client(app_engine, tenant_id=tenant_a, user_id=sibling["user_id"]) as client:
        body = _canonical(client.get(_artifacts_path(sibling["project_id"], run_id)), code="RES-0004", status=404)
        assert diff not in str(body) and record_id not in str(body)
        _canonical(client.get(_verify_path(sibling["project_id"], run_id, diff)), code="RES-0004", status=404)
        _canonical(client.get(_artifacts_path(mine["project_id"], run_id)), code="AUTH-0030", status=403)


def test_the_list_is_paged_on_real_rows_with_a_stable_cursor_and_the_role_filter_across_pages(
    owner_engine, app_engine, app_sessionmaker, two_tenants, clean_tables
):
    """Codex #188 F2 on the real query: filter -> cursor -> limit, no gap, no repeat."""
    tenant_a, _ = two_tenants
    with owner_engine.begin() as connection:
        mine = _seed_project(connection, tenant_id=tenant_a, code="mine")
    pins = [("a.patch", "diff"), ("b.json", "trace"), ("c.patch", "diff"), ("d.log", "log"), ("e.patch", "diff")]
    run_id, _record_id, ids = _sealed_with(app_sessionmaker, tenant_id=tenant_a, seed=mine, pins=pins)
    ordered = sorted(ids)
    diffs = sorted(a for a, (_n, role) in zip(ids, pins) if role == "diff")
    base = _artifacts_path(mine["project_id"], run_id)
    with _client(app_engine, tenant_id=tenant_a, user_id=mine["user_id"]) as client:
        first = client.get(base + "?limit=2").json()
        assert [i["artifactId"] for i in first["items"]] == ordered[:2] and first["count"] == 2
        assert first["nextCursor"] == ordered[1]
        second = client.get(base + f"?limit=2&cursor={first['nextCursor']}").json()
        assert [i["artifactId"] for i in second["items"]] == ordered[2:4] and second["nextCursor"] == ordered[3]
        third = client.get(base + f"?limit=2&cursor={second['nextCursor']}").json()
        assert [i["artifactId"] for i in third["items"]] == ordered[4:] and third["nextCursor"] is None
        walked = [i["artifactId"] for page in (first, second, third) for i in page["items"]]
        assert walked == ordered and len(set(walked)) == 5                  # exactly once each
        # role filter across a page boundary: three diffs, one per page
        page, cursor, seen = None, None, []
        for _ in range(3):
            page = client.get(base + "?role=diff&limit=1" + (f"&cursor={cursor}" if cursor else "")).json()
            assert page["role"] == "diff" and [i["role"] for i in page["items"]] == ["diff"]
            seen += [i["artifactId"] for i in page["items"]]
            cursor = page["nextCursor"]
        assert seen == diffs and cursor is None
        _canonical(client.get(base + "?limit=201"), code="VAL-0003", status=422)
        _canonical(client.get(base + "?limit=0"), code="VAL-0003", status=422)
        _canonical(client.get(base + "?cursor=not-an-id"), code="VAL-0003", status=422)
        _canonical(client.get(base + "?limit=1&limit=2"), code="VAL-0003", status=422)
        # a cursor past the last id is an empty last page, not an error
        empty = client.get(base + f"?cursor={ordered[-1]}").json()
        assert empty["items"] == [] and empty["count"] == 0 and empty["nextCursor"] is None


def test_verify_reports_the_truth_after_the_object_changes_and_the_record_stays(
    owner_engine, app_engine, app_sessionmaker, two_tenants, clean_tables
):
    tenant_a, _ = two_tenants
    with owner_engine.begin() as connection:
        mine = _seed_project(connection, tenant_id=tenant_a, code="mine")
    run_id, record_id, diff, trace = _sealed_with_pins(app_sessionmaker, tenant_id=tenant_a, seed=mine)

    with _client(app_engine, tenant_id=tenant_a, user_id=mine["user_id"]) as client:
        before = client.get(_verify_path(mine["project_id"], run_id, diff)).json()
        assert before == {"recordId": record_id, "runId": run_id, "artifactId": diff, "verified": True,
                          "pinnedChecksumSha256": "b" * 64}
        with owner_engine.begin() as connection:              # the object changes after sealing
            connection.execute(text("UPDATE artifacts SET checksum_sha256 = :c WHERE artifact_id = :a"),
                               {"c": "d" * 64, "a": diff})
        after = client.get(_verify_path(mine["project_id"], run_id, diff))
        assert after.status_code == 200 and after.json()["verified"] is False
        assert after.json()["pinnedChecksumSha256"] == "b" * 64     # the record is the account of what was true
        still = client.get(_artifacts_path(mine["project_id"], run_id, "diff")).json()
        assert still["items"][0]["checksumSha256"] == "b" * 64
        # Not pinned to this record: a real artifact of the run that was never pinned, and a foreign id.
        with app_sessionmaker() as session:
            with session.begin():
                with tenant_scope(session, tenant_a):
                    loose = _verified_artifact(session, tenant_id=tenant_a, run_id=run_id, name="loose.bin")
        _canonical(client.get(_verify_path(mine["project_id"], run_id, loose)), code="RES-0004", status=404)
        _canonical(client.get(_verify_path(mine["project_id"], run_id, new_id("artifact"))), code="RES-0004", status=404)


def test_another_tenants_pins_are_invisible_under_rls(owner_engine, app_engine, app_sessionmaker, two_tenants, clean_tables):
    tenant_a, tenant_b = two_tenants
    with owner_engine.begin() as connection:
        theirs = _seed_project(connection, tenant_id=tenant_b, code="theirs")
        mine = _seed_project(connection, tenant_id=tenant_a, code="mine")
    their_run, their_record, their_diff, _ = _sealed_with_pins(app_sessionmaker, tenant_id=tenant_b, seed=theirs)
    with _client(app_engine, tenant_id=tenant_a, user_id=mine["user_id"]) as client:
        _canonical(client.get(_artifacts_path(theirs["project_id"], their_run)), code="AUTH-0030", status=403)
        body = _canonical(client.get(_artifacts_path(mine["project_id"], their_run)), code="RES-0004", status=404)
        assert their_diff not in str(body)
        _canonical(client.get(_verify_path(mine["project_id"], their_run, their_diff)), code="RES-0004", status=404)
