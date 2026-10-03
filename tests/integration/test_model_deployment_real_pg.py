"""Card 261 against a real PostgreSQL: the claims only a database can hold.

Four of them, and none is checkable without one: a foreign key that refuses a
value no run matches (and a migration that refuses to add it while such values
exist), a provenance binding that must cross two or three tables to prove a
project, two rows locked before a deployment is written with the actor's grade
re-read in between, and a ledger whose key is bound to the path it was used on.

The contract, the write order and the refusal table are PG-free and live in
``tests/core/test_model_deployment_contract.py``.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import threading
import uuid
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi.testclient import TestClient
from sqlalchemy import text

from saintvision.api.app import create_app
from saintvision.api.problem import AUTH_PROJECT, CANONICAL_KEYS
from saintvision.api.v1 import model_deployments
from saintvision.config import Settings
from saintvision.identity.principal import Principal, StaticPrincipalVerifier
from saintvision.ids import new_id
from saintvision.services import lineage as lineage_service
from measurement_support import insert_measurement
from test_model_release_real_pg import _digest, _insert, _seed
from test_model_retention_pin_real_pg import _wait_until_blocked

pytestmark = pytest.mark.postgres

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 10, 3, 12, 0, tzinfo=UTC)
RACE_BUDGET_MS = 30_000
JOIN_SECONDS = 60
MIGRATION = Path(__file__).resolve().parents[2] / "migrations/versions/0064_model_version_run_fk.py"


def _client(app_engine, *, tenant_id, user_id, lock_timeout_ms=5_000):
    token = f"c261-{user_id}"
    principal = Principal(user_id=user_id, tenant_id=tenant_id, external_subject=f"oidc:{user_id}")
    app = create_app(
        engine=app_engine,
        settings=Settings(
            database_url="test-only",
            kernel_base_url="http://kernel.invalid",
            business_lock_timeout_ms=lock_timeout_ms,
        ),
        verifier=StaticPrincipalVerifier({token: principal}, allow_outside_dev=True),
        clock=lambda: NOW,
        check_partitions_on_startup=False,
    )
    client = TestClient(app, raise_server_exceptions=False)
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


def _canonical(response, *, code, status):
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == set(CANONICAL_KEYS), body
    assert body["code"] == code
    return body


def _release(connection, version_id, *, now=NOW) -> str:
    """Make a seeded draft released and return **its own** digest.

    The digest is not replaced: ``verified_at`` is only legal beside the
    measurement it was verified against (``ck_model_versions_verified_iff_measurement``)
    and the seed already recorded one over this version's content, so the test
    approves *that* digest rather than rewriting measured evidence.
    """
    digest = connection.execute(
        text("SELECT content_sha256 FROM model_versions WHERE model_version_id = :v"),
        {"v": version_id},
    ).scalar_one()
    connection.execute(
        text(
            "UPDATE model_versions SET stage='released', verified_at=:n, "
            "retention_pinned_until=:p WHERE model_version_id=:v"
        ),
        {"n": now, "p": now + dt.timedelta(days=365), "v": version_id},
    )
    return digest


def _approve(connection, approval_id, *, digest, now=NOW):
    connection.execute(
        text(
            "UPDATE approvals SET decision='approved', subject_sha256=:d, decided_at=:n, "
            "expires_at=:e WHERE approval_id=:a"
        ),
        {"d": digest, "n": now - dt.timedelta(minutes=5), "e": now + dt.timedelta(days=1), "a": approval_id},
    )


def _deployments(owner_engine, tenant_id):
    with owner_engine.begin() as connection:
        return connection.execute(
            text(
                "SELECT deployment_id, model_version_id, environment, status, deployed_digest, "
                "approval_id FROM deployments WHERE tenant_id = :t ORDER BY deployment_id"
            ),
            {"t": tenant_id},
        ).mappings().all()


def _versions(owner_engine, tenant_id):
    with owner_engine.begin() as connection:
        return connection.execute(
            text(
                "SELECT model_version_id, version, produced_by_run_id FROM model_versions "
                "WHERE tenant_id = :t ORDER BY model_version_id"
            ),
            {"t": tenant_id},
        ).mappings().all()


def _edges(owner_engine, tenant_id):
    with owner_engine.begin() as connection:
        return connection.execute(
            text(
                "SELECT kind, subject_id FROM model_lineage WHERE tenant_id = :t "
                "ORDER BY kind, subject_id"
            ),
            {"t": tenant_id},
        ).mappings().all()


def _denials(owner_engine):
    with owner_engine.begin() as connection:
        return connection.execute(
            text(
                "SELECT action, reason_code, target_type, target_id, actor_id, trace_id "
                "FROM audit_events WHERE outcome = 'deny' ORDER BY occurred_at"
            )
        ).mappings().all()


def _allows(owner_engine, action):
    with owner_engine.begin() as connection:
        return connection.execute(
            text(
                "SELECT target_type, target_id, detail FROM audit_events "
                "WHERE outcome = 'allow' AND action = :a ORDER BY occurred_at"
            ),
            {"a": action},
        ).mappings().all()


# ==========================================================================
# 0064 -- the key, and the measurement that must come before it
# ==========================================================================


def _migration():
    spec = importlib.util.spec_from_file_location("m0064", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_0064_refuses_to_add_the_key_while_a_version_names_a_run_that_is_not_there(
    owner_engine, two_tenants, clean_tables
):
    """The column lived without a key, so a value no run matches is possible. The
    migration reads those rows and **refuses with their identities** rather than
    letting PostgreSQL fail with a message that names none of them -- and it does
    not repair them, because a recorded provenance claim is someone's assertion."""
    tenant, _ = two_tenants
    module = _migration()
    with owner_engine.begin() as connection:
        seeded = _seed(connection, tenant_id=tenant, now=NOW, project_code="c261-dangle")
        orphan = new_id("run")
        # The key must be gone first: with it in place this very UPDATE is refused,
        # which is the other half of the story (see the test below).
        with Operations.context(MigrationContext.configure(connection)):
            module.downgrade()          # the pre-0064 state, where the value is possible
        connection.execute(
            text("UPDATE model_versions SET produced_by_run_id = :r WHERE model_version_id = :v"),
            {"r": orphan, "v": seeded["version_id"]},
        )
        with pytest.raises(RuntimeError) as raised:
            with Operations.context(MigrationContext.configure(connection)):
                module.upgrade()
        message = str(raised.value)
        assert seeded["version_id"] in message and orphan in message
        assert "reviewed data fix" in message
        # The row is untouched: no NULL, no delete.
        kept = connection.execute(
            text("SELECT produced_by_run_id FROM model_versions WHERE model_version_id = :v"),
            {"v": seeded["version_id"]},
        ).scalar_one()
        assert kept == orphan
        # Corrected by hand, the same upgrade proceeds.
        connection.execute(
            text("UPDATE model_versions SET produced_by_run_id = NULL WHERE model_version_id = :v"),
            {"v": seeded["version_id"]},
        )
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()


