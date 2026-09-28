"""G-03 phase one: the conformance status route, over real HTTP, without a database.

Each test is one of the reversions listed in the approved design
(``docs/vault/30_Development/G-03_conformance_결과_API_노출_설계.md`` §8, v1.2).
The numbering in the names is that list's, so a finding in review and a failure
here refer to the same item.

Item 12 -- another tenant's project answering the same denial -- is the database's
behaviour and lives in ``tests/integration/test_conformance_status_real_pg.py``.
Item 13 (``RES-0004`` for an unknown adapter name) is phase two: this route has no
adapter-name path variable, and a test for a path that does not exist would be a
test of nothing.
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import uuid

import jsonschema
import pytest
from fastapi.testclient import TestClient

from saintvision.adapters import agents, conformance
from saintvision.adapters.contract import CONTRACT_VERSION, Capability
from saintvision.api import schemas
from saintvision.api.app import create_app
from saintvision.api.deps import get_session
from saintvision.api.problem import CANONICAL_KEYS, MAX_REQUEST_BYTES
from saintvision.api.v1 import conformance_status
from saintvision.config import Settings
from saintvision.errors import AUTH_PROJECT_SCOPE, InvError
from saintvision.identity.principal import Principal, StaticPrincipalVerifier

TENANT = uuid.UUID("11111111-1111-1111-1111-111111111111")
PROJECT = "prj_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
ABSENT_PROJECT = "prj_01J8Z3XQ2K9WMV5T7N4B6C8D0F"
USER = "usr_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
NOW = dt.datetime(2026, 9, 28, 6, 0, tzinfo=dt.timezone.utc)
AUTH = {"Authorization": "Bearer conformance-token"}

RESPONSE_KEYS = {
    "status",
    "reason",
    "scope",
    "contractVersion",
    "adapters",
    "checks",
    "recordedAt",
}


def path(project_id=PROJECT):
    return f"/v1/projects/{project_id}/adapters/conformance"


def build(monkeypatch, *, permission=None, denial=None):
    """An app whose only database call is replaced, and whose principal is real."""
    calls = {"access": [], "denials": []}

    # The shared denial recorder (#195) writes through the app's engine, which
    # these tests do not have. Recorded here so a 403's audit call is asserted
    # rather than lost -- the same stub the sibling route harnesses use.
    from saintvision.api import app as app_module

    monkeypatch.setattr(
        app_module,
        "record_denial_out_of_band",
        lambda _engine, **kwargs: calls["denials"].append(kwargs),
    )

    def require_project_access(_session, *, tenant_id, project_id, user_id):
        calls["access"].append(
            {"tenant_id": tenant_id, "project_id": project_id, "user_id": user_id}
        )
        if denial is not None:
            raise denial
        return permission if permission is not None else {"canRequest": False, "canApprove": False}

    monkeypatch.setattr(
        conformance_status.project_service, "require_project_access", require_project_access
    )

    def exploded(*_args, **_kwargs):
        raise AssertionError("a read route must not run the conformance suite")

    monkeypatch.setattr(conformance, "run_conformance", exploded)

    principal = Principal(
        user_id=USER,
        tenant_id=TENANT,
        external_subject="oidc:conformance",
        project_ids=frozenset({PROJECT}),
    )
    app = create_app(
        engine=object(),
        settings=Settings(database_url="postgresql://unused"),
        verifier=StaticPrincipalVerifier(
            {"conformance-token": principal}, allow_outside_dev=True
        ),
        clock=lambda: NOW,
        check_partitions_on_startup=False,
    )
    # The route's only session use is the access check, which is replaced above.
    app.dependency_overrides[get_session] = lambda: object()
    return TestClient(app, raise_server_exceptions=False), calls


def get(client, *, project_id=PROJECT, headers=None, data=None):
    sent = dict(AUTH)
    sent.update(headers or {})
    return client.request("GET", path(project_id), content=data, headers=sent)


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
# It answers, and what it answers
# --------------------------------------------------------------------------


def test_a_member_is_told_that_nothing_has_been_observed(monkeypatch):
    client, _ = build(monkeypatch, permission={"canRequest": False, "canApprove": False})
    response = get(client)
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == RESPONSE_KEYS
    assert body["status"] == "NOT_OBSERVED"
    assert body["reason"] == conformance_status.NOT_OBSERVED_REASON
    assert body["scope"] == "control-plane-host"
    assert body["contractVersion"] == CONTRACT_VERSION
    assert body["recordedAt"] is None


# 1. The status stays one value.
def test_1_the_generated_schema_allows_exactly_one_status_and_no_boolean():
    schema = json.loads(
        pathlib.Path("contracts/conformance-status-response.schema.json").read_text("utf-8")
    )
    assert schema["properties"]["status"] == {
        "const": "NOT_OBSERVED",
        "title": "Status",
        "type": "string",
    }
    # RECORDED is not advertised before anything can produce it.
    assert "enum" not in schema["properties"]["status"]
    assert "conformant" not in schema["properties"]
    assert schema["additionalProperties"] is False
    assert schema["properties"]["scope"]["const"] == "control-plane-host"
    assert schema["properties"]["recordedAt"]["type"] == "null"
    assert set(schema["required"]) == RESPONSE_KEYS


@pytest.mark.parametrize("extra", ["conformant", "status_detail", "passed"])
def test_1b_the_response_model_refuses_a_widened_shape(extra):
    with pytest.raises(Exception):
        schemas.ConformanceStatusResponse.model_validate(
            {**_valid_payload(), extra: True}
        )


@pytest.mark.parametrize("value", ["RECORDED", "OBSERVED", "not_observed", ""])
def test_1c_the_model_refuses_any_other_status(value):
    with pytest.raises(Exception):
        schemas.ConformanceStatusResponse.model_validate({**_valid_payload(), "status": value})


# 2. No counts, not even zero.
@pytest.mark.parametrize("count", ["total", "passed", "failed", "skipped"])
def test_2_no_count_is_in_the_response_or_accepted_by_the_model(monkeypatch, count):
    client, _ = build(monkeypatch)
    assert count not in get(client).json()
    with pytest.raises(Exception):
        schemas.ConformanceStatusResponse.model_validate({**_valid_payload(), count: 0})


# 3. recordedAt is the absence of a measurement, not the time of this request.
def test_3_recorded_at_is_null_and_cannot_be_a_timestamp(monkeypatch):
    client, _ = build(monkeypatch)
    assert get(client).json()["recordedAt"] is None
    with pytest.raises(Exception):
        schemas.ConformanceStatusResponse.model_validate(
            {**_valid_payload(), "recordedAt": NOW.isoformat()}
        )


# 4. The reason is there and says why.
def test_4_the_reason_is_required_and_says_why(monkeypatch):
    client, _ = build(monkeypatch)
    reason = get(client).json()["reason"]
    assert "not persist" in reason and "recorded" in reason
    payload = _valid_payload()
    del payload["reason"]
    with pytest.raises(Exception):
        schemas.ConformanceStatusResponse.model_validate(payload)


# 5. The scope does not let the payload pretend to be project data.
def test_5_the_scope_is_the_host_and_cannot_become_the_project(monkeypatch):
    client, _ = build(monkeypatch)
    assert get(client).json()["scope"] == "control-plane-host"
    # The same word GET /v1/adapters uses for the same fact.
    from saintvision.api.v1 import adapters as adapters_route

    import inspect

    assert '"control-plane-host"' in inspect.getsource(adapters_route)
    for value in ("project", "tenant", "fleet"):
        with pytest.raises(Exception):
            schemas.ConformanceStatusResponse.model_validate(
                {**_valid_payload(), "scope": value}
            )


# 6. The route reports; it does not measure.
def test_6_the_route_does_not_run_the_suite(monkeypatch):
    """``build`` replaces ``run_conformance`` with something that raises, so a
    route that called it would 500 here rather than answer."""
    client, _ = build(monkeypatch)
    assert get(client).status_code == 200
    # And the name appears nowhere in the module's *code* -- only in the prose
    # explaining why. Checked over the syntax tree so a docstring mentioning it
    # cannot satisfy or break this.
    assert "run_conformance" not in _referenced_names(conformance_status)


# 7. The lists come from the product's own sources.
def test_7_the_checks_come_from_the_checklist_not_from_a_copy(monkeypatch):
    client, _ = build(monkeypatch)
    body = get(client).json()
    assert body["checks"] == [
        {"name": spec.name, "capabilityGated": spec.capability is not None}
        for spec in conformance.CHECKLIST
    ]
    # The count is not fixed in the contract: the response follows the list.
    assert len(body["checks"]) == len(conformance.CHECKLIST)


def test_7b_a_shorter_checklist_gives_a_shorter_response(monkeypatch):
    """Derivation rather than duplication: if ``CHECKLIST`` changes, so does the
    response. A hardcoded list in the route would ignore this."""
    client, _ = build(monkeypatch)
    trimmed = (
        conformance.CheckSpec("only_one", Capability.USAGE_REPORTING, lambda a, c: (True, "")),
    )
    monkeypatch.setattr(conformance_status, "CHECKLIST", trimmed)
    body = get(client).json()
    assert body["checks"] == [{"name": "only_one", "capabilityGated": True}]


def test_7c_the_adapters_come_from_agents_tools(monkeypatch):
    client, _ = build(monkeypatch)
    body = get(client).json()
    assert body["adapters"] == [tool.name for tool in agents.TOOLS]
    # Order preserved, for the reason GET /v1/adapters states: a status screen
    # should not reshuffle between refreshes.
    assert body["adapters"] == ["claude-code", "codex-cli", "gemini-cli", "antigravity"]


# --------------------------------------------------------------------------
# 8-11. Permission and existence non-disclosure
# --------------------------------------------------------------------------


# 8. The grade is read live, not from the sign-in snapshot.
def test_8_the_access_check_is_the_live_database_one(monkeypatch):
    client, calls = build(monkeypatch)
    get(client)
    assert calls["access"] == [
        {"tenant_id": TENANT, "project_id": PROJECT, "user_id": USER}
    ]
    # Principal.require_project is the snapshot and says so itself; the route
    # does not use it.
    import inspect

    assert "require_project" not in inspect.getsource(conformance_status.read_conformance_status)


# 9. Reading needs membership and no more.
def test_9_membership_alone_is_enough_to_read(monkeypatch):
    client, _ = build(monkeypatch, permission={"canRequest": False, "canApprove": False})
    assert get(client).status_code == 200


# 10. A non-member is refused, and the body says nothing about the project.
def test_10_a_non_member_is_refused_without_naming_the_project(monkeypatch):
    client, calls = build(
        monkeypatch, denial=InvError(AUTH_PROJECT_SCOPE, "no membership", status=403)
    )
    body = canonical(get(client), code="AUTH-0030", status=403)
    assert PROJECT not in json.dumps(body)
    # AC-02: the refusal is recorded once, at the shared handler boundary (#195).
    assert len(calls["denials"]) == 1
    recorded = calls["denials"][0]
    assert recorded["outcome"] == "deny"
    assert recorded["reason_code"] == "AUTH-0030"
    assert recorded["actor_type"] == "user"
    assert recorded["actor_id"] == USER
    assert recorded["tenant_id"] == TENANT
    # The project is the target because the path carried a well-formed id; the
    # tenant is the caller's, never the project's.
    assert (recorded["target_type"], recorded["target_id"]) == ("project", PROJECT)
    assert recorded["trace_id"] == body["traceId"]
    assert recorded["detail"] == {}
    # The action is the bounded template, with no identifier in it (#189).
    assert PROJECT not in recorded["action"]
    assert "adapters/conformance" in recorded["action"]


def test_10b_a_read_that_succeeds_records_no_denial(monkeypatch):
    client, calls = build(monkeypatch)
    assert get(client).status_code == 200
    assert calls["denials"] == []


def test_10c_the_route_does_not_record_the_denial_itself(monkeypatch):
    """One audit point. A route inside a transaction the refusal rolls back
    cannot be the place this is written (#195)."""
    import inspect

    source = inspect.getsource(conformance_status)
    assert "record_denial" not in source
    assert "record_event" not in source


# 11. An absent project is the same denial as one the caller cannot see.
def test_11_an_absent_project_is_the_same_denial(monkeypatch):
    bodies, actions = [], []
    for project_id in (PROJECT, ABSENT_PROJECT):
        client, calls = build(
            monkeypatch, denial=InvError(AUTH_PROJECT_SCOPE, "not visible", status=403)
        )
        body = get(client, project_id=project_id).json()
        bodies.append({key: value for key, value in body.items() if key != "traceId"})
        actions.append(calls["denials"][0]["action"])
    assert bodies[0] == bodies[1]
    # Both are audited, and under the same identifier-free action, so the trail
    # does not distinguish them either.
    assert actions[0] == actions[1]


# --------------------------------------------------------------------------
# 14-17. The contract
# --------------------------------------------------------------------------


# 14. The response is exactly the declared shape.
def test_14_the_response_validates_against_the_generated_schema(monkeypatch):
    schema = json.loads(
        pathlib.Path("contracts/conformance-status-response.schema.json").read_text("utf-8")
    )
    client, _ = build(monkeypatch)
    body = get(client).json()
    jsonschema.validate(body, schema)
    assert schemas.ConformanceStatusResponse.model_validate(body).model_dump(
        by_alias=True, mode="json"
    ) == body


# 15. The one error this route can give is the canonical body.
def test_15_the_translation_table_covers_what_the_call_can_raise():
    """Read from the function that raises rather than restated here."""
    from saintvision.services import projects as project_service

    raised = _raised_codes(project_service, project_service.require_project_access)
    assert raised, "the access check raises nothing this test could find"
    assert raised <= set(conformance_status.TRANSLATION), raised


def test_15b_a_code_the_table_does_not_list_becomes_sys_0002(monkeypatch):
    client, _ = build(monkeypatch, denial=InvError("SEC-0001", "internal detail", status=500))
    body = canonical(get(client), code="SYS-0002", status=500)
    assert "internal detail" not in body["detail"]


# 16. The generated artifact exists because the type is named ...Response.
def test_16_the_response_type_name_makes_the_schema_exist():
    from tools.export_schemas import exported

    # The collector is keyed by the contract file name it will write.
    collected = exported()
    assert "conformance-status-response" in collected
    assert collected["conformance-status-response"] is schemas.ConformanceStatusResponse
    # ConformanceCheckDescriptor is inlined as a $def rather than exported: the
    # collector only takes *Request/*Response, which is the rule #167 learned
    # when ModelReleaseResult produced no schema at all.
    assert schemas.ConformanceCheckDescriptor not in set(collected.values())
    assert "conformance-check-descriptor" not in collected
    schema = json.loads(
        pathlib.Path("contracts/conformance-status-response.schema.json").read_text("utf-8")
    )
    assert "ConformanceCheckDescriptor" in schema["$defs"]


# 17. It is served where the deployed topology looks.
def test_17_the_route_is_registered_on_the_projects_router_once():
    from saintvision.api.v1 import projects

    matches = [
        route
        for route in projects.router.routes
        if getattr(route, "path", None) == f"/v1{conformance_status.CONFORMANCE_PATH}"
    ]
    assert len(matches) == 1
    assert matches[0].methods == {"GET"}
    assert matches[0].response_model is schemas.ConformanceStatusResponse


def test_17b_the_kernel_dispatch_sends_this_path_to_the_business_app():
    from fastapi import FastAPI
    from inv.business_surface import BusinessDispatch

    kernel, business = FastAPI(), FastAPI()

    @kernel.get("/{rest:path}")
    def kernel_catch_all(rest: str):
        return {"servedBy": "kernel"}

    @business.get("/{rest:path}")
    def business_catch_all(rest: str):
        return {"servedBy": "business"}

    with TestClient(BusinessDispatch(kernel, business)) as client:
        assert client.get(path()).json() == {"servedBy": "business"}


# --------------------------------------------------------------------------
# The body boundary on a read
# --------------------------------------------------------------------------


def test_a_body_on_this_get_is_refused(monkeypatch):
    client, _ = build(monkeypatch)
    canonical(get(client, data=b"{}"), code="VAL-0003", status=422)


def test_an_oversized_body_is_refused_before_it_is_buffered(monkeypatch):
    client, _ = build(monkeypatch)
    canonical(
        get(client, data=b"x" * (MAX_REQUEST_BYTES + 1)), code="VAL-0003", status=413
    )


def test_membership_is_checked_before_the_body_is_read(monkeypatch):
    """A non-member learns nothing from how their body is judged: 403, not 413."""
    client, calls = build(
        monkeypatch, denial=InvError(AUTH_PROJECT_SCOPE, "no membership", status=403)
    )
    canonical(
        get(client, data=b"x" * (MAX_REQUEST_BYTES + 100)), code="AUTH-0030", status=403
    )
    assert len(calls["access"]) == 1
    assert len(calls["denials"]) == 1


def test_no_credential_never_reaches_the_access_check(monkeypatch):
    """The refusal happens in the dependency, before this route runs.

    The exact status is deliberately not asserted here. An anonymous denial is
    audited out of band against the engine, and this harness has no engine, so
    what comes back depends on a boundary this route does not own -- the same
    boundary #184 reports 500 on under the real application role. What matters
    here is that nothing about the project was looked at.
    """
    client, calls = build(monkeypatch)
    response = client.get(path())
    assert response.status_code != 200
    assert calls["access"] == []


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _valid_payload():
    return {
        "status": "NOT_OBSERVED",
        "reason": conformance_status.NOT_OBSERVED_REASON,
        "scope": "control-plane-host",
        "contractVersion": CONTRACT_VERSION,
        "adapters": ["claude-code"],
        "checks": [{"name": "declares_contract_version", "capabilityGated": False}],
        "recordedAt": None,
    }


def _referenced_names(module):
    """Every name the module's code refers to, ignoring strings and comments."""
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(module))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.alias):
            names.add(node.name.split(".")[-1])
            if node.asname:
                names.add(node.asname)
    return names


