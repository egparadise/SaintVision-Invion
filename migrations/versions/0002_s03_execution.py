"""S03 execution: workspace, workload, run, evidence, artifact.

Revision ID: 0002_s03_execution
Revises: 0001_s02_baseline
Create Date: 2026-09-09

Covers S03-DB (workspace, workload, run, attempt, step, checkpoint, approval,
evidence, outbox, inbox) and S03-ST (artifact, upload session).

Still absent, and why:

* leases and allocations — ADR-005/006, Codex, S05. ``run_attempts.fence_token``
  is a column, not a fencing mechanism, and claims nothing about ordering.
* context bundles and snapshots — S09-DB owns immutable Context. ADR-009 also
  forbids fixing an embedding dimension before the model is chosen.
* MLflow and lineage tables — S10.

The run state list and the termination reason list are rendered from
``saintvision.runs.state`` rather than retyped, so the CHECK constraint and the
state machine cannot drift apart.
"""

from __future__ import annotations

import datetime as dt

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_s03_execution"
down_revision = "0001_s02_baseline"
branch_labels = None
depends_on = None

INV_ID = sa.CHAR(30)
SHA256 = sa.CHAR(64)
TRACE_ID = sa.CHAR(32)
UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB
TS = sa.DateTime(timezone=True)

APP_ROLE = "inv_app"
TENANT_EXPR = "NULLIF(current_setting('inv.tenant_id', true), '')::uuid"

#: Tenant-scoped tables added by this revision.
NEW_TENANT_SCOPED = (
    "workspaces",
    "workspace_volumes",
    "workloads",
    "runs",
    "run_attempts",
    "steps",
    "checkpoints",
    "approvals",
    "evidence_envelopes",
    "outbox_events",
    "inbox_events",
    "artifacts",
    "upload_sessions",
)

#: Append-only for the application role: INSERT and SELECT, never UPDATE or
#: DELETE. A constraint on the application, not a WORM claim against the owner.
NEW_APPEND_ONLY = ("evidence_envelopes",)

MAX_ARTIFACT_BYTES = 50 * 1024 * 1024 * 1024


def _now():
    return sa.text("now()")


def _state_list() -> str:
    from saintvision.runs.state import ALL_STATES

    return ",".join(f"'{s}'" for s in ALL_STATES)


