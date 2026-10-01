"""Append-only release-to-Evidence bindings (S12-BE, migration 0058)."""

from __future__ import annotations

from sqlalchemy import ForeignKeyConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base, InvId, Sha256, TenantId, Utc


class ReleaseEvidenceBinding(Base):
    """A server-derived Evidence identity attached to one release.

    The database trigger re-derives ``project_id`` and ``envelope_sha256`` through
    Evidence -> Run -> Workload. The application supplies those values only so a
    mismatch is rejected rather than silently rewritten.
    """

    __tablename__ = "release_evidence_bindings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "release_id"],
            ["release_manifests.tenant_id", "release_manifests.release_id"],
        ),
        ForeignKeyConstraint(
            ["tenant_id", "project_id"], ["projects.tenant_id", "projects.project_id"]
        ),
        ForeignKeyConstraint(
            ["evidence_id", "evidence_recorded_at"],
            ["evidence_envelopes.evidence_id", "evidence_envelopes.recorded_at"],
        ),
        Index(
            "ix_release_evidence_bindings_page",
            "tenant_id",
            "release_id",
            "evidence_recorded_at",
            "evidence_id",
        ),
    )

    tenant_id: Mapped[TenantId] = mapped_column(primary_key=True)
    release_id: Mapped[InvId] = mapped_column(primary_key=True)
    evidence_id: Mapped[InvId] = mapped_column(primary_key=True)
    evidence_recorded_at: Mapped[Utc] = mapped_column(primary_key=True)
    project_id: Mapped[InvId] = mapped_column()
    envelope_sha256: Mapped[Sha256] = mapped_column()
    bound_at: Mapped[Utc] = mapped_column()
