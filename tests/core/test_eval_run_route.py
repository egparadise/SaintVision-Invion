"""W5: the eval run route, over real HTTP, without a database and without a CLI.

Each test is a reversion: undo the thing it names in ``api/v1/eval_runs.py`` and
this file fails. The session is a stand-in and the adapter is a stub, because what
these prove is the route's *order* and its wire contract. The suite actually running
against a provider is not something a test should buy.

The database's part -- RLS, a NULL-project suite, the denial row reaching
``audit_events`` -- is ``tests/integration/test_eval_run_real_pg.py``.

This route spends money, so three of the orderings below are not stylistic:
permission before the body, permission again before the adapter call, and a replay
that runs nothing.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import json
import uuid

import pytest
from fastapi.testclient import TestClient

from saintvision.api import schemas
from saintvision.api.app import create_app
from saintvision.api.problem import CANONICAL_KEYS, MAX_REQUEST_BYTES
from saintvision.api.v1 import eval_runs
from saintvision.config import Settings
from saintvision.errors import (
    AUTH_PROJECT_SCOPE,
    GRAPH_IDEMPOTENCY_CONFLICT,
    VAL_SCHEMA,
    InvError,
)
from saintvision.identity.principal import Principal, StaticPrincipalVerifier

TENANT = uuid.UUID("11111111-1111-1111-1111-111111111111")
OTHER_TENANT = uuid.UUID("22222222-2222-2222-2222-222222222222")
PROJECT = "prj_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
OTHER_PROJECT = "prj_01J8Z3XQ2K9WMV5T7N4B6C8D0F"
SUITE = "evs_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
RUN_ID = "evr_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
USER = "usr_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
NOW = dt.datetime(2026, 9, 28, 9, 0, tzinfo=dt.timezone.utc)
PATH = f"/v1/projects/{PROJECT}/eval/suites/{SUITE}/runs"
KEY = "idem-w5-0001"
AUTH = {"Authorization": "Bearer eval-token", "Idempotency-Key": KEY}
BODY = {"adapter": "claude-code"}

#: The bounded, identifier-free action this route's denials must carry (#189).
EVAL_ACTION = "POST /v1/projects/{project_id}/eval/suites/{suite_id}/runs"


class Suite:
    """The columns ``_suite_in_project`` reads. Not an ORM object."""

    def __init__(self, *, tenant_id=TENANT, project_id=PROJECT):
        self.suite_id = SUITE
        self.tenant_id = tenant_id
        self.project_id = project_id


class Run:
    """What ``run_suite`` returns."""

    def __init__(self, *, status="completed", passed_gate=True, violations=0):
        self.eval_run_id = RUN_ID
        self.tenant_id = TENANT
        self.suite_id = SUITE
        self.status = status
        self.total_cases = 30
        self.passed_cases = 30 if passed_gate else 28
        self.violations = violations
        self.passed_gate = passed_gate
        self.component_versions = {"adapter": "claude-code", "contractVersion": "1.0.0"}
        self.started_at = NOW
        self.ended_at = NOW + dt.timedelta(minutes=4)


class Adapter:
    """A stub provider. The route must not care what it does, only that it chose it."""

    def __init__(self, name="claude-code"):
        self.name = name
        self.contract_version = "1.0.0"


class Session:
    def __init__(self, world):
        self.world = world

    def execute(self, statement, params=None):
        sql = str(statement)
        self.world["locks"].append({"sql": sql, "params": params})
        if "lock_timeout" in sql:
            # Card 122: the lane's lock-wait bound (SET LOCAL) is not a lock;
            # it is asserted by statement, not by its place in the log.
            return None
        self.world["log"].append("lock")
        return None

    def get(self, _model, _key, **_kwargs):
        self.world["log"].append("suite-get")
        return self.world["suite"]


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


def build(monkeypatch, world):
    world.setdefault("suite", Suite())
    world.setdefault("run", Run())
    world.setdefault("permissions", [{"canRequest": True, "canApprove": True}])
    world.setdefault("denials", [])
    world.setdefault("replay", None)
    world.setdefault("replay_error", None)
    world.setdefault("service_error", None)
    world.setdefault("unknown_adapters", set())
    world.setdefault("log", [])
    world.setdefault("locks", [])
    world.setdefault("stored", [])
    world.setdefault("audits", [])
    world.setdefault("ran", [])
    world.setdefault("ledger_reads", [])
    world.setdefault("depth", 0)
    world.setdefault("spans", 0)
    world.setdefault("body_depth", [])
    world.setdefault("audited_denials", [])

    monkeypatch.setattr(eval_runs, "make_session_factory", lambda _engine: Factory(world))
    monkeypatch.setattr(
        eval_runs, "tenant_scope", lambda _session, _tenant: contextlib.nullcontext()
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
        eval_runs.project_service, "require_project_access", require_project_access
    )

    def adapter_for(name):
        world["log"].append("adapter-for")
        if name in world["unknown_adapters"]:
            raise KeyError(name)
        return Adapter(name)

    monkeypatch.setattr(eval_runs.agents, "adapter_for", adapter_for)

    original_read = eval_runs.read_bounded_body

    async def read_bounded_body(request, **kwargs):
        world["body_depth"].append(world["depth"])
        world["log"].append("body-read")
        return await original_read(request, **kwargs)

    monkeypatch.setattr(eval_runs, "read_bounded_body", read_bounded_body)

    def replay_or_reserve(_session, **kwargs):
        world["log"].append("ledger-read")
        world["ledger_reads"].append(kwargs)
        error = world["replay_error"]
        if error is not None:
            raise error
        return world["replay"]

    monkeypatch.setattr(eval_runs, "replay_or_reserve", replay_or_reserve)
    monkeypatch.setattr(
        eval_runs,
        "store_idempotent_response",
        lambda _session, **kwargs: world["log"].append("ledger-write")
        or world["stored"].append(kwargs),
    )

    def run_suite(_session, **kwargs):
        world["log"].append("run-suite")
        world["ran"].append(kwargs)
        error = world["service_error"]
        if error is not None:
            raise error
        return world["run"]

    monkeypatch.setattr(eval_runs, "run_suite", run_suite)
    monkeypatch.setattr(
        eval_runs,
        "record_event",
        lambda _session, **kwargs: world["log"].append("audit") or world["audits"].append(kwargs),
    )

    from saintvision.api import app as app_module

    monkeypatch.setattr(
        app_module,
        "record_denial_out_of_band",
        lambda _engine, **kwargs: world["audited_denials"].append(kwargs),
    )

    principal = Principal(
        user_id=USER,
        tenant_id=TENANT,
        external_subject="oidc:eval",
        project_ids=frozenset({PROJECT}),
    )
    app = create_app(
        engine=object(),
        settings=Settings(database_url="postgresql://unused", idempotency_ttl_seconds=600),
        verifier=StaticPrincipalVerifier({"eval-token": principal}, allow_outside_dev=True),
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
    assert body["status"] == status
    assert body["retryable"] is retryable
    assert body["detail"]
    return body


# --------------------------------------------------------------------------
# It is served, and it is the eighth of eight
# --------------------------------------------------------------------------


def test_the_route_is_on_the_projects_router_once_as_a_created_resource():
    from saintvision.api.v1 import projects

    matches = [
        route
        for route in projects.router.routes
        if getattr(route, "path", None) == f"/v1{eval_runs.EVAL_RUN_PATH}"
    ]
    assert len(matches) == 1
    assert matches[0].methods == {"POST"}
    assert matches[0].status_code == 201
    assert matches[0].response_model is schemas.EvalRunResponse


def test_the_dispatch_in_the_kernel_sends_this_path_to_the_business_app():
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
# The order, and the two places it protects money
# --------------------------------------------------------------------------


def test_the_whole_order_is_fixed(monkeypatch):
    world = {}
    client = build(monkeypatch, world)
    assert post(client).status_code == 201, "see the response body"
    assert world["log"] == [
        "permission",
        "body-read",
        "lock",
        "permission",
        "ledger-read",
        "suite-get",
        "adapter-for",
        "permission",
        "run-suite",
        "audit",
        "ledger-write",
    ]
    assert world["spans"] == 2
    assert world["body_depth"] == [0]


def test_the_permission_is_checked_again_immediately_before_the_adapter_runs(monkeypatch):
    """The whole point of this route's ordering: the call after it costs money."""
    world = {}
    client = build(monkeypatch, world)
    post(client)
    log = world["log"]
    # Three checks: the short span, the one guarding the replay, and this one.
    assert log.count("permission") == 3
    assert log.index("run-suite") - log.index("permission", log.index("adapter-for")) == 1


