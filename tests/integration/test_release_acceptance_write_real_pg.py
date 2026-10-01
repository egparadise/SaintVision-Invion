"""The two-person write path over HTTP against a real PostgreSQL (#282 §4, §5, §8).

These are the five things only a real database and a real request can establish, and each
one is a hole Codex measured in the first implementation:

* **convergence.** The same decision under a second idempotency key gets the first
  proposal's answer with ``replayed=true``, and leaves one proposal, one vote and one
  audit row -- not a second of each, and not a conflict that an operator cannot recover
  from;
* **the confirmer race.** The loser of two confirmations converges on the decision the
  winner recorded, with two votes and one confirm audit row;
* **the invalidation commit.** An expired proposal's closing is *kept*: the lifecycle row
  exists, the slot is empty, the 409 is the idempotency receipt, and another key asking
  again gets the same 409. Raising rolled all of that back;
* **the resolver at confirm time.** A reference that resolved when the proposal was made
  and does not resolve now refuses the confirmation. Deleting that call used to leave 124
  focused tests green;
* **the denial audit.** A refused state transition leaves exactly one audit row, with the
  action §8 names, written by the single audit point rather than by the route.

Rows are read as the owner: the application role has no SELECT on ``audit_events`` since
0047, and reading them through it would beg the question.
"""

from __future__ import annotations

import datetime as dt
import json
from types import SimpleNamespace
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from saintvision.api.app import create_app
from saintvision.config import Settings
from saintvision.identity.principal import Principal, StaticPrincipalVerifier
from saintvision.ids import new_id
from saintvision.db.session import make_session_factory, tenant_scope
from saintvision.errors import AUTH_PROJECT_SCOPE, InvError
from saintvision.services import release_acceptance as service
from saintvision.services import release_acceptance_auth as fresh_auth
from saintvision.services import release_acceptance_policy as policy

pytestmark = pytest.mark.postgres

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 10, 1, 11, 0, 0, tzinfo=UTC)
ISSUER = "https://idp.example/realms/inv"
TENANT = None  # set per test from the fixture


class BoundResolver:
    """Stands in for the authoritative registries a later card builds (§0-1.2, §0-1.4)."""

    bound = True

    def __init__(self, acceptance_id_ref: str = "AC-12") -> None:
        self.calls: list[tuple[str, int, int]] = []
        self.refuse_after = None
        self.acceptance_id_ref = acceptance_id_ref

    def resolve(self, session, *, tenant_id, release_id, target_refs, measurement_refs):
        self.calls.append((release_id, len(target_refs), len(measurement_refs)))
        if self.refuse_after is not None and len(self.calls) > self.refuse_after:
            raise service.ReferencesUnresolvable("the evidence is no longer resolvable")
        return SimpleNamespace(acceptance_id_ref=self.acceptance_id_ref)


def _fresh(now: dt.datetime) -> dict:
    """The verified fresh-auth fields a principal carries (#286: one representation)."""
    return {
        "verified_fresh_auth_claims": True,
        "auth_time": int(now.timestamp()) - 30,
        "amr": frozenset({"mfa"}),
        "verified_token_issuer": ISSUER,
        "verified_token_client_id": "portal",
        "verified_token_expires_at": int(now.timestamp()) + 900,
    }


@pytest.fixture
def operators(owner_engine, app_engine, clean_tables):
    """A tenant, a release, and three operators who all hold ``releases.accept``."""
    import uuid as _uuid

    ids = {
        "tenant": _uuid.uuid4(),
        "one": new_id("user"),
        "two": new_id("user"),
        "three": new_id("user"),
    }
    with owner_engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO tenants (tenant_id, slug, display_name, created_at, version) "
                "VALUES (:t, :slug, 'Acceptance', now(), 1)"
            ),
            {"t": ids["tenant"], "slug": f"acc-{str(ids['tenant'])[:8]}"},
        )
        for key in ("one", "two", "three"):
            c.execute(
                text(
                    "INSERT INTO users (user_id, tenant_id, external_subject, display_name, "
                    "status, created_at, updated_at, version) "
                    "VALUES (:u, :t, :s, 'Operator', 'active', now(), now(), 1)"
                ),
                {"u": ids[key], "t": ids["tenant"], "s": f"oidc:{key}"},
            )
            c.execute(
                text(
                    "INSERT INTO inv.business_admin_grants(tenant_id,user_id,permission,enabled) "
                    "VALUES(:t,:u,'releases.accept',true)"
                ),
                {"t": ids["tenant"], "u": ids[key]},
            )
    return ids


