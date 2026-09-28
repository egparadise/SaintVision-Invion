"""W4: the retention-pin route, over real HTTP, without a database.

Each test is a reversion: undo the thing it names in
``api/v1/model_retention.py`` and this file fails. The session is a stand-in
that records what the route asks of it, in order, so what these prove is the
route's *order* (design §5-3) and its wire contract. Lost-update kills are not
claimed here -- a mock session cannot lose an update -- they are
``tests/integration/test_model_retention_pin_real_pg.py`` on hosted CI.

Kept real: ``deps.serialise_idempotent_write`` (the lock key and its position
are the IDEM-6 contract) and ``model_release._locked_version`` (the shared
lock; the fake session records the statement it is given).
"""

from __future__ import annotations

import contextlib
import datetime as dt
import json
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from saintvision.api import schemas
from saintvision.api.app import create_app
from saintvision.api.problem import CANONICAL_KEYS, MAX_REQUEST_BYTES
from saintvision.api.v1 import model_release, model_retention, projects
from saintvision.config import Settings
from saintvision.errors import (
    AUTH_PROJECT_SCOPE,
    GRAPH_IDEMPOTENCY_CONFLICT,
    RES_ARTIFACT_NOT_FOUND,
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
USER = "usr_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
NOW = dt.datetime(2026, 9, 28, 6, 0, tzinfo=dt.timezone.utc)
CURRENT = dt.datetime(2027, 1, 1, tzinfo=dt.timezone.utc)
LATER = dt.datetime(2028, 1, 1, tzinfo=dt.timezone.utc)
PATH = f"/v1/projects/{PROJECT}/models/{MODEL}/versions/{VERSION}/retention-pin"
KEY = "pin-0001"
AUTH = {"Authorization": "Bearer pin-token", "Idempotency-Key": KEY}


def wire(instant: dt.datetime) -> str:
    """Pydantic serialises an aware UTC instant as ``...Z``; compare on the wire form."""
    return instant.isoformat().replace("+00:00", "Z")


BODY = {"until": wire(LATER)}


class Parent:
    def __init__(self, *, tenant_id=TENANT, project_id=PROJECT):
        self.model_id = MODEL
        self.tenant_id = tenant_id
        self.project_id = project_id


class Row:
    def __init__(self, *, tenant_id=TENANT, pinned_until=CURRENT, stage="draft"):
        self.model_version_id = VERSION_ID
        self.tenant_id = tenant_id
        self.model_id = MODEL
        self.version = VERSION
        self.stage = stage
        self.retention_pinned_until = pinned_until


class _Scalars:
    def __init__(self, row):
        self._row = row

    def one_or_none(self):
        return self._row


class Session:
    """Records every call the route makes, in order."""

    def __init__(self, world):
        self.world = world

    def execute(self, statement, params=None):
        sql = str(statement)
        if "lock_timeout" in sql:
            self.world["log"].append("set-lock-timeout")
            self.world["lock_timeouts"].append(sql)
        elif "pg_advisory_xact_lock" in sql:
            self.world["log"].append("advisory-lock")
            self.world["locks"].append({"sql": sql, "params": params})
            # A real lock can wait. Advancing the clock here is how a waiting
            # request is expressed without sleeping.
            if self.world.get("advance_on_lock") is not None:
                self.world["clock"] = self.world["advance_on_lock"]
        else:
            self.world["log"].append("execute")
        return None

    def get(self, _model, _key, **kwargs):
        self.world["log"].append("parent-get")
        self.world["parent_gets"].append(kwargs)
        return self.world["parent"]

    def scalars(self, statement):
        self.world["log"].append("version-lock")
        self.world["version_locks"].append(statement)
        error = self.world.get("lock_error")
        if error is not None:
            raise error
        return _Scalars(self.world["version_row"])


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


def build(monkeypatch, world, *, lock_timeout_ms=5_000):
    world.setdefault("parent", Parent())
    world.setdefault("version_row", Row())
    world.setdefault("permissions", [{"canRequest": True, "canApprove": True}])
    world.setdefault("denials", [])
    world.setdefault("replay", None)
    world.setdefault("replay_error", None)
    world.setdefault("service_error", None)
    world.setdefault("log", [])
    world.setdefault("locks", [])
    world.setdefault("lock_timeouts", [])
    world.setdefault("parent_gets", [])
    world.setdefault("version_locks", [])
    world.setdefault("stored", [])
    world.setdefault("audits", [])
    world.setdefault("pins", [])
    world.setdefault("ledger_reads", [])
    world.setdefault("depth", 0)
    world.setdefault("spans", 0)
    world.setdefault("body_depth", [])
    world.setdefault("clock", NOW)
    world.setdefault("clock_reads", [])

    monkeypatch.setattr(model_retention, "make_session_factory", lambda _engine: Factory(world))
    monkeypatch.setattr(model_retention, "tenant_scope", lambda _s, _t: contextlib.nullcontext())
    # The shared denial recorder (#195) writes through the app's engine, which
    # these tests do not have; recorded here so a 403's audit call is asserted, not lost.
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

    monkeypatch.setattr(model_retention.project_service, "require_project_access", require_project_access)

    original_read = model_retention.read_bounded_body

    async def read_bounded_body(request, **kwargs):
        world["body_depth"].append(world["depth"])
        world["log"].append("body-read")
        # The caller paces the body; a slow one is time passing.
        if world.get("advance_on_body") is not None:
            world["clock"] = world["advance_on_body"]
        return await original_read(request, **kwargs)

    monkeypatch.setattr(model_retention, "read_bounded_body", read_bounded_body)

    def replay_or_reserve(_session, **kwargs):
        world["log"].append("ledger-read")
        world["ledger_reads"].append(kwargs)
        if world["replay_error"] is not None:
            raise world["replay_error"]
        return world["replay"]

    monkeypatch.setattr(model_retention, "replay_or_reserve", replay_or_reserve)

    def store_idempotent_response(_session, **kwargs):
        world["log"].append("ledger-write")
        world["stored"].append(kwargs)

    monkeypatch.setattr(model_retention, "store_idempotent_response", store_idempotent_response)

    def pin_retention(_session, *, tenant_id, model_version_id, until):
        """Recorded, not re-implemented. The row it returns is whatever the
        world says -- normally the locked row itself, with the value the world
        says the service left on it."""
        world["log"].append("service")
        world["pins"].append({"tenant_id": tenant_id, "model_version_id": model_version_id, "until": until})
        if world["service_error"] is not None:
            raise world["service_error"]
        row = world.get("service_returns", world["version_row"])
        if "service_leaves" in world:
            row.retention_pinned_until = world["service_leaves"]
        else:
            row.retention_pinned_until = until
        return row

    monkeypatch.setattr(model_retention, "pin_retention", pin_retention)
    monkeypatch.setattr(
        model_retention,
        "record_event",
        lambda _session, **kwargs: world["log"].append("audit") or world["audits"].append(kwargs),
    )

    principal = Principal(
        user_id=USER, tenant_id=TENANT, external_subject="oidc:pin", project_ids=frozenset({PROJECT})
    )
    def clock():
        world["clock_reads"].append(len(world["log"]))
        return world["clock"]

    app = create_app(
        engine=object(),
        settings=Settings(
            database_url="postgresql://unused", idempotency_ttl_seconds=600, business_lock_timeout_ms=lock_timeout_ms
        ),
        verifier=StaticPrincipalVerifier({"pin-token": principal}, allow_outside_dev=True),
        clock=clock,
        check_partitions_on_startup=False,
    )
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
    "permission", "body-read",
    "set-lock-timeout", "advisory-lock", "permission", "ledger-read",
    "parent-get", "version-lock", "permission", "service", "audit", "ledger-write",
]


