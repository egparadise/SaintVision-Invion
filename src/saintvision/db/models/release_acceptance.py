"""Two-person release acceptance: proposals, votes, withdrawals, and the slot (S12-BE).

Design: ``S12-BE_release_acceptance_operator_signoff_쓰기_계약_설계`` (Codex, #282).
This module is the storage half of §4-1.

**Why new tables at all.** ``acceptance_records`` already holds a final decision and
already has a real foreign key to ``users``, and it still cannot express this
contract: it is unique on ``(release_id, acceptance_id_ref)``, so one criterion can
be decided exactly once and never re-decided, never withdrawn, and never voted on by
two people. Widening that row would mean rewriting history in place -- the thing a
decision record exists to prevent. So the final decision stays where it is, and what
is new is the *history around it*: who proposed, who confirmed, what closed a
proposal, and what was withdrawn.

**Append-only, and what that does and does not mean.** The application role gets
SELECT and INSERT on the proposal, vote, withdrawal and lifecycle tables and nothing
else (§4-1). A proposal is never edited: it expires or is superseded by appending a
lifecycle event, which is why ``release_acceptance_lifecycle_events`` is UNIQUE on
``(proposal_id, event_kind)`` -- a proposal can be closed once for each reason, and
the row that says so is the closing. This is a real constraint on the application and
explicitly **not** a WORM claim against a superuser (PLAN-DB-001).

**The slot is the only mutable row, and the trigger is what makes that safe.**
``release_acceptance_slots`` is unique on ``(tenant_id, release_id,
acceptance_id_ref)`` and names at most one pending proposal or one active final, which
is how two concurrent proposals converge on one (§4). It is the one table here the
application may UPDATE, on exactly two columns.

A caveat worth stating rather than hiding: the canonical write functions are
``SECURITY INVOKER`` (§4-1 forbids ``SECURITY DEFINER``), so they run with the
caller's privileges and the application role must hold that UPDATE for them to work
-- which means the role can also issue the UPDATE directly. "Only the function may
move the slot" is therefore not a privilege boundary, and this module does not claim
it is. What *is* enforced regardless of who issues the statement is the slot's state
machine, in a trigger: a slot may hold a pending proposal or an active final but never
both, the row it names must belong to the same tenant, release and criterion, and a
pending proposal may only be replaced by the final decision it became or by nothing.
A bug that writes the slot directly hits the same wall as a bug inside the function.
"""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base, InvId, Sha256, TenantId, Utc

#: The attestation this build can verify. Stored on every vote so a later reader can
#: tell which rule a row was admitted under, instead of assuming today's.
HUMAN_ATTESTATION_VERSION = "fresh-interactive-v1"

#: What a legacy ``acceptance_records`` row is classified as: a decision written by the
#: one-person path, with no attested human behind it. It is not counted toward
#: sign-off (§4-1), and the word "unverified" is the whole point -- those rows were not
#: wrong, they were never checked for this.
LEGACY_ATTESTATION_VERSION = "legacy-unverified"