def _release(owner_engine, *, tenant, user) -> tuple[str, str]:
    """A release with the policy pin the projection and the proposal digest bind to."""
    release_id = new_id("release")
    manifest = "a1" * 32
    version, digest = (
        policy.load(pinned_sha256=policy.digest_of()).policy_version,
        policy.digest_of(),
    )
    with owner_engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO release_manifests(release_id,tenant_id,version,component_count,"
                "manifest_sha256,components,created_by_user_id,created_at,policy_version,"
                "policy_registry_sha256) VALUES(:r,:t,'R4',1,:m,cast(:c AS jsonb),:u,now(),"
                ":pv,:pd)"
            ),
            {
                "r": release_id,
                "t": tenant,
                "m": manifest,
                "c": json.dumps([{"name": "cp", "kind": "service", "digest": "b" * 64}]),
                "u": user,
                "pv": version,
                "pd": digest,
            },
        )
    return release_id, manifest


def _client(app_engine, monkeypatch, *, operators, who="one", now=NOW, resolver=None):
    return _client_with(
        app_engine, monkeypatch, operators=operators, who=who, now=now,
        resolver=resolver, fields=_fresh(now),
    )


def _client_with(app_engine, monkeypatch, *, operators, who="one", now=NOW, resolver=None,
                 fields=None):
    """A client whose principal carries exactly these verified fields.

    Separate from ``_client`` so a test can withhold one of them: #286's decision makes
    the token provenance part of the proof, and "what happens when it is missing" is a
    question about this boundary rather than about a malformed fixture.
    """
    principal = Principal(
        user_id=operators[who],
        tenant_id=operators["tenant"],
        external_subject=f"oidc:{who}",
        **(fields if fields is not None else _fresh(now)),
    )
    monkeypatch.setattr(service, "active_resolver", lambda: resolver or BoundResolver())
    app = create_app(
        engine=app_engine,
        settings=Settings(database_url="test-only", release_acceptance_write_enabled=True),
        verifier=StaticPrincipalVerifier({"token": principal}, allow_outside_dev=True),
        clock=lambda: now,
        check_partitions_on_startup=False,
    )
    return TestClient(app, raise_server_exceptions=False)