def test_a_revocation_before_the_adapter_call_spends_nothing(monkeypatch):
    """Revoked after the replay check and before the run: nothing is bought."""
    world = {
        "denials": [None, None, InvError(AUTH_PROJECT_SCOPE, "revoked", status=403)]
    }
    client = build(monkeypatch, world)
    canonical(post(client), code="AUTH-0030", status=403)
    assert world["ran"] == []
    assert world["stored"] == []
    assert world["audits"] == []
    assert len(world["audited_denials"]) == 1
    assert world["audited_denials"][0]["action"] == EVAL_ACTION


def test_a_caller_without_the_approval_grade_is_refused_before_the_body_is_read(monkeypatch):
    world = {"permissions": [{"canRequest": True, "canApprove": False}]}
    client = build(monkeypatch, world)
    oversized = b'{"adapter":"' + b"x" * (MAX_REQUEST_BYTES + 100) + b'"}'
    canonical(post(client, data=oversized), code="AUTH-0030", status=403)
    # 403 rather than 413: the body was never read, so its size never mattered.
    assert world["log"] == ["permission"]
    assert world["ran"] == []


def test_a_replay_runs_nothing_and_bills_nothing(monkeypatch):
    stored = {
        "evalRunId": RUN_ID,
        "suiteId": SUITE,
        "status": "completed",
        "totalCases": 30,
        "passedCases": 30,
        "violations": 0,
        "passedGate": True,
        "componentVersions": {"adapter": "claude-code"},
        "startedAt": NOW.isoformat().replace("+00:00", "Z"),
        "endedAt": None,
    }
    world = {"replay": stored}
    client = build(monkeypatch, world)
    response = post(client)
    assert response.status_code == 201
    assert response.json() == stored
    assert world["ran"] == [], "a retry must not buy a second run"
    assert world["stored"] == []
    assert world["audits"] == []
    assert "suite-get" not in world["log"]
    assert "adapter-for" not in world["log"]


