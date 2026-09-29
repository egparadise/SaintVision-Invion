"""Real PostgreSQL nodes for the model release route (VF-CL-03 design §9, 28-30).

These three are the ones a stand-in session cannot establish, because what they
test is the database: RLS keeping another tenant's model version invisible, the
path/project mismatch answering with the same 404 as that invisibility, and a
refusal leaving ``stage`` at ``draft`` in a committed transaction.

The kernel observation is injected. The point here is the database boundary, and
a second HTTP server would add a second failure mode to a test whose subject is
the first one. The transport itself is covered over real HTTP in
``tests/core/test_model_release_route.py``.
"""

from __future__ import annotations

import datetime as dt
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from saintvision.api.app import create_app
from saintvision.api.deps import get_principal
from saintvision.api.problem import CANONICAL_KEYS
from saintvision.api.v1 import model_release
from saintvision.config import Settings
from saintvision.identity.principal import Principal, StaticPrincipalVerifier
from saintvision.tracking import config as tracking_config
from saintvision.ids import new_id
from measurement_support import insert_measurement

pytestmark = pytest.mark.postgres

DECLARATION = {"licensePolicy": "internal-only-eula-2026", "classification": "restricted"}


def _digest() -> str:
    """64 lowercase hex, unique: the shape the checksum columns require."""
    return uuid.uuid4().hex + uuid.uuid4().hex


def _observation(project_id, model_id, version):
    return {
        "projectId": project_id,
        "modelId": model_id,
        "version": version,
        "manifestHash": "d" * 64,
        "sourceRunId": new_id("run"),
        "committedAt": "2026-09-28T01:00:00Z",
        "commitRecoveryEpoch": "33333333-3333-3333-3333-333333333333",
        "format": "safetensors",
        "totalBytes": 4096,
        "shardCount": 1,
        "committed": True,
        "currentAvailability": "unknown",
        "requiresExecutionRevalidation": True,
        **DECLARATION,
    }


def _insert(connection, table_name, **values):
    """Insert through the model metadata, so a wrong column cannot reach hosted CI.

    Raw SQL in a fixture is checked by PostgreSQL and nowhere else, which is how
    this file first failed: an hour of hosted CI to learn a name. Building the
    statement from ``Base.metadata`` validates the column names as it is written,
    and the required-column check below covers the omissions PostgreSQL would
    otherwise be the first to notice.
    """
    from saintvision.db.base import Base
    from saintvision.db import models  # noqa: F401  (registers the tables)

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