def _decision_body(manifest: str) -> dict:
    return {
        "acceptanceIdRef": "AC-12",
        "outcome": "accepted",
        "targetManifestSha256": manifest,
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


def _headers(key: str) -> dict:
    return {
        "Authorization": "Bearer token",
        "Content-Type": "application/json",
        "Idempotency-Key": key,
    }


def _count(owner_engine, sql: str, **params) -> int:
    with owner_engine.begin() as c:
        return c.execute(text(sql), params).scalar_one()


# --------------------------------------------------------------------------- convergence


def test_the_same_decision_under_a_second_key_converges_on_the_first_proposal(
    app_engine, owner_engine, operators, monkeypatch
):
    release_id, manifest = _release(owner_engine, tenant=operators["tenant"], user=operators["one"])
    client = _client(app_engine, monkeypatch, operators=operators)
    path = f"/v1/release-manifests/{release_id}/acceptance-decisions"
    body = json.dumps(_decision_body(manifest))

    first = client.post(path, headers=_headers("key-one"), content=body)
    second = client.post(path, headers=_headers("key-two"), content=body)

    assert first.status_code == 202, first.text
    assert first.json()["replayed"] is False
    assert second.status_code == 202, second.text
    assert second.json()["replayed"] is True
    assert second.json()["proposalId"] == first.json()["proposalId"]
    # One of each: the second key produced a receipt, not a second decision.
    assert (
        _count(
            owner_engine,
            "SELECT count(*) FROM release_acceptance_proposals " "WHERE tenant_id=:t",
            t=operators["tenant"],
        )
        == 1
    )
    assert (
        _count(
            owner_engine,
            "SELECT count(*) FROM release_acceptance_votes " "WHERE tenant_id=:t",
            t=operators["tenant"],
        )
        == 1
    )
    assert (
        _count(
            owner_engine,
            "SELECT count(*) FROM audit_events WHERE tenant_id=:t "
            "AND action='release.acceptance.proposed'",
            t=operators["tenant"],
        )
        == 1
    )


def test_a_different_decision_under_a_second_key_is_a_conflict(
    app_engine, owner_engine, operators, monkeypatch
):
    """Convergence is for the same decision. A different one is the 409 §4 asks for."""
    release_id, manifest = _release(owner_engine, tenant=operators["tenant"], user=operators["one"])
    client = _client(app_engine, monkeypatch, operators=operators)
    path = f"/v1/release-manifests/{release_id}/acceptance-decisions"

    assert (
        client.post(
            path, headers=_headers("key-one"), content=json.dumps(_decision_body(manifest))
        ).status_code
        == 202
    )
    other = _decision_body(manifest)
    other["reasonCode"] = "SECURITY_REVIEW"
    clash = client.post(path, headers=_headers("key-two"), content=json.dumps(other))
    assert clash.status_code == 409
    assert clash.json()["code"] == "GRAPH-0003"


def test_the_losing_confirmation_converges_on_the_recorded_decision(
    app_engine, owner_engine, operators, monkeypatch
):
    """Two confirmations, one decision, two votes, one confirm audit row."""
    release_id, manifest = _release(owner_engine, tenant=operators["tenant"], user=operators["one"])
    proposer = _client(app_engine, monkeypatch, operators=operators, who="one")
    path = f"/v1/release-manifests/{release_id}/acceptance-decisions"
    opened = proposer.post(
        path, headers=_headers("open"), content=json.dumps(_decision_body(manifest))
    )
    assert opened.status_code == 202, opened.text
    proposal = opened.json()

    confirmer = _client(app_engine, monkeypatch, operators=operators, who="two")
    confirm_path = f"{path}/{proposal['proposalId']}/confirm"
    payload = json.dumps(
        {"proposalDigest": proposal["proposalDigest"], "targetManifestSha256": manifest}
    )
    won = confirmer.post(confirm_path, headers=_headers("confirm-one"), content=payload)
    assert won.status_code == 201, won.text
    assert won.json()["decisionSignOff"] is True

    third = _client(app_engine, monkeypatch, operators=operators, who="three")
    lost = third.post(confirm_path, headers=_headers("confirm-two"), content=payload)
    assert lost.status_code == 201, lost.text
    assert lost.json()["replayed"] is True
    assert lost.json()["acceptanceId"] == won.json()["acceptanceId"]
    assert (
        _count(
            owner_engine,
            "SELECT count(*) FROM release_acceptance_votes " "WHERE tenant_id=:t",
            t=operators["tenant"],
        )
        == 2
    )
    assert (
        _count(
            owner_engine,
            "SELECT count(*) FROM acceptance_records WHERE tenant_id=:t",
            t=operators["tenant"],
        )
        == 1
    )
    assert (
        _count(
            owner_engine,
            "SELECT count(*) FROM audit_events WHERE tenant_id=:t "
            "AND action='release.acceptance.confirmed'",
            t=operators["tenant"],
        )
        == 1
    )


# ----------------------------------------------------------------- the invalidation commit


def test_an_expired_proposal_keeps_its_closing_and_returns_the_same_409_to_any_key(
    app_engine, owner_engine, operators, monkeypatch
):
    """The P0-3 contract, end to end: committed, then refused, then identical.

    Raising rolled the lifecycle row, the cleared slot, the audit row and the receipt back
    and told the caller about a state the database never reached.
    """
    release_id, manifest = _release(owner_engine, tenant=operators["tenant"], user=operators["one"])
    proposer = _client(app_engine, monkeypatch, operators=operators, who="one")
    path = f"/v1/release-manifests/{release_id}/acceptance-decisions"
    proposal = proposer.post(
        path, headers=_headers("open"), content=json.dumps(_decision_body(manifest))
    ).json()

    later = NOW + dt.timedelta(minutes=30)
    confirmer = _client(app_engine, monkeypatch, operators=operators, who="two", now=later)
    confirm_path = f"{path}/{proposal['proposalId']}/confirm"
    payload = json.dumps(
        {"proposalDigest": proposal["proposalDigest"], "targetManifestSha256": manifest}
    )

    refused = confirmer.post(confirm_path, headers=_headers("confirm-one"), content=payload)
    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "GRAPH-0003"
    assert refused.headers["content-type"].startswith("application/problem+json")

    # The closing survived the response.
    assert (
        _count(
            owner_engine,
            "SELECT count(*) FROM release_acceptance_lifecycle_events " "WHERE tenant_id=:t",
            t=operators["tenant"],
        )
        == 1
    )
    assert (
        _count(
            owner_engine,
            "SELECT count(*) FROM release_acceptance_slots "
            "WHERE tenant_id=:t AND active_proposal_id IS NULL",
            t=operators["tenant"],
        )
        == 1
    )
    assert (
        _count(
            owner_engine,
            "SELECT count(*) FROM acceptance_records WHERE tenant_id=:t",
            t=operators["tenant"],
        )
        == 0
    )

    # The same key replays the receipt; a different key re-reads the closed state.
    replay = confirmer.post(confirm_path, headers=_headers("confirm-one"), content=payload)
    assert replay.status_code == 409
    assert replay.json()["code"] == refused.json()["code"]
    again = confirmer.post(confirm_path, headers=_headers("confirm-three"), content=payload)
    assert again.status_code == 409
    assert again.json()["code"] == "GRAPH-0003"
    # Still one closing, not three.
    assert (
        _count(
            owner_engine,
            "SELECT count(*) FROM release_acceptance_lifecycle_events " "WHERE tenant_id=:t",
            t=operators["tenant"],
        )
        == 1
    )


# ----------------------------------------------------------------- the resolver at confirm


def test_a_resolver_cannot_authorize_a_different_acceptance_criterion(
    app_engine, owner_engine, operators, monkeypatch
):
    release_id, manifest = _release(owner_engine, tenant=operators["tenant"], user=operators["one"])
    path = f"/v1/release-manifests/{release_id}/acceptance-decisions"
    mismatched = _client(
        app_engine,
        monkeypatch,
        operators=operators,
        who="one",
        resolver=BoundResolver("AC-13"),
    ).post(path, headers=_headers("wrong-criterion"), content=json.dumps(_decision_body(manifest)))
    assert mismatched.status_code == 409, mismatched.text
    assert (
        _count(
            owner_engine,
            "SELECT count(*) FROM release_acceptance_proposals WHERE tenant_id=:t",
            t=operators["tenant"],
        )
        == 0
    )


def test_confirmation_rebinds_to_the_proposal_criterion(
    app_engine, owner_engine, operators, monkeypatch
):
    release_id, manifest = _release(owner_engine, tenant=operators["tenant"], user=operators["one"])
    path = f"/v1/release-manifests/{release_id}/acceptance-decisions"
    proposal = (
        _client(app_engine, monkeypatch, operators=operators, who="one", resolver=BoundResolver())
        .post(path, headers=_headers("open"), content=json.dumps(_decision_body(manifest)))
        .json()
    )

    refused = _client(
        app_engine,
        monkeypatch,
        operators=operators,
        who="two",
        resolver=BoundResolver("AC-13"),
    ).post(
        f"{path}/{proposal['proposalId']}/confirm",
        headers=_headers("confirm-wrong-criterion"),
        content=json.dumps(
            {"proposalDigest": proposal["proposalDigest"], "targetManifestSha256": manifest}
        ),
    )
    assert refused.status_code == 409, refused.text
    assert (
        _count(
            owner_engine,
            "SELECT count(*) FROM acceptance_records WHERE tenant_id=:t",
            t=operators["tenant"],
        )
        == 0
    )


def test_a_reference_that_stops_resolving_refuses_the_confirmation(
    app_engine, owner_engine, operators, monkeypatch
):
    """The mutation Codex kept alive, now fatal.

    The proposal resolved when it was made. By the time the second operator confirms, the
    Evidence does not resolve any more -- which is the whole reason §4 step 6 re-binds
    references at confirm time rather than trusting the earlier call.
    """
    release_id, manifest = _release(owner_engine, tenant=operators["tenant"], user=operators["one"])
    resolver = BoundResolver()
    proposer = _client(app_engine, monkeypatch, operators=operators, who="one", resolver=resolver)
    path = f"/v1/release-manifests/{release_id}/acceptance-decisions"
    proposal = proposer.post(
        path, headers=_headers("open"), content=json.dumps(_decision_body(manifest))
    ).json()
    assert len(resolver.calls) == 1, "the decision path resolves once"

    resolver.refuse_after = 1
    confirmer = _client(app_engine, monkeypatch, operators=operators, who="two", resolver=resolver)
    refused = confirmer.post(
        f"{path}/{proposal['proposalId']}/confirm",
        headers=_headers("confirm-one"),
        content=json.dumps(
            {"proposalDigest": proposal["proposalDigest"], "targetManifestSha256": manifest}
        ),
    )
    assert refused.status_code == 409, refused.text
    assert len(resolver.calls) == 2, "confirm must resolve again"
    assert (
        _count(
            owner_engine,
            "SELECT count(*) FROM acceptance_records WHERE tenant_id=:t",
            t=operators["tenant"],
        )
        == 0
    )


def test_a_revoked_grant_between_proposal_and_confirmation_refuses(
    app_engine, owner_engine, operators, monkeypatch
):
    """The live permission, re-read immediately before the write (§4 step 8)."""
    release_id, manifest = _release(owner_engine, tenant=operators["tenant"], user=operators["one"])
    proposer = _client(app_engine, monkeypatch, operators=operators, who="one")
    path = f"/v1/release-manifests/{release_id}/acceptance-decisions"
    proposal = proposer.post(
        path, headers=_headers("open"), content=json.dumps(_decision_body(manifest))
    ).json()

    with owner_engine.begin() as c:
        c.execute(
            text(
                "UPDATE inv.business_admin_grants SET enabled=false "
                "WHERE tenant_id=:t AND user_id=:u AND permission='releases.accept'"
            ),
            {"t": operators["tenant"], "u": operators["two"]},
        )
    confirmer = _client(app_engine, monkeypatch, operators=operators, who="two")
    refused = confirmer.post(
        f"{path}/{proposal['proposalId']}/confirm",
        headers=_headers("confirm-one"),
        content=json.dumps(
            {"proposalDigest": proposal["proposalDigest"], "targetManifestSha256": manifest}
        ),
    )
    assert refused.status_code == 403, refused.text
    assert (
        _count(
            owner_engine,
            "SELECT count(*) FROM acceptance_records WHERE tenant_id=:t",
            t=operators["tenant"],
        )
        == 0
    )


# ----------------------------------------------------------------- the denial audit


def test_a_refused_state_transition_is_audited_once_with_the_action_the_contract_names(
    app_engine, owner_engine, operators, monkeypatch
):
    """§8's sixth action, written by the single audit point rather than by the route.

    The shared handler is the only place a denial is recorded -- a route is inside a
    transaction the refusal rolls back. So the route names the action and the handler uses
    it, which is how there is exactly one row and it is not the generic template action.
    """
    release_id, manifest = _release(owner_engine, tenant=operators["tenant"], user=operators["one"])
    proposer = _client(app_engine, monkeypatch, operators=operators, who="one")
    path = f"/v1/release-manifests/{release_id}/acceptance-decisions"
    proposal = proposer.post(
        path, headers=_headers("open"), content=json.dumps(_decision_body(manifest))
    ).json()

    confirmer = _client(app_engine, monkeypatch, operators=operators, who="two")
    wrong = confirmer.post(
        f"{path}/{proposal['proposalId']}/confirm",
        headers=_headers("confirm-one"),
        content=json.dumps({"proposalDigest": "9" * 64, "targetManifestSha256": manifest}),
    )
    assert wrong.status_code == 409, wrong.text
    rows = _count(
        owner_engine,
        "SELECT count(*) FROM audit_events WHERE tenant_id=:t AND action=:a AND outcome='deny'",
        t=operators["tenant"],
        a=service.AUDIT_DENIED,
    )
    assert rows == 1, "exactly one denial row, with the contract's action"
    generic = _count(
        owner_engine,
        "SELECT count(*) FROM audit_events WHERE tenant_id=:t AND outcome='deny' "
        "AND action <> :a",
        t=operators["tenant"],
        a=service.AUDIT_DENIED,
    )
    assert generic == 0, "and no second row under the generic template action"


def test_a_second_final_decision_on_one_criterion_is_refused(
    app_engine, owner_engine, operators, monkeypatch
):
    """``_record_final`` used to overwrite the slot, and no test went through the route.

    The database refuses the slot move (0057's trigger, covered in the invariant suite),
    but a mutation that removed the service's own guard still passed everything -- because
    nothing drove the service into this state over HTTP. A release's sign-off could change
    by pointing the criterion at a different decision, with no withdrawal recorded.
    """
    release_id, manifest = _release(owner_engine, tenant=operators["tenant"], user=operators["one"])
    client = _client(app_engine, monkeypatch, operators=operators, who="one")
    path = f"/v1/release-manifests/{release_id}/acceptance-decisions"
    hedged = _decision_body(manifest)
    hedged["outcome"] = "conditional"
    hedged["knownLimitations"] = ["browser acceptance not observed"]

    first = client.post(path, headers=_headers("record-one"), content=json.dumps(hedged))
    assert first.status_code == 201, first.text
    assert first.json()["decisionSignOff"] is False

    second = client.post(path, headers=_headers("record-two"), content=json.dumps(hedged))
    assert second.status_code == 409, second.text
    assert second.json()["code"] == "GRAPH-0003"
    assert (
        _count(
            owner_engine,
            "SELECT count(*) FROM acceptance_records WHERE tenant_id=:t",
            t=operators["tenant"],
        )
        == 1
    )
    # The slot still names the first decision.
    with owner_engine.begin() as c:
        active = c.execute(
            text(
                "SELECT active_acceptance_id FROM release_acceptance_slots "
                "WHERE tenant_id=:t AND release_id=:r"
            ),
            {"t": operators["tenant"], "r": release_id},
        ).scalar_one()
    assert active == first.json()["acceptanceId"]


def test_the_committed_409_is_audited_once_however_many_times_it_is_asked(
    app_engine, owner_engine, operators, monkeypatch
):
    """§8's sixth action for the refusal that *commits* (#286 r2 finding 1, r3).

    Returning the 409 as a response instead of raising skipped the shared handler, so the
    closing left a ``proposal_invalidated`` row and **no** ``denied`` one -- Codex probed
    exactly that. r2 answered it inside the route, which broke the repository's invariant
    that no route records a denial (``tests/core/test_canonical_denial_audit.py``). It is
    now written by ``_close_proposal``, in the transaction that closes the proposal and
    beside the lifecycle event -- so the two rows below are one commit, and the count
    cannot drift from the number of closings.

    A replay returns the stored receipt and another key re-reads an already-closed
    proposal; neither reaches the closing, so neither adds a row. The audit stays a count
    of refusals rather than of retries, and nothing has to remember who transitioned.
    """
    release_id, manifest = _release(owner_engine, tenant=operators["tenant"], user=operators["one"])
    proposer = _client(app_engine, monkeypatch, operators=operators, who="one")
    path = f"/v1/release-manifests/{release_id}/acceptance-decisions"
    proposal = proposer.post(
        path, headers=_headers("open"), content=json.dumps(_decision_body(manifest))
    ).json()

    later = NOW + dt.timedelta(minutes=30)
    confirmer = _client(app_engine, monkeypatch, operators=operators, who="two", now=later)
    confirm_path = f"{path}/{proposal['proposalId']}/confirm"
    payload = json.dumps(
        {"proposalDigest": proposal["proposalDigest"], "targetManifestSha256": manifest}
    )

    first = confirmer.post(confirm_path, headers=_headers("confirm-one"), content=payload)
    assert first.status_code == 409, first.text

    def denials() -> int:
        return _count(
            owner_engine,
            "SELECT count(*) FROM audit_events WHERE tenant_id=:t AND action=:a "
            "AND outcome='deny'",
            t=operators["tenant"], a=service.AUDIT_DENIED,
        )

    assert denials() == 1, "the request that closed the proposal is audited"
    assert _count(
        owner_engine,
        "SELECT count(*) FROM audit_events WHERE tenant_id=:t AND action=:a",
        t=operators["tenant"], a=service.AUDIT_INVALIDATED,
    ) == 1, "and the invalidation row is still there, in the same commit"

    replay = confirmer.post(confirm_path, headers=_headers("confirm-one"), content=payload)
    assert replay.status_code == 409
    assert denials() == 1, "a replay of the receipt denies nothing new"

    other_key = confirmer.post(confirm_path, headers=_headers("confirm-two"), content=payload)
    assert other_key.status_code == 409
    assert denials() == 1, "and neither does another key re-reading a closed proposal"
    assert _count(
        owner_engine,
        "SELECT count(*) FROM release_acceptance_lifecycle_events WHERE tenant_id=:t",
        t=operators["tenant"],
    ) == 1

    # The row itself: the closed action, the ``deny`` outcome the column's set allows, the
    # code the caller was actually given, and the confirmer as the actor -- an out-of-band
    # recorder had to rebuild that actor from request state.
    with owner_engine.begin() as connection:
        row = connection.execute(
            text(
                "SELECT actor_type, actor_id, outcome, detail->>'refusedCode' AS code, "
                "detail->>'closedReason' AS reason FROM audit_events "
                "WHERE tenant_id=:t AND action=:a"
            ),
            {"t": operators["tenant"], "a": service.AUDIT_DENIED},
        ).one()
    assert row.outcome == "deny" and row.code == "GRAPH-0003"
    assert row.actor_type == "user" and row.actor_id == operators["two"]
    assert row.reason == "expired"


# ------------------------------------------------------------------ the whole chain, once


def _oidc_chain(app_engine, owner_engine, operators, tmp_path):
    """A real signed token, a real subject mapping, a real verifier.

    The point of going through all three is that the defect #286 closed lived *between*
    them: ``AccessTokens.verify`` normalised one set of claims and a second reader in the
    business layer judged them again. A test that calls the predicate directly cannot see
    that, and a test that stubs the verifier proves the stub.
    """
    from inv.identity import public_subject
    from saintvision.db.session import make_session_factory
    from saintvision.identity.oidc import OidcPrincipalVerifier
    from jwt_support import jwt_fixture

    tokens = jwt_fixture(tmp_path, str(operators["tenant"]))
    subject = public_subject(tokens.issuer, "operator-two")
    with owner_engine.begin() as connection:
        connection.execute(
            text("UPDATE users SET external_subject=:s WHERE tenant_id=:t AND user_id=:u"),
            {"s": subject, "t": operators["tenant"], "u": operators["two"]},
        )
    verifier = OidcPrincipalVerifier(tokens.auth, make_session_factory(app_engine))
    return tokens, verifier


#: Exactly the combinations the canonical allowlist admits (#285), and the age boundary.
FRESH_ALLOWED = (
    ("mfa",),
    ("pwd", "otp"),
    ("pwd", "hwk"),
    ("pwd", "swk"),
)


@pytest.mark.parametrize("amr", FRESH_ALLOWED)
@pytest.mark.parametrize("age", [0, 300])
def test_the_whole_chain_admits_the_canonical_combinations(
    app_engine, owner_engine, operators, tmp_path, amr, age
):
    tokens, verifier = _oidc_chain(app_engine, owner_engine, operators, tmp_path)
    # Minted against the real clock on purpose: ``AccessTokens.verify`` checks ``exp`` for
    # real, so a token stamped with this module's frozen NOW is simply expired. The policy
    # clock is then derived from the token rather than the other way round.
    issued = int(time.time())
    now = dt.datetime.fromtimestamp(issued, tz=UTC)
    token = tokens.token(
        "operator-two",
        claims={"auth_time": issued - age, "amr": list(amr), "exp": issued + 600,
                "iat": issued},
    )
    principal = verifier.verify(token)
    assert principal.verified_fresh_auth_claims is True
    assert principal.verified_token_issuer == tokens.issuer
    assert principal.verified_token_client_id == "synthetic-web"
    assert principal.verified_token_expires_at == issued + 600

    sessionmaker = make_session_factory(app_engine)
    with sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, operators["tenant"]):
                proof = service.require_fresh_operator(
                    session, principal=principal, now=now
                )
    assert proof.auth_time == issued - age
    assert proof.issuer == tokens.issuer and proof.client_id == "synthetic-web"
    assert proof.amr_sha256 == fresh_auth.amr_digest(frozenset(amr))


