"""What the database refuses, whoever asks (#282 §4-1, §9 hosted list).

Everything here is deliberately tested *through the application role*, not through the
owner. The owner bypasses nothing in these tests -- FORCE ROW LEVEL SECURITY is on -- but
privileges are the point: the claim is that a bug in the service, or a future caller that
reaches these tables another way, still cannot write a second vote from one person, a
second withdrawal, or a decision with no proposal behind it.

The confirm function gets its own group, because it is the one place that inserts an
``accepted`` row and §4-1 requires it to re-derive everything the service already
checked. It takes no user ID: the acting human comes from ``inv.user_id``, which only the
request path sets, so a test that wants to be somebody must set that scope -- which is
itself worth asserting, and the first test in that group does.
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError, ProgrammingError

from saintvision.db.session import actor_scope, tenant_scope
from saintvision.ids import new_id
from saintvision.services import pilot as pilot_service

pytestmark = pytest.mark.postgres

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 10, 1, 11, 0, 0, tzinfo=UTC)
LATER = NOW + dt.timedelta(minutes=4)
AMR = "f" * 64
#: One name for the proposal digest, used by the seed and by every confirm call: two
#: literals drifted apart once and every confirm test failed on the digest comparison
#: instead of on the rule it was about.
PROPOSAL_DIGEST = "a" * 64
ISSUER = "https://idp.example/realms/inv"


@pytest.fixture
def two_operators(owner_engine, two_tenants):
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
            # The live grant the function re-reads. In schema ``inv``, which inv_app
            # cannot read at all -- only ``business_admin_allowed`` can.
            c.execute(
                text(
                    "INSERT INTO inv.business_admin_grants(tenant_id,user_id,permission,enabled) "
                    "VALUES(:t,:u,'releases.accept',true)"
                ),
                {"t": tenant_a, "u": ids[key]},
            )
    return ids


def _components():
    return [
        pilot_service.ReleaseComponent("control-plane", "service", "a" * 64),
        pilot_service.ReleaseComponent("node-agent", "service", "b" * 64),
    ]


def seed(session, *, tenant_id, user_id, criterion="AC-12", expires=LATER):
    """A release with one pending proposal and its proposer's vote."""
    release = pilot_service.create_release_manifest(
        session,
        tenant_id=tenant_id,
        version="R4",
        components=_components(),
        created_by_user_id=user_id,
        now=NOW,
    )
    session.flush()
    proposal_id = new_id("acceptance_proposal")
    session.execute(
        text(
            "INSERT INTO release_acceptance_proposals(proposal_id,tenant_id,release_id,"
            "acceptance_id_ref,outcome,target_manifest_sha256,proposal_digest,reason_code,"
            "target_refs,measurement_refs,known_limitations,policy_version,"
            "policy_registry_sha256,proposed_by_user_id,created_at,expires_at) "
            "VALUES(:p,:t,:r,:c,'accepted',:m,:pd,'OPERATIONAL_ACCEPTANCE',"
            "cast(:tr AS jsonb),cast(:mr AS jsonb),'[]'::jsonb,1,:d,:u,:now,:exp)"
        ),
        {
            "p": proposal_id,
            "t": tenant_id,
            "r": release.release_id,
            "c": criterion,
            "m": release.manifest_sha256,
            "pd": PROPOSAL_DIGEST,
            "tr": '[{"targetId":"t.one","targetSha256":"' + "c" * 64 + '"}]',
            "mr": '[{"evidenceId":"e.one","evidenceSha256":"' + "e" * 64
            + '","observedAt":"2026-10-01T10:00:00.000000Z"}]',
            "d": "b" * 64,
            "u": user_id,
            "now": NOW,
            "exp": expires,
        },
    )
    session.execute(
        text(
            "INSERT INTO release_acceptance_votes(vote_id,tenant_id,proposal_id,user_id,"
            "vote_role,human_attestation_version,verified_issuer,verified_client_id,"
            "auth_time,amr_sha256,identity_verification_event_id,created_at) "
            "VALUES(:v,:t,:p,:u,'proposer','fresh-interactive-v1',:iss,'portal',"
            ":at,:amr,:ev,:now)"
        ),
        {
            "v": new_id("acceptance_vote"),
            "t": tenant_id,
            "p": proposal_id,
            "u": user_id,
            "iss": ISSUER,
            "at": int(NOW.timestamp()) - 60,
            "amr": AMR,
            "ev": new_id("audit_event"),
            "now": NOW,
        },
    )
    session.execute(
        text(
            "INSERT INTO release_acceptance_slots(slot_id,tenant_id,release_id,"
            "acceptance_id_ref,active_proposal_id,updated_at) VALUES(:s,:t,:r,:c,:p,:now)"
        ),
        {
            "s": new_id("acceptance_slot"),
            "t": tenant_id,
            "r": release.release_id,
            "c": criterion,
            "p": proposal_id,
            "now": NOW,
        },
    )
    session.flush()
    return release, proposal_id