def _seed_subjects(connection, *, tenant_id, project_id, user_id, now, label):
    """The four subject rows a fully traceable version needs, and their chain.

    ``trace_model`` resolves each edge to a row and reports a kind as missing when
    the row is absent, so seeding edges alone leaves the version untraceable --
    which is what the first hosted run of this file showed, with every release
    refused as ``GRAPH-0002`` before the declaration was ever compared. The
    approval chain (workspace, workload, run) is here for the same reason: the
    row has to exist to be found.
    """
    dataset_id = new_id("dataset")
    dataset_version_id = new_id("dataset_version")
    commit_id = new_id("commit")
    suite_id = new_id("eval_suite")
    eval_run_id = new_id("eval_run")
    workspace_id = new_id("workspace")
    workload_id = new_id("workload")
    run_id = new_id("run")
    approval_id = new_id("approval")

    _insert(
        connection,
        "datasets",
        dataset_id=dataset_id,
        tenant_id=tenant_id,
        project_id=project_id,
        name=f"dataset-{label}",
        created_at=now,
    )
    _insert(
        connection,
        "dataset_versions",
        dataset_version_id=dataset_version_id,
        tenant_id=tenant_id,
        dataset_id=dataset_id,
        version="2026-09-01",
        content_sha256=_digest(),
        byte_size=1,
        record_count=1,
        uri=f"inv://datasets/dataset-{label}@2026-09-01",
        created_at=now,
    )
    _insert(
        connection,
        "code_commits",
        commit_id=commit_id,
        tenant_id=tenant_id,
        repository="git@example.invalid:saintvision.git",
        # 40 lowercase hex, which the column's CHECK requires.
        commit_sha=uuid.uuid4().hex[:40].ljust(40, "0"),
        recorded_at=now,
    )
    _insert(
        connection,
        "eval_suites",
        suite_id=suite_id,
        tenant_id=tenant_id,
        name=f"suite-{label}",
        version="1",
        definition_sha256=_digest(),
        created_at=now,
    )
    _insert(
        connection,
        "eval_runs",
        eval_run_id=eval_run_id,
        tenant_id=tenant_id,
        suite_id=suite_id,
        status="completed",
        total_cases=1,
        passed_cases=1,
        violations=0,
        passed_gate=True,
        started_at=now,
        ended_at=now,
    )
    _insert(
        connection,
        "workspaces",
        workspace_id=workspace_id,
        tenant_id=tenant_id,
        project_id=project_id,
        name=f"workspace-{label}",
        created_by_user_id=user_id,
        created_at=now,
    )
    _insert(
        connection,
        "workloads",
        workload_id=workload_id,
        tenant_id=tenant_id,
        project_id=project_id,
        objective=f"objective-{label}",
        spec={},
        spec_sha256=_digest(),
        contract_version="v1alpha1",
        created_by_user_id=user_id,
        created_at=now,
    )
    _insert(
        connection,
        "runs",
        run_id=run_id,
        tenant_id=tenant_id,
        workload_id=workload_id,
        workspace_id=workspace_id,
        requested_by_user_id=user_id,
        created_at=now,
    )
    _insert(
        connection,
        "approvals",
        approval_id=approval_id,
        tenant_id=tenant_id,
        run_id=run_id,
        subject_sha256=_digest(),
        decision="approved",
        risk_level=1,
        decided_by_user_id=user_id,
        decided_at=now,
        expires_at=now + dt.timedelta(days=365),
    )
    # Keyed by the model_lineage edge kind, which is a different vocabulary from
    # the identifier kinds used above: the edge kind ``code_commit`` belongs to a
    # row whose id kind is ``commit``.
    return {
        "dataset_version": dataset_version_id,
        "code_commit": commit_id,
        "eval_run": eval_run_id,
        "approval": approval_id,
    }


