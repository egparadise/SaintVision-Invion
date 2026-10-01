"""Two-person release acceptance: history, slot, and the function that admits a final row (0057).

The revision id is ``0057_release_acceptance_quorum`` and not the longer name this file
once had: ``alembic_version.version_num`` is ``varchar(32)``, and a 34-character id
fails the first upgrade with "value too long" rather than at review time.

Design: ``S12-BE_release_acceptance_operator_signoff_쓰기_계약_설계`` (Codex, #282) §4-1.
Card 187. Coordinator-assigned revision number: the alembic head at the base
(``b8f02b1a``) and at ``coord/train8c-ci-1900`` is 0056, no 0057 exists on any ref.

**What this revision is for.** ``acceptance_records`` already carried a foreign key to
``users`` and that key was read as proof a person had signed. Codex measured otherwise:
``users`` draws no line between a person and a service, so a principal whose subject was
``svc:release-bot`` produced a sign-off. The answer is not a better column on that table.
It is that a decision needs *two* attested people, a re-decision has to be possible, a
withdrawal has to be possible, and none of that fits a row that is unique on
``(release_id, acceptance_id_ref)`` and edited in place.

So this revision adds the history around the decision and leaves the decision where it is:

* ``release_acceptance_proposals`` -- an ``accepted`` decision awaiting a second human,
  immutable, carrying the digests and the policy pin it was made under;
* ``release_acceptance_votes`` -- one person's attested agreement, UNIQUE on
  ``(proposal_id, user_id)``, which is the two-person rule written in the schema;
* ``release_acceptance_withdrawals`` -- append-only, UNIQUE on ``acceptance_id``;
* ``release_acceptance_lifecycle_events`` -- how a proposal ended, UNIQUE on
  ``(proposal_id, event_kind)``, so a proposal is closed by appending a row rather than
  by editing the proposal;
* ``release_acceptance_slots`` -- one row per ``(tenant, release, criterion)`` naming at
  most one pending proposal or one active final. This is where two simultaneous
  proposals converge on one.

**acceptance_records changes, and why each is necessary.**

* ``attestation_version``: every existing row becomes ``legacy-unverified``, because that
  is what they are -- written by the one-person path, with nothing recorded about who the
  human was. They are not deleted and not called wrong; they are classified, and the
  sign-off projection does not count them (§4-1).
* ``proposal_id``: a canonical ``accepted`` row names the proposal whose two votes
  admitted it. Without it, "which two people" is a question the schema cannot answer.
* the CHECK: a canonical ``accepted`` row **must** name a proposal. A row claiming
  today's attestation version with no proposal behind it is the exact forgery this
  contract exists to prevent, and the database refuses it rather than trusting the
  service that inserts it.
* ``uq_acceptance_records_release_criterion`` is dropped: one criterion decided once,
  forever, cannot express a withdrawal followed by a new decision. The slot's unique key
  replaces it -- and it is a stronger statement, because it also governs the pending
  state the old key knew nothing about.
* UPDATE and DELETE are revoked from ``inv_app``. 0005 granted them; §4-1 takes them
  back. A decision that can be edited is not a decision.

**The function, and the limit of what a function can promise here.** §4-1 requires
``SECURITY INVOKER`` and forbids ``SECURITY DEFINER``, dynamic SQL, and raw user-ID
arguments. ``public.release_acceptance_confirm`` therefore reads the acting human from
``inv.user_id`` -- transaction state only the request path sets -- and re-derives
everything else: the user is active, the live ``releases.accept`` grant holds, the
proposal is unexpired and unclosed, the slot still points at it, and the one existing
vote belongs to somebody else. Only then does the final row exist.

Because it is ``SECURITY INVOKER``, it runs with the caller's privileges, so the
application role must itself hold the INSERT and the slot UPDATE. "Only the function may
write these rows" is consequently **not** a privilege boundary, and this revision does not
claim it is. What holds regardless of who issues the statement is in the schema: the
distinct-voter UNIQUE, the one-withdrawal UNIQUE, the one-terminal-event UNIQUE, the
slot's single-state CHECK and its state-machine trigger, and the CHECK that a canonical
accepted row names a proposal. A bug that bypasses the function meets the same wall.

**Downgrade reverses while nothing has been recorded.** Guarded, not unconditional: an
irreversible head would empty AC-11's ``migration-reversible-segment``, and 0053-0056 all
guard rather than refuse. Each guard asks whether the old shape could hold what the new one
now holds -- a proposal, a vote, a withdrawal, an attested acceptance, two decisions on one
criterion, a ``releases.accept`` grant -- and names the one that stops it.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0057_release_acceptance_quorum"
down_revision = "0056_kernel_cancel_audit_bridge"
branch_labels = None
depends_on = None

INV_ID = sa.CHAR(30)
SHA256 = sa.CHAR(64)
UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB
TS = sa.DateTime(timezone=True)

APP_ROLE = "inv_app"
TENANT_EXPR = "NULLIF(current_setting('inv.tenant_id', true), '')::uuid"
ACTOR_EXPR = "NULLIF(current_setting('inv.user_id', true), '')"

#: Append-only for the application: SELECT and INSERT, never UPDATE or DELETE.
APPEND_ONLY = (
    "release_acceptance_proposals",
    "release_acceptance_votes",
    "release_acceptance_withdrawals",
    "release_acceptance_lifecycle_events",
)

#: The one table here whose row moves, and the only columns that may move on it.
SLOT_TABLE = "release_acceptance_slots"
SLOT_UPDATE_COLUMNS = ("active_proposal_id", "active_acceptance_id", "updated_at")

#: ``releases.accept`` is the new live permission. The grant-governance permission named
#: in §4-1 is ``users.manage``, which §2-2 already assigns that role and which the CHECK
#: already allows -- so this revision adds exactly one value and invents no new one.
PERMISSIONS = ("users.manage", "resources.manage", "releases.accept")


def upgrade() -> None:
    op.create_table(
        "release_acceptance_proposals",
        sa.Column("proposal_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("release_id", INV_ID, nullable=False),
        sa.Column("acceptance_id_ref", sa.String(16), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("target_manifest_sha256", SHA256, nullable=False),
        sa.Column("proposal_digest", SHA256, nullable=False),
        sa.Column("reason_code", sa.String(64), nullable=False),
        sa.Column("target_refs", JSONB, nullable=False),
        sa.Column("measurement_refs", JSONB, nullable=False),
        sa.Column(
            "known_limitations", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column("policy_version", sa.Integer, nullable=False),
        sa.Column("policy_registry_sha256", SHA256, nullable=False),
        sa.Column("proposed_by_user_id", INV_ID, nullable=False),
        sa.Column("created_at", TS, nullable=False, server_default=sa.text("now()")),
        sa.Column("expires_at", TS, nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id", "release_id"],
            ["release_manifests.tenant_id", "release_manifests.release_id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "proposed_by_user_id"], ["users.tenant_id", "users.user_id"]
        ),
        sa.UniqueConstraint(
            "tenant_id", "proposal_id", name="uq_release_acceptance_proposals_tenant_proposal"
        ),
        sa.CheckConstraint("outcome = 'accepted'", name="proposal_is_accepted"),
        sa.CheckConstraint(
            "target_manifest_sha256 = lower(target_manifest_sha256)",
            name="proposal_manifest_hash_is_lowercase",
        ),
        sa.CheckConstraint(
            "proposal_digest = lower(proposal_digest)", name="proposal_digest_is_lowercase"
        ),
        sa.CheckConstraint(
            "policy_registry_sha256 = lower(policy_registry_sha256)",
            name="proposal_policy_digest_is_lowercase",
        ),
        sa.CheckConstraint("jsonb_array_length(target_refs) > 0", name="proposal_has_targets"),
        sa.CheckConstraint(
            "jsonb_array_length(measurement_refs) > 0", name="proposal_has_measurements"
        ),
        sa.CheckConstraint(
            "jsonb_array_length(known_limitations) = 0", name="proposal_has_no_limitations"
        ),
        sa.CheckConstraint("policy_version > 0", name="proposal_policy_version_positive"),
        sa.CheckConstraint("expires_at > created_at", name="proposal_expiry_is_ahead"),
    )
    op.create_index(
        "ix_release_acceptance_proposals_page",
        "release_acceptance_proposals",
        ["tenant_id", "release_id", "created_at", "proposal_id"],
    )

    op.create_table(
        "release_acceptance_votes",
        sa.Column("vote_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("proposal_id", INV_ID, nullable=False),
        sa.Column("user_id", INV_ID, nullable=False),
        sa.Column("vote_role", sa.String(16), nullable=False),
        sa.Column("human_attestation_version", sa.String(32), nullable=False),
        sa.Column("verified_issuer", sa.String(255), nullable=False),
        sa.Column("verified_client_id", sa.String(255), nullable=False),
        sa.Column("auth_time", sa.Integer, nullable=False),
        sa.Column("amr_sha256", SHA256, nullable=False),
        sa.Column("identity_verification_event_id", INV_ID, nullable=False),
        sa.Column("created_at", TS, nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["tenant_id", "proposal_id"],
            [
                "release_acceptance_proposals.tenant_id",
                "release_acceptance_proposals.proposal_id",
            ],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "user_id"], ["users.tenant_id", "users.user_id"]
        ),
        sa.UniqueConstraint("tenant_id", "vote_id", name="uq_release_acceptance_votes_tenant_vote"),
        # The two-person rule, in the schema rather than in a service.
        sa.UniqueConstraint(
            "proposal_id", "user_id", name="uq_release_acceptance_votes_proposal_user"
        ),
        sa.CheckConstraint("vote_role IN ('proposer','confirmer')", name="vote_role_allowed"),
        sa.CheckConstraint("amr_sha256 = lower(amr_sha256)", name="vote_amr_digest_is_lowercase"),
        sa.CheckConstraint(
            "human_attestation_version <> ''", name="vote_attestation_version_present"
        ),
        sa.CheckConstraint("verified_issuer LIKE 'https://%'", name="vote_issuer_is_https"),
        sa.CheckConstraint("auth_time > 0", name="vote_auth_time_positive"),
    )
    op.create_index(
        "ix_release_acceptance_votes_proposal",
        "release_acceptance_votes",
        ["tenant_id", "proposal_id"],
    )

    op.create_table(
        "release_acceptance_withdrawals",
        sa.Column("withdrawal_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("release_id", INV_ID, nullable=False),
        sa.Column("acceptance_id", INV_ID, nullable=False),
        sa.Column("reason_code", sa.String(32), nullable=False),
        sa.Column("accepted_manifest_sha256", SHA256, nullable=False),
        sa.Column("withdrawn_by_user_id", INV_ID, nullable=False),
        sa.Column("withdrawn_at", TS, nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["tenant_id", "acceptance_id"],
            ["acceptance_records.tenant_id", "acceptance_records.acceptance_id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "release_id"],
            ["release_manifests.tenant_id", "release_manifests.release_id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "withdrawn_by_user_id"], ["users.tenant_id", "users.user_id"]
        ),
        sa.UniqueConstraint(
            "tenant_id", "withdrawal_id", name="uq_release_acceptance_withdrawals_tenant_id"
        ),
        sa.UniqueConstraint(
            "acceptance_id", name="uq_release_acceptance_withdrawals_acceptance"
        ),
        sa.CheckConstraint(
            "reason_code IN ('manifest-superseded','acceptance-error','security-concern',"
            "'operator-request')",
            name="withdrawal_reason_allowed",
        ),
        sa.CheckConstraint(
            "accepted_manifest_sha256 = lower(accepted_manifest_sha256)",
            name="withdrawal_manifest_hash_is_lowercase",
        ),
    )
    op.create_index(
        "ix_release_acceptance_withdrawals_release",
        "release_acceptance_withdrawals",
        ["tenant_id", "release_id", "withdrawn_at"],
    )

    op.create_table(
        "release_acceptance_lifecycle_events",
        sa.Column("event_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("proposal_id", INV_ID, nullable=False),
        sa.Column("event_kind", sa.String(32), nullable=False),
        sa.Column("acceptance_id", INV_ID, nullable=True),
        sa.Column("occurred_at", TS, nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["tenant_id", "proposal_id"],
            [
                "release_acceptance_proposals.tenant_id",
                "release_acceptance_proposals.proposal_id",
            ],
        ),
        sa.UniqueConstraint(
            "tenant_id", "event_id", name="uq_release_acceptance_lifecycle_tenant_event"
        ),
        sa.UniqueConstraint(
            "proposal_id", "event_kind", name="uq_release_acceptance_lifecycle_terminal"
        ),
        sa.CheckConstraint(
            "event_kind IN ('confirmed','expired','manifest-superseded')",
            name="lifecycle_event_kind_allowed",
        ),
    )
    op.create_index(
        "ix_release_acceptance_lifecycle_proposal",
        "release_acceptance_lifecycle_events",
        ["tenant_id", "proposal_id", "occurred_at"],
    )

    op.create_table(
        SLOT_TABLE,
        sa.Column("slot_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("release_id", INV_ID, nullable=False),
        sa.Column("acceptance_id_ref", sa.String(16), nullable=False),
        sa.Column("active_proposal_id", INV_ID, nullable=True),
        sa.Column("active_acceptance_id", INV_ID, nullable=True),
        sa.Column("updated_at", TS, nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["tenant_id", "release_id"],
            ["release_manifests.tenant_id", "release_manifests.release_id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "active_proposal_id"],
            [
                "release_acceptance_proposals.tenant_id",
                "release_acceptance_proposals.proposal_id",
            ],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "active_acceptance_id"],
            ["acceptance_records.tenant_id", "acceptance_records.acceptance_id"],
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "release_id",
            "acceptance_id_ref",
            name="uq_release_acceptance_slots_criterion",
        ),
        sa.CheckConstraint(
            "active_proposal_id IS NULL OR active_acceptance_id IS NULL",
            name="slot_holds_one_state",
        ),
    )
    op.create_index(
        "ix_release_acceptance_slots_release", SLOT_TABLE, ["tenant_id", "release_id"]
    )

    # ---------------------------------------------------------------- the policy pin
    # Which required criteria this release was accepted against, pinned at deployment
    # (§5-1). Nullable because every existing release has no pin, and the projection
    # refuses an unpinned release rather than reading today's registry as its policy:
    # that would be deciding retroactively what a release was accepted against.
    # Both columns move together -- a version without a digest names a document nobody
    # can identify, and a digest without a version cannot be compared for monotonicity.
    op.add_column("release_manifests", sa.Column("policy_version", sa.Integer, nullable=True))
    op.add_column(
        "release_manifests", sa.Column("policy_registry_sha256", SHA256, nullable=True)
    )
    op.create_check_constraint(
        "policy_pin_is_whole",
        "release_manifests",
        "(policy_version IS NULL) = (policy_registry_sha256 IS NULL)",
    )
    op.create_check_constraint(
        "policy_pin_digest_is_lowercase",
        "release_manifests",
        "policy_registry_sha256 IS NULL "
        "OR policy_registry_sha256 = lower(policy_registry_sha256)",
    )
    op.create_check_constraint(
        "policy_pin_version_positive",
        "release_manifests",
        "policy_version IS NULL OR policy_version > 0",
    )

    # ---------------------------------------------------------------- acceptance_records
    # Existing rows are classified, not judged. ``legacy-unverified`` is what they are:
    # written by the one-person path, with nothing recorded about the human. The default
    # stays on the column so a legacy writer cannot produce an unclassified row either.
    op.add_column(
        "acceptance_records",
        sa.Column(
            "attestation_version",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'legacy-unverified'"),
        ),
    )
    op.add_column("acceptance_records", sa.Column("proposal_id", INV_ID, nullable=True))
    op.create_foreign_key(
        "fk_acceptance_records_proposal",
        "acceptance_records",
        "release_acceptance_proposals",
        ["tenant_id", "proposal_id"],
        ["tenant_id", "proposal_id"],
    )
    op.create_check_constraint(
        "attestation_version_allowed",
        "acceptance_records",
        "attestation_version IN ('legacy-unverified','fresh-interactive-v1')",
    )
    # The forgery this contract exists to prevent, refused by the database: a row that
    # claims today's attestation for an ``accepted`` decision with no proposal -- and so
    # no two votes -- behind it.
    op.create_check_constraint(
        "attested_acceptance_names_its_proposal",
        "acceptance_records",
        "NOT (outcome = 'accepted' AND attestation_version = 'fresh-interactive-v1') "
        "OR proposal_id IS NOT NULL",
    )
    # One criterion, decided once, forever: that key cannot express a withdrawal followed
    # by a new decision. The slot's unique key replaces it and also governs the pending
    # state this one knew nothing about.
    op.drop_constraint(
        "uq_acceptance_records_release_criterion", "acceptance_records", type_="unique"
    )
    # 0005 granted UPDATE and DELETE. §4-1 takes them back: a decision that can be
    # edited is not a decision. PUBLIC is named too, so a future role that inherits from
    # it does not arrive holding them.
    op.execute(f"REVOKE UPDATE, DELETE ON acceptance_records FROM {APP_ROLE}")
    op.execute("REVOKE UPDATE, DELETE ON acceptance_records FROM PUBLIC")

    # ---------------------------------------------------------------- permission CHECK
    # The constraint 0027 created is unnamed, so PostgreSQL named it; drop by that name
    # if it is there and add a named one, which is also what makes this revision
    # re-runnable against a database that already has the wider set.
    op.execute(
        "ALTER TABLE inv.business_admin_grants "
        "DROP CONSTRAINT IF EXISTS business_admin_grants_permission_check"
    )
    op.execute(
        "ALTER TABLE inv.business_admin_grants "
        "DROP CONSTRAINT IF EXISTS business_admin_grants_permission_allowed"
    )
    allowed = ",".join(f"'{value}'" for value in PERMISSIONS)
    op.execute(
        "ALTER TABLE inv.business_admin_grants ADD CONSTRAINT "
        f"business_admin_grants_permission_allowed CHECK (permission IN ({allowed}))"
    )

    # ---------------------------------------------------------------- RLS and privileges
    # A tenant-only WITH CHECK was the first version and Codex measured what it allows:
    # with the actor scope set to one user, a row naming *another* user as proposer
    # inserted fine. Tenant isolation is not actor binding, and the application role holds
    # the INSERT, so the row's own actor column has to be checked by the policy.
    #
    # ``release_acceptance_actor_is_live`` answers the three questions the design asks of
    # every write (§2-1, §2-2): is this the human the request was verified as, is that
    # human still active, and do they hold ``releases.accept`` right now. It is
    # SECURITY INVOKER, takes no user argument it does not re-derive, and is used inside
    # the policies so the answer is enforced by the database rather than by whoever wrote
    # the INSERT.
    op.execute(
        f"""
        CREATE FUNCTION public.release_acceptance_actor_is_live(
            p_tenant uuid, p_actor text
        ) RETURNS boolean LANGUAGE sql SECURITY INVOKER STABLE AS $fn$
          SELECT p_actor IS NOT NULL
             AND p_actor = {ACTOR_EXPR}
             AND p_tenant = {TENANT_EXPR}
             AND EXISTS (
                   SELECT 1 FROM public.users u
                    WHERE u.tenant_id = p_tenant AND u.user_id = p_actor
                      AND u.status = 'active')
             AND public.business_admin_allowed(p_tenant, p_actor, 'releases.accept')
        $fn$
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.release_acceptance_actor_is_live(uuid,text) FROM PUBLIC"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.release_acceptance_actor_is_live(uuid,text) "
        f"TO {APP_ROLE}"
    )

    #: Which column names the human who wrote each row. The lifecycle table has none --
    #: an event is the system closing a proposal -- so it is bound to the acting human
    #: being live rather than to a column.
    actor_columns = {
        "release_acceptance_proposals": "proposed_by_user_id",
        "release_acceptance_votes": "user_id",
        "release_acceptance_withdrawals": "withdrawn_by_user_id",
        "release_acceptance_lifecycle_events": None,
    }
    for table in (*APPEND_ONLY, SLOT_TABLE):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        actor = actor_columns.get(table)
        bound = (
            f"public.release_acceptance_actor_is_live(tenant_id, {actor})"
            if actor
            else f"public.release_acceptance_actor_is_live(tenant_id, {ACTOR_EXPR})"
        )
        op.execute(
            f"CREATE POLICY {table}_tenant_isolation ON {table} FOR ALL TO {APP_ROLE} "
            f"USING (tenant_id = {TENANT_EXPR}) "
            f"WITH CHECK (tenant_id = {TENANT_EXPR} AND {bound})"
        )
    for table in APPEND_ONLY:
        op.execute(f"GRANT SELECT, INSERT ON {table} TO {APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT ON {SLOT_TABLE} TO {APP_ROLE}")
    op.execute(
        f"GRANT UPDATE ({', '.join(SLOT_UPDATE_COLUMNS)}) ON {SLOT_TABLE} TO {APP_ROLE}"
    )

    # ---------------------------------------------------------------- slot state machine
    # What a slot may do, enforced wherever the UPDATE comes from. The function is
    # SECURITY INVOKER, so the application role holds this UPDATE and could issue it
    # directly; this trigger is what makes that safe rather than a promise that it will
    # not happen.
    op.execute(
        "CREATE FUNCTION public.release_acceptance_slot_forward() RETURNS trigger "
        "LANGUAGE plpgsql AS $fn$ "
        "BEGIN "
        "  IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id "
        "     OR NEW.release_id IS DISTINCT FROM OLD.release_id "
        "     OR NEW.acceptance_id_ref IS DISTINCT FROM OLD.acceptance_id_ref "
        "     OR NEW.slot_id IS DISTINCT FROM OLD.slot_id THEN "
        "    RAISE EXCEPTION 'a coordination slot cannot change which criterion it is' "
        "      USING ERRCODE = 'check_violation', CONSTRAINT = 'slot_identity_is_fixed'; "
        "  END IF; "
        # A pending proposal leaves the slot only once it has been closed, and that is
        # checked against the lifecycle table rather than against the statement. The first
        # version compared OLD and NEW in one UPDATE, and Codex measured the hole: inside
        # one transaction, clearing the slot and then setting a different proposal passed
        # both times, because neither statement was a non-null to non-null replacement.
        # Asking "is the proposal this slot is giving up actually closed" has no such
        # seam -- there is no order of statements that satisfies it without the event.
        "  IF OLD.active_proposal_id IS NOT NULL "
        "     AND NEW.active_proposal_id IS DISTINCT FROM OLD.active_proposal_id "
        "     AND NOT EXISTS ( "
        "       SELECT 1 FROM release_acceptance_lifecycle_events e "
        "        WHERE e.proposal_id = OLD.active_proposal_id) THEN "
        "    RAISE EXCEPTION 'a pending proposal leaves the slot only when it is closed' "
        "      USING ERRCODE = 'check_violation', CONSTRAINT = 'slot_pending_is_exclusive'; "
        "  END IF; "
        # An active final decision is replaced only after it has been withdrawn. Without
        # this, recording a second decision on a criterion silently overwrote the first in
        # the slot and the release's sign-off changed with no withdrawal anywhere.
        "  IF OLD.active_acceptance_id IS NOT NULL "
        "     AND NEW.active_acceptance_id IS DISTINCT FROM OLD.active_acceptance_id "
        "     AND NOT EXISTS ( "
        "       SELECT 1 FROM release_acceptance_withdrawals w "
        "        WHERE w.acceptance_id = OLD.active_acceptance_id) THEN "
        "    RAISE EXCEPTION 'an active decision leaves the slot only when it is withdrawn' "
        "      USING ERRCODE = 'check_violation', CONSTRAINT = 'slot_final_is_exclusive'; "
        "  END IF; "
        # The row a slot names must be this criterion's. Without this the FK would be
        # satisfied by any proposal of any release in the tenant.
        "  IF NEW.active_proposal_id IS NOT NULL AND NOT EXISTS ( "
        "       SELECT 1 FROM release_acceptance_proposals p "
        "       WHERE p.tenant_id = NEW.tenant_id AND p.proposal_id = NEW.active_proposal_id "
        "         AND p.release_id = NEW.release_id "
        "         AND p.acceptance_id_ref = NEW.acceptance_id_ref) THEN "
        "    RAISE EXCEPTION 'a slot can only hold its own criterion''s proposal' "
        "      USING ERRCODE = 'check_violation', CONSTRAINT = 'slot_proposal_matches_criterion'; "
        "  END IF; "
        "  IF NEW.active_acceptance_id IS NOT NULL AND NOT EXISTS ( "
        "       SELECT 1 FROM acceptance_records a "
        "       WHERE a.tenant_id = NEW.tenant_id AND a.acceptance_id = NEW.active_acceptance_id "
        "         AND a.release_id = NEW.release_id "
        "         AND a.acceptance_id_ref = NEW.acceptance_id_ref) THEN "
        "    RAISE EXCEPTION 'a slot can only hold its own criterion''s decision' "
        "      USING ERRCODE = 'check_violation', CONSTRAINT = 'slot_decision_matches_criterion'; "
        "  END IF; "
        "  RETURN NEW; "
        "END $fn$"
    )
    op.execute(
        f"CREATE TRIGGER {SLOT_TABLE}_forward BEFORE UPDATE ON {SLOT_TABLE} "
        "FOR EACH ROW EXECUTE FUNCTION public.release_acceptance_slot_forward()"
    )

    # ---------------------------------------------------------------- canonical confirm
    # Takes no user ID: the acting human comes from inv.user_id, which only the request
    # path sets from a verified credential. Everything else is re-derived here, after the
    # caller's own checks, because the caller's checks ran before the locks.
    op.execute(
        """
        CREATE FUNCTION public.release_acceptance_confirm(
            p_proposal_id char(30),
            p_proposal_digest char(64),
            p_manifest_sha256 char(64),
            p_acceptance_id char(30),
            p_vote_id char(30),
            p_event_id char(30),
            p_identity_event_id char(30),
            p_attestation_version text,
            p_issuer text,
            p_client_id text,
            p_auth_time integer,
            p_amr_sha256 char(64),
            p_now timestamptz
        ) RETURNS char(30) LANGUAGE plpgsql SECURITY INVOKER AS $fn$
        DECLARE
            v_tenant uuid := NULLIF(current_setting('inv.tenant_id', true), '')::uuid;
            v_actor  text := NULLIF(current_setting('inv.user_id', true), '');
            v_proposal release_acceptance_proposals;
            v_manifest char(64);
            v_proposer text;
            v_votes integer;
        BEGIN
            IF v_tenant IS NULL OR v_actor IS NULL THEN
                RAISE EXCEPTION 'no verified human is in scope for this transaction'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF NOT EXISTS (SELECT 1 FROM users u
                           WHERE u.tenant_id = v_tenant AND u.user_id = v_actor
                             AND u.status = 'active') THEN
                RAISE EXCEPTION 'the acting user is not active'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF NOT public.business_admin_allowed(v_tenant, v_actor, 'releases.accept') THEN
                RAISE EXCEPTION 'the acting user may not accept releases'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;

            SELECT * INTO v_proposal FROM release_acceptance_proposals p
             WHERE p.tenant_id = v_tenant AND p.proposal_id = p_proposal_id;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'no such proposal' USING ERRCODE = 'no_data_found';
            END IF;
            IF v_proposal.proposal_digest IS DISTINCT FROM p_proposal_digest THEN
                RAISE EXCEPTION 'the confirmed digest is not this proposal''s'
                    USING ERRCODE = 'check_violation',
                          CONSTRAINT = 'confirm_digest_matches_proposal';
            END IF;
            IF p_now >= v_proposal.expires_at THEN
                RAISE EXCEPTION 'the proposal has expired'
                    USING ERRCODE = 'check_violation', CONSTRAINT = 'confirm_before_expiry';
            END IF;
            IF EXISTS (SELECT 1 FROM release_acceptance_lifecycle_events e
                        WHERE e.proposal_id = p_proposal_id) THEN
                RAISE EXCEPTION 'the proposal is already closed'
                    USING ERRCODE = 'check_violation', CONSTRAINT = 'confirm_once';
            END IF;

            -- The manifest under lock, not the caller's claim about it.
            SELECT m.manifest_sha256 INTO v_manifest FROM release_manifests m
             WHERE m.tenant_id = v_tenant AND m.release_id = v_proposal.release_id
             FOR UPDATE;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'no such release' USING ERRCODE = 'no_data_found';
            END IF;
            IF v_manifest IS DISTINCT FROM p_manifest_sha256
               OR v_manifest IS DISTINCT FROM v_proposal.target_manifest_sha256 THEN
                RAISE EXCEPTION 'the release composition has changed since the proposal'
                    USING ERRCODE = 'check_violation',
                          CONSTRAINT = 'confirm_manifest_unchanged';
            END IF;

            -- One existing vote, and it must be somebody else's. Counted here as well as
            -- constrained by uq_release_acceptance_votes_proposal_user, because the
            -- UNIQUE would report a duplicate key where the contract wants "the same
            -- person cannot be the quorum".
            SELECT count(*), max(v.user_id) INTO v_votes, v_proposer
              FROM release_acceptance_votes v WHERE v.proposal_id = p_proposal_id;
            IF v_votes <> 1 THEN
                RAISE EXCEPTION 'a proposal awaiting confirmation has exactly one vote'
                    USING ERRCODE = 'check_violation', CONSTRAINT = 'confirm_one_pending_vote';
            END IF;
            IF v_proposer = v_actor THEN
                RAISE EXCEPTION 'the proposer cannot be the second operator'
                    USING ERRCODE = 'insufficient_privilege',
                          CONSTRAINT = 'confirm_distinct_operators';
            END IF;

            INSERT INTO release_acceptance_votes(
                vote_id, tenant_id, proposal_id, user_id, vote_role,
                human_attestation_version, verified_issuer, verified_client_id,
                auth_time, amr_sha256, identity_verification_event_id, created_at)
            VALUES (p_vote_id, v_tenant, p_proposal_id, v_actor, 'confirmer',
                    p_attestation_version, p_issuer, p_client_id,
                    p_auth_time, p_amr_sha256, p_identity_event_id, p_now);

            INSERT INTO acceptance_records(
                acceptance_id, tenant_id, release_id, acceptance_id_ref, outcome,
                accepted_manifest_sha256, known_limitations, accepted_by_user_id,
                decided_at, attestation_version, proposal_id)
            VALUES (p_acceptance_id, v_tenant, v_proposal.release_id,
                    v_proposal.acceptance_id_ref, 'accepted', v_manifest, '[]'::jsonb,
                    v_actor, p_now, p_attestation_version, p_proposal_id);

            INSERT INTO release_acceptance_lifecycle_events(
                event_id, tenant_id, proposal_id, event_kind, acceptance_id, occurred_at)
            VALUES (p_event_id, v_tenant, p_proposal_id, 'confirmed', p_acceptance_id, p_now);

            UPDATE release_acceptance_slots s
               SET active_proposal_id = NULL,
                   active_acceptance_id = p_acceptance_id,
                   updated_at = p_now
             WHERE s.tenant_id = v_tenant AND s.release_id = v_proposal.release_id
               AND s.acceptance_id_ref = v_proposal.acceptance_id_ref
               AND s.active_proposal_id = p_proposal_id;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'the proposal is no longer the pending one'
                    USING ERRCODE = 'check_violation', CONSTRAINT = 'confirm_slot_still_pending';
            END IF;

            RETURN p_acceptance_id;
        END $fn$
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.release_acceptance_confirm("
        "char(30),char(64),char(64),char(30),char(30),char(30),char(30),text,text,text,"
        "integer,char(64),timestamptz) FROM PUBLIC"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.release_acceptance_confirm("
        "char(30),char(64),char(64),char(30),char(30),char(30),char(30),text,text,text,"
        f"integer,char(64),timestamptz) TO {APP_ROLE}"
    )


#: What must be absent for this revision to reverse. Each one is a thing the old shape
#: cannot hold, so the downgrade asks the database rather than assuming.
_BLOCKING_COUNTS = (
    (
        "SELECT count(*) FROM release_acceptance_proposals",
        "a release acceptance proposal exists",
    ),
    ("SELECT count(*) FROM release_acceptance_votes", "an operator vote exists"),
    (
        "SELECT count(*) FROM release_acceptance_withdrawals",
        "a withdrawal exists",
    ),
    (
        "SELECT count(*) FROM release_acceptance_lifecycle_events",
        "a proposal lifecycle event exists",
    ),
    (
        "SELECT count(*) FROM acceptance_records WHERE attestation_version = 'fresh-interactive-v1'",
        "an attested two-person acceptance exists",
    ),
    (
        "SELECT count(*) FROM (SELECT release_id, acceptance_id_ref FROM acceptance_records "
        "GROUP BY release_id, acceptance_id_ref HAVING count(*) > 1) AS d",
        "a criterion has been decided more than once, which the old unique key forbids",
    ),
    (
        "SELECT count(*) FROM inv.business_admin_grants WHERE permission = 'releases.accept'",
        "a releases.accept grant exists, which the old permission CHECK forbids",
    ),
)


def downgrade() -> None:
    """Reverse while nothing has been recorded, and refuse once anything has.

    An unconditional refusal was the first draft and it was wrong for a reason worth
    keeping: AC-11's ``migration-reversible-segment`` axis measures how far the head can
    roll back, and an irreversible head empties that segment. 0053-0056 all guard instead
    -- refuse while rows exist, otherwise drop empty structures -- and this revision has
    exactly that shape, so the segment stays four revisions long rather than becoming
    zero because a new table was added.

    The guards are the honest part. Each asks whether the *old* shape could hold what the
    new one now holds: a proposal, a vote, a withdrawal, a lifecycle event, an attested
    acceptance, two decisions on one criterion (which the restored unique key forbids), or
    a ``releases.accept`` grant (which the restored CHECK forbids). Any of them and the
    downgrade stops and names which, because dropping them would be deciding on an
    operator's behalf which recorded decision to discard.
    """
    connection = op.get_bind()
    for statement, reason in _BLOCKING_COUNTS:
        if connection.execute(sa.text(statement)).scalar_one():
            raise RuntimeError(
                "0057_release_acceptance_quorum cannot be reversed: "
                f"{reason}. Apply a reviewed forward fix instead of discarding it."
            )

    op.execute(f"DROP TRIGGER IF EXISTS {SLOT_TABLE}_forward ON {SLOT_TABLE}")
    op.execute(
        "DROP FUNCTION IF EXISTS public.release_acceptance_confirm("
        "char(30),char(64),char(64),char(30),char(30),char(30),char(30),text,text,text,"
        "integer,char(64),timestamptz)"
    )
    op.execute("DROP FUNCTION IF EXISTS public.release_acceptance_slot_forward()")
    op.execute(
        "DROP FUNCTION IF EXISTS public.release_acceptance_actor_is_live(uuid,text)"
    )

    # The permission CHECK and the grants 0005 gave, as they were.
    op.execute(
        "ALTER TABLE inv.business_admin_grants "
        "DROP CONSTRAINT IF EXISTS business_admin_grants_permission_allowed"
    )
    op.execute(
        "ALTER TABLE inv.business_admin_grants ADD CONSTRAINT "
        "business_admin_grants_permission_check "
        "CHECK (permission IN ('users.manage','resources.manage'))"
    )
    op.execute(f"GRANT UPDATE, DELETE ON acceptance_records TO {APP_ROLE}")

    op.drop_constraint(
        "attested_acceptance_names_its_proposal", "acceptance_records", type_="check"
    )
    op.drop_constraint("attestation_version_allowed", "acceptance_records", type_="check")
    op.drop_constraint("fk_acceptance_records_proposal", "acceptance_records", type_="foreignkey")
    op.drop_column("acceptance_records", "proposal_id")
    op.drop_column("acceptance_records", "attestation_version")
    op.create_unique_constraint(
        "uq_acceptance_records_release_criterion",
        "acceptance_records",
        ["release_id", "acceptance_id_ref"],
    )

    op.drop_constraint("policy_pin_version_positive", "release_manifests", type_="check")
    op.drop_constraint("policy_pin_digest_is_lowercase", "release_manifests", type_="check")
    op.drop_constraint("policy_pin_is_whole", "release_manifests", type_="check")
    op.drop_column("release_manifests", "policy_registry_sha256")
    op.drop_column("release_manifests", "policy_version")

    # Slot first: it is the only table that references the others.
    op.drop_table(SLOT_TABLE)
    op.drop_table("release_acceptance_lifecycle_events")
    op.drop_table("release_acceptance_withdrawals")
    op.drop_table("release_acceptance_votes")
    op.drop_table("release_acceptance_proposals")