def confirm_call(session, *, proposal_id, proposal_digest, manifest_sha256, now=NOW):
    return session.execute(
        text(
            "SELECT public.release_acceptance_confirm("
            ":p,:pd,:md,:a,:v,:e,:i,'fresh-interactive-v1',:iss,'portal',:at,:amr,:now)"
        ),
        {
            "p": proposal_id,
            "pd": proposal_digest,
            "md": manifest_sha256,
            "a": new_id("acceptance"),
            "v": new_id("acceptance_vote"),
            "e": new_id("acceptance_lifecycle_event"),
            "i": new_id("audit_event"),
            "iss": ISSUER,
            "at": int(NOW.timestamp()) - 60,
            "amr": AMR,
            "now": now,
        },
    ).scalar_one()


# ------------------------------------------------------------------ append-only privileges


@pytest.mark.parametrize(
    "table,column",
    [
        ("release_acceptance_proposals", "reason_code"),
        ("release_acceptance_votes", "vote_role"),
        ("release_acceptance_withdrawals", "reason_code"),
        ("release_acceptance_lifecycle_events", "event_kind"),
        ("acceptance_records", "outcome"),
    ],
)
def test_the_application_role_cannot_update_a_recorded_fact(
    app_sessionmaker, two_operators, table, column
):
    """Five tables, including the one 0005 granted UPDATE on and 0057 took it back."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, two_operators["tenant_a"]):
                with pytest.raises((ProgrammingError, DBAPIError)) as refused:
                    session.execute(text(f"UPDATE {table} SET {column} = {column}"))
    assert "permission denied" in str(refused.value).lower()


@pytest.mark.parametrize(
    "table",
    [
        "release_acceptance_proposals",
        "release_acceptance_votes",
        "release_acceptance_withdrawals",
        "release_acceptance_lifecycle_events",
        "acceptance_records",
    ],
)
def test_the_application_role_cannot_delete_a_recorded_fact(
    app_sessionmaker, two_operators, table
):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, two_operators["tenant_a"]):
                with pytest.raises((ProgrammingError, DBAPIError)) as refused:
                    session.execute(text(f"DELETE FROM {table}"))
    assert "permission denied" in str(refused.value).lower()


def test_the_slot_may_only_move_its_two_state_columns(app_sessionmaker, two_operators):
    """Column-level UPDATE: the criterion a slot is for cannot be rewritten."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, two_operators["tenant_a"]):
                with pytest.raises((ProgrammingError, DBAPIError)) as refused:
                    session.execute(
                        text("UPDATE release_acceptance_slots SET acceptance_id_ref = 'AC-99'")
                    )
    assert "permission denied" in str(refused.value).lower()


# ------------------------------------------------------------------ the uniqueness rules


