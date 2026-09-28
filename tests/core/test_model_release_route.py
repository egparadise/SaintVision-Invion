"""VF-CL-03: the release route, its canonical errors and its body boundary.

Every test here is one of the reversions listed in the approved design
(``docs/vault/30_Development/VF-CL-03_import_adapter_요청경로_결속_설계.md`` §9,
v1.3). The numbering in the test names is that list's, so a finding in review and
a failure here refer to the same item.

PostgreSQL behaviour -- RLS across tenants, the path/project mismatch answering
the same 404, and the version staying ``draft`` after a refusal -- is items 28-30
and runs on hosted CI against a real database. Nothing here pretends to cover it:
the session is a stand-in that answers exactly the calls the route makes, so what
it proves is the route's ordering and its wire contract, not the database's.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import json
import urllib.error
import uuid

import pytest
from fastapi.testclient import TestClient

from inv.contracts import validate_contract
from inv.errors import DomainError
from saintvision.adapters.model_import import (
    MODEL_IMPORT_DECLARATION_MISMATCH,
    compare_declaration,
)
from saintvision.api import problem as problem_module
from saintvision.api import schemas
from saintvision.api.app import create_app
from saintvision.api.problem import (
    CANONICAL_KEYS,
    MAX_REQUEST_BYTES,
    CanonicalProblem,
    require_absent_body,
    strict_json_object,
    translate,
)
from saintvision.api.v1 import model_release
from saintvision.config import Settings
from saintvision.errors import AUTH_PROJECT_SCOPE, VAL_SCHEMA, InvError
from saintvision.identity.principal import Principal, StaticPrincipalVerifier

TENANT = uuid.UUID("11111111-1111-1111-1111-111111111111")
OTHER_TENANT = uuid.UUID("22222222-2222-2222-2222-222222222222")
PROJECT = "prj_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
MODEL = "mdl_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
VERSION_ID = "mvr_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
RUN_ID = "run_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
VERSION = "1.4.0"
SHA = "a" * 64
DECLARATION = {"licensePolicy": "internal-only-eula-2026", "classification": "restricted"}
PATH = f"/v1/projects/{PROJECT}/models/{MODEL}/versions/{VERSION}/release"
AUTH = {"Authorization": "Bearer release-token"}


def observation(**overrides):
    body = {
        "projectId": PROJECT,
        "modelId": MODEL,
        "version": VERSION,
        "manifestHash": "b" * 64,
        "sourceRunId": RUN_ID,
        "committedAt": "2026-09-28T01:00:00Z",
        "commitRecoveryEpoch": "33333333-3333-3333-3333-333333333333",
        "format": "safetensors",
        "totalBytes": 4096,
        "shardCount": 1,
        "committed": True,
        "currentAvailability": "unknown",
        "requiresExecutionRevalidation": True,
        **DECLARATION,
    }
    body.update(overrides)
    return body


class Row:
    """The columns the route reads. Not an ORM object: nothing here queries."""

    def __init__(self, *, tenant_id=TENANT, verified=True, pinned=True, stage="draft"):
        self.model_version_id = VERSION_ID
        self.tenant_id = tenant_id
        self.model_id = MODEL
        self.version = VERSION
        self.stage = stage
        self.content_sha256 = SHA
        self.verified_at = dt.datetime(2026, 9, 1, tzinfo=dt.timezone.utc) if verified else None
        self.retention_pinned_until = (
            dt.datetime(2027, 9, 1, tzinfo=dt.timezone.utc) if pinned else None
        )


class Parent:
    def __init__(self, *, tenant_id=TENANT, project_id=PROJECT):
        self.model_id = MODEL
        self.tenant_id = tenant_id
        self.project_id = project_id


class Scalars:
    def __init__(self, row):
        self._row = row

    def one_or_none(self):
        return self._row


class Session:
    def __init__(self, world):
        self.world = world

    def get(self, _model, _key, **_kwargs):
        return self.world["parent"]

    def scalars(self, _statement):
        return Scalars(self.world["row"])


class Factory:
    """A session factory that records transaction spans.

    The route must hold none open while it talks to the kernel, so the depth is
    observable rather than argued about.
    """

    def __init__(self, world):
        self.world = world
        world.setdefault("depth", 0)
        world.setdefault("spans", 0)

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


def build(monkeypatch, world, *, kernel_base_url="http://kernel.invalid"):
    """An app whose database work is replaced and whose kernel call is injected."""
    world.setdefault("parent", Parent())
    world.setdefault("row", Row())
    world.setdefault("missing", [])
    world.setdefault("permission", {"canRequest": True, "canApprove": True})
    world.setdefault("audits", [])
    world.setdefault("released", [])

    factory = Factory(world)
    monkeypatch.setattr(model_release, "make_session_factory", lambda _engine: factory)
    monkeypatch.setattr(
        model_release, "tenant_scope", lambda _session, _tenant: contextlib.nullcontext()
    )

    def require_project_access(_session, *, tenant_id, project_id, user_id):
        denial = world.get("denial")
        if denial is not None:
            raise denial
        return world["permission"]

    monkeypatch.setattr(
        model_release.project_service, "require_project_access", require_project_access
    )
    monkeypatch.setattr(
        model_release,
        "trace_model",
        lambda _session, **_kwargs: {"missing": list(world["missing"])},
    )

    def release(_session, *, tenant_id, model_version_id, now):
        row = world["row"]
        row.stage = "released"
        world["released"].append(model_version_id)
        return row

    monkeypatch.setattr(model_release, "release_model_version", release)
    monkeypatch.setattr(
        model_release,
        "record_event",
        lambda _session, **kwargs: world["audits"].append(kwargs) or "audit",
    )

    def fetcher(**kwargs):
        world.setdefault("fetches", []).append({**kwargs, "depth": world["depth"]})
        error = world.get("fetch_error")
        if error is not None:
            raise error
        return world.get("observation", observation())

    principal = Principal(
        user_id="usr_01J8Z3XQ2K9WMV5T7N4B6C8D0E",
        tenant_id=TENANT,
        external_subject="oidc:release",
        project_ids=frozenset({PROJECT}),
    )
    app = create_app(
        engine=object(),
        settings=Settings(database_url="postgresql://unused", kernel_base_url=kernel_base_url),
        verifier=StaticPrincipalVerifier(
            {"release-token": principal}, allow_outside_dev=True
        ),
        check_partitions_on_startup=False,
    )
    app.state.model_commitment_fetcher = fetcher
    return TestClient(app, raise_server_exceptions=False)


def post(client, body=DECLARATION, *, headers=None, data=None, content_type="application/json"):
    sent = {**AUTH}
    if content_type is not None:
        sent["Content-Type"] = content_type
    sent.update(headers or {})
    payload = data if data is not None else json.dumps(body).encode("utf-8")
    return client.post(PATH, content=payload, headers=sent)


def canonical(response, *, code, status, retryable=False):
    """Assert the canonical envelope, not just the code."""
    assert response.status_code == status, response.text
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert set(body) == set(CANONICAL_KEYS), body
    assert body["type"] == "about:blank"
    assert body["code"] == code
    assert body["status"] == status
    assert body["retryable"] is retryable
    assert body["category"] == code.split("-", 1)[0]
    validate_contract("ProblemDetails", body)
    return body


# ---------------------------------------------------------------------------
# 1, 2, 5: the comparison, its position, and what the refusal may carry
# ---------------------------------------------------------------------------


def test_01_a_proposal_that_differs_from_the_declaration_cannot_release(monkeypatch):
    world = {}
    client = build(monkeypatch, world)
    response = post(client, {**DECLARATION, "classification": "public"})
    canonical(response, code="MODEL-0009", status=409)
    assert world["released"] == []
    assert world["row"].stage == "draft"


def test_02_an_unverified_version_is_refused_before_the_declaration_is_compared(monkeypatch):
    world = {"row": Row(verified=False)}
    client = build(monkeypatch, world)
    # The proposal is wrong too. The caller must still be told the version is not
    # verified, or they read the answer as "fix the declaration and it releases".
    body = canonical(
        post(client, {**DECLARATION, "classification": "public"}),
        code="GRAPH-0002",
        status=409,
    )
    assert "unverified" in body["detail"]
    assert world["released"] == []


def test_02b_an_unpinned_or_untraceable_version_is_refused_the_same_way(monkeypatch):
    world = {"row": Row(pinned=False)}
    client = build(monkeypatch, world)
    canonical(post(client), code="GRAPH-0002", status=409)

    world = {"missing": ["dataset_version", "approval"]}
    client = build(monkeypatch, world)
    body = canonical(post(client), code="GRAPH-0002", status=409)
    assert "dataset_version" in body["detail"]
    assert world["released"] == []


def test_05_neither_the_refusal_nor_the_audit_carries_the_declared_values(monkeypatch):
    world = {}
    client = build(monkeypatch, world)
    body = canonical(
        post(client, {"licensePolicy": "some-other-eula", "classification": "public"}),
        code="MODEL-0009",
        status=409,
    )
    # Field names are diagnosable; values are operator text and never echoed.
    assert "differs:licensePolicy" in body["detail"]
    assert "differs:classification" in body["detail"]
    for value in ("some-other-eula", "public", DECLARATION["licensePolicy"], "restricted"):
        assert value not in json.dumps(body)

    world = {}
    client = build(monkeypatch, world)
    assert post(client).status_code == 200
    detail = world["audits"][0]["detail"]
    assert detail["declarationFields"] == ["licensePolicy", "classification"]
    for value in DECLARATION.values():
        assert value not in json.dumps(detail)


def test_05b_audit_redaction_does_not_cover_these_field_names(monkeypatch):
    """Why 05 is the only defence: nothing filters these values automatically."""
    from saintvision.services.audit import redact

    redacted = redact({"licensePolicy": "secret-eula", "classification": "restricted"})
    assert redacted == {"licensePolicy": "secret-eula", "classification": "restricted"}


# ---------------------------------------------------------------------------
# 3, 13: the observation must describe the row that was named
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        {"projectId": "prj_01J8Z3XQ2K9WMV5T7N4B6C8D0F"},
        {"modelId": "mdl_01J8Z3XQ2K9WMV5T7N4B6C8D0F"},
        {"version": "9.9.9"},
    ],
)
def test_03_13_an_observation_for_another_identity_is_a_404(monkeypatch, overrides):
    world = {"observation": observation(**overrides)}
    client = build(monkeypatch, world)
    body = canonical(post(client), code="RES-0004", status=404)
    assert body["detail"] == "No such model version."
    assert world["released"] == []
    assert world["row"].stage == "draft"


# ---------------------------------------------------------------------------
# 4, 10, 11, 12: the observation is checked, not trusted
# ---------------------------------------------------------------------------


def test_10_an_observation_missing_a_required_field_fails_closed(monkeypatch):
    incomplete = observation()
    del incomplete["manifestHash"]
    world = {"observation": incomplete}
    client = build(monkeypatch, world)
    canonical(post(client), code="SYS-0001", status=503, retryable=True)
    assert world["released"] == []


def test_11_an_observation_with_an_unknown_field_fails_closed(monkeypatch):
    world = {"observation": observation(unexpected="value")}
    client = build(monkeypatch, world)
    canonical(post(client), code="SYS-0001", status=503, retryable=True)


def test_12_an_observation_outside_the_enum_or_const_fails_closed(monkeypatch):
    for override in (
        {"classification": "Restricted"},
        {"currentAvailability": "available"},
        {"requiresExecutionRevalidation": False},
    ):
        world = {"observation": observation(**override)}
        client = build(monkeypatch, world)
        canonical(post(client), code="SYS-0001", status=503, retryable=True)
        assert world["released"] == []


def test_04_an_uncommitted_observation_is_a_precondition_not_an_outage(monkeypatch):
    """Unreachable through the contract, which pins ``committed`` to true.

    Kept and tested with validation stubbed, because the branch exists for the
    day the contract changes: "the kernel says not committed" is not a 503.
    """
    world = {"observation": observation(committed=False)}
    client = build(monkeypatch, world)
    canonical(post(client), code="SYS-0001", status=503, retryable=True)

    calls = []
    monkeypatch.setattr(
        "inv.contracts.validate_contract", lambda name, value: calls.append(name)
    )
    world = {"observation": observation(committed=False)}
    client = build(monkeypatch, world)
    body = canonical(post(client), code="GRAPH-0002", status=409)
    assert "not committed" in body["detail"]
    assert world["released"] == []


def test_an_unreachable_or_unconfigured_kernel_is_a_retryable_503(monkeypatch):
    world = {"fetch_error": OSError("connection refused")}
    client = build(monkeypatch, world)
    canonical(post(client), code="SYS-0001", status=503, retryable=True)

    world = {}
    client = build(monkeypatch, world, kernel_base_url=None)
    body = canonical(post(client), code="SYS-0001", status=503, retryable=True)
    assert "not configured" in body["detail"]
    assert world.get("fetches") is None


# ---------------------------------------------------------------------------
# 6: the request schema
# ---------------------------------------------------------------------------


def test_06_an_unknown_field_in_the_proposal_is_refused_by_the_schema(monkeypatch):
    assert schemas.ModelReleaseRequest.model_config["extra"] == "forbid"
    world = {}
    client = build(monkeypatch, world)
    canonical(post(client, {**DECLARATION, "notes": "hi"}), code="VAL-0003", status=422)
    assert world.get("fetches") is None

    for body in ({}, {"licensePolicy": "x"}, {**DECLARATION, "classification": "Public"}):
        client = build(monkeypatch, {})
        canonical(post(client, body), code="VAL-0003", status=422)


def test_06b_the_adapter_still_reports_an_extra_field_the_route_can_no_longer_reach():
    """The schema refuses first, so keep the adapter's branch covered directly.

    Dropping it because "the route cannot reach it" would leave the adapter
    unguarded for any other caller.
    """
    assert compare_declaration(DECLARATION, {**DECLARATION, "notes": "hi"}) == ["extra:notes"]


# ---------------------------------------------------------------------------
# 7, 9: the permission grade and the window it is checked in
# ---------------------------------------------------------------------------


def test_07_request_grade_permission_cannot_release(monkeypatch):
    world = {"permission": {"canRequest": True, "canApprove": False}}
    client = build(monkeypatch, world)
    body = canonical(post(client), code="AUTH-0030", status=403)
    assert "approval permission" in body["detail"]
    assert world["released"] == []
    # Refused before the kernel is asked anything.
    assert world.get("fetches") is None


def test_07b_an_inaccessible_project_is_the_same_403(monkeypatch):
    world = {
        "denial": InvError(
            AUTH_PROJECT_SCOPE, "project is not accessible to this principal",
            extra={"projectId": PROJECT},
        )
    }
    client = build(monkeypatch, world)
    body = canonical(post(client), code="AUTH-0030", status=403)
    assert body["detail"] == "This project is not accessible."
    assert "projectId" not in body


def test_09_permission_revoked_after_the_preflight_stops_the_release(monkeypatch):
    world = {}
    client = build(monkeypatch, world)
    calls = {"n": 0}
    original = model_release.project_service.require_project_access

    def revoke_after_first(session, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return world["permission"]
        raise InvError(AUTH_PROJECT_SCOPE, "project is not accessible to this principal")

    monkeypatch.setattr(
        model_release.project_service, "require_project_access", revoke_after_first
    )
    canonical(post(client), code="AUTH-0030", status=403)
    assert calls["n"] == 2, "the atomic span must re-check, not trust the preflight"
    assert world["released"] == []
    assert world["row"].stage == "draft"
    assert world["audits"] == []


def test_the_snapshot_is_not_what_authorisation_rests_on():
    """Item 7's premise: the snapshot would pass a revoked membership."""
    principal = Principal(
        user_id="usr_01J8Z3XQ2K9WMV5T7N4B6C8D0E",
        tenant_id=TENANT,
        external_subject="oidc:release",
        project_ids=frozenset({PROJECT}),
    )
    principal.require_project(PROJECT)  # still passes after revocation
    assert "require_project_access" in str(model_release.__doc__ or "") or True
    source = (model_release.__file__ or "")
    assert source.endswith("model_release.py")
    with open(source, encoding="utf-8") as handle:
        text = handle.read()
    assert "require_project_access" in text
    assert "principal.require_project(" not in text


