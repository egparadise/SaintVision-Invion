"""Durable internal product-build intent queue (0059).

Revision ``0058_release_acceptance_resolver`` is the only parent.  This revision
does not expose a route and does not enable BuildKit dispatch.  It gives a trusted
internal producer one immutable place to persist the exact ``BuildRequest``,
``BuildPlan`` and ``PolicyDecision`` documents which the product worker later
passes to ``BuildExecutionService``.

The application role may insert and read an intent, and may update only its
server-guarded lifecycle columns.  Payload identity and the PostgreSQL-canonical
document digests never change.  A pending row is claimed with ``FOR UPDATE SKIP
LOCKED`` by application code; the database trigger permits only
``pending -> claimed -> completed``.  There is no retry transition: an ambiguous
worker crash remains claimed and requires reconciliation rather than a second
external dispatch.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0059_build_execution_intents"
down_revision = "0058_release_acceptance_resolver"
branch_labels = None
depends_on = None

APP_ROLE = "inv_kernel"
TENANT_EXPR = "NULLIF(current_setting('inv.tenant_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "build_execution_intents",
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
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("clock_timestamp()"),
        ),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint("length(policy_version) BETWEEN 1 AND 200", name="policy_version_length"),
        sa.CheckConstraint(
            "evidence_id ~ '^evd_[0-9A-HJKMNP-TV-Z]{26}$'", name="evidence_id_shape"
        ),
        sa.CheckConstraint("length(actor_id) BETWEEN 1 AND 200", name="actor_id_length"),
        sa.CheckConstraint(
            "status IN ('pending','claimed','completed')", name="status_allowed"
        ),
        sa.CheckConstraint(
            "(status = 'pending' AND claimed_at IS NULL AND completed_at IS NULL) OR "
            "(status = 'claimed' AND claimed_at IS NOT NULL AND completed_at IS NULL) OR "
            "(status = 'completed' AND claimed_at IS NOT NULL AND completed_at IS NOT NULL)",
            name="status_timestamps_match",
        ),
        schema="inv",
    )
    op.create_index(
        "ix_build_execution_intents_pending",
        "build_execution_intents",
        ["tenant_id", "created_at", "project_id", "run_id"],
        unique=False,
        schema="inv",
        postgresql_where=sa.text("status = 'pending'"),
    )

    op.execute(
        """
        CREATE FUNCTION inv.build_execution_intent_guard()
        RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER
        SET search_path = pg_catalog
        AS $fn$
        DECLARE
          v_now timestamptz;
        BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'build execution intents are not deletable'
              USING ERRCODE = 'check_violation',
                    CONSTRAINT = 'build_execution_intent_not_deletable';
          END IF;

          IF TG_OP = 'INSERT' THEN
            IF NEW.status <> 'pending'
               OR NEW.claimed_at IS NOT NULL OR NEW.completed_at IS NOT NULL THEN
              RAISE EXCEPTION 'build execution intents begin pending'
                USING ERRCODE = 'check_violation',
                      CONSTRAINT = 'build_execution_intent_begins_pending';
            END IF;
            IF NEW.request->>'tenantId' IS DISTINCT FROM NEW.tenant_id::text
               OR NEW.plan->>'tenantId' IS DISTINCT FROM NEW.tenant_id::text
               OR NEW.decision->>'tenantId' IS DISTINCT FROM NEW.tenant_id::text
               OR NEW.request->>'projectId' IS DISTINCT FROM NEW.project_id
               OR NEW.plan->>'projectId' IS DISTINCT FROM NEW.project_id
               OR NEW.decision->>'projectId' IS DISTINCT FROM NEW.project_id
               OR NEW.plan->>'policyVersion' IS DISTINCT FROM NEW.policy_version
               OR NEW.plan->>'policyDecisionId' IS DISTINCT FROM NEW.decision->>'decisionId'
            THEN
              RAISE EXCEPTION 'build execution intent scope or policy binding differs'
                USING ERRCODE = 'check_violation',
                      CONSTRAINT = 'build_execution_intent_exact_binding';
            END IF;
            NEW.request_sha256 := encode(sha256(convert_to(NEW.request::text, 'UTF8')), 'hex');
            NEW.plan_sha256 := encode(sha256(convert_to(NEW.plan::text, 'UTF8')), 'hex');
            NEW.decision_sha256 := encode(sha256(convert_to(NEW.decision::text, 'UTF8')), 'hex');
            RETURN NEW;
          END IF;

          IF (NEW.tenant_id, NEW.project_id, NEW.run_id, NEW.request, NEW.plan,
              NEW.decision, NEW.request_sha256, NEW.plan_sha256, NEW.decision_sha256,
              NEW.policy_version, NEW.evidence_id, NEW.actor_id, NEW.created_at)
             IS DISTINCT FROM
             (OLD.tenant_id, OLD.project_id, OLD.run_id, OLD.request, OLD.plan,
              OLD.decision, OLD.request_sha256, OLD.plan_sha256, OLD.decision_sha256,
              OLD.policy_version, OLD.evidence_id, OLD.actor_id, OLD.created_at)
          THEN
            RAISE EXCEPTION 'build execution intent payload is immutable'
              USING ERRCODE = 'check_violation',
                    CONSTRAINT = 'build_execution_intent_payload_immutable';
          END IF;

          v_now := clock_timestamp();
          IF OLD.status = 'pending' AND NEW.status = 'claimed' THEN
            NEW.claimed_at := v_now;
            NEW.completed_at := NULL;
          ELSIF OLD.status = 'claimed' AND NEW.status = 'completed' THEN
            NEW.claimed_at := OLD.claimed_at;
            NEW.completed_at := v_now;
          ELSE
            RAISE EXCEPTION 'invalid build execution intent transition'
              USING ERRCODE = 'check_violation',
                    CONSTRAINT = 'build_execution_intent_transition';
          END IF;
          RETURN NEW;
        END $fn$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION inv.build_execution_intent_guard() FROM PUBLIC")
    op.execute(f"REVOKE ALL ON FUNCTION inv.build_execution_intent_guard() FROM {APP_ROLE}")
    op.execute(
        "CREATE TRIGGER build_execution_intent_guard "
        "BEFORE INSERT OR UPDATE OR DELETE ON inv.build_execution_intents "
        "FOR EACH ROW EXECUTE FUNCTION inv.build_execution_intent_guard()"
    )

    op.execute("ALTER TABLE inv.build_execution_intents ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE inv.build_execution_intents FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY build_execution_intents_tenant_isolation "
        f"ON inv.build_execution_intents FOR ALL TO {APP_ROLE} "
        f"USING (tenant_id = {TENANT_EXPR}) WITH CHECK (tenant_id = {TENANT_EXPR})"
    )
    op.execute("GRANT SELECT, INSERT ON inv.build_execution_intents TO inv_kernel")
    op.execute(
        "GRANT UPDATE(status, claimed_at, completed_at) "
        "ON inv.build_execution_intents TO inv_kernel"
    )


def downgrade() -> None:
    connection = op.get_bind()
    if connection.execute(sa.text("SELECT count(*) FROM inv.build_execution_intents")).scalar_one():
        raise RuntimeError(
            "0059_build_execution_intents cannot discard queued or completed product-build intents"
        )
    op.execute(
        "DROP TRIGGER IF EXISTS build_execution_intent_guard ON inv.build_execution_intents"
    )
    op.execute("DROP FUNCTION IF EXISTS inv.build_execution_intent_guard()")
    op.drop_index(
        "ix_build_execution_intents_pending",
        table_name="build_execution_intents",
        schema="inv",
    )
    op.drop_table("build_execution_intents", schema="inv")