# ---------------------------------------------------------------- the §5-3 order


def test_an_extension_follows_the_lock_contract_order_and_answers_the_strict_contract(monkeypatch):
    world: dict = {}
    client = build(monkeypatch, world)
    response = post(client)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body == {
        "modelVersionId": VERSION_ID, "modelId": MODEL, "version": VERSION, "stage": "draft",
        "retentionPinnedUntil": wire(LATER), "extended": True,
    }
    schemas.RetentionPinResponse.model_validate(body)
    assert world["log"] == FULL_ORDER
    assert world["spans"] == 2 and world["body_depth"] == [0]          # body read with no tx open
    assert world["pins"] == [{"tenant_id": TENANT, "model_version_id": VERSION_ID, "until": LATER}]
    assert world["stored"][0]["response_status"] == 200 and world["stored"][0]["response_body"] == body
    assert world["stored"][0]["payload"] == {"modelId": MODEL, "version": VERSION, "request": {"until": wire(LATER)}}
    assert world["ledger_reads"][0]["payload"] == world["stored"][0]["payload"]
    assert world["ledger_reads"][0]["endpoint"] == model_retention.ENDPOINT
    assert world["audits"][0]["action"] == "model_version.retention_pin"
    assert world["audits"][0]["detail"]["extended"] is True