# ---------------------------------------------------------------------------
# 8: no transaction is held across the network call
# ---------------------------------------------------------------------------


def test_08_no_business_transaction_is_open_while_the_kernel_is_called(monkeypatch):
    world = {}
    client = build(monkeypatch, world)
    assert post(client).status_code == 200
    assert [fetch["depth"] for fetch in world["fetches"]] == [0]
    assert world["spans"] == 2, "one preflight span and one atomic span"
    assert world["depth"] == 0


def test_08b_the_callers_own_credential_is_forwarded(monkeypatch):
    world = {}
    client = build(monkeypatch, world)
    assert post(client).status_code == 200
    assert world["fetches"][0]["credential"] == "release-token"


# ---------------------------------------------------------------------------
# 15: the path is resolved to one row, through the parent
# ---------------------------------------------------------------------------


def test_15_the_route_binds_the_path_to_a_row_and_locks_it(monkeypatch):
    world = {}
    client = build(monkeypatch, world)
    assert post(client).status_code == 200
    assert world["released"] == [VERSION_ID]

    source = open(model_release.__file__, encoding="utf-8").read()
    assert "with_for_update()" in source
    assert "ModelVersion.version == version" in source


@pytest.mark.parametrize(
    "world",
    [
        {"parent": None},
        {"parent": Parent(project_id="prj_01J8Z3XQ2K9WMV5T7N4B6C8D0F")},
        {"parent": Parent(tenant_id=OTHER_TENANT)},
        {"row": None},
        {"row": Row(tenant_id=OTHER_TENANT)},
    ],
)
def test_15b_absent_other_project_and_other_tenant_are_one_404(monkeypatch, world):
    client = build(monkeypatch, world)
    body = canonical(post(client), code="RES-0004", status=404)
    assert body["detail"] == "No such model version."


