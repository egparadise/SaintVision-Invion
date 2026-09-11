"""Give the execution core a role it can actually connect as.

Revision ID: 0022_inv_application_grants
Revises: 0021_canonical_resource_units
Create Date: 2026-09-10

Eighteen ``inv`` migrations contain zero ``GRANT`` statements. That reads like a
missing hardening step; it is not. ``inv.db.Database.transaction`` opens every
connection with:

    SELECT r.rolsuper, r.rolbypassrls, r.oid = n.nspowner AS owns_schema ...
    if not role or any(role.values()):
        raise DomainError("AUTH-0020", "Runtime must use a non-owner role ...")

The runtime **refuses** to run as a superuser, as a BYPASSRLS role, or as the
schema owner. So there is no fallback: with no grant to any other role, the
execution core cannot open a connection at all. It is not deployable, and the
only reason the suite is green is that ``tests/integration/conftest.py`` creates
a role per test and grants it fifteen carefully scoped privileges.

That fixture is where the entire least-privilege design currently lives —
including the parts that are genuinely subtle:

* ``evidence`` and ``checkpoints`` get INSERT and nothing else. They are
  append-only by trigger; the grant says so as well, so the trigger is the
  second line rather than the only one.
* ``control_epoch`` gets ``UPDATE(singleton)`` and no other write. The code
  takes ``SELECT ... FOR SHARE`` on it, and PostgreSQL requires an UPDATE
  privilege to lock a row — but ``CHECK(singleton)`` pins the only column the
  grant names, so the lock is possible and the epoch stays read-only.
* ``project_grants``, ``project_nodes`` and ``node_channels`` get
  ``UPDATE(lock_sentinel)`` for the same reason: lockable, not editable. The
  application can prove a project's membership did not change under it without
  being able to change it.

None of that is test scaffolding. It is the authorisation model, and it belongs
in the schema next to the row level security it complements. This revision
moves it there, granted to ``inv_app`` — the same NOLOGIN NOBYPASSRLS role that
``public`` already grants, so both halves are reachable by one connection and a
single transaction can span the seam.

**On ``ON ALL TABLES``.** It is a snapshot, not a rule: it covers the tables
that exist when it runs, and a table added by a later revision is not included.
``ALTER DEFAULT PRIVILEGES`` would cover them automatically and is the wrong
answer here — it would hand DELETE to the next append-only ledger someone adds,
silently, which is the opposite of what the careful revokes above are for. So
the grant stays explicit and ``tests/test_inv_grants.py`` fails when an ``inv``
table has no decision recorded about it. A new table then forces a choice
instead of being either unreachable or over-privileged.
"""

from __future__ import annotations

from alembic import op

revision = "0022_inv_application_grants"
down_revision = "0021_canonical_resource_units"
branch_labels = None
depends_on = None

APP_ROLE = "inv_app"

#: Append-only ledgers: rows may be added and never altered or removed. A
#: trigger already refuses UPDATE and DELETE; withholding the privilege means
#: the attempt fails before it reaches the trigger.
INSERT_ONLY = ("inv.evidence", "inv.checkpoints")

#: Tables the application must be able to *lock* but never write. PostgreSQL
#: requires an UPDATE privilege for SELECT ... FOR SHARE, so the grant names a
#: single column that a CHECK constraint pins to one value.
LOCK_SENTINEL_ONLY = ("inv.project_grants", "inv.project_nodes", "inv.node_channels")

#: Rows that may be written once and then stand as the record of what happened.
APPEND_THEN_FROZEN = (
    "inv.approval_votes",
    "inv.approval_dispatches",
    "inv.approval_audit",
    "inv.tool_claims",
    "inv.node_stop_receipts",
)

#: Read-only to the application: written by operators, never by a request.
READ_ONLY = ("inv.node_channel_audit",)


def upgrade() -> None:
    op.execute(f"GRANT USAGE ON SCHEMA inv TO {APP_ROLE}")
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA inv TO {APP_ROLE}"
    )
    op.execute(f"GRANT USAGE ON ALL SEQUENCES IN SCHEMA inv TO {APP_ROLE}")

    # Now take back everything the application must not have. Granting broadly
    # and revoking precisely is how the fixture does it, and the order matters:
    # a revoke before its grant is silently undone.
    op.execute(
        "REVOKE INSERT, UPDATE, DELETE ON inv.control_epoch, "
        f"{', '.join(INSERT_ONLY)} FROM {APP_ROLE}"
    )
    op.execute(f"GRANT INSERT ON {', '.join(INSERT_ONLY)} TO {APP_ROLE}")
    # Lockable, not writable. CHECK(singleton) pins the named column.
    op.execute(f"GRANT UPDATE (singleton) ON inv.control_epoch TO {APP_ROLE}")

    op.execute(
        f"REVOKE INSERT, UPDATE, DELETE ON {', '.join(LOCK_SENTINEL_ONLY[:2])} "
        f"FROM {APP_ROLE}"
    )
    op.execute(
        f"REVOKE INSERT, UPDATE, DELETE ON inv.node_channels, {', '.join(READ_ONLY)} "
        f"FROM {APP_ROLE}"
    )
    for table in LOCK_SENTINEL_ONLY:
        op.execute(f"GRANT UPDATE (lock_sentinel) ON {table} TO {APP_ROLE}")

    op.execute(
        f"REVOKE UPDATE, DELETE ON {', '.join(APPEND_THEN_FROZEN)} FROM {APP_ROLE}"
    )


def downgrade() -> None:
    # Revoking USAGE on the schema makes every table grant inside it
    # unreachable, so this is the whole reversal.
    op.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA inv FROM {APP_ROLE}")
    op.execute(f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA inv FROM {APP_ROLE}")
    op.execute(f"REVOKE USAGE ON SCHEMA inv FROM {APP_ROLE}")
