"""Artifacts and upload sessions (S03-ST).

"기본 전송" for this sprint means the ledger and the integrity rules, not a
wire protocol: the S3-compatible product is still an S01-ST decision. What is
fixed here is what an upload must prove before its bytes count as an artifact.

Two rules carried from ADR-011 and ADR-012:

* Only a checksum computed by a trusted worker over the actual bytes promotes
  an upload to ``active``. An ETag or a client-declared hash does not.
* An artifact referenced by Evidence is pinned past the ordinary 90 day
  lifetime, and GC must consult ``retention_pinned_until`` and the live upload
  ledger before deleting anything.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base, InvId, Sha256, TenantId, Utc

ARTIFACT_STATUSES = ("staging", "active", "quarantined", "deleted")
UPLOAD_STATUSES = ("initiated", "completing", "verified", "failed", "aborted")

#: PLAN-STORAGE-001 transfer defaults.
DEFAULT_PART_BYTES = 16 * 1024 * 1024
MAX_ARTIFACT_BYTES = 50 * 1024 * 1024 * 1024


class Artifact(Base):
    """A produced file belonging to a run.

    Addressed as ``inv://artifacts/<runId>/<artifactId>`` (ADR-010). The
    resolved object version and digest are pinned into the RunRecord at
    execution time, so a later overwrite cannot silently change what a finished
    run referred to.
    """

    __tablename__ = "artifacts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "run_id"], ["runs.tenant_id", "runs.run_id"]
        ),
        UniqueConstraint("tenant_id", "artifact_id", name="uq_artifacts_tenant_id_artifact_id"),
        UniqueConstraint("run_id", "name", name="uq_artifacts_run_id_name"),
        CheckConstraint(
            "status IN ('staging','active','quarantined','deleted')",
            name="status_allowed",
        ),
        CheckConstraint("byte_size >= 0", name="byte_size_non_negative"),
        CheckConstraint(
            f"byte_size <= {MAX_ARTIFACT_BYTES}", name="byte_size_within_limit"
        ),
        # Same rule as data_locations: active means verified, not merely present.
        CheckConstraint(
            "status <> 'active' OR (checksum_sha256 IS NOT NULL AND verified_at IS NOT NULL)",
            name="active_requires_verification",
        ),
        Index("ix_artifacts_tenant_id_run_id", "tenant_id", "run_id"),
        Index("ix_artifacts_retention_pinned_until", "retention_pinned_until"),
    )

    artifact_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column()
    run_id: Mapped[InvId] = mapped_column()
    name: Mapped[str] = mapped_column(String(128))
    media_type: Mapped[str] = mapped_column(String(128), default="application/octet-stream")
    status: Mapped[str] = mapped_column(String(16), default="staging")
    byte_size: Mapped[int] = mapped_column(BigInteger, default=0)
    #: Computed by a trusted worker over the stored bytes (ADR-011).
    checksum_sha256: Mapped[Sha256 | None] = mapped_column(nullable=True)
    verified_at: Mapped[Utc | None] = mapped_column(nullable=True)
    #: The object store's own version identifier, once a product exists. NULL
    #: until then; not a substitute for the checksum.
    object_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    #: Held past the 90 day artifact lifetime when Evidence depends on it
    #: (ADR-012). GC must honour this and never shorten it.
    retention_pinned_until: Mapped[Utc | None] = mapped_column(nullable=True)
    created_at: Mapped[Utc] = mapped_column(server_default=text("now()"))
    deleted_at: Mapped[Utc | None] = mapped_column(nullable=True)
    version: Mapped[int] = mapped_column(default=1)


class UploadSession(Base):
    """The ledger row for a multipart upload in flight.

    It exists so that GC can tell "no database row, therefore delete the
    object" from "an upload is still running" — deleting on absence alone
    destroys in-progress work (PLAN-STORAGE-001).

    ``reserved_bytes`` is claimed against quota at initiation and settled on
    completion or abort, so two concurrent uploads cannot both fit into space
    only one of them has.
    """

    __tablename__ = "upload_sessions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "artifact_id"],
            ["artifacts.tenant_id", "artifacts.artifact_id"],
        ),
        UniqueConstraint("tenant_id", "upload_id", name="uq_upload_sessions_tenant_id_upload_id"),
        UniqueConstraint("artifact_id", name="uq_upload_sessions_artifact_id"),
        CheckConstraint(
            "status IN ('initiated','completing','verified','failed','aborted')",
            name="status_allowed",
        ),
        CheckConstraint("part_bytes > 0", name="part_bytes_positive"),
        CheckConstraint("reserved_bytes >= 0", name="reserved_bytes_non_negative"),
        CheckConstraint("parts_declared >= 0", name="parts_declared_non_negative"),
        CheckConstraint("expires_at > created_at", name="expiry_after_creation"),
        Index("ix_upload_sessions_status_expires_at", "status", "expires_at"),
    )

    upload_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column()
    artifact_id: Mapped[InvId] = mapped_column()
    status: Mapped[str] = mapped_column(String(16), default="initiated")
    part_bytes: Mapped[int] = mapped_column(BigInteger, default=DEFAULT_PART_BYTES)
    parts_declared: Mapped[int] = mapped_column(Integer, default=0)
    reserved_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    #: Per-part evidence, reused when an upload URL is refreshed so a renewal
    #: does not restart the transfer (PLAN-STORAGE-001).
    part_evidence: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    created_at: Mapped[Utc] = mapped_column(server_default=text("now()"))
    #: Upload URLs live an hour; the session outlives a single URL.
    expires_at: Mapped[Utc]
    settled_at: Mapped[Utc | None] = mapped_column(nullable=True)
    #: Never a presigned URL and never a token (ADR-014).
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