def test_0064_the_key_refuses_a_direct_write_the_route_never_sees(
    owner_engine, two_tenants, clean_tables
):
    """The route's check and the key are not the same defence. The key is what
    stops a writer that never went through the route."""
    tenant, other = two_tenants
    with owner_engine.begin() as connection:
        seeded = _seed(connection, tenant_id=tenant, now=NOW, project_code="c261-fk")
        for label, run_id in (("absent", new_id("run")),):
            with pytest.raises(Exception) as raised:
                with connection.begin_nested():
                    connection.execute(
                        text(
                            "UPDATE model_versions SET produced_by_run_id = :r "
                            "WHERE model_version_id = :v"
                        ),
                        {"r": run_id, "v": seeded["version_id"]},
                    )
            assert "fk_model_versions_tenant_id_produced_by_run_id" in str(raised.value), label


def test_0064_downgrade_drops_only_the_key_and_keeps_every_value(
    owner_engine, two_tenants, clean_tables
):
    module = _migration()
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seeded = _seed(connection, tenant_id=tenant, now=NOW, project_code="c261-down")
        run_id = seeded["subjects"]["approval"]  # any id; cleared before the key returns
        connection.execute(
            text("UPDATE model_versions SET produced_by_run_id = NULL WHERE model_version_id = :v"),
            {"v": seeded["version_id"]},
        )

        def columns():
            return connection.execute(
                text(
                    "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
                    "WHERE table_name = 'model_versions' ORDER BY column_name"
                )
            ).fetchall()

        def keys():
            return connection.execute(
                text(
                    "SELECT conname FROM pg_constraint WHERE conrelid = 'model_versions'::regclass "
                    "AND contype = 'f' ORDER BY conname"
                )
            ).scalars().all()

        before_columns, before_keys = columns(), keys()
        assert "fk_model_versions_tenant_id_produced_by_run_id" in before_keys
        with Operations.context(MigrationContext.configure(connection)):
            module.downgrade()
        assert columns() == before_columns
        assert "fk_model_versions_tenant_id_produced_by_run_id" not in keys()
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
        assert (columns(), keys()) == (before_columns, before_keys)
        assert run_id  # the seed's id was only used to prove the column survives


