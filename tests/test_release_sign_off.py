"""The one sign-off projection, against a real PostgreSQL (#282 §5).

Two things are being established here, and the second is the one that matters today.

The first is the rule set: a release is operator-signed only when every criterion the
pinned registry requires has an *active* accepted decision, admitted by two distinct
attested operators, not withdrawn, pinning the composition the release currently has,
with its references resolvable. Each clause gets a test that removes exactly that
clause and watches the answer go false.

The second is honesty about the present. ``AUTHORITATIVE_REFS_BOUND`` is false in this
build -- there is no target registry and no canonical Evidence digest -- so the real
answer is false for every release that exists. The read surface says the same thing
with ``Literal[False]`` and ``Literal[0]``, and
``test_the_pinned_contract_literals_agree_with_the_projection`` is what makes that a
checked agreement rather than two places hoping to match. The satisfied path is still
tested, by passing ``refs_bound=True``: that is testing the rule, not claiming the
deployment has the registries.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from pathlib import Path

import pytest
from sqlalchemy import text

from saintvision.db.session import tenant_scope
from saintvision.ids import new_id
from saintvision.services import release_acceptance_policy as policy
from saintvision.services import release_sign_off
from saintvision.services import pilot as pilot_service

pytestmark = pytest.mark.postgres

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 10, 1, 11, 0, 0, tzinfo=UTC)
REGISTRY = Path(__file__).resolve().parents[1] / "contracts" / "release-acceptance-policy-registry-v1.json"


def registry_pin() -> tuple[int, str]:
    loaded = policy.load(pinned_sha256=hashlib.sha256(REGISTRY.read_bytes()).hexdigest())
    assert loaded.usable, loaded.refused
    return loaded.policy_version, loaded.registry_sha256


@pytest.fixture
def people(owner_engine, two_tenants):
    """Two operators and a tenant. Both exist as users; nothing here attests them."""
    tenant_a, tenant_b = two_tenants
    ids = {"tenant_a": tenant_a, "tenant_b": tenant_b, "one": new_id("user"), "two": new_id("user")}
    with owner_engine.begin() as c:
        for key in ("one", "two"):
            c.execute(
                text(
                    "INSERT INTO users (user_id, tenant_id, external_subject, display_name, "
                    "status, created_at, updated_at, version) "
                    "VALUES (:u, :t, :s, 'Operator', 'active', now(), now(), 1)"
                ),
                {"u": ids[key], "t": tenant_a, "s": f"oidc:{key}"},
            )
    return ids


def _components():
    return [
        pilot_service.ReleaseComponent("control-plane", "service", "a" * 64),
        pilot_service.ReleaseComponent("node-agent", "service", "b" * 64),
    ]


def make_release(session, *, tenant_id, user_id, pinned=True):
    release = pilot_service.create_release_manifest(
        session,
        tenant_id=tenant_id,
        version="R4",
        components=_components(),
        created_by_user_id=user_id,
        now=NOW,
    )
    session.flush()
    if pinned:
        version, digest = registry_pin()
        session.execute(
            text(
                "UPDATE release_manifests SET policy_version=:v, policy_registry_sha256=:d "
                "WHERE tenant_id=:t AND release_id=:r"
            ),
            {"v": version, "d": digest, "t": tenant_id, "r": release.release_id},
        )
        session.expire(release)
    return release


def accept(
    session,
    *,
    tenant_id,
    release,
    proposer,
    confirmer,
    criterion="AC-12",
    attestation=release_sign_off.HUMAN_ATTESTATION_VERSION,
    manifest_sha256=None,
    outcome="accepted",
    voters=2,
):
    """Write the rows a confirmed decision leaves behind, without the write routes.

    The routes are not enabled in this build (§0-1.5), so the projection is tested
    against rows in the shape the canonical function produces. Every column that the
    projection reads is set here explicitly, which is also why a test can remove one.
    """
    version, digest = registry_pin()
    proposal_id = new_id("acceptance_proposal")
    acceptance_id = new_id("acceptance")
    pinned = manifest_sha256 or release.manifest_sha256
    session.execute(
        text(
            "INSERT INTO release_acceptance_proposals(proposal_id,tenant_id,release_id,"
            "acceptance_id_ref,outcome,target_manifest_sha256,proposal_digest,reason_code,"
            "target_refs,measurement_refs,known_limitations,policy_version,"
            "policy_registry_sha256,proposed_by_user_id,created_at,expires_at) "
            "VALUES(:p,:t,:r,:c,'accepted',:m,:pd,'OPERATIONAL_ACCEPTANCE',"
            "cast(:tr AS jsonb),cast(:mr AS jsonb),'[]'::jsonb,:v,:d,:u,:now,:exp)"
        ),
        {
            "p": proposal_id,
            "t": tenant_id,
            "r": release.release_id,
            "c": criterion,
            "m": pinned,
            "pd": "a" * 64,
            "tr": '[{"targetId":"t.one","targetSha256":"' + "c" * 64 + '"}]',
            "mr": '[{"evidenceId":"e.one","evidenceSha256":"' + "e" * 64
            + '","observedAt":"2026-10-01T10:00:00.000000Z"}]',
            "v": version,
            "d": digest,
            "u": proposer,
            "now": NOW,
            "exp": NOW + dt.timedelta(minutes=5),
        },
    )
    for index, (user, role) in enumerate(((proposer, "proposer"), (confirmer, "confirmer"))):
        if index >= voters:
            break
        session.execute(
            text(
                "INSERT INTO release_acceptance_votes(vote_id,tenant_id,proposal_id,user_id,"
                "vote_role,human_attestation_version,verified_issuer,verified_client_id,"
                "auth_time,amr_sha256,identity_verification_event_id,created_at) "
                "VALUES(:v,:t,:p,:u,:role,:ver,'https://idp.example/realms/inv','portal',"
                ":at,:amr,:ev,:now)"
            ),
            {
                "v": new_id("acceptance_vote"),
                "t": tenant_id,
                "p": proposal_id,
                "u": user,
                "role": role,
                "ver": attestation,
                "at": 1790000000,
                "amr": "f" * 64,
                "ev": new_id("audit_event"),
                "now": NOW,
            },
        )
    session.execute(
        text(
            "INSERT INTO acceptance_records(acceptance_id,tenant_id,release_id,"
            "acceptance_id_ref,outcome,accepted_manifest_sha256,known_limitations,"
            "accepted_by_user_id,decided_at,attestation_version,proposal_id) "
            "VALUES(:a,:t,:r,:c,:o,:m,cast(:lim AS jsonb),:u,:now,:ver,:p)"
        ),
        {
            "a": acceptance_id,
            "t": tenant_id,
            "r": release.release_id,
            "c": criterion,
            "o": outcome,
            "m": pinned,
            "lim": '["browser acceptance not observed"]' if outcome == "conditional" else "[]",
            "u": confirmer,
            "now": NOW,
            "ver": attestation,
            "p": proposal_id,
        },
    )
    session.execute(
        text(
            "INSERT INTO release_acceptance_slots(slot_id,tenant_id,release_id,"
            "acceptance_id_ref,active_acceptance_id,updated_at) "
            "VALUES(:s,:t,:r,:c,:a,:now)"
        ),
        {
            "s": new_id("acceptance_slot"),
            "t": tenant_id,
            "r": release.release_id,
            "c": criterion,
            "a": acceptance_id,
            "now": NOW,
        },
    )
    session.execute(
        text(
            "INSERT INTO release_acceptance_lifecycle_events(event_id,tenant_id,proposal_id,"
            "event_kind,acceptance_id,occurred_at) VALUES(:e,:t,:p,'confirmed',:a,:now)"
        ),
        {"e": new_id("acceptance_lifecycle_event"), "t": tenant_id, "p": proposal_id,
         "a": acceptance_id, "now": NOW},
    )
    session.flush()
    return acceptance_id


def answer(session, *, tenant_id, release, refs_bound=True):
    return release_sign_off.evaluate(
        session, tenant_id=tenant_id, release=release, now=NOW, refs_bound=refs_bound
    )


# --------------------------------------------------------------------- the satisfied path


def test_two_attested_operators_on_every_required_criterion_sign_a_release_off(
    app_sessionmaker, people
):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, people["tenant_a"]):
                release = make_release(
                    session, tenant_id=people["tenant_a"], user_id=people["one"]
                )
                accept(
                    session,
                    tenant_id=people["tenant_a"],
                    release=release,
                    proposer=people["one"],
                    confirmer=people["two"],
                )
                result = answer(session, tenant_id=people["tenant_a"], release=release)
    assert result.operator_sign_off is True, result
    assert result.confirmed_operator_count == 2
    assert result.blocked_by is None
    assert [state.acceptance_id_ref for state in result.criteria] == ["AC-12"]
    assert result.policy_version == registry_pin()[0]


# --------------------------------------------------------------------- one clause removed


def test_the_unbound_reference_registries_are_why_the_answer_is_false_today(
    app_sessionmaker, people
):
    """The default, and the reason the contract's literals are not a placeholder.

    Everything else about this decision is right. It still does not count, because
    nothing can resolve its target and Evidence references -- which the contract owner
    made a separate card and explicitly refused to paper over by comparing the caller's
    own values (§0-1.2, §3-1).
    """
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, people["tenant_a"]):
                release = make_release(
                    session, tenant_id=people["tenant_a"], user_id=people["one"]
                )
                accept(
                    session,
                    tenant_id=people["tenant_a"],
                    release=release,
                    proposer=people["one"],
                    confirmer=people["two"],
                )
                result = answer(
                    session, tenant_id=people["tenant_a"], release=release, refs_bound=False
                )
    assert result.operator_sign_off is False
    assert result.confirmed_operator_count == 0
    assert result.blocked_by == "release-acceptance-prerequisites-unavailable"
    assert "references cannot be resolved" in result.criteria[0].reason


def test_the_pinned_contract_literals_agree_with_the_projection(app_sessionmaker, people):
    """``Literal[False]`` and ``Literal[0]`` are not a lie, and this is the check.

    The read contract pins both fields until the prerequisites land (§0). That is only
    honest while the projection agrees, so this runs the projection in its real
    configuration -- the module default, not an argument -- over a release that has
    everything else right, and asserts it answers exactly what the contract publishes.
    """
    from saintvision.api import schemas

    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, people["tenant_a"]):
                release = make_release(
                    session, tenant_id=people["tenant_a"], user_id=people["one"]
                )
                accept(
                    session,
                    tenant_id=people["tenant_a"],
                    release=release,
                    proposer=people["one"],
                    confirmer=people["two"],
                )
                reported = release_sign_off.evaluate_for_payload(
                    session, tenant_id=people["tenant_a"], release=release, now=NOW
                )
    fields = schemas.ReleaseManifestResponse.model_fields
    assert reported["operatorSignOff"] is False
    assert reported["confirmedOperatorCount"] == 0
    assert reported["operatorSignOffBlockedBy"] == (
        fields["operator_sign_off_blocked_by"].annotation.__args__[0]
    )
    assert fields["operator_sign_off"].annotation.__args__[0] is False
    assert fields["confirmed_operator_count"].annotation.__args__[0] == 0


def test_an_unpinned_release_is_not_signed_off(app_sessionmaker, people):
    """No pin, no policy: today's registry is not what this release was accepted under."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, people["tenant_a"]):
                release = make_release(
                    session, tenant_id=people["tenant_a"], user_id=people["one"], pinned=False
                )
                accept(
                    session,
                    tenant_id=people["tenant_a"],
                    release=release,
                    proposer=people["one"],
                    confirmer=people["two"],
                )
                result = answer(session, tenant_id=people["tenant_a"], release=release)
    assert result.operator_sign_off is False
    assert result.criteria == ()
    assert "no pinned policy registry digest" in result.reason


