"""S12 pilot operations: backup, recovery drill, release, acceptance.

Revision ID: 0005_s12_pilot_operations
Revises: 0004_s10_lineage
Create Date: 2026-09-09

S12-DB (restore, permissions, operational acceptance) and S12-ST (operational
checks, contributed folders, recovery drills).

The constraints here are all of one kind: a record must not claim more than
happened. A drill cannot pass without measurements; a database drill cannot
pass without the fencing check (ERR-DESIGN-006); a conditional acceptance
cannot have an empty limitation list; a healthy storage check cannot have a
checksum mismatch.

Partitioned tables: none added by this revision. Append-only: none — a drill
and an acceptance are written once by construction but are edited during the
exercise, so blanket append-only would be the same mistake 0004 made with
model_versions.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005_s12_pilot_operations"
down_revision = "0004_s10_lineage"
branch_labels = None
depends_on = None

INV_ID = sa.CHAR(30)
SHA256 = sa.CHAR(64)
UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB
TS = sa.DateTime(timezone=True)

APP_ROLE = "inv_app"
TENANT_EXPR = "NULLIF(current_setting('inv.tenant_id', true), '')::uuid"

NEW_TENANT_SCOPED = (
    "backup_records",
    "recovery_drills",
    "storage_checks",
    "release_manifests",
    "acceptance_records",
    "permission_snapshots",
)

TARGET_RPO_SECONDS = 15 * 60
TARGET_RTO_SECONDS = 60 * 60


def _now():
    return sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "backup_records",
        sa.Column("backup_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("location_ref", sa.Text, nullable=False),
        sa.Column("off_site", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("byte_size", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("checksum_sha256", SHA256),
        sa.Column("verified", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("verified_at", TS),
        sa.Column("started_at", TS, nullable=False, server_default=_now()),
        sa.Column("completed_at", TS),
        sa.Column("retention_until", TS),
        sa.UniqueConstraint("tenant_id", "backup_id", name="uq_backup_records_tenant_id_backup_id"),
        sa.CheckConstraint("kind IN ('base','wal','logical')", name="kind_allowed"),
        sa.CheckConstraint("byte_size >= 0", name="byte_size_non_negative"),
        sa.CheckConstraint(
            "completed_at IS NULL OR completed_at >= started_at", name="completion_after_start"
        ),
        sa.CheckConstraint(
            "NOT verified OR (checksum_sha256 IS NOT NULL AND verified_at IS NOT NULL)",
            name="verified_requires_checksum",
        ),
    )
    op.create_index("ix_backup_records_tenant_id_started_at", "backup_records", ["tenant_id", "started_at"])
    op.create_index("ix_backup_records_retention_until", "backup_records", ["retention_until"])

    op.create_table(
        "recovery_drills",
        sa.Column("drill_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("scope", sa.String(16), nullable=False),
        sa.Column("backup_id", INV_ID),
        sa.Column("subject_id", INV_ID),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("measured_rpo_seconds", sa.Integer),
        sa.Column("measured_rto_seconds", sa.Integer),
        sa.Column(
            "target_rpo_seconds", sa.Integer, nullable=False, server_default=str(TARGET_RPO_SECONDS)
        ),
        sa.Column(
            "target_rto_seconds", sa.Integer, nullable=False, server_default=str(TARGET_RTO_SECONDS)
        ),
        sa.Column("met_targets", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("fencing_verified", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("fencing_note", sa.Text),
        sa.Column("integrity_verified", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("performed_by_user_id", INV_ID, nullable=False),
        sa.Column("performed_at", TS, nullable=False, server_default=_now()),
        sa.Column("evidence_id", INV_ID),
        sa.Column("notes", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.UniqueConstraint("tenant_id", "drill_id", name="uq_recovery_drills_tenant_id_drill_id"),
        sa.CheckConstraint(
            "scope IN ('database','workspace','artifact','node')", name="scope_allowed"
        ),
        sa.CheckConstraint("outcome IN ('passed','failed','aborted')", name="outcome_allowed"),
        sa.CheckConstraint(
            "measured_rpo_seconds IS NULL OR measured_rpo_seconds >= 0",
            name="measured_rpo_non_negative",
        ),
        sa.CheckConstraint(
            "measured_rto_seconds IS NULL OR measured_rto_seconds >= 0",
            name="measured_rto_non_negative",
        ),
        sa.CheckConstraint(
            "outcome <> 'passed' OR "
            "(measured_rpo_seconds IS NOT NULL AND measured_rto_seconds IS NOT NULL)",
            name="pass_requires_measurements",
        ),
        sa.CheckConstraint(
            "outcome <> 'passed' OR scope <> 'database' OR fencing_verified",
            name="database_pass_requires_fencing_check",
        ),
        sa.CheckConstraint(
            "NOT met_targets OR ("
            "measured_rpo_seconds IS NOT NULL AND measured_rto_seconds IS NOT NULL "
            "AND measured_rpo_seconds <= target_rpo_seconds "
            "AND measured_rto_seconds <= target_rto_seconds)",
            name="met_targets_agrees_with_measurements",
        ),
    )
    op.create_index("ix_recovery_drills_tenant_id_scope", "recovery_drills", ["tenant_id", "scope"])
    op.create_index("ix_recovery_drills_performed_at", "recovery_drills", ["performed_at"])

    op.create_table(
        "storage_checks",
        sa.Column("check_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("contribution_id", INV_ID, nullable=False),
        sa.Column("reachable", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("sampled_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("mismatch_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("free_bytes", sa.BigInteger),
        sa.Column("healthy", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("checked_at", TS, nullable=False, server_default=_now()),
        sa.Column("detail", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(
            ["tenant_id", "contribution_id"],
            ["storage_contributions.tenant_id", "storage_contributions.contribution_id"],
            name="fk_storage_checks_tenant_id_contribution_id",
        ),
        sa.UniqueConstraint("tenant_id", "check_id", name="uq_storage_checks_tenant_id_check_id"),
        sa.CheckConstraint("sampled_count >= 0", name="sampled_count_non_negative"),
        sa.CheckConstraint("mismatch_count >= 0", name="mismatch_count_non_negative"),
        sa.CheckConstraint("mismatch_count <= sampled_count", name="mismatches_within_sample"),
        sa.CheckConstraint(
            "free_bytes IS NULL OR free_bytes >= 0", name="free_bytes_non_negative"
        ),
        sa.CheckConstraint(
            "NOT healthy OR (reachable AND mismatch_count = 0)",
            name="healthy_requires_no_mismatch",
        ),
    )
    op.create_index("ix_storage_checks_tenant_id_checked_at", "storage_checks", ["tenant_id", "checked_at"])

    op.create_table(
        "release_manifests",
        sa.Column("release_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("components", JSONB, nullable=False),
        sa.Column("component_count", sa.Integer, nullable=False),
        sa.Column("manifest_sha256", SHA256, nullable=False),
        sa.Column("created_by_user_id", INV_ID, nullable=False),
        sa.Column("created_at", TS, nullable=False, server_default=_now()),
        sa.UniqueConstraint(
            "tenant_id", "release_id", name="uq_release_manifests_tenant_id_release_id"
        ),
        sa.UniqueConstraint("tenant_id", "version", name="uq_release_manifests_tenant_id_version"),
        sa.CheckConstraint(
            "manifest_sha256 = lower(manifest_sha256)", name="manifest_hash_is_lowercase"
        ),
        sa.CheckConstraint("component_count > 0", name="component_count_positive"),
    )
    op.create_index(
        "ix_release_manifests_tenant_id_created_at", "release_manifests", ["tenant_id", "created_at"]
    )

    op.create_table(
        "acceptance_records",
        sa.Column("acceptance_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("release_id", INV_ID, nullable=False),
        sa.Column("acceptance_id_ref", sa.String(16), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("accepted_manifest_sha256", SHA256, nullable=False),
        sa.Column(
            "known_limitations", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column("accepted_by_user_id", INV_ID, nullable=False),
        sa.Column("decided_at", TS, nullable=False, server_default=_now()),
        sa.Column("notes", sa.Text),
        sa.ForeignKeyConstraint(
            ["tenant_id", "release_id"],
            ["release_manifests.tenant_id", "release_manifests.release_id"],
            name="fk_acceptance_records_tenant_id_release_id",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "accepted_by_user_id"],
            ["users.tenant_id", "users.user_id"],
            name="fk_acceptance_records_tenant_id_accepted_by_user_id",
        ),
        sa.UniqueConstraint(
            "tenant_id", "acceptance_id", name="uq_acceptance_records_tenant_id_acceptance_id"
        ),
        sa.UniqueConstraint(
            "release_id", "acceptance_id_ref", name="uq_acceptance_records_release_criterion"
        ),
        sa.CheckConstraint(
            "outcome IN ('accepted','conditional','rejected')", name="outcome_allowed"
        ),
        sa.CheckConstraint(
            "accepted_manifest_sha256 = lower(accepted_manifest_sha256)",
            name="accepted_hash_is_lowercase",
        ),
        sa.CheckConstraint(
            "outcome <> 'conditional' OR jsonb_array_length(known_limitations) > 0",
            name="conditional_requires_limitations",
        ),
    )
    op.create_index(
        "ix_acceptance_records_tenant_id_release_id", "acceptance_records", ["tenant_id", "release_id"]
    )

    op.create_table(
        "permission_snapshots",
        sa.Column("snapshot_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("subject_type", sa.String(16), nullable=False),
        sa.Column("subject_id", sa.String(64), nullable=False),
        sa.Column("grants", JSONB, nullable=False),
        sa.Column("digest_sha256", SHA256, nullable=False),
        sa.Column("taken_at", TS, nullable=False, server_default=_now()),
        sa.UniqueConstraint(
            "tenant_id", "snapshot_id", name="uq_permission_snapshots_tenant_id_snapshot_id"
        ),
        sa.CheckConstraint(
            "subject_type IN ('user','role','node','app_role')", name="subject_type_allowed"
        ),
        sa.CheckConstraint("digest_sha256 = lower(digest_sha256)", name="digest_is_lowercase"),
    )
    op.create_index(
        "ix_permission_snapshots_tenant_id_taken_at", "permission_snapshots", ["tenant_id", "taken_at"]
    )

    _install_rls()


def _install_rls() -> None:
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
        "permission_snapshots",
        "acceptance_records",
        "release_manifests",
        "storage_checks",
        "recovery_drills",
        "backup_records",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