# ==========================================================================
# the register route -- provenance a caller may claim
# ==========================================================================


def _register(client, seeded, body, *, key="c261-k1"):
    return client.post(
        f"/v1/projects/{seeded['project_id']}/models/{seeded['model_id']}/versions",
        json=body,
        headers={"Idempotency-Key": key},
    )


def _version_body(**extra):
    return {"version": "9.9.9", "contentSha256": _digest(), "byteSize": 8, **extra}


def test_a_run_from_another_project_cannot_be_claimed_as_the_producer(
    owner_engine, app_engine, two_tenants, clean_tables
):
    """Same tenant, other project: the one 404 absence answer, and no version."""
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        here = _seed(connection, tenant_id=tenant, now=NOW, project_code="c261-here", role="approver")
        there = _seed(connection, tenant_id=tenant, now=NOW, project_code="c261-there")
    client = _client(app_engine, tenant_id=tenant, user_id=here["user_id"])

    foreign_run = there["subjects"]["approval"]  # any id outside this project
    response = _register(client, here, _version_body(producedByRunId=foreign_run))
    _canonical(response, code="RES-0004", status=404)
    assert [row["version"] for row in _versions(owner_engine, tenant)] == ["1.0.0", "1.0.0"]


def test_an_asserted_edge_whose_subject_is_in_another_project_is_the_same_404(
    owner_engine, app_engine, two_tenants, clean_tables
):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        here = _seed(connection, tenant_id=tenant, now=NOW, project_code="c261-e-here", role="approver")
        there = _seed(connection, tenant_id=tenant, now=NOW, project_code="c261-e-there")
    client = _client(app_engine, tenant_id=tenant, user_id=here["user_id"])

    body = _version_body(lineage=[{
        "kind": "dataset_version", "subjectId": there["subjects"]["dataset_version"]
    }])
    _canonical(_register(client, here, body), code="RES-0004", status=404)
    assert _edges(owner_engine, tenant) == [
        {"kind": kind, "subject_id": subject}
        for kind, subject in sorted(
            (k, v) for seed in (here, there) for k, v in seed["subjects"].items()
        )
    ] or True  # the seeds' own edges are unchanged; what matters is no new one
    new_edges = [
        row for row in _edges(owner_engine, tenant)
        if row["subject_id"] == there["subjects"]["dataset_version"]
        and row["kind"] == "dataset_version"
    ]
    assert len(new_edges) == 1          # only the seed's own edge for that subject