class ReleaseAcceptanceProposal(Base):
    """An ``accepted`` decision waiting for a distinct second human.

    Immutable. Everything a confirmer must agree to is here, including the digests
    the decision was made against, so a confirmation is a confirmation of *this*
    content and not of a proposal ID.

    ``proposal_digest`` is server-derived over the parse-complete model (§3-2); it is
    stored because the confirmer sends it back and the comparison must be against
    what was proposed, not against a recomputation that could pick up today's values.

    ``policy_version`` and ``policy_registry_sha256`` are pinned here for the same
    reason: a decision made under one set of required criteria is not a decision
    under another, so a registry change invalidates it rather than silently
    re-scoping it (§5-1).
    """

    __tablename__ = "release_acceptance_proposals"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "release_id"],
            ["release_manifests.tenant_id", "release_manifests.release_id"],
        ),
        ForeignKeyConstraint(
            ["tenant_id", "proposed_by_user_id"], ["users.tenant_id", "users.user_id"]
        ),
        UniqueConstraint(
            "tenant_id", "proposal_id", name="uq_release_acceptance_proposals_tenant_proposal"
        ),
        # Only ``accepted`` needs a second person, so only ``accepted`` is proposed.
        # conditional and rejected are one person's final record and go straight to
        # acceptance_records (§0.2).
        CheckConstraint("outcome = 'accepted'", name="proposal_is_accepted"),
        CheckConstraint(
            "target_manifest_sha256 = lower(target_manifest_sha256)",
            name="proposal_manifest_hash_is_lowercase",
        ),
        CheckConstraint(
            "proposal_digest = lower(proposal_digest)", name="proposal_digest_is_lowercase"
        ),
        CheckConstraint(
            "policy_registry_sha256 = lower(policy_registry_sha256)",
            name="proposal_policy_digest_is_lowercase",
        ),
        # A target declaration and a measurement are both required, and neither may
        # stand in for the other (§3-1). Empty lists would make "accepted" mean
        # "somebody pressed the button".
        CheckConstraint("jsonb_array_length(target_refs) > 0", name="proposal_has_targets"),
        CheckConstraint(
            "jsonb_array_length(measurement_refs) > 0", name="proposal_has_measurements"
        ),
        # An accepted decision carries no limitations; a hedge is a ``conditional``,
        # which never becomes a proposal.
        CheckConstraint(
            "jsonb_array_length(known_limitations) = 0", name="proposal_has_no_limitations"
        ),
        CheckConstraint("policy_version > 0", name="proposal_policy_version_positive"),
        # The fresh-auth window is bounded and in the future when written. A proposal
        # that is born expired would be a confirmable row nobody could confirm.
        CheckConstraint("expires_at > created_at", name="proposal_expiry_is_ahead"),
        # The list order in §3 is (created_at, proposal_id); this index is that order.
        Index(
            "ix_release_acceptance_proposals_page",
            "tenant_id",
            "release_id",
            "created_at",
            "proposal_id",
        ),
    )

    proposal_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column()
    release_id: Mapped[InvId] = mapped_column()
    acceptance_id_ref: Mapped[str] = mapped_column(String(16))
    outcome: Mapped[str] = mapped_column(String(16))
    #: The manifest digest **the server read under lock**, not the caller's value.
    target_manifest_sha256: Mapped[Sha256] = mapped_column()
    proposal_digest: Mapped[Sha256] = mapped_column()
    reason_code: Mapped[str] = mapped_column(String(64))
    target_refs: Mapped[list] = mapped_column(JSONB)
    measurement_refs: Mapped[list] = mapped_column(JSONB)
    known_limitations: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    policy_version: Mapped[int] = mapped_column(Integer)
    policy_registry_sha256: Mapped[Sha256] = mapped_column()
    #: The proposer, kept here because the final row records the *confirmer* (§5).
    #: Neither ever appears in a response.
    proposed_by_user_id: Mapped[InvId] = mapped_column()
    created_at: Mapped[Utc] = mapped_column(server_default=text("now()"))
    #: The earlier of the proposer's verified ``auth_time + 300s`` and their token
    #: ``exp`` (§2-2). After it, the proposal is closed by an appended event.
    expires_at: Mapped[Utc] = mapped_column()