@pytest.mark.parametrize(
    ("label", "claims"),
    [
        ("no claims at all", {}),
        ("auth_time is a bool", {"auth_time": True, "amr": ["mfa"]}),
        ("auth_time is a string", {"auth_time": "1790000000", "amr": ["mfa"]}),
        ("auth_time is a float", {"auth_time": 1790000000.0, "amr": ["mfa"]}),
        ("auth_time is negative", {"auth_time": -1, "amr": ["mfa"]}),
        ("auth_time is in the future", {"auth_time": "FUTURE", "amr": ["mfa"]}),
        ("301 seconds old", {"auth_time": "STALE", "amr": ["mfa"]}),
        ("no method at all", {"auth_time": "NOW", "amr": []}),
        ("a password alone", {"auth_time": "NOW", "amr": ["pwd"]}),
        ("a one-time code alone", {"auth_time": "NOW", "amr": ["otp"]}),
        ("an unregistered method", {"auth_time": "NOW", "amr": ["webauthn"]}),
        # The one that matters most: this combination passed an independent RFC 8176
        # check while the canonical allowlist refused it. With one policy it is refused
        # once, here, and there is no second answer for it to disagree with.
        ("mfa with an out-of-allowlist factor", {"auth_time": "NOW", "amr": ["mfa", "sms"]}),
    ],
)
def test_the_whole_chain_refuses_everything_else(
    app_engine, owner_engine, operators, tmp_path, label, claims
):
    tokens, verifier = _oidc_chain(app_engine, owner_engine, operators, tmp_path)
    issued = int(time.time())
    now = dt.datetime.fromtimestamp(issued, tz=UTC)
    resolved = dict(claims)
    substitutions = {"NOW": issued, "FUTURE": issued + 1, "STALE": issued - 301}
    if resolved.get("auth_time") in substitutions:
        resolved["auth_time"] = substitutions[resolved["auth_time"]]
    token = tokens.token(
        "operator-two", claims={**resolved, "exp": issued + 600, "iat": issued}
    )
    principal = verifier.verify(token)

    sessionmaker = make_session_factory(app_engine)
    with sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, operators["tenant"]):
                with pytest.raises(InvError) as refused:
                    service.require_fresh_operator(session, principal=principal, now=now)
    assert refused.value.code == AUTH_PROJECT_SCOPE, label