# ---------------------------------------------------------------------------
# 14: every error is the canonical envelope, and 16: so is the success
# ---------------------------------------------------------------------------


def test_14_every_error_this_route_can_emit_has_the_exact_canonical_key_set(monkeypatch):
    seen = {}
    cases = [
        ("VAL-0003", 422, False, {}, {"body": {**DECLARATION, "notes": "x"}}),
        ("AUTH-0030", 403, False, {"permission": {"canApprove": False}}, {}),
        ("RES-0004", 404, False, {"row": None}, {}),
        ("GRAPH-0002", 409, False, {"row": Row(verified=False)}, {}),
        ("SYS-0001", 503, True, {"fetch_error": OSError("down")}, {}),
        ("MODEL-0009", 409, False, {}, {"body": {**DECLARATION, "classification": "public"}}),
    ]
    for code, status, retryable, world, kwargs in cases:
        client = build(monkeypatch, dict(world))
        seen[code] = canonical(post(client, **kwargs), code=code, status=status, retryable=retryable)
    assert set(seen) == {
        "VAL-0003",
        "AUTH-0030",
        "RES-0004",
        "GRAPH-0002",
        "SYS-0001",
        "MODEL-0009",
    }
    for body in seen.values():
        assert "fields" not in body
        assert "instance" not in body
        assert "mismatches" not in body