class ReleaseAcceptanceVote(Base):
    """One person's attested agreement to one proposal.

    What makes this a vote rather than a row with a user ID in it: the attestation
    metadata beside it. ``accepted_by_user_id`` on a final row proves the referenced
    user exists -- Codex measured that a service principal satisfies it -- so a
    quorum counted from foreign keys is a quorum of rows, not of people. These columns
    record what was actually verified about the human at the moment they voted, and
    nothing that could re-authenticate anyone: no token, no subject, no claim bodies,
    only the issuer and client the token was verified against, the verified
    ``auth_time``, and a digest of the normalised AMR set (§2-1).

    UNIQUE ``(proposal_id, user_id)`` is the two-person rule in the schema: the same
    person cannot be both voters however many requests they send.
    """

    __tablename__ = "release_acceptance_votes"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "proposal_id"],
            [
                "release_acceptance_proposals.tenant_id",
                "release_acceptance_proposals.proposal_id",
            ],
        ),
        ForeignKeyConstraint(["tenant_id", "user_id"], ["users.tenant_id", "users.user_id"]),
        UniqueConstraint(
            "tenant_id", "vote_id", name="uq_release_acceptance_votes_tenant_vote"
        ),
        # §4-1. Not (tenant, proposal, user): a proposal ID is already tenant-unique,
        # and the narrower key is the one that states the rule.
        UniqueConstraint(
            "proposal_id", "user_id", name="uq_release_acceptance_votes_proposal_user"
        ),
        CheckConstraint(
            "vote_role IN ('proposer','confirmer')", name="vote_role_allowed"
        ),
        CheckConstraint("amr_sha256 = lower(amr_sha256)", name="vote_amr_digest_is_lowercase"),
        CheckConstraint(
            "human_attestation_version <> ''", name="vote_attestation_version_present"
        ),
        # A verified issuer and client are part of what "this human authenticated"
        # means: the same subject from another issuer is another person (§2-1).
        CheckConstraint("verified_issuer LIKE 'https://%'", name="vote_issuer_is_https"),
        CheckConstraint("auth_time > 0", name="vote_auth_time_positive"),
        Index("ix_release_acceptance_votes_proposal", "tenant_id", "proposal_id"),
    )

    vote_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column()
    proposal_id: Mapped[InvId] = mapped_column()
    user_id: Mapped[InvId] = mapped_column()
    vote_role: Mapped[str] = mapped_column(String(16))
    human_attestation_version: Mapped[str] = mapped_column(String(32))
    verified_issuer: Mapped[str] = mapped_column(String(255))
    verified_client_id: Mapped[str] = mapped_column(String(255))
    #: The verified ``auth_time`` claim as seconds since the epoch. An integer, so a
    #: reader can compare it to the proposal's window without parsing anything.
    auth_time: Mapped[int] = mapped_column(Integer)
    #: SHA-256 of the normalised AMR set. The set itself is small and guessable, so
    #: the digest is not a secret -- it is here because a digest cannot grow a free
    #: text field, and this table must never become a claim store.
    amr_sha256: Mapped[Sha256] = mapped_column()
    #: The audit event that recorded the identity verification this vote rests on.
    identity_verification_event_id: Mapped[InvId] = mapped_column()
    created_at: Mapped[Utc] = mapped_column(server_default=text("now()"))


class ReleaseAcceptanceWithdrawal(Base):
    """A final decision withdrawn without being deleted or rewritten (§6).

    UNIQUE on ``acceptance_id``: a decision is withdrawn once. A second withdrawal is
    not a stronger statement, and allowing one would make "when was this withdrawn"
    unanswerable.

    ``accepted_manifest_sha256`` is the digest **stored on the withdrawn row**, not
    the release's current digest. They differ exactly when the release has moved on,
    which is a common reason to withdraw, so comparing against the current digest
    would refuse the withdrawal that matters most.
    """

    __tablename__ = "release_acceptance_withdrawals"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "acceptance_id"],
            ["acceptance_records.tenant_id", "acceptance_records.acceptance_id"],
        ),
        ForeignKeyConstraint(
            ["tenant_id", "release_id"],
            ["release_manifests.tenant_id", "release_manifests.release_id"],
        ),
        ForeignKeyConstraint(
            ["tenant_id", "withdrawn_by_user_id"], ["users.tenant_id", "users.user_id"]
        ),
        UniqueConstraint(
            "tenant_id", "withdrawal_id", name="uq_release_acceptance_withdrawals_tenant_id"
        ),
        # §4-1: one withdrawal per acceptance, stated without the tenant for the same
        # reason as the vote key.
        UniqueConstraint(
            "acceptance_id", name="uq_release_acceptance_withdrawals_acceptance"
        ),
        CheckConstraint(
            "reason_code IN ('manifest-superseded','acceptance-error','security-concern',"
            "'operator-request')",
            name="withdrawal_reason_allowed",
        ),
        CheckConstraint(
            "accepted_manifest_sha256 = lower(accepted_manifest_sha256)",
            name="withdrawal_manifest_hash_is_lowercase",
        ),
        Index(
            "ix_release_acceptance_withdrawals_release", "tenant_id", "release_id", "withdrawn_at"
        ),
    )

    withdrawal_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column()
    release_id: Mapped[InvId] = mapped_column()
    acceptance_id: Mapped[InvId] = mapped_column()
    reason_code: Mapped[str] = mapped_column(String(32))
    accepted_manifest_sha256: Mapped[Sha256] = mapped_column()
    #: One fresh operator may withdraw, including a decision they did not make (§6).
    #: Withdrawal is the safe direction; requiring two people to stop trusting
    #: something would mean one person cannot stop trusting it.
    withdrawn_by_user_id: Mapped[InvId] = mapped_column()
    withdrawn_at: Mapped[Utc] = mapped_column(server_default=text("now()"))