def test_the_version_row_is_locked_for_update_with_populate_existing_after_the_parent_read(monkeypatch):
    world: dict = {}
    client = build(monkeypatch, world)
    assert post(client).status_code == 200
    assert world["log"].index("parent-get") < world["log"].index("version-lock")
    assert world["parent_gets"] == [{"populate_existing": True}]
    (statement,) = world["version_locks"]
    assert statement.get_execution_options().get("populate_existing") is True
    assert "FOR UPDATE" in str(statement.compile(compile_kwargs={"literal_binds": True})).upper()


def test_the_serialisation_point_precedes_every_row_and_uses_the_endpoint_constant(monkeypatch):
    world: dict = {}
    client = build(monkeypatch, world)
    assert post(client).status_code == 200
    log = world["log"]
    assert log.index("advisory-lock") < log.index("ledger-read") < log.index("parent-get")
    assert log.index("set-lock-timeout") < log.index("advisory-lock")
    assert world["lock_timeouts"] == ["SET LOCAL lock_timeout = '5000ms'"]


def test_the_lock_timeout_comes_from_settings(monkeypatch):
    world: dict = {}
    client = build(monkeypatch, world, lock_timeout_ms=250)
    assert post(client).status_code == 200
    assert world["lock_timeouts"] == ["SET LOCAL lock_timeout = '250ms'"]


@pytest.mark.parametrize("value", [0, -1, True, "5000", None])
def test_a_lock_timeout_that_is_not_a_positive_integer_is_refused_before_any_lock(value):
    with pytest.raises(RuntimeError):
        model_retention._bound_lock_wait(Session({"log": [], "lock_timeouts": []}), timeout_ms=value)


def test_a_shorter_or_equal_until_is_a_200_no_op_that_is_still_recorded(monkeypatch):
    world = {"service_leaves": CURRENT}
    client = build(monkeypatch, world)
    response = post(client, {"until": dt.datetime(2026, 12, 1, tzinfo=dt.timezone.utc).isoformat()})
    assert response.status_code == 200, response.text
    assert response.json()["extended"] is False
    assert response.json()["retentionPinnedUntil"] == wire(CURRENT)
    assert world["log"] == FULL_ORDER                                    # audit + ledger even for a no-op
    assert world["audits"][0]["detail"]["extended"] is False


def test_a_released_version_can_still_be_extended_and_says_so(monkeypatch):
    world = {"version_row": Row(stage="released")}
    client = build(monkeypatch, world)
    response = post(client)
    assert response.status_code == 200 and response.json()["stage"] == "released"


# ---------------------------------------------------------------- the clock (Codex #196 F2)


def test_the_clock_is_read_once_after_the_lock_and_the_live_permission(monkeypatch):
    world: dict = {}
    client = build(monkeypatch, world)
    assert post(client).status_code == 200
    assert len(world["clock_reads"]) == 1
    log = world["log"]
    read_at = world["clock_reads"][0]
    assert read_at > log.index("advisory-lock") and read_at > log.index("permission", log.index("advisory-lock"))
    assert read_at <= log.index("ledger-read")


