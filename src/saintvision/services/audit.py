"""Audit recording.

AC-02 requires authentication failures to be recorded, so a denial must be
written even when there is no tenant to attribute it to and no transaction the
caller would otherwise open.

Two rules this module keeps:

* A denial is recorded in its **own** transaction. If the denial were written in
  the request transaction, rolling that transaction back — which a denial
  usually does — would erase the very record we need.
* ``detail`` is redacted before it arrives. Credentials, presigned URLs and raw
  prompts never reach here (ADR-014); the helpers below drop any key that looks
  like one rather than trusting callers.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any, Final

from sqlalchemy import Engine, insert
from sqlalchemy.orm import Session, sessionmaker

from ..db.models import AuditEvent
from ..ids import new_id

#: Substrings that mark a value as unloggable. Matched case-insensitively
#: against the key, because a value-based check cannot recognise a secret.
_REDACT_KEY_MARKERS: Final[tuple[str, ...]] = (
    "secret",
    "token",
    "password",
    "credential",
    "authorization",
    "signature",
    "presigned",
    "url",
    "prompt",
    "key",
)

REDACTED: Final[str] = "[redacted]"


def redact(detail: dict[str, Any]) -> dict[str, Any]:
    """Return a copy with sensitive-looking entries replaced.

    This is the application-side first pass required by ADR-014; the collector
    performs a second one. Neither is a substitute for not putting the value in
    the dictionary in the first place.
    """
    out: dict[str, Any] = {}
    for key, value in detail.items():
        lowered = key.lower()
        if any(marker in lowered for marker in _REDACT_KEY_MARKERS):
            out[key] = REDACTED
        elif isinstance(value, dict):
            out[key] = redact(value)
        else:
            out[key] = value
    return out


def record_event(
    session: Session,
    *,
    now: dt.datetime,
    actor_type: str,
    action: str,
    outcome: str,
    tenant_id: uuid.UUID | None = None,
    actor_id: str | None = None,
    reason_code: str | None = None,
    trace_id: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    detail: dict[str, Any] | None = None,
    source_ip: str | None = None,
    user_agent: str | None = None,
) -> str:
    """Write one audit row into the caller's transaction. Returns its ID."""
    event_id = new_id("audit_event")
    session.execute(
        insert(AuditEvent).values(
            event_id=event_id,
            occurred_at=now,
            tenant_id=tenant_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            outcome=outcome,
            reason_code=reason_code,
            trace_id=trace_id,
            target_type=target_type,
            target_id=target_id,
            detail=redact(detail or {}),
            source_ip=source_ip,
            user_agent=user_agent,
        )
    )
    return event_id


def record_denial_out_of_band(engine: Engine, **kwargs: Any) -> str:
    """Write a denial in its own transaction, independent of the request's.

    Used for authentication and authorisation failures, which roll the request
    transaction back.
    """
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        with session.begin():
            event_id = record_event(session, **kwargs)
    return event_id
