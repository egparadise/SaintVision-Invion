"""Real PostgreSQL nodes for the lineage read routes (S10-DB design §10, 30-37).

These are the ones a stand-in session cannot establish: RLS hiding another
tenant's rows, the 403/404 split against real grants, two dataset versions
converging on one model version through a real join, and the page boundary.

The design's other two real-PostgreSQL items -- the query plan and the concurrent
index retry -- travel with the migration, which is a separate PR on top of the
MLflow mirror migration because the coordinator fixed one migration order. They
are not here because the index is not in this diff.

Rows are inserted through ``Base.metadata`` rather than as raw SQL, so an unknown
column and an omitted required column both fail where they are written, and every
``new_id`` kind is an entity kind from ``ids.PREFIXES`` -- a different vocabulary
from the ``model_lineage`` edge kind, where ``code_commit``'s row has the id kind
``commit``. A PG-free test runs this file's seed against a recording connection,
because the release card lost two hosted rounds to fixture mistakes of exactly
that shape.
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



def _digest() -> str:
    return uuid.uuid4().hex + uuid.uuid4().hex


def _insert(connection, table_name, **values):
    """Insert through the model metadata, so a wrong column cannot reach hosted CI.

    Raw SQL in a fixture is checked by PostgreSQL and nowhere else. The release
    card spent two hosted rounds learning things the schema already knew, so this
    builds each statement from ``Base.metadata``: an unknown column name fails
    where it is written, and so does an omitted column that has no default.
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


#: The edge kind is the ``model_lineage`` vocabulary; the identifier kind is
#: ``ids.PREFIXES``. They are not the same: the edge kind ``code_commit`` names a
#: row whose id kind is ``commit``, and ``container_image``'s is ``image``.
ID_KINDS = {
    "dataset_version": "dataset_version",
    "code_commit": "commit",
    "container_image": "image",
    "eval_run": "eval_run",
    "approval": "approval",
}