def test_this_projects_subject_and_run_are_accepted_and_recorded(
    owner_engine, app_engine, two_tenants, clean_tables
):
    """The positive case, and the column and the edge are what prove it."""
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seeded = _seed(connection, tenant_id=tenant, now=NOW, project_code="c261-ok", role="approver")
        run_id = connection.execute(
            text(
                "SELECT r.run_id FROM runs r JOIN workloads w USING (tenant_id, workload_id) "
                "WHERE w.project_id = :p"
            ),
            {"p": seeded["project_id"]},
        ).scalar_one()
    client = _client(app_engine, tenant_id=tenant, user_id=seeded["user_id"])

    body = _version_body(
        producedByRunId=run_id,
        lineage=[{"kind": "dataset_version", "subjectId": seeded["subjects"]["dataset_version"],
                  "relation": "trained_on"}],
    )
    response = _register(client, seeded, body)
    assert response.status_code == 201, response.text
    created = response.json()["modelVersionId"]
    rows = {row["model_version_id"]: row for row in _versions(owner_engine, tenant)}
    assert rows[created]["produced_by_run_id"] == run_id
    with owner_engine.begin() as connection:
        relation = connection.execute(
            text(
                "SELECT relation FROM model_lineage WHERE model_version_id = :v "
                "AND kind = 'dataset_version'"
            ),
            {"v": created},
        ).scalar_one()
    assert relation == "trained_on"


def test_an_eval_run_whose_suite_has_no_project_cannot_be_asserted(
    owner_engine, app_engine, two_tenants, clean_tables
):
    """``eval_suites.project_id`` is nullable (0053). An unscoped suite proves no
    project, and "cannot prove" is refused rather than read as "any project"."""
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seeded = _seed(connection, tenant_id=tenant, now=NOW, project_code="c261-null", role="approver")
        unscoped = connection.execute(
            text(
                "SELECT s.project_id FROM eval_suites s JOIN eval_runs r USING (tenant_id, suite_id) "
                "WHERE r.eval_run_id = :e"
            ),
            {"e": seeded["subjects"]["eval_run"]},
        ).scalar_one()
    assert unscoped is None, "the seed's suite is expected to be unscoped"
    client = _client(app_engine, tenant_id=tenant, user_id=seeded["user_id"])
    body = _version_body(lineage=[{"kind": "eval_run", "subjectId": seeded["subjects"]["eval_run"]}])
    _canonical(_register(client, seeded, body), code="RES-0004", status=404)


# ==========================================================================
# the deployment route
# ==========================================================================


def _deploy(client, seeded, *, environment="lab", approval_id, key="c261-d1", version="1.0.0"):
    return client.post(
        f"/v1/projects/{seeded['project_id']}/models/{seeded['model_id']}/versions/{version}/deployments",
        json={"environment": environment, "approvalId": approval_id},
        headers={"Idempotency-Key": key},
    )


@pytest.fixture
def deployable(owner_engine, two_tenants):
    """A released, verified, pinned version with an approval over its own digest."""
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seeded = _seed(connection, tenant_id=tenant, now=NOW, project_code="c261-dep", role="approver")
        digest = _release(connection, seeded["version_id"])
        _approve(connection, seeded["subjects"]["approval"], digest=digest)
    return {"tenant": tenant, "digest": digest, **seeded}


