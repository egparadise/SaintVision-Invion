"""Committed authority for the internal S08-BE intent producer (0060).

The product worker may promote only an immutable admission written by the
trusted internal service.  This revision adds no route or CLI and does not
enable product dispatch.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0060_build_execution_admissions"
down_revision = "0059_build_execution_intents"
branch_labels = None
depends_on = None

APP_ROLE = "inv_kernel"
TENANT_EXPR = "NULLIF(current_setting('inv.tenant_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "build_execution_admissions",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("request", postgresql.JSONB(), nullable=False),
        sa.Column("plan", postgresql.JSONB(), nullable=False),
        sa.Column("decision", postgresql.JSONB(), nullable=False),
        sa.Column("request_sha256", sa.CHAR(64), nullable=False),
        sa.Column("plan_sha256", sa.CHAR(64), nullable=False),
        sa.Column("decision_sha256", sa.CHAR(64), nullable=False),
        sa.Column("policy_version", sa.Text(), nullable=False),
        sa.Column("evidence_id", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="ready"),
        sa.Column("last_error_code", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("clock_timestamp()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("clock_timestamp()"),
        ),
        sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("quarantined_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("tenant_id", "project_id", "run_id"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "project_id", "run_id"],
            ["inv.runs.tenant_id", "inv.runs.project_id", "inv.runs.run_id"],
        ),
        sa.CheckConstraint("jsonb_typeof(request) = 'object'", name="request_is_object"),
        sa.CheckConstraint("jsonb_typeof(plan) = 'object'", name="plan_is_object"),
        sa.CheckConstraint("jsonb_typeof(decision) = 'object'", name="decision_is_object"),
        sa.CheckConstraint(
            "request_sha256 ~ '^[0-9a-f]{64}$' AND "
            "plan_sha256 ~ '^[0-9a-f]{64}$' AND "
            "decision_sha256 ~ '^[0-9a-f]{64}$'",
            name="document_digests_are_lowercase",
        ),
        sa.CheckConstraint(
            "evidence_id ~ '^evd_[0-9A-HJKMNP-TV-Z]{26}$'",
            name="evidence_id_shape",
        ),
        sa.CheckConstraint("length(actor_id) BETWEEN 1 AND 200", name="actor_id_length"),
        sa.CheckConstraint(
            "length(policy_version) BETWEEN 1 AND 200", name="policy_version_length"
        ),
        sa.CheckConstraint("status IN ('ready','promoted','quarantined')", name="status_allowed"),
        sa.CheckConstraint(
            "last_error_code IS NULL OR last_error_code ~ '^[A-Z]+-[0-9]{4}$'",
            name="last_error_code_shape",
        ),
        sa.CheckConstraint("retry_count >= 0", name="retry_count_nonnegative"),
        schema="inv",
    )
    op.create_index(
        "ix_build_execution_admissions_ready",
        "build_execution_admissions",
        ["tenant_id", "created_at", "project_id", "run_id"],
        schema="inv",
        postgresql_where=sa.text("status = 'ready'"),
    )
    op.execute("""
        CREATE FUNCTION inv.build_execution_admission_guard()
        RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER
        SET search_path = pg_catalog
        AS $fn$
        DECLARE v_now timestamptz;
        BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'build execution admissions are not deletable'
              USING ERRCODE='check_violation',
                    CONSTRAINT='build_execution_admission_not_deletable';
          END IF;
          IF TG_OP = 'INSERT' THEN
            IF NEW.status <> 'ready' OR NEW.last_error_code IS NOT NULL
               OR NEW.retry_count <> 0
               OR NEW.promoted_at IS NOT NULL OR NEW.quarantined_at IS NOT NULL THEN
              RAISE EXCEPTION 'build execution admissions begin ready'
                USING ERRCODE='check_violation',
                      CONSTRAINT='build_execution_admission_begins_ready';
            END IF;
            IF NEW.request->>'tenantId' IS DISTINCT FROM NEW.tenant_id::text
               OR NEW.plan->>'tenantId' IS DISTINCT FROM NEW.tenant_id::text
               OR NEW.decision->>'tenantId' IS DISTINCT FROM NEW.tenant_id::text
               OR NEW.request->>'projectId' IS DISTINCT FROM NEW.project_id
               OR NEW.plan->>'projectId' IS DISTINCT FROM NEW.project_id
               OR NEW.decision->>'projectId' IS DISTINCT FROM NEW.project_id
               OR NEW.plan->>'policyVersion' IS DISTINCT FROM NEW.policy_version
               OR NEW.plan->>'policyDecisionId' IS DISTINCT FROM NEW.decision->>'decisionId'
               OR NEW.decision->>'subjectId' IS DISTINCT FROM NEW.actor_id
               OR NEW.plan->>'actionDigest' IS DISTINCT FROM NEW.decision->>'actionDigest'
               OR NEW.plan->>'policyExpiresAt' IS DISTINCT FROM NEW.decision->>'expiresAt'
            THEN
              RAISE EXCEPTION 'build execution admission scope or policy binding differs'
                USING ERRCODE='check_violation',
                      CONSTRAINT='build_execution_admission_exact_binding';
            END IF;
            NEW.request_sha256 := encode(sha256(convert_to(NEW.request::text,'UTF8')),'hex');
            NEW.plan_sha256 := encode(sha256(convert_to(NEW.plan::text,'UTF8')),'hex');
            NEW.decision_sha256 := encode(sha256(convert_to(NEW.decision::text,'UTF8')),'hex');
            RETURN NEW;
          END IF;
          IF (NEW.tenant_id,NEW.project_id,NEW.run_id,NEW.request,NEW.plan,NEW.decision,
              NEW.request_sha256,NEW.plan_sha256,NEW.decision_sha256,NEW.policy_version,
              NEW.evidence_id,NEW.actor_id,NEW.created_at)
             IS DISTINCT FROM
             (OLD.tenant_id,OLD.project_id,OLD.run_id,OLD.request,OLD.plan,OLD.decision,
              OLD.request_sha256,OLD.plan_sha256,OLD.decision_sha256,OLD.policy_version,
              OLD.evidence_id,OLD.actor_id,OLD.created_at) THEN
            RAISE EXCEPTION 'build execution admission payload is immutable'
              USING ERRCODE='check_violation',
                    CONSTRAINT='build_execution_admission_payload_immutable';
          END IF;
          v_now := clock_timestamp();
          IF OLD.status='ready' AND NEW.status='ready' THEN
            IF NEW.retry_count <> OLD.retry_count + 1
               OR NEW.next_attempt_at <= OLD.next_attempt_at
               OR NEW.last_error_code IS NULL THEN
              RAISE EXCEPTION 'a ready admission retry requires bounded backoff'
                USING ERRCODE='check_violation',
                      CONSTRAINT='build_execution_admission_retry_backoff';
            END IF;
            NEW.promoted_at := NULL;
            NEW.quarantined_at := NULL;
          ELSIF OLD.status='ready' AND NEW.status='promoted' THEN
            NEW.promoted_at := v_now;
            NEW.quarantined_at := NULL;
            NEW.last_error_code := NULL;
          ELSIF OLD.status='ready' AND NEW.status='quarantined' THEN
            IF NEW.last_error_code IS NULL THEN
              RAISE EXCEPTION 'a quarantined admission requires an error code'
                USING ERRCODE='check_violation',
                      CONSTRAINT='build_execution_admission_quarantine_error';
            END IF;
            NEW.promoted_at := NULL;
            NEW.quarantined_at := v_now;
          ELSE
            RAISE EXCEPTION 'invalid build execution admission transition'
              USING ERRCODE='check_violation',
                    CONSTRAINT='build_execution_admission_transition';
          END IF;
          RETURN NEW;
        END $fn$
        """)
    op.execute("REVOKE ALL ON FUNCTION inv.build_execution_admission_guard() FROM PUBLIC")
    op.execute(f"REVOKE ALL ON FUNCTION inv.build_execution_admission_guard() FROM {APP_ROLE}")
    op.execute(
        "CREATE TRIGGER build_execution_admission_guard "
        "BEFORE INSERT OR UPDATE OR DELETE ON inv.build_execution_admissions "
        "FOR EACH ROW EXECUTE FUNCTION inv.build_execution_admission_guard()"
    )
    op.execute("ALTER TABLE inv.build_execution_admissions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE inv.build_execution_admissions FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY build_execution_admissions_tenant_isolation "
        f"ON inv.build_execution_admissions FOR ALL TO {APP_ROLE} "
        f"USING (tenant_id = {TENANT_EXPR}) WITH CHECK (tenant_id = {TENANT_EXPR})"
    )
    op.execute("GRANT SELECT, INSERT ON inv.build_execution_admissions TO inv_kernel")
    op.execute(
        "GRANT UPDATE(status,last_error_code,retry_count,next_attempt_at,"
        "promoted_at,quarantined_at) "
        "ON inv.build_execution_admissions TO inv_kernel"
    )


def downgrade() -> None:
    connection = op.get_bind()
    if connection.execute(
        sa.text("SELECT count(*) FROM inv.build_execution_admissions")
    ).scalar_one():
        raise RuntimeError(
            "0060_build_execution_admissions cannot discard committed build authority"
        )
    op.execute(
        "DROP TRIGGER IF EXISTS build_execution_admission_guard "
        "ON inv.build_execution_admissions"
    )
    op.execute("DROP FUNCTION IF EXISTS inv.build_execution_admission_guard()")
    op.drop_index(
        "ix_build_execution_admissions_ready",
        table_name="build_execution_admissions",
        schema="inv",
    )
    op.drop_table("build_execution_admissions", schema="inv")
