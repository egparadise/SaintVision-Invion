"""G-03: the conformance routes over real HTTP, without a database.

Stage one's items (design ``G-03_conformance_결과_API_노출_설계`` §8 v1.2) keep
their numbers below. Stage two's items are the design
``G-03_conformance_실행기록_저장과_노출_2단계_설계`` v1.2 §5 tests T1-T15 that a
stand-in can establish; the ones only a database can (T8, T9, T10, the DB side
of T2/T3, T13 on stored rows) are ``tests/integration/test_conformance_records_real_pg.py``.

The harness replaces three things: the session factory (a stand-in that counts
the transaction spans and records the ``SET LOCAL`` statements each one issues),
the access check and the record reader. Everything else -- the principal, the
body boundary, the lock-wait bound, the canonical problem handler, the response
models -- is the product's own.
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import uuid

import jsonschema
import pytest
from fastapi.testclient import TestClient

import contextlib

from sqlalchemy.exc import OperationalError

from saintvision.adapters import agents, conformance
from saintvision.adapters.contract import CONTRACT_VERSION, Capability
from saintvision.api import schemas
from saintvision.api.app import create_app
from saintvision.api.lock_wait import LOCK_WAIT_DETAIL
from saintvision.api.problem import CANONICAL_KEYS, MAX_REQUEST_BYTES
from saintvision.api.v1 import conformance_status
from saintvision.config import Settings
from saintvision.errors import AUTH_PROJECT_SCOPE, InvError
from saintvision.identity.principal import Principal, StaticPrincipalVerifier
from saintvision.services import conformance_records
from saintvision.services.conformance_records import Outcome, Recorded, StoredRecordInvalid

TENANT = uuid.UUID("11111111-1111-1111-1111-111111111111")
HOST = uuid.UUID("0f8fad5b-d9cb-469f-a165-70867728950e")
PROJECT = "prj_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
ABSENT_PROJECT = "prj_01J8Z3XQ2K9WMV5T7N4B6C8D0F"
USER = "usr_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
NOW = dt.datetime(2026, 9, 28, 6, 0, tzinfo=dt.timezone.utc)
EARLIER = NOW - dt.timedelta(hours=1)
AUTH = {"Authorization": "Bearer conformance-token"}
TOOL_NAMES = [tool.name for tool in agents.TOOLS]

NOT_OBSERVED_KEYS = {
    "status",
    "reason",
    "scope",
    "contractVersion",
    "adapters",
    "checks",
    "recordedAt",
}
RECORDED_KEYS = {
    "status",
    "scope",
    "contractVersion",
    "adapters",
    "checks",
    "records",
    "latestRecordedAt",
}
ITEM_KEYS = {
    "adapter",
    "subject",
    "provenance",
    "contractVersion",
    "suiteContractVersion",
    "total",
    "passed",
    "failed",
    "skipped",
    "outcomes",
    "recordedAt",
}
ADAPTER_NOT_OBSERVED_KEYS = {
    "status",
    "reason",
    "scope",
    "adapter",
    "contractVersion",
    "checks",
    "recordedAt",
}
ADAPTER_RECORDED_KEYS = ITEM_KEYS | {"status", "scope"}
OUTCOME_KEYS = {"name", "passed", "skipped"}

CONTRACTS = pathlib.Path("contracts")


def path(project_id=PROJECT):
    return f"/v1/projects/{project_id}/adapters/conformance"


def adapter_path(name, project_id=PROJECT):
    return f"/v1/projects/{project_id}/adapters/{name}/conformance"


def outcomes(*, failed=(), skipped=("declared_server_cancel_actually_stops",)):
    """Every check in CHECKLIST order: the fixture adapter's real result shape."""
    return tuple(
        Outcome(
            name=spec.name,
            passed=spec.name not in failed and spec.name not in skipped,
            skipped=spec.name in skipped,
        )
        for spec in conformance.CHECKLIST
    )


def recorded(adapter, *, recorded_at=NOW, record_id="cfr_01J8Z3XQ2K9WMV5T7N4B6C8D0E", **overrides):
    """A validated record as the reader hands it out; counts derived unless overridden."""
    outs = overrides.pop("outcomes", outcomes())
    values = dict(
        record_id=record_id,
        adapter=adapter,
        subject="fixture-adapter",
        provenance="in-server",
        contract_version=CONTRACT_VERSION,
        suite_contract_version=CONTRACT_VERSION,
        total=len(outs),
        passed=sum(1 for o in outs if o.passed and not o.skipped),
        failed=sum(1 for o in outs if not o.passed and not o.skipped),
        skipped=sum(1 for o in outs if o.skipped),
        outcomes=outs,
        recorded_at=recorded_at,
    )
    values.update(overrides)
    return Recorded(**values)


class _Session:
    """A session stand-in: records the SET LOCALs the spans issue and counts them."""

    def __init__(self, calls):
        self.calls = calls

    def in_transaction(self):
        return True

    def execute(self, statement, params=None):
        self.calls["statements"].append(str(statement))
        return None

    @contextlib.contextmanager
    def begin(self):
        self.calls["spans"] += 1
        yield


def _operational(sqlstate):
    class Orig(Exception):
        pass

    orig = Orig("locked")
    orig.sqlstate = sqlstate
    return OperationalError("SELECT ... FROM project_members", {}, orig)