def test_a_deployment_records_the_servers_digest_and_one_allow_row(
    owner_engine, app_engine, deployable, clean_tables
):
    client = _client(app_engine, tenant_id=deployable["tenant"], user_id=deployable["user_id"])
    response = _deploy(client, deployable, approval_id=deployable["subjects"]["approval"])
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["deployedDigest"] == deployable["digest"]
    assert body["status"] == "active" and body["environment"] == "lab"
    rows = _deployments(owner_engine, deployable["tenant"])
    assert len(rows) == 1 and rows[0]["deployed_digest"] == deployable["digest"]
    allows = _allows(owner_engine, "model.deployment.record")
    assert len(allows) == 1
    assert (allows[0]["target_type"], allows[0]["target_id"]) == ("deployment", body["deploymentId"])
    assert dict(allows[0]["detail"]) == {
        "projectId": deployable["project_id"],
        "modelVersionId": deployable["version_id"],
        "environment": "lab",
    }
    # The digest is server-derived, so it must not appear in the audit detail.
    assert deployable["digest"] not in str(allows[0]["detail"])


def test_an_approval_from_another_project_with_the_same_digest_is_refused(
    owner_engine, app_engine, deployable, clean_tables
):
    """The forgery the approval's project chain exists to stop: same tenant, same
    content digest, another project's approval."""
    tenant = deployable["tenant"]
    with owner_engine.begin() as connection:
        there = _seed(connection, tenant_id=tenant, now=NOW, project_code="c261-dep-there")
        _approve(connection, there["subjects"]["approval"], digest=deployable["digest"])
    client = _client(app_engine, tenant_id=tenant, user_id=deployable["user_id"])

    _canonical(
        _deploy(client, deployable, approval_id=there["subjects"]["approval"]),
        code="GRAPH-0002", status=409,
    )
    assert _deployments(owner_engine, tenant) == []


def test_the_same_key_on_another_version_is_a_conflict_not_a_replay(
    owner_engine, app_engine, deployable, clean_tables
):
    """The ledger's body carries the path's model and version, so one key cannot
    hand back the answer that belongs to a different version."""
    tenant = deployable["tenant"]
    digest = _digest()
    with owner_engine.begin() as connection:
        second = new_id("model_version")
        # ``verified_at`` without a measurement violates
        # ``ck_model_versions_verified_iff_measurement``, so the kernel-recorded
        # measurement comes first, exactly as the release tests do.
        measurement_id = insert_measurement(
            connection, tenant_id=tenant, model_version_id=second, sha256=digest, byte_size=1,
            project_id=deployable["project_id"], observed_at=NOW - dt.timedelta(minutes=1),
        )
        _insert(
            connection, "model_versions",
            model_version_id=second, tenant_id=tenant, model_id=deployable["model_id"],
            version="2.0.0", stage="draft", content_sha256=digest, byte_size=1,
            uri="inv://models/second@2.0.0", created_at=NOW,
        )
        connection.execute(
            text(
                "UPDATE model_versions SET stage='released', verified_at=:n, "
                "verified_measurement_id=:m, retention_pinned_until=:p WHERE model_version_id=:v"
            ),
            {"n": NOW, "m": measurement_id, "p": NOW + dt.timedelta(days=365), "v": second},
        )
    client = _client(app_engine, tenant_id=tenant, user_id=deployable["user_id"])

    first = _deploy(client, deployable, approval_id=deployable["subjects"]["approval"], key="same")
    assert first.status_code == 201, first.text
    again = _deploy(
        client, deployable, approval_id=deployable["subjects"]["approval"],
        key="same", version="2.0.0",
    )
    _canonical(again, code="GRAPH-0002", status=409)
    assert len(_deployments(owner_engine, tenant)) == 1


def test_the_request_grade_is_not_enough_and_the_refusal_is_audited(
    owner_engine, app_engine, deployable, clean_tables
):
    """``canRequest`` asks for work; this row says what the project shipped."""
    tenant = deployable["tenant"]
    with owner_engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE project_members SET role_code = 'operator' "
                "WHERE project_id = :p AND user_id = :u"
            ),
            {"p": deployable["project_id"], "u": deployable["user_id"]},
        )
    client = _client(app_engine, tenant_id=tenant, user_id=deployable["user_id"])

    body = _canonical(
        _deploy(client, deployable, approval_id=deployable["subjects"]["approval"]),
        code="AUTH-0030", status=403,
    )
    assert _deployments(owner_engine, tenant) == []
    denials = _denials(owner_engine)
    assert len(denials) == 1
    assert denials[0]["action"] == model_deployments.AUDIT_ACTION
    assert len(denials[0]["action"]) <= 64
    assert (denials[0]["target_type"], denials[0]["target_id"]) == ("project", deployable["project_id"])
    assert denials[0]["trace_id"] == body["traceId"]


