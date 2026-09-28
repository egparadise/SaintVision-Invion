"""W1: the seal route, over real HTTP, without a database.

Each test is a reversion of ``api/v1/run_seal.py``. The session is a stand-in
that records what the route asks of it, in order, so these prove the §5-2
*order*, the server derivation of the sealed set and the wire contract. Lost
updates are not claimed here -- a mock session cannot lose one -- they are
``tests/integration/test_run_seal_real_pg.py`` on hosted CI.

Kept real: ``deps.serialise_idempotent_write`` (the lock key and its position
are the IDEM-6 contract).
"""

from __future__ import annotations

import contextlib
import datetime as dt
import json
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError, OperationalError

from saintvision.api import schemas
from saintvision.api.app import create_app
from saintvision.api.problem import CANONICAL_KEYS, MAX_REQUEST_BYTES
from saintvision.api.v1 import run_seal
from saintvision.config import Settings
from saintvision.errors import (
    AUTH_PROJECT_SCOPE,
    GRAPH_IDEMPOTENCY_CONFLICT,
    RES_RUN_NOT_FOUND,
    VAL_SCHEMA,
    InvError,
)
from saintvision.identity.principal import Principal, StaticPrincipalVerifier

TENANT = uuid.UUID("11111111-1111-1111-1111-111111111111")
OTHER_TENANT = uuid.UUID("22222222-2222-2222-2222-222222222222")
PROJECT = "prj_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
OTHER_PROJECT = "prj_01J8Z3XQ2K9WMV5T7N4B6C8D0F"
RUN = "run_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
WORKLOAD = "wkl_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
EVIDENCE = "evd_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
BUNDLE = "bdl_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
RECORD = "rec_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
ART_A = "art_01J8Z3XQ2K9WMV5T7N4B6C8D0A"
ART_B = "art_01J8Z3XQ2K9WMV5T7N4B6C8D0B"
ART_STAGING = "art_01J8Z3XQ2K9WMV5T7N4B6C8D0C"
ART_FOREIGN = "art_01J8Z3XQ2K9WMV5T7N4B6C8D0Z"
USER = "usr_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
SHA_A, SHA_B, BUNDLE_SHA, SPEC_SHA = "a" * 64, "b" * 64, "c" * 64, "d" * 64
NOW = dt.datetime(2026, 9, 28, 6, 0, tzinfo=dt.timezone.utc)
PATH = f"/v1/projects/{PROJECT}/runs/{RUN}/record"
KEY = "seal-0001"
AUTH = {"Authorization": "Bearer seal-token", "Idempotency-Key": KEY}


class RunRow:
    def __init__(self, *, tenant_id=TENANT, state="succeeded", termination_reason="completed", evidence_id=EVIDENCE):
        self.run_id = RUN
        self.tenant_id = tenant_id
        self.workload_id = WORKLOAD
        self.state = state
        self.termination_reason = termination_reason
        self.evidence_id = evidence_id
        self.attempt_count = 1


class WorkloadRow:
    def __init__(self, *, tenant_id=TENANT, project_id=PROJECT):
        self.workload_id = WORKLOAD
        self.tenant_id = tenant_id
        self.project_id = project_id
        self.spec_sha256 = SPEC_SHA


class BundleRow:
    def __init__(self, versions=None):
        self.bundle_id = BUNDLE
        self.tenant_id = TENANT
        self.run_id = RUN
        self.bundle_hash = BUNDLE_SHA
        self.component_versions = versions if versions is not None else {"retriever": "explicit-1"}


class EvidenceRow:
    def __init__(self, versions=None):
        self.component_versions = versions if versions is not None else {"adapter": "reference", "retriever": "evidence-wins"}


class ArtifactRow:
    def __init__(self, artifact_id, *, status="active", checksum=SHA_A, run_id=RUN):
        self.artifact_id = artifact_id
        self.tenant_id = TENANT
        self.run_id = run_id
        self.status = status
        self.checksum_sha256 = checksum
        self.object_version = "v1"
        self.byte_size = 12


class RecordRow:
    def __init__(self, *, bundle_id=BUNDLE, bundle_hash=BUNDLE_SHA, versions=None):
        self.record_id = RECORD
        self.run_id = RUN
        self.final_state = "succeeded"
        self.termination_reason = "completed"
        self.evidence_id = EVIDENCE
        self.bundle_id = bundle_id
        self.bundle_hash = bundle_hash
        self.workload_spec_sha256 = SPEC_SHA
        self.component_versions = versions if versions is not None else {"adapter": "reference", "retriever": "evidence-wins"}
        self.attempt_count = 1
        self.sealed_at = NOW