def build(
    monkeypatch,
    *,
    permission=None,
    denial=None,
    records=None,
    host_id=HOST,
    reader=None,
    lock_timeout_ms=5_000,
):
    """An app whose session factory, access check and record reader are replaced.

    ``records`` is what the reader returns, keyed by adapter; ``reader`` replaces
    the reader wholesale (to raise). The stand-in asserts the host binding: it
    is called with this app's host id and the adapters in the platform order.
    """
    calls = {"access": [], "denials": [], "reads": [], "statements": [], "spans": 0}

    @contextlib.contextmanager
    def session_cm():
        yield _Session(calls)

    monkeypatch.setattr(conformance_status, "make_session_factory", lambda _engine: session_cm)

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

    def latest(_session, *, host_id, adapters):
        calls["reads"].append({"host_id": host_id, "adapters": list(adapters)})
        if reader is not None:
            return reader(host_id=host_id, adapters=adapters)
        found = records or {}
        return {name: found[name] for name in adapters if name in found}

    monkeypatch.setattr(conformance_status, "latest_records", latest)

    def exploded(*_args, **_kwargs):
        raise AssertionError("a read route must not run the conformance suite")

    monkeypatch.setattr(conformance, "run_conformance", exploded)
    monkeypatch.setattr(conformance_records, "run_conformance", exploded)

    principal = Principal(
        user_id=USER,
        tenant_id=TENANT,
        external_subject="oidc:conformance",
        project_ids=frozenset({PROJECT}),
    )
    app = create_app(
        engine=object(),
        settings=Settings(
            database_url="postgresql://unused",
            control_plane_host_id=host_id,
            business_lock_timeout_ms=lock_timeout_ms,
        ),
        verifier=StaticPrincipalVerifier(
            {"conformance-token": principal}, allow_outside_dev=True
        ),
        clock=lambda: NOW,
        check_partitions_on_startup=False,
    )
    return TestClient(app, raise_server_exceptions=False), calls


def get(client, *, project_id=PROJECT, headers=None, data=None, name=None):
    sent = dict(AUTH)
    sent.update(headers or {})
    target = path(project_id) if name is None else adapter_path(name, project_id)
    return client.request("GET", target, content=data, headers=sent)


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


def schema(name):
    return json.loads((CONTRACTS / f"{name}.schema.json").read_text("utf-8"))


# --------------------------------------------------------------------------
# Nothing recorded: the stage-one shape, exactly
# --------------------------------------------------------------------------


def test_a_member_is_told_that_nothing_has_been_observed(monkeypatch):
    client, _ = build(monkeypatch, permission={"canRequest": False, "canApprove": False})
    response = get(client)
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == NOT_OBSERVED_KEYS
    assert body["status"] == "NOT_OBSERVED"
    assert body["reason"] == conformance_status.NOT_OBSERVED_REASON
    assert body["scope"] == "control-plane-host"
    assert body["contractVersion"] == CONTRACT_VERSION
    assert body["recordedAt"] is None


# 1. The stage-one contract file did not move (T5a): one status, no boolean, no
#    counts, recordedAt only null, the same seven keys.
def test_1_the_stage_one_schema_is_unchanged():
    document = schema("conformance-status-response")
    assert document["properties"]["status"] == {
        "const": "NOT_OBSERVED",
        "title": "Status",
        "type": "string",
    }
    assert "enum" not in document["properties"]["status"]
    assert "conformant" not in document["properties"]
    assert not {"total", "passed", "failed", "skipped", "records", "latestRecordedAt"} & set(
        document["properties"]
    )
    assert document["additionalProperties"] is False
    assert document["properties"]["scope"]["const"] == "control-plane-host"
    assert document["properties"]["recordedAt"]["type"] == "null"
    assert set(document["required"]) == NOT_OBSERVED_KEYS


@pytest.mark.parametrize("extra", ["conformant", "status_detail", "passed", "records"])
def test_1b_the_not_observed_model_refuses_a_widened_shape(extra):
    with pytest.raises(Exception):
        schemas.ConformanceStatusResponse.model_validate({**_valid_payload(), extra: True})


@pytest.mark.parametrize("value", ["RECORDED", "OBSERVED", "not_observed", ""])
def test_1c_the_not_observed_model_refuses_any_other_status(value):
    with pytest.raises(Exception):
        schemas.ConformanceStatusResponse.model_validate({**_valid_payload(), "status": value})


# 2. No counts, not even zero, while nothing is recorded.
@pytest.mark.parametrize("count", ["total", "passed", "failed", "skipped"])
def test_2_no_count_is_in_the_empty_response_or_accepted_by_the_model(monkeypatch, count):
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


# 4 / T5b. The reason says why -- and no longer says the platform does not persist.
def test_4_the_reason_states_the_absence_and_not_the_stage_one_sentence(monkeypatch):
    client, _ = build(monkeypatch)
    reason = get(client).json()["reason"]
    assert reason == conformance_status.NOT_OBSERVED_REASON
    assert "recorded" in reason
    # Stage one's claim. With 0055 in place it would be false.
    assert "not persist" not in reason
    assert "yet" not in reason
    for constant in (
        conformance_status.NOT_OBSERVED_REASON,
        conformance_status.ADAPTER_NOT_OBSERVED_REASON,
    ):
        assert 1 <= len(constant) <= 300
    payload = _valid_payload()
    del payload["reason"]
    with pytest.raises(Exception):
        schemas.ConformanceStatusResponse.model_validate(payload)


