"""W4 against a real PostgreSQL: the §5-3 lock contract, with independent sessions.

A mock session cannot lose an update, so nothing here is claimed by the
PG-free file. Each contention case holds the ``model_versions`` row from an
*independent* connection (as the owner, outside RLS), sends the request from
a thread, waits until PostgreSQL reports that backend blocked on a lock, then
commits the holder -- so the request really waited and really read the
committed row afterwards.

Expected outcomes are the design table: pin after release extends the
released row; two extensions end at ``max(old, a, b)`` whichever commits
first; a shorter ``until`` is a 200 no-op; a wait past the budget is
``SYS-0001/503/retryable`` with nothing written.
"""

from __future__ import annotations

import datetime as dt
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from saintvision.api.app import create_app
from saintvision.api.deps import get_principal
from saintvision.api.v1 import model_retention
from saintvision.config import Settings
from saintvision.identity.principal import Principal, StaticPrincipalVerifier
from saintvision.db.session import make_session_factory, tenant_scope
from saintvision.ids import new_id
from saintvision.services.lineage import release_model_version
from measurement_support import insert_measurement
from test_model_release_real_pg import _seed as _seed_releasable
from test_model_version_register_real_pg import _canonical, _digest, _insert, _ledger, _seed

pytestmark = pytest.mark.postgres

UTC = dt.timezone.utc
OLD = dt.datetime(2027, 1, 1, tzinfo=UTC)
A = dt.datetime(2028, 1, 1, tzinfo=UTC)
B = dt.datetime(2029, 1, 1, tzinfo=UTC)
SHORTER = dt.datetime(2026, 12, 1, tzinfo=UTC)


def _version(connection, *, tenant_id, model_id, now, pinned_until=OLD, verified=False):
    version_id = new_id("model_version")
    digest = _digest()
    # Verified means bound to a kernel-recorded measurement (0054, #213): the
    # seed records one first, as the kernel would, or the CHECK refuses the row.
    measurement_id = (
        insert_measurement(connection, tenant_id=tenant_id, model_version_id=version_id, sha256=digest, byte_size=4096)
        if verified else None
    )
    _insert(
        connection,
        "model_versions",
        model_version_id=version_id,
        tenant_id=tenant_id,
        model_id=model_id,
        version="1.0.0",
        stage="draft",
        content_sha256=digest,
        byte_size=4096,
        uri="inv://models/demo@1.0.0",
        verified_at=now if verified else None,
        verified_measurement_id=measurement_id,
        retention_pinned_until=pinned_until,
        created_at=now,
    )
    return version_id


def _client(app_engine, *, tenant_id, user_id, now, authenticate=True, lock_timeout_ms=5_000):
    app = create_app(
        engine=app_engine,
        settings=Settings(database_url="test-only", idempotency_ttl_seconds=600, business_lock_timeout_ms=lock_timeout_ms),
        verifier=StaticPrincipalVerifier({}, allow_outside_dev=True),
        clock=lambda: now,
        check_partitions_on_startup=False,
    )
    if authenticate:
        app.dependency_overrides[get_principal] = lambda: Principal(
            user_id=user_id, tenant_id=tenant_id, external_subject="synthetic-pin"
        )
    return TestClient(app, raise_server_exceptions=False)


def _path(seeded):
    return f"/v1/projects/{seeded['project_id']}/models/{seeded['model_id']}/versions/1.0.0/retention-pin"


def _headers(key):
    return {"Idempotency-Key": key, "Content-Type": "application/json"}


def _body(until):
    return {"until": until.isoformat()}


def _pinned_until(owner_engine, version_id):
    with owner_engine.begin() as connection:
        return connection.execute(
            text("SELECT retention_pinned_until, stage FROM model_versions WHERE model_version_id = :v"),
            {"v": version_id},
        ).one()


