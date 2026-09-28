"""W2: the model version registration route, over real HTTP, without a database.

Each test is a reversion: undo the thing it names in
``api/v1/model_versions.py`` and this file fails. The session is a stand-in that
answers exactly the calls the route makes, so what these prove is the route's
*order* and its wire contract -- not the database's behaviour. The database's
part (RLS, the unique constraints actually firing, two concurrent first requests
with one key) is ``tests/integration/test_model_version_register_real_pg.py``
and runs on hosted CI.

The one thing kept real here is ``deps.serialise_idempotent_write``: the lock
key derivation and the position of the lock in the order are the IDEM-6
contract, so a stub of it would test nothing.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import json
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from saintvision.api import schemas
from saintvision.api.app import create_app
from saintvision.api.deps import (
    IDEMPOTENCY_LOCK_NAMESPACE,
    serialise_idempotent_write,
)
from saintvision.api.problem import CANONICAL_KEYS, MAX_REQUEST_BYTES
from saintvision.api.v1 import model_versions
from saintvision.config import Settings
from saintvision.errors import (
    AUTH_PROJECT_SCOPE,
    GRAPH_IDEMPOTENCY_CONFLICT,
    RES_ARTIFACT_NOT_FOUND,
    VAL_SCHEMA,
    InvError,
)
from saintvision.identity.principal import Principal, StaticPrincipalVerifier

TENANT = uuid.UUID("11111111-1111-1111-1111-111111111111")
OTHER_TENANT = uuid.UUID("22222222-2222-2222-2222-222222222222")
PROJECT = "prj_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
OTHER_PROJECT = "prj_01J8Z3XQ2K9WMV5T7N4B6C8D0F"
MODEL = "mdl_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
VERSION_ID = "mdv_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
USER = "usr_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
SHA = "a" * 64
NOW = dt.datetime(2026, 9, 28, 6, 0, tzinfo=dt.timezone.utc)
PATH = f"/v1/projects/{PROJECT}/models/{MODEL}/versions"
KEY = "idem-0001"
AUTH = {"Authorization": "Bearer register-token", "Idempotency-Key": KEY}
BODY = {
    "version": "1.4.0",
    "contentSha256": SHA,
    "uri": "inv://models/demo@1.4.0",
    "byteSize": 4096,
}


class Parent:
    """The columns ``_model_in_project`` reads. Not an ORM object."""

    def __init__(self, *, tenant_id=TENANT, project_id=PROJECT):
        self.model_id = MODEL
        self.tenant_id = tenant_id
        self.project_id = project_id


class Row:
    """What ``register_model_version`` returns."""

    def __init__(self, *, version="1.4.0", content_sha256=SHA, byte_size=4096):
        self.model_version_id = VERSION_ID
        self.tenant_id = TENANT
        self.model_id = MODEL
        self.version = version
        self.stage = "draft"
        self.content_sha256 = content_sha256
        self.byte_size = byte_size
        self.uri = "inv://models/demo@1.4.0"
        self.created_at = NOW


class Session:
    """A session that records what the route asks of it, in order."""

    def __init__(self, world):
        self.world = world

    def execute(self, statement, params=None):
        self.world["log"].append("lock")
        self.world["locks"].append({"sql": str(statement), "params": params})
        return None

    def get(self, _model, _key, **_kwargs):
        self.world["log"].append("model-get")
        return self.world["parent"]


class Factory:
    """A session factory that records how many transactions were opened."""

    def __init__(self, world):
        self.world = world

    def __call__(self):
        world = self.world

        @contextlib.contextmanager
        def session_cm():
            session = Session(world)

            @contextlib.contextmanager
            def begin():
                world["depth"] += 1
                world["spans"] += 1
                try:
                    yield
                finally:
                    world["depth"] -= 1

            session.begin = begin
            yield session

        return session_cm()


def build(monkeypatch, world):
    world.setdefault("parent", Parent())
    world.setdefault("row", Row())
    world.setdefault("permissions", [{"canRequest": True, "canApprove": True}])
    world.setdefault("denials", [])
    world.setdefault("replay", None)
    world.setdefault("replay_error", None)
    world.setdefault("service_error", None)
    world.setdefault("log", [])
    world.setdefault("locks", [])
    world.setdefault("stored", [])
    world.setdefault("audits", [])
    world.setdefault("registered", [])
    world.setdefault("ledger_reads", [])
    world.setdefault("depth", 0)
    world.setdefault("spans", 0)
    world.setdefault("body_depth", [])

    monkeypatch.setattr(model_versions, "make_session_factory", lambda _engine: Factory(world))
    # The shared denial recorder writes through the app's engine, which these
    # tests do not have; recorded here so a 403's audit call is asserted, not lost.
    from saintvision.api import app as app_module

    monkeypatch.setattr(
        app_module,
        "record_denial_out_of_band",
        lambda _engine, **kwargs: world.setdefault("denials_recorded", []).append(kwargs),
    )
    monkeypatch.setattr(
        model_versions, "tenant_scope", lambda _session, _tenant: contextlib.nullcontext()
    )

    calls = {"permission": 0}

    def require_project_access(_session, *, tenant_id, project_id, user_id):
        world["log"].append("permission")
        index = calls["permission"]
        calls["permission"] += 1
        denial = world["denials"][index] if index < len(world["denials"]) else None
        if denial is not None:
            raise denial
        grants = world["permissions"]
        return grants[index] if index < len(grants) else grants[-1]

    monkeypatch.setattr(
        model_versions.project_service, "require_project_access", require_project_access
    )

    original_read = model_versions.read_bounded_body

    async def read_bounded_body(request, **kwargs):
        world["body_depth"].append(world["depth"])
        world["log"].append("body-read")
        return await original_read(request, **kwargs)

    monkeypatch.setattr(model_versions, "read_bounded_body", read_bounded_body)

    def replay_or_reserve(_session, **kwargs):
        world["log"].append("ledger-read")
        world["ledger_reads"].append(kwargs)
        error = world["replay_error"]
        if error is not None:
            raise error
        return world["replay"]

    monkeypatch.setattr(model_versions, "replay_or_reserve", replay_or_reserve)

    def store_idempotent_response(_session, **kwargs):
        world["log"].append("ledger-write")
        world["stored"].append(kwargs)

    monkeypatch.setattr(model_versions, "store_idempotent_response", store_idempotent_response)

    def register(_session, **kwargs):
        world["log"].append("service")
        world["registered"].append(kwargs)
        error = world["service_error"]
        if error is not None:
            raise error
        return world["row"]

    monkeypatch.setattr(model_versions, "register_model_version", register)
    monkeypatch.setattr(
        model_versions,
        "record_event",
        lambda _session, **kwargs: world["log"].append("audit") or world["audits"].append(kwargs),
    )

    principal = Principal(
        user_id=USER,
        tenant_id=TENANT,
        external_subject="oidc:register",
        project_ids=frozenset({PROJECT}),
    )
    app = create_app(
        engine=object(),
        settings=Settings(database_url="postgresql://unused", idempotency_ttl_seconds=600),
        verifier=StaticPrincipalVerifier({"register-token": principal}, allow_outside_dev=True),
        clock=lambda: NOW,
        check_partitions_on_startup=False,
    )
    return TestClient(app, raise_server_exceptions=False)


def post(client, body=None, *, headers=None, data=None, content_type="application/json", path=PATH):
    sent = dict(AUTH)
    if content_type is not None:
        sent["Content-Type"] = content_type
    sent.update(headers or {})
    payload = data if data is not None else json.dumps(BODY if body is None else body).encode()
    return client.post(path, content=payload, headers=sent)


def canonical(response, *, code, status, retryable=False):
    assert response.status_code == status, response.text
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert set(body) == set(CANONICAL_KEYS), body
    assert body["type"] == "about:blank"
    assert body["code"] == code
    assert body["title"] == code
    assert body["status"] == status
    assert body["category"] == code.split("-", 1)[0]
    assert body["retryable"] is retryable
    assert body["detail"]
    return body


# --------------------------------------------------------------------------
# It is served, and it is served here
# --------------------------------------------------------------------------


def test_the_route_is_on_the_projects_router_once_as_a_created_resource():
    from saintvision.api.v1 import projects

    matches = [
        route
        for route in projects.router.routes
        if getattr(route, "path", None) == f"/v1{model_versions.REGISTER_PATH}"
    ]
    assert len(matches) == 1, [getattr(r, "path", r) for r in projects.router.routes]
    route = matches[0]
    assert route.methods == {"POST"}
    # 201, because the response describes a row that did not exist before. The
    # ledger stores this same status, so a replay is an exact replay.
    assert route.status_code == 201
    assert route.response_model is schemas.ModelVersionResponse


def test_the_dispatch_in_the_kernel_sends_this_path_to_the_business_app():
    """A route the deployed topology does not reach is not a served route."""
    from fastapi import FastAPI
    from inv.business_surface import BusinessDispatch

    kernel, business = FastAPI(), FastAPI()

    @kernel.post("/{rest:path}")
    def kernel_catch_all(rest: str):
        return {"servedBy": "kernel"}

    @business.post("/{rest:path}")
    def business_catch_all(rest: str):
        return {"servedBy": "business"}

    with TestClient(BusinessDispatch(kernel, business)) as client:
        assert client.post(PATH).json() == {"servedBy": "business"}


# --------------------------------------------------------------------------
# Order: permission, then the key, then the body, then the lock, then the row
# --------------------------------------------------------------------------


def test_the_whole_order_is_fixed(monkeypatch):
    world = {}
    client = build(monkeypatch, world)
    assert post(client).status_code == 201
    assert world["log"] == [
        "permission",
        "body-read",
        "lock",
        "permission",
        "ledger-read",
        "model-get",
        "service",
        "audit",
        "ledger-write",
    ]
    # Two spans: the permission check, and the write. The body is read between
    # them with no transaction open, so a slow caller cannot pin one.
    assert world["spans"] == 2
    assert world["body_depth"] == [0]


def test_a_caller_without_the_approval_grade_is_refused_before_the_body_is_read(monkeypatch):
    world = {"permissions": [{"canRequest": True, "canApprove": False}]}
    client = build(monkeypatch, world)
    oversized = b'{"version":"' + b"x" * (MAX_REQUEST_BYTES + 100) + b'"}'
    response = post(client, data=oversized)
    canonical(response, code="AUTH-0030", status=403)
    # 403 rather than 413: the body was never read, so its size never mattered.
    assert world["log"] == ["permission"]
    assert world["registered"] == []


def test_a_non_member_is_refused_with_the_same_code(monkeypatch):
    world = {"denials": [InvError(AUTH_PROJECT_SCOPE, "no membership", status=403)]}
    client = build(monkeypatch, world)
    body = canonical(post(client), code="AUTH-0030", status=403)
    # The refusal names the project only as the thing that is not accessible;
    # no identifier of it is echoed into the body.
    assert PROJECT not in json.dumps(body)
    assert world["registered"] == []


def test_the_idempotency_key_is_required(monkeypatch):
    world = {}
    client = build(monkeypatch, world)
    response = client.post(
        PATH,
        content=json.dumps(BODY).encode(),
        headers={"Authorization": "Bearer register-token", "Content-Type": "application/json"},
    )
    canonical(response, code="VAL-0003", status=422)
    assert world["log"] == ["permission"]


@pytest.mark.parametrize(
    "key",
    [
        "",
        " ",
        "a" * 129,
        "has space",
        "has/slash",
        "has\x1fseparator",
        "has\nnewline",
    ],
)
def test_an_unusable_idempotency_key_is_a_request_error(monkeypatch, key):
    """The ledger column is ``String(128)`` and the lock material is separated
    by ``\\x1f``: a key that does not fit either would be a database error or an
    ambiguous lock instead of a request error."""
    world = {}
    client = build(monkeypatch, world)
    response = post(client, headers={"Idempotency-Key": key})
    canonical(response, code="VAL-0003", status=422)
    assert world["registered"] == []


def test_the_key_is_judged_before_the_body(monkeypatch):
    world = {}
    client = build(monkeypatch, world)
    oversized = b"x" * (MAX_REQUEST_BYTES + 100)
    response = post(client, data=oversized, headers={"Idempotency-Key": "bad key"})
    # 422 for the key, not 413 for the body.
    canonical(response, code="VAL-0003", status=422)
    assert "body-read" not in world["log"]


def test_the_permission_is_checked_again_after_the_lock(monkeypatch):
    """A membership revoked between the two spans must not write, and must not
    be able to read a stored response either."""
    world = {
        "denials": [None, InvError(AUTH_PROJECT_SCOPE, "revoked", status=403)],
        "replay": {"modelVersionId": VERSION_ID},
    }
    client = build(monkeypatch, world)
    canonical(post(client), code="AUTH-0030", status=403)
    assert world["log"] == ["permission", "body-read", "lock", "permission"]
    assert world["registered"] == []
    assert world["stored"] == []


# --------------------------------------------------------------------------
# IDEM-6: the serialisation point
# --------------------------------------------------------------------------


def test_the_lock_is_taken_before_the_ledger_is_read_and_before_any_row(monkeypatch):
    world = {}
    client = build(monkeypatch, world)
    post(client)
    assert world["log"].index("lock") < world["log"].index("ledger-read")
    assert world["log"].index("lock") < world["log"].index("model-get")
    assert len(world["locks"]) == 1
    assert "pg_advisory_xact_lock" in world["locks"][0]["sql"]


def test_the_lock_key_is_derived_from_tenant_project_endpoint_and_key():
    """Same four values, same lock; a different one of them, a different lock."""
    taken = []

    class Recorder:
        def execute(self, statement, params=None):
            taken.append(params["key"])

    base = dict(
        tenant_id=TENANT,
        endpoint=model_versions.ENDPOINT,
        idempotency_key=KEY,
        project_id=PROJECT,
    )
    first = serialise_idempotent_write(Recorder(), **base)
    again = serialise_idempotent_write(Recorder(), **base)
    assert first == again
    assert taken == [first, again]
    assert -(2**63) <= first < 2**63

    for field, value in (
        ("tenant_id", OTHER_TENANT),
        ("endpoint", "POST /v1/other"),
        ("idempotency_key", "idem-0002"),
        ("project_id", OTHER_PROJECT),
    ):
        assert serialise_idempotent_write(Recorder(), **{**base, field: value}) != first, field

    # The namespace is in the material, so another user of the same database
    # cannot collide with these locks by accident.
    assert IDEMPOTENCY_LOCK_NAMESPACE == "saintvision.idempotency.v1"


def test_the_ledger_key_includes_the_model_so_one_key_cannot_answer_for_another(monkeypatch):
    world = {}
    client = build(monkeypatch, world)
    post(client)
    payload = world["ledger_reads"][0]["payload"]
    assert payload["modelId"] == MODEL
    assert payload["request"]["contentSha256"] == SHA
    assert world["ledger_reads"][0]["endpoint"] == model_versions.ENDPOINT
    assert world["ledger_reads"][0]["project_id"] == PROJECT


def test_a_replay_returns_the_stored_body_and_calls_nothing(monkeypatch):
    stored = schemas.ModelVersionResponse(
        modelVersionId=VERSION_ID,
        modelId=MODEL,
        version="1.4.0",
        stage="draft",
        contentSha256=SHA,
        byteSize=4096,
        uri="inv://models/demo@1.4.0",
        createdAt=NOW,
    ).model_dump(by_alias=True, mode="json")
    world = {"replay": stored}
    client = build(monkeypatch, world)
    response = post(client)
    assert response.status_code == 201
    assert response.json() == stored
    assert world["registered"] == []
    assert world["stored"] == []
    assert world["audits"] == []
    assert "model-get" not in world["log"]


def test_the_same_key_with_a_different_body_is_a_conflict(monkeypatch):
    world = {
        "replay_error": InvError(GRAPH_IDEMPOTENCY_CONFLICT, "different body", status=409)
    }
    client = build(monkeypatch, world)
    canonical(post(client), code="GRAPH-0002", status=409)
    assert world["registered"] == []
    assert world["stored"] == []


def test_the_stored_status_is_the_status_this_route_returns(monkeypatch):
    world = {}
    client = build(monkeypatch, world)
    response = post(client)
    assert world["stored"][0]["response_status"] == response.status_code == 201
    assert world["stored"][0]["response_body"] == response.json()


# --------------------------------------------------------------------------
# path -> row, and one answer for every way it fails
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "parent",
    [
        None,
        Parent(tenant_id=OTHER_TENANT),
        Parent(project_id=OTHER_PROJECT),
    ],
    ids=["absent", "other-tenant", "other-project"],
)
def test_every_way_the_path_fails_to_name_a_model_is_the_same_404(monkeypatch, parent):
    world = {"parent": parent}
    client = build(monkeypatch, world)
    body = canonical(post(client), code="RES-0004", status=404)
    assert body["detail"] == model_versions.NO_SUCH_MODEL
    assert world["registered"] == []


def test_the_three_404_bodies_are_indistinguishable(monkeypatch):
    bodies = []
    for parent in (None, Parent(tenant_id=OTHER_TENANT), Parent(project_id=OTHER_PROJECT)):
        world = {"parent": parent}
        client = build(monkeypatch, world)
        body = post(client).json()
        bodies.append({key: value for key, value in body.items() if key != "traceId"})
    assert bodies[0] == bodies[1] == bodies[2]


def test_the_model_is_bound_before_the_service_is_called(monkeypatch):
    world = {"parent": Parent(project_id=OTHER_PROJECT)}
    client = build(monkeypatch, world)
    post(client)
    assert "service" not in world["log"]


# --------------------------------------------------------------------------
# The request contract
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        {**BODY, "contentSha256": "A" * 64},
        {**BODY, "contentSha256": "a" * 63},
        {**BODY, "contentSha256": "a" * 65},
        {**BODY, "version": ""},
        {**BODY, "version": "v" * 65},
        {**BODY, "uri": ""},
        {**BODY, "byteSize": -1},
        {key: value for key, value in BODY.items() if key != "version"},
        {key: value for key, value in BODY.items() if key != "contentSha256"},
        {key: value for key, value in BODY.items() if key != "uri"},
    ],
    ids=[
        "uppercase-digest",
        "short-digest",
        "long-digest",
        "empty-version",
        "long-version",
        "empty-uri",
        "negative-size",
        "no-version",
        "no-digest",
        "no-uri",
    ],
)
def test_the_request_contract_is_enforced_at_the_boundary(monkeypatch, body):
    world = {}
    client = build(monkeypatch, world)
    canonical(post(client, body), code="VAL-0003", status=422)
    assert world["registered"] == []


@pytest.mark.parametrize("field", ["producedByRunId", "lineage", "stage", "modelId"])
def test_the_request_refuses_the_fields_this_route_deliberately_does_not_take(
    monkeypatch, field
):
    """``producedByRunId`` and ``lineage`` are omissions with a reason (see the
    module docstring), not oversights. Accepting either by accident would write
    provenance nothing has checked."""
    world = {}
    client = build(monkeypatch, world)
    value = [] if field == "lineage" else "run_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
    canonical(post(client, {**BODY, field: value}), code="VAL-0003", status=422)
    assert world["registered"] == []


def test_the_service_is_called_with_only_what_the_request_carried(monkeypatch):
    world = {}
    client = build(monkeypatch, world)
    post(client)
    call = world["registered"][0]
    assert call == {
        "tenant_id": TENANT,
        "model_id": MODEL,
        "version": "1.4.0",
        "content_sha256": SHA,
        "uri": "inv://models/demo@1.4.0",
        "now": NOW,
        "byte_size": 4096,
    }
    # The service's own defaults for the provenance arguments stay in force.
    assert "produced_by_run_id" not in call
    assert "lineage" not in call


@pytest.mark.parametrize(
    "headers,data,status",
    [
        ({"Content-Type": "text/plain"}, b"{}", 415),
        ({"Content-Encoding": "gzip"}, b"{}", 415),
        ({}, b"", 422),
        ({}, b"[]", 422),
        ({}, b'{"version": 1, "version": 2}', 422),
        ({}, b"x" * (MAX_REQUEST_BYTES + 1), 413),
    ],
    ids=["media-type", "encoding", "empty", "not-an-object", "duplicate-key", "too-large"],
)
def test_the_body_boundary_is_one_code(monkeypatch, headers, data, status):
    world = {}
    client = build(monkeypatch, world)
    sent = dict(AUTH)
    sent.setdefault("Content-Type", "application/json")
    sent.update(headers)
    response = client.post(PATH, content=data, headers=sent)
    canonical(response, code="VAL-0003", status=status)


# --------------------------------------------------------------------------
# The unique constraints are the second defence, and they are not a 500
# --------------------------------------------------------------------------


class _Diag:
    def __init__(self, constraint_name):
        self.constraint_name = constraint_name


class _Orig(Exception):
    def __init__(self, message, *, constraint=None, sqlstate=None):
        super().__init__(message)
        if constraint is not None:
            self.diag = _Diag(constraint)
        self.sqlstate = sqlstate


def _integrity(message, *, constraint=None, sqlstate=None):
    return IntegrityError("INSERT", {}, _Orig(message, constraint=constraint, sqlstate=sqlstate))


@pytest.mark.parametrize(
    "error,detail",
    [
        (
            _integrity("dup", constraint="uq_model_versions_model_id_version"),
            "This model already has a version with that name.",
        ),
        (
            _integrity("dup", constraint="uq_model_versions_tenant_id_content_sha256"),
            "That content digest is already registered.",
        ),
        (
            _integrity(
                'duplicate key value violates unique constraint '
                '"uq_model_versions_tenant_id_content_sha256"'
            ),
            "That content digest is already registered.",
        ),
        (
            _integrity("duplicate key", sqlstate="23505"),
            "That content digest is already registered.",
        ),
    ],
    ids=["by-constraint-name", "digest-by-name", "by-message", "by-sqlstate"],
)
def test_a_unique_violation_is_a_409_not_a_500(monkeypatch, error, detail):
    world = {"service_error": error}
    client = build(monkeypatch, world)
    body = canonical(post(client), code="GRAPH-0002", status=409)
    assert body["detail"] == detail
    assert world["stored"] == []
    assert world["audits"] == []


def test_the_digest_conflict_does_not_name_the_project_it_collided_in(monkeypatch):
    """``uq_model_versions_tenant_id_content_sha256`` is tenant scoped, so the
    row it collided with may be in a project the caller cannot see. The detail
    says the registration conflicts and nothing about where."""
    world = {
        "service_error": _integrity(
            "dup", constraint="uq_model_versions_tenant_id_content_sha256"
        )
    }
    client = build(monkeypatch, world)
    text = json.dumps(post(client).json())
    assert OTHER_PROJECT not in text
    assert "project" not in text.lower()


def test_an_integrity_error_that_is_not_a_unique_violation_is_not_disguised(monkeypatch):
    """A foreign key refusal here would be our defect. Reporting it as 409 would
    tell the caller to stop retrying something that is not their fault."""
    world = {"service_error": _integrity("fk", sqlstate="23503")}
    client = build(monkeypatch, world)
    assert post(client).status_code == 500
    assert world["stored"] == []


# --------------------------------------------------------------------------
# Translation
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "code,status,expected",
    [
        (VAL_SCHEMA, 422, "VAL-0003"),
        (RES_ARTIFACT_NOT_FOUND, 404, "RES-0004"),
        (AUTH_PROJECT_SCOPE, 403, "AUTH-0030"),
        (GRAPH_IDEMPOTENCY_CONFLICT, 409, "GRAPH-0002"),
    ],
)
def test_every_business_code_this_route_can_reach_has_a_canonical_form(
    monkeypatch, code, status, expected
):
    world = {"service_error": InvError(code, "refused", status=status)}
    client = build(monkeypatch, world)
    canonical(post(client), code=expected, status=status)


def test_the_translation_table_covers_the_codes_the_calls_raise():
    """The codes are read from the code that raises them, not restated: a new
    raise in ``register_model_version`` shows up here rather than as SYS-0002 in
    production."""
    import inspect

    from saintvision.services import lineage as lineage_service

    source = inspect.getsource(lineage_service.register_model_version)
    raised = {
        name
        for name, value in vars(lineage_service).items()
        if isinstance(value, str) and name.isupper() and f"InvError({name}" in source
    }
    assert raised, source
    reachable = {getattr(lineage_service, name) for name in raised}
    assert reachable <= set(model_versions.TRANSLATION), reachable


def test_a_code_the_table_does_not_list_is_not_leaked(monkeypatch):
    world = {"service_error": InvError("SEC-0001", "internal", status=500)}
    client = build(monkeypatch, world)
    body = canonical(post(client), code="SYS-0002", status=500)
    assert "internal" not in body["detail"]


# --------------------------------------------------------------------------
# The response and the audit
# --------------------------------------------------------------------------


def test_the_response_is_the_strict_contract(monkeypatch):
    world = {}
    client = build(monkeypatch, world)
    response = post(client)
    assert response.status_code == 201
    body = response.json()
    assert set(body) == {
        "modelVersionId",
        "modelId",
        "version",
        "stage",
        "contentSha256",
        "byteSize",
        "uri",
        "createdAt",
    }
    assert body["stage"] == "draft"
    assert body["modelVersionId"] == VERSION_ID
    # Round-trips through the declared model: a response the contract would
    # reject is not a response this route can give.
    assert schemas.ModelVersionResponse.model_validate(body).model_dump(
        by_alias=True, mode="json"
    ) == body


def test_the_response_matches_the_generated_json_schema(monkeypatch):
    import pathlib

    import jsonschema

    schema = json.loads(
        pathlib.Path("contracts/model-version-response.schema.json").read_text("utf-8")
    )
    world = {}
    client = build(monkeypatch, world)
    jsonschema.validate(post(client).json(), schema)


def test_the_audit_records_identifiers_and_the_digest_but_not_the_uri(monkeypatch):
    world = {}
    client = build(monkeypatch, world)
    post(client)
    assert len(world["audits"]) == 1
    audit = world["audits"][0]
    assert audit["action"] == "model_version.register"
    assert audit["outcome"] == "allow"
    assert audit["target_type"] == "model_version"
    assert audit["target_id"] == VERSION_ID
    assert audit["actor_id"] == USER
    assert audit["detail"] == {
        "projectId": PROJECT,
        "modelId": MODEL,
        "version": "1.4.0",
        "contentSha256": SHA,
    }
    # ``uri`` is caller-written text; it is not copied into the audit trail.
    assert "uri" not in audit["detail"]


def test_the_audit_and_the_ledger_are_written_inside_the_same_span(monkeypatch):
    """IDEM-4: the ledger row and the registration commit together, so a stored
    response can never exist for a registration that rolled back."""
    world = {}
    client = build(monkeypatch, world)
    post(client)
    tail = world["log"][world["log"].index("service"):]
    assert tail == ["service", "audit", "ledger-write"]
    assert world["spans"] == 2

# --------------------------------------------------------------------------
# The real-PostgreSQL fixture, exercised without PostgreSQL
# --------------------------------------------------------------------------


def test_the_real_pg_fixture_builds_every_row_without_a_database():
    """Run the integration fixture's seed against a stub connection.

    #167 spent an hour of hosted CI to learn that ``new_id("code_commit")`` is
    not an entity kind, with every product assertion behind it unrun. That class
    of failure needs no database to find, so it should not need one: importing
    the fixture and handing it a connection that only records statements catches
    a wrong column, a missing required column and a wrong id kind before the
    hosted run.
    """
    import importlib.util
    from pathlib import Path

    path = (
        Path(__file__).resolve().parents[1]
        / "integration/test_model_version_register_real_pg.py"
    )
    spec = importlib.util.spec_from_file_location("real_pg_w2_fixture", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class Recorder:
        def __init__(self):
            self.statements: list[str] = []

        def execute(self, statement, params=None):
            self.statements.append(str(statement))
            return None

    recorder = Recorder()
    seeded = module._seed(
        recorder, tenant_id=TENANT, now=NOW, label="fixture-guard"
    )
    assert set(seeded) == {"user_id", "project_id", "model_id"}
    # A user, a project, a membership and a model -- and deliberately no
    # ``model_versions`` row: the route under test is the one that creates it.
    written = [
        statement.split("INSERT INTO ", 1)[1].split(" ", 1)[0]
        for statement in recorder.statements
    ]
    assert written == ["users", "projects", "project_members", "models"], written

    # The ids are the kinds ``ids.PREFIXES`` actually knows. A wrong kind raises
    # in ``new_id`` while the fixture is built, which is what this catches.
    from saintvision.ids import is_id

    assert is_id(seeded["user_id"], "user")
    assert is_id(seeded["project_id"], "project")
    assert is_id(seeded["model_id"], "model")

    # The second fixture that inserts a model version directly uses the same
    # metadata-checked helper, so exercise it too.
    from saintvision.ids import new_id

    module._insert(
        recorder,
        "model_versions",
        model_version_id=new_id("model_version"),
        tenant_id=TENANT,
        model_id=seeded["model_id"],
        version="1.0.0",
        stage="draft",
        content_sha256=SHA,
        byte_size=1,
        uri="inv://models/guard@1.0.0",
        created_at=NOW,
    )
    assert recorder.statements[-1].startswith("INSERT INTO model_versions")