# 5. The scope does not let the payload pretend to be project data.
def test_5_the_scope_is_the_host_and_cannot_become_the_project(monkeypatch):
    client, _ = build(monkeypatch)
    assert get(client).json()["scope"] == "control-plane-host"
    from saintvision.api.v1 import adapters as adapters_route

    import inspect

    assert '"control-plane-host"' in inspect.getsource(adapters_route)
    for value in ("project", "tenant", "fleet"):
        with pytest.raises(Exception):
            schemas.ConformanceStatusResponse.model_validate({**_valid_payload(), "scope": value})
        with pytest.raises(Exception):
            schemas.ConformanceStatusRecordedResponse.model_validate(
                {**_recorded_payload(), "scope": value}
            )


# 6 / T11. The routes report; they do not measure.
def test_6_the_routes_do_not_run_the_suite(monkeypatch):
    """``build`` replaces ``run_conformance`` with something that raises, so a
    route that called it would 500 here rather than answer."""
    client, _ = build(monkeypatch, records={"codex-cli": recorded("codex-cli")})
    assert get(client).status_code == 200
    assert get(client, name="codex-cli").status_code == 200
    assert get(client, name="claude-code").status_code == 200
    # And neither the suite nor the producer nor any adapter class is referred
    # to by the module's *code* -- only by the prose explaining why.
    names = _referenced_names(conformance_status)
    for forbidden in (
        "run_conformance",
        "record_fixture_conformance",
        "ReferenceAdapter",
        "CliAdapter",
        "adapter_for",
        "subprocess",
    ):
        assert forbidden not in names, forbidden


# 7. The lists come from the product's own sources.
def test_7_the_checks_come_from_the_checklist_not_from_a_copy(monkeypatch):
    client, _ = build(monkeypatch)
    body = get(client).json()
    assert body["checks"] == [
        {"name": spec.name, "capabilityGated": spec.capability is not None}
        for spec in conformance.CHECKLIST
    ]
    assert len(body["checks"]) == len(conformance.CHECKLIST)


def test_7b_a_shorter_checklist_gives_a_shorter_response(monkeypatch):
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
    assert body["adapters"] == TOOL_NAMES
    assert body["adapters"] == ["claude-code", "codex-cli", "gemini-cli", "antigravity"]


# --------------------------------------------------------------------------
# 8-11. Permission and existence non-disclosure, on both routes
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", [None, "codex-cli"])
def test_8_the_access_check_is_the_live_database_one(monkeypatch, name):
    client, calls = build(monkeypatch)
    get(client, name=name)
    assert calls["access"] == [{"tenant_id": TENANT, "project_id": PROJECT, "user_id": USER}]
    import inspect

    assert "require_project" not in inspect.getsource(conformance_status.read_conformance_status)
    assert "require_project" not in inspect.getsource(conformance_status.read_adapter_conformance)


@pytest.mark.parametrize("name", [None, "codex-cli"])
def test_9_membership_alone_is_enough_to_read(monkeypatch, name):
    client, _ = build(monkeypatch, permission={"canRequest": False, "canApprove": False})
    assert get(client, name=name).status_code == 200


@pytest.mark.parametrize("name", [None, "codex-cli"])
def test_10_a_non_member_is_refused_without_naming_the_project(monkeypatch, name):
    client, calls = build(
        monkeypatch, denial=InvError(AUTH_PROJECT_SCOPE, "no membership", status=403)
    )
    body = canonical(get(client, name=name), code="AUTH-0030", status=403)
    assert PROJECT not in json.dumps(body)
    assert len(calls["denials"]) == 1
    recorded_denial = calls["denials"][0]
    assert recorded_denial["outcome"] == "deny"
    assert recorded_denial["reason_code"] == "AUTH-0030"
    assert recorded_denial["actor_type"] == "user"
    assert recorded_denial["actor_id"] == USER
    assert recorded_denial["tenant_id"] == TENANT
    assert (recorded_denial["target_type"], recorded_denial["target_id"]) == ("project", PROJECT)
    assert recorded_denial["trace_id"] == body["traceId"]
    assert recorded_denial["detail"] == {}
    assert PROJECT not in recorded_denial["action"]
    assert "conformance" in recorded_denial["action"]
    if name is not None:
        assert name not in recorded_denial["action"]
    # A non-member is refused before the host or the records are looked at.
    assert calls["reads"] == []


def test_10b_a_read_that_succeeds_records_no_denial(monkeypatch):
    client, calls = build(monkeypatch)
    assert get(client).status_code == 200
    assert get(client, name="codex-cli").status_code == 200
    assert calls["denials"] == []


def test_10c_the_route_does_not_record_the_denial_itself():
    import inspect

    source = inspect.getsource(conformance_status)
    assert "record_denial" not in source
    assert "record_event" not in source


@pytest.mark.parametrize("name", [None, "codex-cli"])
def test_11_an_absent_project_is_the_same_denial(monkeypatch, name):
    bodies, actions = [], []
    for project_id in (PROJECT, ABSENT_PROJECT):
        client, calls = build(
            monkeypatch, denial=InvError(AUTH_PROJECT_SCOPE, "not visible", status=403)
        )
        body = get(client, project_id=project_id, name=name).json()
        bodies.append({key: value for key, value in body.items() if key != "traceId"})
        actions.append(calls["denials"][0]["action"])
    assert bodies[0] == bodies[1]
    assert actions[0] == actions[1]


# --------------------------------------------------------------------------
# RECORDED: the list route with records
# --------------------------------------------------------------------------