@pytest.mark.parametrize("missing", ["issuer", "client_id", "expires_at"])
def test_token_provenance_is_fail_closed_and_writes_nothing(
    app_engine, owner_engine, operators, monkeypatch, missing
):
    """§2-1's receipt facts are verified metadata, not optional decoration.

    A principal that is fresh by the canonical predicate but carries no verified issuer,
    client or expiry is refused -- and the refusal is the same ``AUTH-0030``/403 as a
    missing permission, with no proposal, no vote and no audit row behind it.
    """
    fields = dict(_fresh(NOW))
    fields[f"verified_token_{missing}"] = None
    release_id, manifest = _release(
        owner_engine, tenant=operators["tenant"], user=operators["one"]
    )
    client = _client_with(app_engine, monkeypatch, operators=operators, who="one",
                          fields=fields)
    response = client.post(
        f"/v1/release-manifests/{release_id}/acceptance-decisions",
        headers=_headers("provenance"),
        content=json.dumps(_decision_body(manifest)),
    )
    assert response.status_code == 403, response.text
    assert response.json()["code"] == "AUTH-0030"
    for table in ("release_acceptance_proposals", "release_acceptance_votes",
                  "acceptance_records"):
        assert _count(
            owner_engine, f"SELECT count(*) FROM {table} WHERE tenant_id=:t",
            t=operators["tenant"],
        ) == 0, table
    # The refusal itself IS audited -- §8 asks for exactly that, and the canonical
    # boundary records it. What must be absent is any audit of a write that did not
    # happen.
    assert _count(
        owner_engine,
        "SELECT count(*) FROM audit_events WHERE tenant_id=:t AND action=:a",
        t=operators["tenant"], a=service.AUDIT_DENIED,
    ) == 1
    for action in (service.AUDIT_PROPOSED, service.AUDIT_RECORDED, service.AUDIT_CONFIRMED,
                   service.AUDIT_WITHDRAWN, service.AUDIT_INVALIDATED):
        assert _count(
            owner_engine,
            "SELECT count(*) FROM audit_events WHERE tenant_id=:t AND action=:a",
            t=operators["tenant"], a=action,
        ) == 0, action


