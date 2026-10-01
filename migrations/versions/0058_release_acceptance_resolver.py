"""Release acceptance target and Evidence identity binding (0058).

Revision ``0057_release_acceptance_quorum`` owns the two-person decision rows.  This
revision supplies the other half of that decision: an Evidence identity computed by
PostgreSQL from the stored envelope and an append-only release binding whose project is
re-derived through Evidence -> Run -> Workload.  Caller supplied hashes and projects
are never authority.

The Git target registry remains the source of truth.  A release records the exact
registry version, Git blob and file SHA-256 it used; all three are nullable together so
pre-0058 releases remain classified as unresolved rather than silently adopting the
current registry.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0058_release_acceptance_resolver"
down_revision = "0057_release_acceptance_quorum"
branch_labels = None
depends_on = None

INV_ID = sa.CHAR(30)
SHA1 = sa.CHAR(40)
SHA256 = sa.CHAR(64)
UUID = postgresql.UUID(as_uuid=True)
TS = sa.DateTime(timezone=True)

APP_ROLE = "inv_app"
TENANT_EXPR = "NULLIF(current_setting('inv.tenant_id', true), '')::uuid"


def _digest_object(row: str) -> str:
    """The exact PostgreSQL-16 JSONB text whose bytes define digest v1."""

    return f"""pg_catalog.jsonb_build_object(
      'schemaVersion', 'evidence-envelope-digest:1',
      'evidenceId', {row}.evidence_id::text,
      'recordedAt', pg_catalog.to_char(
          {row}.recorded_at AT TIME ZONE 'UTC',
          'YYYY-MM-DD\"T\"HH24:MI:SS.US\"Z\"'),
      'tenantId', {row}.tenant_id::text,
      'runId', {row}.run_id::text,
      'stepId', {row}.step_id::text,
      'traceId', {row}.trace_id::text,
      'actorType', {row}.actor_type,
      'actorId', {row}.actor_id,
      'action', {row}.action,
      'policyId', {row}.policy_id,
      'effect', {row}.effect,
      'approvalId', {row}.approval_id::text,
      'inputSchema', {row}.input_schema,
      'inputSha256', {row}.input_sha256::text,
      'outputSchema', {row}.output_schema,
      'outputRef', {row}.output_ref,
      'result', {row}.result,
      'telemetry', {row}.telemetry,
      'componentVersions', {row}.component_versions
    )::text"""


def _digest_expression(row: str) -> str:
    return (
        "pg_catalog.encode(public.digest(pg_catalog.convert_to("
        "'saintvision:evidence-envelope:v1' || pg_catalog.chr(10) || "
        f"{_digest_object(row)}, 'UTF8'), 'sha256'), 'hex')::char(64)"
    )


def upgrade() -> None:
    # ``digest(bytea,text)`` is supplied by pgcrypto.  Keep the extension on downgrade:
    # another consumer may already use it and extension ownership is deployment-wide.
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public")

    op.add_column(
        "evidence_envelopes", sa.Column("envelope_sha256", SHA256, nullable=True)
    )
    op.create_check_constraint(
        "envelope_digest_is_lowercase",
        "evidence_envelopes",
        "envelope_sha256 IS NULL OR envelope_sha256 ~ '^[0-9a-f]{64}$'",
    )
    op.create_index(
        "ix_evidence_envelopes_tenant_evidence_recorded",
        "evidence_envelopes",
        ["tenant_id", "evidence_id", "recorded_at"],
    )

    helper_expr = _digest_expression("p_row")
    op.execute(
        f"""
        CREATE FUNCTION public.evidence_envelope_digest_v1(
            p_row public.evidence_envelopes
        ) RETURNS char(64)
        LANGUAGE sql SECURITY INVOKER IMMUTABLE
        SET search_path = pg_catalog
        AS $fn$ SELECT {helper_expr} $fn$
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.evidence_envelope_digest_v1("
        "public.evidence_envelopes) FROM PUBLIC"
    )
    op.execute(
        f"REVOKE ALL ON FUNCTION public.evidence_envelope_digest_v1("
        f"public.evidence_envelopes) FROM {APP_ROLE}"
    )

    trigger_expr = _digest_expression("NEW")
    op.execute(
        f"""
        CREATE FUNCTION public.evidence_envelope_digest_on_insert()
        RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER
        SET search_path = pg_catalog
        AS $fn$
        BEGIN
          NEW.envelope_sha256 := {trigger_expr};
          RETURN NEW;
        END $fn$
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.evidence_envelope_digest_on_insert() FROM PUBLIC"
    )
    op.execute(
        f"REVOKE ALL ON FUNCTION public.evidence_envelope_digest_on_insert() FROM {APP_ROLE}"
    )
    op.execute(
        "CREATE TRIGGER evidence_envelope_digest_before_insert "
        "BEFORE INSERT ON public.evidence_envelopes FOR EACH ROW "
        "EXECUTE FUNCTION public.evidence_envelope_digest_on_insert()"
    )

    # A release recorded before this revision stays unresolved.  All three values are a
    # unit: version without bytes, or bytes without the Git blob, is not a pin.
    op.add_column(
        "release_manifests", sa.Column("target_registry_version", sa.Integer, nullable=True)
    )
    op.add_column(
        "release_manifests", sa.Column("target_registry_git_blob_sha", SHA1, nullable=True)
    )
    op.add_column(
        "release_manifests", sa.Column("target_registry_file_sha256", SHA256, nullable=True)
    )
    op.create_check_constraint(
        "target_registry_pin_is_whole",
        "release_manifests",
        "(target_registry_version IS NULL AND target_registry_git_blob_sha IS NULL "
        "AND target_registry_file_sha256 IS NULL) OR "
        "(target_registry_version IS NOT NULL AND target_registry_git_blob_sha IS NOT NULL "
        "AND target_registry_file_sha256 IS NOT NULL)",
    )
    op.create_check_constraint(
        "target_registry_version_positive",
        "release_manifests",
        "target_registry_version IS NULL OR target_registry_version > 0",
    )
    op.create_check_constraint(
        "target_registry_blob_is_lowercase",
        "release_manifests",
        "target_registry_git_blob_sha IS NULL OR "
        "target_registry_git_blob_sha ~ '^[0-9a-f]{40}$'",
    )
    op.create_check_constraint(
        "target_registry_digest_is_lowercase",
        "release_manifests",
        "target_registry_file_sha256 IS NULL OR "
        "target_registry_file_sha256 ~ '^[0-9a-f]{64}$'",
    )

    op.create_table(
        "release_evidence_bindings",
        sa.Column("tenant_id", UUID, primary_key=True),
        sa.Column("release_id", INV_ID, primary_key=True),
        sa.Column("evidence_id", INV_ID, primary_key=True),
        sa.Column("evidence_recorded_at", TS, primary_key=True),
        sa.Column("project_id", INV_ID, nullable=False),
        sa.Column("envelope_sha256", SHA256, nullable=False),
        sa.Column("bound_at", TS, nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["tenant_id", "release_id"],
            ["release_manifests.tenant_id", "release_manifests.release_id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "project_id"], ["projects.tenant_id", "projects.project_id"]
        ),
        sa.ForeignKeyConstraint(
            ["evidence_id", "evidence_recorded_at"],
            ["evidence_envelopes.evidence_id", "evidence_envelopes.recorded_at"],
        ),
        sa.CheckConstraint(
            "envelope_sha256 ~ '^[0-9a-f]{64}$'",
            name="binding_digest_is_lowercase",
        ),
    )
    op.create_index(
        "ix_release_evidence_bindings_page",
        "release_evidence_bindings",
        ["tenant_id", "release_id", "evidence_recorded_at", "evidence_id"],
    )

    op.execute(
        """
        CREATE FUNCTION public.release_evidence_binding_exact()
        RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER
        SET search_path = pg_catalog
        AS $fn$
        DECLARE
          v_project char(30);
          v_digest char(64);
        BEGIN
          SELECT w.project_id, e.envelope_sha256
            INTO v_project, v_digest
            FROM public.evidence_envelopes e
            JOIN public.runs r
              ON r.tenant_id = e.tenant_id AND r.run_id = e.run_id
            JOIN public.workloads w
              ON w.tenant_id = r.tenant_id AND w.workload_id = r.workload_id
           WHERE e.tenant_id = NEW.tenant_id
             AND e.evidence_id = NEW.evidence_id
             AND e.recorded_at = NEW.evidence_recorded_at;
          IF NOT FOUND THEN
            RAISE EXCEPTION 'the Evidence row is unavailable'
              USING ERRCODE = 'no_data_found';
          END IF;
          IF v_digest IS NULL THEN
            RAISE EXCEPTION 'legacy Evidence has no canonical envelope digest'
              USING ERRCODE = 'object_not_in_prerequisite_state';
          END IF;
          IF NEW.project_id IS DISTINCT FROM v_project THEN
            RAISE EXCEPTION 'binding project is not the Evidence project'
              USING ERRCODE = 'check_violation',
                    CONSTRAINT = 'binding_project_is_server_derived';
          END IF;
          IF NEW.envelope_sha256 IS DISTINCT FROM v_digest THEN
            RAISE EXCEPTION 'binding digest is not the stored Evidence digest'
              USING ERRCODE = 'check_violation',
                    CONSTRAINT = 'binding_digest_is_server_derived';
          END IF;
          RETURN NEW;
        END $fn$
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.release_evidence_binding_exact() FROM PUBLIC"
    )
    op.execute(
        f"REVOKE ALL ON FUNCTION public.release_evidence_binding_exact() FROM {APP_ROLE}"
    )
    op.execute(
        "CREATE TRIGGER release_evidence_binding_exact_before_insert "
        "BEFORE INSERT ON public.release_evidence_bindings FOR EACH ROW "
        "EXECUTE FUNCTION public.release_evidence_binding_exact()"
    )

    op.execute("ALTER TABLE release_evidence_bindings ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE release_evidence_bindings FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY release_evidence_bindings_tenant_isolation "
        f"ON release_evidence_bindings FOR ALL TO {APP_ROLE} "
        f"USING (tenant_id = {TENANT_EXPR}) WITH CHECK (tenant_id = {TENANT_EXPR})"
    )
    op.execute(f"GRANT SELECT, INSERT ON release_evidence_bindings TO {APP_ROLE}")