def test_a_record_turns_the_list_into_the_recorded_branch(monkeypatch):
    client, calls = build(monkeypatch, records={"codex-cli": recorded("codex-cli")})
    body = get(client).json()
    assert set(body) == RECORDED_KEYS
    assert body["status"] == "RECORDED"
    assert body["scope"] == "control-plane-host"
    assert body["contractVersion"] == CONTRACT_VERSION
    assert body["adapters"] == TOOL_NAMES
    assert body["checks"] == [
        {"name": spec.name, "capabilityGated": spec.capability is not None}
        for spec in conformance.CHECKLIST
    ]
    assert len(body["records"]) == 1
    item = body["records"][0]
    assert set(item) == ITEM_KEYS
    assert item["adapter"] == "codex-cli"
    assert item["subject"] == "fixture-adapter"
    assert item["provenance"] == "in-server"
    assert (item["total"], item["passed"], item["failed"], item["skipped"]) == (15, 14, 0, 1)
    assert item["recordedAt"] == "2026-09-28T06:00:00Z"
    # The reader was asked for this host and the platform's target list.
    assert calls["reads"] == [{"host_id": HOST, "adapters": TOOL_NAMES}]


# T1. No detail anywhere.
def test_T1_outcomes_carry_name_passed_skipped_and_never_detail(monkeypatch):
    client, _ = build(monkeypatch, records={"codex-cli": recorded("codex-cli")})
    for body in (get(client).json()["records"][0], get(client, name="codex-cli").json()):
        assert body["outcomes"]
        for outcome in body["outcomes"]:
            assert set(outcome) == OUTCOME_KEYS
    assert "detail" not in json.dumps(get(client).json())
    with pytest.raises(Exception):
        schemas.ConformanceCheckOutcome.model_validate(
            {"name": "declares_contract_version", "passed": True, "skipped": False, "detail": "x"}
        )
    for name in ("conformance-status-recorded-response", "adapter-conformance-recorded-response"):
        outcome = schema(name)["$defs"]["ConformanceCheckOutcome"]
        assert set(outcome["properties"]) == OUTCOME_KEYS
        assert outcome["additionalProperties"] is False


# T2. Counts are one measurement.
@pytest.mark.parametrize(
    "change",
    [
        {"total": 16},
        {"passed": 13},
        {"failed": 1},
        {"skipped": 0},
        {"passed": 15, "skipped": 0},
    ],
)
def test_T2_the_models_refuse_counts_that_do_not_agree_with_the_outcomes(change):
    item = {**_item_payload(), **change}
    with pytest.raises(Exception):
        schemas.ConformanceRecordItem.model_validate(item)
    with pytest.raises(Exception):
        schemas.AdapterConformanceRecordedResponse.model_validate(
            {**item, "status": "RECORDED", "scope": "control-plane-host"}
        )
    with pytest.raises(Exception):
        schemas.ConformanceStatusRecordedResponse.model_validate(
            {**_recorded_payload(), "records": [item]}
        )


def test_T2b_an_outcome_cannot_be_both_passed_and_skipped():
    with pytest.raises(Exception):
        schemas.ConformanceCheckOutcome.model_validate(
            {"name": "declares_contract_version", "passed": True, "skipped": True}
        )
    item = _item_payload()
    item["outcomes"][0] = {**item["outcomes"][0], "passed": True, "skipped": True}
    with pytest.raises(Exception):
        schemas.ConformanceRecordItem.model_validate(item)


def test_T2c_a_count_is_an_integer_not_a_boolean_or_a_string():
    for value in (True, "14", 14.0, -1):
        with pytest.raises(Exception):
            schemas.ConformanceRecordItem.model_validate({**_item_payload(), "passed": value})


# T3. subject and provenance: required, and only the values this stage produces.
@pytest.mark.parametrize("field", ["subject", "provenance"])
def test_T3_subject_and_provenance_are_required(field):
    item = _item_payload()
    del item[field]
    with pytest.raises(Exception):
        schemas.ConformanceRecordItem.model_validate(item)
    with pytest.raises(Exception):
        schemas.AdapterConformanceRecordedResponse.model_validate(
            {**item, "status": "RECORDED", "scope": "control-plane-host"}
        )


@pytest.mark.parametrize(
    "field, value",
    [
        ("subject", "installed-cli"),
        ("subject", "fixture"),
        ("subject", ""),
        ("provenance", "hosted-ci-import"),
        ("provenance", "in-request"),
        ("provenance", ""),
    ],
)
def test_T3b_only_the_producible_subject_and_provenance_are_accepted(field, value):
    with pytest.raises(Exception):
        schemas.ConformanceRecordItem.model_validate({**_item_payload(), field: value})
    for name in ("conformance-status-recorded-response", "adapter-conformance-recorded-response"):
        document = schema(name)
        holder = document["$defs"]["ConformanceRecordItem"] if "ConformanceRecordItem" in document["$defs"] else document
        assert holder["properties"]["subject"] == {
            "const": "fixture-adapter",
            "title": "Subject",
            "type": "string",
        }
        assert holder["properties"]["provenance"] == {
            "const": "in-server",
            "title": "Provenance",
            "type": "string",
        }