def test_one_person_cannot_vote_twice_on_a_proposal(app_sessionmaker, two_operators):
    """The two-person rule, in the schema. Two rows from one user is a duplicate key."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, two_operators["tenant_a"]):
                release, proposal_id = seed(
                    session, tenant_id=two_operators["tenant_a"], user_id=two_operators["one"]
                )
                with pytest.raises(IntegrityError) as refused:
                    session.execute(
                        text(
                            "INSERT INTO release_acceptance_votes(vote_id,tenant_id,proposal_id,"
                            "user_id,vote_role,human_attestation_version,verified_issuer,"
                            "verified_client_id,auth_time,amr_sha256,"
                            "identity_verification_event_id,created_at) "
                            "VALUES(:v,:t,:p,:u,'confirmer','fresh-interactive-v1',:iss,"
                            "'portal',:at,:amr,:ev,:now)"
                        ),
                        {
                            "v": new_id("acceptance_vote"),
                            "t": two_operators["tenant_a"],
                            "p": proposal_id,
                            "u": two_operators["one"],
                            "iss": ISSUER,
                            "at": int(NOW.timestamp()),
                            "amr": AMR,
                            "ev": new_id("audit_event"),
                            "now": LATER,
                        },
                    )
    assert "uq_release_acceptance_votes_proposal_user" in str(refused.value)


def test_a_decision_is_withdrawn_once(app_sessionmaker, two_operators):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, two_operators["tenant_a"]):
                release, proposal_id = seed(
                    session, tenant_id=two_operators["tenant_a"], user_id=two_operators["one"]
                )
                acceptance_id = new_id("acceptance")
                session.execute(
                    text(
                        "INSERT INTO acceptance_records(acceptance_id,tenant_id,release_id,"
                        "acceptance_id_ref,outcome,accepted_manifest_sha256,known_limitations,"
                        "accepted_by_user_id,decided_at,attestation_version,proposal_id) "
                        "VALUES(:a,:t,:r,'AC-12','accepted',:m,'[]'::jsonb,:u,:now,"
                        "'fresh-interactive-v1',:p)"
                    ),
                    {
                        "a": acceptance_id,
                        "t": two_operators["tenant_a"],
                        "r": release.release_id,
                        "m": release.manifest_sha256,
                        "u": two_operators["two"],
                        "now": NOW,
                        "p": proposal_id,
                    },
                )
                for attempt in range(2):
                    statement = text(
                        "INSERT INTO release_acceptance_withdrawals(withdrawal_id,tenant_id,"
                        "release_id,acceptance_id,reason_code,accepted_manifest_sha256,"
                        "withdrawn_by_user_id,withdrawn_at) "
                        "VALUES(:w,:t,:r,:a,'security-concern',:m,:u,:now)"
                    )
                    values = {
                        "w": new_id("acceptance_withdrawal"),
                        "t": two_operators["tenant_a"],
                        "r": release.release_id,
                        "a": acceptance_id,
                        "m": release.manifest_sha256,
                        "u": two_operators["one"],
                        "now": LATER,
                    }
                    if attempt == 0:
                        session.execute(statement, values)
                        session.flush()
                    else:
                        with pytest.raises(IntegrityError) as refused:
                            session.execute(statement, values)
    assert "uq_release_acceptance_withdrawals_acceptance" in str(refused.value)


def test_a_proposal_is_closed_once_for_each_reason(app_sessionmaker, two_operators):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, two_operators["tenant_a"]):
                release, proposal_id = seed(
                    session, tenant_id=two_operators["tenant_a"], user_id=two_operators["one"]
                )
                for attempt in range(2):
                    statement = text(
                        "INSERT INTO release_acceptance_lifecycle_events(event_id,tenant_id,"
                        "proposal_id,event_kind,occurred_at) VALUES(:e,:t,:p,'expired',:now)"
                    )
                    values = {
                        "e": new_id("acceptance_lifecycle_event"),
                        "t": two_operators["tenant_a"],
                        "p": proposal_id,
                        "now": LATER,
                    }
                    if attempt == 0:
                        session.execute(statement, values)
                        session.flush()
                    else:
                        with pytest.raises(IntegrityError) as refused:
                            session.execute(statement, values)
    assert "uq_release_acceptance_lifecycle_terminal" in str(refused.value)


def test_an_attested_acceptance_must_name_a_proposal(app_sessionmaker, two_operators):
    """The forgery the CHECK exists for: today's attestation with no two votes behind it."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, two_operators["tenant_a"]):
                release, _ = seed(
                    session, tenant_id=two_operators["tenant_a"], user_id=two_operators["one"]
                )
                with pytest.raises(IntegrityError) as refused:
                    session.execute(
                        text(
                            "INSERT INTO acceptance_records(acceptance_id,tenant_id,release_id,"
                            "acceptance_id_ref,outcome,accepted_manifest_sha256,"
                            "known_limitations,accepted_by_user_id,decided_at,"
                            "attestation_version) "
                            "VALUES(:a,:t,:r,'AC-12','accepted',:m,'[]'::jsonb,:u,:now,"
                            "'fresh-interactive-v1')"
                        ),
                        {
                            "a": new_id("acceptance"),
                            "t": two_operators["tenant_a"],
                            "r": release.release_id,
                            "m": release.manifest_sha256,
                            "u": two_operators["one"],
                            "now": NOW,
                        },
                    )
    assert "attested_acceptance_names_its_proposal" in str(refused.value)