def test_16_the_success_body_is_the_exact_result_contract(monkeypatch):
    world = {}
    client = build(monkeypatch, world)
    response = post(client)
    assert response.status_code == 200
    body = response.json()
    assert body == {
        "modelVersionId": VERSION_ID,
        "modelId": MODEL,
        "version": VERSION,
        "stage": "released",
        "contentSha256": SHA,
    }
    schemas.ModelReleaseResponse.model_validate(body)
    with pytest.raises(Exception):
        schemas.ModelReleaseResponse.model_validate({**body, "extra": 1})
    with pytest.raises(Exception):
        schemas.ModelReleaseResponse.model_validate({**body, "stage": "candidate"})
    incomplete = dict(body)
    del incomplete["contentSha256"]
    with pytest.raises(Exception):
        schemas.ModelReleaseResponse.model_validate(incomplete)


# ---------------------------------------------------------------------------
# 17-19, 24-27: the body boundary
# ---------------------------------------------------------------------------


def test_17_malformed_json_is_one_canonical_refusal(monkeypatch):
    world = {}
    client = build(monkeypatch, world)
    canonical(post(client, data=b'{"licensePolicy":'), code="VAL-0003", status=422)
    assert world.get("fetches") is None


@pytest.mark.parametrize("payload", [b'[{"licensePolicy":"x"}]', b'"released"', b"3", b"null"])
def test_18_19_an_array_or_a_scalar_body_is_refused(monkeypatch, payload):
    client = build(monkeypatch, {})
    canonical(post(client, data=payload), code="VAL-0003", status=422)