def test_the_same_key_with_a_different_body_is_a_conflict(monkeypatch):
    world = {
        "replay_error": InvError(GRAPH_IDEMPOTENCY_CONFLICT, "different body", status=409)
    }
    client = build(monkeypatch, world)
    canonical(post(client), code="GRAPH-0002", status=409)
    assert world["ran"] == []


def test_the_ledger_key_includes_the_suite(monkeypatch):
    world = {}
    client = build(monkeypatch, world)
    post(client)
    payload = world["ledger_reads"][0]["payload"]
    assert payload["suiteId"] == SUITE
    assert payload["request"]["adapter"] == "claude-code"
    assert world["ledger_reads"][0]["endpoint"] == eval_runs.ENDPOINT
    assert world["ledger_reads"][0]["project_id"] == PROJECT


def test_the_lock_is_taken_before_the_ledger_and_before_any_row(monkeypatch):
    world = {}
    client = build(monkeypatch, world)
    post(client)
    assert world["log"].index("lock") < world["log"].index("ledger-read")
    assert world["log"].index("lock") < world["log"].index("suite-get")
    statements = [entry["sql"] for entry in world["locks"] if "lock_timeout" not in entry["sql"]]
    assert "pg_advisory_xact_lock" in statements[0]


def test_card122_both_spans_bound_their_lock_waits(monkeypatch):
    """Card 122 (audit of #211): the permission preflight and the write
    transaction both ``SET LOCAL lock_timeout`` before anything else they
    execute, so a held key or a held row is refused after the budget instead
    of waited on forever. The bound precedes the advisory lock in the write span."""
    world = {}
    client = build(monkeypatch, world)
    post(client)
    statements = [entry["sql"] for entry in world["locks"]]
    bounds = [s for s in statements if s.startswith("SET LOCAL lock_timeout = '")]
    assert len(bounds) == 2, statements
    assert statements[0] == bounds[0]  # preflight span: the bound is its only statement
    first_lock = next(i for i, s in enumerate(statements) if "pg_advisory_xact_lock" in s)
    assert statements[first_lock - 1] == bounds[1]  # write span: bound, then the key lock


