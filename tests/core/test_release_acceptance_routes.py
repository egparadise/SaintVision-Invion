"""The five routes, and above all the order they do things in (#282 §3, §0-1.5).

The first group is the gate, and it is the point of this file. ``O1`` asks for the order
to be stated and pinned: the prerequisite refusal must happen **before** the idempotency
ledger and before anything that reads a row, on all five routes including the two GETs.
Three properties make that checkable rather than asserted:

* every route answers ``SYS-0003`` / 503 / ``retryable=false`` with one fixed sentence;
* a refused request leaves **no ledger row** -- the key it carried is still unused;
* a refused request touches **no session at all**, which the tests establish by giving
  the app a session dependency that fails if anybody asks for it.

The second group is the request contract: a body that names a user, a missing
``Idempotency-Key``, a duplicate JSON key, an oversized body, an unknown field. Those
are refused at the same door whether or not the feature is on, and the tests run them
with the feature *on* so a 422 or 415 proves the body rules rather than the gate.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from saintvision.api import app as app_module  # noqa: E402
from saintvision.api.app import create_app  # noqa: E402
from saintvision.api.deps import get_session, get_write_session  # noqa: E402
from saintvision.api.v1 import release_acceptance as route  # noqa: E402
from saintvision.services import release_acceptance as service  # noqa: E402
from saintvision.config import Settings  # noqa: E402
from saintvision.identity.principal import Principal, StaticPrincipalVerifier  # noqa: E402

TENANT = uuid.UUID("22222222-2222-2222-2222-222222222222")
USER = "usr_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
RELEASE = "rel_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
PROPOSAL = "rap_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
ACCEPTANCE = "acc_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
NOW = dt.datetime(2026, 10, 1, 11, 0, 0, tzinfo=dt.timezone.utc)
AUTH = {"Authorization": "Bearer token", "Idempotency-Key": "key-one"}
JSON = {**AUTH, "Content-Type": "application/json"}

DECIDE = f"/v1/release-manifests/{RELEASE}/acceptance-decisions"
REVIEW = f"{DECIDE}/{PROPOSAL}"
CONFIRM = f"{REVIEW}/confirm"
WITHDRAW = f"/v1/release-manifests/{RELEASE}/acceptances/{ACCEPTANCE}/withdrawals"

DECISION_BODY = {
    "acceptanceIdRef": "AC-12",
    "outcome": "accepted",
    "targetManifestSha256": "a" * 64,
    "reasonCode": "OPERATIONAL_ACCEPTANCE",
    "targetRefs": [{"targetId": "target.one", "targetSha256": "c" * 64}],
    "measurementRefs": [
        {
            "evidenceId": "evidence.one",
            "evidenceSha256": "e" * 64,
            "observedAt": "2026-10-01T10:00:00.000000Z",
        }
    ],
    "knownLimitations": [],
}
CONFIRM_BODY = {"proposalDigest": "b" * 64, "targetManifestSha256": "a" * 64}
WITHDRAW_BODY = {"acceptedManifestSha256": "a" * 64, "reasonCode": "security-concern"}


class RefusingSession:
    """A session that fails on any use.

    This is how the "gate first" claim is measured rather than reviewed: if a handler
    reads a release, locks a row or reserves an idempotency key before refusing, the
    test fails with this message instead of passing with a 503 that happened to be
    produced late.
    """

    def __getattr__(self, name):
        raise AssertionError(f"a refused request must not touch the database (session.{name})")


class BoundResolver:
    """A resolver that resolves, for tests that need to get past the gate.

    Standing in for the registries a later card builds. Using it is how the request
    contract below is tested at all: with the real resolver the gate refuses first, which
    is correct in production and would make every body test assert 503.
    """

    bound = True

    def __init__(self, acceptance_id_ref: str = "AC-12") -> None:
        self.acceptance_id_ref = acceptance_id_ref

    def resolve(self, session, *, tenant_id, release_id, target_refs, measurement_refs):
        return SimpleNamespace(acceptance_id_ref=self.acceptance_id_ref)


def build(monkeypatch, *, enabled: bool, fresh: bool = True, session=None, resolver=None):
    principal = Principal(
        user_id=USER,
        tenant_id=TENANT,
        external_subject="oidc:operator",
        # #286's decision: one representation. A principal is fresh because the
        # verifier marked the claims verified and the canonical predicate admits them,
        # not because a second object was attached.
        verified_fresh_auth_claims=fresh,
        auth_time=int(NOW.timestamp()) - 60 if fresh else None,
        amr=frozenset({"mfa"}) if fresh else frozenset(),
        verified_token_issuer="https://idp.example/realms/inv" if fresh else None,
        verified_token_client_id="portal" if fresh else None,
        verified_token_expires_at=int(NOW.timestamp()) + 600 if fresh else None,
    )
    monkeypatch.setenv("INV_ENV", "test")
    # A denied request is audited in its own transaction, which opens a session from the
    # engine -- and these tests have no engine. Overridden here so an auth refusal
    # reports the refusal rather than failing on the audit of it.
    monkeypatch.setattr(app_module, "record_denial_out_of_band", lambda *a, **k: None)
    if resolver is not None:
        monkeypatch.setattr(service, "active_resolver", lambda: resolver)
    settings = Settings(
        database_url="postgresql+psycopg://offline:offline@localhost:1/offline",
        release_acceptance_write_enabled=enabled,
    )
    app = create_app(
        engine=object(),
        settings=settings,
        verifier=StaticPrincipalVerifier({"token": principal}, allow_outside_dev=True),
        clock=lambda: NOW,
        check_partitions_on_startup=False,
    )
    target = session if session is not None else RefusingSession()
    app.dependency_overrides[get_session] = lambda: target
    app.dependency_overrides[get_write_session] = lambda: target
    return TestClient(app, raise_server_exceptions=False)


# ------------------------------------------------------------------ the gate, on all five


GATED = [
    ("post", DECIDE, DECISION_BODY),
    ("get", DECIDE, None),
    ("get", REVIEW, None),
    ("post", CONFIRM, CONFIRM_BODY),
    ("post", WITHDRAW, WITHDRAW_BODY),
]


@pytest.mark.parametrize("method,path,body", GATED, ids=lambda value: str(value)[:40])
def test_every_route_including_the_gets_is_refused_before_it_touches_anything(
    monkeypatch, method, path, body
):
    client = build(monkeypatch, enabled=False)
    response = (
        client.get(path, headers=AUTH)
        if method == "get"
        else client.post(path, headers=JSON, content=json.dumps(body))
    )
    assert response.status_code == 503, response.text
    problem = response.json()
    assert problem["code"] == "SYS-0003"
    assert problem["retryable"] is False
    assert problem["detail"] == route.PREREQUISITES_DETAIL
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("method,path,body", GATED, ids=lambda value: str(value)[:40])
def test_authentication_comes_first_and_the_gate_immediately_after(monkeypatch, method, path, body):
    """No token is ``AUTH-0050``/401; a verified token on a closed surface is 503.

    I first wrote this test asserting 503 for an unauthenticated caller too, reasoning
    that a disabled surface should not confirm anything. That reasoning was wrong, and
    in the wrong direction: **every** route in this API answers 401 without a token, so
    401 here says nothing about this route -- while answering 503 to an anonymous caller
    would confirm that the path exists and that the feature is merely switched off.
    Authentication is also where the framework puts it, in the dependencies, and the
    order ``O1`` asks about is the gate against the *ledger* and the *rows*, which the
    tests above measure.
    """
    client = build(monkeypatch, enabled=False)
    # §7 asks for ``AUTH-0050``/401 on a missing or invalid token. Measured: this
    # application's shared auth dependency answers ``AUTH-MISSING-CREDENTIAL``/401 when
    # the header is absent and ``auth-invalid-credential``/403 when it is present and
    # wrong. ``AUTH-0050`` exists in the *kernel* application
    # (``services/control-plane``), not here. Producing it on these five routes would
    # mean changing the dependency every business route shares -- a cross-cutting
    # decision that is not this card's to make -- so the test states what the
    # application actually answers and the PR raises the deviation for the contract owner.
    for headers, expected, code in (
        ({}, 401, "AUTH-MISSING-CREDENTIAL"),
        ({"Authorization": "Bearer wrong"}, 403, "AUTH-INVALID-CREDENTIAL"),
        (AUTH, 503, "SYS-0003"),
    ):
        full = {**headers, "Content-Type": "application/json", "Idempotency-Key": "k"}
        response = (
            client.get(path, headers=headers)
            if method == "get"
            else client.post(path, headers=full, content=json.dumps(body))
        )
        assert response.status_code == expected, (headers, response.text)
        assert response.json()["code"] == code


def test_a_refused_write_reserves_no_idempotency_key(monkeypatch):
    """The ledger is untouched, so the key is still unused afterwards.

    ``RefusingSession`` already proves no statement ran; this states the consequence the
    contract cares about (§0-1.5: "off 응답은 receipt를 만들거나 proposal·audit row를
    남기지 않는다"), so a future refactor that reserved first and refused second fails
    here with a sentence about receipts rather than about attribute access.
    """
    client = build(monkeypatch, enabled=False)
    first = client.post(DECIDE, headers=JSON, content=json.dumps(DECISION_BODY))
    second = client.post(DECIDE, headers=JSON, content=json.dumps(DECISION_BODY))
    assert first.status_code == second.status_code == 503
    # Same answer twice, compared on the fields a receipt would have changed. The trace
    # id differs per request by design, so the whole body is not the comparison.
    assert first.json()["code"] == second.json()["code"] == "SYS-0003"
    assert first.json()["detail"] == second.json()["detail"] == route.PREREQUISITES_DETAIL


def test_the_gate_precedes_the_body_rules(monkeypatch):
    """A malformed body on a disabled surface is still 503, not 422.

    Which way round this goes is a real choice. 422 first would tell a caller their
    body was wrong on a route they cannot use, and -- worse -- would make the status
    code depend on the body, which is a side channel into whether the feature is on.
    """
    client = build(monkeypatch, enabled=False)
    response = client.post(DECIDE, headers=JSON, content="{not json")
    assert response.status_code == 503
    assert response.json()["code"] == "SYS-0003"


def test_the_enabled_flag_alone_does_not_open_the_surface(monkeypatch):
    """Turning the flag on changes nothing while the registries are unbound.

    This is the property that makes the flag safe to ship: the second half of the gate
    is a fact about the deployment, not a setting, so an operator cannot enable a
    two-person rule the build cannot prove (§0-1.2, §0-1.4).
    """
    # Card 194 binds the production resolver. Exercise the independent half of the
    # gate explicitly: a deployment that has not bound it still stays closed even when
    # an operator flips the write flag.
    client = build(monkeypatch, enabled=True, resolver=service.UnboundReferenceResolver())
    response = client.post(DECIDE, headers=JSON, content=json.dumps(DECISION_BODY))
    assert response.status_code == 503
    assert response.json()["code"] == "SYS-0003"


def test_the_gate_is_the_first_statement_of_every_handler():
    """Read the source, because ordering is the property and tests above are its effect.

    A handler could pass the tests above while doing something harmless before the gate
    today and something harmful after a refactor. This asserts the shape instead: the
    first statement in each handler body is the gate call.
    """
    import inspect

    for handler in (
        route.decide,
        route.list_pending,
        route.read_pending,
        route.confirm,
        route.withdraw,
    ):
        body = inspect.getsource(handler)
        statements = [
            line.strip()
            for line in body.split('"""')[-1].splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        assert statements[0] == "_gate(settings)", (handler.__name__, statements[:2])


# ------------------------------------------------------------------ the request contract


def test_the_body_may_not_name_a_user_or_carry_a_reauthentication_proof(monkeypatch):
    """Identity comes from the token. A body that supplies it is refused, not ignored.

    Ignoring an extra field would mean a caller could believe they had chosen the
    operator; the contract's ``extra="forbid"`` makes the attempt an error.
    """
    client = build(monkeypatch, enabled=True, resolver=BoundResolver())
    for extra in ("acceptedByUserId", "token", "reauthProof", "notes"):
        body = {**DECISION_BODY, extra: "x"}
        response = client.post(DECIDE, headers=JSON, content=json.dumps(body))
        assert response.status_code == 422, (extra, response.status_code)
        assert response.json()["code"] == "VAL-0003"


def test_a_duplicate_json_key_is_refused(monkeypatch):
    client = build(monkeypatch, enabled=True, resolver=BoundResolver())
    raw = '{"acceptanceIdRef":"AC-12","acceptanceIdRef":"AC-13"}'
    response = client.post(DECIDE, headers=JSON, content=raw)
    assert response.status_code == 422
    assert response.json()["code"] == "VAL-0003"


@pytest.mark.parametrize("key", [None, "", "k" * 129, "bad key", "key\n"])
def test_a_write_without_a_usable_idempotency_key_is_refused(monkeypatch, key):
    client = build(monkeypatch, enabled=True, resolver=BoundResolver())
    headers = {"Authorization": "Bearer token", "Content-Type": "application/json"}
    if key is not None:
        headers["Idempotency-Key"] = key
    response = client.post(DECIDE, headers=headers, content=json.dumps(DECISION_BODY))
    assert response.status_code == 422, (key, response.status_code)
    assert response.json()["code"] == "VAL-0003"


def test_a_non_json_media_type_is_refused(monkeypatch):
    client = build(monkeypatch, enabled=True, resolver=BoundResolver())
    headers = {**AUTH, "Content-Type": "text/plain"}
    response = client.post(DECIDE, headers=headers, content=json.dumps(DECISION_BODY))
    assert response.status_code == 415
    assert response.json()["code"] == "VAL-0003"


def test_an_oversized_body_is_refused(monkeypatch):
    client = build(monkeypatch, enabled=True, resolver=BoundResolver())
    body = {**DECISION_BODY, "reasonCode": "A" * 9000}
    response = client.post(DECIDE, headers=JSON, content=json.dumps(body))
    assert response.status_code in (413, 422)
    assert response.json()["code"] == "VAL-0003"


@pytest.mark.parametrize(
    "digest",
    ["A" * 64, "a" * 63, "a" * 64 + "\n", " " + "a" * 64, "a" * 65, ""],
)
def test_a_digest_that_is_not_exactly_lowercase_hex_is_refused(monkeypatch, digest):
    """§9.1: upper case, 63 characters and a trailing newline are each refused."""
    client = build(monkeypatch, enabled=True, resolver=BoundResolver())
    body = {**CONFIRM_BODY, "proposalDigest": digest}
    response = client.post(CONFIRM, headers=JSON, content=json.dumps(body))
    assert response.status_code == 422, (digest, response.status_code)
    assert response.json()["code"] == "VAL-0003"


def test_a_conditional_decision_must_name_its_limitations(monkeypatch):
    client = build(monkeypatch, enabled=True, resolver=BoundResolver())
    body = {**DECISION_BODY, "outcome": "conditional", "knownLimitations": []}
    assert client.post(DECIDE, headers=JSON, content=json.dumps(body)).status_code == 422
    accepted = {**DECISION_BODY, "knownLimitations": ["browser acceptance not observed"]}
    assert client.post(DECIDE, headers=JSON, content=json.dumps(accepted)).status_code == 422


@pytest.mark.parametrize("field", ["targetRefs", "measurementRefs"])
def test_a_decision_needs_at_least_one_of_each_reference(monkeypatch, field):
    client = build(monkeypatch, enabled=True, resolver=BoundResolver())
    body = {**DECISION_BODY, field: []}
    response = client.post(DECIDE, headers=JSON, content=json.dumps(body))
    assert response.status_code == 422
    assert response.json()["code"] == "VAL-0003"


@pytest.mark.parametrize("field", ["targetRefs", "measurementRefs"])
def test_duplicate_reference_ids_are_refused(monkeypatch, field):
    client = build(monkeypatch, enabled=True, resolver=BoundResolver())
    body = {**DECISION_BODY, field: list(DECISION_BODY[field]) * 2}
    response = client.post(DECIDE, headers=JSON, content=json.dumps(body))
    assert response.status_code == 422


# ------------------------------------------------------------------ where the denial is written


def test_the_audit_helper_refuses_an_outcome_the_column_does_not_allow():
    """``audit_events.outcome`` is ``varchar(8)`` over allow/deny/error (#286 r3).

    The denial of a committed refusal is the first ``deny`` this service writes, so the
    helper takes the outcome now -- and a value outside the set has to be a ValueError at
    the call site rather than a failed INSERT in the middle of a request.
    """
    assert service.AUDIT_OUTCOMES == frozenset({"allow", "deny"})
    with pytest.raises(ValueError) as refused:
        service._audit(
            None,
            principal=None,
            action=service.AUDIT_DENIED,
            detail={},
            now=NOW,
            outcome="succeeded",
        )
    assert "outcome" in str(refused.value)


def test_closing_a_proposal_is_the_only_place_the_denial_is_written():
    """The route records nothing, and exactly one function writes the row (#286 r3).

    Read from the source, because the point is *where* the call is rather than that some
    call exists: an out-of-band recorder in the route passed every behavioural test in r2
    and still broke the global invariant that the canonical boundary is the only route-side
    denial writer.
    """
    route_source = Path(route.__file__).read_text(encoding="utf-8")
    for writer in ("record_denial_out_of_band", "record_event", "audit_service"):
        assert writer not in route_source, writer
    # It may still *name* the action: ``_audited`` puts it on the problem so the shared
    # canonical handler uses it for the refusals that raise. Naming is not writing, and
    # that one line is the whole of the route's part in the audit.
    assert route_source.count("audit_action=service.AUDIT_DENIED") == 1

    source = Path(service.__file__).read_text(encoding="utf-8")
    writing = [line for line in source.splitlines() if "action=AUDIT_DENIED" in line]
    assert len(writing) == 1, writing
    body = source.split("def _close_proposal(")[1].split("\ndef ")[0]
    assert "action=AUDIT_DENIED" in body and 'outcome="deny"' in body


# ------------------------------------------------------------------ one policy, statically


def test_no_second_fresh_auth_representation_survives_in_the_tree():
    """#286's decision, pinned where a revival would be visible.

    A behavioural test cannot see a *second* policy that happens to agree today. These
    assertions can: the removed names, and the removed constants, must not come back.
    """
    from saintvision.identity import oidc as oidc_module
    from saintvision.identity import principal as principal_module
    from saintvision.services import release_acceptance_auth as auth_module
    from saintvision.services import release_acceptance as service_module

    identity_source = Path(oidc_module.__file__).read_text(encoding="utf-8")
    principal_source = Path(principal_module.__file__).read_text(encoding="utf-8")
    auth_source = Path(auth_module.__file__).read_text(encoding="utf-8")
    service_source = Path(service_module.__file__).read_text(encoding="utf-8")

    # The second parse and the second object are gone, and `FreshAuth` is not importable.
    assert not hasattr(principal_module, "FreshAuth")
    assert not hasattr(oidc_module, "_fresh_auth_from")
    assert "def _fresh_auth_from" not in identity_source
    assert "fresh_auth=" not in identity_source
    assert "class FreshAuth:" not in principal_source

    # The acceptance side holds no policy of its own: no registry, no second-factor set,
    # no window constant.
    for banned in ("RFC8176", "SECOND_FACTORS", "FRESH_AUTH_WINDOW_SECONDS", "webauthn"):
        assert banned not in auth_source, banned
    assert not hasattr(auth_module, "RFC8176_VALUES")
    assert not hasattr(auth_module, "SECOND_FACTORS")
    assert not hasattr(auth_module, "FRESH_AUTH_WINDOW_SECONDS")

    # It asks the canonical predicate, exactly once, and the window it uses is the
    # canonical one.
    assert auth_source.count("has_fresh_interactive_auth(principal, now=now)") == 1
    assert "FRESH_AUTH_MAX_AGE_SECONDS" in auth_source
    assert "principal_policy.FRESH_AUTH_MAX_AGE_SECONDS" in service_source

    # And the one judge is where #285 put it.
    assert hasattr(principal_module, "has_fresh_interactive_auth")


def test_removing_the_canonical_predicate_call_is_caught():
    """The mutation this pins: an acceptance boundary that stops asking.

    Read from the source rather than monkeypatched, because the mutation that matters is
    the call disappearing -- and a test that patches the function still passes when the
    call is gone.
    """
    from saintvision.services import release_acceptance_auth as auth_module

    source = Path(auth_module.__file__).read_text(encoding="utf-8")
    body = source.split("def proof_of_interactive_human(")[1]
    assert "if not has_fresh_interactive_auth(principal, now=now):" in body
    assert "raise NotInteractiveHuman" in body.split(
        "if not has_fresh_interactive_auth(principal, now=now):"
    )[1][:200]


def test_every_write_route_goes_through_the_one_consumer():
    """Including the replay path: a route that skipped it would admit a stale operator."""
    from saintvision.services import release_acceptance as service_module

    source = Path(service_module.__file__).read_text(encoding="utf-8")
    assert source.count("fresh.proof_of_interactive_human(principal, now=now)") == 2
    # Every route, counted against the number of routes rather than a number I typed:
    # a sixth route that forgot the call would otherwise pass.
    route_source = Path(route.__file__).read_text(encoding="utf-8")
    assert route_source.count("service.require_fresh_operator(") == route_source.count("@router.")
