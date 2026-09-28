"""Tenant-scoped service credentials for the MLflow mirror worker (design #168 §4).

Revision ID: 0051_service_credentials
Revises: 0050_dataset_digest_lookup
Create Date: 2026-09-28

Numbering (coordinator 2026-09-28 13:06 KST): 0047 (#128) -> 0048 (#159) ->
0049 (#172) -> 0050 (#174, dataset digest lookup) -> 0051 (this). This branch
carries the #174 head merged in, so 0050 exists here and the graph has one
head (``tools/migration_graph.py`` refuses two). Merge order #172 -> #174 -> #176.

Two tables, both tenant-scoped under RLS. The application role may INSERT and
SELECT; lifecycle columns (``revoked_at`` on a version, ``enabled`` and
``revoked_at`` on a grant) get column-level UPDATE so a credential can be
disabled or revoked without anything else being rewritable (the 0004 lifecycle
pattern). No secret bytes live here: a version is a file reference pinned by
device/inode and content digest, read by the existing descriptor-bound reader.

Boundary: ``inv.credential_*`` (0035) remains the run-bound contract and is not
touched.

Partitioned tables: none added by this revision.

The downgrade is a refusal: revocations and grants are an audit record of who
could use an operator credential and when.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0051_service_credentials"
down_revision = "0050_dataset_digest_lookup"
branch_labels = None
depends_on = None

INV_ID = sa.CHAR(30)
SHA256 = sa.CHAR(64)
UUID = postgresql.UUID(as_uuid=True)
TS = sa.DateTime(timezone=True)

APP_ROLE = "inv_app"
TENANT_EXPR = "NULLIF(current_setting('inv.tenant_id', true), '')::uuid"

PURPOSES = ("mlflow.mirror",)
LIFECYCLE_UPDATE_COLUMNS = {
    "service_credential_versions": ("revoked_at",),
    "service_credential_grants": ("enabled", "revoked_at"),
}


def _now():
    return sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "service_credential_versions",
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("credential_id", UUID, nullable=False),
        sa.Column("version_id", UUID, nullable=False),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("destination", sa.String(64), nullable=False),
        sa.Column("destination_uri_sha256", SHA256, nullable=False),
        sa.Column("file_name", sa.String(40), nullable=False),
        sa.Column("device", sa.BigInteger, nullable=False),
        sa.Column("inode", sa.BigInteger, nullable=False),
        sa.Column("content_sha256", SHA256, nullable=False),
        sa.Column("created_at", TS, nullable=False, server_default=_now()),
        sa.Column("revoked_at", TS),
        sa.PrimaryKeyConstraint("tenant_id", "credential_id", "version_id", name="pk_service_credential_versions"),
        sa.CheckConstraint("purpose IN (" + ",".join(f"'{p}'" for p in PURPOSES) + ")", name="purpose_allowed"),
        sa.CheckConstraint("destination ~ '^[a-z][a-z0-9-]{0,63}$'", name="destination_alias"),
        sa.CheckConstraint("destination_uri_sha256 ~ '^[0-9a-f]{64}$'", name="destination_uri_sha256_hex"),
        sa.CheckConstraint("file_name ~ '^[0-9a-f]{32}[.]secret$'", name="file_name_secret"),
        sa.CheckConstraint("content_sha256 ~ '^[0-9a-f]{64}$'", name="content_sha256_hex"),
        sa.CheckConstraint("device >= 0 AND inode >= 0", name="identity_non_negative"),
    )
    op.create_index(
        "ix_service_credential_versions_lookup",
        "service_credential_versions",
        ["tenant_id", "purpose", "destination"],
    )

    op.create_table(
        "service_credential_grants",
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("grant_id", INV_ID, nullable=False),
        sa.Column("credential_id", UUID, nullable=False),
        sa.Column("version_id", UUID, nullable=False),
        sa.Column("worker_principal", sa.String(64), nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("recovery_epoch", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", TS, nullable=False, server_default=_now()),
        sa.Column("expires_at", TS, nullable=False),
        sa.Column("revoked_at", TS),
        sa.PrimaryKeyConstraint("tenant_id", "grant_id", name="pk_service_credential_grants"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "credential_id", "version_id"],
            [
                "service_credential_versions.tenant_id",
                "service_credential_versions.credential_id",
                "service_credential_versions.version_id",
            ],
            name="fk_service_credential_grants_version",
        ),
        sa.UniqueConstraint(
            "tenant_id", "credential_id", "version_id", "worker_principal",
            name="uq_service_credential_grants_principal",
        ),
        sa.CheckConstraint("worker_principal ~ '^[a-z][a-z0-9._-]{2,63}$'", name="worker_principal_shape"),
        sa.CheckConstraint("recovery_epoch >= 0", name="recovery_epoch_non_negative"),
        sa.CheckConstraint("expires_at > created_at", name="expiry_after_creation"),
    )

    for table, columns in LIFECYCLE_UPDATE_COLUMNS.items():
        op.execute(f"GRANT SELECT, INSERT ON {table} TO {APP_ROLE}")
        op.execute(f"GRANT UPDATE ({', '.join(columns)}) ON {table} TO {APP_ROLE}")
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_tenant_isolation ON {table} FOR ALL TO {APP_ROLE} "
            f"USING (tenant_id = {TENANT_EXPR}) WITH CHECK (tenant_id = {TENANT_EXPR})"
        )


def downgrade() -> None:
    raise RuntimeError(
        "0051_service_credentials is irreversible: grants and revocations are the audit "
        "record of operator credential use and cannot be restored; apply a reviewed forward fix"
    )
