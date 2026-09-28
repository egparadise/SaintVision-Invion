"""Card 84 on a real PostgreSQL: every write route ends within the budget when its lock is held.

For each write route in the business lane an *independent* connection holds
the lock the route needs -- the idempotency advisory lock (the same key the
route derives) or the resource row ``FOR UPDATE`` -- and the route is called
with a short budget. It must answer ``SYS-0001/503/retryable=true`` within a
bounded wall-clock time and write nothing. Revert the bound and the request
waits on the held lock until the test's own deadline kills it.
"""

from __future__ import annotations

import datetime as dt
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from saintvision.api.app import create_app
from saintvision.api.deps import get_principal, serialise_idempotent_write
from saintvision.api.problem import CANONICAL_KEYS
from saintvision.api.v1 import model_retention, model_versions, run_seal
from saintvision.config import Settings
from saintvision.db.session import tenant_scope
from saintvision.identity.principal import Principal, StaticPrincipalVerifier
from saintvision.ids import new_id
from test_model_release_real_pg import DECLARATION, _observation
from test_model_release_real_pg import _seed as _seed_releasable
from test_model_version_register_real_pg import _body as _register_body
from test_model_version_register_real_pg import _digest, _insert, _seed
from test_run_record_real_pg import NOW, _seed_project
from test_run_seal_real_pg import _prepare as _prepare_run

pytestmark = pytest.mark.postgres

BUDGET_MS = 300
#: The test's own deadline for a request: far above the budget, far below a
#: default lock wait (which is forever). A reverted bound fails here.
DEADLINE_SECONDS = 20
UTC = dt.timezone.utc
TOKEN = "lock-wait-token"


def _client(app_engine, *, tenant_id, user_id, observation=None):
    principal = Principal(user_id=user_id, tenant_id=tenant_id, external_subject="synthetic-lock-wait")
    app = create_app(
        engine=app_engine,
        settings=Settings(
            database_url="test-only", idempotency_ttl_seconds=600,
            business_lock_timeout_ms=BUDGET_MS, kernel_base_url="http://kernel.invalid",
        ),
        verifier=StaticPrincipalVerifier({}, allow_outside_dev=True),
        clock=lambda: NOW,
        check_partitions_on_startup=False,
    )
    app.dependency_overrides[get_principal] = lambda: principal
    if observation is not None:
        app.state.model_commitment_fetcher = lambda **_kwargs: observation
    return TestClient(app, raise_server_exceptions=False)


def _canonical_503(response):
    assert response.status_code == 503, response.text
    body = response.json()
    assert set(body) == set(CANONICAL_KEYS), body
    assert body["code"] == "SYS-0001" and body["retryable"] is True
    for forbidden in ("55P03", "40P01", "SELECT", "pg_advisory"):
        assert forbidden not in body["detail"]
    return body


def _within_deadline(call):
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=1) as pool:
        response = pool.submit(call).result(timeout=DEADLINE_SECONDS)
    return response, time.monotonic() - started


class _Held:
    """An independent transaction holding one lock until closed."""

    def __init__(self, engine):
        self.connection = engine.connect()
        self.tx = self.connection.begin()

    def row(self, table, column, value):
        self.connection.execute(text(f"SELECT 1 FROM {table} WHERE {column} = :v FOR UPDATE"), {"v": value})
        return self

    def advisory(self, *, tenant_id, endpoint, key, project_id):
        session = sessionmaker(bind=self.connection)()
        serialise_idempotent_write(session, tenant_id=tenant_id, endpoint=endpoint, idempotency_key=key, project_id=project_id)
        return self

    def close(self):
        self.tx.rollback()
        self.connection.close()


def _approver(connection, tenant, label):
    seeded = _seed(connection, tenant_id=tenant, now=NOW, label=label, role="approver")
    return seeded


# ---------------------------------------------------------------- W2 register


