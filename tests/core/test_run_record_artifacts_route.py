"""G-04 PR 2 (R2): the pinned-artifact list and the pin verification routes.

Same harness and same rules as PR 1 (``test_run_record_route.py``): the
session answers exactly the calls the routes make, the service functions are
recorded rather than re-implemented, and each test is a reversion the design
(G-04·G-05 통합 설계 v1.1 §3, §7) says must fail.
"""

from __future__ import annotations

import datetime as dt
import uuid

import pytest
from fastapi.testclient import TestClient

from inv.contracts import validate_contract
from saintvision.api import schemas
from saintvision.api.app import create_app
from saintvision.api.problem import CANONICAL_KEYS
from saintvision.api.v1 import lineage_query, run_records
from saintvision.config import Settings
from saintvision.errors import (
    AUTH_PROJECT_SCOPE,
    RES_ARTIFACT_NOT_FOUND,
    RES_RUN_NOT_FOUND,
    VAL_SCHEMA,
    InvError,
)
from saintvision.identity.principal import Principal, StaticPrincipalVerifier
from saintvision.services.records import ARTIFACT_ROLES

TENANT = uuid.UUID("11111111-1111-1111-1111-111111111111")
OTHER_TENANT = uuid.UUID("22222222-2222-2222-2222-222222222222")
PROJECT = "prj_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
OTHER_PROJECT = "prj_01J8Z3XQ2K9WMV5T7N4B6C8D0F"
RUN = "run_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
WORKLOAD = "wkl_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
RECORD = "rec_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
ART_DIFF = "art_01J8Z3XQ2K9WMV5T7N4B6C8D0A"
ART_TRACE = "art_01J8Z3XQ2K9WMV5T7N4B6C8D0B"
SHA = "c" * 64
ARTIFACTS_PATH = f"/v1/projects/{PROJECT}/runs/{RUN}/record/artifacts"
AUTH = {"Authorization": "Bearer record-token"}
NOW = dt.datetime(2026, 9, 28, 5, 0, tzinfo=dt.timezone.utc)


def verify_path(artifact_id):
    return f"{ARTIFACTS_PATH}/{artifact_id}/verify"


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
    record_id = RECORD
    run_id = RUN


class PinRow:
    def __init__(self, artifact_id, role, *, checksum=SHA):
        self.tenant_id = TENANT
        self.record_id = RECORD
        self.artifact_id = artifact_id
        self.role = role
        self.uri = f"inv://artifacts/{RUN}/{artifact_id}"
        self.checksum_sha256 = checksum
        self.object_version = "v1"
        self.byte_size = 12


class Session:
    def __init__(self, world):
        self.world = world
        self.gets: list[tuple[str, object]] = []

    def get(self, model, key, **_kwargs):
        self.gets.append((model.__name__, key))
        if model.__name__ == "RunRecordArtifact":
            return self.world["pins"].get(key[2])
        return self.world.get(model.__name__.lower())


def build(monkeypatch, world):
    world.setdefault("run", RunRow())
    world.setdefault("workload", WorkloadRow())
    world.setdefault("record", RecordRow())
    world.setdefault("pins", {ART_DIFF: PinRow(ART_DIFF, "diff"), ART_TRACE: PinRow(ART_TRACE, "trace")})
    world.setdefault("live_checksums", {ART_DIFF: SHA, ART_TRACE: SHA})
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

    def list_pinned_artifacts(_session, *, tenant_id, record_id, role=None):
        world.setdefault("list_calls", []).append((tenant_id, record_id, role))
        if role is not None and role not in ARTIFACT_ROLES:
            raise InvError(VAL_SCHEMA, f"unknown artifact role: {role!r}")
        rows = [pin for pin in world["pins"].values() if role is None or pin.role == role]
        return sorted(rows, key=lambda pin: pin.artifact_id)

    def verify_pin(_session, *, tenant_id, record_id, artifact_id):
        world.setdefault("verify_calls", []).append((tenant_id, record_id, artifact_id))
        pin = world["pins"].get(artifact_id)
        if pin is None:
            raise InvError(RES_ARTIFACT_NOT_FOUND, "artifact is not pinned to this record")
        live = world["live_checksums"].get(artifact_id)
        return live is not None and live == pin.checksum_sha256

    monkeypatch.setattr(run_records.record_service, "get_record", get_record)
    monkeypatch.setattr(run_records.record_service, "list_pinned_artifacts", list_pinned_artifacts)
    monkeypatch.setattr(run_records.record_service, "verify_pin", verify_pin)
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


