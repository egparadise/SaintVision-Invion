"""S09 context, run record and evaluation.

Revision ID: 0003_s09_context_eval
Revises: 0002_s03_execution
Create Date: 2026-09-09

S09-DB (immutable Context, RunRecord, eval) and S09-ST (diff / test / trace
artifacts pinned into the RunRecord).

No vector column. ADR-009 forbids fixing an embedding dimension before the
model is chosen, and it has not been chosen. Adding ``vector(1024)`` now would
be a decision disguised as a schema detail.

No pgvector extension is enabled for the same reason.

The partitioned-table list is a literal, as in every revision: reading the live
constant is what broke 0001 when 0002 changed it.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_s09_context_eval"
down_revision = "0002_s03_execution"
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
    "context_snapshots",
    "context_bundles",
    "context_bundle_items",
    "run_records",
    "run_record_artifacts",
    "eval_suites",
    "eval_cases",
    "eval_runs",
    "eval_results",
)

#: INSERT and SELECT only for the application role. A sealed RunRecord that can
#: be updated is not a record, and a snapshot is immutable by construction so
#: UPDATE has no meaning. Deleting orphaned snapshots is the collector's job and
#: it runs as the owner.
NEW_APPEND_ONLY = (
    "context_snapshots",
    "run_records",
    "run_record_artifacts",
)


def _now():
    return sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "context_snapshots",
        sa.Column("tenant_id", UUID, primary_key=True),
        sa.Column("content_hash", SHA256, primary_key=True),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("byte_size", sa.BigInteger, nullable=False),
        sa.Column("first_seen_at", TS, nullable=False, server_default=_now()),
        sa.CheckConstraint("byte_size >= 0", name="byte_size_non_negative"),
        sa.CheckConstraint("content_hash = lower(content_hash)", name="hash_is_lowercase"),
    )
    op.create_index("ix_context_snapshots_first_seen_at", "context_snapshots", ["first_seen_at"])

    op.create_table(
        "context_bundles",
        sa.Column("bundle_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("run_id", INV_ID, nullable=False),
        sa.Column("bundle_hash", SHA256, nullable=False),
        sa.Column("item_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_bytes", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column(
            "retrieval_strategy", sa.String(16), nullable=False, server_default="explicit"
        ),
        sa.Column(
            "component_versions", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("token_estimate", sa.Integer),
        sa.Column("built_at", TS, nullable=False, server_default=_now()),
        sa.ForeignKeyConstraint(
            ["tenant_id", "run_id"], ["runs.tenant_id", "runs.run_id"],
            name="fk_context_bundles_tenant_id_run_id",
        ),
        sa.UniqueConstraint(
            "tenant_id", "bundle_id", name="uq_context_bundles_tenant_id_bundle_id"
        ),
        sa.CheckConstraint("item_count >= 0", name="item_count_non_negative"),
        sa.CheckConstraint("total_bytes >= 0", name="total_bytes_non_negative"),
        sa.CheckConstraint("bundle_hash = lower(bundle_hash)", name="hash_is_lowercase"),
        sa.CheckConstraint(
            "retrieval_strategy IN ('lexical','metadata','hybrid','explicit')",
            name="retrieval_strategy_allowed",
        ),
    )
    op.create_index("ix_context_bundles_tenant_id_run_id", "context_bundles", ["tenant_id", "run_id"])
    op.create_index("ix_context_bundles_bundle_hash", "context_bundles", ["bundle_hash"])

    op.create_table(
        "context_bundle_items",
        sa.Column("tenant_id", UUID, primary_key=True),
        sa.Column("bundle_id", INV_ID, primary_key=True),
        sa.Column("ordinal", sa.Integer, primary_key=True),
        sa.Column("item_id", sa.String(255), nullable=False),
        sa.Column("item_version", sa.Integer, nullable=False),
        sa.Column("content_hash", SHA256, nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("source_uri", sa.Text),
        sa.Column("confidence", sa.Float),
        sa.Column("redacted", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.ForeignKeyConstraint(
            ["tenant_id", "bundle_id"],
            ["context_bundles.tenant_id", "context_bundles.bundle_id"],
            name="fk_context_bundle_items_tenant_id_bundle_id",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "content_hash"],
            ["context_snapshots.tenant_id", "context_snapshots.content_hash"],
            name="fk_context_bundle_items_tenant_id_content_hash",
        ),
        sa.CheckConstraint("ordinal >= 0", name="ordinal_non_negative"),
        sa.CheckConstraint("item_version >= 1", name="item_version_positive"),
        sa.CheckConstraint(
            "kind IN ('document','code','message','tool_output','summary')",
            name="kind_allowed",
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="confidence_in_range",
        ),
    )
    op.create_index(
        "ix_context_bundle_items_tenant_id_content_hash",
        "context_bundle_items",
        ["tenant_id", "content_hash"],
    )

    op.create_table(
        "run_records",
        sa.Column("record_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("run_id", INV_ID, nullable=False),
        sa.Column("final_state", sa.String(16), nullable=False),
        sa.Column("termination_reason", sa.String(24), nullable=False),
        sa.Column("evidence_id", INV_ID),
        sa.Column("bundle_id", INV_ID),
        sa.Column("bundle_hash", SHA256),
        sa.Column("workload_spec_sha256", SHA256, nullable=False),
        sa.Column(
            "component_versions", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("attempt_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("sealed_at", TS, nullable=False, server_default=_now()),
        sa.ForeignKeyConstraint(
            ["tenant_id", "run_id"], ["runs.tenant_id", "runs.run_id"],
            name="fk_run_records_tenant_id_run_id",
        ),
        sa.UniqueConstraint("tenant_id", "record_id", name="uq_run_records_tenant_id_record_id"),
        sa.UniqueConstraint("run_id", name="uq_run_records_run_id"),
        sa.CheckConstraint(
            "final_state IN ('succeeded','failed','cancelled')",
            name="final_state_is_terminal",
        ),
    )
    op.create_index("ix_run_records_tenant_id_sealed_at", "run_records", ["tenant_id", "sealed_at"])

    op.create_table(
        "run_record_artifacts",
        sa.Column("tenant_id", UUID, primary_key=True),
        sa.Column("record_id", INV_ID, primary_key=True),
        sa.Column("artifact_id", INV_ID, primary_key=True),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("uri", sa.Text, nullable=False),
        sa.Column("checksum_sha256", SHA256, nullable=False),
        sa.Column("object_version", sa.String(128)),
        sa.Column("byte_size", sa.BigInteger, nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "record_id"],
            ["run_records.tenant_id", "run_records.record_id"],
            name="fk_run_record_artifacts_tenant_id_record_id",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "artifact_id"],
            ["artifacts.tenant_id", "artifacts.artifact_id"],
            name="fk_run_record_artifacts_tenant_id_artifact_id",
        ),
        sa.CheckConstraint(
            "role IN ('diff','test_report','trace','log','model','dataset','other')",
            name="role_allowed",
        ),
        sa.CheckConstraint("byte_size >= 0", name="byte_size_non_negative"),
    )
    op.create_index(
        "ix_run_record_artifacts_tenant_id_role", "run_record_artifacts", ["tenant_id", "role"]
    )

    op.create_table(
        "eval_suites",
        sa.Column("suite_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("case_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("definition_sha256", SHA256, nullable=False),
        sa.Column("created_at", TS, nullable=False, server_default=_now()),
        sa.UniqueConstraint("tenant_id", "suite_id", name="uq_eval_suites_tenant_id_suite_id"),
        sa.UniqueConstraint("tenant_id", "name", "version", name="uq_eval_suites_name_version"),
        sa.CheckConstraint("case_count >= 0", name="case_count_non_negative"),
    )

    op.create_table(
        "eval_cases",
        sa.Column("case_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("suite_id", INV_ID, nullable=False),
        sa.Column("key", sa.String(128), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column(
            "forbidden_behaviour", sa.Boolean, nullable=False, server_default=sa.text("false")
        ),
        sa.Column("weight", sa.Integer, nullable=False, server_default="1"),
        sa.Column("definition", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", TS, nullable=False, server_default=_now()),
        sa.ForeignKeyConstraint(
            ["tenant_id", "suite_id"], ["eval_suites.tenant_id", "eval_suites.suite_id"],
            name="fk_eval_cases_tenant_id_suite_id",
        ),
        sa.UniqueConstraint("tenant_id", "case_id", name="uq_eval_cases_tenant_id_case_id"),
        sa.UniqueConstraint("suite_id", "key", name="uq_eval_cases_suite_id_key"),
        sa.CheckConstraint(
            "category IN ('structured_output','tool_selection','coding_task',"
            "'policy_compliance','context_grounding')",
            name="category_allowed",
        ),
        sa.CheckConstraint("weight > 0", name="weight_positive"),
        sa.CheckConstraint(
            "NOT forbidden_behaviour OR weight = 1", name="forbidden_case_has_unit_weight"
        ),
    )
    op.create_index("ix_eval_cases_tenant_id_category", "eval_cases", ["tenant_id", "category"])

    op.create_table(
        "eval_runs",
        sa.Column("eval_run_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("suite_id", INV_ID, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="running"),
        sa.Column("total_cases", sa.Integer, nullable=False, server_default="0"),
        sa.Column("passed_cases", sa.Integer, nullable=False, server_default="0"),
        sa.Column("violations", sa.Integer, nullable=False, server_default="0"),
        sa.Column("passed_gate", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column(
            "component_versions", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("started_at", TS, nullable=False, server_default=_now()),
        sa.Column("ended_at", TS),
        sa.ForeignKeyConstraint(
            ["tenant_id", "suite_id"], ["eval_suites.tenant_id", "eval_suites.suite_id"],
            name="fk_eval_runs_tenant_id_suite_id",
        ),
        sa.UniqueConstraint("tenant_id", "eval_run_id", name="uq_eval_runs_tenant_id_eval_run_id"),
        sa.CheckConstraint("total_cases >= 0", name="total_cases_non_negative"),
        sa.CheckConstraint("passed_cases >= 0", name="passed_cases_non_negative"),
        sa.CheckConstraint("passed_cases <= total_cases", name="passed_within_total"),
        sa.CheckConstraint("violations >= 0", name="violations_non_negative"),
        sa.CheckConstraint("status IN ('running','completed','aborted')", name="status_allowed"),
        sa.CheckConstraint("NOT passed_gate OR violations = 0", name="gate_requires_no_violations"),
    )
    op.create_index("ix_eval_runs_tenant_id_started_at", "eval_runs", ["tenant_id", "started_at"])

    op.create_table(
        "eval_results",
        sa.Column("tenant_id", UUID, primary_key=True),
        sa.Column("eval_run_id", INV_ID, primary_key=True),
        sa.Column("case_id", INV_ID, primary_key=True),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("score", sa.Float),
        sa.Column("violated", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("observed", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("run_id", INV_ID),
        sa.Column("duration_ms", sa.Integer),
        sa.Column("recorded_at", TS, nullable=False, server_default=_now()),
        sa.ForeignKeyConstraint(
            ["tenant_id", "eval_run_id"],
            ["eval_runs.tenant_id", "eval_runs.eval_run_id"],
            name="fk_eval_results_tenant_id_eval_run_id",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"], ["eval_cases.tenant_id", "eval_cases.case_id"],
            name="fk_eval_results_tenant_id_case_id",
        ),
        sa.UniqueConstraint("eval_run_id", "case_id", name="uq_eval_results_eval_run_id_case_id"),
        sa.CheckConstraint(
            "outcome IN ('passed','failed','errored','skipped')", name="outcome_allowed"
        ),
        sa.CheckConstraint("score IS NULL OR (score >= 0 AND score <= 1)", name="score_in_range"),
        sa.CheckConstraint("NOT violated OR outcome = 'failed'", name="violation_implies_failure"),
    )
    op.create_index("ix_eval_results_tenant_id_eval_run_id", "eval_results", ["tenant_id", "eval_run_id"])
    op.create_index("ix_eval_results_violated", "eval_results", ["violated"])

    _install_rls()


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
        "eval_results",
        "eval_runs",
        "eval_cases",
        "eval_suites",
        "run_record_artifacts",
        "run_records",
        "context_bundle_items",
        "context_bundles",
        "context_snapshots",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