def test_w2_register_ends_within_the_budget_when_the_idempotency_key_is_held(owner_engine, app_engine, two_tenants, clean_tables):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seeded = _approver(connection, tenant, "lw-w2-key")
    held = _Held(owner_engine).advisory(tenant_id=tenant, endpoint=model_versions.ENDPOINT, key="k-held", project_id=seeded["project_id"])
    try:
        client = _client(app_engine, tenant_id=tenant, user_id=seeded["user_id"])
        response, elapsed = _within_deadline(lambda: client.post(
            f"/v1/projects/{seeded['project_id']}/models/{seeded['model_id']}/versions",
            json=_register_body(), headers={"Idempotency-Key": "k-held", "Content-Type": "application/json"},
        ))
    finally:
        held.close()
    _canonical_503(response)
    assert elapsed < DEADLINE_SECONDS
    with owner_engine.begin() as connection:
        assert connection.execute(text("SELECT count(*) FROM model_versions WHERE tenant_id = :t"), {"t": tenant}).scalar_one() == 0
        assert connection.execute(text("SELECT count(*) FROM idempotency_records WHERE tenant_id = :t"), {"t": tenant}).scalar_one() == 0


# ---------------------------------------------------------------- W4 retention pin


def _version_row(connection, *, tenant, model_id):
    version_id = new_id("model_version")
    _insert(
        connection, "model_versions",
        model_version_id=version_id, tenant_id=tenant, model_id=model_id, version="1.0.0", stage="draft",
        content_sha256=_digest(), byte_size=1, uri="inv://models/demo@1.0.0",
        retention_pinned_until=dt.datetime(2027, 1, 1, tzinfo=UTC), created_at=NOW,
    )
    return version_id


def test_w4_pin_ends_within_the_budget_when_the_version_row_is_held(owner_engine, app_engine, two_tenants, clean_tables):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seeded = _approver(connection, tenant, "lw-w4-row")
        version_id = _version_row(connection, tenant=tenant, model_id=seeded["model_id"])
    held = _Held(owner_engine).row("model_versions", "model_version_id", version_id)
    try:
        client = _client(app_engine, tenant_id=tenant, user_id=seeded["user_id"])
        response, elapsed = _within_deadline(lambda: client.post(
            f"/v1/projects/{seeded['project_id']}/models/{seeded['model_id']}/versions/1.0.0/retention-pin",
            json={"until": "2028-01-01T00:00:00+00:00"}, headers={"Idempotency-Key": "k-w4", "Content-Type": "application/json"},
        ))
    finally:
        held.close()
    _canonical_503(response)
    assert elapsed < DEADLINE_SECONDS
    with owner_engine.begin() as connection:
        until = connection.execute(text("SELECT retention_pinned_until FROM model_versions WHERE model_version_id = :v"), {"v": version_id}).scalar_one()
    assert until == dt.datetime(2027, 1, 1, tzinfo=UTC)


def test_w4_pin_ends_within_the_budget_when_the_idempotency_key_is_held(owner_engine, app_engine, two_tenants, clean_tables):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seeded = _approver(connection, tenant, "lw-w4-key")
        _version_row(connection, tenant=tenant, model_id=seeded["model_id"])
    held = _Held(owner_engine).advisory(tenant_id=tenant, endpoint=model_retention.ENDPOINT, key="k-w4-held", project_id=seeded["project_id"])
    try:
        client = _client(app_engine, tenant_id=tenant, user_id=seeded["user_id"])
        response, elapsed = _within_deadline(lambda: client.post(
            f"/v1/projects/{seeded['project_id']}/models/{seeded['model_id']}/versions/1.0.0/retention-pin",
            json={"until": "2028-01-01T00:00:00+00:00"}, headers={"Idempotency-Key": "k-w4-held", "Content-Type": "application/json"},
        ))
    finally:
        held.close()
    _canonical_503(response)
    assert elapsed < DEADLINE_SECONDS


# ---------------------------------------------------------------- W1 seal