def test_time_that_passes_in_the_body_and_the_lock_wait_is_what_the_ledger_and_the_audit_carry(monkeypatch):
    """Revert (``Depends(get_now)``): the stamps would be NOW, before the wait."""
    after_body = NOW + dt.timedelta(minutes=5)
    after_lock = NOW + dt.timedelta(minutes=30)
    world = {"advance_on_body": after_body, "advance_on_lock": after_lock}
    client = build(monkeypatch, world)
    assert post(client).status_code == 200
    assert world["ledger_reads"][0]["now"] == after_lock
    assert world["stored"][0]["now"] == after_lock
    assert world["audits"][0]["now"] == after_lock
    assert world["clock_reads"] and world["clock"] == after_lock


def test_the_route_declares_no_clock_dependency():
    import inspect

    assert "now" not in inspect.signature(model_retention.pin_model_version_retention).parameters
    assert not hasattr(model_retention, "get_now")


# ---------------------------------------------------------------- permission, before anything


def test_a_member_without_the_approval_grade_is_403_before_the_body_is_read(monkeypatch):
    world = {"permissions": [{"canRequest": True, "canApprove": False}]}
    client = build(monkeypatch, world)
    canonical(post(client, content=b"{" + b"x" * 20000), code="AUTH-0030", status=403)
    assert world["log"] == ["permission"]


def test_a_non_member_is_403_before_the_body_is_read(monkeypatch):
    world = {"denials": [InvError(AUTH_PROJECT_SCOPE, "not accessible")]}
    client = build(monkeypatch, world)
    canonical(post(client), code="AUTH-0030", status=403)
    assert world["log"] == ["permission"]


def test_a_revocation_between_the_spans_is_403_and_locks_no_row(monkeypatch):
    world = {"permissions": [{"canApprove": True}, {"canApprove": False}]}
    client = build(monkeypatch, world)
    canonical(post(client), code="AUTH-0030", status=403)
    assert world["log"] == ["permission", "body-read", "set-lock-timeout", "advisory-lock", "permission"]
    assert world["version_locks"] == [] and world["stored"] == []


def test_a_revocation_during_the_lock_wait_is_403_and_writes_nothing(monkeypatch):
    """The third check, after the row lock: the one that closes the TOCTOU."""
    world = {"permissions": [{"canApprove": True}, {"canApprove": True}, {"canApprove": False}]}
    client = build(monkeypatch, world)
    canonical(post(client), code="AUTH-0030", status=403)
    assert world["log"][-1] == "permission" and world["log"].count("permission") == 3
    assert "service" not in world["log"] and world["stored"] == [] and world["audits"] == []


# ---------------------------------------------------------------- the key and the body


def test_a_missing_idempotency_key_is_422_before_the_body_is_read(monkeypatch):
    world: dict = {}
    client = build(monkeypatch, world)
    headers = {"Authorization": AUTH["Authorization"], "Content-Type": "application/json"}
    response = client.post(PATH, content=json.dumps(BODY).encode(), headers=headers)
    canonical(response, code="VAL-0003", status=422)
    assert world["log"] == ["permission"]


@pytest.mark.parametrize(
    "body",
    [
        {"until": "2028-01-01T00:00:00"},                 # naive: no offset
        {"until": "not-a-time"},
        {"until": wire(LATER), "extra": 1},
        {},
        [],
    ],
)
def test_a_body_that_is_not_the_strict_request_is_422_and_locks_nothing(monkeypatch, body):
    world: dict = {}
    client = build(monkeypatch, world)
    canonical(post(client, body), code="VAL-0003", status=422)
    assert world["spans"] == 1 and world["locks"] == [] and world["stored"] == []


def test_an_oversized_body_is_refused_by_the_shared_bounded_reader(monkeypatch):
    world: dict = {}
    client = build(monkeypatch, world)
    canonical(post(client, content=b"{" + b" " * (MAX_REQUEST_BYTES + 1)), code="VAL-0003", status=413)
    assert world["locks"] == []


