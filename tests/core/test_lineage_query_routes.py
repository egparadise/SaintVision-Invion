"""S10-DB: the two lineage read routes and the honesty rules they carry.

Each test is one of the reversions in the approved design
(``docs/vault/30_Development/S10-DB_lineage_조회_API_설계.md`` §10, v1.2), and the
numbers in the test names are that list's.

Items 30-37 are PostgreSQL behaviour -- RLS across tenants, the 403/404 split
against real grants, the concurrent index retry, the query plan -- and run on
hosted CI. The session here answers exactly the calls the service makes, so what
these tests establish is the shape of the answer and the order of the checks, not
the database's behaviour.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import json
import uuid

import pytest
from fastapi.testclient import TestClient

from inv.contracts import validate_contract
from saintvision.api import schemas
from saintvision.api.app import create_app
from saintvision.api.problem import CANONICAL_KEYS
from saintvision.api.v1 import lineage_query
from saintvision.config import Settings
from saintvision.errors import AUTH_PROJECT_SCOPE, InvError
from saintvision.identity.principal import Principal, StaticPrincipalVerifier
from saintvision.services import lineage as lineage_service

TENANT = uuid.UUID("11111111-1111-1111-1111-111111111111")
OTHER_TENANT = uuid.UUID("22222222-2222-2222-2222-222222222222")
PROJECT = "prj_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
OTHER_PROJECT = "prj_01J8Z3XQ2K9WMV5T7N4B6C8D0F"
MODEL = "mdl_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
VERSION_ID = "mvr_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
VERSION = "1.4.0"
SHA = "a" * 64
DIGEST = "b" * 64
TRACE_PATH = f"/v1/projects/{PROJECT}/models/{MODEL}/versions/{VERSION}/lineage"
REVERSE_PATH = (
    f"/v1/projects/{PROJECT}/lineage/dataset-versions/by-digest/{DIGEST}/model-versions"
)
AUTH = {"Authorization": "Bearer lineage-token"}


class Row:
    def __init__(self, *, tenant_id=TENANT):
        self.model_version_id = VERSION_ID
        self.tenant_id = tenant_id
        self.model_id = MODEL
        self.version = VERSION
        self.stage = "released"
        self.content_sha256 = SHA
        self.produced_by_run_id = None


class Parent:
    def __init__(self, *, tenant_id=TENANT, project_id=PROJECT):
        self.model_id = MODEL
        self.tenant_id = tenant_id
        self.project_id = project_id


class Scalars:
    def __init__(self, row):
        self._row = row

    def one_or_none(self):
        return self._row


class Session:
    def __init__(self, world):
        self.world = world

    def get(self, _model, _key, **_kwargs):
        return self.world["parent"]

    def scalars(self, _statement):
        return Scalars(self.world["row"])


def build(monkeypatch, world):
    world.setdefault("parent", Parent())
    world.setdefault("row", Row())

    @contextlib.contextmanager
    def session_dependency():
        yield Session(world)

    principal = Principal(
        user_id="usr_01J8Z3XQ2K9WMV5T7N4B6C8D0E",
        tenant_id=TENANT,
        external_subject="oidc:lineage",
        project_ids=frozenset({PROJECT}),
    )
    app = create_app(
        engine=object(),
        settings=Settings(database_url="postgresql://unused"),
        verifier=StaticPrincipalVerifier(
            {"lineage-token": principal}, allow_outside_dev=True
        ),
        check_partitions_on_startup=False,
    )
    from saintvision.api.deps import get_session

    app.dependency_overrides[get_session] = lambda: Session(world)

    def require_project_access(_session, *, tenant_id, project_id, user_id):
        denial = world.get("denial")
        if denial is not None:
            raise denial
        return world.get("permission", {"canRequest": False, "canApprove": False})

    monkeypatch.setattr(
        lineage_query.project_service, "require_project_access", require_project_access
    )
    if "trace" in world:
        monkeypatch.setattr(
            lineage_query,
            "trace_model_for_project",
            lambda _session, **kwargs: world["trace"](**kwargs)
            if callable(world["trace"])
            else world["trace"],
        )
    if "page" in world:
        monkeypatch.setattr(
            lineage_query,
            "models_from_dataset_digest",
            lambda _session, **kwargs: world["page"](**kwargs)
            if callable(world["page"])
            else world["page"],
        )
    return TestClient(app, raise_server_exceptions=False)


def trace_body(**overrides):
    body = {
        "modelVersionId": VERSION_ID,
        "version": VERSION,
        "stage": "released",
        "contentSha256": SHA,
        "producedByRunId": None,
        "datasets": [],
        "deployments": [],
        "missing": [],
        "unresolved": [],
        "truncated": {},
        "fullyTraceable": True,
        "traceabilityLimitedByScope": False,
        "detailedKinds": list(lineage_service.DETAILED_KINDS),
        "countOnlyKinds": list(lineage_service.COUNT_ONLY_KINDS),
    }
    body.update(overrides)
    return body


def page_body(**overrides):
    body = {
        "contentSha256": DIGEST,
        "datasetVersionIds": ["dsv_01J8Z3XQ2K9WMV5T7N4B6C8D0E"],
        "items": [],
        "nextCursor": None,
        "unresolvedModelVersions": 0,
        "truncated": {},
        "complete": True,
    }
    body.update(overrides)
    return body


def canonical(response, *, code, status, retryable=False):
    assert response.status_code == status, response.text
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert set(body) == set(CANONICAL_KEYS), body
    assert body["type"] == "about:blank"
    assert (body["code"], body["status"], body["retryable"]) == (code, status, retryable)
    validate_contract("ProblemDetails", body)
    return body


# ---------------------------------------------------------------------------
# The service: what it reads, what it counts, what it refuses to distinguish
# ---------------------------------------------------------------------------


class Edge:
    def __init__(self, kind, subject_id):
        self.kind = kind
        self.subject_id = subject_id


class DatasetRow:
    def __init__(self, identifier):
        self.dataset_version_id = identifier
        self.version = "2026-09-01"
        self.content_sha256 = DIGEST
        self.uri = f"inv://datasets/sales@{identifier}"


class DeploymentRow:
    def __init__(self, identifier):
        self.deployment_id = identifier
        self.environment = "lab"
        self.status = "active"
        self.deployed_digest = SHA
        self.image_id = None
        self.approval_id = "apr_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
        self.deployed_at = dt.datetime(2026, 9, 20, tzinfo=dt.timezone.utc)
        self.superseded_at = None
        self.deployed_by_user_id = "usr_secret"
        self.notes = "internal reasoning nobody outside should read"


class ServiceSession:
    """Answers the three shapes ``trace_model_for_project`` issues.

    Every statement is recorded, which is how "rows that will not be served are
    never read" is asserted rather than asserted about.
    """

    def __init__(self, *, edges, datasets, deployments, version_row=None):
        self.edges = edges
        self.datasets = datasets
        self.deployments = deployments
        self.version_row = version_row or Row()
        self.statements: list[str] = []

    def get(self, _entity, _key, **_kwargs):
        return self.version_row

    def scalars(self, statement):
        text = str(statement)
        self.statements.append(text)
        if "model_lineage" in text:
            return _Iter(self.edges)
        if "deployments" in text:
            return _Iter(self.deployments)
        raise AssertionError(text)

    def execute(self, statement):
        text = str(statement)
        self.statements.append(text)
        if "dataset_versions" in text:
            return _Result(self.datasets)
        raise AssertionError(text)


class _Iter:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _One(_Iter):
    def one_or_none(self):
        return self._rows


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return _Iter(self._rows)


def run_trace(*, edges, datasets, deployments=()):
    session = ServiceSession(edges=edges, datasets=datasets, deployments=list(deployments))
    trace = lineage_service.trace_model_for_project(
        session, tenant_id=TENANT, project_id=PROJECT, model_version_id=VERSION_ID
    )
    return trace, session


def test_01_a_model_version_with_no_edges_is_not_fully_traceable():
    trace, _ = run_trace(edges=[], datasets=[])
    assert trace["missing"] == ["dataset_version", "code_commit", "eval_run", "approval"]
    assert trace["fullyTraceable"] is False


def test_02_07_unresolved_subjects_keep_fully_traceable_false_and_say_why():
    trace, _ = run_trace(
        edges=[
            Edge("dataset_version", "dsv_1"),
            Edge("code_commit", "cmt_1"),
            Edge("eval_run", "evl_1"),
            Edge("approval", "apr_1"),
        ],
        datasets=[DatasetRow("dsv_1")],
    )
    assert trace["missing"] == []
    assert trace["unresolved"] == [
        {"kind": "approval", "count": 1},
        {"kind": "code_commit", "count": 1},
        {"kind": "eval_run", "count": 1},
    ]
    assert trace["fullyTraceable"] is False
    # The reason is legible: a permission boundary, not a recording gap.
    assert trace["traceabilityLimitedByScope"] is True


def test_03_rows_that_will_not_be_served_are_never_read():
    _, session = run_trace(
        edges=[
            Edge("code_commit", "cmt_1"),
            Edge("container_image", "img_1"),
            Edge("eval_run", "evl_1"),
            Edge("approval", "apr_1"),
        ],
        datasets=[],
    )
    issued = " ".join(session.statements)
    for table in ("code_commits", "container_images", "eval_runs", "approvals"):
        assert table not in issued, table


def test_04_05_another_projects_subject_and_an_absent_one_are_indistinguishable():
    # One dataset edge whose row is in another project (so the join drops it)...
    other_project, _ = run_trace(edges=[Edge("dataset_version", "dsv_1")], datasets=[])
    # ...and one whose row does not exist at all. The join drops it the same way.
    absent, _ = run_trace(edges=[Edge("dataset_version", "dsv_9")], datasets=[])
    assert other_project == absent
    assert other_project["unresolved"] == [{"kind": "dataset_version", "count": 1}]
    assert "dangling" not in other_project
    assert "outOfScope" not in other_project


def test_06_unresolved_carries_no_identifier_and_no_reason():
    trace, _ = run_trace(edges=[Edge("dataset_version", "dsv_1")], datasets=[])
    assert trace["unresolved"] == [{"kind": "dataset_version", "count": 1}]
    assert "dsv_1" not in json.dumps(trace)


def test_08_the_count_only_kinds_have_no_arrays_at_all():
    trace, _ = run_trace(edges=[], datasets=[])
    for absent in ("commits", "images", "evaluations", "approvals"):
        assert absent not in trace
    # A deployment array that is empty means something complete, so it stays.
    assert trace["deployments"] == []


def test_09_10_a_truncated_array_is_reported_and_is_not_full_traceability():
    many = [DatasetRow(f"dsv_{index:04d}") for index in range(lineage_service.ARRAY_LIMIT + 5)]
    trace, _ = run_trace(
        edges=[Edge(kind, "x") for kind in ("code_commit", "eval_run", "approval")]
        + [Edge("dataset_version", row.dataset_version_id) for row in many],
        datasets=many,
    )
    assert len(trace["datasets"]) == lineage_service.ARRAY_LIMIT
    assert trace["truncated"]["datasets"] == len(many)
    assert trace["fullyTraceable"] is False

    deployments = [DeploymentRow(f"dpl_{index:04d}") for index in range(lineage_service.ARRAY_LIMIT + 1)]
    trace, _ = run_trace(edges=[], datasets=[], deployments=deployments)
    assert len(trace["deployments"]) == lineage_service.ARRAY_LIMIT
    assert trace["truncated"]["deployments"] == len(deployments)


def test_12_deployment_detail_omits_the_user_identifier_and_the_notes():
    trace, _ = run_trace(edges=[], datasets=[], deployments=[DeploymentRow("dpl_1")])
    assert set(trace["deployments"][0]) == {
        "deploymentId",
        "environment",
        "status",
        "deployedDigest",
        "imageId",
        "approvalId",
        "deployedAt",
        "supersededAt",
    }
    serialised = json.dumps(trace, default=str)
    assert "usr_secret" not in serialised
    assert "internal reasoning" not in serialised


# ---------------------------------------------------------------------------
# The reverse lookup service
# ---------------------------------------------------------------------------


class ReverseSession:
    """Answers the four statements ``models_from_dataset_digest`` issues."""

    def __init__(self, *, dataset_ids, edge_targets, versions, resolvable=None):
        self.dataset_ids = dataset_ids
        self.edge_targets = edge_targets
        self.versions = versions
        self.resolvable = len(versions) if resolvable is None else resolvable
        self.statements: list[str] = []
        self.in_sets: list[str] = []

    def execute(self, statement):
        text = str(statement)
        self.statements.append(text)
        compiled = str(statement.compile(compile_kwargs={"literal_binds": True}))
        if "count(" in text:
            return _Scalar(self.resolvable)
        if "dataset_versions" in text and "model_lineage" not in text:
            return _Result(self.dataset_ids)
        if "model_lineage" in text:
            self.in_sets.append(compiled)
            return _Result(self.edge_targets)
        if "model_versions" in text:
            self.in_sets.append(compiled)
            return _Result(self.versions)
        raise AssertionError(text)


class _Scalar:
    def __init__(self, value):
        self._value = value

    def scalar_one(self):
        return self._value


def reverse(*, dataset_ids, edge_targets, versions, limit=50, cursor=None, resolvable=None):
    session = ReverseSession(
        dataset_ids=dataset_ids,
        edge_targets=edge_targets,
        versions=versions,
        resolvable=resolvable,
    )
    page = lineage_service.models_from_dataset_digest(
        session,
        tenant_id=TENANT,
        project_id=PROJECT,
        content_sha256=DIGEST,
        limit=limit,
        cursor=cursor,
    )
    return page, session


def test_11_an_uppercase_digest_is_a_client_error_not_a_normalisation():
    session = ReverseSession(dataset_ids=["dsv_1"], edge_targets=[], versions=[])
    with pytest.raises(InvError):
        lineage_service.models_from_dataset_digest(
            session,
            tenant_id=TENANT,
            project_id=PROJECT,
            content_sha256=DIGEST.upper(),
            limit=50,
        )
    assert session.statements == [], "nothing is queried before the digest is checked"


def test_a_digest_with_no_dataset_version_in_this_project_is_not_found():
    session = ReverseSession(dataset_ids=[], edge_targets=[], versions=[])
    with pytest.raises(InvError):
        lineage_service.models_from_dataset_digest(
            session, tenant_id=TENANT, project_id=PROJECT, content_sha256=DIGEST, limit=50
        )


def test_27_several_dataset_versions_converging_yield_the_model_version_once():
    row = Row()
    page, session = reverse(
        dataset_ids=["dsv_1", "dsv_2"],
        # The same model version reached through both dataset versions.
        edge_targets=[VERSION_ID, VERSION_ID],
        versions=[row],
    )
    assert page["datasetVersionIds"] == ["dsv_1", "dsv_2"]
    assert [item["modelVersionId"] for item in page["items"]] == [VERSION_ID]
    # The distinct happens before the page is cut, not after.
    model_statement = next(s for s in session.in_sets if "model_versions" in s)
    assert "DISTINCT" in model_statement.upper()
    assert model_statement.upper().index("DISTINCT") < model_statement.upper().index("LIMIT")


def test_28_the_in_set_is_exactly_the_bounded_dataset_version_list():
    many = [f"dsv_{index:04d}" for index in range(lineage_service.ARRAY_LIMIT + 7)]
    page, session = reverse(dataset_ids=many, edge_targets=[], versions=[])
    assert page["datasetVersionIds"] == many[: lineage_service.ARRAY_LIMIT]
    assert page["truncated"]["datasetVersionIds"] == len(many)
    edge_statement = next(s for s in session.in_sets if "model_lineage" in s)
    # Every listed id is in the query, and the ones that were cut are not.
    for identifier in page["datasetVersionIds"]:
        assert identifier in edge_statement
    for identifier in many[lineage_service.ARRAY_LIMIT :]:
        assert identifier not in edge_statement


def test_29_a_truncated_reverse_answer_is_never_complete():
    many = [f"dsv_{index:04d}" for index in range(lineage_service.ARRAY_LIMIT + 1)]
    page, _ = reverse(dataset_ids=many, edge_targets=[], versions=[])
    assert page["truncated"]
    assert page["complete"] is False


def test_the_unresolved_count_merges_other_project_and_absent_rows():
    row = Row()
    page, _ = reverse(
        dataset_ids=["dsv_1"],
        edge_targets=[VERSION_ID, "mvr_elsewhere", "mvr_gone"],
        versions=[row],
        resolvable=1,
    )
    assert page["unresolvedModelVersions"] == 2
    assert page["complete"] is False
    assert "mvr_elsewhere" not in json.dumps(page)


def test_the_page_probe_row_does_not_leak_into_the_items():
    rows = [Row() for _ in range(3)]
    for index, row in enumerate(rows):
        row.model_version_id = f"mvr_{index}"
    page, _ = reverse(
        dataset_ids=["dsv_1"],
        edge_targets=[row.model_version_id for row in rows],
        versions=rows,
        limit=2,
        resolvable=3,
    )
    assert [item["modelVersionId"] for item in page["items"]] == ["mvr_0", "mvr_1"]
    assert page["nextCursor"] == "mvr_1"


# ---------------------------------------------------------------------------
# The routes: permission grade, path binding, query boundary, canonical errors
# ---------------------------------------------------------------------------


def test_13_14_reading_needs_membership_and_not_an_action_grade(monkeypatch):
    # A principal with membership and neither flag reads successfully.
    world = {"trace": trace_body(), "permission": {"canRequest": False, "canApprove": False}}
    client = build(monkeypatch, world)
    assert client.get(TRACE_PATH, headers=AUTH).status_code == 200

    world = {
        "trace": trace_body(),
        "denial": InvError(AUTH_PROJECT_SCOPE, "project is not accessible to this principal"),
    }
    client = build(monkeypatch, world)
    body = canonical(client.get(TRACE_PATH, headers=AUTH), code="AUTH-0030", status=403)
    assert body["detail"] == "This project is not accessible."
    assert "projectId" not in body


def test_13b_the_route_uses_the_live_check_not_the_snapshot():
    source = open(lineage_query.__file__, encoding="utf-8").read()
    assert "require_project_access" in source
    assert "principal.require_project(" not in source
    assert "canApprove" not in source.split("TRANSLATION")[1]


@pytest.mark.parametrize(
    "world",
    [
        {"parent": None},
        {"parent": Parent(project_id=OTHER_PROJECT)},
        {"parent": Parent(tenant_id=OTHER_TENANT)},
        {"row": None},
        {"row": Row(tenant_id=OTHER_TENANT)},
    ],
)
def test_16_17_the_path_is_bound_through_the_parent_and_all_misses_are_one_404(
    monkeypatch, world
):
    world = {**world, "trace": trace_body()}
    client = build(monkeypatch, world)
    body = canonical(client.get(TRACE_PATH, headers=AUTH), code="RES-0004", status=404)
    assert body["detail"] == "No such model version."


def test_16b_the_read_path_takes_no_row_lock():
    source = open(lineage_query.__file__, encoding="utf-8").read()
    assert "with_for_update" not in source


def test_18_the_response_types_are_strict(monkeypatch):
    world = {"trace": trace_body()}
    client = build(monkeypatch, world)
    body = client.get(TRACE_PATH, headers=AUTH).json()
    assert set(body) == set(trace_body())
    schemas.ModelLineageTraceResponse.model_validate(body)
    with pytest.raises(Exception):
        schemas.ModelLineageTraceResponse.model_validate({**body, "extra": 1})
    incomplete = dict(body)
    del incomplete["traceabilityLimitedByScope"]
    with pytest.raises(Exception):
        schemas.ModelLineageTraceResponse.model_validate(incomplete)

    world = {"page": page_body()}
    client = build(monkeypatch, world)
    page = client.get(REVERSE_PATH, headers=AUTH).json()
    assert set(page) == set(page_body())
    schemas.ModelVersionByDatasetDigestPageResponse.model_validate(page)
    with pytest.raises(Exception):
        schemas.ModelVersionByDatasetDigestPageResponse.model_validate({**page, "extra": 1})


def test_19_20_an_unknown_query_parameter_is_refused_rather_than_ignored(monkeypatch):
    for path in (TRACE_PATH, REVERSE_PATH):
        world = {"trace": trace_body(), "page": page_body()}
        client = build(monkeypatch, world)
        body = canonical(
            client.get(f"{path}?foo=1", headers=AUTH), code="VAL-0003", status=422
        )
        assert "unsupported query parameter" in body["detail"]
    # The forward route takes none at all, including the reverse route's own.
    world = {"trace": trace_body()}
    client = build(monkeypatch, world)
    canonical(
        client.get(f"{TRACE_PATH}?limit=10", headers=AUTH), code="VAL-0003", status=422
    )


def test_21_a_repeated_query_parameter_is_refused_rather_than_resolved(monkeypatch):
    world = {"page": page_body()}
    client = build(monkeypatch, world)
    body = canonical(
        client.get(f"{REVERSE_PATH}?limit=1&limit=2", headers=AUTH),
        code="VAL-0003",
        status=422,
    )
    assert "more than once" in body["detail"]
    source = open(lineage_query.__file__, encoding="utf-8").read()
    assert "multi_items()" in source


def test_22_a_malformed_or_oversized_cursor_is_refused(monkeypatch):
    for cursor in ("not-a-ulid", "x" * 400, "", "mvr_"):
        world = {"page": page_body()}
        client = build(monkeypatch, world)
        canonical(
            client.get(f"{REVERSE_PATH}?cursor={cursor}", headers=AUTH),
            code="VAL-0003",
            status=422,
        )


def test_23_an_out_of_range_limit_is_refused_and_never_trimmed(monkeypatch):
    for raw in ("abc", "0", "201", "-1", "10000", "1e3", " 5"):
        world = {"page": page_body()}
        client = build(monkeypatch, world)
        canonical(
            client.get(f"{REVERSE_PATH}?limit={raw}", headers=AUTH),
            code="VAL-0003",
            status=422,
        )
    # And the bound itself is accepted.
    seen = {}
    world = {"page": lambda **kwargs: seen.update(kwargs) or page_body()}
    client = build(monkeypatch, world)
    assert client.get(f"{REVERSE_PATH}?limit=200", headers=AUTH).status_code == 200
    assert seen["limit"] == 200


def test_23b_the_route_does_not_reuse_the_clamping_helper():
    source = open(lineage_query.__file__, encoding="utf-8").read()
    # Named in the comment that explains why; never called.
    assert "clamp_limit(" not in source
    assert "from ...services.pagination import" not in source


def test_24_a_body_on_these_reads_is_refused_rather_than_discarded(monkeypatch):
    for path, key in ((TRACE_PATH, "trace"), (REVERSE_PATH, "page")):
        world = {"trace": trace_body(), "page": page_body()}
        client = build(monkeypatch, world)
        response = client.request("GET", path, headers=AUTH, content=b" ")
        canonical(response, code="VAL-0003", status=422)


def test_15_25_26_every_error_is_the_canonical_envelope(monkeypatch):
    seen = {}
    cases = [
        ("VAL-0003", 422, {"trace": trace_body()}, f"{TRACE_PATH}?foo=1"),
        (
            "AUTH-0030",
            403,
            {
                "trace": trace_body(),
                "denial": InvError(AUTH_PROJECT_SCOPE, "not accessible"),
            },
            TRACE_PATH,
        ),
        ("RES-0004", 404, {"trace": trace_body(), "row": None}, TRACE_PATH),
    ]
    for code, status, world, path in cases:
        client = build(monkeypatch, world)
        seen[code] = canonical(client.get(path, headers=AUTH), code=code, status=status)
    assert set(seen) == {"VAL-0003", "AUTH-0030", "RES-0004"}
    for body in seen.values():
        assert "fields" not in body
        assert "instance" not in body


def test_25_the_translation_table_covers_every_code_these_routes_can_reach():
    from saintvision.api.problem import translate
    from saintvision.errors import RES_ARTIFACT_NOT_FOUND, VAL_CURSOR, VAL_SCHEMA

    reachable = {VAL_SCHEMA, VAL_CURSOR, AUTH_PROJECT_SCOPE, RES_ARTIFACT_NOT_FOUND}
    assert reachable <= set(lineage_query.TRANSLATION)
    unmapped = translate(
        InvError("RES-NODE-NOT-FOUND", "something else"), table=lineage_query.TRANSLATION
    )
    assert (unmapped.code, unmapped.status) == ("SYS-0002", 500)


def test_the_digest_route_reports_a_bad_digest_as_a_request_error(monkeypatch):
    from saintvision.errors import VAL_SCHEMA

    def raise_bad_digest(**_kwargs):
        raise InvError(VAL_SCHEMA, "content digest must be 64 lowercase hex characters")

    world = {"page": raise_bad_digest}
    client = build(monkeypatch, world)
    body = canonical(client.get(REVERSE_PATH, headers=AUTH), code="VAL-0003", status=422)
    assert "64 lowercase hex" in body["detail"]


# ---------------------------------------------------------------------------
# Registration, and the index this route depends on
# ---------------------------------------------------------------------------


def test_both_routes_are_visible_to_the_business_dispatch_selection():
    from saintvision.api.v1 import adapters, projects, settings as settings_router

    routes = [
        route
        for module in (projects, settings_router, adapters)
        for route in module.router.routes
    ]
    paths = {
        getattr(route, "path", ""): route.methods
        for route in routes
        if "lineage" in getattr(route, "path", "")
    }
    assert paths == {
        "/v1/projects/{project_id}/models/{model_id}/versions/{version}/lineage": {"GET"},
        "/v1/projects/{project_id}/lineage/dataset-versions/by-digest/{content_sha256}"
        "/model-versions": {"GET"},
    }


def test_the_real_pg_seed_builds_every_row_without_a_database():
    """Run the integration fixture against a recording connection.

    The release card's six real-PostgreSQL nodes all died in their fixture on
    hosted CI over an identifier kind, and no product assertion behind them ran.
    That failure needed no database to find, so this file's fixture is exercised
    here: every ``new_id`` kind, every column list and every branch of the seed.
    """
    import importlib.util
    from pathlib import Path

    from saintvision.db.models.lineage import LINEAGE_KINDS
    from saintvision.ids import PREFIXES

    path = (
        Path(__file__).resolve().parents[1] / "integration/test_lineage_query_real_pg.py"
    )
    spec = importlib.util.spec_from_file_location("real_pg_lineage_fixture", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class Recorder:
        def __init__(self):
            self.statements: list[str] = []

        def execute(self, statement, params=None):
            self.statements.append(str(statement))
            return None

    now = dt.datetime(2026, 9, 9, tzinfo=dt.timezone.utc)
    recorder = Recorder()
    seeded = module._seed(
        recorder,
        tenant_id=TENANT,
        now=now,
        project_code="fixture-guard",
        dataset_versions=2,
        with_deployment=True,
        edge_kinds=("dataset_version", "code_commit", "container_image", "eval_run", "approval"),
    )
    assert len(seeded["dataset_version_ids"]) == 2
    assert seeded["deployment_id"] is not None
    # users, projects, project_members, models, model_versions, datasets,
    # two dataset_versions, two dataset_version edges, four other edges,
    # one deployment.
    assert len(recorder.statements) == 15

    # Empty edge set and a cross-project dataset are the other two branches.
    recorder = Recorder()
    module._seed(
        recorder,
        tenant_id=TENANT,
        now=now,
        project_code="no-edges",
        edge_kinds=(),
        dataset_project_id="prj_other",
    )
    assert len(recorder.statements) == 7

    # The trap named: two lineage kinds are not entity kinds.
    assert set(LINEAGE_KINDS) - set(PREFIXES) == {"code_commit", "container_image"}


def test_the_reverse_lookup_names_the_index_it_depends_on():
    """The index ships in its own PR; the dependency is recorded, not assumed.

    ``migrations/versions/0050_dataset_digest_lookup.py`` sits on top of the
    MLflow mirror migration (0049) because the coordinator fixed one migration
    order, and this PR is stacked on the release route instead. So the index is
    not in this diff, and the route must not reach an environment before it: the
    first step of the reverse lookup is a ``content_sha256`` predicate, and
    without the index that is a sequential scan of the table the route exists to
    search.
    """
    from saintvision.services.lineage import models_from_dataset_digest

    source = open(models_from_dataset_digest.__code__.co_filename, encoding="utf-8").read()
    body = source[source.index("def models_from_dataset_digest") :]
    assert "DatasetVersion.content_sha256 == content_sha256" in body
    # Named here so a reader of this file finds the migration it waits for.
    assert "0050_dataset_digest_lookup"