def test_a_criterion_with_no_active_decision_is_not_signed_off(app_sessionmaker, people):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, people["tenant_a"]):
                release = make_release(
                    session, tenant_id=people["tenant_a"], user_id=people["one"]
                )
                result = answer(session, tenant_id=people["tenant_a"], release=release)
    assert result.operator_sign_off is False
    assert "no active decision" in result.criteria[0].reason


def test_one_attested_operator_is_not_two(app_sessionmaker, people):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, people["tenant_a"]):
                release = make_release(
                    session, tenant_id=people["tenant_a"], user_id=people["one"]
                )
                accept(
                    session,
                    tenant_id=people["tenant_a"],
                    release=release,
                    proposer=people["one"],
                    confirmer=people["two"],
                    voters=1,
                )
                result = answer(session, tenant_id=people["tenant_a"], release=release)
    assert result.operator_sign_off is False
    assert "fewer than two attested operators" in result.criteria[0].reason


def test_a_legacy_decision_does_not_count(app_sessionmaker, people):
    """The rows 0005 allowed are kept and classified, and they do not sign anything off."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, people["tenant_a"]):
                release = make_release(
                    session, tenant_id=people["tenant_a"], user_id=people["one"]
                )
                accept(
                    session,
                    tenant_id=people["tenant_a"],
                    release=release,
                    proposer=people["one"],
                    confirmer=people["two"],
                    attestation="legacy-unverified",
                )
                result = answer(session, tenant_id=people["tenant_a"], release=release)
    assert result.operator_sign_off is False
    assert "no fresh human attestation" in result.criteria[0].reason


def test_a_conditional_active_decision_is_not_sign_off(app_sessionmaker, people):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, people["tenant_a"]):
                release = make_release(
                    session, tenant_id=people["tenant_a"], user_id=people["one"]
                )
                accept(
                    session,
                    tenant_id=people["tenant_a"],
                    release=release,
                    proposer=people["one"],
                    confirmer=people["two"],
                    outcome="conditional",
                )
                result = answer(session, tenant_id=people["tenant_a"], release=release)
    assert result.operator_sign_off is False
    assert "is conditional" in result.criteria[0].reason


def test_a_decision_pinning_another_composition_is_not_sign_off(app_sessionmaker, people):
    """A new composition under the same name needs a new proposal and two fresh people."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, people["tenant_a"]):
                release = make_release(
                    session, tenant_id=people["tenant_a"], user_id=people["one"]
                )
                accept(
                    session,
                    tenant_id=people["tenant_a"],
                    release=release,
                    proposer=people["one"],
                    confirmer=people["two"],
                    manifest_sha256="9" * 64,
                )
                result = answer(session, tenant_id=people["tenant_a"], release=release)
    assert result.operator_sign_off is False
    assert "different composition" in result.criteria[0].reason