def downgrade() -> None:
    connection = op.get_bind()
    if connection.execute(sa.text("SELECT count(*) FROM release_evidence_bindings")).scalar_one():
        raise RuntimeError(
            "0058_release_acceptance_resolver cannot be reversed while release Evidence "
            "bindings exist"
        )
    if connection.execute(
        sa.text(
            "SELECT count(*) FROM release_manifests "
            "WHERE target_registry_version IS NOT NULL"
        )
    ).scalar_one():
        raise RuntimeError(
            "0058_release_acceptance_resolver cannot discard a recorded target registry pin"
        )

    op.execute(
        "DROP TRIGGER IF EXISTS release_evidence_binding_exact_before_insert "
        "ON release_evidence_bindings"
    )
    op.execute("DROP FUNCTION IF EXISTS public.release_evidence_binding_exact()")
    op.drop_table("release_evidence_bindings")

    op.drop_constraint("target_registry_digest_is_lowercase", "release_manifests", type_="check")
    op.drop_constraint("target_registry_blob_is_lowercase", "release_manifests", type_="check")
    op.drop_constraint("target_registry_version_positive", "release_manifests", type_="check")
    op.drop_constraint("target_registry_pin_is_whole", "release_manifests", type_="check")
    op.drop_column("release_manifests", "target_registry_file_sha256")
    op.drop_column("release_manifests", "target_registry_git_blob_sha")
    op.drop_column("release_manifests", "target_registry_version")

    op.execute(
        "DROP TRIGGER IF EXISTS evidence_envelope_digest_before_insert "
        "ON evidence_envelopes"
    )
    op.execute("DROP FUNCTION IF EXISTS public.evidence_envelope_digest_on_insert()")
    op.execute(
        "DROP FUNCTION IF EXISTS public.evidence_envelope_digest_v1("
        "public.evidence_envelopes)"
    )
    op.drop_index(
        "ix_evidence_envelopes_tenant_evidence_recorded",
        table_name="evidence_envelopes",
    )
    op.drop_constraint("envelope_digest_is_lowercase", "evidence_envelopes", type_="check")
    op.drop_column("evidence_envelopes", "envelope_sha256")