def _seed(
    connection,
    *,
    tenant_id,
    now,
    project_code,
    role="operator",
    digest=None,
    edge_kinds=("dataset_version", "code_commit", "eval_run", "approval"),
    dataset_versions=1,
    with_deployment=False,
    dataset_project_id=None,
):
    """One project with a member, a model version, its edges and its datasets.

    These routes only read, so an edge is enough for the kinds this API counts
    rather than describes -- ``missing`` is computed from the edges and the
    count-only kinds are never resolved to a row. The dataset versions and the
    deployment are real rows, because those two are the detail the response
    carries and a join is what proves they belong to this project.

    ``dataset_project_id`` puts the dataset in a *different* project while the
    edge still points at it, which is how a cross-project subject is produced:
    the write path checks neither the subject's project nor its existence.
    """
    user_id = new_id("user")
    project_id = new_id("project")
    model_id = new_id("model")
    version_id = new_id("model_version")
    dataset_id = new_id("dataset")
    digest = digest or _digest()

    _insert(
        connection,
        "users",
        user_id=user_id,
        tenant_id=tenant_id,
        external_subject=f"lineage-{project_code}",
        display_name=f"lineage-{project_code}",
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
    _insert(
        connection,
        "model_versions",
        model_version_id=version_id,
        tenant_id=tenant_id,
        model_id=model_id,
        version="1.0.0",
        stage="released",
        content_sha256=_digest(),
        byte_size=1,
        uri=f"inv://models/model-{project_code}@1.0.0",
        # A released row must carry both, by table CHECK.
        verified_at=now,
        retention_pinned_until=now + dt.timedelta(days=365),
        created_at=now,
    )
    _insert(
        connection,
        "datasets",
        dataset_id=dataset_id,
        tenant_id=tenant_id,
        project_id=dataset_project_id or project_id,
        name=f"dataset-{project_code}",
        created_at=now,
    )

    dataset_version_ids = []
    for index in range(dataset_versions):
        dataset_version_id = new_id("dataset_version")
        dataset_version_ids.append(dataset_version_id)
        _insert(
            connection,
            "dataset_versions",
            dataset_version_id=dataset_version_id,
            tenant_id=tenant_id,
            dataset_id=dataset_id,
            version=f"2026-09-{index + 1:02d}",
            # The same bytes under more than one version, which is the case the
            # reverse lookup has to return as a list.
            content_sha256=digest,
            byte_size=1,
            record_count=1,
            uri=f"inv://datasets/dataset-{project_code}@{index}",
            created_at=now,
        )

    for kind in edge_kinds:
        subjects = (
            dataset_version_ids if kind == "dataset_version" else [new_id(ID_KINDS[kind])]
        )
        for subject in subjects:
            _insert(
                connection,
                "model_lineage",
                tenant_id=tenant_id,
                model_version_id=version_id,
                kind=kind,
                subject_id=subject,
                relation="derived_from",
                recorded_at=now,
            )

    deployment_id = None
    if with_deployment:
        deployment_id = new_id("deployment")
        _insert(
            connection,
            "deployments",
            deployment_id=deployment_id,
            tenant_id=tenant_id,
            model_version_id=version_id,
            environment="lab",
            status="active",
            deployed_digest=_digest(),
            # Nothing reaches an environment without a recorded approval, by
            # table CHECK.
            approval_id=new_id("approval"),
            deployed_by_user_id=user_id,
            deployed_at=now,
        )

    return {
        "user_id": user_id,
        "project_id": project_id,
        "model_id": model_id,
        "version_id": version_id,
        "dataset_id": dataset_id,
        "dataset_version_ids": dataset_version_ids,
        "digest": digest,
        "deployment_id": deployment_id,
    }


def _client(app_engine, *, tenant_id, user_id, now):
    app = create_app(
        engine=app_engine,
        settings=Settings(database_url="test-only"),
        verifier=StaticPrincipalVerifier({}, allow_outside_dev=True),
        clock=lambda: now,
        check_partitions_on_startup=False,
    )
    app.dependency_overrides[get_principal] = lambda: Principal(
        user_id=user_id, tenant_id=tenant_id, external_subject="synthetic-lineage"
    )
    return TestClient(app, raise_server_exceptions=False)


def _trace_path(project_id, model_id):
    return f"/v1/projects/{project_id}/models/{model_id}/versions/1.0.0/lineage"


def _reverse_path(project_id, digest):
    return (
        f"/v1/projects/{project_id}/lineage/dataset-versions/by-digest/{digest}"
        "/model-versions"
    )


def _canonical(response, *, code, status):
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == set(CANONICAL_KEYS), body
    assert body["code"] == code
    return body


def test_30_another_tenants_model_version_and_digest_are_not_visible(
    owner_engine, app_engine, two_tenants, frozen_now
):
    """RLS keeps the rows out of reach; the answer says nothing more."""
    tenant_a, tenant_b = two_tenants
    with owner_engine.begin() as connection:
        theirs = _seed(connection, tenant_id=tenant_b, now=frozen_now, project_code="theirs")
        mine = _seed(connection, tenant_id=tenant_a, now=frozen_now, project_code="mine")

    with _client(
        app_engine, tenant_id=tenant_a, user_id=mine["user_id"], now=frozen_now
    ) as client:
        # Their project: not visible at all, which is the same answer an absent
        # project gets.
        _canonical(
            client.get(_trace_path(theirs["project_id"], theirs["model_id"])),
            code="AUTH-0030",
            status=403,
        )
        # Their model under my project: one 404.
        _canonical(
            client.get(_trace_path(mine["project_id"], theirs["model_id"])),
            code="RES-0004",
            status=404,
        )
        # Their digest under my project: the same 404, and their ids appear nowhere.
        body = _canonical(
            client.get(_reverse_path(mine["project_id"], theirs["digest"])),
            code="RES-0004",
            status=404,
        )
        assert theirs["dataset_version_ids"][0] not in str(body)


def test_31_a_project_without_a_grant_is_403_and_a_missing_target_inside_one_is_404(
    owner_engine, app_engine, two_tenants, frozen_now
):
    tenant_a, _ = two_tenants
    with owner_engine.begin() as connection:
        mine = _seed(connection, tenant_id=tenant_a, now=frozen_now, project_code="granted")
        other = _seed(connection, tenant_id=tenant_a, now=frozen_now, project_code="ungranted")

    with _client(
        app_engine, tenant_id=tenant_a, user_id=mine["user_id"], now=frozen_now
    ) as client:
        _canonical(
            client.get(_trace_path(other["project_id"], other["model_id"])),
            code="AUTH-0030",
            status=403,
        )
        # Inside the project I do hold, an absent model is 404, not 403.
        _canonical(
            client.get(_trace_path(mine["project_id"], new_id("model"))),
            code="RES-0004",
            status=404,
        )


def test_32_a_cross_project_subject_and_an_absent_subject_read_identically(
    owner_engine, app_engine, two_tenants, frozen_now
):
    """The existence oracle this design closes, checked against a real join."""
    tenant_a, _ = two_tenants
    with owner_engine.begin() as connection:
        elsewhere = _seed(
            connection, tenant_id=tenant_a, now=frozen_now, project_code="elsewhere"
        )
        # Its dataset lives in another project, but the edge still points at it.
        crossed = _seed(
            connection,
            tenant_id=tenant_a,
            now=frozen_now,
            project_code="crossed",
            edge_kinds=("dataset_version",),
            dataset_project_id=elsewhere["project_id"],
        )
        # Its edge points at a dataset version that does not exist at all.
        absent = _seed(
            connection,
            tenant_id=tenant_a,
            now=frozen_now,
            project_code="absent",
            edge_kinds=(),
        )
        _insert(
            connection,
            "model_lineage",
            tenant_id=tenant_a,
            model_version_id=absent["version_id"],
            kind="dataset_version",
            # No such row anywhere: the edge is the only thing that exists.
            subject_id=new_id("dataset_version"),
            relation="derived_from",
            recorded_at=frozen_now,
        )

    with _client(
        app_engine, tenant_id=tenant_a, user_id=crossed["user_id"], now=frozen_now
    ) as client:
        crossed_body = client.get(
            _trace_path(crossed["project_id"], crossed["model_id"])
        ).json()
    with _client(
        app_engine, tenant_id=tenant_a, user_id=absent["user_id"], now=frozen_now
    ) as client:
        absent_body = client.get(
            _trace_path(absent["project_id"], absent["model_id"])
        ).json()

    for body in (crossed_body, absent_body):
        assert body["datasets"] == []
        assert body["unresolved"] == [{"kind": "dataset_version", "count": 1}]
    # Everything that could tell the two apart is identical.
    variable = {"modelVersionId", "version", "contentSha256", "producedByRunId"}
    assert {k: v for k, v in crossed_body.items() if k not in variable} == {
        k: v for k, v in absent_body.items() if k not in variable
    }
    assert elsewhere["dataset_version_ids"][0] not in str(crossed_body)


def test_33_two_dataset_versions_converging_return_the_model_version_once(
    owner_engine, app_engine, two_tenants, frozen_now
):
    tenant_a, _ = two_tenants
    digest = _digest()
    with owner_engine.begin() as connection:
        seeded = _seed(
            connection,
            tenant_id=tenant_a,
            now=frozen_now,
            project_code="converging",
            digest=digest,
            dataset_versions=2,
            edge_kinds=("dataset_version",),
        )

    with _client(
        app_engine, tenant_id=tenant_a, user_id=seeded["user_id"], now=frozen_now
    ) as client:
        body = client.get(_reverse_path(seeded["project_id"], digest)).json()

    assert sorted(body["datasetVersionIds"]) == sorted(seeded["dataset_version_ids"])
    assert len(body["datasetVersionIds"]) == 2
    assert [item["modelVersionId"] for item in body["items"]] == [seeded["version_id"]]
    assert body["unresolvedModelVersions"] == 0
    assert body["complete"] is True


def test_34_the_reverse_page_boundary_neither_repeats_nor_drops(
    owner_engine, app_engine, two_tenants, frozen_now
):
    """Three model versions from one digest, read one page at a time."""
    tenant_a, _ = two_tenants
    digest = _digest()
    with owner_engine.begin() as connection:
        seeded = _seed(
            connection,
            tenant_id=tenant_a,
            now=frozen_now,
            project_code="paging",
            digest=digest,
            edge_kinds=("dataset_version",),
        )
        expected = {seeded["version_id"]}
        for index in range(2):
            extra_version = new_id("model_version")
            expected.add(extra_version)
            _insert(
                connection,
                "model_versions",
                model_version_id=extra_version,
                tenant_id=tenant_a,
                model_id=seeded["model_id"],
                version=f"2.{index}.0",
                # draft, so the release CHECK does not require verify and pin.
                stage="draft",
                content_sha256=_digest(),
                byte_size=1,
                uri=f"inv://models/paging@2.{index}.0",
                created_at=frozen_now,
            )
            _insert(
                connection,
                "model_lineage",
                tenant_id=tenant_a,
                model_version_id=extra_version,
                kind="dataset_version",
                # The same dataset version as the seeded model version: three
                # model versions converge on one digest.
                subject_id=seeded["dataset_version_ids"][0],
                relation="derived_from",
                recorded_at=frozen_now,
            )

    seen: list[str] = []
    with _client(
        app_engine, tenant_id=tenant_a, user_id=seeded["user_id"], now=frozen_now
    ) as client:
        cursor = None
        for _ in range(5):
            path = _reverse_path(seeded["project_id"], digest) + "?limit=2"
            if cursor:
                path += f"&cursor={cursor}"
            body = client.get(path).json()
            seen.extend(item["modelVersionId"] for item in body["items"])
            cursor = body["nextCursor"]
            if not cursor:
                break

    assert len(seen) == len(set(seen)), "no identifier is returned twice"
    assert set(seen) == expected, "and none is dropped at a page boundary"


def test_37_the_positive_control_reports_detail_and_admits_its_own_limit(
    owner_engine, app_engine, two_tenants, frozen_now
):
    """Dataset and deployment detail arrive; the rest is a count, and says so."""
    tenant_a, _ = two_tenants
    with owner_engine.begin() as connection:
        seeded = _seed(
            connection,
            tenant_id=tenant_a,
            now=frozen_now,
            project_code="complete",
            with_deployment=True,
        )

    with _client(
        app_engine, tenant_id=tenant_a, user_id=seeded["user_id"], now=frozen_now
    ) as client:
        body = client.get(_trace_path(seeded["project_id"], seeded["model_id"])).json()

    assert [row["datasetVersionId"] for row in body["datasets"]] == seeded[
        "dataset_version_ids"
    ]
    assert [row["deploymentId"] for row in body["deployments"]] == [seeded["deployment_id"]]
    assert body["missing"] == []
    # Three required kinds cannot be shown here, so this is never fully traceable,
    # and the flag says the cause is the boundary rather than a recording gap.
    assert body["fullyTraceable"] is False
    assert body["traceabilityLimitedByScope"] is True
    assert {entry["kind"] for entry in body["unresolved"]} == {
        "code_commit",
        "eval_run",
        "approval",
    }
    # No user identifier and no free text on a deployment.
    assert "deployedByUserId" not in body["deployments"][0]
    assert seeded["user_id"] not in str(body)
    # The kinds that were only counted have no arrays at all.
    for absent in ("commits", "images", "evaluations", "approvals"):
        assert absent not in body
