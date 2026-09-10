"""S10 lineage: dataset, commit, image, model version, deployment.

Revision ID: 0004_s10_lineage
Revises: 0003_s09_context_eval
Create Date: 2026-09-09

S10-DB (lineage) and S10-ST (immutable model version, retention pin).

The identity rules are enforced by constraint rather than convention: an image
digest must match ``sha256:<64 hex>``, a commit must be a 40 or 64 character
hex SHA, and a released model version must already be verified and pinned. A
lineage record built on a mutable tag would read precisely and mean nothing.

Partitioned tables: none added by this revision. Stated rather than derived, as
in every revision since 0001 read a live constant and broke.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004_s10_lineage"
down_revision = "0003_s09_context_eval"
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
    "datasets",
    "dataset_versions",
    "code_commits",
    "container_images",
    "models",
    "model_versions",
    "model_lineage",
    "deployments",
)

#: Identity is immutable; the lifecycle advances. The application role gets
#: column-level UPDATE on exactly these columns, so content_sha256, version and
#: uri cannot be rewritten while stage, verification and the retention pin can
#: still move forward. Blanket append-only was tried first and was wrong — a
#: model version must become verified, pinned and released after insertion.
LIFECYCLE_UPDATE_COLUMNS = {
    "dataset_versions": ("retention_pinned_until",),
    "model_versions": ("stage", "verified_at", "retention_pinned_until"),
}


def _now():
    return sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "datasets",
        sa.Column("dataset_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("project_id", INV_ID, nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("sensitivity", sa.String(16), nullable=False, server_default="synthetic"),
        sa.Column("description", sa.Text),
        sa.Column("created_at", TS, nullable=False, server_default=_now()),
        sa.ForeignKeyConstraint(
            ["tenant_id", "project_id"],
            ["projects.tenant_id", "projects.project_id"],
            name="fk_datasets_tenant_id_project_id",
        ),
        sa.UniqueConstraint("tenant_id", "dataset_id", name="uq_datasets_tenant_id_dataset_id"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_datasets_tenant_id_name"),
        sa.CheckConstraint(
            "sensitivity IN ('synthetic','internal','restricted')", name="sensitivity_allowed"
        ),
    )

    op.create_table(
        "dataset_versions",
        sa.Column("dataset_version_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("dataset_id", INV_ID, nullable=False),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("content_sha256", SHA256, nullable=False),
        sa.Column("byte_size", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("record_count", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("uri", sa.Text, nullable=False),
        sa.Column("retention_pinned_until", TS),
        sa.Column("created_at", TS, nullable=False, server_default=_now()),
        sa.ForeignKeyConstraint(
            ["tenant_id", "dataset_id"],
            ["datasets.tenant_id", "datasets.dataset_id"],
            name="fk_dataset_versions_tenant_id_dataset_id",
        ),
        sa.UniqueConstraint(
            "tenant_id", "dataset_version_id", name="uq_dataset_versions_tenant_id_version_id"
        ),
        sa.UniqueConstraint(
            "dataset_id", "version", name="uq_dataset_versions_dataset_id_version"
        ),
        sa.CheckConstraint("byte_size >= 0", name="byte_size_non_negative"),
        sa.CheckConstraint("record_count >= 0", name="record_count_non_negative"),
        sa.CheckConstraint(
            "content_sha256 = lower(content_sha256)", name="checksum_is_lowercase"
        ),
    )

    op.create_table(
        "code_commits",
        sa.Column("commit_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("repository", sa.String(255), nullable=False),
        sa.Column("commit_sha", sa.String(64), nullable=False),
        sa.Column("ref", sa.String(255)),
        sa.Column("dirty", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("committed_at", TS),
        sa.Column("recorded_at", TS, nullable=False, server_default=_now()),
        sa.UniqueConstraint("tenant_id", "commit_id", name="uq_code_commits_tenant_id_commit_id"),
        sa.UniqueConstraint(
            "tenant_id", "repository", "commit_sha", name="uq_code_commits_repo_sha"
        ),
        sa.CheckConstraint(
            "commit_sha ~ '^[0-9a-f]{40}$' OR commit_sha ~ '^[0-9a-f]{64}$'",
            name="commit_sha_is_hex",
        ),
    )
    op.create_index("ix_code_commits_tenant_id_repository", "code_commits", ["tenant_id", "repository"])

    op.create_table(
        "container_images",
        sa.Column("image_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("repository", sa.String(255), nullable=False),
        sa.Column("digest", sa.String(80), nullable=False),
        sa.Column("tag", sa.String(128)),
        sa.Column("byte_size", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("built_at", TS),
        sa.Column("recorded_at", TS, nullable=False, server_default=_now()),
        sa.UniqueConstraint("tenant_id", "image_id", name="uq_container_images_tenant_id_image_id"),
        sa.UniqueConstraint("tenant_id", "digest", name="uq_container_images_tenant_id_digest"),
        sa.CheckConstraint("digest ~ '^sha256:[0-9a-f]{64}$'", name="digest_is_oci_sha256"),
    )
    op.create_index(
        "ix_container_images_tenant_id_repository", "container_images", ["tenant_id", "repository"]
    )

    op.create_table(
        "models",
        sa.Column("model_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("project_id", INV_ID, nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("task", sa.String(64)),
        sa.Column("description", sa.Text),
        sa.Column("created_at", TS, nullable=False, server_default=_now()),
        sa.ForeignKeyConstraint(
            ["tenant_id", "project_id"],
            ["projects.tenant_id", "projects.project_id"],
            name="fk_models_tenant_id_project_id",
        ),
        sa.UniqueConstraint("tenant_id", "model_id", name="uq_models_tenant_id_model_id"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_models_tenant_id_name"),
    )

    op.create_table(
        "model_versions",
        sa.Column("model_version_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("model_id", INV_ID, nullable=False),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("stage", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("content_sha256", SHA256, nullable=False),
        sa.Column("byte_size", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("uri", sa.Text, nullable=False),
        sa.Column("verified_at", TS),
        sa.Column("retention_pinned_until", TS),
        sa.Column("produced_by_run_id", INV_ID),
        sa.Column("created_at", TS, nullable=False, server_default=_now()),
        sa.ForeignKeyConstraint(
            ["tenant_id", "model_id"], ["models.tenant_id", "models.model_id"],
            name="fk_model_versions_tenant_id_model_id",
        ),
        sa.UniqueConstraint(
            "tenant_id", "model_version_id", name="uq_model_versions_tenant_id_version_id"
        ),
        sa.UniqueConstraint("model_id", "version", name="uq_model_versions_model_id_version"),
        sa.UniqueConstraint(
            "tenant_id", "content_sha256", name="uq_model_versions_tenant_id_content_sha256"
        ),
        sa.CheckConstraint("byte_size >= 0", name="byte_size_non_negative"),
        sa.CheckConstraint(
            "content_sha256 = lower(content_sha256)", name="checksum_is_lowercase"
        ),
        sa.CheckConstraint(
            "stage IN ('draft','candidate','released','retired')", name="stage_allowed"
        ),
        sa.CheckConstraint(
            "stage <> 'released' OR (verified_at IS NOT NULL AND retention_pinned_until IS NOT NULL)",
            name="release_requires_verification_and_pin",
        ),
    )
    op.create_index("ix_model_versions_tenant_id_stage", "model_versions", ["tenant_id", "stage"])

    op.create_table(
        "model_lineage",
        sa.Column("tenant_id", UUID, primary_key=True),
        sa.Column("model_version_id", INV_ID, primary_key=True),
        sa.Column("kind", sa.String(24), primary_key=True),
        sa.Column("subject_id", INV_ID, primary_key=True),
        sa.Column("relation", sa.String(32), nullable=False, server_default="derived_from"),
        sa.Column("recorded_at", TS, nullable=False, server_default=_now()),
        sa.ForeignKeyConstraint(
            ["tenant_id", "model_version_id"],
            ["model_versions.tenant_id", "model_versions.model_version_id"],
            name="fk_model_lineage_tenant_id_model_version_id",
        ),
        sa.CheckConstraint(
            "kind IN ('dataset_version','code_commit','container_image','eval_run','approval')",
            name="kind_allowed",
        ),
    )
    op.create_index("ix_model_lineage_tenant_id_kind", "model_lineage", ["tenant_id", "kind"])
    op.create_index("ix_model_lineage_subject_id", "model_lineage", ["subject_id"])

    op.create_table(
        "deployments",
        sa.Column("deployment_id", INV_ID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("model_version_id", INV_ID, nullable=False),
        sa.Column("environment", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("deployed_digest", SHA256, nullable=False),
        sa.Column("image_id", INV_ID),
        sa.Column("approval_id", INV_ID),
        sa.Column("deployed_by_user_id", INV_ID, nullable=False),
        sa.Column("deployed_at", TS, nullable=False, server_default=_now()),
        sa.Column("superseded_at", TS),
        sa.Column("notes", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(
            ["tenant_id", "model_version_id"],
            ["model_versions.tenant_id", "model_versions.model_version_id"],
            name="fk_deployments_tenant_id_model_version_id",
        ),
        sa.UniqueConstraint(
            "tenant_id", "deployment_id", name="uq_deployments_tenant_id_deployment_id"
        ),
        sa.CheckConstraint("environment IN ('lab','staging','pilot')", name="environment_allowed"),
        sa.CheckConstraint(
            "status IN ('pending','active','superseded','rolled_back','failed')",
            name="status_allowed",
        ),
        sa.CheckConstraint(
            "deployed_digest = lower(deployed_digest)", name="digest_is_lowercase"
        ),
        sa.CheckConstraint(
            "status = 'failed' OR approval_id IS NOT NULL", name="deployment_requires_approval"
        ),
    )
    op.create_index(
        "ix_deployments_tenant_id_environment_status",
        "deployments",
        ["tenant_id", "environment", "status"],
    )

    # One active deployment per environment per model. Enforced as a partial
    # unique index because "active" is the only status that must be exclusive —
    # superseded and rolled_back rows are history and there may be many.
    op.execute(
        "CREATE UNIQUE INDEX uq_deployments_one_active_per_environment "
        "ON deployments (tenant_id, model_version_id, environment) "
        "WHERE status = 'active'"
    )

    _install_rls()


def _install_rls() -> None:
    for table in NEW_TENANT_SCOPED:
        if table in LIFECYCLE_UPDATE_COLUMNS:
            # No DELETE, and UPDATE only on the named columns.
            op.execute(f"GRANT SELECT, INSERT ON {table} TO {APP_ROLE}")
            columns = ", ".join(LIFECYCLE_UPDATE_COLUMNS[table])
            op.execute(f"GRANT UPDATE ({columns}) ON {table} TO {APP_ROLE}")
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
        "deployments",
        "model_lineage",
        "model_versions",
        "models",
        "container_images",
        "code_commits",
        "dataset_versions",
        "datasets",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