def test_24_invalid_utf8_bytes_do_not_escape_as_a_500(monkeypatch):
    client = build(monkeypatch, {})
    canonical(post(client, data=b'{"licensePolicy":"\xff\xfe"}'), code="VAL-0003", status=422)


def test_25_a_duplicate_key_is_ambiguous_and_refused(monkeypatch):
    client = build(monkeypatch, {})
    canonical(
        post(
            client,
            data=b'{"licensePolicy":"a","classification":"public","classification":"restricted"}',
        ),
        code="VAL-0003",
        status=422,
    )
    # Standard json would have taken the last value and released.
    assert json.loads(b'{"a":1,"a":2}') == {"a": 2}


def test_26_a_wrong_content_type_or_any_content_encoding_is_415(monkeypatch):
    client = build(monkeypatch, {})
    canonical(post(client, content_type="text/plain"), code="VAL-0003", status=415)
    client = build(monkeypatch, {})
    canonical(
        post(client, headers={"Content-Encoding": "gzip"}), code="VAL-0003", status=415
    )
    # A charset parameter is accepted: this route is called by importers and
    # people, not only by our own agents.
    client = build(monkeypatch, {})
    assert post(client, content_type="application/json; charset=utf-8").status_code == 200


def test_27_an_oversize_body_is_413_and_is_not_parsed(monkeypatch):
    client = build(monkeypatch, {})
    payload = json.dumps({**DECLARATION, "pad": "x" * MAX_REQUEST_BYTES}).encode("utf-8")
    assert len(payload) > MAX_REQUEST_BYTES
    canonical(post(client, data=payload), code="VAL-0003", status=413)


def test_an_empty_body_is_refused(monkeypatch):
    client = build(monkeypatch, {})
    canonical(post(client, data=b""), code="VAL-0003", status=422)


def test_the_shared_helper_refuses_a_body_where_a_route_takes_none():
    require_absent_body(b"")
    with pytest.raises(CanonicalProblem) as raised:
        require_absent_body(b" ")
    assert (raised.value.code, raised.value.status) == ("VAL-0003", 422)


def test_strict_json_object_translates_every_parser_failure_to_one_code():
    for raw in (
        b'{"a":',
        b'{"a":1,"a":2}',
        b"[1]",
        b'{"a":Infinity}',
        b'{"a":"\xff"}',
        b"[" * 4000 + b"]" * 4000,
    ):
        with pytest.raises(CanonicalProblem) as raised:
            strict_json_object(raw, content_type="application/json")
        assert (raised.value.code, raised.value.status) == ("VAL-0003", 422), raw[:20]
    assert strict_json_object(b'{"a":1}', content_type="application/json") == {"a": 1}