# T4. The time keys.
def test_T4_latest_recorded_at_is_the_maximum_and_the_aggregate_has_no_recorded_at(monkeypatch):
    client, _ = build(
        monkeypatch,
        records={
            "claude-code": recorded("claude-code", recorded_at=EARLIER),
            "codex-cli": recorded("codex-cli", recorded_at=NOW),
            "gemini-cli": recorded("gemini-cli", recorded_at=EARLIER),
        },
    )
    body = get(client).json()
    assert "recordedAt" not in body
    assert body["latestRecordedAt"] == "2026-09-28T06:00:00Z"
    assert body["latestRecordedAt"] == max(item["recordedAt"] for item in body["records"])
    assert [item["recordedAt"] for item in body["records"]] == [
        "2026-09-28T05:00:00Z",
        "2026-09-28T06:00:00Z",
        "2026-09-28T05:00:00Z",
    ]
    single = get(client, name="claude-code").json()
    assert single["recordedAt"] == "2026-09-28T05:00:00Z"
    assert "latestRecordedAt" not in single


def test_T4b_the_models_refuse_a_wrong_latest_and_a_stray_recorded_at():
    payload = _recorded_payload()
    with pytest.raises(Exception):
        schemas.ConformanceStatusRecordedResponse.model_validate(
            {**payload, "latestRecordedAt": EARLIER.isoformat()}
        )
    with pytest.raises(Exception):
        schemas.ConformanceStatusRecordedResponse.model_validate(
            {**payload, "recordedAt": None}
        )
    with pytest.raises(Exception):
        schemas.ConformanceStatusRecordedResponse.model_validate(
            {**payload, "reason": "anything"}
        )
    with pytest.raises(Exception):
        schemas.AdapterConformanceRecordedResponse.model_validate(
            {**_item_payload(), "status": "RECORDED", "scope": "control-plane-host", "recordedAt": None}
        )
    # A naive timestamp is not a time.
    with pytest.raises(Exception):
        schemas.ConformanceRecordItem.model_validate(
            {**_item_payload(), "recordedAt": "2026-09-28T06:00:00"}
        )


def test_T4c_records_follow_the_adapters_order_and_omit_the_unrecorded(monkeypatch):
    client, _ = build(
        monkeypatch,
        records={
            "antigravity": recorded("antigravity"),
            "claude-code": recorded("claude-code"),
        },
    )
    body = get(client).json()
    assert [item["adapter"] for item in body["records"]] == ["claude-code", "antigravity"]
    # Absence from records is the absence of a measurement: no per-adapter
    # NOT_OBSERVED entry, and the target list is still complete.
    assert body["adapters"] == TOOL_NAMES
    with pytest.raises(Exception):
        schemas.ConformanceStatusRecordedResponse.model_validate(
            {**_recorded_payload(), "records": [_item_payload(), _item_payload()]}
        )
    with pytest.raises(Exception):
        schemas.ConformanceStatusRecordedResponse.model_validate(
            {**_recorded_payload(), "records": [{**_item_payload(), "adapter": "not-a-tool"}]}
        )
    with pytest.raises(Exception):
        schemas.ConformanceStatusRecordedResponse.model_validate(
            {**_recorded_payload(), "records": []}
        )


# --------------------------------------------------------------------------
# T6. The single route: unknown is 404, unrecorded is 200
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["nope", "codex", "Codex-CLI", "codex-cli%00", "<script>"])
def test_T6_an_unknown_adapter_is_res_0004_and_the_name_is_not_echoed(monkeypatch, name):
    client, calls = build(monkeypatch, records={"codex-cli": recorded("codex-cli")})
    body = canonical(get(client, name=name), code="RES-0004", status=404)
    assert name not in json.dumps(body)
    assert body["detail"] == conformance_status.UNKNOWN_ADAPTER_DETAIL
    # Not a denial: 404 is not audited (#195 records 401 and 403 only), and the
    # records were never consulted for a name that is not a tool.
    assert calls["denials"] == []
    assert calls["reads"] == []


def test_T6b_a_known_adapter_without_a_record_is_200_not_observed(monkeypatch):
    client, calls = build(monkeypatch, records={"codex-cli": recorded("codex-cli")})
    response = get(client, name="gemini-cli")
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == ADAPTER_NOT_OBSERVED_KEYS
    assert body["status"] == "NOT_OBSERVED"
    assert body["reason"] == conformance_status.ADAPTER_NOT_OBSERVED_REASON
    assert body["adapter"] == "gemini-cli"
    assert body["scope"] == "control-plane-host"
    assert body["contractVersion"] == CONTRACT_VERSION
    assert body["recordedAt"] is None
    assert body["checks"] == [
        {"name": spec.name, "capabilityGated": spec.capability is not None}
        for spec in conformance.CHECKLIST
    ]
    assert calls["reads"] == [{"host_id": HOST, "adapters": ["gemini-cli"]}]


def test_T6c_a_known_adapter_with_a_record_is_its_record(monkeypatch):
    client, _ = build(monkeypatch, records={"codex-cli": recorded("codex-cli")})
    body = get(client, name="codex-cli").json()
    assert set(body) == ADAPTER_RECORDED_KEYS
    assert body["status"] == "RECORDED"
    assert body["adapter"] == "codex-cli"
    assert body["subject"] == "fixture-adapter"
    assert body["provenance"] == "in-server"
    assert body["suiteContractVersion"] == CONTRACT_VERSION
    assert (body["total"], body["passed"], body["failed"], body["skipped"]) == (15, 14, 0, 1)
    assert body["recordedAt"] == "2026-09-28T06:00:00Z"
    # The same fields and values as the list item for the same record.
    item = get(client).json()["records"][0]
    assert {k: v for k, v in body.items() if k in ITEM_KEYS} == item


