"""Server-owned S08-BE build preparation authority.

No caller-authored BuildRequest, BuildPlan, policy decision, provider, lease, or
secret value is stored here.  The approval snapshot and the 0060 admission are
the document authorities on either side of human quorum.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0061_build_preparations"
down_revision = "0060_build_execution_admissions"
branch_labels = None
depends_on = None

APP_ROLE = "inv_kernel"
TENANT_EXPR = "NULLIF(current_setting('inv.tenant_id', true), '')::uuid"


def _tenant_policy(table: str) -> None:
    op.execute(f"ALTER TABLE inv.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE inv.{table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {table}_tenant_isolation ON inv.{table} FOR ALL TO {APP_ROLE} "
        f"USING (tenant_id = {TENANT_EXPR}) WITH CHECK (tenant_id = {TENANT_EXPR})"
    )


def upgrade() -> None:
    op.create_table(
        "build_policy_profiles",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("profile_id", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("project_ids", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("context_path", sa.Text(), nullable=False),
        sa.Column("dockerfile_path", sa.Text(), nullable=False),
        sa.Column("target_platform", sa.Text(), nullable=False),
        sa.Column("target_stage", sa.Text(), nullable=False),
        sa.Column("network_policy_id", sa.Text(), nullable=False),
        sa.Column("cache_policy_id", sa.Text(), nullable=False),
        sa.Column("cache_mode", sa.Text(), nullable=False),
        sa.Column("secret_aliases", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("clock_timestamp()")),
        sa.PrimaryKeyConstraint("tenant_id", "profile_id", "version"),
        sa.ForeignKeyConstraint(["tenant_id"], ["inv.tenants.tenant_id"]),
        sa.CheckConstraint("profile_id ~ '^bpp_[0-9A-HJKMNP-TV-Z]{26}$'", name="profile_id_shape"),
        sa.CheckConstraint("version > 0", name="profile_version_positive"),
        sa.CheckConstraint("cardinality(project_ids) > 0", name="profile_projects_nonempty"),
        sa.CheckConstraint("target_platform ~ '^linux/(amd64|arm64)$'", name="profile_platform_allowed"),
        sa.CheckConstraint("network_policy_id = 'none'", name="profile_network_fail_closed"),
        sa.CheckConstraint(
            "cache_mode IN ('disabled','read-only')", name="profile_cache_mode_allowed"
        ),
        sa.CheckConstraint("timeout_seconds BETWEEN 1 AND 3600", name="profile_timeout_bounded"),
        schema="inv",
    )
    op.create_table(
        "build_preparations",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("build_id", sa.Text(), nullable=False),
        sa.Column("source_run_id", sa.Text(), nullable=False),
        sa.Column("checkout_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_attempt", sa.Integer(), nullable=False),
        sa.Column("source_recovery_epoch", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_revision", sa.BigInteger(), nullable=False),
        sa.Column("source_snapshot_sha256", sa.CHAR(64), nullable=False),
        sa.Column("source_capsule_sha256", sa.CHAR(64), nullable=False),
        sa.Column("source_capsule_locator", sa.Text(), nullable=False),
        sa.Column("source_capsule_retained_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approval_id", sa.Text(), nullable=False),
        sa.Column("requester_id", sa.Text(), nullable=False),
        sa.Column("profile_id", sa.Text(), nullable=False),
        sa.Column("profile_version", sa.Integer(), nullable=False),
        sa.Column("expected_run_version", sa.BigInteger(), nullable=False),
        sa.Column("bound_run_version", sa.BigInteger(), nullable=False),
        sa.Column("request_sha256", sa.CHAR(64), nullable=False),
        sa.Column("decision_sha256", sa.CHAR(64), nullable=False),
        sa.Column("decision_identity_sha256", sa.CHAR(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("clock_timestamp()")),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("tenant_id", "project_id", "run_id", "build_id"),
        sa.UniqueConstraint("tenant_id", "run_id", name="uq_build_preparations_run"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "project_id", "run_id"],
            ["inv.runs.tenant_id", "inv.runs.project_id", "inv.runs.run_id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "project_id", "source_run_id"],
            ["inv.runs.tenant_id", "inv.runs.project_id", "inv.runs.run_id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "checkout_id"],
            ["inv.workspace_checkouts.tenant_id", "inv.workspace_checkouts.checkout_id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "approval_id"],
            ["inv.approval_requests.tenant_id", "inv.approval_requests.approval_id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "profile_id", "profile_version"],
            ["inv.build_policy_profiles.tenant_id", "inv.build_policy_profiles.profile_id",
             "inv.build_policy_profiles.version"],
        ),
        sa.CheckConstraint("build_id ~ '^bld_[0-9A-HJKMNP-TV-Z]{26}$'", name="build_id_shape"),
        sa.CheckConstraint(
            "source_attempt > 0 AND source_revision > 0",
            name="build_preparation_source_cursors_positive",
        ),
        sa.CheckConstraint(
            "source_snapshot_sha256 ~ '^[0-9a-f]{64}$' AND "
            "source_capsule_sha256 ~ '^[0-9a-f]{64}$' AND "
            "request_sha256 ~ '^[0-9a-f]{64}$' AND "
            "decision_sha256 ~ '^[0-9a-f]{64}$' AND "
            "decision_identity_sha256 ~ '^[0-9a-f]{64}$'",
            name="build_preparation_digests_lowercase",
        ),
        sa.CheckConstraint("expected_run_version > 0 AND bound_run_version > 0",
                           name="build_preparation_versions_positive"),
        sa.CheckConstraint("expires_at > created_at", name="build_preparation_expiry_future"),
        sa.CheckConstraint(
            "source_capsule_retained_until >= created_at + interval '35 days'",
            name="build_capsule_retention_minimum",
        ),
        schema="inv",
    )
    op.create_index(
        "ix_build_preparations_retention", "build_preparations",
        ["tenant_id", "created_at"], schema="inv"
    )
    op.create_table(
        "build_preparation_rate_windows",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("subject_id", sa.Text(), nullable=False),
        sa.Column("operation", sa.Text(), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("clock_timestamp()")),
        sa.PrimaryKeyConstraint(
            "tenant_id", "project_id", "scope", "subject_id", "operation", "window_started_at"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "project_id"], ["inv.projects.tenant_id", "inv.projects.project_id"]
        ),
        sa.CheckConstraint("scope IN ('subject','project','tenant-project')", name="rate_scope_allowed"),
        sa.CheckConstraint("operation IN ('prepare','enqueue','combined')", name="rate_operation_allowed"),
        sa.CheckConstraint("count > 0", name="rate_count_positive"),
        schema="inv",
    )

    op.execute("""
        CREATE FUNCTION inv.build_policy_profile_guard() RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $fn$
        BEGIN
          RAISE EXCEPTION 'build policy profiles are append-only'
            USING ERRCODE='check_violation', CONSTRAINT='build_policy_profile_append_only';
        END $fn$""")
    op.execute("""
        CREATE FUNCTION inv.build_preparation_guard() RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $fn$
        BEGIN
          IF TG_OP='DELETE' THEN
            RAISE EXCEPTION 'build preparations are retained for at least 35 days'
              USING ERRCODE='check_violation', CONSTRAINT='build_preparation_retained';
          END IF;
          IF (to_jsonb(NEW)-'queued_at') IS DISTINCT FROM (to_jsonb(OLD)-'queued_at')
             OR OLD.queued_at IS NOT NULL OR NEW.queued_at IS NULL THEN
            RAISE EXCEPTION 'build preparation payload is immutable'
              USING ERRCODE='check_violation', CONSTRAINT='build_preparation_immutable';
          END IF;
          RETURN NEW;
        END $fn$""")
    for fn in ("build_policy_profile_guard", "build_preparation_guard"):
        op.execute(f"REVOKE ALL ON FUNCTION inv.{fn}() FROM PUBLIC")
        op.execute(f"REVOKE ALL ON FUNCTION inv.{fn}() FROM {APP_ROLE}")
    op.execute("CREATE TRIGGER build_policy_profile_guard BEFORE UPDATE OR DELETE ON inv.build_policy_profiles FOR EACH ROW EXECUTE FUNCTION inv.build_policy_profile_guard()")
    op.execute("CREATE TRIGGER build_preparation_guard BEFORE UPDATE OR DELETE ON inv.build_preparations FOR EACH ROW EXECUTE FUNCTION inv.build_preparation_guard()")

    for table in ("build_policy_profiles", "build_preparations", "build_preparation_rate_windows"):
        _tenant_policy(table)
    op.execute("GRANT SELECT ON inv.build_policy_profiles TO inv_kernel")
    op.execute("GRANT SELECT, INSERT ON inv.build_preparations TO inv_kernel")
    op.execute("GRANT UPDATE(queued_at) ON inv.build_preparations TO inv_kernel")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON inv.build_preparation_rate_windows TO inv_kernel")


def downgrade() -> None:
    connection = op.get_bind()
    for table in ("build_preparations", "build_policy_profiles", "build_preparation_rate_windows"):
        if connection.execute(sa.text(f"SELECT count(*) FROM inv.{table}")).scalar_one():
            raise RuntimeError("0061_build_preparations cannot discard retained build authority")
    op.execute("DROP TRIGGER IF EXISTS build_preparation_guard ON inv.build_preparations")
    op.execute("DROP TRIGGER IF EXISTS build_policy_profile_guard ON inv.build_policy_profiles")
    op.execute("DROP FUNCTION IF EXISTS inv.build_preparation_guard()")
    op.execute("DROP FUNCTION IF EXISTS inv.build_policy_profile_guard()")
    op.drop_table("build_preparation_rate_windows", schema="inv")
    op.drop_index("ix_build_preparations_retention", table_name="build_preparations", schema="inv")
    op.drop_table("build_preparations", schema="inv")
    op.drop_table("build_policy_profiles", schema="inv")
