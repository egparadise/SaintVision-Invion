"""Stop editing, and record which moment a Run was approved for.

Revision ID: 0023_execution_handoff
Revises: 0022_inv_application_grants
Create Date: 2026-09-10

The business chain is: check the project permission, stop editing, freeze the
inputs, obtain a fresh approval, reserve resources, queue the execution, run it,
store the result. From "freeze the inputs" onward the execution core already
implements every step. The first two, and the record that ties the chain to one
moment, are what this adds.

``workspace_edit_locks`` — **stop editing.** Freezing inputs is only meaningful
if something stopped them changing first. Without a lock the freeze captures
whatever the workspace held when the read happened, and an editor's save landing
a moment later produces a Run whose approved inputs are not the inputs anyone
looked at. The lock stores the content digest at the moment editing stopped, so
the freeze can prove it captured *that* state and not a later one. One held lock
per workspace, by partial unique index: two callers quiescing the same workspace
for two different Runs is the race the lock exists to prevent, and a check in
application code loses that race.

``execution_bindings`` — **the identity and epoch mapping.** The two halves
already agree on identity: a public Run and an ``inv`` Run are the same string,
``run_`` plus the same 26-character Crockford ULID, and projects (``prj_``),
nodes (``nod_``) and workspaces (``wsp_``) match too. What an id cannot carry is
*when*. The execution core rolls a recovery epoch whenever an operator
reconciles after a restart, and every lease, claim and delivery is bound to the
epoch in force when it was made. Inputs frozen before a roll must not execute
after one — they describe a world that no longer exists.

So the binding records the epoch and the ``inv`` run version that the frozen
inputs and the approval were tied to, and every later step compares. That
comparison is the reason the table exists: an id alone cannot say whether the
thing it names is still the thing that was approved.

The one identity that did **not** match is fixed here too. ``public`` minted
approvals as ``apv_`` while ``inv.approval_requests`` has
``CHECK(approval_id ~ '^apr_...')``. One value could not be written to both
sides, which makes an approval unmappable across exactly the seam it has to
cross. ``apr`` wins: it is enforced by a constraint, it is already in the web
client's types, and ``apv`` existed in one dictionary entry and three call
sites. Being authoritative for a concept does not mean winning every spelling.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0023_execution_handoff"
down_revision = "0022_inv_application_grants"
branch_labels = None
depends_on = None

INV_ID = sa.CHAR(30)
SHA256 = sa.CHAR(64)
UUID = postgresql.UUID(as_uuid=True)
TS = sa.DateTime(timezone=True)

APP_ROLE = "inv_app"
TENANT_EXPR = "NULLIF(current_setting('inv.tenant_id', true), '')::uuid"

NEW_TENANT_SCOPED = ("workspace_edit_locks", "execution_bindings")


def _now():
    return sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "workspace_edit_locks",
        sa.Column("lock_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("workspace_id", INV_ID, nullable=False),
        sa.Column("run_id", INV_ID, nullable=False),
        sa.Column("held_by_user_id", INV_ID, nullable=False),
        sa.Column("content_sha256", SHA256, nullable=False),
        sa.Column("reason", sa.String(64), nullable=False, server_default="execution"),
        sa.Column("acquired_at", TS, nullable=False, server_default=_now()),
        sa.Column("released_at", TS),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "workspace_id"],
            ["workspaces.tenant_id", "workspaces.workspace_id"],
            name="fk_workspace_edit_locks_tenant_id_workspace_id",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "run_id"],
            ["runs.tenant_id", "runs.run_id"],
            name="fk_workspace_edit_locks_tenant_id_run_id",
        ),
        sa.UniqueConstraint(
            "tenant_id", "lock_id", name="uq_workspace_edit_locks_tenant_id_lock_id"
        ),
        sa.CheckConstraint(
            "released_at IS NULL OR released_at >= acquired_at",
            name="release_follows_acquisition",
        ),
        sa.CheckConstraint(
            "content_sha256 = lower(content_sha256)", name="digest_is_lowercase"
        ),
    )
    # One held lock per workspace. Released rows stay as history, which is why
    # this is a partial index and not a plain unique constraint.
    op.execute(
        "CREATE UNIQUE INDEX uq_workspace_edit_locks_held "
        "ON workspace_edit_locks (tenant_id, workspace_id) "
        "WHERE released_at IS NULL"
    )
    op.create_index(
        "ix_workspace_edit_locks_tenant_id_run_id",
        "workspace_edit_locks",
        ["tenant_id", "run_id"],
    )

    op.create_table(
        "execution_bindings",
        sa.Column("binding_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("project_id", INV_ID, nullable=False),
        sa.Column("run_id", INV_ID, nullable=False),
        sa.Column("workspace_id", INV_ID, nullable=False),
        sa.Column("lock_id", INV_ID, nullable=False),
        sa.Column("recovery_epoch", UUID, nullable=False),
        sa.Column("bound_run_version", sa.BigInteger, nullable=False),
        sa.Column("source_attempt", sa.Integer, nullable=False),
        sa.Column("resume_id", UUID),
        sa.Column("checkout_id", UUID),
        sa.Column("input_sha256", SHA256, nullable=False),
        sa.Column("input_size_bytes", sa.BigInteger, nullable=False),
        sa.Column("step_id", sa.String(200), nullable=False),
        sa.Column("approval_id", sa.String(30)),
        sa.Column("permission_snapshot_id", INV_ID),
        sa.Column("state", sa.String(16), nullable=False, server_default="frozen"),
        sa.Column("created_by_user_id", INV_ID, nullable=False),
        sa.Column("created_at", TS, nullable=False, server_default=_now()),
        sa.Column("settled_at", TS),
        sa.Column("note", sa.String(200)),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "run_id"],
            ["runs.tenant_id", "runs.run_id"],
            name="fk_execution_bindings_tenant_id_run_id",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "project_id"],
            ["projects.tenant_id", "projects.project_id"],
            name="fk_execution_bindings_tenant_id_project_id",
        ),
        # The binding cannot exist without the lock it froze under. This is the
        # link that makes "the inputs were still when we read them" a fact the
        # schema holds rather than a claim the service makes.
        sa.ForeignKeyConstraint(
            ["tenant_id", "lock_id"],
            ["workspace_edit_locks.tenant_id", "workspace_edit_locks.lock_id"],
            name="fk_execution_bindings_tenant_id_lock_id",
        ),
        sa.UniqueConstraint(
            "tenant_id", "binding_id", name="uq_execution_bindings_tenant_id_binding_id"
        ),
        # One binding per (run, epoch, version). A Run may be bound more than
        # once — that is a recovery attempt — but never twice for one moment,
        # which would be two approvals for the same decision.
        sa.UniqueConstraint(
            "tenant_id",
            "run_id",
            "recovery_epoch",
            "bound_run_version",
            name="uq_execution_bindings_run_epoch_version",
        ),
        sa.CheckConstraint(
            "state IN ('frozen','approved','queued','executing','settled','abandoned')",
            name="state_allowed",
        ),
        sa.CheckConstraint("bound_run_version > 0", name="bound_version_positive"),
        sa.CheckConstraint("source_attempt >= 1", name="source_attempt_positive"),
        sa.CheckConstraint("input_size_bytes >= 0", name="input_size_non_negative"),
        sa.CheckConstraint(
            "input_sha256 = lower(input_sha256)", name="digest_is_lowercase"
        ),
        sa.CheckConstraint(
            "(state = 'frozen') = (approval_id IS NULL)",
            name="approval_paired_to_state",
        ),
        # The execution core's spelling, enforced here so an unmappable id
        # cannot be stored on this side and discovered at the seam.
        sa.CheckConstraint(
            "approval_id IS NULL OR approval_id ~ '^apr_[0-9A-HJKMNP-TV-Z]{26}$'",
            name="approval_id_is_a_core_approval",
        ),
        sa.CheckConstraint(
            "(state IN ('settled','abandoned')) = (settled_at IS NOT NULL)",
            name="settlement_paired",
        ),
    )
    op.create_index(
        "ix_execution_bindings_tenant_id_state",
        "execution_bindings",
        ["tenant_id", "state"],
    )
    op.create_index(
        "ix_execution_bindings_tenant_id_recovery_epoch",
        "execution_bindings",
        ["tenant_id", "recovery_epoch"],
    )

    for table in NEW_TENANT_SCOPED:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO {APP_ROLE}")
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_tenant_isolation ON {table} FOR ALL TO {APP_ROLE} "
            f"USING (tenant_id = {TENANT_EXPR}) WITH CHECK (tenant_id = {TENANT_EXPR})"
        )

    # One approval id, spelled one way, so it can cross the seam it has to.
    op.execute("UPDATE approvals SET approval_id = 'apr_' || substr(approval_id, 5)")
    op.create_check_constraint(
        "approval_id_prefix",
        "approvals",
        "approval_id ~ '^apr_[0-9A-HJKMNP-TV-Z]{26}$'",
    )


def downgrade() -> None:
    op.drop_constraint("approval_id_prefix", "approvals", type_="check")
    op.execute("UPDATE approvals SET approval_id = 'apv_' || substr(approval_id, 5)")
    for table in ("execution_bindings", "workspace_edit_locks"):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
