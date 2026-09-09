"""Evidence, outbox and inbox (S03-DB).

ADR-008: the Evidence INSERT, the success transition and the outbox row are one
transaction. That is why the outbox lives in PostgreSQL next to the Evidence
rather than in the message broker — a broker publish cannot join the
transaction that decides the Run succeeded.

ADR-007: redelivery is normal, not an incident. The broker is at-least-once, so
the consumer deduplicates on ``event_id`` through a UNIQUE constraint on
``inbox_events``. An outbox row may therefore be republished freely.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
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

EVIDENCE_RESULTS = ("succeeded", "failed", "denied")
OUTBOX_STATUSES = ("pending", "published", "failed")


class EvidenceEnvelope(Base):
    """The record that makes a completion defensible.

    Range partitioned by month, one year retention (PLAN-DB-001), no DEFAULT
    partition for the same reason as the other partitioned tables (CR-06).

    The application role has SELECT and INSERT only — no UPDATE, no DELETE.
    That is a real constraint on the application and explicitly **not** a claim
    of WORM against a superuser.

    Sensitive originals never live here. ``input_sha256`` and ``output_ref``
    are a hash and a reference; the content, if it must be kept, goes to
    encrypted storage (공통 계약 §5).
    """

    __tablename__ = "evidence_envelopes"
    __table_args__ = (
        CheckConstraint(
            "result IN ('succeeded','failed','denied')", name="result_allowed"
        ),
        CheckConstraint(
            "effect IS NULL OR effect IN ('allow','deny')", name="effect_allowed"
        ),
        CheckConstraint(
            "actor_type IN ('user','node','agent','system')", name="actor_type_allowed"
        ),
        Index("ix_evidence_envelopes_tenant_id_recorded_at", "tenant_id", "recorded_at"),
        Index("ix_evidence_envelopes_run_id_recorded_at", "run_id", "recorded_at"),
        Index("ix_evidence_envelopes_trace_id", "trace_id"),
        {"postgresql_partition_by": "RANGE (recorded_at)"},
    )

    evidence_id: Mapped[InvId] = mapped_column(primary_key=True)
    recorded_at: Mapped[Utc] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column()
    run_id: Mapped[InvId] = mapped_column()
    #: NULL for run-level evidence that is not attributable to one step.
    step_id: Mapped[InvId | None] = mapped_column(nullable=True)
    trace_id: Mapped[TraceId | None] = mapped_column(nullable=True)
    actor_type: Mapped[str] = mapped_column(String(16))
    actor_id: Mapped[str] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(128))
    #: The policy decision that permitted this, when one applied.
    policy_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    effect: Mapped[str | None] = mapped_column(String(8), nullable=True)
    approval_id: Mapped[InvId | None] = mapped_column(nullable=True)
    input_schema: Mapped[str] = mapped_column(String(128))
    input_sha256: Mapped[Sha256]
    output_schema: Mapped[str | None] = mapped_column(String(128), nullable=True)
    #: inv:// reference to the output artifact, not the output itself.
    output_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[str] = mapped_column(String(16))
    telemetry: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    #: Versions in force when this was produced, so the run is reproducible
    #: (공통 계약 §13).
    component_versions: Mapped[dict] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb")
    )


class OutboxEvent(Base):
    """An event to publish, written in the transaction that caused it.

    ``published_at`` advancing is not a promise of single delivery — republish
    is expected and safe because consumers deduplicate (ADR-007).
    """

    __tablename__ = "outbox_events"
    __table_args__ = (
        UniqueConstraint("event_id", name="uq_outbox_events_event_id"),
        CheckConstraint(
            "status IN ('pending','published','failed')", name="status_allowed"
        ),
        # inv.* namespace, fixed by ADR-004.
        CheckConstraint("event_type LIKE 'inv.%'", name="event_type_namespaced"),
        CheckConstraint("publish_attempts >= 0", name="publish_attempts_non_negative"),
        Index("ix_outbox_events_status_created_at", "status", "created_at"),
        Index("ix_outbox_events_tenant_id_created_at", "tenant_id", "created_at"),
    )

    outbox_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column()
    #: The identity consumers deduplicate on. Stable across republishes.
    event_id: Mapped[InvId] = mapped_column()
    event_type: Mapped[str] = mapped_column(String(128))
    aggregate_type: Mapped[str] = mapped_column(String(32))
    aggregate_id: Mapped[InvId] = mapped_column()
    payload: Mapped[dict] = mapped_column(JSONB)
    trace_id: Mapped[TraceId | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    publish_attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[Utc] = mapped_column(server_default=text("now()"))
    published_at: Mapped[Utc | None] = mapped_column(nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class InboxEvent(Base):
    """Consumer-side deduplication.

    The UNIQUE on ``(consumer, event_id)`` is the whole mechanism: a redelivered
    event fails to insert, and the consumer skips it. Doing this with a cache
    would turn an eviction into a duplicate side effect.
    """

    __tablename__ = "inbox_events"
    __table_args__ = (
        UniqueConstraint("consumer", "event_id", name="uq_inbox_events_consumer_event_id"),
        Index("ix_inbox_events_processed_at", "processed_at"),
    )

    inbox_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column()
    consumer: Mapped[str] = mapped_column(String(64))
    event_id: Mapped[InvId] = mapped_column()
    event_type: Mapped[str] = mapped_column(String(128))
    processed_at: Mapped[Utc] = mapped_column(server_default=text("now()"))
