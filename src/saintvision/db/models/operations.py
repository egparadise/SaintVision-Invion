"""Idempotency ledger and audit events.

Both exist in S02 because AC-02 requires authentication failures to be
recorded, and because node enrollment is a mutation that must not double-apply
on a retried request (ADR-007).
"""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base, InvId, Sha256, TenantId, TraceId, Utc

AUDIT_OUTCOMES = ("allow", "deny", "error")
ACTOR_TYPES = ("user", "node", "agent", "system", "anonymous")


class IdempotencyRecord(Base):
    """Durable record of a completed mutation, keyed by the caller's key.

    PostgreSQL owns this, not Redis: a cache eviction must not turn a replay
    into a second side effect (ADR-007). ``request_sha256`` is stored so that
    the same key used with a *different* body is a conflict rather than a
    silent replay of the first response.
    """

    __tablename__ = "idempotency_records"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "endpoint",
            "idempotency_key",
            name="uq_idempotency_records_scope_key",
        ),
        CheckConstraint(
            "response_status BETWEEN 100 AND 599",
            name="status_is_http",
        ),
        Index("ix_idempotency_records_expires_at", "expires_at"),
    )

    record_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column()
    endpoint: Mapped[str] = mapped_column(String(128))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    request_sha256: Mapped[Sha256]
    response_status: Mapped[int] = mapped_column(Integer)
    response_body: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[Utc] = mapped_column(server_default=text("now()"))
    expires_at: Mapped[Utc]


class AuditEvent(Base):
    """Append-only record of an authorisation decision or a mutation.

    Range partitioned by month with a one year retention (PLAN-DB-001), and no
    DEFAULT partition for the same reason as resource_snapshots (CR-06).

    ``tenant_id`` is nullable: a rejected credential may not resolve to a
    tenant, and losing that record is exactly the case AC-02 asks us to keep.
    Those rows are outside RLS by construction, so the audit read role is
    separate from the application role.
    """

    __tablename__ = "audit_events"
    __table_args__ = (
        CheckConstraint(
            "outcome IN ('allow','deny','error')", name="outcome_allowed"
        ),
        CheckConstraint(
            "actor_type IN ('user','node','agent','system','anonymous')",
            name="actor_type_allowed",
        ),
        Index("ix_audit_events_tenant_id_occurred_at", "tenant_id", "occurred_at"),
        Index("ix_audit_events_action_occurred_at", "action", "occurred_at"),
        Index("ix_audit_events_trace_id", "trace_id"),
        {"postgresql_partition_by": "RANGE (occurred_at)"},
    )

    event_id: Mapped[InvId] = mapped_column(primary_key=True)
    occurred_at: Mapped[Utc] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId | None] = mapped_column(nullable=True)
    actor_type: Mapped[str] = mapped_column(String(16))
    #: NULL when the caller could not be identified at all.
    actor_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    action: Mapped[str] = mapped_column(String(64))
    outcome: Mapped[str] = mapped_column(String(8))
    #: The error code from saintvision.errors for a denial, NULL for an allow.
    reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    trace_id: Mapped[TraceId | None] = mapped_column(nullable=True)
    target_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: Redacted before it gets here. No credentials, no presigned URLs, no raw
    #: prompts (ADR-014).
    detail: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    source_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