def _raised_codes(module, function):
    """The code constants ``function`` passes as ``InvError``'s first argument.

    Read from the syntax tree of the thing that raises, so a new refusal shows up
    as a failure here rather than as ``SYS-0002`` in production.
    """
    import ast
    import inspect
    import textwrap

    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    codes = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        callee = node.func
        name = getattr(callee, "id", None) or getattr(callee, "attr", None)
        if name != "InvError" or not node.args:
            continue
        first = node.args[0]
        if isinstance(first, ast.Name):
            value = getattr(module, first.id, None)
            if isinstance(value, str):
                codes.add(value)
        elif isinstance(first, ast.Constant) and isinstance(first.value, str):
            codes.add(first.value)
    return codes


# --------------------------------------------------------------------------
# The real-PostgreSQL fixture, exercised without PostgreSQL
# --------------------------------------------------------------------------


def test_the_real_pg_fixture_builds_its_rows_without_a_database():
    """A wrong column or a wrong id kind should not cost an hour of hosted CI.

    #167 spent one learning that ``new_id("code_commit")`` is not an entity kind,
    with every assertion behind it unrun. Importing the fixture and handing it a
    connection that only records statements catches that class here.
    """
    import importlib.util

    path = (
        pathlib.Path(__file__).resolve().parents[1]
        / "integration/test_conformance_status_real_pg.py"
    )
    spec = importlib.util.spec_from_file_location("real_pg_conformance_fixture", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class Recorder:
        def __init__(self):
            self.statements: list[str] = []

        def execute(self, statement, params=None):
            self.statements.append(str(statement))
            return None

    recorder = Recorder()
    seeded = module._seed(recorder, tenant_id=TENANT, now=NOW, label="fixture-guard")
    assert set(seeded) == {"user_id", "project_id"}
    written = [
        statement.split("INSERT INTO ", 1)[1].split(" ", 1)[0]
        for statement in recorder.statements
    ]
    # A user, a project and a membership -- and no model or version: this route
    # reads static facts and needs no registry rows at all.
    assert written == ["users", "projects", "project_members"], written

    from saintvision.ids import is_id

    assert is_id(seeded["user_id"], "user")
    assert is_id(seeded["project_id"], "project")

    # The default role is deliberately the one without the approval grade: reading
    # this route needs membership and nothing more, so the real-PG happy path must
    # not be seeded with an approver.
    import inspect

    assert 'role="requester"' in inspect.getsource(module._seed)