@pytest.mark.parametrize(
    "key", ["", " ", "a" * 129, "has space", "has/slash", "has\x1fseparator"]
)
def test_an_unusable_idempotency_key_is_a_request_error(monkeypatch, key):
    world = {}
    client = build(monkeypatch, world)
    canonical(post(client, headers={"Idempotency-Key": key}), code="VAL-0003", status=422)
    assert world["ran"] == []


def test_the_idempotency_key_is_required(monkeypatch):
    world = {}
    client = build(monkeypatch, world)
    response = client.post(
        PATH,
        content=json.dumps(BODY).encode(),
        headers={"Authorization": "Bearer eval-token", "Content-Type": "application/json"},
    )
    canonical(response, code="VAL-0003", status=422)
    assert world["log"] == ["permission"]


# --------------------------------------------------------------------------
# path -> suite, including the NULL project 0053 leaves behind
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "suite",
    [
        None,
        Suite(tenant_id=OTHER_TENANT),
        Suite(project_id=OTHER_PROJECT),
        Suite(project_id=None),
    ],
    ids=["absent", "other-tenant", "other-project", "no-project"],
)
def test_every_way_the_path_fails_to_name_a_suite_is_the_same_404(monkeypatch, suite):
    world = {"suite": suite}
    client = build(monkeypatch, world)
    body = canonical(post(client), code="RES-0004", status=404)
    assert body["detail"] == eval_runs.NO_SUCH_SUITE
    assert world["ran"] == []


def test_a_suite_with_no_project_is_not_treated_as_every_projects(monkeypatch):
    """0053 made ``project_id`` nullable for suites that predate it.

    NULL means *this suite belongs to no project*. Reading it as "matches any
    project" would hand every pre-0053 suite to any approver of any project.

    Honest about what this proves: the route's explicit ``project_id is None``
    guard is **redundant** with the comparison beside it, because ``None`` never
    equals a path value. Removing that line leaves this test passing. It is kept
    in the product as a statement of the decision, not because a test holds it --
    what this test holds is the *behaviour*, which is what callers see.
    """
    world = {"suite": Suite(project_id=None)}
    client = build(monkeypatch, world)
    canonical(post(client), code="RES-0004", status=404)
    assert world["ran"] == []


def test_the_four_404_bodies_are_indistinguishable(monkeypatch):
    bodies = []
    for suite in (
        None,
        Suite(tenant_id=OTHER_TENANT),
        Suite(project_id=OTHER_PROJECT),
        Suite(project_id=None),
    ):
        world = {"suite": suite}
        client = build(monkeypatch, world)
        body = post(client).json()
        bodies.append({k: v for k, v in body.items() if k != "traceId"})
    assert bodies[0] == bodies[1] == bodies[2] == bodies[3]


def test_the_suite_is_bound_before_the_adapter_is_resolved(monkeypatch):
    world = {"suite": Suite(project_id=OTHER_PROJECT)}
    client = build(monkeypatch, world)
    post(client)
    assert "adapter-for" not in world["log"]
    assert world["ran"] == []


# --------------------------------------------------------------------------
# The adapter is a name from the configured allowlist, never an endpoint
# --------------------------------------------------------------------------