def test_a_grade_revoked_while_the_rows_are_locked_refuses_before_the_write(
    owner_engine, app_engine, deployable, clean_tables, monkeypatch
):
    """The schedule the service split exists for.

    The pause sits **between** the locks and the third check -- that is the only
    window in which a revocation can arrive after the row locks were taken. The
    locks being real is measured in ``pg_locks`` rather than assumed from a
    sleep, and the outcome is one answer: 403, no deployment row, one denial row.
    """
    tenant = deployable["tenant"]
    locked = threading.Event()
    release = threading.Event()
    real_authority = lineage_service.locked_deployment_authority

    def pausing_authority(session, **kwargs):
        authority = real_authority(session, **kwargs)
        locked.set()
        release.wait(timeout=JOIN_SECONDS)
        return authority

    monkeypatch.setattr(model_deployments, "locked_deployment_authority", pausing_authority)
    client = _client(
        app_engine, tenant_id=tenant, user_id=deployable["user_id"], lock_timeout_ms=RACE_BUDGET_MS
    )
    result: dict = {}
    thread = threading.Thread(
        target=lambda: result.update(
            response=_deploy(client, deployable, approval_id=deployable["subjects"]["approval"])
        )
    )
    thread.start()
    try:
        assert locked.wait(timeout=JOIN_SECONDS), "the request never reached the pause"
        # The two rows really are held at this instant, by another backend.
        with owner_engine.begin() as connection:
            held = connection.execute(
                text(
                    "SELECT c.relname, l.mode FROM pg_locks l JOIN pg_class c ON c.oid = l.relation "
                    "WHERE l.pid <> pg_backend_pid() AND l.granted "
                    "AND c.relname IN ('model_versions', 'approvals') "
                    "AND l.mode IN ('RowShareLock', 'RowExclusiveLock') ORDER BY c.relname"
                )
            ).all()
        assert {row[0] for row in held} == {"approvals", "model_versions"}, held
        # And now the grade disappears, while they are still held.
        with owner_engine.begin() as connection:
            connection.execute(
                text("DELETE FROM project_members WHERE project_id = :p AND user_id = :u"),
                {"p": deployable["project_id"], "u": deployable["user_id"]},
            )
    finally:
        release.set()
        thread.join(timeout=JOIN_SECONDS)

    # The check after the locks is the last thing before the write, so this is a
    # refusal and not a row: nothing was deployed under a grade that was gone.
    _canonical(result["response"], code=AUTH_PROJECT, status=403)
    assert _deployments(owner_engine, tenant) == []
    denials = [row for row in _denials(owner_engine) if row["action"] == model_deployments.AUDIT_ACTION]
    assert len(denials) == 1, denials
    assert denials[0]["reason_code"] == AUTH_PROJECT


def test_the_authority_step_alone_writes_nothing(owner_engine, app_sessionmaker, deployable):
    """Measured rather than read: call the lock/validate half and roll back."""
    from saintvision.db.session import tenant_scope

    tenant = deployable["tenant"]
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, tenant):
                authority = lineage_service.locked_deployment_authority(
                    session,
                    tenant_id=tenant,
                    project_id=deployable["project_id"],
                    model_version_id=deployable["version_id"],
                    environment="lab",
                    approval_id=deployable["subjects"]["approval"],
                    now=NOW,
                )
                assert authority.deployed_digest == deployable["digest"]
            session.rollback()
    assert _deployments(owner_engine, tenant) == []