def test_a_slot_cannot_hold_another_criterions_proposal(app_sessionmaker, two_operators):
    """The FK allows any proposal in the tenant; the trigger allows only this criterion's."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, two_operators["tenant_a"]):
                release, proposal_id = seed(
                    session, tenant_id=two_operators["tenant_a"], user_id=two_operators["one"]
                )
                session.execute(
                    text(
                        "INSERT INTO release_acceptance_slots(slot_id,tenant_id,release_id,"
                        "acceptance_id_ref,updated_at) VALUES(:s,:t,:r,'AC-13',:now)"
                    ),
                    {
                        "s": new_id("acceptance_slot"),
                        "t": two_operators["tenant_a"],
                        "r": release.release_id,
                        "now": NOW,
                    },
                )
                session.flush()
                with pytest.raises((IntegrityError, DBAPIError)) as refused:
                    session.execute(
                        text(
                            "UPDATE release_acceptance_slots SET active_proposal_id=:p "
                            "WHERE tenant_id=:t AND release_id=:r AND acceptance_id_ref='AC-13'"
                        ),
                        {"p": proposal_id, "t": two_operators["tenant_a"], "r": release.release_id},
                    )
    assert "own criterion" in str(refused.value)


def test_a_pending_proposal_cannot_be_replaced_by_another(app_sessionmaker, two_operators):
    """Two pending proposals on one criterion would let a confirmer approve in ignorance."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, two_operators["tenant_a"]):
                release, first = seed(
                    session, tenant_id=two_operators["tenant_a"], user_id=two_operators["one"]
                )
                second = new_id("acceptance_proposal")
                session.execute(
                    text(
                        "INSERT INTO release_acceptance_proposals(proposal_id,tenant_id,"
                        "release_id,acceptance_id_ref,outcome,target_manifest_sha256,"
                        "proposal_digest,reason_code,target_refs,measurement_refs,"
                        "known_limitations,policy_version,policy_registry_sha256,"
                        "proposed_by_user_id,created_at,expires_at) "
                        "VALUES(:p,:t,:r,'AC-12','accepted',:m,:pd,'OPERATIONAL_ACCEPTANCE',"
                        "cast(:tr AS jsonb),cast(:mr AS jsonb),'[]'::jsonb,1,:d,:u,:now,:exp)"
                    ),
                    {
                        "p": second,
                        "t": two_operators["tenant_a"],
                        "r": release.release_id,
                        "m": release.manifest_sha256,
                        "pd": "c" * 64,
                        "tr": '[{"targetId":"t.two","targetSha256":"' + "d" * 64 + '"}]',
                        "mr": '[{"evidenceId":"e.two","evidenceSha256":"' + "e" * 64
                        + '","observedAt":"2026-10-01T10:00:00.000000Z"}]',
                        "d": "b" * 64,
                        "u": two_operators["two"],
                        "now": NOW,
                        "exp": LATER,
                    },
                )
                session.flush()
                with pytest.raises((IntegrityError, DBAPIError)) as refused:
                    session.execute(
                        text(
                            "UPDATE release_acceptance_slots SET active_proposal_id=:p "
                            "WHERE tenant_id=:t AND release_id=:r AND acceptance_id_ref='AC-12'"
                        ),
                        {"p": second, "t": two_operators["tenant_a"], "r": release.release_id},
                    )
    assert "cannot be replaced" in str(refused.value)


# ------------------------------------------------------------------ the confirm function


def test_the_function_refuses_when_no_human_is_in_transaction_scope(
    app_sessionmaker, two_operators
):
    """It takes no user ID, so with no ``inv.user_id`` set there is nobody to be.

    This is the first test in the group because it is the property the whole design rests
    on: the function cannot be *told* who is acting.
    """
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, two_operators["tenant_a"]):
                release, proposal_id = seed(
                    session, tenant_id=two_operators["tenant_a"], user_id=two_operators["one"]
                )
                with pytest.raises(DBAPIError) as refused:
                    confirm_call(
                        session,
                        proposal_id=proposal_id,
                        proposal_digest=PROPOSAL_DIGEST,
                        manifest_sha256=release.manifest_sha256,
                    )
    assert "no verified human is in scope" in str(refused.value)