class PinRow:
    def __init__(self, artifact_id, role, checksum):
        self.artifact_id = artifact_id
        self.role = role
        self.checksum_sha256 = checksum


class _Scalars:
    def __init__(self, rows):
        self._rows = rows

    def one_or_none(self):
        return self._rows[0] if self._rows else None

    def first(self):
        return self._rows[0] if self._rows else None

    def all(self):
        return list(self._rows)


def _entity(statement):
    return statement.column_descriptions[0]["entity"].__name__


class Session:
    def __init__(self, world):
        self.world = world
        self.log = world["log"]

    def execute(self, statement, params=None):
        sql = str(statement)
        if "lock_timeout" in sql:
            # Card 84: recorded apart from the order log; both spans set it.
            self.world.setdefault("lock_timeouts", []).append(sql)
        elif "pg_advisory_xact_lock" in sql:
            self.log.append("advisory-lock")
            if self.world.get("advance_on_lock") is not None:
                self.world["clock"] = self.world["advance_on_lock"]
        return None

    def get(self, model, key, **kwargs):
        self.log.append(f"get:{model.__name__}")
        if model.__name__ == "Workload":
            return self.world["workload"]
        return None

    def scalars(self, statement):
        name = _entity(statement)
        self.log.append(f"select:{name}")
        self.world["statements"].append((name, statement))
        error = self.world.get("lock_errors", {}).get(name)
        if error is not None:
            raise error
        if name == "Run":
            row = self.world["run"]
            return _Scalars([row] if row is not None else [])
        if name == "ContextBundle":
            b = self.world["bundle"]
            return _Scalars([b] if b is not None else [])
        if name == "EvidenceEnvelope":
            e = self.world["evidence"]
            return _Scalars([e] if e is not None else [])
        if name == "Artifact":
            return _Scalars(sorted(self.world["artifacts"], key=lambda a: a.artifact_id))
        if name == "RunRecordArtifact":
            return _Scalars(self.world["stored_pins"])
        raise AssertionError(f"unexpected select of {name}")


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
    world.setdefault("log", [])
    world.setdefault("statements", [])
    world.setdefault("run", RunRow())
    world.setdefault("workload", WorkloadRow())
    world.setdefault("bundle", BundleRow())
    world.setdefault("evidence", EvidenceRow())
    world.setdefault("artifacts", [
        ArtifactRow(ART_B, checksum=SHA_B), ArtifactRow(ART_A), ArtifactRow(ART_STAGING, status="staging", checksum=None),
    ])
    world.setdefault("existing", None)
    world.setdefault("stored_pins", [])
    world.setdefault("permissions", [{"canRequest": True, "canApprove": True}])
    world.setdefault("denials", [])
    world.setdefault("replay", None)
    world.setdefault("replay_error", None)
    world.setdefault("seal_error", None)
    world.setdefault("stored", [])
    world.setdefault("audits", [])
    world.setdefault("sealed", [])
    world.setdefault("ledger_reads", [])
    world.setdefault("depth", 0)
    world.setdefault("spans", 0)
    world.setdefault("body_depth", [])
    world.setdefault("clock", NOW)
    world.setdefault("clock_reads", [])

    monkeypatch.setattr(run_seal, "make_session_factory", lambda _engine: Factory(world))
    monkeypatch.setattr(run_seal, "tenant_scope", lambda _s, _t: contextlib.nullcontext())
    from saintvision.api import app as app_module

    monkeypatch.setattr(
        app_module, "record_denial_out_of_band",
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

    monkeypatch.setattr(run_seal.project_service, "require_project_access", require_project_access)
    original_read = run_seal.read_bounded_body

    async def read_bounded_body(request, **kwargs):
        world["body_depth"].append(world["depth"])
        world["log"].append("body-read")
        if world.get("advance_on_body") is not None:
            world["clock"] = world["advance_on_body"]
        return await original_read(request, **kwargs)

    monkeypatch.setattr(run_seal, "read_bounded_body", read_bounded_body)

    def replay_or_reserve(_session, **kwargs):
        world["log"].append("ledger-read")
        world["ledger_reads"].append(kwargs)
        if world["replay_error"] is not None:
            raise world["replay_error"]
        return world["replay"]

    monkeypatch.setattr(run_seal, "replay_or_reserve", replay_or_reserve)

    def store_idempotent_response(_session, **kwargs):
        world["log"].append("ledger-write")
        world["stored"].append(kwargs)

    monkeypatch.setattr(run_seal, "store_idempotent_response", store_idempotent_response)

    def get_record(_session, *, tenant_id, run_id):
        world["log"].append("record-lookup")
        if world["existing"] is None:
            raise InvError(RES_RUN_NOT_FOUND, "no sealed record for this run")
        return world["existing"]

    def seal(_session, **kwargs):
        world["log"].append("service")
        world["sealed"].append(kwargs)
        if world["seal_error"] is not None:
            raise world["seal_error"]
        return RecordRow(versions=kwargs["component_versions"])

    monkeypatch.setattr(run_seal.record_service, "get_record", get_record)
    monkeypatch.setattr(run_seal.record_service, "seal_run_record", seal)
    monkeypatch.setattr(
        run_seal, "record_event",
        lambda _session, **kwargs: world["log"].append("audit") or world["audits"].append(kwargs),
    )

    def clock():
        world["clock_reads"].append(len(world["log"]))
        return world["clock"]

    principal = Principal(user_id=USER, tenant_id=TENANT, external_subject="oidc:seal", project_ids=frozenset({PROJECT}))
    app = create_app(
        engine=object(),
        settings=Settings(database_url="postgresql://unused", idempotency_ttl_seconds=600, business_lock_timeout_ms=lock_timeout_ms),
        verifier=StaticPrincipalVerifier({"seal-token": principal}, allow_outside_dev=True),
        clock=clock,
        check_partitions_on_startup=False,
    )
    return TestClient(app, raise_server_exceptions=False)


def post(client, body=None, *, headers=None, content=None):
    sent = {**AUTH, "Content-Type": "application/json", **(headers or {})}
    if content is None:
        content = json.dumps({} if body is None else body).encode("utf-8")
    return client.post(PATH, content=content, headers=sent)


def canonical(response, *, code, status, retryable=False):
    assert response.status_code == status, response.text
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert set(body) == set(CANONICAL_KEYS), body
    assert (body["code"], body["status"], body["retryable"]) == (code, status, retryable)
    return body


FULL_ORDER = [
    "permission", "body-read",
    "advisory-lock", "permission", "ledger-read",
    "select:Run", "get:Workload", "permission",
    "get:Workload", "select:ContextBundle", "select:EvidenceEnvelope", "select:Artifact",
    "record-lookup", "service", "audit", "ledger-write",
]


# ---------------------------------------------------------------- the §5-2 order and the server derivation


def test_a_seal_follows_the_contract_order_and_derives_everything_from_the_locked_rows(monkeypatch):
    world: dict = {}
    client = build(monkeypatch, world)
    response = post(client, {"roles": {ART_A: "diff"}})
    assert response.status_code == 200, response.text
    body = response.json()
    schemas.RunRecordResponse.model_validate(body)
    assert body["recordId"] == RECORD and body["runId"] == RUN
    assert world["log"] == FULL_ORDER
    assert world["spans"] == 2 and world["body_depth"] == [0]
    (sealed,) = world["sealed"]
    # the sealed set is the server's: both active+checksummed artifacts, ordered, staging excluded
    assert [(p.artifact_id, p.role) for p in sealed["artifacts"]] == [(ART_A, "diff"), (ART_B, "other")]
    assert sealed["bundle_id"] == BUNDLE
    # evidence versions first, bundle keys only where evidence has none
    assert sealed["component_versions"] == {"adapter": "reference", "retriever": "evidence-wins"}
    assert sealed["now"] == NOW
    assert world["stored"][0]["response_status"] == 200 and world["stored"][0]["response_body"] == body
    assert world["stored"][0]["payload"] == {"runId": RUN, "request": {"roles": {ART_A: "diff"}}}
    # both spans -- the permission preflight and the write -- are bounded (card 84 F1)
    assert world["lock_timeouts"] == ["SET LOCAL lock_timeout = '5000ms'"] * 2
    assert world["audits"][0]["action"] == "run_record.seal" and world["audits"][0]["detail"]["created"] is True
    assert world["audits"][0]["detail"]["artifactCount"] == 2


def test_the_run_and_the_artifacts_are_locked_for_update_with_populate_existing_in_artifact_id_order(monkeypatch):
    world: dict = {}
    client = build(monkeypatch, world)
    assert post(client).status_code == 200
    by_name = {name: statement for name, statement in world["statements"]}
    for name in ("Run", "Artifact"):
        compiled = str(by_name[name].compile(compile_kwargs={"literal_binds": True})).upper()
        assert "FOR UPDATE" in compiled, name
        assert by_name[name].get_execution_options().get("populate_existing") is True, name
    assert "ORDER BY ARTIFACTS.ARTIFACT_ID" in str(by_name["Artifact"].compile(compile_kwargs={"literal_binds": True})).upper()
    log = world["log"]
    assert log.index("select:Run") < log.index("select:Artifact")
    assert log.index("advisory-lock") < log.index("ledger-read") < log.index("select:Run")


def test_the_request_cannot_add_an_artifact_to_the_sealed_set(monkeypatch):
    world: dict = {}
    client = build(monkeypatch, world)
    body = canonical(post(client, {"roles": {ART_FOREIGN: "diff"}}), code="GRAPH-0002", status=409)
    assert "sealable set" in body["detail"]
    assert "service" not in world["log"] and world["stored"] == []


def test_a_staging_artifact_cannot_be_named_even_by_role(monkeypatch):
    world: dict = {}
    client = build(monkeypatch, world)
    canonical(post(client, {"roles": {ART_STAGING: "log"}}), code="GRAPH-0002", status=409)
    assert "service" not in world["log"]


def test_an_unmapped_artifact_is_sealed_as_other_never_left_out(monkeypatch):
    world: dict = {}
    client = build(monkeypatch, world)
    assert post(client).status_code == 200
    assert [(p.artifact_id, p.role) for p in world["sealed"][0]["artifacts"]] == [(ART_A, "other"), (ART_B, "other")]


def test_without_evidence_the_bundles_versions_are_used_and_without_a_bundle_none(monkeypatch):
    world = {"evidence": None}
    client = build(monkeypatch, world)
    assert post(client).status_code == 200
    assert world["sealed"][0]["component_versions"] == {"retriever": "explicit-1"}
    world2 = {"evidence": None, "bundle": None}
    client2 = build(monkeypatch, world2)
    assert post(client2).status_code == 200
    assert world2["sealed"][0]["component_versions"] == {} and world2["sealed"][0]["bundle_id"] is None


# ---------------------------------------------------------------- an existing record (step 6)


def test_an_identical_existing_record_is_the_natural_idempotent_success_without_the_service(monkeypatch):
    world = {"existing": RecordRow(), "stored_pins": [PinRow(ART_A, "diff", SHA_A), PinRow(ART_B, "other", SHA_B)]}
    client = build(monkeypatch, world)
    response = post(client, {"roles": {ART_A: "diff"}})
    assert response.status_code == 200, response.text
    assert response.json()["recordId"] == RECORD
    assert "service" not in world["log"] and world["log"][-2:] == ["audit", "ledger-write"]
    assert world["audits"][0]["detail"]["created"] is False


@pytest.mark.parametrize(
    "existing,pins,request_roles",
    [
        (RecordRow(), [PinRow(ART_A, "diff", SHA_A), PinRow(ART_B, "other", SHA_B)], {ART_A: "trace"}),      # role differs
        (RecordRow(), [PinRow(ART_A, "diff", SHA_A)], {ART_A: "diff"}),                                       # a pin is missing
        (RecordRow(), [PinRow(ART_A, "diff", "e" * 64), PinRow(ART_B, "other", SHA_B)], {ART_A: "diff"}),   # digest differs
        (RecordRow(bundle_id=None, bundle_hash=None), [PinRow(ART_A, "diff", SHA_A), PinRow(ART_B, "other", SHA_B)], {ART_A: "diff"}),
        (RecordRow(versions={"adapter": "other"}), [PinRow(ART_A, "diff", SHA_A), PinRow(ART_B, "other", SHA_B)], {ART_A: "diff"}),
    ],
    ids=["role", "missing-pin", "digest", "bundle", "versions"],
)
def test_a_different_existing_record_is_409_and_writes_nothing(monkeypatch, existing, pins, request_roles):
    world = {"existing": existing, "stored_pins": pins}
    client = build(monkeypatch, world)
    body = canonical(post(client, {"roles": request_roles}), code="GRAPH-0002", status=409)
    assert body["detail"] == "This run is already sealed with a different record."
    assert "service" not in world["log"] and world["stored"] == [] and world["audits"] == []


def test_the_unique_constraint_firing_is_a_409_not_a_raw_500(monkeypatch):
    class Orig(Exception):
        pass

    orig = Orig('duplicate key value violates unique constraint "uq_run_records_run_id"')
    world = {"seal_error": IntegrityError("INSERT", {}, orig)}
    client = build(monkeypatch, world)
    body = canonical(post(client), code="GRAPH-0002", status=409)
    assert body["detail"] == "This run is already sealed." and world["stored"] == []


def test_any_other_integrity_error_is_not_disguised(monkeypatch):
    class Orig(Exception):
        pass

    world = {"seal_error": IntegrityError("INSERT", {}, Orig("some other constraint"))}
    client = build(monkeypatch, world)
    assert post(client).status_code == 500 and world["stored"] == []


# ---------------------------------------------------------------- the run's state (step 3)


@pytest.mark.parametrize("run", [RunRow(state="verifying"), RunRow(termination_reason=None)], ids=["not-terminal", "no-reason"])
def test_an_unfinished_run_is_409_before_any_artifact_is_locked(monkeypatch, run):
    world = {"run": run}
    client = build(monkeypatch, world)
    body = canonical(post(client), code="GRAPH-0002", status=409)
    assert body["detail"] == "Only a finished run can be sealed."
    assert "select:Artifact" not in world["log"] and "service" not in world["log"]


@pytest.mark.parametrize(
    "world,label",
    [({"run": None}, "missing"), ({"run": RunRow(tenant_id=OTHER_TENANT)}, "other tenant"),
     ({"workload": WorkloadRow(project_id=OTHER_PROJECT)}, "other project"), ({"workload": None}, "no workload")],
)
def test_every_binding_failure_is_the_same_404(monkeypatch, world, label):
    client = build(monkeypatch, dict(world))
    body = canonical(post(client), code="RES-0004", status=404)
    assert body["detail"] == "No such run."


# ---------------------------------------------------------------- permission, key, body


def test_a_member_without_the_approval_grade_is_403_before_the_body(monkeypatch):
    world = {"permissions": [{"canApprove": False}]}
    client = build(monkeypatch, world)
    canonical(post(client, content=b"{" + b"x" * 20000), code="AUTH-0030", status=403)
    assert world["log"] == ["permission"] and len(world["denials_recorded"]) == 1
    assert world["lock_timeouts"] == ["SET LOCAL lock_timeout = '5000ms'"]        # the preflight span is bounded too


def test_a_revocation_between_the_spans_locks_no_row(monkeypatch):
    world = {"permissions": [{"canApprove": True}, {"canApprove": False}]}
    client = build(monkeypatch, world)
    canonical(post(client), code="AUTH-0030", status=403)
    assert "select:Run" not in world["log"] and world["stored"] == []


def test_a_revocation_during_the_lock_wait_is_403_after_the_run_is_locked_and_writes_nothing(monkeypatch):
    world = {"permissions": [{"canApprove": True}, {"canApprove": True}, {"canApprove": False}]}
    client = build(monkeypatch, world)
    canonical(post(client), code="AUTH-0030", status=403)
    log = world["log"]
    assert log.count("permission") == 3 and log.index("select:Run") < len(log) - 1
    assert "select:Artifact" not in log and "service" not in log and world["stored"] == []
    assert len(world["denials_recorded"]) == 1


def test_a_missing_idempotency_key_is_422_before_the_body(monkeypatch):
    world: dict = {}
    client = build(monkeypatch, world)
    headers = {"Authorization": AUTH["Authorization"], "Content-Type": "application/json"}
    canonical(client.post(PATH, content=b"{}", headers=headers), code="VAL-0003", status=422)
    assert world["log"] == ["permission"]


@pytest.mark.parametrize(
    "body",
    [
        {"roles": {ART_A: "screenshot"}},           # unknown role
        {"roles": {"not-an-artifact": "diff"}},     # not an artifact id
        {"roles": ["diff"]},
        {"componentVersions": {"adapter": "x"}},    # the caller may not name integrity values
        {"bundleId": BUNDLE},
        {"artifacts": [{"artifactId": ART_A, "role": "diff"}]},
        [],
    ],
)
def test_a_body_that_is_not_the_strict_request_is_422_and_locks_nothing(monkeypatch, body):
    world: dict = {}
    client = build(monkeypatch, world)
    canonical(post(client, body), code="VAL-0003", status=422)
    assert world["spans"] == 1 and "advisory-lock" not in world["log"]


def test_an_oversized_body_is_413(monkeypatch):
    world: dict = {}
    client = build(monkeypatch, world)
    canonical(post(client, content=b"{" + b" " * (MAX_REQUEST_BYTES + 1)), code="VAL-0003", status=413)


# ---------------------------------------------------------------- the ledger and the clock


def test_a_stored_answer_is_replayed_exactly_and_no_row_is_locked(monkeypatch):
    stored = run_seal.record_response(RecordRow()).model_dump(by_alias=True, mode="json")
    world = {"replay": stored}
    client = build(monkeypatch, world)
    response = post(client)
    assert response.status_code == 200 and response.json() == stored
    assert "select:Run" not in world["log"]


def test_the_same_key_with_a_different_request_is_409(monkeypatch):
    world = {"replay_error": InvError(GRAPH_IDEMPOTENCY_CONFLICT, "different body")}
    client = build(monkeypatch, world)
    body = canonical(post(client), code="GRAPH-0002", status=409)
    assert body["detail"] == "That idempotency key was used with a different request."


def test_the_clock_is_read_once_after_the_lock_and_stamps_record_audit_and_ledger(monkeypatch):
    after_lock = NOW + dt.timedelta(minutes=30)
    world = {"advance_on_body": NOW + dt.timedelta(minutes=5), "advance_on_lock": after_lock}
    client = build(monkeypatch, world)
    assert post(client).status_code == 200
    assert len(world["clock_reads"]) == 1 and world["clock_reads"][0] > world["log"].index("advisory-lock")
    assert world["sealed"][0]["now"] == after_lock
    assert world["stored"][0]["now"] == after_lock and world["audits"][0]["now"] == after_lock


# ---------------------------------------------------------------- lock waits


def _operational(sqlstate):
    class Orig(Exception):
        pass

    orig = Orig("locked")
    orig.sqlstate = sqlstate
    return OperationalError("SELECT ... FOR UPDATE", {}, orig)


@pytest.mark.parametrize("entity", ["Run", "Artifact"])
@pytest.mark.parametrize("sqlstate", ["55P03", "40P01"])
def test_a_lock_timeout_or_deadlock_on_the_run_or_an_artifact_is_a_retryable_503(monkeypatch, entity, sqlstate):
    world = {"lock_errors": {entity: _operational(sqlstate)}}
    client = build(monkeypatch, world)
    body = canonical(post(client), code="SYS-0001", status=503, retryable=True)
    assert RUN not in body["detail"] and ART_A not in body["detail"]
    assert "service" not in world["log"] and world["stored"] == []


def test_any_other_operational_failure_is_not_disguised(monkeypatch):
    world = {"lock_errors": {"Run": _operational("57P01")}}
    client = build(monkeypatch, world)
    assert post(client).status_code == 500


# ---------------------------------------------------------------- registration and tables


def test_the_seal_route_is_registered_once_beside_the_read_route():
    from saintvision.api.v1 import projects, run_records

    routes = [(r.path, tuple(sorted(r.methods))) for r in projects.router.routes]
    assert routes.count(("/v1" + run_seal.SEAL_PATH, ("POST",))) == 1
    assert routes.count(("/v1" + run_records.RECORD_PATH, ("GET",))) == 1
    assert run_seal.SEAL_PATH == run_records.RECORD_PATH


def test_every_reachable_business_code_is_in_the_translation_table():
    assert {AUTH_PROJECT_SCOPE, RES_RUN_NOT_FOUND, VAL_SCHEMA, GRAPH_IDEMPOTENCY_CONFLICT} <= set(run_seal.TRANSLATION)


def test_the_route_records_no_denial_itself_and_declares_no_clock_dependency():
    import inspect

    source = inspect.getsource(run_seal)
    assert "record_denial_out_of_band" not in source
    assert "now" not in inspect.signature(run_seal.seal_run_record).parameters