# --------------------------------------------------------------------------
# T13 (stand-in side) and T15: the two fail-closed refusals
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", [None, "codex-cli"])
def test_T13_a_broken_stored_record_is_sys_0002_and_says_nothing_about_the_row(monkeypatch, name):
    def reader(*, host_id, adapters):
        raise StoredRecordInvalid("check names or order differ from the suite's list")

    client, calls = build(monkeypatch, reader=reader)
    body = canonical(get(client, name=name), code="SYS-0002", status=500, retryable=False)
    assert body["detail"] == conformance_status.RECORD_INVALID_DETAIL
    assert "differ" not in body["detail"]
    for spec in conformance.CHECKLIST:
        assert spec.name not in json.dumps(body)
    assert calls["denials"] == []


@pytest.mark.parametrize("name", [None, "codex-cli"])
def test_T15_no_host_identity_is_sys_0002_not_not_observed(monkeypatch, name):
    client, calls = build(monkeypatch, host_id=None, records={"codex-cli": recorded("codex-cli")})
    body = canonical(get(client, name=name), code="SYS-0002", status=500, retryable=False)
    assert body["detail"] == conformance_status.HOST_UNCONFIGURED_DETAIL
    assert "NOT_OBSERVED" not in json.dumps(body)
    assert "INV_CONTROL_PLANE_HOST_ID" not in body["detail"]
    # The records are not consulted at all: with no host there is nothing to
    # bind them to, and another host's rows must not be reported.
    assert calls["reads"] == []
    assert calls["denials"] == []


def test_T15b_membership_is_still_checked_first_without_a_host(monkeypatch):
    client, calls = build(
        monkeypatch, host_id=None, denial=InvError(AUTH_PROJECT_SCOPE, "no", status=403)
    )
    canonical(get(client), code="AUTH-0030", status=403)
    assert len(calls["denials"]) == 1


def test_T15c_the_fixed_details_are_fixed():
    """The two sentences carry no placeholder and are not built at request time."""
    import inspect

    source = inspect.getsource(conformance_status)
    for constant in (
        conformance_status.HOST_UNCONFIGURED_DETAIL,
        conformance_status.RECORD_INVALID_DETAIL,
        conformance_status.UNKNOWN_ADAPTER_DETAIL,
    ):
        assert "{" not in constant and "%" not in constant
    assert "f\"" not in source.split("HOST_UNCONFIGURED_DETAIL =")[1].split("\n\n")[0]


# --------------------------------------------------------------------------
# Two bounded spans (card 103 addendum; Codex card 105 W5)
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", [None, "codex-cli"])
def test_each_read_is_two_bounded_spans_with_the_budget_from_settings(monkeypatch, name):
    client, calls = build(monkeypatch, records={"codex-cli": recorded("codex-cli")}, lock_timeout_ms=250)
    assert get(client, name=name).status_code == 200
    assert calls["spans"] == 2
    locks = [s for s in calls["statements"] if "lock_timeout" in s]
    scopes = [s for s in calls["statements"] if "inv.tenant_id" in s]
    assert locks == ["SET LOCAL lock_timeout = '250ms'"] * 2
    assert len(scopes) == 2 and all(str(TENANT) in s for s in scopes)
    # The bound is set inside each span, after the tenant scope, before any read.
    order = [("lock" if "lock_timeout" in s else "scope") for s in calls["statements"]]
    assert order == ["scope", "lock", "scope", "lock"]


@pytest.mark.parametrize("name", [None, "codex-cli"])
@pytest.mark.parametrize("sqlstate", ["55P03", "40P01"])
def test_a_lock_wait_in_the_membership_span_is_a_retryable_503(monkeypatch, name, sqlstate):
    client, calls = build(monkeypatch, denial=_operational(sqlstate))
    body = canonical(get(client, name=name), code="SYS-0001", status=503, retryable=True)
    assert body["detail"] == LOCK_WAIT_DETAIL
    for forbidden in (sqlstate, "project_members", "SELECT", PROJECT):
        assert forbidden not in body["detail"]
    # The second span never opened, and a 503 is not a denial.
    assert calls["spans"] == 1 and calls["reads"] == [] and calls["denials"] == []


@pytest.mark.parametrize("name", [None, "codex-cli"])
@pytest.mark.parametrize("sqlstate", ["55P03", "40P01"])
def test_a_lock_wait_in_the_record_span_is_a_retryable_503(monkeypatch, name, sqlstate):
    def reader(*, host_id, adapters):
        raise _operational(sqlstate)

    client, calls = build(monkeypatch, reader=reader)
    body = canonical(get(client, name=name), code="SYS-0001", status=503, retryable=True)
    assert body["detail"] == LOCK_WAIT_DETAIL
    assert calls["spans"] == 2 and calls["denials"] == []


@pytest.mark.parametrize("name", [None, "codex-cli"])
@pytest.mark.parametrize("where", ["membership", "records"])
@pytest.mark.parametrize("sqlstate", ["57P01", "08006", "53300"])
def test_any_other_operational_failure_is_not_disguised_as_a_lock_wait(monkeypatch, name, where, sqlstate):
    """An outage or a dropped connection is a defect, not contention: it must
    not come back as ``SYS-0001`` telling the caller to retry."""
    error = _operational(sqlstate)
    if where == "membership":
        client, calls = build(monkeypatch, denial=error)
    else:
        def reader(*, host_id, adapters):
            raise error

        client, calls = build(monkeypatch, reader=reader)
    response = get(client, name=name)
    assert response.status_code == 500, response.text
    assert "SYS-0001" not in response.text
    assert LOCK_WAIT_DETAIL not in response.text
    assert calls["denials"] == []