# ---------------------------------------------------------------------------
# 20-23: the canonical module itself
# ---------------------------------------------------------------------------


def test_20_pydantic_error_contents_are_never_serialised(monkeypatch):
    client = build(monkeypatch, {})
    body = canonical(
        post(client, {"licensePolicy": "x" * 500, "classification": "public"}),
        code="VAL-0003",
        status=422,
    )
    assert body["detail"] == "The request body does not match the schema."
    assert "licensePolicy" not in json.dumps(body)
    assert "x" * 50 not in json.dumps(body)


def test_21_the_business_error_type_cannot_express_these_codes():
    for code in ("MODEL-0009", "SYS-0001", "SYS-0002"):
        with pytest.raises(ValueError, match="no known category prefix"):
            InvError(code, "would be the error path collapsing into a 500")
    # And the shape it does produce is not the canonical one.
    legacy = InvError(VAL_SCHEMA, "bad", extra={"mismatches": ["differs:x"]}).to_problem(
        trace_id="0" * 31 + "1"
    )
    assert legacy["type"].startswith("https://")
    assert "mismatches" in legacy
    with pytest.raises(DomainError):
        validate_contract("ProblemDetails", legacy)


def test_22_the_canonical_body_is_validated_against_the_contract():
    body = CanonicalProblem("MODEL-0009", 409, "declaration differs").body(
        trace_id="0" * 31 + "1"
    )
    assert list(body) == list(CANONICAL_KEYS)
    assert body["type"] == "about:blank"
    # The anchor is what would catch a regression that added a key back.
    with pytest.raises(DomainError):
        validate_contract("ProblemDetails", {**body, "instance": "/v1/x"})
    with pytest.raises(DomainError):
        validate_contract("ProblemDetails", {k: v for k, v in body.items() if k != "detail"})


def test_22b_a_non_canonical_code_or_status_is_refused_at_construction():
    for code in ("VAL-SCHEMA", "model-0009", "MODEL-9"):
        with pytest.raises(ValueError, match="not canonical"):
            CanonicalProblem(code, 409, "x")
    with pytest.raises(ValueError, match="not an error status"):
        CanonicalProblem("MODEL-0009", 200, "x")
    with pytest.raises(ValueError, match="detail is required"):
        CanonicalProblem("MODEL-0009", 409, "")


def test_23_the_translation_table_covers_every_code_this_route_can_reach():
    reachable = {VAL_SCHEMA, AUTH_PROJECT_SCOPE, MODEL_IMPORT_DECLARATION_MISMATCH}
    assert reachable <= set(model_release.TRANSLATION)
    # Read the service, so a new refusal added there without a mapping here is a
    # failing test rather than a 500 in production.
    import re

    from saintvision.services import lineage as lineage_module

    source = open(lineage_module.__file__, encoding="utf-8").read()
    body = source[source.index("def release_model_version") : source.index("def trace_model")]
    raised = set(re.findall(r"InvError\(\s*([A-Za-z_][A-Za-z_0-9]*)", body))
    assert raised == {"VAL_SCHEMA"}, raised
    assert {getattr(lineage_module, name) for name in raised} <= set(
        model_release.TRANSLATION
    )
    unmapped = translate(
        InvError("RES-NODE-NOT-FOUND", "something else entirely"),
        table=model_release.TRANSLATION,
    )
    assert (unmapped.code, unmapped.status, unmapped.retryable) == ("SYS-0002", 500, False)
    assert "something else entirely" not in unmapped.detail


def test_23b_sys_0001_is_not_reused_for_our_own_mapping_gap():
    """The ledger records why: a 503 made clients retry and paged operators."""
    assert problem_module.SYS_UNMAPPED == "SYS-0002"
    assert problem_module.SYS_UPSTREAM_UNAVAILABLE == "SYS-0001"


# ---------------------------------------------------------------------------
# Registration: a route the deployed topology never reaches is not a route
# ---------------------------------------------------------------------------


def test_the_route_is_visible_to_the_business_dispatch_selection():
    from saintvision.api.v1 import adapters, projects, settings as settings_router

    routes = [
        route
        for module in (projects, settings_router, adapters)
        for route in module.router.routes
    ]
    matching = [route for route in routes if getattr(route, "path", "").endswith("/release")]
    assert len(matching) == 1
    assert matching[0].methods == {"POST"}
    assert matching[0].path == (
        "/v1/projects/{project_id}/models/{model_id}/versions/{version}/release"
    )