def _reason_list() -> str:
    from saintvision.runs.state import ALL_REASONS

    return ",".join(f"'{r}'" for r in ALL_REASONS)


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("workspace_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("project_id", INV_ID, nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="provisioning"),
        sa.Column("node_id", INV_ID),
        sa.Column("created_by_user_id", INV_ID, nullable=False),
        sa.Column("created_at", TS, nullable=False, server_default=_now()),
        sa.Column("deleted_at", TS),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "project_id"],
            ["projects.tenant_id", "projects.project_id"],
            name="fk_workspaces_tenant_id_project_id",
        ),
        sa.UniqueConstraint("tenant_id", "workspace_id", name="uq_workspaces_tenant_id_workspace_id"),
        sa.UniqueConstraint("project_id", "name", name="uq_workspaces_project_id_name"),
        sa.CheckConstraint(
            "status IN ('provisioning','ready','suspended','deleting','deleted')",
            name="status_allowed",
        ),
        sa.CheckConstraint(
            "(status = 'deleted') = (deleted_at IS NOT NULL)", name="deletion_paired"
        ),
    )
    op.create_index("ix_workspaces_tenant_id_project_id", "workspaces", ["tenant_id", "project_id"])

    op.create_table(
        "workspace_volumes",
        sa.Column("volume_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("workspace_id", INV_ID, nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("mount_path", sa.Text, nullable=False),
        sa.Column("writable", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("size_bytes", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("source_uri", sa.Text),
        sa.Column("created_at", TS, nullable=False, server_default=_now()),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "workspace_id"],
            ["workspaces.tenant_id", "workspaces.workspace_id"],
            name="fk_workspace_volumes_tenant_id_workspace_id",
        ),
        sa.UniqueConstraint("tenant_id", "volume_id", name="uq_workspace_volumes_tenant_id_volume_id"),
        sa.UniqueConstraint(
            "workspace_id", "mount_path", name="uq_workspace_volumes_workspace_id_mount_path"
        ),
        sa.CheckConstraint(
            "kind IN ('persistent','ephemeral','dataset_mount')", name="kind_allowed"
        ),
        sa.CheckConstraint(
            "NOT (kind = 'dataset_mount' AND writable)", name="dataset_mount_is_read_only"
        ),
        sa.CheckConstraint("size_bytes >= 0", name="size_non_negative"),
    )

    op.create_table(
        "workloads",
        sa.Column("workload_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("project_id", INV_ID, nullable=False),
        sa.Column("kind", sa.String(16), nullable=False, server_default="batch"),
        sa.Column("objective", sa.Text, nullable=False),
        sa.Column("spec", JSONB, nullable=False),
        sa.Column("spec_sha256", SHA256, nullable=False),
        sa.Column("contract_version", sa.String(32), nullable=False),
        sa.Column("created_by_user_id", INV_ID, nullable=False),
        sa.Column("created_at", TS, nullable=False, server_default=_now()),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "project_id"],
            ["projects.tenant_id", "projects.project_id"],
            name="fk_workloads_tenant_id_project_id",
        ),
        sa.UniqueConstraint("tenant_id", "workload_id", name="uq_workloads_tenant_id_workload_id"),
        sa.CheckConstraint("kind IN ('batch','agent','service')", name="kind_allowed"),
    )
    op.create_index("ix_workloads_tenant_id_project_id", "workloads", ["tenant_id", "project_id"])

    op.create_table(
        "runs",
        sa.Column("run_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("workload_id", INV_ID, nullable=False),
        sa.Column("workspace_id", INV_ID, nullable=False),
        sa.Column("state", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("termination_reason", sa.String(24)),
        sa.Column("evidence_id", INV_ID),
        sa.Column("requested_by_user_id", INV_ID, nullable=False),
        sa.Column("trace_id", TRACE_ID),
        sa.Column("attempt_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("retry_budget", sa.Integer, nullable=False, server_default="2"),
        sa.Column("max_wall_time_seconds", sa.Integer),
        sa.Column("created_at", TS, nullable=False, server_default=_now()),
        sa.Column("started_at", TS),
        sa.Column("ended_at", TS),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "workload_id"],
            ["workloads.tenant_id", "workloads.workload_id"],
            name="fk_runs_tenant_id_workload_id",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "workspace_id"],
            ["workspaces.tenant_id", "workspaces.workspace_id"],
            name="fk_runs_tenant_id_workspace_id",
        ),
        sa.UniqueConstraint("tenant_id", "run_id", name="uq_runs_tenant_id_run_id"),
        sa.CheckConstraint(f"state IN ({_state_list()})", name="state_allowed"),
        sa.CheckConstraint(
            f"termination_reason IS NULL OR termination_reason IN ({_reason_list()})",
            name="termination_reason_allowed",
        ),
        sa.CheckConstraint(
            "(state IN ('succeeded','failed','cancelled')) = (termination_reason IS NOT NULL)",
            name="reason_only_when_terminal",
        ),
        sa.CheckConstraint(
            "(state IN ('succeeded','failed','cancelled')) = (ended_at IS NOT NULL)",
            name="ended_at_only_when_terminal",
        ),
        sa.CheckConstraint(
            "state <> 'succeeded' OR evidence_id IS NOT NULL",
            name="success_requires_evidence",
        ),
        sa.CheckConstraint("attempt_count >= 0", name="attempt_count_non_negative"),
        sa.CheckConstraint("retry_budget >= 0", name="retry_budget_non_negative"),
    )
    op.create_index("ix_runs_tenant_id_state", "runs", ["tenant_id", "state"])
    op.create_index("ix_runs_tenant_id_workspace_id", "runs", ["tenant_id", "workspace_id"])
    op.create_index("ix_runs_trace_id", "runs", ["trace_id"])

    op.create_table(
        "run_attempts",
        sa.Column("attempt_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("run_id", INV_ID, nullable=False),
        sa.Column("attempt_number", sa.Integer, nullable=False),
        sa.Column("node_id", INV_ID),
        sa.Column("placement_snapshot", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("fence_token", sa.BigInteger),
        sa.Column("scheduler_version", sa.String(32)),
        sa.Column("policy_version", sa.String(32)),
        sa.Column("started_at", TS, nullable=False, server_default=_now()),
        sa.Column("ended_at", TS),
        sa.Column("outcome", sa.String(16)),
        sa.Column("error_code", sa.String(64)),
        sa.ForeignKeyConstraint(
            ["tenant_id", "run_id"], ["runs.tenant_id", "runs.run_id"],
            name="fk_run_attempts_tenant_id_run_id",
        ),
        sa.UniqueConstraint("tenant_id", "attempt_id", name="uq_run_attempts_tenant_id_attempt_id"),
        sa.UniqueConstraint("run_id", "attempt_number", name="uq_run_attempts_run_id_attempt_number"),
        sa.CheckConstraint("attempt_number >= 1", name="attempt_number_positive"),
        sa.CheckConstraint(
            "outcome IS NULL OR outcome IN ('succeeded','failed','cancelled','abandoned')",
            name="outcome_allowed",
        ),
    )
    op.create_index("ix_run_attempts_tenant_id_run_id", "run_attempts", ["tenant_id", "run_id"])

    op.create_table(
        "steps",
        sa.Column("step_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("attempt_id", INV_ID, nullable=False),
        sa.Column("ordinal", sa.Integer, nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("tool_name", sa.String(128)),
        sa.Column("tool_version", sa.String(32)),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("exit_code", sa.Integer),
        sa.Column("error_code", sa.String(64)),
        sa.Column("started_at", TS),
        sa.Column("ended_at", TS),
        sa.Column("duration_ms", sa.BigInteger),
        sa.ForeignKeyConstraint(
            ["tenant_id", "attempt_id"],
            ["run_attempts.tenant_id", "run_attempts.attempt_id"],
            name="fk_steps_tenant_id_attempt_id",
        ),
        sa.UniqueConstraint("tenant_id", "step_id", name="uq_steps_tenant_id_step_id"),
        sa.UniqueConstraint("attempt_id", "ordinal", name="uq_steps_attempt_id_ordinal"),
        sa.CheckConstraint(
            "status IN ('pending','running','succeeded','failed','skipped')",
            name="status_allowed",
        ),
        sa.CheckConstraint("ordinal >= 0", name="ordinal_non_negative"),
    )
    op.create_index("ix_steps_tenant_id_attempt_id", "steps", ["tenant_id", "attempt_id"])

    op.create_table(
        "checkpoints",
        sa.Column("checkpoint_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("run_id", INV_ID, nullable=False),
        sa.Column("step_ordinal", sa.Integer, nullable=False),
        sa.Column("state_blob", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", TS, nullable=False, server_default=_now()),
        sa.ForeignKeyConstraint(
            ["tenant_id", "run_id"], ["runs.tenant_id", "runs.run_id"],
            name="fk_checkpoints_tenant_id_run_id",
        ),
        sa.UniqueConstraint("tenant_id", "checkpoint_id", name="uq_checkpoints_tenant_id_checkpoint_id"),
        sa.UniqueConstraint("run_id", "step_ordinal", name="uq_checkpoints_run_id_step_ordinal"),
        sa.CheckConstraint("step_ordinal >= 0", name="step_ordinal_non_negative"),
    )

    op.create_table(
        "approvals",
        sa.Column("approval_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("run_id", INV_ID, nullable=False),
        sa.Column("subject_sha256", SHA256, nullable=False),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("risk_level", sa.Integer, nullable=False),
        sa.Column("scope", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("decided_by_user_id", INV_ID, nullable=False),
        sa.Column("decided_at", TS, nullable=False, server_default=_now()),
        sa.Column("expires_at", TS, nullable=False),
        sa.Column("note", sa.Text),
        sa.ForeignKeyConstraint(
            ["tenant_id", "run_id"], ["runs.tenant_id", "runs.run_id"],
            name="fk_approvals_tenant_id_run_id",
        ),
        sa.UniqueConstraint("tenant_id", "approval_id", name="uq_approvals_tenant_id_approval_id"),
        sa.CheckConstraint("decision IN ('approved','rejected')", name="decision_allowed"),
        sa.CheckConstraint("risk_level BETWEEN 0 AND 3", name="risk_level_in_range"),
        sa.CheckConstraint("expires_at > decided_at", name="expiry_after_decision"),
    )
    op.create_index("ix_approvals_tenant_id_run_id", "approvals", ["tenant_id", "run_id"])

    op.create_table(
        "evidence_envelopes",
        sa.Column("evidence_id", INV_ID, primary_key=True),
        sa.Column("recorded_at", TS, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("run_id", INV_ID, nullable=False),
        sa.Column("step_id", INV_ID),
        sa.Column("trace_id", TRACE_ID),
        sa.Column("actor_type", sa.String(16), nullable=False),
        sa.Column("actor_id", sa.String(255), nullable=False),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("policy_id", sa.String(128)),
        sa.Column("effect", sa.String(8)),
        sa.Column("approval_id", INV_ID),
        sa.Column("input_schema", sa.String(128), nullable=False),
        sa.Column("input_sha256", SHA256, nullable=False),
        sa.Column("output_schema", sa.String(128)),
        sa.Column("output_ref", sa.Text),
        sa.Column("result", sa.String(16), nullable=False),
        sa.Column("telemetry", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "component_versions", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.CheckConstraint("result IN ('succeeded','failed','denied')", name="result_allowed"),
        sa.CheckConstraint("effect IS NULL OR effect IN ('allow','deny')", name="effect_allowed"),
        sa.CheckConstraint(
            "actor_type IN ('user','node','agent','system')", name="actor_type_allowed"
        ),
        postgresql_partition_by="RANGE (recorded_at)",
    )
    op.create_index(
        "ix_evidence_envelopes_tenant_id_recorded_at",
        "evidence_envelopes",
        ["tenant_id", "recorded_at"],
    )
    op.create_index(
        "ix_evidence_envelopes_run_id_recorded_at",
        "evidence_envelopes",
        ["run_id", "recorded_at"],
    )
    op.create_index("ix_evidence_envelopes_trace_id", "evidence_envelopes", ["trace_id"])

    op.create_table(
        "outbox_events",
        sa.Column("outbox_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("event_id", INV_ID, nullable=False),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("aggregate_type", sa.String(32), nullable=False),
        sa.Column("aggregate_id", INV_ID, nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("trace_id", TRACE_ID),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("publish_attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", TS, nullable=False, server_default=_now()),
        sa.Column("published_at", TS),
        sa.Column("last_error", sa.Text),
        sa.UniqueConstraint("event_id", name="uq_outbox_events_event_id"),
        sa.CheckConstraint("status IN ('pending','published','failed')", name="status_allowed"),
        sa.CheckConstraint("event_type LIKE 'inv.%'", name="event_type_namespaced"),
        sa.CheckConstraint("publish_attempts >= 0", name="publish_attempts_non_negative"),
    )
    op.create_index("ix_outbox_events_status_created_at", "outbox_events", ["status", "created_at"])
    op.create_index(
        "ix_outbox_events_tenant_id_created_at", "outbox_events", ["tenant_id", "created_at"]
    )

    op.create_table(
        "inbox_events",
        sa.Column("inbox_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("consumer", sa.String(64), nullable=False),
        sa.Column("event_id", INV_ID, nullable=False),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("processed_at", TS, nullable=False, server_default=_now()),
        sa.UniqueConstraint("consumer", "event_id", name="uq_inbox_events_consumer_event_id"),
    )
    op.create_index("ix_inbox_events_processed_at", "inbox_events", ["processed_at"])

    op.create_table(
        "artifacts",
        sa.Column("artifact_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("run_id", INV_ID, nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column(
            "media_type", sa.String(128), nullable=False, server_default="application/octet-stream"
        ),
        sa.Column("status", sa.String(16), nullable=False, server_default="staging"),
        sa.Column("byte_size", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("checksum_sha256", SHA256),
        sa.Column("verified_at", TS),
        sa.Column("object_version", sa.String(128)),
        sa.Column("retention_pinned_until", TS),
        sa.Column("created_at", TS, nullable=False, server_default=_now()),
        sa.Column("deleted_at", TS),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "run_id"], ["runs.tenant_id", "runs.run_id"],
            name="fk_artifacts_tenant_id_run_id",
        ),
        sa.UniqueConstraint("tenant_id", "artifact_id", name="uq_artifacts_tenant_id_artifact_id"),
        sa.UniqueConstraint("run_id", "name", name="uq_artifacts_run_id_name"),
        sa.CheckConstraint(
            "status IN ('staging','active','quarantined','deleted')", name="status_allowed"
        ),
        sa.CheckConstraint("byte_size >= 0", name="byte_size_non_negative"),
        sa.CheckConstraint(
            f"byte_size <= {MAX_ARTIFACT_BYTES}", name="byte_size_within_limit"
        ),
        sa.CheckConstraint(
            "status <> 'active' OR (checksum_sha256 IS NOT NULL AND verified_at IS NOT NULL)",
            name="active_requires_verification",
        ),
    )
    op.create_index("ix_artifacts_tenant_id_run_id", "artifacts", ["tenant_id", "run_id"])
    op.create_index(
        "ix_artifacts_retention_pinned_until", "artifacts", ["retention_pinned_until"]
    )

    op.create_table(
        "upload_sessions",
        sa.Column("upload_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("artifact_id", INV_ID, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="initiated"),
        sa.Column("part_bytes", sa.BigInteger, nullable=False, server_default=str(16 * 1024 * 1024)),
        sa.Column("parts_declared", sa.Integer, nullable=False, server_default="0"),
        sa.Column("reserved_bytes", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("part_evidence", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", TS, nullable=False, server_default=_now()),
        sa.Column("expires_at", TS, nullable=False),
        sa.Column("settled_at", TS),
        sa.Column("last_error", sa.Text),
        sa.ForeignKeyConstraint(
            ["tenant_id", "artifact_id"],
            ["artifacts.tenant_id", "artifacts.artifact_id"],
            name="fk_upload_sessions_tenant_id_artifact_id",
        ),
        sa.UniqueConstraint("tenant_id", "upload_id", name="uq_upload_sessions_tenant_id_upload_id"),
        sa.UniqueConstraint("artifact_id", name="uq_upload_sessions_artifact_id"),
        sa.CheckConstraint(
            "status IN ('initiated','completing','verified','failed','aborted')",
            name="status_allowed",
        ),
        sa.CheckConstraint("part_bytes > 0", name="part_bytes_positive"),
        sa.CheckConstraint("reserved_bytes >= 0", name="reserved_bytes_non_negative"),
        sa.CheckConstraint("parts_declared >= 0", name="parts_declared_non_negative"),
        sa.CheckConstraint("expires_at > created_at", name="expiry_after_creation"),
    )
    op.create_index(
        "ix_upload_sessions_status_expires_at", "upload_sessions", ["status", "expires_at"]
    )

    _create_evidence_partitions()
    _install_rls()


def _create_evidence_partitions() -> None:
    """Same rule as 0001: three months ahead, no DEFAULT partition (CR-06)."""
    from alembic import context

    from saintvision.db.partitions import add_months, ensure_partitions, month_floor, partition_name

    now = dt.datetime.now(dt.timezone.utc)
    tables = {"evidence_envelopes": "recorded_at"}

    if context.is_offline_mode():
        start = month_floor(now)
        for offset in range(4):
            lower = add_months(start, offset)
            upper = add_months(lower, 1)
            op.execute(
                f"CREATE TABLE {partition_name('evidence_envelopes', lower)} "
                f"PARTITION OF evidence_envelopes "
                f"FOR VALUES FROM ('{lower:%Y-%m-%d}') TO ('{upper:%Y-%m-%d}')"
            )
        return

    created = ensure_partitions(op.get_bind(), now=now, lead_months=3, tables=tables)
    if not created:  # pragma: no cover
        raise RuntimeError("no partitions were created for evidence_envelopes")


def _install_rls() -> None:
    for table in NEW_TENANT_SCOPED:
        if table in NEW_APPEND_ONLY:
            op.execute(f"GRANT SELECT, INSERT ON {table} TO {APP_ROLE}")
        else:
            op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO {APP_ROLE}")
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_tenant_isolation ON {table} FOR ALL TO {APP_ROLE} "
            f"USING (tenant_id = {TENANT_EXPR}) WITH CHECK (tenant_id = {TENANT_EXPR})"
        )


def downgrade() -> None:
    for table in (
        "upload_sessions",
        "artifacts",
        "inbox_events",
        "outbox_events",
        "evidence_envelopes",
        "approvals",
        "checkpoints",
        "steps",
        "run_attempts",
        "runs",
        "workloads",
        "workspace_volumes",
        "workspaces",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
