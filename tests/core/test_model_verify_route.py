"""W3: the verify route, over real HTTP, without a database (design #209 v1.1 §6, §7-9).

Each test is a reversion: undo the thing it names in ``api/v1/model_verify.py``
and this file fails. The session is a stand-in that records what the route
asks of it, in order, so what these prove is the route's *order* and its wire
contract. What only PostgreSQL can establish -- RLS, the CHECK and the key of
0054, the real lock wait, the denial row -- is
``tests/integration/test_model_verify_real_pg.py`` on hosted CI.

Kept real: ``deps.serialise_idempotent_write`` (the IDEM-6 lock key and its
position), ``model_release._locked_version`` (the shared lock), the request and
observation schemas, and ``services.resolver.resolve_location`` against the
stand-in session.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import inspect
import json
import urllib.error
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from saintvision.api import schemas
from saintvision.api.app import create_app
from saintvision.api.problem import CANONICAL_KEYS, MAX_REQUEST_BYTES
from saintvision.api.v1 import model_release, model_verify, projects
from saintvision.config import Settings
from saintvision.db.models.lineage import Model
from saintvision.db.models.locality import DataReplica
from saintvision.db.models.storage import DataLocation, StorageContribution
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
VERSION = "1.4.0"
VERSION_ID = "mdv_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
OTHER_VERSION_ID = "mdv_01J8Z3XQ2K9WMV5T7N4B6C8D0F"
USER = "usr_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
MEASUREMENT = "mvm_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
OTHER_MEASUREMENT = "mvm_01J8Z3XQ2K9WMV5T7N4B6C8D0F"
CONTRIBUTION = "stc_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
LOCATION = "dtl_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
NODE = "nod_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
URI = "inv://models/classifier@1.4.0"
SHA = "a" * 64
NOW = dt.datetime(2026, 9, 28, 6, 0, tzinfo=dt.timezone.utc)
OBSERVED = NOW - dt.timedelta(minutes=10)
RECORDED = NOW - dt.timedelta(minutes=9)
PATH = f"/v1/projects/{PROJECT}/models/{MODEL}/versions/{VERSION}/verify"
KEY = "verify-0001"
AUTH = {"Authorization": "Bearer verify-token", "Idempotency-Key": KEY}
BODY = {"measurementId": MEASUREMENT}


def wire(instant: dt.datetime) -> str:
    return instant.isoformat().replace("+00:00", "Z")


def observation(**overrides):
    body = {
        "measurementId": MEASUREMENT,
        "tenantId": str(TENANT),
        "projectId": PROJECT,
        "modelId": MODEL,
        "modelVersionId": VERSION_ID,
        "uri": URI,
        "contributionId": CONTRIBUTION,
        "contributionVersion": 1,
        "locationId": LOCATION,
        "locationVersion": 1,
        "relativePath": "weights.safetensors",
        "nodeId": NODE,
        "recoveryEpoch": "33333333-3333-3333-3333-333333333333",
        "channelVersion": 2,
        "certificateSha256": "c" * 64,
        "sha256": SHA,
        "byteSize": 4096,
        "observedAt": wire(OBSERVED),
        "recordedAt": wire(RECORDED),
    }
    body.update(overrides)
    return {k: v for k, v in body.items() if v is not ...}


class Parent:
    def __init__(self, *, tenant_id=TENANT, project_id=PROJECT):
        self.model_id = MODEL
        self.tenant_id = tenant_id
        self.project_id = project_id


class Row:
    def __init__(self, *, tenant_id=TENANT, uri=URI, verified_by=None, stage="draft"):
        self.model_version_id = VERSION_ID
        self.tenant_id = tenant_id
        self.model_id = MODEL
        self.version = VERSION
        self.stage = stage
        self.uri = uri
        self.content_sha256 = SHA
        self.byte_size = 4096
        self.verified_at = NOW - dt.timedelta(days=1) if verified_by else None
        self.verified_measurement_id = verified_by
        self.retention_pinned_until = None


class Location:
    def __init__(self, **overrides):
        self.location_id = LOCATION
        self.tenant_id = TENANT
        self.contribution_id = CONTRIBUTION
        self.uri = URI
        self.kind = "model"
        self.relative_path = "weights.safetensors"
        self.ready = True
        self.version = 1
        self.__dict__.update(overrides)


class Contribution:
    def __init__(self, **overrides):
        self.contribution_id = CONTRIBUTION
        self.tenant_id = TENANT
        self.node_id = NODE
        self.status = "active"
        self.version = 1
        self.__dict__.update(overrides)


class _Scalars:
    def __init__(self, rows):
        self._rows = rows

    def one_or_none(self):
        return self._rows[0] if self._rows else None

    def first(self):
        return self._rows[0] if self._rows else None


def _entity(statement):
    try:
        return statement.column_descriptions[0]["entity"]
    except Exception:  # noqa: BLE001 - a raw text statement
        return None


class Session:
    """Records every call the route makes, in order."""

    def __init__(self, world):
        self.world = world

    def execute(self, statement, params=None):
        sql = str(statement)
        if "lock_timeout" in sql:
            self.world["lock_timeouts"].append(sql)
        elif "pg_advisory_xact_lock" in sql:
            self.world["log"].append("advisory-lock")
            self.world["locks"].append({"sql": sql, "params": params})
        else:
            self.world["log"].append("execute")
        return None

    def get(self, model, _key, **kwargs):
        if model is Model:
            self.world["log"].append("parent-get")
            self.world["parent_gets"].append(kwargs)
            return self.world["parent"]
        if model is StorageContribution:
            self.world["log"].append("contribution-get")
            return self.world["contribution"]
        raise AssertionError(f"unexpected get of {model}")

    def scalar(self, statement):
        # ``resolve_location`` reads the location by URI.
        assert _entity(statement) is DataLocation
        self.world["log"].append("location-resolve")
        location = self.world["location"]
        return location if location is not None and location.uri == self.world["resolve_uri_seen"](statement) else None

    def scalars(self, statement):
        entity = _entity(statement)
        if entity is DataReplica:
            self.world["log"].append("replica-query")
            return _Scalars(self.world["replicas"])
        self.world["log"].append("version-lock")
        self.world["version_locks"].append(statement)
        error = self.world.get("lock_error")
        if error is not None:
            raise error
        return _Scalars([self.world["version_row"]] if self.world["version_row"] else [])


class Factory:
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


def _uri_in(statement):
    """The URI literal ``resolve_location`` bound into its WHERE clause."""
    compiled = statement.compile(compile_kwargs={"literal_binds": True})
    text = str(compiled)
    start = text.index("inv://")
    end = text.index("'", start)
    return text[start:end]


def build(monkeypatch, world, *, lock_timeout_ms=5_000, kernel_base_url="http://kernel.invalid", max_age=86_400):
    world.setdefault("parent", Parent())
    world.setdefault("version_row", Row())
    world.setdefault("location", Location())
    world.setdefault("contribution", Contribution())
    world.setdefault("replicas", [object()])
    world.setdefault("permissions", [{"canRequest": True, "canApprove": True}])
    world.setdefault("denials", [])
    world.setdefault("replay", None)
    world.setdefault("replay_error", None)
    world.setdefault("service_error", None)
    world.setdefault("observation", observation())
    world.setdefault("log", [])
    world.setdefault("locks", [])
    world.setdefault("lock_timeouts", [])
    world.setdefault("parent_gets", [])
    world.setdefault("version_locks", [])
    world.setdefault("stored", [])
    world.setdefault("audits", [])
    world.setdefault("verifies", [])
    world.setdefault("fetches", [])
    world.setdefault("ledger_reads", [])
    world.setdefault("depth", 0)
    world.setdefault("spans", 0)
    world.setdefault("body_depth", [])
    world.setdefault("clock", NOW)
    world.setdefault("clock_reads", [])
    world["resolve_uri_seen"] = _uri_in

    monkeypatch.setattr(model_verify, "make_session_factory", lambda _engine: Factory(world))
    monkeypatch.setattr(model_verify, "tenant_scope", lambda _s, _t: contextlib.nullcontext())
    from saintvision.api import app as app_module

    monkeypatch.setattr(
        app_module,
        "record_denial_out_of_band",
        lambda _engine, **kwargs: world.setdefault("denials_recorded", []).append(kwargs),
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

    monkeypatch.setattr(model_verify.project_service, "require_project_access", require_project_access)

    original_read = model_verify.read_bounded_body

    async def read_bounded_body(request, **kwargs):
        world["body_depth"].append(world["depth"])
        world["log"].append("body-read")
        return await original_read(request, **kwargs)

    monkeypatch.setattr(model_verify, "read_bounded_body", read_bounded_body)

    def replay_or_reserve(_session, **kwargs):
        world["log"].append("ledger-read")
        world["ledger_reads"].append(kwargs)
        if world["replay_error"] is not None:
            raise world["replay_error"]
        return world["replay"]

    monkeypatch.setattr(model_verify, "replay_or_reserve", replay_or_reserve)

    def store_idempotent_response(_session, **kwargs):
        world["log"].append("ledger-write")
        world["stored"].append(kwargs)

    monkeypatch.setattr(model_verify, "store_idempotent_response", store_idempotent_response)

    def verify(_session, *, tenant_id, model_version_id, measurement_id, content_sha256, now):
        world["log"].append("service")
        world["verifies"].append({
            "tenant_id": tenant_id, "model_version_id": model_version_id,
            "measurement_id": measurement_id, "content_sha256": content_sha256, "now": now,
        })
        if world["service_error"] is not None:
            raise world["service_error"]
        row = world.get("service_returns", world["version_row"])
        if row.verified_measurement_id is None:
            row.verified_at = now
            row.verified_measurement_id = measurement_id
        return row

    monkeypatch.setattr(model_verify, "verify_model_version", verify)
    monkeypatch.setattr(
        model_verify,
        "record_event",
        lambda _session, **kwargs: world["log"].append("audit") or world["audits"].append(kwargs),
    )

    def fetcher(**kwargs):
        world["log"].append("observe")
        world["fetches"].append({**kwargs, "depth": world["depth"]})
        error = world.get("fetch_error")
        if error is not None:
            raise error
        return world["observation"]

    principal = Principal(user_id=USER, tenant_id=TENANT, external_subject="oidc:verify", project_ids=frozenset({PROJECT}))

    def clock():
        world["clock_reads"].append(len(world["log"]))
        return world["clock"]

    app = create_app(
        engine=object(),
        settings=Settings(
            database_url="postgresql://unused", idempotency_ttl_seconds=600,
            business_lock_timeout_ms=lock_timeout_ms, kernel_base_url=kernel_base_url,
            model_measurement_max_age_seconds=max_age,
        ),
        verifier=StaticPrincipalVerifier({"verify-token": principal}, allow_outside_dev=True),
        clock=clock,
        check_partitions_on_startup=False,
    )
    app.state.model_measurement_fetcher = fetcher
    return TestClient(app, raise_server_exceptions=False)


def post(client, body=BODY, *, headers=None, content=None, path=PATH):
    sent = {**AUTH, "Content-Type": "application/json", **(headers or {})}
    if content is None:
        content = json.dumps(body).encode("utf-8")
    return client.post(path, content=content, headers=sent)


def canonical(response, *, code, status, retryable=False):
    assert response.status_code == status, response.text
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert set(body) == set(CANONICAL_KEYS), body
    assert (body["code"], body["status"], body["retryable"]) == (code, status, retryable)
    return body


FULL_ORDER = [
    "permission", "body-read", "observe",
    "advisory-lock", "permission", "ledger-read",
    "parent-get", "version-lock", "permission",
    "location-resolve", "contribution-get", "replica-query",
    "service", "audit", "ledger-write",
]

SUCCESS = {
    "modelVersionId": VERSION_ID, "modelId": MODEL, "version": VERSION, "stage": "draft",
    "verifiedAt": wire(NOW), "verifiedMeasurementId": MEASUREMENT, "contentSha256": SHA, "newlyVerified": True,
}


def _no_value_leaked(body, *values):
    for value in (VERSION_ID, LOCATION, CONTRIBUTION, NODE, URI, SHA, "c" * 64, *values):
        assert value not in body["detail"], (value, body["detail"])


# ---------------------------------------------------------------- the §6 order and the contract


def test_a_verification_follows_the_three_span_order_and_answers_the_strict_contract(monkeypatch):
    world: dict = {}
    client = build(monkeypatch, world)
    response = post(client)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body == SUCCESS
    schemas.ModelVerifyResponse.model_validate(body)
    assert world["log"] == FULL_ORDER
    assert world["spans"] == 2 and world["body_depth"] == [0]
    assert world["fetches"][0]["depth"] == 0                              # no tx open while the kernel is called
    assert world["fetches"][0]["measurement_id"] == MEASUREMENT
    assert world["fetches"][0]["credential"] == "verify-token"           # the caller's own bearer
    assert world["verifies"] == [{
        "tenant_id": TENANT, "model_version_id": VERSION_ID, "measurement_id": MEASUREMENT,
        "content_sha256": SHA, "now": NOW,                                # the *observed* digest, not a body value
    }]
    assert world["stored"][0]["response_status"] == 200 and world["stored"][0]["response_body"] == body
    assert world["stored"][0]["payload"] == {"modelId": MODEL, "version": VERSION, "request": {"measurementId": MEASUREMENT}}
    assert world["ledger_reads"][0]["payload"] == world["stored"][0]["payload"]
    assert world["ledger_reads"][0]["endpoint"] == model_verify.ENDPOINT
    assert world["audits"][0]["action"] == "model_version.verify"
    assert world["audits"][0]["detail"] == {
        "projectId": PROJECT, "modelId": MODEL, "version": VERSION, "measurementId": MEASUREMENT, "newlyVerified": True,
    }
    assert set(world["audits"][0]["detail"]) & {"sha256", "contentSha256", "uri"} == set()


def test_the_version_row_is_locked_for_update_with_populate_existing_after_the_parent_read(monkeypatch):
    world: dict = {}
    client = build(monkeypatch, world)
    assert post(client).status_code == 200
    assert world["log"].index("parent-get") < world["log"].index("version-lock")
    assert world["parent_gets"] == [{"populate_existing": True}]
    (statement,) = world["version_locks"]
    assert statement.get_execution_options().get("populate_existing") is True
    assert "FOR UPDATE" in str(statement.compile(compile_kwargs={"literal_binds": True})).upper()


def test_the_serialisation_point_precedes_every_row_and_both_spans_are_bounded(monkeypatch):
    world: dict = {}
    client = build(monkeypatch, world)
    assert post(client).status_code == 200
    log = world["log"]
    assert log.index("advisory-lock") < log.index("ledger-read") < log.index("parent-get")
    assert world["lock_timeouts"] == ["SET LOCAL lock_timeout = '5000ms'"] * 2
    assert len(world["locks"]) == 1                                      # the real IDEM-6 helper, once


def test_the_clock_is_read_once_after_the_lock_and_the_live_permission(monkeypatch):
    world: dict = {}
    client = build(monkeypatch, world)
    assert post(client).status_code == 200
    (position,) = world["clock_reads"]
    log = world["log"]
    assert position == log.index("ledger-read")                        # after advisory-lock and permission, before the ledger
    assert world["stored"][0]["now"] == NOW and world["audits"][0]["now"] == NOW


def test_the_route_declares_no_clock_dependency():
    parameters = inspect.signature(model_verify.verify_model_version_route).parameters
    assert "now" not in parameters


def test_a_repeat_with_a_fresh_key_on_the_already_bound_measurement_is_a_200_no_op(monkeypatch):
    world = {"version_row": Row(verified_by=MEASUREMENT)}
    client = build(monkeypatch, world)
    response = post(client, headers={"Idempotency-Key": "verify-0002"})
    assert response.status_code == 200, response.text
    assert response.json()["newlyVerified"] is False
    assert world["audits"][0]["detail"]["newlyVerified"] is False


# ---------------------------------------------------------------- the body: a measurement, never a value


@pytest.mark.parametrize(
    "body",
    [
        {}, {"measurementId": "not-an-id"}, {"measurementId": MEASUREMENT, "sha256": SHA},
        {"measurementId": MEASUREMENT, "contentSha256": SHA}, {"measurementId": MEASUREMENT, "byteSize": 4096},
        {"measurementId": MEASUREMENT, "uri": URI}, {"measurementId": "mdv_01J8Z3XQ2K9WMV5T7N4B6C8D0E"},
    ],
    ids=["empty", "malformed-id", "digest", "content-digest", "size", "uri", "wrong-kind"],
)
def test_a_body_that_is_not_exactly_one_measurement_id_is_422_and_nothing_is_fetched_or_locked(monkeypatch, body):
    world: dict = {}
    client = build(monkeypatch, world)
    canonical(post(client, body), code="VAL-0003", status=422)
    assert world["fetches"] == [] and world["locks"] == [] and world["stored"] == []


def test_a_missing_idempotency_key_is_422_before_the_body_is_read(monkeypatch):
    world: dict = {}
    client = build(monkeypatch, world)
    response = client.post(PATH, content=json.dumps(BODY).encode(), headers={"Authorization": "Bearer verify-token", "Content-Type": "application/json"})
    canonical(response, code="VAL-0003", status=422)
    assert "body-read" not in world["log"] and world["fetches"] == []


def test_an_oversized_body_is_refused_by_the_shared_bounded_reader(monkeypatch):
    world: dict = {}
    client = build(monkeypatch, world)
    padded = {"measurementId": MEASUREMENT, "pad": "x" * (MAX_REQUEST_BYTES + 1)}
    canonical(post(client, padded), code="VAL-0003", status=413)
    assert world["fetches"] == []


def test_a_non_json_content_type_is_415(monkeypatch):
    world: dict = {}
    client = build(monkeypatch, world)
    canonical(post(client, headers={"Content-Type": "text/plain"}), code="VAL-0003", status=415)


# ---------------------------------------------------------------- the observation


@pytest.mark.parametrize(
    "overrides",
    [
        {"nodeId": ...}, {"certificateSha256": ...}, {"recoveryEpoch": ...}, {"channelVersion": ...},     # no worker identity
        {"sha256": ...}, {"observedAt": ...}, {"extra": 1}, {"byteSize": "4096"}, {"sha256": "A" * 64},
        {"contributionVersion": 0}, {"observedAt": "2026-09-28T05:50:00"},                              # naive time
    ],
    ids=["no-node", "no-leaf", "no-epoch", "no-channel-version", "no-digest", "no-observed", "unknown-key", "string-int", "upper-hex", "zero-version", "naive-time"],
)
def test_an_observation_that_is_not_the_strict_contract_is_a_retryable_503_and_locks_nothing(monkeypatch, overrides):
    world = {"observation": observation(**overrides)}
    client = build(monkeypatch, world)
    body = canonical(post(client), code="SYS-0001", status=503, retryable=True)
    _no_value_leaked(body)
    assert world["locks"] == [] and world["verifies"] == [] and world["stored"] == []


@pytest.mark.parametrize(
    "error",
    [urllib.error.URLError("refused"), OSError("timed out"), ValueError("oversize"), urllib.error.HTTPError("u", 500, "boom", {}, None)],
    ids=["unreachable", "os", "oversize-or-scheme", "kernel-500"],
)
def test_a_kernel_that_cannot_be_read_is_a_retryable_503(monkeypatch, error):
    world = {"fetch_error": error}
    client = build(monkeypatch, world)
    canonical(post(client), code="SYS-0001", status=503, retryable=True)
    assert world["locks"] == []


def test_an_unconfigured_kernel_is_a_retryable_503_before_any_lock(monkeypatch):
    world: dict = {}
    client = build(monkeypatch, world, kernel_base_url=None)
    canonical(post(client), code="SYS-0001", status=503, retryable=True)
    assert world["locks"] == [] and world["fetches"] == []


def test_a_kernel_404_is_this_routes_404_with_no_value(monkeypatch):
    world = {"fetch_error": urllib.error.HTTPError("u", 404, "no", {}, None)}
    client = build(monkeypatch, world)
    body = canonical(post(client), code="RES-0004", status=404)
    assert body["detail"] == model_verify.MEASUREMENT_NOT_FOUND_DETAIL
    assert world["locks"] == []


def test_a_redirecting_kernel_is_refused_by_the_shared_opener():
    assert model_verify._RefuseRedirect is model_release._RefuseRedirect
    class _Req:
        full_url = "http://kernel.invalid/v1/x"

    with pytest.raises(urllib.error.HTTPError):
        model_verify._RefuseRedirect().redirect_request(_Req(), None, 302, "moved", {}, "http://elsewhere.invalid/")


def test_the_fetch_uses_the_measurement_path_and_refuses_a_non_http_scheme():
    with pytest.raises(ValueError):
        model_verify.fetch_measurement(
            base_url="file:///etc", credential="t", project_id=PROJECT, model_id=MODEL, version=VERSION, measurement_id=MEASUREMENT
        )
    source = inspect.getsource(model_verify.fetch_measurement)
    assert "/measurements/{measurement_id}" in source


# ---------------------------------------------------------------- identity re-binding: one 404


@pytest.mark.parametrize(
    "overrides",
    [
        {"measurementId": OTHER_MEASUREMENT}, {"tenantId": str(OTHER_TENANT)}, {"projectId": OTHER_PROJECT},
        {"modelId": "mdl_01J8Z3XQ2K9WMV5T7N4B6C8D0F"}, {"modelVersionId": OTHER_VERSION_ID}, {"uri": "inv://models/other@1.4.0"},
    ],
    ids=["other-measurement", "other-tenant", "other-project", "other-model", "other-version", "other-uri"],
)
def test_an_observation_for_another_identity_is_the_same_404_and_writes_nothing(monkeypatch, overrides):
    world = {"observation": observation(**overrides)}
    client = build(monkeypatch, world)
    body = canonical(post(client), code="RES-0004", status=404)
    assert body["detail"] == model_verify.NOT_FOUND_DETAIL
    _no_value_leaked(body, OTHER_VERSION_ID, OTHER_MEASUREMENT)
    assert world["verifies"] == [] and world["stored"] == [] and world["audits"] == []


@pytest.mark.parametrize(
    "world",
    [
        {"parent": None}, {"parent": Parent(project_id=OTHER_PROJECT)}, {"parent": Parent(tenant_id=OTHER_TENANT)},
        {"version_row": None}, {"version_row": Row(tenant_id=OTHER_TENANT)},
    ],
    ids=["no-parent", "other-project", "other-tenant-parent", "no-row", "other-tenant-row"],
)
def test_every_way_the_path_fails_to_name_a_version_is_the_same_404(monkeypatch, world):
    world = dict(world)
    client = build(monkeypatch, world)
    body = canonical(post(client), code="RES-0004", status=404)
    assert body["detail"] == model_verify.NOT_FOUND_DETAIL
    assert "service" not in world["log"]


# ---------------------------------------------------------------- snapshot drift and freshness: one 409, no value


@pytest.mark.parametrize(
    "world",
    [
        {"location": None},
        {"location": Location(kind="dataset")},
        {"location": Location(ready=False)},
        {"location": Location(version=2)},
        {"location": Location(location_id="dtl_01J8Z3XQ2K9WMV5T7N4B6C8D0F")},
        {"location": Location(relative_path="other.bin")},
        {"location": Location(contribution_id="stc_01J8Z3XQ2K9WMV5T7N4B6C8D0F")},
        {"contribution": None},
        {"contribution": Contribution(status="revoked")},
        {"contribution": Contribution(version=2)},
        {"contribution": Contribution(node_id="nod_01J8Z3XQ2K9WMV5T7N4B6C8D0F")},
        {"contribution": Contribution(tenant_id=OTHER_TENANT)},
        {"replicas": []},
        {"version_row": Row(uri="inv://models/classifier@1.4.0/other")},
    ],
    ids=["unresolved", "not-model", "not-ready", "location-version", "other-location", "other-path", "other-contribution",
         "no-contribution", "revoked", "contribution-version", "other-node", "other-tenant-contribution", "no-ready-replica", "row-uri-differs"],
)
def test_a_snapshot_that_drifted_from_the_measurement_is_409_and_writes_nothing(monkeypatch, world):
    world = dict(world)
    if "version_row" in world:
        # The row's URI is what the observation is re-bound to; a differing row URI is identity, not snapshot.
        pass
    client = build(monkeypatch, world)
    response = post(client)
    assert response.status_code in (404, 409), response.text
    body = response.json()
    assert body["code"] in ("RES-0004", "GRAPH-0002")
    _no_value_leaked(body)
    assert world["verifies"] == [] and world["stored"] == [] and world["audits"] == []


@pytest.mark.parametrize(
    "overrides",
    [
        {"observedAt": wire(NOW - dt.timedelta(days=2))},                                              # stale
        {"observedAt": wire(NOW + dt.timedelta(minutes=1)), "recordedAt": wire(NOW + dt.timedelta(minutes=2))},  # future
        {"recordedAt": wire(NOW + dt.timedelta(seconds=1))},                                             # recorded after now
        {"observedAt": wire(RECORDED + dt.timedelta(seconds=1))},                                        # observed after recorded
    ],
    ids=["stale", "future", "recorded-after-now", "observed-after-recorded"],
)
def test_a_measurement_that_is_not_fresh_is_409_with_no_value(monkeypatch, overrides):
    world = {"observation": observation(**overrides)}
    client = build(monkeypatch, world)
    body = canonical(post(client), code="GRAPH-0002", status=409)
    assert body["detail"] == model_verify.STALE_DETAIL
    assert world["verifies"] == [] and world["stored"] == []


def test_the_freshness_window_comes_from_settings(monkeypatch):
    world = {"observation": observation(observedAt=wire(NOW - dt.timedelta(minutes=10)))}
    client = build(monkeypatch, world, max_age=300)
    canonical(post(client), code="GRAPH-0002", status=409)
    world = {"observation": observation(observedAt=wire(NOW - dt.timedelta(minutes=10)))}
    client = build(monkeypatch, world, max_age=900)
    assert post(client).status_code == 200


@pytest.mark.parametrize("value", [0, -1, True, 1.5, "86400", 31_536_001])
def test_settings_refuse_a_nonsensical_freshness_window_at_construction(value):
    with pytest.raises(ValueError):
        Settings(database_url="postgresql://unused", model_measurement_max_age_seconds=value)


# ---------------------------------------------------------------- the service's refusals


@pytest.mark.parametrize(
    "error, code, status",
    [
        (InvError(RES_ARTIFACT_NOT_FOUND, "measurement not found"), "RES-0004", 404),          # forged: no such row in the kernel table
        (InvError(VAL_SCHEMA, "the computed checksum does not match the recorded one"), "GRAPH-0002", 409),
        (InvError(VAL_SCHEMA, "the measurement belongs to a different model version"), "GRAPH-0002", 409),
        (InvError(VAL_SCHEMA, "the model version is already verified by another measurement"), "GRAPH-0002", 409),
    ],
    ids=["forged", "digest-mismatch", "other-version", "second-measurement"],
)
def test_a_service_refusal_is_translated_with_a_fixed_detail_and_nothing_stored(monkeypatch, error, code, status):
    world = {"service_error": error}
    client = build(monkeypatch, world)
    body = canonical(post(client), code=code, status=status)
    _no_value_leaked(body)
    assert "checksum" not in body["detail"]
    assert world["stored"] == [] and world["audits"] == []


def test_a_service_that_returns_a_row_other_than_the_locked_one_is_a_failure_not_a_200(monkeypatch):
    world = {"service_returns": Row()}
    client = build(monkeypatch, world)
    assert post(client).status_code == 500
    assert world["stored"] == [] and world["audits"] == []


# ---------------------------------------------------------------- permission and denials


def test_a_member_without_the_approval_grade_is_403_before_the_body_is_read_and_is_recorded_once(monkeypatch):
    world = {"permissions": [{"canRequest": True, "canApprove": False}]}
    client = build(monkeypatch, world)
    canonical(post(client), code="AUTH-0030", status=403)
    assert world["log"] == ["permission"] and world["fetches"] == []
    assert len(world["denials_recorded"]) == 1


def test_a_non_member_is_403_and_recorded_once(monkeypatch):
    world = {"denials": [InvError(AUTH_PROJECT_SCOPE, "no")]}
    client = build(monkeypatch, world)
    canonical(post(client), code="AUTH-0030", status=403)
    assert len(world["denials_recorded"]) == 1


def test_a_revocation_between_the_spans_is_403_and_locks_no_row(monkeypatch):
    world = {"permissions": [{"canApprove": True}, {"canApprove": False}]}
    client = build(monkeypatch, world)
    canonical(post(client), code="AUTH-0030", status=403)
    assert "version-lock" not in world["log"] and world["stored"] == []


def test_a_revocation_during_the_lock_wait_is_403_and_writes_nothing(monkeypatch):
    world = {"permissions": [{"canApprove": True}, {"canApprove": True}, {"canApprove": False}]}
    client = build(monkeypatch, world)
    canonical(post(client), code="AUTH-0030", status=403)
    assert "version-lock" in world["log"] and "service" not in world["log"] and world["stored"] == []


def test_no_token_is_401_and_recorded_once(monkeypatch):
    world: dict = {}
    client = build(monkeypatch, world)
    response = client.post(PATH, content=json.dumps(BODY).encode(), headers={"Content-Type": "application/json", "Idempotency-Key": KEY})
    assert response.status_code == 401, response.text
    assert len(world.get("denials_recorded", [])) == 1
    assert world["fetches"] == []


# ---------------------------------------------------------------- idempotency


def test_a_stored_answer_is_replayed_exactly_and_no_row_is_locked(monkeypatch):
    world = {"replay": {**SUCCESS}}
    client = build(monkeypatch, world)
    response = post(client)
    assert response.status_code == 200 and response.json() == SUCCESS
    assert "version-lock" not in world["log"] and world["verifies"] == []


def test_the_same_key_with_a_different_request_is_409(monkeypatch):
    world = {"replay_error": InvError(GRAPH_IDEMPOTENCY_CONFLICT, "differs")}
    client = build(monkeypatch, world)
    canonical(post(client), code="GRAPH-0002", status=409)


def test_the_ledger_payload_names_the_version_so_one_key_cannot_answer_for_another(monkeypatch):
    world: dict = {}
    client = build(monkeypatch, world)
    assert post(client).status_code == 200
    assert world["stored"][0]["payload"]["modelId"] == MODEL and world["stored"][0]["payload"]["version"] == VERSION


# ---------------------------------------------------------------- lock waits


def _operational(sqlstate):
    class Orig(Exception):
        pass

    orig = Orig("locked")
    orig.sqlstate = sqlstate
    return OperationalError("SELECT ... FOR UPDATE", {}, orig)


@pytest.mark.parametrize("sqlstate", ["55P03", "40P01"])
def test_a_lock_timeout_or_deadlock_is_a_retryable_503_with_nothing_written(monkeypatch, sqlstate):
    world = {"lock_error": _operational(sqlstate)}
    client = build(monkeypatch, world)
    body = canonical(post(client), code="SYS-0001", status=503, retryable=True)
    assert "FOR UPDATE" not in body["detail"] and VERSION_ID not in body["detail"]
    assert "service" not in world["log"] and world["stored"] == []


def test_the_lock_timeout_comes_from_settings(monkeypatch):
    world: dict = {}
    client = build(monkeypatch, world, lock_timeout_ms=250)
    assert post(client).status_code == 200
    assert world["lock_timeouts"] == ["SET LOCAL lock_timeout = '250ms'"] * 2


# ---------------------------------------------------------------- registration and tables


def test_the_route_is_on_the_projects_router_once_where_business_dispatch_reads_it():
    paths = [route.path for route in projects.router.routes]
    assert paths.count("/v1" + model_verify.VERIFY_PATH) == 1
    assert model_verify.ENDPOINT.endswith(model_verify.VERIFY_PATH)


def test_every_reachable_business_code_is_in_the_translation_table():
    from saintvision.services import lineage

    source = inspect.getsource(lineage.verify_model_version)
    reachable = {code for code in (RES_ARTIFACT_NOT_FOUND, VAL_SCHEMA) if code.replace("-", "_") in source or code in source}
    assert reachable <= set(model_verify.TRANSLATION)
    assert {AUTH_PROJECT_SCOPE, GRAPH_IDEMPOTENCY_CONFLICT, RES_ARTIFACT_NOT_FOUND, VAL_SCHEMA} <= set(model_verify.TRANSLATION)


def test_the_shared_lock_helper_is_the_release_routes_own():
    assert model_verify._locked_version is model_release._locked_version