def test_the_module_has_no_private_copy_of_the_bound():
    import inspect

    source = inspect.getsource(conformance_status)
    assert "SET LOCAL lock_timeout" not in source
    assert "55P03" not in source and "40P01" not in source
    assert source.count("with factory() as session:") == 2
    assert source.count("bounded_lock_wait(") == 2
    # No route-owned session dependency: each read opens its own spans.
    assert "get_session" not in source


# --------------------------------------------------------------------------
# 14-17 / T7. The contract
# --------------------------------------------------------------------------


def test_14_the_empty_response_validates_against_the_stage_one_schema(monkeypatch):
    client, _ = build(monkeypatch)
    body = get(client).json()
    jsonschema.validate(body, schema("conformance-status-response"))
    assert schemas.ConformanceStatusResponse.model_validate(body).model_dump(
        by_alias=True, mode="json"
    ) == body


def test_14b_the_recorded_responses_validate_against_their_schemas(monkeypatch):
    client, _ = build(
        monkeypatch,
        records={"codex-cli": recorded("codex-cli"), "antigravity": recorded("antigravity")},
    )
    body = get(client).json()
    jsonschema.validate(body, schema("conformance-status-recorded-response"))
    assert schemas.ConformanceStatusRecordedResponse.model_validate(body).model_dump(
        by_alias=True, mode="json"
    ) == body
    single = get(client, name="codex-cli").json()
    jsonschema.validate(single, schema("adapter-conformance-recorded-response"))
    assert schemas.AdapterConformanceRecordedResponse.model_validate(single).model_dump(
        by_alias=True, mode="json"
    ) == single
    empty = get(client, name="gemini-cli").json()
    jsonschema.validate(empty, schema("adapter-conformance-not-observed-response"))
    assert schemas.AdapterConformanceNotObservedResponse.model_validate(empty).model_dump(
        by_alias=True, mode="json"
    ) == empty
    # Each branch's schema pins its own status, so the union is decidable.
    assert schema("conformance-status-recorded-response")["properties"]["status"]["const"] == "RECORDED"
    assert schema("adapter-conformance-not-observed-response")["properties"]["status"]["const"] == "NOT_OBSERVED"
    assert schema("adapter-conformance-recorded-response")["properties"]["status"]["const"] == "RECORDED"
    assert set(schema("conformance-status-recorded-response")["required"]) == RECORDED_KEYS
    assert set(schema("adapter-conformance-not-observed-response")["required"]) == ADAPTER_NOT_OBSERVED_KEYS
    assert set(schema("adapter-conformance-recorded-response")["required"]) == ADAPTER_RECORDED_KEYS


def test_15_the_translation_table_covers_what_the_call_can_raise():
    from saintvision.services import projects as project_service

    raised = _raised_codes(project_service, project_service.require_project_access)
    assert raised, "the access check raises nothing this test could find"
    assert raised <= set(conformance_status.TRANSLATION), raised


def test_15b_a_code_the_table_does_not_list_becomes_sys_0002(monkeypatch):
    client, _ = build(monkeypatch, denial=InvError("SEC-0001", "internal detail", status=500))
    body = canonical(get(client), code="SYS-0002", status=500)
    assert "internal detail" not in body["detail"]


# T7. The exported set is fixed: four contract files, none orphaned.
def test_16_T7_the_exported_conformance_contracts_are_exactly_four():
    from tools.export_schemas import exported, render

    collected = exported()
    expected = {
        "conformance-status-response": schemas.ConformanceStatusResponse,
        "conformance-status-recorded-response": schemas.ConformanceStatusRecordedResponse,
        "adapter-conformance-not-observed-response": schemas.AdapterConformanceNotObservedResponse,
        "adapter-conformance-recorded-response": schemas.AdapterConformanceRecordedResponse,
    }
    assert {name: model for name, model in collected.items() if "conformance" in name} == expected
    # The nested classes are inlined, not exported; the union aliases are not
    # Strict subclasses and are not collected (design §4-2).
    for nested in (
        schemas.ConformanceCheckDescriptor,
        schemas.ConformanceCheckOutcome,
        schemas.ConformanceRecordItem,
    ):
        assert nested not in set(collected.values())
    # Every file on disk that names conformance is one of the four, and each
    # matches its model: the orphan the gate cannot see is caught here.
    on_disk = {p.name[: -len(".schema.json")] for p in CONTRACTS.glob("*conformance*.schema.json")}
    assert on_disk == set(expected)
    for name, model in expected.items():
        assert (CONTRACTS / f"{name}.schema.json").read_text("utf-8") == render(model)


def test_17_both_routes_are_registered_on_the_projects_router_once():
    from saintvision.api.v1 import projects

    for route_path, response_model, name in (
        (conformance_status.CONFORMANCE_PATH, schemas.ConformanceStatusUnion, "read_conformance_status"),
        (
            conformance_status.ADAPTER_CONFORMANCE_PATH,
            schemas.AdapterConformanceUnion,
            "read_adapter_conformance",
        ),
    ):
        matches = [
            route
            for route in projects.router.routes
            if getattr(route, "path", None) == f"/v1{route_path}"
        ]
        assert len(matches) == 1, route_path
        assert matches[0].methods == {"GET"}
        assert matches[0].response_model is response_model
        assert matches[0].name == name


def test_17b_the_kernel_dispatch_sends_both_paths_to_the_business_app():
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
        assert client.get(adapter_path("codex-cli")).json() == {"servedBy": "business"}


