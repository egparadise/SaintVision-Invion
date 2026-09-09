"""Evidence and outbox writes (S03-DB).

Neither function opens a transaction. That is the point: they are called from
inside the caller's transaction so the Evidence, the state change and the event
commit together or not at all (ADR-008). A helper that committed on its own
would quietly break the invariant it exists to serve.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import uuid
from typing import Any

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from ..db.models import EvidenceEnvelope, InboxEvent, OutboxEvent
from ..errors import VAL_SCHEMA, InvError
from ..ids import new_id
from .audit import redact

#: Event names live in the inv.* namespace (ADR-004).
EVENT_NAMESPACE = "inv."


def canonical_sha256(payload: Any) -> str:
    """Hash a structure the same way every time.

    Sorted keys and no incidental whitespace, so that two callers building the
    same input independently produce the same digest — which is what makes the
    hash comparable across services at all.
    """
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def record_evidence(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    run_id: str,
    action: str,
    actor_type: str,
    actor_id: str,
    input_schema: str,
    input_payload: Any,
    result: str,
    now: dt.datetime,
    step_id: str | None = None,
    trace_id: str | None = None,
    policy_id: str | None = None,
    effect: str | None = None,
    approval_id: str | None = None,
    output_schema: str | None = None,
    output_ref: str | None = None,
    telemetry: dict[str, Any] | None = None,
    component_versions: dict[str, str] | None = None,
) -> str:
    """Write one EvidenceEnvelope and return its id.

    The input is hashed, never stored: 공통 계약 §5 keeps sensitive originals
    out of Evidence, and a reference plus a hash is enough to prove what was
    submitted without holding it.
    """
    if result not in ("succeeded", "failed", "denied"):
        raise InvError(VAL_SCHEMA, f"unknown evidence result: {result!r}")
    if output_ref is not None and not output_ref.startswith("inv://"):
        # A raw path or a presigned URL here would leak on every read of the
        # evidence table (ADR-014).
        raise InvError(VAL_SCHEMA, "output_ref must be an inv:// reference")

    evidence_id = new_id("evidence")
    session.execute(
        insert(EvidenceEnvelope).values(
            evidence_id=evidence_id,
            recorded_at=now,
            tenant_id=tenant_id,
            run_id=run_id,
            step_id=step_id,
            trace_id=trace_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            policy_id=policy_id,
            effect=effect,
            approval_id=approval_id,
            input_schema=input_schema,
            input_sha256=canonical_sha256(input_payload),
            output_schema=output_schema,
            output_ref=output_ref,
            result=result,
            telemetry=redact(telemetry or {}),
            component_versions=component_versions or {},
        )
    )
    return evidence_id


def enqueue_event(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    payload: dict[str, Any],
    now: dt.datetime,
    trace_id: str | None = None,
) -> str:
    """Append to the outbox inside the caller's transaction.

    Returns the ``event_id`` consumers deduplicate on. It is stable across
    republishes, so redelivery is safe rather than merely tolerated.
    """
    if not event_type.startswith(EVENT_NAMESPACE):
        raise InvError(VAL_SCHEMA, f"event type must start with {EVENT_NAMESPACE!r}")

    event_id = new_id("outbox")
    session.execute(
        insert(OutboxEvent).values(
            outbox_id=new_id("outbox"),
            tenant_id=tenant_id,
            event_id=event_id,
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            payload=redact(payload),
            trace_id=trace_id,
            status="pending",
            publish_attempts=0,
            created_at=now,
        )
    )
    return event_id


def claim_pending_events(session: Session, *, limit: int = 100) -> list[OutboxEvent]:
    """Fetch pending events for a publisher, skipping rows another one holds.

    ``FOR UPDATE SKIP LOCKED`` lets several publishers run without either
    blocking on each other or handing the same row to both.
    """
    return list(
        session.scalars(
            select(OutboxEvent)
            .where(OutboxEvent.status == "pending")
            .order_by(OutboxEvent.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        ).all()
    )


def mark_published(session: Session, outbox_id: str, *, now: dt.datetime) -> None:
    event = session.get(OutboxEvent, outbox_id)
    if event is None:
        return
    event.status = "published"
    event.published_at = now
    event.publish_attempts += 1


def mark_publish_failed(
    session: Session, outbox_id: str, *, error: str, max_attempts: int = 10
) -> None:
    """Record a failed publish attempt.

    The row stays ``pending`` until the attempt budget is spent, because a
    transient broker outage should be retried rather than parked. Only then
    does it become ``failed`` and stop being claimed.
    """
    event = session.get(OutboxEvent, outbox_id)
    if event is None:
        return
    event.publish_attempts += 1
    # Truncated and redacted: a broker error can echo the payload back.
    event.last_error = error[:500]
    if event.publish_attempts >= max_attempts:
        event.status = "failed"


def already_processed(session: Session, *, consumer: str, event_id: str) -> bool:
    return (
        session.scalar(
            select(InboxEvent.inbox_id).where(
                InboxEvent.consumer == consumer, InboxEvent.event_id == event_id
            )
        )
        is not None
    )


def mark_processed(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    consumer: str,
    event_id: str,
    event_type: str,
    now: dt.datetime,
) -> None:
    """Claim an event for a consumer.

    Relies on the UNIQUE constraint rather than a prior read: checking first and
    inserting second lets two deliveries both pass the check. The caller treats
    an IntegrityError here as "already handled".
    """
    session.execute(
        insert(InboxEvent).values(
            inbox_id=new_id("inbox"),
            tenant_id=tenant_id,
            consumer=consumer,
            event_id=event_id,
            event_type=event_type,
            processed_at=now,
        )
    )
