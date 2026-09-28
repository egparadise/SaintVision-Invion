"""G-04 PR 3 (R3): the context-bundle metadata route, over real HTTP, without a database.

Same harness and rules as PR 1 (``test_run_record_route.py``): the session
answers exactly the calls the route makes, the services are recorded rather
than re-implemented, and each test is a reversion the design (G-04·G-05 통합
설계 §3, §7) says must fail.
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
from saintvision.api.v1 import context_bundles, lineage_query
from saintvision.config import Settings
from saintvision.errors import (
    AUTH_PROJECT_SCOPE,
    CTX_SNAPSHOT_MISSING,
    RES_RUN_NOT_FOUND,
    InvError,
)
from saintvision.identity.principal import Principal, StaticPrincipalVerifier

TENANT = uuid.UUID("11111111-1111-1111-1111-111111111111")
OTHER_TENANT = uuid.UUID("22222222-2222-2222-2222-222222222222")
PROJECT = "prj_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
OTHER_PROJECT = "prj_01J8Z3XQ2K9WMV5T7N4B6C8D0F"
RUN = "run_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
OTHER_RUN = "run_01J8Z3XQ2K9WMV5T7N4B6C8D0F"
WORKLOAD = "wkl_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
BUNDLE = "bdl_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
LATEST = "bdl_01J8Z3XQ2K9WMV5T7N4B6C8D0F"
SHA = "c" * 64
HASH_A = "a" * 64
HASH_B = "b" * 64
PATH = f"/v1/projects/{PROJECT}/runs/{RUN}/context-bundle"
AUTH = {"Authorization": "Bearer bundle-token"}
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
    def __init__(self, *, bundle_id=BUNDLE):
        self.record_id = "rec_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
        self.run_id = RUN
        self.bundle_id = bundle_id


class BundleRow:
    def __init__(self, bundle_id=BUNDLE, *, tenant_id=TENANT, run_id=RUN):
        self.bundle_id = bundle_id
        self.tenant_id = tenant_id
        self.run_id = run_id
        self.bundle_hash = SHA
        self.item_count = 2
        self.total_bytes = 11
        self.retrieval_strategy = "explicit"
        self.component_versions = {"retriever": "explicit-1"}
        self.token_estimate = 7
        self.built_at = NOW


class ItemRow:
    def __init__(self, ordinal, item_id, content_hash, *, kind="document", confidence=None, redacted=True):
        self.ordinal = ordinal
        self.item_id = item_id
        self.item_version = 1
        self.kind = kind
        self.content_hash = content_hash
        self.source_uri = "file:///secret/path/should/not/appear"
        self.confidence = confidence
        self.redacted = redacted


class _Scalars:
    def __init__(self, row):
        self._row = row

    def first(self):
        return self._row


class Session:
    def __init__(self, world):
        self.world = world
        self.gets: list[tuple[str, object]] = []
        self.latest_queries = 0

    def get(self, model, key, **_kwargs):
        self.gets.append((model.__name__, key))
        if model.__name__ == "ContextBundle":
            return self.world["bundles"].get(key)
        return self.world.get(model.__name__.lower())

    def scalars(self, _statement):
        self.latest_queries += 1
        return _Scalars(self.world.get("latest"))


def build(monkeypatch, world):
    world.setdefault("run", RunRow())
    world.setdefault("workload", WorkloadRow())
    world.setdefault("record", RecordRow())
    world.setdefault("bundles", {BUNDLE: BundleRow(), LATEST: BundleRow(LATEST)})
    world.setdefault("latest", world["bundles"].get(LATEST))
    world.setdefault(
        "entries",
        [(ItemRow(0, "doc-0", HASH_A), "hello"), (ItemRow(1, "doc-1", HASH_B, kind="code", confidence=0.5), "world!")],
    )
    world.setdefault("verified", True)
    session = Session(world)
    world["session"] = session

    principal = Principal(
        user_id="usr_01J8Z3XQ2K9WMV5T7N4B6C8D0E",
        tenant_id=TENANT,
        external_subject="oidc:bundle",
        project_ids=frozenset({PROJECT}),
    )
    app = create_app(
        engine=object(),
        settings=Settings(database_url="postgresql://unused"),
        verifier=StaticPrincipalVerifier({"bundle-token": principal}, allow_outside_dev=True),
        check_partitions_on_startup=False,
    )
    from saintvision.api.deps import get_session

    app.dependency_overrides[get_session] = lambda: session
    from saintvision.api import app as app_module

    monkeypatch.setattr(
        app_module,
        "record_denial_out_of_band",
        lambda _engine, **kwargs: world.setdefault("denials_recorded", []).append(kwargs),
    )

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

    def read_bundle(_session, *, tenant_id, bundle_id):
        world.setdefault("read_calls", []).append((tenant_id, bundle_id))
        if world.get("read_error") is not None:
            raise world["read_error"]
        return world["entries"]

    def verify_bundle(_session, *, tenant_id, bundle_id):
        world.setdefault("verify_calls", []).append((tenant_id, bundle_id))
        if world.get("verify_error") is not None:
            raise world["verify_error"]
        return world["verified"]

    monkeypatch.setattr(context_bundles.record_service, "get_record", get_record)
    monkeypatch.setattr(context_bundles.context_service, "read_bundle", read_bundle)
    monkeypatch.setattr(context_bundles.context_service, "verify_bundle", verify_bundle)
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


# ---------------------------------------------------------------- the answer


def test_a_member_reads_the_sealed_bundles_metadata_as_the_strict_contract(monkeypatch):
    world: dict = {}
    client = build(monkeypatch, world)
    response = client.get(PATH, headers=AUTH)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body == {
        "bundleId": BUNDLE, "runId": RUN, "bundleHash": SHA, "hashVerified": True, "sealed": True,
        "itemCount": 2, "totalBytes": 11, "retrievalStrategy": "explicit",
        "componentVersions": {"retriever": "explicit-1"}, "tokenEstimate": 7, "builtAt": "2026-09-28T05:00:00Z",
        "items": [
            {"ordinal": 0, "itemId": "doc-0", "itemVersion": 1, "kind": "document", "contentHash": HASH_A,
             "byteSize": 5, "confidence": None, "redacted": True},
            {"ordinal": 1, "itemId": "doc-1", "itemVersion": 1, "kind": "code", "contentHash": HASH_B,
             "byteSize": 6, "confidence": 0.5, "redacted": True},
        ],
    }
    schemas.ContextBundleResponse.model_validate(body)
    assert "hello" not in response.text and "world!" not in response.text          # no content
    assert "secret/path" not in response.text                                     # no source URI
    assert world["access_calls"] == [(TENANT, PROJECT, "usr_01J8Z3XQ2K9WMV5T7N4B6C8D0E")]
    assert world["session"].gets[:2] == [("Run", RUN), ("Workload", WORKLOAD)]
    assert world["record_calls"] == [(TENANT, RUN)]
    assert world["read_calls"] == [(TENANT, BUNDLE)] and world["verify_calls"] == [(TENANT, BUNDLE)]
    assert world["session"].latest_queries == 0                                    # the sealed pin, not a search


def test_byte_size_is_the_utf8_length_of_the_content_never_the_content(monkeypatch):
    world = {"entries": [(ItemRow(0, "doc-0", HASH_A), "héllo wörld")]}
    client = build(monkeypatch, world)
    body = client.get(PATH, headers=AUTH).json()
    assert body["items"][0]["byteSize"] == len("héllo wörld".encode("utf-8")) == 13
    assert "héllo" not in client.get(PATH, headers=AUTH).text


def test_a_hash_mismatch_is_a_200_fact_not_an_error(monkeypatch):
    world = {"verified": False}
    client = build(monkeypatch, world)
    response = client.get(PATH, headers=AUTH)
    assert response.status_code == 200 and response.json()["hashVerified"] is False
    assert response.json()["bundleHash"] == SHA                                    # what the record said, unchanged


def test_a_missing_snapshot_is_the_canonical_409_not_a_verified_false(monkeypatch):
    world = {"read_error": InvError(CTX_SNAPSHOT_MISSING, "a bundle item's snapshot is missing", cause_ref=BUNDLE)}
    client = build(monkeypatch, world)
    body = canonical(client.get(PATH, headers=AUTH), code="GRAPH-0002", status=409)
    assert body["detail"] == "A bundle item's snapshot is missing; the bundle cannot be reproduced."
    assert "verify_calls" not in world


# ---------------------------------------------------------------- which bundle


def test_an_unsealed_run_answers_its_latest_bundle_and_says_so(monkeypatch):
    world = {"record": None}
    client = build(monkeypatch, world)
    body = client.get(PATH, headers=AUTH).json()
    assert body["bundleId"] == LATEST and body["sealed"] is False
    assert world["session"].latest_queries == 1
    assert world["read_calls"] == [(TENANT, LATEST)]


def test_a_record_sealed_without_a_bundle_falls_back_to_the_latest(monkeypatch):
    world = {"record": RecordRow(bundle_id=None)}
    client = build(monkeypatch, world)
    body = client.get(PATH, headers=AUTH).json()
    assert body["bundleId"] == LATEST and body["sealed"] is False


def test_a_run_with_no_bundle_at_all_is_404(monkeypatch):
    world = {"record": None, "latest": None}
    client = build(monkeypatch, world)
    body = canonical(client.get(PATH, headers=AUTH), code="RES-0004", status=404)
    assert body["detail"] == "No context bundle for this run."
    assert "read_calls" not in world


@pytest.mark.parametrize(
    "pinned",
    [None, BundleRow(BUNDLE, tenant_id=OTHER_TENANT), BundleRow(BUNDLE, run_id=OTHER_RUN)],
    ids=["absent", "other-tenant", "other-run"],
)
def test_a_sealed_pin_that_does_not_belong_to_this_run_is_404_never_answered(monkeypatch, pinned):
    """The record already checked this at sealing; the route checks it again
    rather than trusting a row it did not lock."""
    world = {"bundles": {BUNDLE: pinned} if pinned is not None else {}}
    client = build(monkeypatch, world)
    canonical(client.get(PATH, headers=AUTH), code="RES-0004", status=404)
    assert "read_calls" not in world


# ---------------------------------------------------------------- shared rules (revert: drop membership / binding)


def test_a_non_member_is_403_before_any_row_and_the_denial_is_recorded(monkeypatch):
    world = {"denial": InvError(AUTH_PROJECT_SCOPE, "project is not accessible to this principal")}
    client = build(monkeypatch, world)
    canonical(client.get(PATH, headers=AUTH), code="AUTH-0030", status=403)
    assert world["session"].gets == [] and "record_calls" not in world
    assert len(world["denials_recorded"]) == 1
    assert world["denials_recorded"][0]["action"] == "GET /v1/projects/{project_id}/runs/{run_id}/context-bundle"
    assert world["denials_recorded"][0]["target_id"] == PROJECT


def test_a_non_member_with_a_body_is_403_and_the_body_is_never_judged(monkeypatch):
    world = {"denial": InvError(AUTH_PROJECT_SCOPE, "project is not accessible to this principal")}
    client = build(monkeypatch, world)
    canonical(client.request("GET", PATH, headers=AUTH, content=b"{" + b"x" * 20000), code="AUTH-0030", status=403)
    assert world["session"].gets == []


def test_a_body_on_this_get_is_refused_after_membership_and_before_any_row(monkeypatch):
    world: dict = {}
    client = build(monkeypatch, world)
    canonical(client.request("GET", PATH, headers=AUTH, content=b"{}"), code="VAL-0003", status=422)
    assert world["access_calls"] == [(TENANT, PROJECT, "usr_01J8Z3XQ2K9WMV5T7N4B6C8D0E")]
    assert world["session"].gets == [] and "record_calls" not in world


def test_an_oversized_body_is_refused_by_the_shared_bounded_reader(monkeypatch):
    world: dict = {}
    client = build(monkeypatch, world)
    canonical(client.request("GET", PATH, headers=AUTH, content=b"x" * 9000), code="VAL-0003", status=413)
    assert world["session"].gets == []


@pytest.mark.parametrize(
    "world,label",
    [
        ({"run": None}, "missing run"),
        ({"run": RunRow(tenant_id=OTHER_TENANT)}, "another tenant's run"),
        ({"workload": WorkloadRow(project_id=OTHER_PROJECT)}, "another project's run"),
        ({"workload": None}, "run without a workload"),
    ],
)
def test_binding_failures_are_the_same_404_before_the_bundle_is_looked_up(monkeypatch, world, label):
    client = build(monkeypatch, dict(world))
    body = canonical(client.get(PATH, headers=AUTH), code="RES-0004", status=404)
    assert body["detail"] == "No such run."
    assert BUNDLE not in body["detail"]


def test_without_a_credential_the_route_is_401_and_the_denial_is_audited_before_any_row(monkeypatch):
    world: dict = {}
    client = build(monkeypatch, world)
    response = client.get(PATH)
    assert response.status_code == 401, response.text
    assert response.headers["www-authenticate"] == "Bearer"
    denials = world["denials_recorded"]
    assert [d["reason_code"] for d in denials] == ["AUTH-MISSING-CREDENTIAL"]
    assert denials[0]["actor_type"] == "anonymous" and denials[0]["tenant_id"] is None
    assert denials[0]["action"] == "GET /v1/projects/{project_id}/runs/{run_id}/context-bundle"
    assert world["session"].gets == [] and world["access_calls"] == []


# ---------------------------------------------------------------- tables and registration


def test_every_reachable_business_code_is_in_the_translation_table():
    reachable = {AUTH_PROJECT_SCOPE, RES_RUN_NOT_FOUND, CTX_SNAPSHOT_MISSING}
    assert reachable <= set(context_bundles.TRANSLATION)
    assert context_bundles.TRANSLATION[CTX_SNAPSHOT_MISSING] == ("GRAPH-0002", 409, False)


def test_the_route_is_registered_once_on_the_projects_router_and_the_action_fits_the_column():
    from saintvision.api.audit_action import AUDIT_ACTION_LIMIT
    from saintvision.api.v1 import projects

    paths = [route.path for route in projects.router.routes]
    assert paths.count("/v1" + context_bundles.BUNDLE_PATH) == 1
    assert len("GET /v1" + context_bundles.BUNDLE_PATH) <= AUDIT_ACTION_LIMIT


def test_the_services_are_called_not_re_implemented():
    source = open(context_bundles.__file__, encoding="utf-8").read()
    assert "bundle_hash(" not in source and "content_hash(" not in source      # no recomputation in the route
    assert "ContextSnapshot" not in source                                     # no content read in the route