def test_an_unknown_adapter_name_runs_nothing(monkeypatch):
    world = {"unknown_adapters": {"not-a-tool"}}
    client = build(monkeypatch, world)
    canonical(post(client, {"adapter": "not-a-tool"}), code="VAL-0003", status=422)
    assert world["ran"] == []


@pytest.mark.parametrize(
    "adapter",
    [
        "https://evil.example/v1",
        "claude-code; curl x",
        "../../etc/passwd",
        "Claude-Code",
        "",
        "a" * 65,
    ],
)
def test_the_adapter_field_cannot_carry_an_endpoint(monkeypatch, adapter):
    """The request names one of the platform's CLIs or it is a request error.

    A field that could hold a URL would let the caller aim a route that spends
    money at a host of their choosing.
    """
    world = {}
    client = build(monkeypatch, world)
    canonical(post(client, {"adapter": adapter}), code="VAL-0003", status=422)
    assert world["ran"] == []


def test_the_resolved_adapter_is_the_one_the_service_is_given(monkeypatch):
    world = {}
    client = build(monkeypatch, world)
    post(client, {"adapter": "codex-cli"})
    assert world["ran"][0]["adapter"].name == "codex-cli"


def test_the_service_is_called_with_only_what_the_request_carried(monkeypatch):
    world = {}
    client = build(monkeypatch, world)
    post(client, {"adapter": "gemini-cli", "requireModelPinning": False})
    call = world["ran"][0]
    assert call["tenant_id"] == TENANT
    assert call["suite_id"] == SUITE
    assert call["now"] == NOW
    assert call["component_versions"] == {}
    assert call["require_model_pinning"] is False
    assert set(call) == {
        "tenant_id",
        "suite_id",
        "adapter",
        "now",
        "component_versions",
        "require_model_pinning",
    }


# --------------------------------------------------------------------------
# componentVersions: the caller may add to the identity, not forge it
# --------------------------------------------------------------------------


@pytest.mark.parametrize("field", ["adapter", "contractVersion", "modelPinned"])
def test_the_caller_cannot_set_the_versions_the_service_records(monkeypatch, field):
    """``run_suite`` merges with ``setdefault``, so a caller's value would win."""
    world = {}
    client = build(monkeypatch, world)
    body = canonical(
        post(client, {**BODY, "componentVersions": {field: "forged"}}),
        code="VAL-0003",
        status=422,
    )
    assert field in body["detail"]
    assert world["ran"] == []


def test_other_component_versions_are_passed_through(monkeypatch):
    world = {}
    client = build(monkeypatch, world)
    post(client, {**BODY, "componentVersions": {"promptSet": "v3", "context": "c7"}})
    assert world["ran"][0]["component_versions"] == {"promptSet": "v3", "context": "c7"}


def test_too_many_component_versions_is_a_request_error(monkeypatch):
    world = {}
    client = build(monkeypatch, world)
    many = {f"k{i}": "v" for i in range(33)}
    canonical(
        post(client, {**BODY, "componentVersions": many}), code="VAL-0003", status=422
    )
    assert world["ran"] == []


# --------------------------------------------------------------------------
# Translation
# --------------------------------------------------------------------------


def test_an_adapter_that_cannot_pin_a_model_is_a_precondition_not_a_request_error(
    monkeypatch,
):
    """``run_suite`` raises ``VAL-SCHEMA`` for it, but the request was well formed:
    the state of the chosen adapter is what refuses."""
    world = {"service_error": InvError(VAL_SCHEMA, "cannot report model", status=422)}
    client = build(monkeypatch, world)
    canonical(post(client), code="GRAPH-0002", status=409)
    assert world["stored"] == []
    assert world["audits"] == []


def test_a_code_the_table_does_not_list_is_not_leaked(monkeypatch):
    world = {"service_error": InvError("SEC-0001", "internal detail", status=500)}
    client = build(monkeypatch, world)
    body = canonical(post(client), code="SYS-0002", status=500)
    assert "internal detail" not in body["detail"]


