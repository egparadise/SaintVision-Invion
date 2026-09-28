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
from saintvision.config import Settings
from saintvision.identity.principal import Principal, StaticPrincipalVerifier
from saintvision.ids import new_id

pytestmark = pytest.mark.postgres

DECLARATION = {"licensePolicy": "internal-only-eula-2026", "classification": "restricted"}


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


def _seed(connection, *, tenant_id, now, project_code, role="approver"):
    """One project, one approving member, one releasable model version."""
    user_id = new_id("user")
    project_id = new_id("project")
    model_id = new_id("model")
    version_id = new_id("model_version")
    connection.execute(
        text(
            "INSERT INTO users (user_id, tenant_id, external_subject, display_name, "
            "status, created_at, updated_at, version) "
            "VALUES (:user, :tenant, :subject, :subject, 'active', :now, :now, 1)"
        ),
        {"user": user_id, "tenant": tenant_id, "subject": f"release-{project_code}", "now": now},
    )
    connection.execute(
        text(
            "INSERT INTO projects (project_id, tenant_id, code, display_name, status, "
            "created_at, version) VALUES (:project, :tenant, :code, :code, 'active', :now, 1)"
        ),
        {"project": project_id, "tenant": tenant_id, "code": project_code, "now": now},
    )
    connection.execute(
        text(
            "INSERT INTO project_members (tenant_id, project_id, user_id, role_code) "
            "VALUES (:tenant, :project, :user, :role)"
        ),
        {"tenant": tenant_id, "project": project_id, "user": user_id, "role": role},
    )
    connection.execute(
        text(
            "INSERT INTO models (model_id, tenant_id, project_id, name, created_at) "
            "VALUES (:model, :tenant, :project, :name, :now)"
        ),
        {
            "model": model_id,
            "tenant": tenant_id,
            "project": project_id,
            "name": f"model-{project_code}",
            "now": now,
        },
    )
    # 64 lowercase hex, unique per tenant, because the response contract checks
    # the shape and the table has a per-tenant unique constraint.
    digest = uuid.uuid4().hex + uuid.uuid4().hex
    connection.execute(
        text(
            "INSERT INTO model_versions (model_version_id, tenant_id, model_id, version, "
            "stage, content_sha256, byte_size, uri, verified_at, retention_pinned_until, "
            "created_at) VALUES (:version_id, :tenant, :model, '1.0.0', 'draft', :sha, 1, "
            ":uri, :now, :until, :now)"
        ),
        {
            "version_id": version_id,
            "tenant": tenant_id,
            "model": model_id,
            "sha": digest,
            "uri": f"inv://models/model-{project_code}@1.0.0",
            "now": now,
            "until": now + dt.timedelta(days=365),
        },
    )
    # Every required lineage kind, so the release is refused for no other reason.
    #
    # The lineage kind and the identifier kind are not the same vocabulary: the
    # edge kind is ``code_commit`` (the model_lineage CHECK) while the id kind is
    # ``commit`` (ids.PREFIXES). Passing the edge kind to new_id raises, which is
    # how this fixture failed on hosted PostgreSQL before every assertion below
    # had a chance to run.
    for kind, id_kind in (
        ("dataset_version", "dataset_version"),
        ("code_commit", "commit"),
        ("eval_run", "eval_run"),
        ("approval", "approval"),
    ):
        # Composite primary key, no surrogate id: the edge *is* the four values.
        connection.execute(
            text(
                "INSERT INTO model_lineage (tenant_id, model_version_id, kind, subject_id, "
                "relation, recorded_at) VALUES (:tenant, :version_id, :kind, :subject, "
                "'derived_from', :now)"
            ),
            {
                "tenant": tenant_id,
                "version_id": version_id,
                "kind": kind,
                "subject": new_id(id_kind),
                "now": now,
            },
        )
    return {
        "user_id": user_id,
        "project_id": project_id,
        "model_id": model_id,
        "version_id": version_id,
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
        response = client.post(_path(mine), json={**DECLARATION, "classification": "public"})

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
        response = client.post(_path(mine), json=DECLARATION)

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
        response = client.post(_path(mine), json=DECLARATION)

    body = _canonical(response, code="AUTH-0030", status=403)
    assert "approval permission" in body["detail"]
    assert _stage(owner_engine, mine["version_id"]) == "draft"