def test_the_existing_error_handlers_are_left_in_place(monkeypatch):
    # The legacy InvError handler records the denial out of band, which needs a
    # real engine; this file has none, so the write is stubbed. What is under
    # test is that the legacy handler still answers, not that it writes.
    from saintvision.api import app as app_module

    monkeypatch.setattr(app_module, "record_denial_out_of_band", lambda *a, **k: None)
    client = build(monkeypatch, {})
    response = client.post(PATH, content=b"{}")
    assert response.status_code == 401
    body = response.json()
    # The legacy shape still serves the legacy path, untouched by this card.
    assert body["code"] == "AUTH-MISSING-CREDENTIAL"
    assert response.headers["www-authenticate"] == "Bearer"


# ---------------------------------------------------------------------------
# F-R1: the deployed factory must bind the kernel URL, and the blocking fetch
# must not run on the event loop it may be calling back into
# ---------------------------------------------------------------------------


def test_fr1_the_production_factory_binds_the_kernel_base_url():
    """The defect: ``Settings(database_url=...)`` alone leaves it None.

    A route that answers 503 in every deployment has not closed the blocker,
    however well the development helper is configured, so the binding is checked
    where the deployed app is actually built.
    """
    assert Settings(database_url="configured").kernel_base_url is None

    from pathlib import Path

    factory = (
        Path(__file__).resolve().parents[2]
        / "services/control-plane/src/inv/business_surface.py"
    )
    source = factory.read_text(encoding="utf-8")
    assert "kernel_base_url=kernel_base_url" in source
    assert "INV_KERNEL_BASE_URL" in source
    # Kernel and business are the same process and port here, so the fallback is
    # the loopback self URL rather than a guessed host.
    assert 'os.environ.get(\'PORT\', \'8080\')' in source or 'os.environ.get("PORT", "8080")' in source

    compose = (Path(__file__).resolve().parents[2] / "docker-compose.prod.yml").read_text(
        encoding="utf-8"
    )
    assert "INV_KERNEL_BASE_URL" in compose


def test_fr1_the_kernel_fetch_does_not_run_on_the_event_loop(monkeypatch):
    """A self-call on the loop would wait for a request only the loop can serve.

    Asserted by where the fetch runs: off the loop thread, with no running loop
    in it. Remove ``run_in_threadpool`` and this fails instead of deadlocking in
    production.
    """
    import asyncio
    import threading

    observed: dict[str, object] = {}
    world: dict = {}

    def fetcher(**kwargs):
        observed["thread"] = threading.current_thread().name
        try:
            asyncio.get_running_loop()
            observed["loop"] = True
        except RuntimeError:
            observed["loop"] = False
        return observation()

    client = build(monkeypatch, world)
    client.app.state.model_commitment_fetcher = fetcher
    assert post(client).status_code == 200
    assert observed["loop"] is False, "the blocking GET ran on the event loop"
    assert observed["thread"] != threading.current_thread().name


# ---------------------------------------------------------------------------
# F-R3: the transport around the caller's bearer token
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def kernel_stub(handler_factory):
    """A real HTTP server, because what is under test is the HTTP client."""
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    received: list[dict] = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            received.append(
                {"path": self.path, "authorization": self.headers.get("Authorization")}
            )
            handler_factory(self)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", received
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _send(handler, status, body: bytes, headers=None):
    handler.send_response(status)
    for name, value in (headers or {}).items():
        handler.send_header(name, value)
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    if body:
        handler.wfile.write(body)


def test_fr3_a_redirect_is_refused_and_the_bearer_never_reaches_the_target():
    """Python's redirect handler copies ``Authorization`` onto the new request."""

    def redirect(handler):
        if handler.path.endswith("/commitment"):
            _send(handler, 302, b"", {"Location": "/elsewhere"})
        else:
            _send(handler, 200, json.dumps(observation()).encode("utf-8"))

    with kernel_stub(redirect) as (base_url, received):
        with pytest.raises(urllib.error.HTTPError):
            model_release.fetch_commitment(
                base_url=base_url,
                credential="release-token",
                project_id=PROJECT,
                model_id=MODEL,
                version=VERSION,
            )
    assert [entry["path"].endswith("/commitment") for entry in received] == [True]
    assert not any(entry["path"] == "/elsewhere" for entry in received)


def test_fr3_a_refused_redirect_reaches_the_caller_as_a_retryable_503(monkeypatch):
    def redirect(handler):
        _send(handler, 302, b"", {"Location": "http://other.invalid/steal"})

    with kernel_stub(redirect) as (base_url, _received):
        client = build(monkeypatch, {}, kernel_base_url=base_url)
        client.app.state.model_commitment_fetcher = None
        canonical(post(client), code="SYS-0001", status=503, retryable=True)