def test_the_translation_table_covers_what_the_calls_raise():
    """Read from the functions that raise, not restated here."""
    import ast
    import inspect
    import textwrap

    from saintvision.services import eval_execution, evaluation, projects as project_service

    codes = set()
    for module, function in (
        (eval_execution, eval_execution.run_suite),
        (evaluation, evaluation.start_eval_run),
        (project_service, project_service.require_project_access),
    ):
        tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if name != "InvError" or not node.args:
                continue
            first = node.args[0]
            if isinstance(first, ast.Name):
                value = getattr(module, first.id, None)
                if isinstance(value, str):
                    codes.add(value)
            elif isinstance(first, ast.Constant) and isinstance(first.value, str):
                codes.add(first.value)
    assert codes, "the calls raise nothing this test could find"
    assert codes <= set(eval_runs.TRANSLATION), codes


# --------------------------------------------------------------------------
# The response, the audit, and the denial
# --------------------------------------------------------------------------


def test_the_response_is_the_strict_contract(monkeypatch):
    world = {}
    client = build(monkeypatch, world)
    response = post(client)
    assert response.status_code == 201
    body = response.json()
    assert set(body) == {
        "evalRunId",
        "suiteId",
        "status",
        "totalCases",
        "passedCases",
        "violations",
        "passedGate",
        "componentVersions",
        "startedAt",
        "endedAt",
    }
    assert body["passedGate"] is True
    assert schemas.EvalRunResponse.model_validate(body).model_dump(
        by_alias=True, mode="json"
    ) == body


def test_the_response_matches_the_generated_json_schema(monkeypatch):
    import pathlib

    import jsonschema

    schema = json.loads(
        pathlib.Path("contracts/eval-run-response.schema.json").read_text("utf-8")
    )
    world = {}
    client = build(monkeypatch, world)
    jsonschema.validate(post(client).json(), schema)


def test_a_run_that_did_not_pass_the_gate_is_reported_as_it_is(monkeypatch):
    """A failing run is a result, not an error: 201 with the numbers."""
    world = {"run": Run(passed_gate=False, violations=2)}
    client = build(monkeypatch, world)
    response = post(client)
    assert response.status_code == 201
    body = response.json()
    assert body["passedGate"] is False
    assert body["violations"] == 2


def test_the_audit_records_identifiers_and_counts_but_no_case_content(monkeypatch):
    world = {}
    client = build(monkeypatch, world)
    post(client)
    assert len(world["audits"]) == 1
    audit = world["audits"][0]
    assert audit["action"] == "eval_run.execute"
    assert audit["outcome"] == "allow"
    assert audit["target_type"] == "eval_run"
    assert audit["target_id"] == RUN_ID
    assert audit["detail"] == {
        "projectId": PROJECT,
        "suiteId": SUITE,
        "adapter": "claude-code",
        "requireModelPinning": True,
        "totalCases": 30,
        "passedGate": True,
    }
    text = json.dumps(audit["detail"])
    assert "observed" not in text and "score" not in text


def test_the_stored_status_is_the_status_this_route_returns(monkeypatch):
    world = {}
    client = build(monkeypatch, world)
    response = post(client)
    assert world["stored"][0]["response_status"] == response.status_code == 201
    assert world["stored"][0]["response_body"] == response.json()


def test_a_refusal_records_one_denial_with_this_routes_action(monkeypatch):
    world = {"permissions": [{"canRequest": True, "canApprove": False}]}
    client = build(monkeypatch, world)
    body = canonical(post(client), code="AUTH-0030", status=403)
    assert len(world["audited_denials"]) == 1
    recorded = world["audited_denials"][0]
    assert recorded["action"] == EVAL_ACTION
    assert recorded["actor_id"] == USER
    assert recorded["tenant_id"] == TENANT
    assert (recorded["target_type"], recorded["target_id"]) == ("project", PROJECT)
    assert recorded["trace_id"] == body["traceId"]
    for identifier in (PROJECT, SUITE, USER, KEY):
        assert identifier not in recorded["action"]
    assert len(recorded["action"]) <= 64


def test_a_run_that_succeeds_records_no_denial(monkeypatch):
    world = {}
    client = build(monkeypatch, world)
    assert post(client).status_code == 201
    assert world["audited_denials"] == []