def test_the_proposer_cannot_be_the_second_operator(app_sessionmaker, two_operators):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, two_operators["tenant_a"]):
                release, proposal_id = seed(
                    session, tenant_id=two_operators["tenant_a"], user_id=two_operators["one"]
                )
                with actor_scope(session, two_operators["one"]):
                    with pytest.raises(DBAPIError) as refused:
                        confirm_call(
                            session,
                            proposal_id=proposal_id,
                            proposal_digest=PROPOSAL_DIGEST,
                            manifest_sha256=release.manifest_sha256,
                        )
    assert "proposer cannot be the second operator" in str(refused.value)


def test_a_distinct_second_operator_records_the_decision(app_sessionmaker, two_operators):
    """The one path that produces an attested ``accepted`` row, end to end in the database."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, two_operators["tenant_a"]):
                release, proposal_id = seed(
                    session, tenant_id=two_operators["tenant_a"], user_id=two_operators["one"]
                )
                with actor_scope(session, two_operators["two"]):
                    acceptance_id = confirm_call(
                        session,
                        proposal_id=proposal_id,
                        proposal_digest=PROPOSAL_DIGEST,
                        manifest_sha256=release.manifest_sha256,
                    )
                row = session.execute(
                    text(
                        "SELECT outcome, attestation_version, proposal_id, accepted_by_user_id "
                        "FROM acceptance_records WHERE tenant_id=:t AND acceptance_id=:a"
                    ),
                    {"t": two_operators["tenant_a"], "a": acceptance_id},
                ).one()
                votes = session.execute(
                    text(
                        "SELECT count(DISTINCT user_id) FROM release_acceptance_votes "
                        "WHERE proposal_id=:p"
                    ),
                    {"p": proposal_id},
                ).scalar_one()
                slot = session.execute(
                    text(
                        "SELECT active_proposal_id, active_acceptance_id FROM "
                        "release_acceptance_slots WHERE tenant_id=:t AND release_id=:r"
                    ),
                    {"t": two_operators["tenant_a"], "r": release.release_id},
                ).one()
                closed = session.execute(
                    text(
                        "SELECT event_kind FROM release_acceptance_lifecycle_events "
                        "WHERE proposal_id=:p"
                    ),
                    {"p": proposal_id},
                ).scalar_one()
    assert row.outcome == "accepted"
    assert row.attestation_version == "fresh-interactive-v1"
    assert row.proposal_id == proposal_id
    # The confirmer is on the final row and the proposer stays on the vote (§5).
    assert row.accepted_by_user_id == two_operators["two"]
    assert votes == 2
    assert slot.active_proposal_id is None and slot.active_acceptance_id == acceptance_id
    assert closed == "confirmed"


def test_a_second_confirmation_of_the_same_proposal_is_refused(app_sessionmaker, two_operators):
    """The lifecycle UNIQUE is the backstop: a confirmed proposal is already closed."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, two_operators["tenant_a"]):
                release, proposal_id = seed(
                    session, tenant_id=two_operators["tenant_a"], user_id=two_operators["one"]
                )
                with actor_scope(session, two_operators["two"]):
                    confirm_call(
                        session,
                        proposal_id=proposal_id,
                        proposal_digest=PROPOSAL_DIGEST,
                        manifest_sha256=release.manifest_sha256,
                    )
                    with pytest.raises(DBAPIError) as refused:
                        confirm_call(
                            session,
                            proposal_id=proposal_id,
                            proposal_digest=PROPOSAL_DIGEST,
                            manifest_sha256=release.manifest_sha256,
                        )
    assert "already closed" in str(refused.value)


def test_a_wrong_digest_is_refused(app_sessionmaker, two_operators):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, two_operators["tenant_a"]):
                release, proposal_id = seed(
                    session, tenant_id=two_operators["tenant_a"], user_id=two_operators["one"]
                )
                with actor_scope(session, two_operators["two"]):
                    with pytest.raises(DBAPIError) as refused:
                        confirm_call(
                            session,
                            proposal_id=proposal_id,
                            proposal_digest="9" * 64,
                            manifest_sha256=release.manifest_sha256,
                        )
    assert "not this proposal" in str(refused.value)