# ---------------------------------------------------------------- list: shape, role filter, order of checks


def test_a_member_lists_the_pins_in_artifact_id_order_as_the_strict_contract(monkeypatch):
    world: dict = {}
    client = build(monkeypatch, world)
    response = client.get(ARTIFACTS_PATH, headers=AUTH)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body == {
        "recordId": RECORD,
        "runId": RUN,
        "role": None,
        "items": [
            {"artifactId": ART_DIFF, "role": "diff", "uri": f"inv://artifacts/{RUN}/{ART_DIFF}",
             "checksumSha256": SHA, "objectVersion": "v1", "byteSize": 12},
            {"artifactId": ART_TRACE, "role": "trace", "uri": f"inv://artifacts/{RUN}/{ART_TRACE}",
             "checksumSha256": SHA, "objectVersion": "v1", "byteSize": 12},
        ],
        "count": 2,
    }
    schemas.RunRecordArtifactsResponse.model_validate(body)
    assert world["access_calls"] == [(TENANT, PROJECT, "usr_01J8Z3XQ2K9WMV5T7N4B6C8D0E")]
    assert world["session"].gets[:2] == [("Run", RUN), ("Workload", WORKLOAD)]
    assert world["record_calls"] == [(TENANT, RUN)]
    assert world["list_calls"] == [(TENANT, RECORD, None)]


def test_the_role_filter_is_passed_to_the_service_and_echoed(monkeypatch):
    world: dict = {}
    client = build(monkeypatch, world)
    body = client.get(ARTIFACTS_PATH + "?role=trace", headers=AUTH).json()
    assert body["role"] == "trace" and [i["artifactId"] for i in body["items"]] == [ART_TRACE] and body["count"] == 1
    assert world["list_calls"] == [(TENANT, RECORD, "trace")]


def test_an_unknown_role_is_the_services_422_not_a_route_copy_of_the_list(monkeypatch):
    world: dict = {}
    client = build(monkeypatch, world)
    body = canonical(client.get(ARTIFACTS_PATH + "?role=screenshot", headers=AUTH), code="VAL-0003", status=422)
    assert body["detail"] == "Unknown artifact role."
    assert world["list_calls"] == [(TENANT, RECORD, "screenshot")]      # the service decided, after the binding
    source = open(run_records.__file__, encoding="utf-8").read()
    assert "ARTIFACT_ROLES" not in source                              # no copy of the allowed roles in the route


@pytest.mark.parametrize("query", ["?limit=5", "?role=diff&role=trace", "?Role=diff"])
def test_unsupported_or_repeated_query_parameters_are_refused_before_any_row(monkeypatch, query):
    world: dict = {}
    client = build(monkeypatch, world)
    canonical(client.get(ARTIFACTS_PATH + query, headers=AUTH), code="VAL-0003", status=422)
    assert world["session"].gets == [] and "list_calls" not in world


def test_an_empty_record_lists_nothing_with_count_zero(monkeypatch):
    world = {"pins": {}}
    client = build(monkeypatch, world)
    body = client.get(ARTIFACTS_PATH, headers=AUTH).json()
    assert body["items"] == [] and body["count"] == 0


# ---------------------------------------------------------------- verify: facts, not errors


def test_verify_reports_true_when_the_object_still_matches(monkeypatch):
    world: dict = {}
    client = build(monkeypatch, world)
    response = client.get(verify_path(ART_DIFF), headers=AUTH)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body == {"recordId": RECORD, "runId": RUN, "artifactId": ART_DIFF, "verified": True, "pinnedChecksumSha256": SHA}
    schemas.ArtifactPinVerificationResponse.model_validate(body)
    assert world["verify_calls"] == [(TENANT, RECORD, ART_DIFF)]