def test_an_expired_verified_token_cannot_cast_a_vote(app_engine, owner_engine, operators,
                                                      monkeypatch):
    """The window a receipt records would already be over."""
    fields = dict(_fresh(NOW))
    fields["verified_token_expires_at"] = int(NOW.timestamp()) - 1
    release_id, manifest = _release(
        owner_engine, tenant=operators["tenant"], user=operators["one"]
    )
    client = _client_with(app_engine, monkeypatch, operators=operators, who="one",
                          fields=fields)
    response = client.post(
        f"/v1/release-manifests/{release_id}/acceptance-decisions",
        headers=_headers("expired"),
        content=json.dumps(_decision_body(manifest)),
    )
    assert response.status_code == 403, response.text
    assert response.json()["code"] == "AUTH-0030"


def test_a_hand_built_principal_cannot_claim_fresh_authentication(app_engine, owner_engine,
                                                                 operators, monkeypatch):
    """Filling the fields is not the same as having been verified.

    ``verified_fresh_auth_claims`` is set by ``OidcPrincipalVerifier`` and by nothing
    else, so a development verifier that fills ``auth_time`` and ``amr`` is still refused.
    """
    fields = dict(_fresh(NOW))
    fields["verified_fresh_auth_claims"] = False
    release_id, manifest = _release(
        owner_engine, tenant=operators["tenant"], user=operators["one"]
    )
    client = _client_with(app_engine, monkeypatch, operators=operators, who="one",
                          fields=fields)
    response = client.post(
        f"/v1/release-manifests/{release_id}/acceptance-decisions",
        headers=_headers("hand-built"),
        content=json.dumps(_decision_body(manifest)),
    )
    assert response.status_code == 403, response.text
    assert response.json()["code"] == "AUTH-0030"