class ReleaseAcceptanceLifecycleEvent(Base):
    """How a proposal ended, appended rather than written into the proposal.

    A proposal that expired is not an edited proposal; it is a proposal with an
    ``expired`` event. That distinction is why §4 can commit the closing transaction
    and *then* return 409: the state change is a row that exists, not an error that
    rolled back.

    UNIQUE ``(proposal_id, event_kind)`` makes each terminal reason recordable once,
    which also means the database refuses a second confirmation of the same proposal
    even if every check above it were bypassed.
    """

    __tablename__ = "release_acceptance_lifecycle_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "proposal_id"],
            [
                "release_acceptance_proposals.tenant_id",
                "release_acceptance_proposals.proposal_id",
            ],
        ),
        UniqueConstraint(
            "tenant_id", "event_id", name="uq_release_acceptance_lifecycle_tenant_event"
        ),
        UniqueConstraint(
            "proposal_id", "event_kind", name="uq_release_acceptance_lifecycle_terminal"
        ),
        # A closed set. ``confirmed`` is the terminal event of a proposal that became a
        # final decision; the other two are §5's invalidation reasons.
        CheckConstraint(
            "event_kind IN ('confirmed','expired','manifest-superseded')",
            name="lifecycle_event_kind_allowed",
        ),
        Index(
            "ix_release_acceptance_lifecycle_proposal", "tenant_id", "proposal_id", "occurred_at"
        ),
    )

    event_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column()
    proposal_id: Mapped[InvId] = mapped_column()
    event_kind: Mapped[str] = mapped_column(String(32))
    #: The final decision this proposal became, for ``confirmed`` only.
    acceptance_id: Mapped[InvId | None] = mapped_column(nullable=True)
    occurred_at: Mapped[Utc] = mapped_column(server_default=text("now()"))


class ReleaseAcceptanceSlot(Base):
    """One criterion of one release: what is pending, or what is active.

    The convergence point of §4. Two operators proposing the same criterion at the
    same moment both try to claim this row; the unique key means one of them gets it
    and the other is told about the proposal that already exists, instead of a second
    pending proposal appearing that a confirmer could approve in ignorance of the
    first.

    Both columns nullable and never both set: a criterion is pending, decided, or
    neither. The third state is real -- a proposal that expired leaves the slot empty,
    and the criterion is then unmet, which is the honest answer rather than leaving a
    dead proposal in place to look like progress.
    """

    __tablename__ = "release_acceptance_slots"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "release_id"],
            ["release_manifests.tenant_id", "release_manifests.release_id"],
        ),
        ForeignKeyConstraint(
            ["tenant_id", "active_proposal_id"],
            [
                "release_acceptance_proposals.tenant_id",
                "release_acceptance_proposals.proposal_id",
            ],
        ),
        ForeignKeyConstraint(
            ["tenant_id", "active_acceptance_id"],
            ["acceptance_records.tenant_id", "acceptance_records.acceptance_id"],
        ),
        # §4-1. This is the key that makes concurrent proposals converge.
        UniqueConstraint(
            "tenant_id",
            "release_id",
            "acceptance_id_ref",
            name="uq_release_acceptance_slots_criterion",
        ),
        CheckConstraint(
            "active_proposal_id IS NULL OR active_acceptance_id IS NULL",
            name="slot_holds_one_state",
        ),
        Index("ix_release_acceptance_slots_release", "tenant_id", "release_id"),
    )

    slot_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column()
    release_id: Mapped[InvId] = mapped_column()
    acceptance_id_ref: Mapped[str] = mapped_column(String(16))
    active_proposal_id: Mapped[InvId | None] = mapped_column(nullable=True)
    active_acceptance_id: Mapped[InvId | None] = mapped_column(nullable=True)
    updated_at: Mapped[Utc] = mapped_column(server_default=text("now()"))