def test_a_changed_or_missing_object_is_verified_false_with_200_not_an_error(monkeypatch):
    world = {"live_checksums": {ART_DIFF: "d" * 64, ART_TRACE: None}}
    client = build(monkeypatch, world)
    changed = client.get(verify_path(ART_DIFF), headers=AUTH)
    assert changed.status_code == 200 and changed.json()["verified"] is False
    assert changed.json()["pinnedChecksumSha256"] == SHA                # what the record said, unchanged
    gone = client.get(verify_path(ART_TRACE), headers=AUTH)
    assert gone.status_code == 200 and gone.json()["verified"] is False


@pytest.mark.parametrize(
    "artifact_id",
    ["art_01J8Z3XQ2K9WMV5T7N4B6C8D0Z", "not-an-id", "run_01J8Z3XQ2K9WMV5T7N4B6C8D0E"],
)
def test_an_artifact_not_pinned_to_this_record_or_malformed_is_the_same_404(monkeypatch, artifact_id):
    world: dict = {}
    client = build(monkeypatch, world)
    body = canonical(client.get(verify_path(artifact_id), headers=AUTH), code="RES-0004", status=404)
    assert body["detail"] == "No such pinned artifact."


# ---------------------------------------------------------------- shared rules (revert: drop membership / binding)


@pytest.mark.parametrize("path", [ARTIFACTS_PATH, verify_path(ART_DIFF)])
def test_a_non_member_is_403_before_any_row_on_both_routes(monkeypatch, path):
    world = {"denial": InvError(AUTH_PROJECT_SCOPE, "project is not accessible to this principal")}
    client = build(monkeypatch, world)
    canonical(client.get(path, headers=AUTH), code="AUTH-0030", status=403)
    assert world["session"].gets == [] and "record_calls" not in world


@pytest.mark.parametrize("path", [ARTIFACTS_PATH, verify_path(ART_DIFF)])
@pytest.mark.parametrize(
    "world,label",
    [
        ({"run": None}, "missing run"),
        ({"run": RunRow(tenant_id=OTHER_TENANT)}, "another tenant's run"),
        ({"workload": WorkloadRow(project_id=OTHER_PROJECT)}, "another project's run"),
        ({"record": None}, "unsealed run"),
    ],
)
def test_binding_and_sealing_failures_are_404_on_both_routes(monkeypatch, path, world, label):
    client = build(monkeypatch, dict(world))
    canonical(client.get(path, headers=AUTH), code="RES-0004", status=404)


@pytest.mark.parametrize("path", [ARTIFACTS_PATH, verify_path(ART_DIFF)])
def test_a_body_on_these_gets_is_refused(monkeypatch, path):
    client = build(monkeypatch, {})
    canonical(client.request("GET", path, headers=AUTH, content=b"{}"), code="VAL-0003", status=422)


def test_every_reachable_business_code_is_in_the_translation_table():
    reachable = {AUTH_PROJECT_SCOPE, RES_RUN_NOT_FOUND, RES_ARTIFACT_NOT_FOUND, VAL_SCHEMA}
    assert reachable <= set(run_records.TRANSLATION)
    assert run_records.TRANSLATION[VAL_SCHEMA] == ("VAL-0003", 422, False)
    assert run_records.TRANSLATION[RES_ARTIFACT_NOT_FOUND] == ("RES-0004", 404, False)


def test_the_three_routes_are_registered_once_each():
    from saintvision.api.v1 import projects

    paths = [route.path for route in projects.router.routes]
    for suffix in (run_records.RECORD_PATH, run_records.ARTIFACTS_PATH, run_records.VERIFY_PATH):
        assert paths.count("/v1" + suffix) + paths.count(suffix) == 1, suffix


def test_the_response_models_are_strict():
    with pytest.raises(Exception):
        schemas.ArtifactPinVerificationResponse.model_validate(
            {"recordId": RECORD, "runId": RUN, "artifactId": ART_DIFF, "verified": True, "content": "x"}
        )
    with pytest.raises(Exception):
        schemas.RunRecordArtifactPin.model_validate(
            {"artifactId": ART_DIFF, "role": "screenshot", "uri": "u", "checksumSha256": SHA, "byteSize": 1}
        )