def test_a_non_json_content_type_is_415(monkeypatch):
    world: dict = {}
    client = build(monkeypatch, world)
    canonical(post(client, headers={"Content-Type": "text/plain"}), code="VAL-0003", status=415)


# ---------------------------------------------------------------- the ledger


def test_a_stored_answer_is_replayed_exactly_and_no_row_is_locked(monkeypatch):
    stored = {"modelVersionId": VERSION_ID, "modelId": MODEL, "version": VERSION, "stage": "draft",
              "retentionPinnedUntil": wire(LATER), "extended": True}
    world = {"replay": stored}
    client = build(monkeypatch, world)
    response = post(client)
    assert response.status_code == 200 and response.json() == stored
    assert world["log"] == ["permission", "body-read", "set-lock-timeout", "advisory-lock", "permission", "ledger-read"]


def test_the_same_key_with_a_different_request_is_409(monkeypatch):
    world = {"replay_error": InvError(GRAPH_IDEMPOTENCY_CONFLICT, "different body")}
    client = build(monkeypatch, world)
    body = canonical(post(client), code="GRAPH-0002", status=409)
    assert body["detail"] == "That idempotency key was used with a different request."
    assert "version-lock" not in world["log"]


def test_the_ledger_payload_names_the_version_so_one_key_cannot_answer_for_another(monkeypatch):
    world: dict = {}
    client = build(monkeypatch, world)
    assert post(client).status_code == 200
    payload = world["ledger_reads"][0]["payload"]
    assert payload["modelId"] == MODEL and payload["version"] == VERSION


# ---------------------------------------------------------------- binding: the one 404


@pytest.mark.parametrize(
    "world",
    [
        {"parent": None},
        {"parent": Parent(tenant_id=OTHER_TENANT)},
        {"parent": Parent(project_id=OTHER_PROJECT)},
        {"version_row": None},
        {"version_row": Row(tenant_id=OTHER_TENANT)},
    ],
)
def test_every_way_the_path_fails_to_name_a_version_is_the_same_404(monkeypatch, world):
    client = build(monkeypatch, dict(world))
    body = canonical(post(client), code="RES-0004", status=404)
    assert body["detail"] == "No such model version."
    assert "service" not in world.get("log", []) if "log" in world else True


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
    assert "service" not in world["log"] and world["stored"] == [] and world["audits"] == []


def test_any_other_operational_failure_is_not_disguised_as_retryable(monkeypatch):
    world = {"lock_error": _operational("57P01")}
    client = build(monkeypatch, world)
    assert post(client).status_code == 500
    assert world["stored"] == []


# ---------------------------------------------------------------- the route<->service invariant


def test_a_service_that_returns_a_row_other_than_the_locked_one_is_a_failure_not_a_200(monkeypatch):
    world = {"service_returns": Row()}
    client = build(monkeypatch, world)
    assert post(client).status_code == 500
    assert world["stored"] == [] and world["audits"] == []


def test_a_service_refusal_is_translated_not_raw(monkeypatch):
    world = {"service_error": InvError(RES_ARTIFACT_NOT_FOUND, "model version not found")}
    client = build(monkeypatch, world)
    canonical(post(client), code="RES-0004", status=404)


# ---------------------------------------------------------------- registration and tables


def test_the_route_is_on_the_projects_router_once_where_business_dispatch_reads_it():
    paths = [route.path for route in projects.router.routes]
    assert paths.count("/v1" + model_retention.PIN_PATH) == 1
    assert model_retention.ENDPOINT.endswith(model_retention.PIN_PATH)


def test_every_reachable_business_code_is_in_the_translation_table():
    assert {AUTH_PROJECT_SCOPE, RES_ARTIFACT_NOT_FOUND, GRAPH_IDEMPOTENCY_CONFLICT} <= set(model_retention.TRANSLATION)


def test_the_shared_lock_helper_is_the_release_routes_own():
    assert model_retention._locked_version is model_release._locked_version