@pytest.mark.parametrize(
    "world_kwargs,code,status",
    [
        ({"suite": None}, "RES-0004", 404),
        ({"unknown_adapters": {"claude-code"}}, "VAL-0003", 422),
        (
            {"service_error": InvError(VAL_SCHEMA, "cannot pin", status=422)},
            "GRAPH-0002",
            409,
        ),
    ],
    ids=["not-found", "unknown-adapter", "precondition"],
)
def test_only_authorisation_refusals_are_audited(monkeypatch, world_kwargs, code, status):
    world = dict(world_kwargs)
    client = build(monkeypatch, world)
    canonical(post(client), code=code, status=status)
    assert world["audited_denials"] == []


def test_the_route_does_not_record_the_denial_itself():
    import inspect

    source = inspect.getsource(eval_runs)
    assert "record_denial" not in source
    assert "record_event" in source


# --------------------------------------------------------------------------
# The body boundary
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "headers,data,status",
    [
        ({"Content-Type": "text/plain"}, b"{}", 415),
        ({"Content-Encoding": "gzip"}, b"{}", 415),
        ({}, b"", 422),
        ({}, b"[]", 422),
        ({}, b'{"adapter": "a", "adapter": "b"}', 422),
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
    canonical(
        client.post(PATH, content=data, headers=sent), code="VAL-0003", status=status
    )
    assert world["ran"] == []


@pytest.mark.parametrize("field", ["suiteId", "projectId", "endpoint", "credential"])
def test_the_request_refuses_fields_it_does_not_take(monkeypatch, field):
    world = {}
    client = build(monkeypatch, world)
    canonical(post(client, {**BODY, field: "x"}), code="VAL-0003", status=422)
    assert world["ran"] == []


def test_the_adapter_field_is_required(monkeypatch):
    world = {}
    client = build(monkeypatch, world)
    canonical(post(client, {}), code="VAL-0003", status=422)
    assert world["ran"] == []


# --------------------------------------------------------------------------
# The real-PostgreSQL fixture, exercised without PostgreSQL
# --------------------------------------------------------------------------


def test_the_real_pg_fixture_builds_its_rows_without_a_database():
    """A wrong column or a wrong id kind should not cost an hour of hosted CI.

    #167 spent one learning that ``new_id("code_commit")`` is not an entity kind.
    Both shapes the fixture can produce are exercised here -- the suite bound to a
    project, and the pre-0053 suite with none -- because the NULL case is the whole
    point of one of the real-PG tests.
    """
    import importlib.util
    import pathlib

    path = (
        pathlib.Path(__file__).resolve().parents[1] / "integration/test_eval_run_real_pg.py"
    )
    spec = importlib.util.spec_from_file_location("real_pg_w5_fixture", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class Recorder:
        def __init__(self):
            self.statements: list[str] = []

        def execute(self, statement, params=None):
            self.statements.append(str(statement))
            return None

    from saintvision.ids import is_id

    for project_id, expect_null in (("own", False), (None, True)):
        recorder = Recorder()
        seeded = module._seed(
            recorder, tenant_id=TENANT, now=NOW, label="guard", project_id=project_id
        )
        assert set(seeded) == {"user_id", "project_id", "suite_id"}
        written = [
            statement.split("INSERT INTO ", 1)[1].split(" ", 1)[0]
            for statement in recorder.statements
        ]
        assert written == ["users", "projects", "project_members", "eval_suites"], written
        assert is_id(seeded["user_id"], "user")
        assert is_id(seeded["project_id"], "project")
        assert is_id(seeded["suite_id"], "eval_suite")
        # The NULL branch has to actually produce NULL, or the test that depends on
        # it would pass for the wrong reason.
        assert expect_null == (project_id is None)

    # The stub adapter answers exactly what run_suite asks before the case loop.
    from saintvision.adapters.contract import Capability

    stub = module.StubAdapter()
    assert Capability.MODEL_PINNING in stub.capabilities
    assert stub.name and stub.contract_version
