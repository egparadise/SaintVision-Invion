"""S02 baseline: identity, node observation, storage catalogue, operations.

Revision ID: 0001_s02_baseline
Revises:
Create Date: 2026-09-09

Scope is S02 only (S02-DB, S02-ST). Workspace, workload, run, lease, allocation
and evidence tables are S03+ and belong to their owners; they are deliberately
absent rather than stubbed, so that no one reads a placeholder as a contract.

Not included, and why:

* fencing sequence — ADR-006 requires it to be created before the allocation
  table it fences. There is no allocation table until S05, and creating a bare
  sequence now would imply a contract this sprint does not define.
* pgvector columns — ADR-009 forbids fixing an embedding dimension before the
  model is chosen. The extension is not enabled here.

Downgrade drops everything this revision created. That is safe only because it
is the initial revision against an empty schema; later irreversible revisions
must state a restore/forward-fix plan instead (PLAN-DB-001).
"""

from __future__ import annotations

import datetime as dt

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_s02_baseline"
down_revision = None
branch_labels = None
depends_on = None

INV_ID = sa.CHAR(30)
SHA256 = sa.CHAR(64)
TRACE_ID = sa.CHAR(32)
UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB
QTY = sa.NUMERIC(20, 4)
TS = sa.DateTime(timezone=True)

TENANT_SCOPED = (
    "users",
    "roles",
    "user_roles",
    "projects",
    "project_members",
    "nodes",
    "node_bootstrap_tokens",
    "node_capabilities",
    "resource_offers",
    "resource_snapshots",
    "storage_contributions",
    "data_locations",
    "idempotency_records",
)

APP_ROLE = "inv_app"
TENANT_EXPR = "NULLIF(current_setting('inv.tenant_id', true), '')::uuid"