def test_a_withdrawn_decision_leaves_the_criterion_unmet(app_sessionmaker, people):
    """§6: history is kept, the criterion stops being met, and nothing is edited."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, people["tenant_a"]):
                release = make_release(
                    session, tenant_id=people["tenant_a"], user_id=people["one"]
                )
                acceptance_id = accept(
                    session,
                    tenant_id=people["tenant_a"],
                    release=release,
                    proposer=people["one"],
                    confirmer=people["two"],
                )
                before = answer(session, tenant_id=people["tenant_a"], release=release)
                session.execute(
                    text(
                        "INSERT INTO release_acceptance_withdrawals(withdrawal_id,tenant_id,"
                        "release_id,acceptance_id,reason_code,accepted_manifest_sha256,"
                        "withdrawn_by_user_id,withdrawn_at) "
                        "VALUES(:w,:t,:r,:a,'security-concern',:m,:u,:now)"
                    ),
                    {
                        "w": new_id("acceptance_withdrawal"),
                        "t": people["tenant_a"],
                        "r": release.release_id,
                        "a": acceptance_id,
                        "m": release.manifest_sha256,
                        "u": people["one"],
                        "now": NOW,
                    },
                )
                session.flush()
                after = answer(session, tenant_id=people["tenant_a"], release=release)
                kept = session.execute(
                    text(
                        "SELECT count(*) FROM acceptance_records WHERE tenant_id=:t "
                        "AND acceptance_id=:a"
                    ),
                    {"t": people["tenant_a"], "a": acceptance_id},
                ).scalar_one()
    assert before.operator_sign_off is True
    assert after.operator_sign_off is False
    assert "withdrawn" in after.criteria[0].reason
    assert kept == 1, "a withdrawal must not delete the decision"


def test_another_tenants_rows_do_not_sign_this_release_off(app_sessionmaker, people):
    """RLS plus the explicit predicate: the projection reads one tenant's rows."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, people["tenant_a"]):
                release = make_release(
                    session, tenant_id=people["tenant_a"], user_id=people["one"]
                )
                accept(
                    session,
                    tenant_id=people["tenant_a"],
                    release=release,
                    proposer=people["one"],
                    confirmer=people["two"],
                )
                signed = answer(session, tenant_id=people["tenant_a"], release=release)
                # The same release object, asked as another tenant.
                crossed = answer(session, tenant_id=people["tenant_b"], release=release)
    assert signed.operator_sign_off is True
    assert crossed.operator_sign_off is False