def test_an_expired_proposal_is_refused(app_sessionmaker, two_operators):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, two_operators["tenant_a"]):
                release, proposal_id = seed(
                    session,
                    tenant_id=two_operators["tenant_a"],
                    user_id=two_operators["one"],
                    expires=NOW + dt.timedelta(seconds=30),
                )
                with actor_scope(session, two_operators["two"]):
                    with pytest.raises(DBAPIError) as refused:
                        confirm_call(
                            session,
                            proposal_id=proposal_id,
                            proposal_digest=PROPOSAL_DIGEST,
                            manifest_sha256=release.manifest_sha256,
                            now=NOW + dt.timedelta(minutes=10),
                        )
    assert "expired" in str(refused.value)


def test_a_moved_manifest_is_refused(app_sessionmaker, two_operators):
    """The caller's digest and the proposal's are both compared with the locked row."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, two_operators["tenant_a"]):
                release, proposal_id = seed(
                    session, tenant_id=two_operators["tenant_a"], user_id=two_operators["one"]
                )
                with actor_scope(session, two_operators["two"]):
                    with pytest.raises(DBAPIError) as refused:
                        confirm_call(
                            session,
                            proposal_id=proposal_id,
                            proposal_digest=PROPOSAL_DIGEST,
                            manifest_sha256="7" * 64,
                        )
    assert "composition has changed" in str(refused.value)


def test_an_operator_without_the_grant_is_refused(app_sessionmaker, owner_engine, two_operators):
    """The grant is re-read inside the function, from the row and not from a claim."""
    with owner_engine.begin() as c:
        c.execute(
            text(
                "UPDATE inv.business_admin_grants SET enabled=false "
                "WHERE tenant_id=:t AND user_id=:u AND permission='releases.accept'"
            ),
            {"t": two_operators["tenant_a"], "u": two_operators["two"]},
        )
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, two_operators["tenant_a"]):
                release, proposal_id = seed(
                    session, tenant_id=two_operators["tenant_a"], user_id=two_operators["one"]
                )
                with actor_scope(session, two_operators["two"]):
                    with pytest.raises(DBAPIError) as refused:
                        confirm_call(
                            session,
                            proposal_id=proposal_id,
                            proposal_digest=PROPOSAL_DIGEST,
                            manifest_sha256=release.manifest_sha256,
                        )
    assert "may not accept releases" in str(refused.value)


def test_a_suspended_operator_is_refused(app_sessionmaker, owner_engine, two_operators):
    with owner_engine.begin() as c:
        c.execute(
            text("UPDATE users SET status='suspended' WHERE tenant_id=:t AND user_id=:u"),
            {"t": two_operators["tenant_a"], "u": two_operators["two"]},
        )
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, two_operators["tenant_a"]):
                release, proposal_id = seed(
                    session, tenant_id=two_operators["tenant_a"], user_id=two_operators["one"]
                )
                with actor_scope(session, two_operators["two"]):
                    with pytest.raises(DBAPIError) as refused:
                        confirm_call(
                            session,
                            proposal_id=proposal_id,
                            proposal_digest=PROPOSAL_DIGEST,
                            manifest_sha256=release.manifest_sha256,
                        )
    assert "not active" in str(refused.value)


def test_the_function_is_not_executable_by_public(app_sessionmaker, owner_engine, two_operators):
    """EXECUTE is granted to the application role only (§4-1)."""
    with owner_engine.begin() as c:
        granted = c.execute(
            text(
                "SELECT has_function_privilege('inv_app', p.oid, 'EXECUTE') AS app, "
                "has_function_privilege('public', p.oid, 'EXECUTE') AS anyone "
                "FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
                "WHERE n.nspname='public' AND p.proname='release_acceptance_confirm'"
            )
        ).one()
        security = c.execute(
            text(
                "SELECT prosecdef FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                "WHERE n.nspname='public' AND p.proname='release_acceptance_confirm'"
            )
        ).scalar_one()
    assert granted.app is True
    assert granted.anyone is False
    # SECURITY INVOKER, as §4-1 requires: no definer privileges anywhere in this path.
    assert security is False


# ------------------------------------------------------------------ two connections at once


def test_two_connections_cannot_both_claim_one_criterion(app_sessionmaker, two_operators):
    """§9 hosted 1: concurrent first proposals converge on one pending proposal.

    Two real connections and a bounded lock wait, in the two phases the convergence
    actually has -- which is not what I first wrote. My first version had the second
    connection take ``FOR UPDATE`` on the slot while the first held it *uncommitted*, and
    it was not blocked at all: an uncommitted row is invisible, so the second transaction
    found nothing to lock. The mechanism is index-level before the row exists and
    row-level after it:

    * **phase one, the row does not exist yet.** Both transactions insert the slot. The
      second blocks on the unique index until the first commits or rolls back, which is
      why two simultaneous first proposals cannot both create a pending proposal;
    * **phase two, the row exists.** The second transaction waits on ``FOR UPDATE``,
      which is what serialises every later writer on that criterion.

    Both phases end in a lock timeout here so the test states "blocked" instead of
    hanging. In a request the loser waits inside the lock budget and then reads the
    committed state, which is the convergence §4 describes.
    """
    tenant = two_operators["tenant_a"]
    with app_sessionmaker() as first, app_sessionmaker() as second:
        # phase one: neither slot row exists yet
        with first.begin():
            with tenant_scope(first, tenant):
                release = pilot_service.create_release_manifest(
                    first,
                    tenant_id=tenant,
                    version="R4",
                    components=_components(),
                    created_by_user_id=two_operators["one"],
                    now=NOW,
                )
                first.flush()
        with first.begin():
            with tenant_scope(first, tenant):
                first.execute(
                    text(
                        "INSERT INTO release_acceptance_slots(slot_id,tenant_id,release_id,"
                        "acceptance_id_ref,updated_at) VALUES(:s,:t,:r,'AC-12',:now)"
                    ),
                    {
                        "s": new_id("acceptance_slot"),
                        "t": tenant,
                        "r": release.release_id,
                        "now": NOW,
                    },
                )
                first.flush()
                with second.begin():
                    with tenant_scope(second, tenant):
                        second.execute(text("SET LOCAL lock_timeout = '750ms'"))
                        with pytest.raises(DBAPIError) as blocked_on_index:
                            second.execute(
                                text(
                                    "INSERT INTO release_acceptance_slots(slot_id,tenant_id,"
                                    "release_id,acceptance_id_ref,updated_at) "
                                    "VALUES(:s,:t,:r,'AC-12',:now)"
                                ),
                                {
                                    "s": new_id("acceptance_slot"),
                                    "t": tenant,
                                    "r": release.release_id,
                                    "now": NOW,
                                },
                            )
        assert "lock timeout" in str(blocked_on_index.value).lower()

        # phase two: the row is committed, so the wait is on the row
        with first.begin():
            with tenant_scope(first, tenant):
                held = first.execute(
                    text(
                        "SELECT slot_id FROM release_acceptance_slots WHERE tenant_id=:t "
                        "AND release_id=:r AND acceptance_id_ref='AC-12' FOR UPDATE"
                    ),
                    {"t": tenant, "r": release.release_id},
                ).scalar_one()
                assert held
                with second.begin():
                    with tenant_scope(second, tenant):
                        second.execute(text("SET LOCAL lock_timeout = '750ms'"))
                        with pytest.raises(DBAPIError) as blocked_on_row:
                            second.execute(
                                text(
                                    "SELECT slot_id FROM release_acceptance_slots "
                                    "WHERE tenant_id=:t AND release_id=:r "
                                    "AND acceptance_id_ref='AC-12' FOR UPDATE"
                                ),
                                {"t": tenant, "r": release.release_id},
                            )
    assert "lock timeout" in str(blocked_on_row.value).lower()


def test_a_second_slot_row_for_one_criterion_is_impossible(app_sessionmaker, two_operators):
    """The uniqueness the convergence rests on, stated without concurrency."""
    tenant = two_operators["tenant_a"]
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, tenant):
                release, _ = seed(session, tenant_id=tenant, user_id=two_operators["one"])
                with pytest.raises(IntegrityError) as refused:
                    session.execute(
                        text(
                            "INSERT INTO release_acceptance_slots(slot_id,tenant_id,release_id,"
                            "acceptance_id_ref,updated_at) VALUES(:s,:t,:r,'AC-12',:now)"
                        ),
                        {
                            "s": new_id("acceptance_slot"),
                            "t": tenant,
                            "r": release.release_id,
                            "now": NOW,
                        },
                    )
    assert "uq_release_acceptance_slots_criterion" in str(refused.value)