def test_w1_seal_ends_within_the_budget_when_the_run_row_is_held(owner_engine, app_engine, app_sessionmaker, two_tenants, clean_tables):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seed = _seed_project(connection, tenant_id=tenant, code="lw-w1")
        connection.execute(text("UPDATE project_members SET role_code = 'approver' WHERE user_id = :u"), {"u": seed["user_id"]})
    run_id, _, _ = _prepare_run(app_sessionmaker, tenant_id=tenant, seed=seed)
    held = _Held(owner_engine).row("runs", "run_id", run_id)
    try:
        client = _client(app_engine, tenant_id=tenant, user_id=seed["user_id"])
        response, elapsed = _within_deadline(lambda: client.post(
            f"/v1/projects/{seed['project_id']}/runs/{run_id}/record",
            json={}, headers={"Idempotency-Key": "k-w1", "Content-Type": "application/json"},
        ))
    finally:
        held.close()
    _canonical_503(response)
    assert elapsed < DEADLINE_SECONDS
    with owner_engine.begin() as connection:
        assert connection.execute(text("SELECT count(*) FROM run_records WHERE run_id = :r"), {"r": run_id}).scalar_one() == 0


def test_w1_seal_ends_within_the_budget_when_the_idempotency_key_is_held(owner_engine, app_engine, app_sessionmaker, two_tenants, clean_tables):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seed = _seed_project(connection, tenant_id=tenant, code="lw-w1k")
        connection.execute(text("UPDATE project_members SET role_code = 'approver' WHERE user_id = :u"), {"u": seed["user_id"]})
    run_id, _, _ = _prepare_run(app_sessionmaker, tenant_id=tenant, seed=seed)
    held = _Held(owner_engine).advisory(tenant_id=tenant, endpoint=run_seal.ENDPOINT, key="k-w1-held", project_id=seed["project_id"])
    try:
        client = _client(app_engine, tenant_id=tenant, user_id=seed["user_id"])
        response, elapsed = _within_deadline(lambda: client.post(
            f"/v1/projects/{seed['project_id']}/runs/{run_id}/record",
            json={}, headers={"Idempotency-Key": "k-w1-held", "Content-Type": "application/json"},
        ))
    finally:
        held.close()
    _canonical_503(response)
    assert elapsed < DEADLINE_SECONDS


# ---------------------------------------------------------------- #167 release


def test_release_ends_within_the_budget_when_the_version_row_is_held(owner_engine, app_engine, two_tenants, clean_tables):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seeded = _seed_releasable(connection, tenant_id=tenant, now=NOW, project_code="lw-rel", role="approver")
    observation = _observation(seeded["project_id"], seeded["model_id"], "1.0.0")
    held = _Held(owner_engine).row("model_versions", "model_version_id", seeded["version_id"])
    try:
        client = _client(app_engine, tenant_id=tenant, user_id=seeded["user_id"], observation=observation)
        response, elapsed = _within_deadline(lambda: client.post(
            f"/v1/projects/{seeded['project_id']}/models/{seeded['model_id']}/versions/1.0.0/release",
            json=DECLARATION, headers={"Content-Type": "application/json"},
        ))
    finally:
        held.close()
    _canonical_503(response)
    assert elapsed < DEADLINE_SECONDS
    with owner_engine.begin() as connection:
        stage = connection.execute(text("SELECT stage FROM model_versions WHERE model_version_id = :v"), {"v": seeded["version_id"]}).scalar_one()
    assert stage == "draft"


# ---------------------------------------------------------------- the bound is the session's, not the connection's


def test_the_bound_is_local_to_the_transaction_and_the_next_write_proceeds(owner_engine, app_engine, two_tenants, clean_tables):
    """After a refused wait the same application engine serves a normal write:
    SET LOCAL did not leak a tiny lock_timeout into the pool's connection."""
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seeded = _approver(connection, tenant, "lw-local")
    held = _Held(owner_engine).advisory(tenant_id=tenant, endpoint=model_versions.ENDPOINT, key="k-local", project_id=seeded["project_id"])
    client = _client(app_engine, tenant_id=tenant, user_id=seeded["user_id"])
    try:
        _canonical_503(client.post(
            f"/v1/projects/{seeded['project_id']}/models/{seeded['model_id']}/versions",
            json=_register_body(), headers={"Idempotency-Key": "k-local", "Content-Type": "application/json"},
        ))
    finally:
        held.close()
    ok = client.post(
        f"/v1/projects/{seeded['project_id']}/models/{seeded['model_id']}/versions",
        json=_register_body(), headers={"Idempotency-Key": "k-local-2", "Content-Type": "application/json"},
    )
    assert ok.status_code == 201, ok.text
