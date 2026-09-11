"""Scope the idempotency ledger by project and the inbox by tenant.

Revision ID: 0020_idempotency_and_inbox_scope
Revises: 0019_node_certificate_lookup
Create Date: 2026-09-10

Found by comparing the two implementations of these concepts after the
integration merge. ``public`` is authoritative, so the weaker constraint is the
one that has to move.

**Idempotency was not scoped by project.** The key was
``(tenant_id, endpoint, idempotency_key)``. Two projects in one tenant that use
the same client-chosen key — "deploy-1", "retry" — for the same endpoint would
collide, and the second project would silently receive the first project's
stored response instead of performing its own operation. ``inv.idempotency``
keys on ``(tenant, project, operation, key)`` and is right. ``project_id`` is
nullable because some endpoints are tenant-wide, and the unique index uses
NULLS NOT DISTINCT so those still collide with each other rather than becoming
unlimited duplicates.

**Inbox deduplication was not scoped by tenant.** The key was
``(consumer, event_id)``, so one tenant's processed event could suppress
another tenant's. ULID event ids make an accidental collision unrealistic, but
"unrealistic" is not the property a deduplication key should rest on, and a
deliberately chosen id is not unrealistic at all.

Both are rewrites of a unique constraint on tables whose existing rows remain
valid, so this revision is reversible.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0020_idempotency_and_inbox_scope"
down_revision = "0019_node_certificate_lookup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("idempotency_records", sa.Column("project_id", sa.CHAR(30)))
    op.drop_constraint(
        "uq_idempotency_records_scope_key", "idempotency_records", type_="unique"
    )
    # NULLS NOT DISTINCT: a tenant-wide operation has no project, and two of
    # them with the same key must still be the same operation.
    op.execute(
        "CREATE UNIQUE INDEX uq_idempotency_records_scope_key "
        "ON idempotency_records (tenant_id, project_id, endpoint, idempotency_key) "
        "NULLS NOT DISTINCT"
    )

    op.drop_constraint(
        "uq_inbox_events_consumer_event_id", "inbox_events", type_="unique"
    )
    op.create_unique_constraint(
        "uq_inbox_events_consumer_event_id",
        "inbox_events",
        ["tenant_id", "consumer", "event_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_inbox_events_consumer_event_id", "inbox_events", type_="unique"
    )
    op.create_unique_constraint(
        "uq_inbox_events_consumer_event_id", "inbox_events", ["consumer", "event_id"]
    )

    op.execute("DROP INDEX IF EXISTS uq_idempotency_records_scope_key")
    op.create_unique_constraint(
        "uq_idempotency_records_scope_key",
        "idempotency_records",
        ["tenant_id", "endpoint", "idempotency_key"],
    )
    op.drop_column("idempotency_records", "project_id")