def _now() -> sa.sql.elements.TextClause:
    return sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("tenant_id", UUID, primary_key=True),
        sa.Column("slug", sa.String(64), nullable=False, unique=True),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("created_at", TS, nullable=False, server_default=_now()),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
    )

    op.create_table(
        "users",
        sa.Column("user_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.tenant_id"), nullable=False),
        sa.Column("external_subject", sa.String(255), nullable=False),
        sa.Column("email", sa.String(320)),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("created_at", TS, nullable=False, server_default=_now()),
        sa.Column("updated_at", TS, nullable=False, server_default=_now()),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.UniqueConstraint("tenant_id", "external_subject", name="uq_users_tenant_id_external_subject"),
        sa.UniqueConstraint("tenant_id", "user_id", name="uq_users_tenant_id_user_id"),
        sa.CheckConstraint("status IN ('active','suspended','retired')", name="status_allowed"),
    )

    op.create_table(
        "roles",
        sa.Column("role_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.tenant_id"), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("created_at", TS, nullable=False, server_default=_now()),
        sa.UniqueConstraint("tenant_id", "code", name="uq_roles_tenant_id_code"),
        sa.UniqueConstraint("tenant_id", "role_id", name="uq_roles_tenant_id_role_id"),
    )

    op.create_table(
        "user_roles",
        sa.Column("tenant_id", UUID, primary_key=True),
        sa.Column("user_id", INV_ID, primary_key=True),
        sa.Column("role_id", INV_ID, primary_key=True),
        sa.Column("granted_at", TS, nullable=False, server_default=_now()),
        sa.ForeignKeyConstraint(
            ["tenant_id", "user_id"],
            ["users.tenant_id", "users.user_id"],
            name="fk_user_roles_tenant_id_user_id",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "role_id"],
            ["roles.tenant_id", "roles.role_id"],
            name="fk_user_roles_tenant_id_role_id",
        ),
    )

    op.create_table(
        "projects",
        sa.Column("project_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.tenant_id"), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("created_at", TS, nullable=False, server_default=_now()),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.UniqueConstraint("tenant_id", "code", name="uq_projects_tenant_id_code"),
        sa.UniqueConstraint("tenant_id", "project_id", name="uq_projects_tenant_id_project_id"),
        sa.CheckConstraint("status IN ('active','archived')", name="status_allowed"),
    )

    op.create_table(
        "project_members",
        sa.Column("tenant_id", UUID, primary_key=True),
        sa.Column("project_id", INV_ID, primary_key=True),
        sa.Column("user_id", INV_ID, primary_key=True),
        sa.Column("role_code", sa.String(64), nullable=False),
        sa.Column("granted_at", TS, nullable=False, server_default=_now()),
        sa.ForeignKeyConstraint(
            ["tenant_id", "project_id"],
            ["projects.tenant_id", "projects.project_id"],
            name="fk_project_members_tenant_id_project_id",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "user_id"],
            ["users.tenant_id", "users.user_id"],
            name="fk_project_members_tenant_id_user_id",
        ),
    )
    op.create_index("ix_project_members_tenant_id_user_id", "project_members", ["tenant_id", "user_id"])

    op.create_table(
        "nodes",
        sa.Column("node_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.tenant_id"), nullable=False),
        sa.Column("hostname", sa.String(253), nullable=False),
        sa.Column("os_type", sa.String(16), nullable=False),
        sa.Column("os_version", sa.String(64), nullable=False),
        sa.Column("agent_version", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="enrolling"),
        sa.Column("certificate_fingerprint", SHA256),
        sa.Column("labels", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("enrolled_at", TS, nullable=False, server_default=_now()),
        sa.Column("last_heartbeat_at", TS),
        sa.Column("heartbeat_sequence", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.UniqueConstraint("tenant_id", "hostname", name="uq_nodes_tenant_id_hostname"),
        sa.UniqueConstraint("tenant_id", "node_id", name="uq_nodes_tenant_id_node_id"),
        sa.CheckConstraint(
            "status IN ('enrolling','active','draining','lost','retired')",
            name="status_allowed",
        ),
        sa.CheckConstraint("heartbeat_sequence >= 0", name="heartbeat_sequence_non_negative"),
    )
    # Unique when present. NULL means enrollment has not completed, a state
    # many nodes legitimately share, so this is a partial index; NULLS NOT
    # DISTINCT here would cap the platform at one unenrolled node.
    op.execute(
        "CREATE UNIQUE INDEX uq_nodes_certificate_fingerprint ON nodes "
        "(certificate_fingerprint) WHERE certificate_fingerprint IS NOT NULL"
    )
    op.create_index("ix_nodes_tenant_id_status", "nodes", ["tenant_id", "status"])
    op.create_index("ix_nodes_tenant_id_last_heartbeat_at", "nodes", ["tenant_id", "last_heartbeat_at"])

    op.create_table(
        "node_bootstrap_tokens",
        sa.Column("token_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.tenant_id"), nullable=False),
        sa.Column("token_sha256", SHA256, nullable=False),
        sa.Column("issued_by_user_id", INV_ID, nullable=False),
        sa.Column("issued_at", TS, nullable=False, server_default=_now()),
        sa.Column("expires_at", TS, nullable=False),
        sa.Column("consumed_at", TS),
        sa.Column("consumed_by_node_id", INV_ID),
        sa.UniqueConstraint("token_sha256", name="uq_node_bootstrap_tokens_token_sha256"),
        sa.CheckConstraint(
            "(consumed_at IS NULL) = (consumed_by_node_id IS NULL)",
            name="consumption_paired",
        ),
    )
    op.create_index(
        "ix_node_bootstrap_tokens_tenant_id_expires_at",
        "node_bootstrap_tokens",
        ["tenant_id", "expires_at"],
    )

    op.create_table(
        "node_capabilities",
        sa.Column("capability_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("node_id", INV_ID, nullable=False),
        sa.Column("kind", sa.String(8), nullable=False),
        sa.Column("device_index", sa.Integer),
        sa.Column("vendor", sa.String(64)),
        sa.Column("model", sa.String(128)),
        sa.Column("total_quantity", QTY, nullable=False),
        sa.Column("unit", sa.String(16), nullable=False),
        sa.Column("divisible", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("detected_at", TS, nullable=False, server_default=_now()),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "node_id"],
            ["nodes.tenant_id", "nodes.node_id"],
            name="fk_node_capabilities_tenant_id_node_id",
        ),
        sa.UniqueConstraint("tenant_id", "capability_id", name="uq_node_capabilities_tenant_id_capability_id"),
        sa.CheckConstraint("kind IN ('cpu','gpu','ram','disk')", name="kind_allowed"),
        sa.CheckConstraint("total_quantity >= 0", name="total_non_negative"),
        sa.CheckConstraint(
            "(kind = 'gpu') = (device_index IS NOT NULL)",
            name="device_index_gpu_only",
        ),
    )
    # device_index is NULL for whole-host resources; without NULLS NOT DISTINCT
    # a node could register "the RAM" more than once.
    op.execute(
        "ALTER TABLE node_capabilities ADD CONSTRAINT uq_node_capabilities_node_id_kind_device_index "
        "UNIQUE NULLS NOT DISTINCT (node_id, kind, device_index)"
    )

    op.create_table(
        "resource_offers",
        sa.Column("offer_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("capability_id", INV_ID, nullable=False),
        sa.Column("offered_quantity", QTY, nullable=False),
        sa.Column("unit", sa.String(16), nullable=False),
        sa.Column("effective_from", TS, nullable=False, server_default=_now()),
        sa.Column("effective_to", TS),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "capability_id"],
            ["node_capabilities.tenant_id", "node_capabilities.capability_id"],
            name="fk_resource_offers_tenant_id_capability_id",
        ),
        sa.UniqueConstraint("tenant_id", "offer_id", name="uq_resource_offers_tenant_id_offer_id"),
        sa.CheckConstraint("offered_quantity >= 0", name="offered_non_negative"),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to > effective_from",
            name="effective_range_ordered",
        ),
    )
    op.create_index("ix_resource_offers_tenant_id_capability_id", "resource_offers", ["tenant_id", "capability_id"])

    op.create_table(
        "resource_snapshots",
        sa.Column("snapshot_id", INV_ID, primary_key=True),
        sa.Column("observed_at", TS, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("node_id", INV_ID, nullable=False),
        sa.Column("capability_id", INV_ID, nullable=False),
        sa.Column("used_quantity", QTY, nullable=False),
        sa.Column("unit", sa.String(16), nullable=False),
        sa.Column("detail", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.CheckConstraint("used_quantity >= 0", name="used_non_negative"),
        postgresql_partition_by="RANGE (observed_at)",
    )
    op.create_index("ix_resource_snapshots_tenant_id_observed_at", "resource_snapshots", ["tenant_id", "observed_at"])
    op.create_index("ix_resource_snapshots_node_id_observed_at", "resource_snapshots", ["node_id", "observed_at"])

    op.create_table(
        "storage_contributions",
        sa.Column("contribution_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("node_id", INV_ID, nullable=False),
        sa.Column("declared_path", sa.Text, nullable=False),
        sa.Column("normalized_path", sa.Text, nullable=False),
        sa.Column("mode", sa.String(16), nullable=False, server_default="read_only"),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("capacity_bytes", sa.BigInteger),
        sa.Column("available_bytes", sa.BigInteger),
        sa.Column("registered_by_user_id", INV_ID, nullable=False),
        sa.Column("registered_at", TS, nullable=False, server_default=_now()),
        sa.Column("revoked_at", TS),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "node_id"],
            ["nodes.tenant_id", "nodes.node_id"],
            name="fk_storage_contributions_tenant_id_node_id",
        ),
        sa.UniqueConstraint(
            "tenant_id", "contribution_id", name="uq_storage_contributions_tenant_id_contribution_id"
        ),
        sa.UniqueConstraint(
            "node_id", "normalized_path", name="uq_storage_contributions_node_id_normalized_path"
        ),
        sa.CheckConstraint("mode IN ('read_only','read_write')", name="mode_allowed"),
        sa.CheckConstraint(
            "status IN ('pending','active','revoked')",
            name="status_allowed",
        ),
        sa.CheckConstraint(
            "capacity_bytes IS NULL OR capacity_bytes >= 0",
            name="capacity_non_negative",
        ),
        sa.CheckConstraint(
            "(status = 'revoked') = (revoked_at IS NOT NULL)",
            name="revocation_paired",
        ),
    )
    op.create_index("ix_storage_contributions_tenant_id_status", "storage_contributions", ["tenant_id", "status"])

    op.create_table(
        "data_locations",
        sa.Column("location_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("contribution_id", INV_ID, nullable=False),
        sa.Column("uri", sa.Text, nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("relative_path", sa.Text, nullable=False),
        sa.Column("byte_size", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("checksum_sha256", SHA256),
        sa.Column("verified_at", TS),
        sa.Column("ready", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("retention_pinned_until", TS),
        sa.Column("catalogued_at", TS, nullable=False, server_default=_now()),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "contribution_id"],
            ["storage_contributions.tenant_id", "storage_contributions.contribution_id"],
            name="fk_data_locations_tenant_id_contribution_id",
        ),
        sa.UniqueConstraint("tenant_id", "location_id", name="uq_data_locations_tenant_id_location_id"),
        sa.UniqueConstraint("tenant_id", "uri", name="uq_data_locations_tenant_id_uri"),
        sa.CheckConstraint(
            "kind IN ('dataset','model','artifact','workspace')",
            name="kind_allowed",
        ),
        sa.CheckConstraint("byte_size >= 0", name="byte_size_non_negative"),
        sa.CheckConstraint(
            "NOT ready OR (checksum_sha256 IS NOT NULL AND verified_at IS NOT NULL)",
            name="ready_requires_verification",
        ),
    )
    op.create_index("ix_data_locations_tenant_id_kind", "data_locations", ["tenant_id", "kind"])
    op.create_index("ix_data_locations_contribution_id", "data_locations", ["contribution_id"])

    op.create_table(
        "idempotency_records",
        sa.Column("record_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("endpoint", sa.String(128), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_sha256", SHA256, nullable=False),
        sa.Column("response_status", sa.Integer, nullable=False),
        sa.Column("response_body", JSONB, nullable=False),
        sa.Column("created_at", TS, nullable=False, server_default=_now()),
        sa.Column("expires_at", TS, nullable=False),
        sa.UniqueConstraint(
            "tenant_id", "endpoint", "idempotency_key", name="uq_idempotency_records_scope_key"
        ),
        sa.CheckConstraint(
            "response_status BETWEEN 100 AND 599",
            name="status_is_http",
        ),
    )
    op.create_index("ix_idempotency_records_expires_at", "idempotency_records", ["expires_at"])

    op.create_table(
        "audit_events",
        sa.Column("event_id", INV_ID, primary_key=True),
        sa.Column("occurred_at", TS, primary_key=True),
        sa.Column("tenant_id", UUID),
        sa.Column("actor_type", sa.String(16), nullable=False),
        sa.Column("actor_id", sa.String(255)),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("outcome", sa.String(8), nullable=False),
        sa.Column("reason_code", sa.String(64)),
        sa.Column("trace_id", TRACE_ID),
        sa.Column("target_type", sa.String(32)),
        sa.Column("target_id", sa.String(64)),
        sa.Column("detail", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("source_ip", sa.String(45)),
        sa.Column("user_agent", sa.Text),
        sa.CheckConstraint("outcome IN ('allow','deny','error')", name="outcome_allowed"),
        sa.CheckConstraint(
            "actor_type IN ('user','node','agent','system','anonymous')",
            name="actor_type_allowed",
        ),
        postgresql_partition_by="RANGE (occurred_at)",
    )
    op.create_index("ix_audit_events_tenant_id_occurred_at", "audit_events", ["tenant_id", "occurred_at"])
    op.create_index("ix_audit_events_action_occurred_at", "audit_events", ["action", "occurred_at"])
    op.create_index("ix_audit_events_trace_id", "audit_events", ["trace_id"])

    _create_initial_partitions()
    _install_rls()


def _create_initial_partitions() -> None:
    """Create this month plus three, per CR-06. No DEFAULT partition."""
    from alembic import context

    from saintvision.db.models import PARTITIONED_TABLES
    from saintvision.db.partitions import add_months, ensure_partitions, month_floor, partition_name

    now = dt.datetime.now(dt.timezone.utc)

    if context.is_offline_mode():
        # --sql cannot ask the server what already exists, so emit the four
        # months unconditionally. Against an empty schema this is the same DDL
        # the online path produces.
        start = month_floor(now)
        for table in PARTITIONED_TABLES:
            for offset in range(4):
                lower = add_months(start, offset)
                upper = add_months(lower, 1)
                op.execute(
                    f"CREATE TABLE {partition_name(table, lower)} PARTITION OF {table} "
                    f"FOR VALUES FROM ('{lower:%Y-%m-%d}') TO ('{upper:%Y-%m-%d}')"
                )
        return

    created = ensure_partitions(op.get_bind(), now=now, lead_months=3)
    if not created:  # pragma: no cover - initial migration always creates some
        raise RuntimeError("no partitions were created for the partitioned tables")


def _install_rls() -> None:
    op.execute(
        "DO $$ BEGIN "
        f"IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN "
        f"CREATE ROLE {APP_ROLE} NOLOGIN NOBYPASSRLS NOSUPERUSER NOCREATEDB NOCREATEROLE; "
        "END IF; END $$;"
    )
    op.execute(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}")
    op.execute(f"GRANT SELECT ON tenants TO {APP_ROLE}")
    # Append-only for the application role. Not a WORM claim against a
    # superuser (PLAN-DB-001).
    op.execute(f"GRANT SELECT, INSERT ON audit_events TO {APP_ROLE}")
    for table in TENANT_SCOPED:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO {APP_ROLE}")
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        # FORCE, or the migration owner silently bypasses every policy below.
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_tenant_isolation ON {table} FOR ALL TO {APP_ROLE} "
            f"USING (tenant_id = {TENANT_EXPR}) WITH CHECK (tenant_id = {TENANT_EXPR})"
        )


def downgrade() -> None:
    for table in (
        "audit_events",
        "idempotency_records",
        "data_locations",
        "storage_contributions",
        "resource_snapshots",
        "resource_offers",
        "node_capabilities",
        "node_bootstrap_tokens",
        "nodes",
        "project_members",
        "projects",
        "user_roles",
        "roles",
        "users",
        "tenants",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    # The role may be shared with another database in the cluster, so it is not
    # dropped here.
