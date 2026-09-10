"""Contributed folder and data location catalogue (S02-ST).

Only folders a user explicitly contributes become a StorageContribution
(PLAN-STORAGE-001). Nothing here formats, adopts a whole disk, or garbage
collects a user's own files.

The object store product is undecided — MinIO was found archived/source-only on
2026-09-09 and S01-ST owns the replacement decision. That decision blocks the
*transfer* path, not this catalogue: the URI grammar, integrity fields and
retention columns are contract, and are stated here without naming a product.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base, InvId, Sha256, TenantId, Utc

CONTRIBUTION_MODES = ("read_only", "read_write")
CONTRIBUTION_STATUSES = ("pending", "active", "revoked")
LOCATION_KINDS = ("dataset", "model", "artifact", "workspace")


class StorageContribution(Base):
    """A folder on a node that its owner has offered to the platform."""

    __tablename__ = "storage_contributions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "node_id"], ["nodes.tenant_id", "nodes.node_id"]
        ),
        UniqueConstraint(
            "tenant_id",
            "contribution_id",
            name="uq_storage_contributions_tenant_id_contribution_id",
        ),
        # normalized_path is what the safety check produced, and it is what
        # uniqueness is judged on. Two spellings of the same folder are one
        # contribution.
        UniqueConstraint(
            "node_id",
            "normalized_path",
            name="uq_storage_contributions_node_id_normalized_path",
        ),
        CheckConstraint(
            "mode IN ('read_only','read_write')", name="mode_allowed"
        ),
        CheckConstraint(
            "status IN ('pending','active','revoked')",
            name="status_allowed",
        ),
        CheckConstraint(
            "capacity_bytes IS NULL OR capacity_bytes >= 0",
            name="capacity_non_negative",
        ),
        CheckConstraint(
            "(status = 'revoked') = (revoked_at IS NOT NULL)",
            name="revocation_paired",
        ),
        Index("ix_storage_contributions_tenant_id_status", "tenant_id", "status"),
    )

    contribution_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column()
    node_id: Mapped[InvId] = mapped_column()
    #: Exactly what the node owner typed, kept for display and for the audit
    #: trail. Never used to open a file.
    declared_path: Mapped[str] = mapped_column(Text)
    #: The result of saintvision.storage.pathsafe.normalize_contribution_path.
    #: This is the only value the platform resolves against.
    normalized_path: Mapped[str] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(String(16), default="read_only")
    status: Mapped[str] = mapped_column(String(16), default="pending")
    capacity_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    available_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    registered_by_user_id: Mapped[InvId] = mapped_column()
    registered_at: Mapped[Utc] = mapped_column(server_default=text("now()"))
    revoked_at: Mapped[Utc | None] = mapped_column(nullable=True)
    version: Mapped[int] = mapped_column(default=1)


class DataLocation(Base):
    """A catalogued item inside a contribution, addressed by an ``inv://`` URI.

    ``ready`` means checksum verified, access policy checked and the file
    complete — not merely present (PLAN-STORAGE-001). It is therefore derived
    from ``checksum_sha256`` and ``verified_at`` being set, which the check
    constraint holds to.
    """

    __tablename__ = "data_locations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "contribution_id"],
            [
                "storage_contributions.tenant_id",
                "storage_contributions.contribution_id",
            ],
        ),
        UniqueConstraint(
            "tenant_id", "location_id", name="uq_data_locations_tenant_id_location_id"
        ),
        UniqueConstraint(
            "tenant_id", "uri", name="uq_data_locations_tenant_id_uri"
        ),
        CheckConstraint(
            "kind IN ('dataset','model','artifact','workspace')",
            name="kind_allowed",
        ),
        CheckConstraint("byte_size >= 0", name="byte_size_non_negative"),
        # An unverified file is never ready. This is the ADR-011 rule expressed
        # as a constraint so no service path can shortcut it.
        CheckConstraint(
            "NOT ready OR (checksum_sha256 IS NOT NULL AND verified_at IS NOT NULL)",
            name="ready_requires_verification",
        ),
        Index("ix_data_locations_tenant_id_kind", "tenant_id", "kind"),
        Index("ix_data_locations_contribution_id", "contribution_id"),
    )

    location_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column()
    contribution_id: Mapped[InvId] = mapped_column()
    #: inv://datasets/<name>@<version>/<path> and friends (ADR-010).
    uri: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(16))
    #: Path relative to the contribution root. Never absolute, never escaping.
    relative_path: Mapped[str] = mapped_column(Text)
    byte_size: Mapped[int] = mapped_column(BigInteger, default=0)
    #: Computed by a trusted worker over the actual bytes. An ETag or a
    #: client-supplied metadata field is not accepted in its place (ADR-011).
    checksum_sha256: Mapped[Sha256 | None] = mapped_column(nullable=True)
    verified_at: Mapped[Utc | None] = mapped_column(nullable=True)
    ready: Mapped[bool] = mapped_column(default=False)
    #: Retention pin. Evidence-referenced artifacts are held past the ordinary
    #: 90 day artifact lifetime (ADR-012); GC must honour this.
    retention_pinned_until: Mapped[Utc | None] = mapped_column(nullable=True)
    catalogued_at: Mapped[Utc] = mapped_column(server_default=text("now()"))
    version: Mapped[int] = mapped_column(default=1)
