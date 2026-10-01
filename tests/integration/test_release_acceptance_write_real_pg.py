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

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from saintvision.api.app import create_app
from saintvision.config import Settings
from saintvision.identity.principal import FreshAuth, Principal, StaticPrincipalVerifier
from saintvision.ids import new_id
from saintvision.services import release_acceptance as service
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


def _fresh(now: dt.datetime) -> FreshAuth:
    return FreshAuth(
        auth_time=int(now.timestamp()) - 30,
        amr=frozenset({"mfa"}),
        issuer=ISSUER,
        client_id="portal",
        expires_at=int(now.timestamp()) + 900,
    )


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
    principal = Principal(
        user_id=operators[who],
        tenant_id=operators["tenant"],
        external_subject=f"oidc:{who}",
        fresh_auth=_fresh(now),
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