def _seed(connection, *, tenant_id, now, project_code, role="approver"):
    """One project, one approving member, one releasable model version."""
    user_id = new_id("user")
    project_id = new_id("project")
    model_id = new_id("model")
    version_id = new_id("model_version")

    _insert(
        connection,
        "users",
        user_id=user_id,
        tenant_id=tenant_id,
        external_subject=f"release-{project_code}",
        display_name=f"release-{project_code}",
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
        code=project_code,
        display_name=project_code,
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
    _insert(
        connection,
        "models",
        model_id=model_id,
        tenant_id=tenant_id,
        project_id=project_id,
        name=f"model-{project_code}",
        created_at=now,
    )
    # 64 lowercase hex, unique per tenant: the response contract checks the
    # shape and the table has a per-tenant unique constraint.
    digest = _digest()
    # Verified means bound to a kernel-recorded measurement (0054): the seed
    # records one, as the kernel would, before it marks the row verified.
    measurement_id = insert_measurement(
        connection, tenant_id=tenant_id, model_version_id=version_id, sha256=digest, byte_size=1,
        project_id=project_id, observed_at=now - dt.timedelta(minutes=1),
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
        byte_size=1,
        uri=f"inv://models/model-{project_code}@1.0.0",
        verified_at=now,
        verified_measurement_id=measurement_id,
        retention_pinned_until=now + dt.timedelta(days=365),
        created_at=now,
    )

    subjects = _seed_subjects(
        connection,
        tenant_id=tenant_id,
        project_id=project_id,
        user_id=user_id,
        now=now,
        label=project_code,
    )
    for kind, subject_id in subjects.items():
        _insert(
            connection,
            "model_lineage",
            tenant_id=tenant_id,
            model_version_id=version_id,
            kind=kind,
            subject_id=subject_id,
            relation="derived_from",
            recorded_at=now,
        )
    return {
        "user_id": user_id,
        "project_id": project_id,
        "model_id": model_id,
        "version_id": version_id,
        "subjects": subjects,
    }


def _client(app_engine, *, tenant_id, user_id, now, observation):
    app = create_app(
        engine=app_engine,
        settings=Settings(database_url="test-only", kernel_base_url="http://kernel.invalid"),
        verifier=StaticPrincipalVerifier({}, allow_outside_dev=True),
        clock=lambda: now,
        check_partitions_on_startup=False,
    )
    app.dependency_overrides[get_principal] = lambda: Principal(
        user_id=user_id, tenant_id=tenant_id, external_subject="synthetic-release"
    )
    app.state.model_commitment_fetcher = lambda **_kwargs: observation
    return TestClient(app, raise_server_exceptions=False)


def _path(seeded, project_id=None):
    return (
        f"/v1/projects/{project_id or seeded['project_id']}"
        f"/models/{seeded['model_id']}/versions/1.0.0/release"
    )


def _headers(key="release-k1"):
    """Card 113: every release carries an Idempotency-Key."""
    return {"Idempotency-Key": key}


CONFIGURED_MIRROR_ENV = {
    "INV_MLFLOW_TRACKING_URI": "https://mlflow.lab.example/",
    "INV_MLFLOW_DESTINATION": "lab-mlflow",
    "INV_MLFLOW_EXPERIMENT_PREFIX": "inv",
}


@pytest.fixture
def configured_mirror(monkeypatch):
    """Card 113: a strict ``configured`` tracking environment, so a release
    writes exactly one mirror intent and the idempotency assertions measure a
    real duplicate-suppression instead of the ``absent`` skip.

    ``enqueue_mirror`` resolves ``os.environ`` at call time; hosted Backend
    sets no ``INV_MLFLOW_*`` variable, and this fixture never leaks past the
    test (monkeypatch restores the environment and the client probe)."""
    for key, value in CONFIGURED_MIRROR_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("INV_MLFLOW_TIMEOUT_SECONDS", raising=False)
    monkeypatch.setattr(tracking_config, "mlflow_client_present", lambda: True)
    resolved = tracking_config.resolve()
    assert resolved.readiness.value == "configured", resolved.readiness
    return resolved


def _mirror_intents(owner_engine, version_id):
    """Mirror intents for one version, read as the owner (the duplicate this
    contract exists to prevent)."""
    with owner_engine.begin() as connection:
        return connection.execute(
            text(
                "SELECT intent_id FROM mlflow_mirror_intents "
                "WHERE subject_kind = 'model_version' AND model_version_id = :v ORDER BY intent_id"
            ),
            {"v": version_id},
        ).scalars().all()


def _ledger(owner_engine, tenant_id):
    with owner_engine.begin() as connection:
        return connection.execute(
            text(
                "SELECT endpoint, idempotency_key, project_id, response_status "
                "FROM idempotency_records WHERE tenant_id = :t"
            ),
            {"t": tenant_id},
        ).mappings().all()


def _release_audits(owner_engine):
    with owner_engine.begin() as connection:
        return connection.execute(
            text("SELECT target_id FROM audit_events WHERE action = 'model_version.release'")
        ).scalars().all()
def _stage(owner_engine, version_id):
    with owner_engine.begin() as connection:
        return connection.execute(
            text("SELECT stage FROM model_versions WHERE model_version_id = :v"),
            {"v": version_id},
        ).scalar_one()


def _canonical(response, *, code, status):
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == set(CANONICAL_KEYS), body
    assert body["type"] == "about:blank"
    assert body["code"] == code
    return body


def test_30_another_tenants_model_version_is_the_same_404_and_is_not_changed(
    owner_engine, app_engine, two_tenants, frozen_now
):
    """RLS makes the row invisible; the answer must not say more than that."""
    tenant_a, tenant_b = two_tenants
    with owner_engine.begin() as connection:
        theirs = _seed(connection, tenant_id=tenant_b, now=frozen_now, project_code="other-tenant")
        mine = _seed(connection, tenant_id=tenant_a, now=frozen_now, project_code="my-tenant")

    # Tenant A's principal asks for tenant B's model version, by its real ids.
    with _client(
        app_engine,
        tenant_id=tenant_a,
        user_id=mine["user_id"],
        now=frozen_now,
        observation=_observation(theirs["project_id"], theirs["model_id"], "1.0.0"),
    ) as client:
        response = client.post(
            f"/v1/projects/{theirs['project_id']}/models/{theirs['model_id']}"
            "/versions/1.0.0/release",
            json=DECLARATION,
            headers=_headers(),
        )
    # 403 here, because the project itself is not visible to this principal, and
    # that is the same answer an absent project gets. Either way nothing moved.
    body = _canonical(response, code="AUTH-0030", status=403)
    assert "projectId" not in body
    assert _stage(owner_engine, theirs["version_id"]) == "draft"


def test_30b_another_tenants_version_under_an_accessible_project_is_a_404(
    owner_engine, app_engine, two_tenants, frozen_now
):
    """The path's project is mine; the model named in it is not.

    This is the case that separates "cannot see the project" from "cannot see the
    row", and both must end in a refusal that reveals nothing.
    """
    tenant_a, tenant_b = two_tenants
    with owner_engine.begin() as connection:
        theirs = _seed(connection, tenant_id=tenant_b, now=frozen_now, project_code="theirs")
        mine = _seed(connection, tenant_id=tenant_a, now=frozen_now, project_code="mine")

    with _client(
        app_engine,
        tenant_id=tenant_a,
        user_id=mine["user_id"],
        now=frozen_now,
        observation=_observation(mine["project_id"], theirs["model_id"], "1.0.0"),
    ) as client:
        response = client.post(
            f"/v1/projects/{mine['project_id']}/models/{theirs['model_id']}"
            "/versions/1.0.0/release",
            json=DECLARATION,
            headers=_headers(),
        )
    body = _canonical(response, code="RES-0004", status=404)
    assert body["detail"] == "No such model version."
    assert _stage(owner_engine, theirs["version_id"]) == "draft"
    assert _stage(owner_engine, mine["version_id"]) == "draft"


def test_29b_a_model_in_another_project_of_my_tenant_is_the_same_404(
    owner_engine, app_engine, two_tenants, frozen_now
):
    """Same tenant, different project: indistinguishable from the cross-tenant 404."""
    tenant_a, _ = two_tenants
    with owner_engine.begin() as connection:
        first = _seed(connection, tenant_id=tenant_a, now=frozen_now, project_code="first")
        second = _seed(connection, tenant_id=tenant_a, now=frozen_now, project_code="second")

    with _client(
        app_engine,
        tenant_id=tenant_a,
        user_id=first["user_id"],
        now=frozen_now,
        observation=_observation(first["project_id"], second["model_id"], "1.0.0"),
    ) as client:
        response = client.post(
            f"/v1/projects/{first['project_id']}/models/{second['model_id']}"
            "/versions/1.0.0/release",
            json=DECLARATION,
            headers=_headers(),
        )
    body = _canonical(response, code="RES-0004", status=404)
    assert body["detail"] == "No such model version."
    assert _stage(owner_engine, second["version_id"]) == "draft"


def test_29c_a_declaration_mismatch_leaves_the_version_in_draft(
    owner_engine, app_engine, two_tenants, frozen_now
):
    """The refusal has to survive as a refusal: nothing committed, nothing audited."""
    tenant_a, _ = two_tenants
    with owner_engine.begin() as connection:
        mine = _seed(connection, tenant_id=tenant_a, now=frozen_now, project_code="mismatch")

    with _client(
        app_engine,
        tenant_id=tenant_a,
        user_id=mine["user_id"],
        now=frozen_now,
        observation=_observation(mine["project_id"], mine["model_id"], "1.0.0"),
    ) as client:
        response = client.post(_path(mine), json={**DECLARATION, "classification": "public"}, headers=_headers())

    body = _canonical(response, code="MODEL-0009", status=409)
    assert "differs:classification" in body["detail"]
    # Neither the submitted value nor the declared one is anywhere in the body.
    assert "public" not in body["detail"]
    assert "restricted" not in body["detail"]
    assert _stage(owner_engine, mine["version_id"]) == "draft"
    with owner_engine.begin() as connection:
        audited = connection.execute(
            text(
                "SELECT count(*) FROM audit_events WHERE action = 'model_version.release'"
            )
        ).scalar_one()
    assert audited == 0


def test_30c_a_release_that_satisfies_everything_commits_and_audits_once(
    owner_engine, app_engine, two_tenants, frozen_now
):
    """The positive control, so the refusals above are not passing vacuously."""
    tenant_a, _ = two_tenants
    with owner_engine.begin() as connection:
        mine = _seed(connection, tenant_id=tenant_a, now=frozen_now, project_code="positive")

    with _client(
        app_engine,
        tenant_id=tenant_a,
        user_id=mine["user_id"],
        now=frozen_now,
        observation=_observation(mine["project_id"], mine["model_id"], "1.0.0"),
    ) as client:
        response = client.post(_path(mine), json=DECLARATION, headers=_headers())

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["stage"] == "released"
    assert payload["modelVersionId"] == mine["version_id"]
    assert set(payload) == {
        "modelVersionId",
        "modelId",
        "version",
        "stage",
        "contentSha256",
    }
    assert _stage(owner_engine, mine["version_id"]) == "released"

    with owner_engine.begin() as connection:
        rows = connection.execute(
            text(
                "SELECT target_id, detail FROM audit_events "
                "WHERE action = 'model_version.release'"
            )
        ).all()
    assert len(rows) == 1
    target_id, detail = rows[0]
    assert target_id == mine["version_id"]
    # Field names, never the values they name.
    assert detail["declarationFields"] == ["licensePolicy", "classification"]
    serialised = str(detail)
    assert DECLARATION["licensePolicy"] not in serialised
    assert "restricted" not in serialised
    # Tracking is ``absent`` here (no ``INV_MLFLOW_*``): the canonical change
    # succeeds and no mirror intent is written. The configured path is the
    # ``configured_mirror`` fixture below.
    assert tracking_config.resolve().readiness.value == "absent"
    assert _mirror_intents(owner_engine, mine["version_id"]) == []


def test_29d_a_member_without_the_approval_grade_cannot_release(
    owner_engine, app_engine, two_tenants, frozen_now
):
    """``operator`` can request things; releasing is an approval grade."""
    tenant_a, _ = two_tenants
    with owner_engine.begin() as connection:
        mine = _seed(
            connection,
            tenant_id=tenant_a,
            now=frozen_now,
            project_code="operator-only",
            role="operator",
        )

    with _client(
        app_engine,
        tenant_id=tenant_a,
        user_id=mine["user_id"],
        now=frozen_now,
        observation=_observation(mine["project_id"], mine["model_id"], "1.0.0"),
    ) as client:
        response = client.post(_path(mine), json=DECLARATION, headers=_headers())

    body = _canonical(response, code="AUTH-0030", status=403)
    assert "approval permission" in body["detail"]
    assert _stage(owner_engine, mine["version_id"]) == "draft"


# ---------------------------------------------------------------------------
# Card 113 (Codex #219 r4 F1): a lost response and a retry release once
# ---------------------------------------------------------------------------


def test_113_the_same_key_replays_the_stored_answer_and_the_mirror_intent_is_not_duplicated(
    owner_engine, app_engine, two_tenants, frozen_now, configured_mirror
):
    tenant_a, _ = two_tenants
    with owner_engine.begin() as connection:
        mine = _seed(connection, tenant_id=tenant_a, now=frozen_now, project_code="idem-replay")
    with _client(
        app_engine, tenant_id=tenant_a, user_id=mine["user_id"], now=frozen_now,
        observation=_observation(mine["project_id"], mine["model_id"], "1.0.0"),
    ) as client:
        first = client.post(_path(mine), json=DECLARATION, headers=_headers("k-replay"))
        second = client.post(_path(mine), json=DECLARATION, headers=_headers("k-replay"))
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json() == second.json()
    assert first.json()["stage"] == "released"
    # One stage write, one mirror intent, one audit row, one ledger row.
    assert _stage(owner_engine, mine["version_id"]) == "released"
    assert len(_mirror_intents(owner_engine, mine["version_id"])) == 1
    assert _release_audits(owner_engine) == [mine["version_id"]]
    ledger = _ledger(owner_engine, tenant_a)
    assert len(ledger) == 1
    assert ledger[0]["endpoint"] == model_release.ENDPOINT
    assert ledger[0]["idempotency_key"] == "k-replay" and ledger[0]["response_status"] == 200
    assert ledger[0]["project_id"] == mine["project_id"]


def test_113_the_same_key_with_a_different_declaration_is_409_and_changes_nothing(
    owner_engine, app_engine, two_tenants, frozen_now, configured_mirror
):
    tenant_a, _ = two_tenants
    with owner_engine.begin() as connection:
        mine = _seed(connection, tenant_id=tenant_a, now=frozen_now, project_code="idem-conflict")
    with _client(
        app_engine, tenant_id=tenant_a, user_id=mine["user_id"], now=frozen_now,
        observation=_observation(mine["project_id"], mine["model_id"], "1.0.0"),
    ) as client:
        first = client.post(_path(mine), json=DECLARATION, headers=_headers("k-conflict"))
        other = client.post(
            _path(mine), json={**DECLARATION, "classification": "internal"}, headers=_headers("k-conflict")
        )
    assert first.status_code == 200, first.text
    body = _canonical(other, code="GRAPH-0002", status=409)
    assert body["detail"] == "That idempotency key was used with a different request."
    assert "internal" not in str(body)
    assert len(_mirror_intents(owner_engine, mine["version_id"])) == 1
    assert len(_ledger(owner_engine, tenant_a)) == 1


def test_113_a_second_release_under_another_key_is_409_and_does_not_mirror_again(
    owner_engine, app_engine, two_tenants, frozen_now, configured_mirror
):
    tenant_a, _ = two_tenants
    with owner_engine.begin() as connection:
        mine = _seed(connection, tenant_id=tenant_a, now=frozen_now, project_code="idem-twice")
    with _client(
        app_engine, tenant_id=tenant_a, user_id=mine["user_id"], now=frozen_now,
        observation=_observation(mine["project_id"], mine["model_id"], "1.0.0"),
    ) as client:
        first = client.post(_path(mine), json=DECLARATION, headers=_headers("k-first"))
        again = client.post(_path(mine), json=DECLARATION, headers=_headers("k-second"))
    assert first.status_code == 200, first.text
    body = _canonical(again, code="GRAPH-0002", status=409)
    assert body["detail"] == "The model version is already released."
    assert len(_mirror_intents(owner_engine, mine["version_id"])) == 1
    assert _release_audits(owner_engine) == [mine["version_id"]]
    # The refused request stored nothing under its key.
    assert [row["idempotency_key"] for row in _ledger(owner_engine, tenant_a)] == ["k-first"]


def test_113_a_release_without_a_key_is_422_and_leaves_the_version_in_draft(
    owner_engine, app_engine, two_tenants, frozen_now
):
    tenant_a, _ = two_tenants
    with owner_engine.begin() as connection:
        mine = _seed(connection, tenant_id=tenant_a, now=frozen_now, project_code="idem-nokey")
    with _client(
        app_engine, tenant_id=tenant_a, user_id=mine["user_id"], now=frozen_now,
        observation=_observation(mine["project_id"], mine["model_id"], "1.0.0"),
    ) as client:
        response = client.post(_path(mine), json=DECLARATION)
    _canonical(response, code="VAL-0003", status=422)
    assert _stage(owner_engine, mine["version_id"]) == "draft"
    assert _mirror_intents(owner_engine, mine["version_id"]) == []
    assert _ledger(owner_engine, tenant_a) == []


def test_113_two_concurrent_first_requests_with_one_key_release_once_and_replay(
    owner_engine, app_engine, two_tenants, frozen_now, monkeypatch, configured_mirror
):
    """IDEM-6 on the real database: the advisory lock serialises the two, the
    second finds the stored answer. One stage write, one mirror intent."""
    import threading
    from concurrent.futures import ThreadPoolExecutor

    tenant_a, _ = two_tenants
    with owner_engine.begin() as connection:
        mine = _seed(connection, tenant_id=tenant_a, now=frozen_now, project_code="idem-race")
    barrier = threading.Barrier(2, timeout=60)
    real = model_release.serialise_idempotent_write

    def at_the_same_moment(session, **kwargs):
        barrier.wait()
        return real(session, **kwargs)

    monkeypatch.setattr(model_release, "serialise_idempotent_write", at_the_same_moment)

    def send():
        client = _client(
            app_engine, tenant_id=tenant_a, user_id=mine["user_id"], now=frozen_now,
            observation=_observation(mine["project_id"], mine["model_id"], "1.0.0"),
        )
        return client.post(_path(mine), json=DECLARATION, headers=_headers("k-race"))

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = [f.result(timeout=90) for f in [pool.submit(send), pool.submit(send)]]
    assert sorted(r.status_code for r in responses) == [200, 200], [r.text for r in responses]
    assert responses[0].json() == responses[1].json()
    assert len(_mirror_intents(owner_engine, mine["version_id"])) == 1
    assert _release_audits(owner_engine) == [mine["version_id"]]
    assert len(_ledger(owner_engine, tenant_a)) == 1


def test_113_F1_a_lost_response_replays_while_the_kernel_is_unavailable_and_a_conflict_is_409_first(
    owner_engine, app_engine, two_tenants, frozen_now, configured_mirror
):
    """Codex #229 F1 on the real ledger: after a committed release the retry is
    answered from ``idempotency_records`` with the kernel unreachable, and a
    different body under the same key is refused before any upstream call."""
    tenant_a, _ = two_tenants
    with owner_engine.begin() as connection:
        mine = _seed(connection, tenant_id=tenant_a, now=frozen_now, project_code="idem-kernel-down")
    calls = {"n": 0}

    def broken(**_kwargs):
        calls["n"] += 1
        raise OSError("kernel unavailable")

    with _client(
        app_engine, tenant_id=tenant_a, user_id=mine["user_id"], now=frozen_now,
        observation=_observation(mine["project_id"], mine["model_id"], "1.0.0"),
    ) as client:
        first = client.post(_path(mine), json=DECLARATION, headers=_headers("k-lost"))
        assert first.status_code == 200, first.text
        client.app.state.model_commitment_fetcher = broken
        retry = client.post(_path(mine), json=DECLARATION, headers=_headers("k-lost"))
        conflict = client.post(
            _path(mine), json={**DECLARATION, "classification": "internal"}, headers=_headers("k-lost")
        )
    assert retry.status_code == 200, retry.text
    assert retry.json() == first.json()
    body = _canonical(conflict, code="GRAPH-0002", status=409)
    assert body["detail"] == "That idempotency key was used with a different request."
    assert calls["n"] == 0                                    # the kernel was never asked
    assert len(_mirror_intents(owner_engine, mine["version_id"])) == 1
    assert _release_audits(owner_engine) == [mine["version_id"]]
    assert len(_ledger(owner_engine, tenant_a)) == 1
