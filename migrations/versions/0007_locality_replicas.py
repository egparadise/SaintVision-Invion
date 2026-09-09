"""Data replicas and measured node links.

Revision ID: 0007_locality_replicas
Revises: 0006_discovery_pools_placement
Create Date: 2026-09-10

Pooling storage usefully means knowing which machine already holds the bytes,
so work can go to the data rather than the data to the work.

The constraints encode the two places an optimistic default would produce a
wrong schedule rather than a slow one:

* ``ready_requires_verification`` — a replica is usable only when its checksum
  matched. Scheduling onto unverified bytes yields a confidently wrong result.
* ``bandwidth_positive`` plus the absence of a row — a link is measured or it
  is unknown. ADR-011 forbids calling an unmeasured link zero seconds, and
  there is no default row to make that mistake with.

Partitioned tables: none. Append-only: none.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007_locality_replicas"
down_revision = "0006_discovery_pools_placement"
branch_labels = None
depends_on = None

INV_ID = sa.CHAR(30)
SHA256 = sa.CHAR(64)
UUID = postgresql.UUID(as_uuid=True)
TS = sa.DateTime(timezone=True)

APP_ROLE = "inv_app"
TENANT_EXPR = "NULLIF(current_setting('inv.tenant_id', true), '')::uuid"

NEW_TENANT_SCOPED = ("data_replicas", "node_links")


def _now():
    return sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "data_replicas",
        sa.Column("replica_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("location_id", INV_ID, nullable=False),
        sa.Column("node_id", INV_ID, nullable=False),
        sa.Column("contribution_id", INV_ID, nullable=False),
        sa.Column("state", sa.String(16), nullable=False, server_default="transferring"),
        sa.Column("local_bytes", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("checksum_sha256", SHA256),
        sa.Column("verified_at", TS),
        sa.Column("pinned_until", TS),
        sa.Column("last_used_at", TS, nullable=False, server_default=_now()),
        sa.Column("created_at", TS, nullable=False, server_default=_now()),
        sa.ForeignKeyConstraint(
            ["tenant_id", "location_id"],
            ["data_locations.tenant_id", "data_locations.location_id"],
            name="fk_data_replicas_tenant_id_location_id",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "node_id"], ["nodes.tenant_id", "nodes.node_id"],
            name="fk_data_replicas_tenant_id_node_id",
        ),
        sa.UniqueConstraint(
            "tenant_id", "replica_id", name="uq_data_replicas_tenant_id_replica_id"
        ),
        sa.UniqueConstraint(
            "location_id", "node_id", name="uq_data_replicas_location_id_node_id"
        ),
        sa.CheckConstraint(
            "state IN ('transferring','ready','stale','corrupt','evicted')",
            name="state_allowed",
        ),
        sa.CheckConstraint("local_bytes >= 0", name="local_bytes_non_negative"),
        sa.CheckConstraint(
            "state <> 'ready' OR (checksum_sha256 IS NOT NULL AND verified_at IS NOT NULL)",
            name="ready_requires_verification",
        ),
        sa.CheckConstraint(
            "pinned_until IS NULL OR state = 'ready'", name="only_ready_replicas_pin"
        ),
    )
    op.create_index("ix_data_replicas_tenant_id_node_id", "data_replicas", ["tenant_id", "node_id"])
    op.create_index(
        "ix_data_replicas_tenant_id_location_id", "data_replicas", ["tenant_id", "location_id"]
    )
    op.create_index("ix_data_replicas_last_used_at", "data_replicas", ["last_used_at"])

    op.create_table(
        "node_links",
        sa.Column("tenant_id", UUID, primary_key=True),
        sa.Column("from_node_id", INV_ID, primary_key=True),
        sa.Column("to_node_id", INV_ID, primary_key=True),
        sa.Column("bits_per_second", sa.BigInteger, nullable=False),
        sa.Column("sample_count", sa.Integer, nullable=False, server_default="1"),
        sa.Column("measured_at", TS, nullable=False, server_default=_now()),
        sa.Column("note", sa.Text),
        sa.ForeignKeyConstraint(
            ["tenant_id", "from_node_id"], ["nodes.tenant_id", "nodes.node_id"],
            name="fk_node_links_tenant_id_from_node_id",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "to_node_id"], ["nodes.tenant_id", "nodes.node_id"],
            name="fk_node_links_tenant_id_to_node_id",
        ),
        sa.UniqueConstraint(
            "tenant_id", "from_node_id", "to_node_id", name="uq_node_links_pair"
        ),
        sa.CheckConstraint("bits_per_second > 0", name="bandwidth_positive"),
        sa.CheckConstraint("from_node_id <> to_node_id", name="link_is_between_two_nodes"),
        sa.CheckConstraint("sample_count >= 1", name="sample_count_positive"),
    )
    op.create_index("ix_node_links_tenant_id_measured_at", "node_links", ["tenant_id", "measured_at"])

    for table in NEW_TENANT_SCOPED:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO {APP_ROLE}")
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_tenant_isolation ON {table} FOR ALL TO {APP_ROLE} "
            f"USING (tenant_id = {TENANT_EXPR}) WITH CHECK (tenant_id = {TENANT_EXPR})"
        )


def downgrade() -> None:
    for table in ("node_links", "data_replicas"):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