def test_the_whole_chain_refuses_mfa_plus_sms_at_the_canonical_policy(
    app_engine, owner_engine, operators, tmp_path
):
    """#286 F1: observed, not inferred — the claim arrives verified and the policy refuses.

    ``mfa+sms`` is the combination where two allowlists disagreed. The refusal has to come
    from ``has_fresh_interactive_auth``, so this asserts the principal *carried* both
    methods with ``verified_fresh_auth_claims`` set — meaning the verifier passed them on —
    and only then that the write boundary refused.
    """
    tokens, verifier = _oidc_chain(app_engine, owner_engine, operators, tmp_path)
    issued = int(time.time())
    now = dt.datetime.fromtimestamp(issued, tz=UTC)
    token = tokens.token(
        "operator-two",
        claims={"auth_time": issued, "amr": ["mfa", "sms"], "exp": issued + 600,
                "iat": issued},
    )
    principal = verifier.verify(token)
    assert principal.verified_fresh_auth_claims is True
    assert principal.amr == frozenset({"mfa", "sms"}), "the verifier did not filter it"

    from saintvision.identity.principal import has_fresh_interactive_auth
    assert not has_fresh_interactive_auth(principal, now=now)

    sessionmaker = make_session_factory(app_engine)
    with sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, operators["tenant"]):
                with pytest.raises(InvError) as refused:
                    service.require_fresh_operator(session, principal=principal, now=now)
    assert refused.value.code == AUTH_PROJECT_SCOPE