def _wait_until_blocked(owner_engine, *, timeout=30.0):
    """Until PostgreSQL reports a backend of this database waiting on a lock."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with owner_engine.begin() as connection:
            waiting = connection.execute(
                text(
                    "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
                    "AND wait_event_type = 'Lock' AND pid <> pg_backend_pid()"
                )
            ).scalar_one()
        if waiting:
            return
        time.sleep(0.05)
    raise AssertionError("the request never blocked on the row lock")


def _hold_row(owner_engine, version_id):
    """A raw transaction holding the row FOR UPDATE; the caller commits it."""
    connection = owner_engine.connect()
    tx = connection.begin()
    connection.execute(
        text("SELECT model_version_id FROM model_versions WHERE model_version_id = :v FOR UPDATE"),
        {"v": version_id},
    )
    return connection, tx


# ---------------------------------------------------------------- the plain rules


def test_an_approver_extends_the_pin_once_and_the_ledger_has_one_row(owner_engine, app_engine, two_tenants, frozen_now, clean_tables):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seeded = _seed(connection, tenant_id=tenant, now=frozen_now, label="w4-1", role="approver")
        version_id = _version(connection, tenant_id=tenant, model_id=seeded["model_id"], now=frozen_now)
    client = _client(app_engine, tenant_id=tenant, user_id=seeded["user_id"], now=frozen_now)

    response = client.post(_path(seeded), json=_body(A), headers=_headers("k-1"))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["modelVersionId"] == version_id and body["extended"] is True and body["stage"] == "draft"
    assert dt.datetime.fromisoformat(body["retentionPinnedUntil"].replace("Z", "+00:00")) == A
    until, _stage = _pinned_until(owner_engine, version_id)
    assert until == A
    ledger = _ledger(owner_engine, tenant)
    assert len(ledger) == 1 and ledger[0]["response_status"] == 200 and ledger[0]["endpoint"] == model_retention.ENDPOINT
    # exact replay, no second write
    again = client.post(_path(seeded), json=_body(A), headers=_headers("k-1"))
    assert again.status_code == 200 and again.json() == body
    assert len(_ledger(owner_engine, tenant)) == 1
    # same key, different request -> 409
    _canonical(client.post(_path(seeded), json=_body(B), headers=_headers("k-1")), code="GRAPH-0002", status=409)


def test_a_shorter_or_equal_until_is_a_200_no_op_that_never_shortens(owner_engine, app_engine, two_tenants, frozen_now, clean_tables):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seeded = _seed(connection, tenant_id=tenant, now=frozen_now, label="w4-2", role="approver")
        version_id = _version(connection, tenant_id=tenant, model_id=seeded["model_id"], now=frozen_now)
    client = _client(app_engine, tenant_id=tenant, user_id=seeded["user_id"], now=frozen_now)
    for key, until in (("k-shorter", SHORTER), ("k-equal", OLD)):
        response = client.post(_path(seeded), json=_body(until), headers=_headers(key))
        assert response.status_code == 200, response.text
        assert response.json()["extended"] is False
        assert dt.datetime.fromisoformat(response.json()["retentionPinnedUntil"].replace("Z", "+00:00")) == OLD
        assert _pinned_until(owner_engine, version_id)[0] == OLD
    assert len(_ledger(owner_engine, tenant)) == 2


def test_a_member_without_the_grade_and_a_sibling_project_and_another_tenant(owner_engine, app_engine, two_tenants, frozen_now, clean_tables):
    tenant_a, tenant_b = two_tenants
    with owner_engine.begin() as connection:
        operator = _seed(connection, tenant_id=tenant_a, now=frozen_now, label="w4-3a", role="operator")
        _version(connection, tenant_id=tenant_a, model_id=operator["model_id"], now=frozen_now)
        mine = _seed(connection, tenant_id=tenant_a, now=frozen_now, label="w4-3b", role="approver")
        theirs = _seed(connection, tenant_id=tenant_b, now=frozen_now, label="w4-3c", role="approver")
        _version(connection, tenant_id=tenant_b, model_id=theirs["model_id"], now=frozen_now)
    with _client(app_engine, tenant_id=tenant_a, user_id=operator["user_id"], now=frozen_now) as client:
        _canonical(client.post(_path(operator), json=_body(A), headers=_headers("k-3a")), code="AUTH-0030", status=403)
    with _client(app_engine, tenant_id=tenant_a, user_id=mine["user_id"], now=frozen_now) as client:
        # my project by path, the operator's model: the parent binds to another project -> 404
        path = f"/v1/projects/{mine['project_id']}/models/{operator['model_id']}/versions/1.0.0/retention-pin"
        _canonical(client.post(path, json=_body(A), headers=_headers("k-3b")), code="RES-0004", status=404)
        _canonical(client.post(_path(theirs), json=_body(A), headers=_headers("k-3c")), code="AUTH-0030", status=403)
    assert _ledger(owner_engine, tenant_a) == [] and _ledger(owner_engine, tenant_b) == []


# ---------------------------------------------------------------- contention (design §5-3 table)


@pytest.mark.parametrize("holder_sets,request_until,expected", [(A, B, B), (B, A, B)], ids=["holder-shorter", "holder-longer"])
def test_two_extensions_end_at_the_max_whichever_commits_first(
    owner_engine, app_engine, two_tenants, frozen_now, clean_tables, holder_sets, request_until, expected
):
    """Reverse-commit order, both ways: the request waits for the holder's
    commit, reads the committed value under its own lock, and the final value
    is ``max(old, a, b)``. Revert the lock (or read before it) and one
    direction loses an update."""
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seeded = _seed(connection, tenant_id=tenant, now=frozen_now, label="w4-4", role="approver")
        version_id = _version(connection, tenant_id=tenant, model_id=seeded["model_id"], now=frozen_now)
    holder, tx = _hold_row(owner_engine, version_id)
    try:
        def send():
            client = _client(app_engine, tenant_id=tenant, user_id=seeded["user_id"], now=frozen_now, lock_timeout_ms=60_000)
            return client.post(_path(seeded), json=_body(request_until), headers=_headers("k-4"))

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(send)
            _wait_until_blocked(owner_engine)
            holder.execute(
                text("UPDATE model_versions SET retention_pinned_until = :u WHERE model_version_id = :v"),
                {"u": holder_sets, "v": version_id},
            )
            tx.commit()
            response = future.result(timeout=90)
    finally:
        holder.close()
    assert response.status_code == 200, response.text
    assert dt.datetime.fromisoformat(response.json()["retentionPinnedUntil"].replace("Z", "+00:00")) == expected
    assert response.json()["extended"] is (expected == request_until and holder_sets < request_until)
    assert _pinned_until(owner_engine, version_id)[0] == expected == max(OLD, holder_sets, request_until)


def test_a_pin_waits_for_a_release_and_extends_the_released_row(owner_engine, app_engine, two_tenants, frozen_now, clean_tables):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seeded = _seed(connection, tenant_id=tenant, now=frozen_now, label="w4-5", role="approver")
        version_id = _version(connection, tenant_id=tenant, model_id=seeded["model_id"], now=frozen_now, verified=True)
    holder, tx = _hold_row(owner_engine, version_id)
    try:
        def send():
            client = _client(app_engine, tenant_id=tenant, user_id=seeded["user_id"], now=frozen_now, lock_timeout_ms=60_000)
            return client.post(_path(seeded), json=_body(B), headers=_headers("k-5"))

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(send)
            _wait_until_blocked(owner_engine)
            holder.execute(
                text("UPDATE model_versions SET stage = 'released' WHERE model_version_id = :v"), {"v": version_id}
            )
            tx.commit()
            response = future.result(timeout=90)
    finally:
        holder.close()
    assert response.status_code == 200, response.text
    assert response.json()["stage"] == "released" and response.json()["extended"] is True
    until, stage = _pinned_until(owner_engine, version_id)
    assert until == B and stage == "released"


def test_a_release_waits_for_a_pin_in_flight_and_then_judges_the_new_pin(
    owner_engine, app_engine, two_tenants, frozen_now, clean_tables, monkeypatch
):
    """Design §5-3, the other direction: the pin holds the row first; the
    release (the #167 write path: ``_locked_version`` then
    ``release_model_version``, in an independent application session) blocks
    on that lock, and after the pin commits it reads the *new* retention and
    releases with it intact. The pin transaction is held open from inside the
    route -- after ``pin_retention`` ran, before commit -- until PostgreSQL
    reports the release blocked."""
    from saintvision.api.v1.model_release import _locked_version

    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seeded = _seed_releasable(connection, tenant_id=tenant, now=frozen_now, project_code="w4-9", role="approver")
    version_id = seeded["version_id"]
    with owner_engine.begin() as connection:
        connection.execute(
            text("UPDATE model_versions SET retention_pinned_until = :u WHERE model_version_id = :v"),
            {"u": OLD, "v": version_id},
        )
    pin_locked = threading.Event()
    release_blocked = threading.Event()
    real_pin = model_retention.pin_retention

    def pin_then_hold(session, **kwargs):
        row = real_pin(session, **kwargs)
        pin_locked.set()                      # the row is locked and the new pin written, uncommitted
        assert release_blocked.wait(timeout=60), "the release never blocked on the pin's lock"
        return row

    monkeypatch.setattr(model_retention, "pin_retention", pin_then_hold)

    def pin():
        client = _client(app_engine, tenant_id=tenant, user_id=seeded["user_id"], now=frozen_now, lock_timeout_ms=60_000)
        return client.post(_path({"project_id": seeded["project_id"], "model_id": seeded["model_id"]}), json=_body(B), headers=_headers("k-9"))

    def release():
        factory = make_session_factory(app_engine)
        with factory() as session:
            with session.begin():
                with tenant_scope(session, tenant):
                    session.execute(text("SET LOCAL lock_timeout = '60000ms'"))
                    row = _locked_version(
                        session, tenant_id=tenant, project_id=seeded["project_id"], model_id=seeded["model_id"], version="1.0.0"
                    )
                    seen = row.retention_pinned_until
                    released = release_model_version(session, tenant_id=tenant, model_version_id=row.model_version_id, now=frozen_now)
                    return seen, released.stage, released.retention_pinned_until

    with ThreadPoolExecutor(max_workers=2) as pool:
        pin_future = pool.submit(pin)
        assert pin_locked.wait(timeout=60), "the pin never reached the service"
        release_future = pool.submit(release)
        _wait_until_blocked(owner_engine)     # the release is on the row lock the pin holds
        release_blocked.set()
        response = pin_future.result(timeout=90)
        seen, stage, kept = release_future.result(timeout=90)

    assert response.status_code == 200, response.text
    assert seen == B, "the release read the pin before it committed"
    assert stage == "released" and kept == B
    until, final_stage = _pinned_until(owner_engine, version_id)
    assert until == B and final_stage == "released"


def test_a_wait_past_the_budget_is_a_retryable_503_with_nothing_written(owner_engine, app_engine, two_tenants, frozen_now, clean_tables):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seeded = _seed(connection, tenant_id=tenant, now=frozen_now, label="w4-6", role="approver")
        version_id = _version(connection, tenant_id=tenant, model_id=seeded["model_id"], now=frozen_now)
    holder, tx = _hold_row(owner_engine, version_id)
    try:
        client = _client(app_engine, tenant_id=tenant, user_id=seeded["user_id"], now=frozen_now, lock_timeout_ms=300)
        response = client.post(_path(seeded), json=_body(A), headers=_headers("k-6"))
    finally:
        tx.rollback()
        holder.close()
    body = _canonical(response, code="SYS-0001", status=503)
    assert body["retryable"] is True and version_id not in body["detail"] and "FOR UPDATE" not in body["detail"]
    assert _pinned_until(owner_engine, version_id)[0] == OLD
    assert _ledger(owner_engine, tenant) == []
    # and the same key is free to retry
    retry = client.post(_path(seeded), json=_body(A), headers=_headers("k-6"))
    assert retry.status_code == 200 and _pinned_until(owner_engine, version_id)[0] == A


def test_two_concurrent_first_requests_with_one_key_extend_once_and_replay(owner_engine, app_engine, two_tenants, frozen_now, clean_tables, monkeypatch):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seeded = _seed(connection, tenant_id=tenant, now=frozen_now, label="w4-7", role="approver")
        version_id = _version(connection, tenant_id=tenant, model_id=seeded["model_id"], now=frozen_now)
    barrier = threading.Barrier(2, timeout=60)
    real = model_retention.serialise_idempotent_write

    def at_the_same_moment(session, **kwargs):
        barrier.wait()
        return real(session, **kwargs)

    monkeypatch.setattr(model_retention, "serialise_idempotent_write", at_the_same_moment)

    def send():
        client = _client(app_engine, tenant_id=tenant, user_id=seeded["user_id"], now=frozen_now)
        return client.post(_path(seeded), json=_body(A), headers=_headers("k-race"))

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = [f.result(timeout=90) for f in [pool.submit(send), pool.submit(send)]]
    assert sorted(r.status_code for r in responses) == [200, 200], [r.text for r in responses]
    assert responses[0].json() == responses[1].json()
    assert len(_ledger(owner_engine, tenant)) == 1 and _pinned_until(owner_engine, version_id)[0] == A


def test_a_request_without_a_credential_is_refused_and_writes_nothing(owner_engine, app_engine, two_tenants, frozen_now, clean_tables):
    """Observed, not narrowly asserted: the anonymous denial audit is the shared
    boundary (#189/#195), which this branch's base does not yet carry."""
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seeded = _seed(connection, tenant_id=tenant, now=frozen_now, label="w4-8", role="approver")
        version_id = _version(connection, tenant_id=tenant, model_id=seeded["model_id"], now=frozen_now)
    client = _client(app_engine, tenant_id=tenant, user_id=seeded["user_id"], now=frozen_now, authenticate=False)
    response = client.post(_path(seeded), json=_body(A), headers=_headers("k-anon"))
    assert response.status_code != 200, response.text
    assert _pinned_until(owner_engine, version_id)[0] == OLD and _ledger(owner_engine, tenant) == []
