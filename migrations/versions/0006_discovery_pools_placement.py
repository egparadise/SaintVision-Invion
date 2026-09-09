"""Node discovery, resource pools and distributed placement.

Revision ID: 0006_discovery_pools_placement
Revises: 0005_s12_pilot_operations
Create Date: 2026-09-10

Resource aggregation is the product's purpose: connect the CPU, GPU, RAM and
folders five machines offer, and spread work across them. These tables are the
record of which machines were found, which were admitted, which pool they serve,
and how one job was spread over them.

Two constraints carry the design decisions:

* ``splitting_requires_declaration`` — a plan with more than one shard requires
  the workload to have declared it can be split. Splitting a program that is
  not shard-aware produces wrong answers, not slow ones, so the platform never
  infers it.
* ``admission_paired_with_node`` — an announcement is only ``admitted`` when it
  actually became a node. Discovery grants nothing on its own.

Partitioned tables: none. Append-only: none.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006_discovery_pools_placement"
down_revision = "0005_s12_pilot_operations"
branch_labels = None
depends_on = None

INV_ID = sa.CHAR(30)
UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB
INET = postgresql.INET
QTY = sa.NUMERIC(20, 4)
TS = sa.DateTime(timezone=True)

APP_ROLE = "inv_app"
TENANT_EXPR = "NULLIF(current_setting('inv.tenant_id', true), '')::uuid"

NEW_TENANT_SCOPED = (
    "node_announcements",
    "resource_pools",
    "resource_pool_members",
    "distributed_plans",
    "plan_placements",
)


def _now():
    return sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "node_announcements",
        sa.Column("announcement_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("state", sa.String(16), nullable=False, server_default="candidate"),
        sa.Column("instance_id", sa.String(128), nullable=False),
        sa.Column("source_ip", INET, nullable=False),
        sa.Column("claimed_hostname", sa.String(253), nullable=False),
        sa.Column("claimed_os_type", sa.String(16), nullable=False),
        sa.Column("claimed_os_version", sa.String(64), nullable=False),
        sa.Column("claimed_agent_version", sa.String(64), nullable=False),
        sa.Column("claimed_cpu_cores", sa.Integer, nullable=False, server_default="0"),
        sa.Column("claimed_ram_bytes", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("claimed_gpu_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("claimed_labels", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("first_seen_at", TS, nullable=False, server_default=_now()),
        sa.Column("last_seen_at", TS, nullable=False, server_default=_now()),
        sa.Column("announce_count", sa.Integer, nullable=False, server_default="1"),
        sa.Column("admitted_node_id", INV_ID),
        sa.Column("admitted_by_user_id", INV_ID),
        sa.Column("decided_at", TS),
        sa.Column("decline_reason", sa.Text),
        sa.UniqueConstraint(
            "tenant_id", "announcement_id",
            name="uq_node_announcements_tenant_id_announcement_id",
        ),
        sa.UniqueConstraint(
            "tenant_id", "instance_id", "source_ip",
            name="uq_node_announcements_tenant_instance_source",
        ),
        sa.CheckConstraint(
            "state IN ('candidate','admitted','declined','expired')", name="state_allowed"
        ),
        sa.CheckConstraint(
            "claimed_os_type IN ('windows','linux')", name="claimed_os_type_allowed"
        ),
        sa.CheckConstraint("claimed_cpu_cores >= 0", name="claimed_cpu_cores_non_negative"),
        sa.CheckConstraint("claimed_ram_bytes >= 0", name="claimed_ram_bytes_non_negative"),
        sa.CheckConstraint("claimed_gpu_count >= 0", name="claimed_gpu_count_non_negative"),
        sa.CheckConstraint("announce_count >= 1", name="announce_count_positive"),
        sa.CheckConstraint(
            "(state = 'admitted') = (admitted_node_id IS NOT NULL)",
            name="admission_paired_with_node",
        ),
    )
    op.create_index(
        "ix_node_announcements_tenant_id_state", "node_announcements", ["tenant_id", "state"]
    )
    op.create_index("ix_node_announcements_last_seen_at", "node_announcements", ["last_seen_at"])

    op.create_table(
        "resource_pools",
        sa.Column("pool_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("project_id", INV_ID, nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("created_by_user_id", INV_ID, nullable=False),
        sa.Column("created_at", TS, nullable=False, server_default=_now()),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "project_id"],
            ["projects.tenant_id", "projects.project_id"],
            name="fk_resource_pools_tenant_id_project_id",
        ),
        sa.UniqueConstraint("tenant_id", "pool_id", name="uq_resource_pools_tenant_id_pool_id"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_resource_pools_tenant_id_name"),
        sa.CheckConstraint("status IN ('active','archived')", name="status_allowed"),
    )
    op.create_index(
        "ix_resource_pools_tenant_id_project_id", "resource_pools", ["tenant_id", "project_id"]
    )

    op.create_table(
        "resource_pool_members",
        sa.Column("tenant_id", UUID, primary_key=True),
        sa.Column("pool_id", INV_ID, primary_key=True),
        sa.Column("node_id", INV_ID, primary_key=True),
        sa.Column("added_by_user_id", INV_ID, nullable=False),
        sa.Column("added_at", TS, nullable=False, server_default=_now()),
        sa.ForeignKeyConstraint(
            ["tenant_id", "pool_id"],
            ["resource_pools.tenant_id", "resource_pools.pool_id"],
            name="fk_resource_pool_members_tenant_id_pool_id",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "node_id"],
            ["nodes.tenant_id", "nodes.node_id"],
            name="fk_resource_pool_members_tenant_id_node_id",
        ),
    )
    op.create_index(
        "ix_resource_pool_members_tenant_id_node_id",
        "resource_pool_members",
        ["tenant_id", "node_id"],
    )

    op.create_table(
        "distributed_plans",
        sa.Column("plan_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("run_id", INV_ID, nullable=False),
        sa.Column("pool_id", INV_ID, nullable=False),
        sa.Column("strategy", sa.String(16), nullable=False, server_default="single_node"),
        sa.Column("state", sa.String(16), nullable=False, server_default="planned"),
        sa.Column("shard_count", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "splittable_declared", sa.Boolean, nullable=False, server_default=sa.text("false")
        ),
        sa.Column("shard_cpu_cores", QTY, nullable=False, server_default="0"),
        sa.Column("shard_ram_bytes", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("shard_gpu_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("ranking_snapshot", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", TS, nullable=False, server_default=_now()),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "run_id"], ["runs.tenant_id", "runs.run_id"],
            name="fk_distributed_plans_tenant_id_run_id",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "pool_id"],
            ["resource_pools.tenant_id", "resource_pools.pool_id"],
            name="fk_distributed_plans_tenant_id_pool_id",
        ),
        sa.UniqueConstraint("tenant_id", "plan_id", name="uq_distributed_plans_tenant_id_plan_id"),
        sa.UniqueConstraint("run_id", name="uq_distributed_plans_run_id"),
        sa.CheckConstraint(
            "strategy IN ('single_node','data_parallel','sharded')", name="strategy_allowed"
        ),
        sa.CheckConstraint(
            "state IN ('planned','placed','running','completed','failed','cancelled')",
            name="state_allowed",
        ),
        sa.CheckConstraint("shard_count >= 1", name="shard_count_positive"),
        sa.CheckConstraint(
            "strategy <> 'single_node' OR shard_count = 1", name="single_node_has_one_shard"
        ),
        sa.CheckConstraint(
            "shard_count = 1 OR splittable_declared", name="splitting_requires_declaration"
        ),
    )
    op.create_index(
        "ix_distributed_plans_tenant_id_pool_id", "distributed_plans", ["tenant_id", "pool_id"]
    )

    op.create_table(
        "plan_placements",
        sa.Column("tenant_id", UUID, primary_key=True),
        sa.Column("plan_id", INV_ID, primary_key=True),
        sa.Column("shard_index", sa.Integer, primary_key=True),
        sa.Column("node_id", INV_ID, nullable=False),
        sa.Column("assigned_cpu_cores", QTY, nullable=False, server_default="0"),
        sa.Column("assigned_ram_bytes", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("assigned_gpu_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "spare_at_placement", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("state", sa.String(16), nullable=False, server_default="planned"),
        sa.Column("placed_at", TS, nullable=False, server_default=_now()),
        sa.Column("note", sa.Text),
        sa.ForeignKeyConstraint(
            ["tenant_id", "plan_id"],
            ["distributed_plans.tenant_id", "distributed_plans.plan_id"],
            name="fk_plan_placements_tenant_id_plan_id",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "node_id"], ["nodes.tenant_id", "nodes.node_id"],
            name="fk_plan_placements_tenant_id_node_id",
        ),
        sa.UniqueConstraint(
            "plan_id", "shard_index", name="uq_plan_placements_plan_id_shard_index"
        ),
        sa.CheckConstraint("shard_index >= 0", name="shard_index_non_negative"),
        sa.CheckConstraint(
            "state IN ('planned','running','succeeded','failed','skipped')", name="state_allowed"
        ),
        sa.CheckConstraint("assigned_cpu_cores >= 0", name="assigned_cpu_non_negative"),
        sa.CheckConstraint("assigned_ram_bytes >= 0", name="assigned_ram_non_negative"),
        sa.CheckConstraint("assigned_gpu_count >= 0", name="assigned_gpu_non_negative"),
    )
    op.create_index(
        "ix_plan_placements_tenant_id_node_id", "plan_placements", ["tenant_id", "node_id"]
    )

    for table in NEW_TENANT_SCOPED:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO {APP_ROLE}")
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_tenant_isolation ON {table} FOR ALL TO {APP_ROLE} "
            f"USING (tenant_id = {TENANT_EXPR}) WITH CHECK (tenant_id = {TENANT_EXPR})"
        )


def downgrade() -> None:
    for table in (
        "plan_placements",
        "distributed_plans",
        "resource_pool_members",
        "resource_pools",
        "node_announcements",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
