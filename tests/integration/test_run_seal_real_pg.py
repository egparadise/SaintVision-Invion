"""W1 against a real PostgreSQL: the §5-2 seal contract with independent sessions.

Nothing here is claimed by the PG-free file. The contention cases use an
independent connection holding the run row (as the owner, outside RLS), the
request in a thread, and PostgreSQL's own lock-wait state as the barrier, or
two requests released together at the serialisation point.

Design §5-2 kill list: (a) the same intent twice at once -> one record, one
pin set, both succeed; (b) two different intents at once -> one winner, one
409, no partial pins; (c) a terminal transition racing the seal -> the seal
waits and seals the committed final state; (d) a revocation during the wait ->
403 after the lock, nothing written, one denial row.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from saintvision.api.app import create_app
from saintvision.api.deps import get_principal
from saintvision.api.v1 import run_seal
from saintvision.config import Settings
from saintvision.db.session import tenant_scope
from saintvision.identity.principal import Principal, StaticPrincipalVerifier
from saintvision.ids import new_id
from saintvision.services import runs as run_service
from test_run_record_real_pg import NOW, _canonical, _seed_project

pytestmark = pytest.mark.postgres


def _verified_artifact(session, *, tenant_id, run_id, name, checksum):
    """An active, verified artifact of the run (the sealable kind)."""
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


def _client(app_engine, *, tenant_id, user_id, authenticate=True, lock_timeout_ms=5_000):
    app = create_app(
        engine=app_engine,
        settings=Settings(database_url="test-only", idempotency_ttl_seconds=600, business_lock_timeout_ms=lock_timeout_ms),
        verifier=StaticPrincipalVerifier({}, allow_outside_dev=True),
        clock=lambda: NOW,
        check_partitions_on_startup=False,
    )
    if authenticate:
        app.dependency_overrides[get_principal] = lambda: Principal(
            user_id=user_id, tenant_id=tenant_id, external_subject="synthetic-seal"
        )
    return TestClient(app, raise_server_exceptions=False)


def _run_to(session, *, tenant_id, seed, terminal=True):
    """A run at ``verifying`` (or finished), with two verified artifacts and one staging."""
    run = run_service.create_run(
        session, tenant_id=tenant_id, workload_id=seed["workload_id"],
        workspace_id=seed["workspace_id"], requested_by_user_id=seed["user_id"], now=NOW,
    )
    for target in ("validated", "planned", "scheduled"):
        run_service.advance(session, tenant_id=tenant_id, run_id=run.run_id, target=target, now=NOW)
    run_service.start_attempt(session, tenant_id=tenant_id, run_id=run.run_id, now=NOW)
    run_service.advance(session, tenant_id=tenant_id, run_id=run.run_id, target="verifying", now=NOW)
    if terminal:
        _complete(session, tenant_id=tenant_id, run_id=run.run_id)
    a = _verified_artifact(session, tenant_id=tenant_id, run_id=run.run_id, name="changes.patch", checksum="1" * 64)
    b = _verified_artifact(session, tenant_id=tenant_id, run_id=run.run_id, name="otel.json", checksum="2" * 64)
    staging = new_id("artifact")
    session.execute(
        text(
            "INSERT INTO artifacts (artifact_id, tenant_id, run_id, name, media_type, status, byte_size, created_at, version) "
            "VALUES (:a, :t, :r, 'draft.bin', 'application/octet-stream', 'staging', 3, now(), 1)"
        ),
        {"a": staging, "t": tenant_id, "r": run.run_id},
    )
    return run.run_id, sorted([a, b]), staging


def _complete(session, *, tenant_id, run_id):
    run_service.complete_run(
        session, tenant_id=tenant_id, run_id=run_id, now=NOW, actor_type="system",
        actor_id="control-plane", action="run.complete", input_schema="RunInput@1",
        input_payload={"objective": "train"}, output_ref=f"inv://artifacts/{run_id}/art_x",
    )


def _prepare(app_sessionmaker, *, tenant_id, seed, terminal=True):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, tenant_id):
                return _run_to(session, tenant_id=tenant_id, seed=seed, terminal=terminal)


def _path(project_id, run_id):
    return f"/v1/projects/{project_id}/runs/{run_id}/record"


def _headers(key):
    return {"Idempotency-Key": key, "Content-Type": "application/json"}


def _records(owner_engine, run_id):
    with owner_engine.begin() as connection:
        records = connection.execute(
            text("SELECT record_id, final_state, termination_reason, bundle_id FROM run_records WHERE run_id = :r"), {"r": run_id}
        ).mappings().all()
        pins = connection.execute(
            text("SELECT ra.artifact_id, ra.role, ra.checksum_sha256 FROM run_record_artifacts ra "
                 "JOIN run_records r ON r.record_id = ra.record_id WHERE r.run_id = :r ORDER BY ra.artifact_id"),
            {"r": run_id},
        ).mappings().all()
    return records, pins


def _ledger(owner_engine, tenant_id):
    with owner_engine.begin() as connection:
        return connection.execute(
            text("SELECT idempotency_key, response_status FROM idempotency_records WHERE tenant_id = :t ORDER BY idempotency_key"),
            {"t": tenant_id},
        ).mappings().all()


def _denials(owner_engine):
    with owner_engine.begin() as connection:
        return connection.execute(
            text("SELECT actor_type, actor_id, reason_code, action, target_id FROM audit_events WHERE outcome = 'deny' ORDER BY occurred_at")
        ).mappings().all()


def _wait_until_blocked(owner_engine, *, timeout=30.0):
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with owner_engine.begin() as connection:
            waiting = connection.execute(
                text("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
                     "AND wait_event_type = 'Lock' AND pid <> pg_backend_pid()")
            ).scalar_one()
        if waiting:
            return
        time.sleep(0.05)
    raise AssertionError("the request never blocked on the row lock")


def _hold_run(owner_engine, run_id):
    connection = owner_engine.connect()
    tx = connection.begin()
    connection.execute(text("SELECT run_id FROM runs WHERE run_id = :r FOR UPDATE"), {"r": run_id})
    return connection, tx


# ---------------------------------------------------------------- the plain rules


def test_an_approver_seals_the_servers_set_with_the_requested_roles_and_replays_exactly(
    owner_engine, app_engine, app_sessionmaker, two_tenants, clean_tables
):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seed = _seed_project(connection, tenant_id=tenant, code="w1-1")
        connection.execute(text("UPDATE project_members SET role_code = 'approver' WHERE user_id = :u"), {"u": seed["user_id"]})
    run_id, (a, b), staging = _prepare(app_sessionmaker, tenant_id=tenant, seed=seed)
    client = _client(app_engine, tenant_id=tenant, user_id=seed["user_id"])

    response = client.post(_path(seed["project_id"], run_id), json={"roles": {a: "diff"}}, headers=_headers("k-1"))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["runId"] == run_id and body["finalState"] == "succeeded" and body["terminationReason"] == "completed"
    records, pins = _records(owner_engine, run_id)
    assert len(records) == 1 and records[0]["record_id"] == body["recordId"]
    assert [(p["artifact_id"], p["role"]) for p in pins] == [(a, "diff"), (b, "other")]
    assert staging not in [p["artifact_id"] for p in pins]
    assert [(p["checksum_sha256"]) for p in pins] == ["1" * 64, "2" * 64]
    # exact replay
    again = client.post(_path(seed["project_id"], run_id), json={"roles": {a: "diff"}}, headers=_headers("k-1"))
    assert again.status_code == 200 and again.json() == body
    assert len(_ledger(owner_engine, tenant)) == 1
    # same key, different request -> 409; different key, same intent -> natural idempotent success
    _canonical(client.post(_path(seed["project_id"], run_id), json={"roles": {a: "trace"}}, headers=_headers("k-1")), code="GRAPH-0002", status=409)
    same = client.post(_path(seed["project_id"], run_id), json={"roles": {a: "diff"}}, headers=_headers("k-2"))
    assert same.status_code == 200 and same.json()["recordId"] == body["recordId"]
    # different key, different intent -> 409, nothing rewritten
    _canonical(client.post(_path(seed["project_id"], run_id), json={"roles": {a: "trace"}}, headers=_headers("k-3")), code="GRAPH-0002", status=409)
    assert _records(owner_engine, run_id) == (records, pins)
    # a mapping outside the server's set (the staging artifact) is refused
    _canonical(client.post(_path(seed["project_id"], run_id), json={"roles": {staging: "log"}}, headers=_headers("k-4")), code="GRAPH-0002", status=409)


def test_an_unfinished_run_is_409_and_a_member_without_the_grade_is_403(owner_engine, app_engine, app_sessionmaker, two_tenants, clean_tables):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seed = _seed_project(connection, tenant_id=tenant, code="w1-2")          # operator: canRequest, not canApprove
        approver = _seed_project(connection, tenant_id=tenant, code="w1-2b")
        connection.execute(text("UPDATE project_members SET role_code = 'approver' WHERE user_id = :u"), {"u": approver["user_id"]})
    run_id, _, _ = _prepare(app_sessionmaker, tenant_id=tenant, seed=approver, terminal=False)
    with _client(app_engine, tenant_id=tenant, user_id=approver["user_id"]) as client:
        body = _canonical(client.post(_path(approver["project_id"], run_id), json={}, headers=_headers("k-u")), code="GRAPH-0002", status=409)
        assert body["detail"] == "Only a finished run can be sealed."
    with _client(app_engine, tenant_id=tenant, user_id=seed["user_id"]) as client:
        _canonical(client.post(_path(seed["project_id"], run_id), json={}, headers=_headers("k-o")), code="AUTH-0030", status=403)
    assert _records(owner_engine, run_id) == ([], []) and _ledger(owner_engine, tenant) == []


# ---------------------------------------------------------------- contention (design §5-2)


def test_a_the_same_intent_twice_at_once_produces_one_record_and_both_succeed(owner_engine, app_engine, app_sessionmaker, two_tenants, clean_tables, monkeypatch):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seed = _seed_project(connection, tenant_id=tenant, code="w1-a")
        connection.execute(text("UPDATE project_members SET role_code = 'approver' WHERE user_id = :u"), {"u": seed["user_id"]})
    run_id, (a, b), _ = _prepare(app_sessionmaker, tenant_id=tenant, seed=seed)
    barrier = threading.Barrier(2, timeout=60)
    real = run_seal.serialise_idempotent_write

    def together(session, **kwargs):
        barrier.wait()                       # different keys: both pass the serialisation point, then meet at the run lock
        return real(session, **kwargs)

    monkeypatch.setattr(run_seal, "serialise_idempotent_write", together)

    def send(key):
        client = _client(app_engine, tenant_id=tenant, user_id=seed["user_id"], lock_timeout_ms=60_000)
        return client.post(_path(seed["project_id"], run_id), json={"roles": {a: "diff"}}, headers=_headers(key))

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = [f.result(timeout=90) for f in [pool.submit(send, "k-a1"), pool.submit(send, "k-a2")]]
    assert sorted(r.status_code for r in responses) == [200, 200], [r.text for r in responses]
    assert responses[0].json() == responses[1].json()
    records, pins = _records(owner_engine, run_id)
    assert len(records) == 1 and [(p["artifact_id"], p["role"]) for p in pins] == [(a, "diff"), (b, "other")]
    assert len(_ledger(owner_engine, tenant)) == 2


def test_b_two_different_intents_at_once_have_one_winner_one_409_and_no_partial_pins(owner_engine, app_engine, app_sessionmaker, two_tenants, clean_tables, monkeypatch):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seed = _seed_project(connection, tenant_id=tenant, code="w1-b")
        connection.execute(text("UPDATE project_members SET role_code = 'approver' WHERE user_id = :u"), {"u": seed["user_id"]})
    run_id, (a, b), _ = _prepare(app_sessionmaker, tenant_id=tenant, seed=seed)
    barrier = threading.Barrier(2, timeout=60)
    real = run_seal.serialise_idempotent_write

    def together(session, **kwargs):
        barrier.wait()
        return real(session, **kwargs)

    monkeypatch.setattr(run_seal, "serialise_idempotent_write", together)

    def send(key, role):
        client = _client(app_engine, tenant_id=tenant, user_id=seed["user_id"], lock_timeout_ms=60_000)
        return client.post(_path(seed["project_id"], run_id), json={"roles": {a: role}}, headers=_headers(key))

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = [f.result(timeout=90) for f in [pool.submit(send, "k-b1", "diff"), pool.submit(send, "k-b2", "trace")]]
    statuses = sorted(r.status_code for r in responses)
    assert statuses == [200, 409], [r.text for r in responses]
    winner = next(r for r in responses if r.status_code == 200)
    records, pins = _records(owner_engine, run_id)
    assert len(records) == 1 and records[0]["record_id"] == winner.json()["recordId"]
    roles = {p["artifact_id"]: p["role"] for p in pins}
    assert roles[b] == "other" and roles[a] in ("diff", "trace") and len(pins) == 2       # the winner's set, whole
    assert len(_ledger(owner_engine, tenant)) == 1                                            # the loser left no ledger row


def test_c_a_terminal_transition_racing_the_seal_is_waited_for_and_the_final_state_is_sealed(owner_engine, app_engine, app_sessionmaker, two_tenants, clean_tables):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seed = _seed_project(connection, tenant_id=tenant, code="w1-c")
        connection.execute(text("UPDATE project_members SET role_code = 'approver' WHERE user_id = :u"), {"u": seed["user_id"]})
    run_id, (a, b), _ = _prepare(app_sessionmaker, tenant_id=tenant, seed=seed, terminal=False)
    holder, tx = _hold_run(owner_engine, run_id)
    try:
        def send():
            client = _client(app_engine, tenant_id=tenant, user_id=seed["user_id"], lock_timeout_ms=60_000)
            return client.post(_path(seed["project_id"], run_id), json={"roles": {a: "diff"}}, headers=_headers("k-c"))

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(send)
            _wait_until_blocked(owner_engine)
            # the transition commits under the lock the seal is waiting for
            holder.execute(
                text("UPDATE runs SET state = 'succeeded', termination_reason = 'completed', ended_at = now() WHERE run_id = :r"),
                {"r": run_id},
            )
            tx.commit()
            response = future.result(timeout=90)
    finally:
        holder.close()
    assert response.status_code == 200, response.text
    assert response.json()["finalState"] == "succeeded" and response.json()["terminationReason"] == "completed"
    records, pins = _records(owner_engine, run_id)
    assert records[0]["final_state"] == "succeeded" and len(pins) == 2


def test_d_a_revocation_during_the_lock_wait_is_403_after_the_lock_with_nothing_written_and_one_denial(owner_engine, app_engine, app_sessionmaker, two_tenants, clean_tables):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seed = _seed_project(connection, tenant_id=tenant, code="w1-d")
        connection.execute(text("UPDATE project_members SET role_code = 'approver' WHERE user_id = :u"), {"u": seed["user_id"]})
    run_id, _, _ = _prepare(app_sessionmaker, tenant_id=tenant, seed=seed)
    holder, tx = _hold_run(owner_engine, run_id)
    try:
        def send():
            client = _client(app_engine, tenant_id=tenant, user_id=seed["user_id"], lock_timeout_ms=60_000)
            return client.post(_path(seed["project_id"], run_id), json={}, headers=_headers("k-d"))

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(send)
            _wait_until_blocked(owner_engine)
            holder.execute(
                text("DELETE FROM project_members WHERE tenant_id = :t AND project_id = :p AND user_id = :u"),
                {"t": tenant, "p": seed["project_id"], "u": seed["user_id"]},
            )
            tx.commit()
            response = future.result(timeout=90)
    finally:
        holder.close()
    _canonical(response, code="AUTH-0030", status=403)
    assert _records(owner_engine, run_id) == ([], []) and _ledger(owner_engine, tenant) == []
    rows = _denials(owner_engine)
    assert len(rows) == 1 and rows[0]["actor_id"] == seed["user_id"] and rows[0]["reason_code"] == "AUTH-0030"
    assert rows[0]["action"] == "POST /v1/projects/{project_id}/runs/{run_id}/record" and rows[0]["target_id"] == seed["project_id"]


def test_a_wait_past_the_budget_is_a_retryable_503_with_nothing_written(owner_engine, app_engine, app_sessionmaker, two_tenants, clean_tables):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seed = _seed_project(connection, tenant_id=tenant, code="w1-t")
        connection.execute(text("UPDATE project_members SET role_code = 'approver' WHERE user_id = :u"), {"u": seed["user_id"]})
    run_id, _, _ = _prepare(app_sessionmaker, tenant_id=tenant, seed=seed)
    holder, tx = _hold_run(owner_engine, run_id)
    try:
        client = _client(app_engine, tenant_id=tenant, user_id=seed["user_id"], lock_timeout_ms=300)
        response = client.post(_path(seed["project_id"], run_id), json={}, headers=_headers("k-t"))
    finally:
        tx.rollback()
        holder.close()
    body = _canonical(response, code="SYS-0001", status=503)
    assert body["retryable"] is True and run_id not in body["detail"]
    assert _records(owner_engine, run_id) == ([], []) and _ledger(owner_engine, tenant) == []


def test_without_a_credential_the_seal_is_401_with_one_anonymous_denial_and_nothing_written(owner_engine, app_engine, app_sessionmaker, two_tenants, clean_tables):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seed = _seed_project(connection, tenant_id=tenant, code="w1-anon")
    run_id, _, _ = _prepare(app_sessionmaker, tenant_id=tenant, seed=seed)
    client = _client(app_engine, tenant_id=tenant, user_id=seed["user_id"], authenticate=False)
    response = client.post(_path(seed["project_id"], run_id), json={}, headers=_headers("k-anon"))
    assert response.status_code == 401 and response.headers.get("www-authenticate") == "Bearer"
    rows = _denials(owner_engine)
    assert len(rows) == 1 and rows[0]["actor_type"] == "anonymous"
    assert rows[0]["action"] == "POST /v1/projects/{project_id}/runs/{run_id}/record"
    assert _records(owner_engine, run_id) == ([], [])