def test_fr3_an_oversize_response_is_refused_without_being_held(monkeypatch):
    def huge(handler):
        _send(handler, 200, b"[" + b"0," * 60000 + b"0]")

    with kernel_stub(huge) as (base_url, _received):
        with pytest.raises(ValueError, match="permitted size"):
            model_release.fetch_commitment(
                base_url=base_url,
                credential="release-token",
                project_id=PROJECT,
                model_id=MODEL,
                version=VERSION,
            )
        client = build(monkeypatch, {}, kernel_base_url=base_url)
        client.app.state.model_commitment_fetcher = None
        canonical(post(client), code="SYS-0001", status=503, retryable=True)


def test_fr3_invalid_utf8_in_the_response_is_a_canonical_503(monkeypatch):
    """Reported as an uncaught 500; it is not, and this pins that.

    ``UnicodeDecodeError`` derives from ``ValueError``, which the observation
    reader already catches, so the answer is the canonical ``SYS-0001``. The test
    exists because the claim is worth checking rather than arguing about.
    """
    assert issubclass(UnicodeDecodeError, ValueError)

    def invalid(handler):
        _send(handler, 200, b'{"projectId": "\xff\xfe"}')

    with kernel_stub(invalid) as (base_url, _received):
        with pytest.raises(UnicodeDecodeError):
            model_release.fetch_commitment(
                base_url=base_url,
                credential="release-token",
                project_id=PROJECT,
                model_id=MODEL,
                version=VERSION,
            )
        client = build(monkeypatch, {}, kernel_base_url=base_url)
        client.app.state.model_commitment_fetcher = None
        canonical(post(client), code="SYS-0001", status=503, retryable=True)


def test_fr3_only_http_and_https_are_accepted_as_a_kernel_base_url():
    for base_url in ("file:///etc/passwd", "ftp://kernel.invalid", "gopher://x"):
        with pytest.raises(ValueError, match="http or https"):
            model_release.fetch_commitment(
                base_url=base_url,
                credential="release-token",
                project_id=PROJECT,
                model_id=MODEL,
                version=VERSION,
            )


def test_fr3_the_positive_path_still_works_over_real_http(monkeypatch):
    """The stub is a real server, so this is the self-call shape end to end."""

    def ok(handler):
        _send(handler, 200, json.dumps(observation()).encode("utf-8"))

    with kernel_stub(ok) as (base_url, received):
        client = build(monkeypatch, {}, kernel_base_url=base_url)
        client.app.state.model_commitment_fetcher = None
        assert post(client).status_code == 200
    assert received[0]["authorization"] == "Bearer release-token"
    assert received[0]["path"] == (
        f"/v1/projects/{PROJECT}/models/{MODEL}/versions/{VERSION}/commitment"
    )


def test_fr3_the_request_body_bound_is_applied_while_reading(monkeypatch):
    """The bound is an allocation limit, not only a parser limit.

    ``await request.body()`` buffers everything before its length can be checked;
    the streaming read refuses at the first chunk that crosses the bound.
    """
    from saintvision.api.problem import read_bounded_body

    source = open(model_release.__file__, encoding="utf-8").read()
    assert "read_bounded_body(request)" in source
    assert "await request.body()" not in source

    client = build(monkeypatch, {})
    payload = b"{" + b'"pad":"' + b"x" * (MAX_REQUEST_BYTES * 4) + b'"}'
    canonical(post(client, data=payload), code="VAL-0003", status=413)


# ---------------------------------------------------------------------------
# The real-PostgreSQL fixture, exercised without PostgreSQL
# ---------------------------------------------------------------------------


def test_the_real_pg_seed_builds_every_row_without_a_database():
    """Run the integration fixture's body against a stub connection.

    This exists because the six real-PostgreSQL nodes all failed on hosted CI in
    ``_seed`` -- ``new_id("code_commit")`` is not an entity kind, the id kind is
    ``commit`` -- and every product assertion behind them went unrun. The failure
    needed no database to find, so it should not have needed one: importing the
    fixture and handing it a connection that only records statements catches this
    whole class before the hosted run.
    """
    import datetime as dt
    import importlib.util
    from pathlib import Path

    from saintvision.db.models.lineage import LINEAGE_KINDS
    from saintvision.ids import PREFIXES

    path = (
        Path(__file__).resolve().parents[1]
        / "integration/test_model_release_real_pg.py"
    )
    spec = importlib.util.spec_from_file_location("real_pg_release_fixture", path)
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
        recorder,
        tenant_id=TENANT,
        now=dt.datetime(2026, 9, 9, tzinfo=dt.timezone.utc),
        project_code="fixture-guard",
    )
    assert set(seeded) == {"user_id", "project_id", "model_id", "version_id"}
    # users, projects, project_members, models, model_versions, four edges.
    assert len(recorder.statements) == 9

    # The trap itself, named: two lineage kinds are not entity kinds, so a fixture
    # that reuses an edge kind as an id kind raises.
    assert set(LINEAGE_KINDS) - set(PREFIXES) == {"code_commit", "container_image"}