# --------------------------------------------------------------------------
# The body boundary on both reads
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", [None, "codex-cli"])
def test_a_body_on_this_get_is_refused(monkeypatch, name):
    client, _ = build(monkeypatch)
    canonical(get(client, data=b"{}", name=name), code="VAL-0003", status=422)


@pytest.mark.parametrize("name", [None, "codex-cli"])
def test_an_oversized_body_is_refused_before_it_is_buffered(monkeypatch, name):
    client, _ = build(monkeypatch)
    canonical(
        get(client, data=b"x" * (MAX_REQUEST_BYTES + 1), name=name), code="VAL-0003", status=413
    )


def test_membership_is_checked_before_the_body_is_read(monkeypatch):
    client, calls = build(
        monkeypatch, denial=InvError(AUTH_PROJECT_SCOPE, "no membership", status=403)
    )
    canonical(
        get(client, data=b"x" * (MAX_REQUEST_BYTES + 100)), code="AUTH-0030", status=403
    )
    assert len(calls["access"]) == 1
    assert len(calls["denials"]) == 1


def test_the_unknown_adapter_answer_comes_after_membership_and_body(monkeypatch):
    """A non-member cannot probe the tool list, and a body is refused before
    the name is judged: 403, then 422, then 404."""
    client, _ = build(monkeypatch, denial=InvError(AUTH_PROJECT_SCOPE, "no", status=403))
    canonical(get(client, name="nope"), code="AUTH-0030", status=403)
    client, _ = build(monkeypatch)
    canonical(get(client, name="nope", data=b"{}"), code="VAL-0003", status=422)
    canonical(get(client, name="nope"), code="RES-0004", status=404)


@pytest.mark.parametrize("name", [None, "codex-cli"])
def test_no_credential_never_reaches_the_access_check(monkeypatch, name):
    client, calls = build(monkeypatch)
    target = path() if name is None else adapter_path(name)
    response = client.get(target)
    assert response.status_code != 200
    assert calls["access"] == []
    assert calls["reads"] == []


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


def _item_payload(adapter="codex-cli"):
    outs = outcomes()
    return {
        "adapter": adapter,
        "subject": "fixture-adapter",
        "provenance": "in-server",
        "contractVersion": CONTRACT_VERSION,
        "suiteContractVersion": CONTRACT_VERSION,
        "total": len(outs),
        "passed": sum(1 for o in outs if o.passed and not o.skipped),
        "failed": sum(1 for o in outs if not o.passed and not o.skipped),
        "skipped": sum(1 for o in outs if o.skipped),
        "outcomes": [{"name": o.name, "passed": o.passed, "skipped": o.skipped} for o in outs],
        "recordedAt": NOW.isoformat(),
    }


def _recorded_payload():
    return {
        "status": "RECORDED",
        "scope": "control-plane-host",
        "contractVersion": CONTRACT_VERSION,
        "adapters": TOOL_NAMES,
        "checks": [
            {"name": spec.name, "capabilityGated": spec.capability is not None}
            for spec in conformance.CHECKLIST
        ],
        "records": [_item_payload()],
        "latestRecordedAt": NOW.isoformat(),
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
# The real-PostgreSQL fixtures, exercised without PostgreSQL
# --------------------------------------------------------------------------


def _load(relative):
    import importlib.util

    target = pathlib.Path(__file__).resolve().parents[1] / relative
    spec = importlib.util.spec_from_file_location(target.stem, target)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Recorder:
    def __init__(self):
        self.statements: list[str] = []

    def execute(self, statement, params=None):
        self.statements.append(str(statement))
        return None


def _tables_written(recorder):
    return [
        statement.split("INSERT INTO ", 1)[1].split(" ", 1)[0]
        for statement in recorder.statements
    ]


def test_the_stage_one_real_pg_fixture_builds_its_rows_without_a_database():
    module = _load("integration/test_conformance_status_real_pg.py")
    recorder = _Recorder()
    seeded = module._seed(recorder, tenant_id=TENANT, now=NOW, label="fixture-guard")
    assert set(seeded) == {"user_id", "project_id"}
    assert _tables_written(recorder) == ["users", "projects", "project_members"]

    from saintvision.ids import is_id

    assert is_id(seeded["user_id"], "user")
    assert is_id(seeded["project_id"], "project")
    import inspect

    assert 'role="requester"' in inspect.getsource(module._seed)
    # Stage two: the stage-one client now needs the host identity to read at all.
    assert "control_plane_host_id" in inspect.getsource(module._client)


def test_the_records_real_pg_fixture_builds_its_rows_without_a_database():
    """A wrong column or id kind in the record seed should fail here, not in
    hosted CI an hour later (#167)."""
    module = _load("integration/test_conformance_records_real_pg.py")
    recorder = _Recorder()
    record_id = module._store(
        recorder, adapter="codex-cli", host_id=HOST, recorded_at=NOW
    )
    assert _tables_written(recorder) == ["adapter_conformance_records"]

    from saintvision.ids import is_id

    assert is_id(record_id, "conformance_record")
    # Every tampering the real-PG T13 stores passes the database's own CHECKs
    # (so only the reader can catch it) -- length equals total, counts add up.
    for label, tamper in module.TAMPERINGS.items():
        values = module._well_formed(adapter="codex-cli", host_id=HOST, recorded_at=NOW)
        values.update(tamper(values))
        assert len(values["checks"]) == values["total"], label
        assert values["passed"] + values["failed"] + values["skipped"] == values["total"], label
