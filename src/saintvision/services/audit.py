"""Audit recording.

AC-02 requires authentication failures to be recorded, so a denial must be
written even when there is no tenant to attribute it to and no transaction the
caller would otherwise open.

Three rules this module keeps:

* A denial is recorded in its **own** transaction. If the denial were written in
  the request transaction, rolling that transaction back — which a denial
  usually does — would erase the very record we need.
* ``detail`` is redacted before it arrives. Credentials, presigned URLs and raw
  prompts never reach here (ADR-014); the helpers below drop any key that looks
  like one rather than trusting callers.
* Since 0047_audit_events_isolation the table has RLS, so *how* a row is written
  depends on whether it has a tenant. A row with a tenant goes through the
  tenant policy, which means the scope has to be set even though no request
  transaction is open. A row without one cannot satisfy any tenant policy and
  goes through ``public.record_auth_denial``, the one narrow primitive allowed
  to append a tenant-less denial. The application role can no longer read this
  table at all; 0067 removes the unused cross-tenant reader as well.
"""

from __future__ import annotations

import datetime as dt
import json
import uuid
from typing import Any, Final

from sqlalchemy import Engine, insert, text
from sqlalchemy.orm import Session, sessionmaker

from ..db.models import AuditEvent
from ..db.session import tenant_scope
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


#: Named arguments, not positional: every parameter of the primitive is text, so
#: a transposed pair would be recorded as a plausible-looking wrong denial rather
#: than rejected.
_RECORD_DENIAL = text(
    "SELECT public.record_auth_denial("
    "p_event_id => :event_id, p_actor_type => :actor_type, p_action => :action, "
    "p_reason_code => :reason_code, p_actor_id => :actor_id, p_trace_id => :trace_id, "
    "p_target_type => :target_type, p_target_id => :target_id, "
    "p_detail => CAST(:detail AS jsonb), p_source_ip => :source_ip, "
    "p_user_agent => :user_agent)"
)


def record_denial_out_of_band(
    engine: Engine,
    *,
    now: dt.datetime,
    actor_type: str,
    action: str,
    outcome: str = "deny",
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
    """Write a denial in its own transaction, independent of the request's.

    Used for authentication and authorisation failures, which roll the request
    transaction back.

    The two branches are the two kinds of denial. An authorisation failure that
    got as far as a principal has a tenant, so its row is an ordinary
    tenant-scoped audit row and the scope is set explicitly here — nothing else
    in this transaction would set it. An authentication failure that resolved no
    tenant has no scope to set, and its row is written by
    ``public.record_auth_denial``, which is allowed to append exactly that and
    nothing else. ``now`` applies to the first branch; the second is stamped by
    the server clock, because a row with no tenant to attribute it to should not
    also take its timestamp from the audited caller.
    """
    if outcome != "deny":
        raise ValueError(f"record_denial_out_of_band records denials, not {outcome!r}")
    if not reason_code:
        raise ValueError("a denial must carry the error code that caused it")

    event_id = new_id("audit_event")
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        with session.begin():
            if tenant_id is None:
                session.execute(
                    _RECORD_DENIAL,
                    {
                        "event_id": event_id,
                        "actor_type": actor_type,
                        "action": action,
                        "reason_code": reason_code,
                        "actor_id": actor_id,
                        "trace_id": trace_id,
                        "target_type": target_type,
                        "target_id": target_id,
                        "detail": json.dumps(redact(detail or {})),
                        "source_ip": source_ip,
                        "user_agent": user_agent,
                    },
                )
            else:
                with tenant_scope(session, tenant_id):
                    event_id = record_event(
                        session,
                        now=now,
                        actor_type=actor_type,
                        action=action,
                        outcome=outcome,
                        tenant_id=tenant_id,
                        actor_id=actor_id,
                        reason_code=reason_code,
                        trace_id=trace_id,
                        target_type=target_type,
                        target_id=target_id,
                        detail=detail,
                        source_ip=source_ip,
                        user_agent=user_agent,
                    )
    return event_id
