"""Seed the first recovery epoch, so a migrated database can start.

Revision ID: 0024_initial_recovery_epoch
Revises: 0023_execution_handoff
Create Date: 2026-09-10

``inv.control_epoch`` is created empty and never populated by any migration.
Every ``inv.db.Database.transaction`` reads it before doing anything:

    epoch = conn.execute("SELECT epoch FROM inv.control_epoch WHERE singleton FOR SHARE")
    if not epoch or str(epoch["epoch"]) != self.recovery_epoch:
        raise DomainError("LEASE-0004", "Recovery epoch requires operator reconciliation", 503)

With no row, every transaction fails. This is the same shape as the missing
grants in 0022: something the execution core cannot start without, existing only
in ``tests/integration/conftest.py``, where the fixture inserts one per test.

Rolling the epoch **is** an operator act — it is how a control plane declares
that everything it held before a restart is void, and no migration should ever
do that. But the *first* epoch is not a reconciliation. A database that has
never run has nothing to reconcile, and refusing to start until an operator
performs a recovery ritual for a system that has never recovered from anything
is a worse default than a fresh value.

So this seeds one, and ``ON CONFLICT DO NOTHING`` makes it a no-op forever
after: if an operator has rolled the epoch, or if this revision is replayed,
the value in the table is the one that stays. The migration can create the
first epoch and can never overwrite a later one.
"""

from __future__ import annotations

from alembic import op

revision = "0024_initial_recovery_epoch"
down_revision = "0023_execution_handoff"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "INSERT INTO inv.control_epoch (singleton, epoch) "
        "VALUES (true, gen_random_uuid()) ON CONFLICT (singleton) DO NOTHING"
    )


def downgrade() -> None:
    # Deliberately not deleting the row. Removing the epoch would make every
    # execution-core transaction fail, and a downgrade that breaks the running
    # system more thoroughly than the thing it reverses is not a rollback.
    pass
