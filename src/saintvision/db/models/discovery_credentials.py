"""Operator-issued, single-installation discovery grants."""

from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, Index, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base, Sha256, TenantId, Utc


class DiscoveryMachineCredential(Base):
    __tablename__ = "discovery_machine_credentials"
    __table_args__ = (
        CheckConstraint("scope = 'discovery:announce'", name="scope_is_announce_only"),
        CheckConstraint("expires_at > issued_at", name="expiry_after_issue"),
        CheckConstraint(
            "(announcement_id IS NULL) = (last_announcement_at IS NULL)",
            name="announcement_link_paired",
        ),
        Index("ix_discovery_machine_credentials_tenant_install", "tenant_id", "installation_id"),
        Index("ix_discovery_machine_credentials_expires_at", "expires_at"),
        Index(
            "uq_discovery_machine_credentials_one_active",
            "tenant_id",
            "installation_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )

    credential_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column(primary_key=False)
    installation_id: Mapped[str] = mapped_column(String(128))
    scope: Mapped[str] = mapped_column(String(40), default="discovery:announce")
    token_sha256: Mapped[Sha256] = mapped_column(unique=True)
    issued_by: Mapped[str] = mapped_column(String(128))
    issued_at: Mapped[Utc] = mapped_column(server_default=text("clock_timestamp()"))
    expires_at: Mapped[Utc] = mapped_column()
    revoked_at: Mapped[Utc | None] = mapped_column(nullable=True)
    announcement_id: Mapped[str | None] = mapped_column(String(30), nullable=True)
    last_announcement_at: Mapped[Utc | None] = mapped_column(nullable=True)


class DiscoveryCredentialEvent(Base):
    """Append-only audit metadata. A bearer secret is never an event field."""

    __tablename__ = "discovery_credential_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('issued','revoked','announced','denied','admitted')",
            name="event_type_allowed",
        ),
        CheckConstraint(
            "outcome IN ('allow','deny')", name="outcome_allowed"
        ),
        Index("ix_discovery_credential_events_tenant_time", "tenant_id", "occurred_at"),
    )

    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column()
    credential_id: Mapped[str | None] = mapped_column(String(30), nullable=True)
    installation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    actor: Mapped[str] = mapped_column(String(128))
    event_type: Mapped[str] = mapped_column(String(16))
    outcome: Mapped[str] = mapped_column(String(8))
    reason_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    occurred_at: Mapped[Utc] = mapped_column(server_default=text("clock_timestamp()"))
