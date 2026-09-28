"""G-04 PR 1: ``GET /projects/{p}/runs/{run}/record`` and the rules it carries.

Each test is one reversion the design (G-04·G-05 통합 설계 v1.1 §3, §7) says
must fail: the membership check, the path-to-row binding through the workload,
the canonical error body, the strict response, and the translation table. The
session here answers exactly the calls the route makes; the PostgreSQL facts
(RLS, real grants) are in ``tests/integration/test_run_record_real_pg.py``.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import uuid

import pytest
from fastapi.testclient import TestClient

from inv.contracts import validate_contract
from saintvision.api import schemas
from saintvision.api.app import create_app
from saintvision.api.problem import CANONICAL_KEYS
from saintvision.api.v1 import lineage_query, project_scope, run_records
from saintvision.config import Settings
from saintvision.errors import AUTH_PROJECT_SCOPE, RES_RUN_NOT_FOUND, InvError
from saintvision.identity.principal import Principal, StaticPrincipalVerifier

TENANT = uuid.UUID("11111111-1111-1111-1111-111111111111")
OTHER_TENANT = uuid.UUID("22222222-2222-2222-2222-222222222222")
PROJECT = "prj_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
OTHER_PROJECT = "prj_01J8Z3XQ2K9WMV5T7N4B6C8D0F"
RUN = "run_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
WORKLOAD = "wkl_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
RECORD = "rec_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
SHA = "c" * 64
PATH = f"/v1/projects/{PROJECT}/runs/{RUN}/record"
AUTH = {"Authorization": "Bearer record-token"}
NOW = dt.datetime(2026, 9, 28, 5, 0, tzinfo=dt.timezone.utc)


class RunRow:
    def __init__(self, *, tenant_id=TENANT, workload_id=WORKLOAD):
        self.run_id = RUN
        self.tenant_id = tenant_id
        self.workload_id = workload_id


class WorkloadRow:
    def __init__(self, *, tenant_id=TENANT, project_id=PROJECT):
        self.workload_id = WORKLOAD
        self.tenant_id = tenant_id
        self.project_id = project_id


class RecordRow:
    def __init__(self, **overrides):
        self.record_id = RECORD
        self.run_id = RUN
        self.final_state = "succeeded"
        self.termination_reason = "completed"
        self.evidence_id = "evd_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
        self.bundle_id = None
        self.bundle_hash = None
        self.workload_spec_sha256 = SHA
        self.component_versions = {"adapter": "reference"}
        self.attempt_count = 1
        self.sealed_at = NOW
        self.__dict__.update(overrides)


class Session:
    """Answers ``session.get`` for Run and Workload by class name; nothing else."""

    def __init__(self, world):
        self.world = world
        self.gets: list[tuple[str, str]] = []

    def get(self, model, key, **_kwargs):
        self.gets.append((model.__name__, key))
        return self.world.get(model.__name__.lower())


def build(monkeypatch, world):
    world.setdefault("run", RunRow())
    world.setdefault("workload", WorkloadRow())
    world.setdefault("record", RecordRow())
    session = Session(world)
    world["session"] = session

    principal = Principal(
        user_id="usr_01J8Z3XQ2K9WMV5T7N4B6C8D0E",
        tenant_id=TENANT,
        external_subject="oidc:record",
        project_ids=frozenset({PROJECT}),
    )
    app = create_app(
        engine=object(),
        settings=Settings(database_url="postgresql://unused"),
        verifier=StaticPrincipalVerifier({"record-token": principal}, allow_outside_dev=True),
        check_partitions_on_startup=False,
    )
    from saintvision.api.deps import get_session

    app.dependency_overrides[get_session] = lambda: session

    calls = world.setdefault("access_calls", [])

    def require_project_access(_session, *, tenant_id, project_id, user_id):
        calls.append((tenant_id, project_id, user_id))
        denial = world.get("denial")
        if denial is not None:
            raise denial
        return {"canRequest": False, "canApprove": False}

    monkeypatch.setattr(lineage_query.project_service, "require_project_access", require_project_access)

    def get_record(_session, *, tenant_id, run_id):
        world.setdefault("record_calls", []).append((tenant_id, run_id))
        if world.get("record") is None:
            raise InvError(RES_RUN_NOT_FOUND, "no sealed record for this run")
        return world["record"]

    monkeypatch.setattr(run_records.record_service, "get_record", get_record)
    return TestClient(app, raise_server_exceptions=False)


def canonical(response, *, code, status, retryable=False):
    assert response.status_code == status, response.text
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert set(body) == set(CANONICAL_KEYS), body
    assert body["type"] == "about:blank"
    assert (body["code"], body["status"], body["retryable"]) == (code, status, retryable)
    validate_contract("ProblemDetails", body)
    return body


# ---------------------------------------------------------------- the happy path and its shape


def test_a_member_reads_the_sealed_record_as_the_strict_contract(monkeypatch):
    world: dict = {}
    client = build(monkeypatch, world)
    response = client.get(PATH, headers=AUTH)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body == {
        "recordId": RECORD,
        "runId": RUN,
        "finalState": "succeeded",
        "terminationReason": "completed",
        "evidenceId": "evd_01J8Z3XQ2K9WMV5T7N4B6C8D0E",
        "bundleId": None,
        "bundleHash": None,
        "workloadSpecSha256": SHA,
        "componentVersions": {"adapter": "reference"},
        "attemptCount": 1,
        "sealedAt": "2026-09-28T05:00:00Z",
    }
    schemas.RunRecordResponse.model_validate(body)
    # Order of checks: membership first, then the path binding, then the service.
    assert world["access_calls"] == [(TENANT, PROJECT, "usr_01J8Z3XQ2K9WMV5T7N4B6C8D0E")]
    assert world["session"].gets == [("Run", RUN), ("Workload", WORKLOAD)]
    assert world["record_calls"] == [(TENANT, RUN)]


def test_the_response_model_is_strict_and_never_carries_extras():
    with pytest.raises(Exception):
        schemas.RunRecordResponse.model_validate({**_valid_body(), "requestedBy": "someone"})
    with pytest.raises(Exception):
        schemas.RunRecordResponse.model_validate({**_valid_body(), "bundleHash": "X" * 64})


def _valid_body():
    return {
        "recordId": RECORD, "runId": RUN, "finalState": "succeeded", "terminationReason": "completed",
        "evidenceId": None, "bundleId": None, "bundleHash": None, "workloadSpecSha256": SHA,
        "componentVersions": {}, "attemptCount": 0, "sealedAt": "2026-09-28T05:00:00Z",
    }


# ---------------------------------------------------------------- membership (revert: drop the check)


def test_a_non_member_is_403_and_nothing_else_is_touched(monkeypatch):
    world = {"denial": InvError(AUTH_PROJECT_SCOPE, "project is not accessible to this principal")}
    client = build(monkeypatch, world)
    canonical(client.get(PATH, headers=AUTH), code="AUTH-0030", status=403)
    assert world["session"].gets == []                 # denied before any row is read
    assert "record_calls" not in world


def test_without_a_credential_the_route_is_401_and_the_denial_is_audited_before_any_row(monkeypatch):
    """The app records every AUTH denial out of band; that writer touches the
    engine, which this harness cannot provide, so it is captured here. What the
    route contributes is only that nothing of its own runs before the denial."""
    from saintvision.api import app as app_module

    denials = []
    monkeypatch.setattr(app_module, "record_denial_out_of_band", lambda engine, **fields: denials.append(fields))
    world: dict = {}
    client = build(monkeypatch, world)
    response = client.get(PATH)
    assert response.status_code == 401, response.text
    body = response.json()                      # legacy InvError shape on the auth boundary, not CanonicalProblem
    assert response.headers["www-authenticate"] == "Bearer"
    assert body["code"] == "AUTH-MISSING-CREDENTIAL" and body["status"] == 401
    # The legacy problem body echoes the request path as ``instance``; what must not
    # appear is anything read from the record.
    assert "recordId" not in response.text and RECORD not in response.text
    assert [d["reason_code"] for d in denials] == ["AUTH-MISSING-CREDENTIAL"]
    assert denials[0]["actor_type"] == "anonymous" and denials[0]["outcome"] == "deny"
    assert world["access_calls"] == [] and world["session"].gets == [] and "record_calls" not in world


# ---------------------------------------------------------------- path -> row binding (revert: drop the helper)


@pytest.mark.parametrize(
    "world,label",
    [
        ({"run": None}, "missing run"),
        ({"run": RunRow(tenant_id=OTHER_TENANT)}, "another tenant's run"),
        ({"workload": WorkloadRow(project_id=OTHER_PROJECT)}, "another project's run"),
        ({"workload": None}, "run whose workload is gone"),
        ({"workload": WorkloadRow(tenant_id=OTHER_TENANT)}, "workload of another tenant"),
    ],
)
def test_every_binding_failure_is_the_same_404_before_the_service_is_called(monkeypatch, world, label):
    client = build(monkeypatch, world)
    body = canonical(client.get(PATH, headers=AUTH), code="RES-0004", status=404)
    assert body["detail"] == project_scope.NO_SUCH_RUN, label
    assert "record_calls" not in world, label            # the service never saw the run id


def test_the_helper_is_the_only_place_that_binds_and_it_reads_run_then_workload(monkeypatch):
    world = {"workload": WorkloadRow(project_id=OTHER_PROJECT)}
    client = build(monkeypatch, world)
    canonical(client.get(PATH, headers=AUTH), code="RES-0004", status=404)
    assert world["session"].gets == [("Run", RUN), ("Workload", WORKLOAD)]
    # Reverting to a route that skips the helper would let this request through:
    monkeypatch.setattr(run_records, "run_in_project", lambda _s, **k: RunRow())
    assert client.get(PATH, headers=AUTH).status_code == 200


# ---------------------------------------------------------------- the service's own refusal


def test_an_unsealed_run_is_404_with_the_canonical_body(monkeypatch):
    world = {"record": None}
    client = build(monkeypatch, world)
    body = canonical(client.get(PATH, headers=AUTH), code="RES-0004", status=404)
    assert body["detail"] == "No sealed record for this run."
    assert world["record_calls"] == [(TENANT, RUN)]


def test_a_body_on_this_get_is_refused(monkeypatch):
    client = build(monkeypatch, {})
    canonical(client.request("GET", PATH, headers=AUTH, content=b"{}"), code="VAL-0003", status=422)


# ---------------------------------------------------------------- the translation table is complete


def test_every_reachable_business_code_is_in_the_translation_table():
    reachable = {AUTH_PROJECT_SCOPE, RES_RUN_NOT_FOUND}
    assert reachable <= set(run_records.TRANSLATION)
    for code, status, retryable in run_records.TRANSLATION.values():
        # R2 adds the service's role refusal (VAL-0003, 422); nothing is retryable.
        assert status in (403, 404, 422) and retryable is False and code in ("AUTH-0030", "RES-0004", "VAL-0003")


def test_the_route_is_registered_once_on_the_projects_router():
    from saintvision.api.v1 import projects

    paths = [route.path for route in projects.router.routes]
    assert paths.count("/v1" + run_records.RECORD_PATH) + paths.count(run_records.RECORD_PATH) == 1
