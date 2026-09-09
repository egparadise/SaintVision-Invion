"""Request dependencies: authentication, tenant scope, idempotency.

Order matters. The credential is verified first, the tenant scope is opened from
the *verified* principal — never from a header the caller controls — and only
then does any query run.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from collections.abc import Iterator
from typing import Any

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from ..config import Settings
from ..db.models import IdempotencyRecord
from ..db.session import make_session_factory, tenant_scope
from ..errors import (
    AUTH_MISSING_CREDENTIAL,
    GRAPH_IDEMPOTENCY_CONFLICT,
    InvError,
)
from ..identity.principal import Principal
from ..ids import new_id


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_now(request: Request) -> dt.datetime:
    return request.app.state.clock()


def get_principal(
    request: Request, authorization: str | None = Header(default=None)
) -> Principal:
    """Verify the caller's credential.

    A missing header and an unrecognised credential are different codes so the
    audit trail can tell "not logged in" from "rejected", but both are denials
    and both are recorded.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise InvError(AUTH_MISSING_CREDENTIAL, "a bearer credential is required")
    credential = authorization.split(" ", 1)[1].strip()
    principal = request.app.state.verifier.verify(credential)
    # Recorded on the request so the error handler can attribute a later denial.
    request.state.actor_type = "user"
    request.state.actor_id = principal.user_id
    request.state.tenant_id = principal.tenant_id
    return principal


def get_session(
    request: Request, principal: Principal = Depends(get_principal)
) -> Iterator[Session]:
    """Yield a session already inside a transaction and a tenant scope.

    CR-12: the scope is set with SET LOCAL inside this transaction, so a
    transaction-mode pooler reassigning the backend afterwards cannot leak it
    to the next tenant. There is no code path that sets it at session level.
    """
    factory = make_session_factory(request.app.state.engine)
    with factory() as session:
        with session.begin():
            with tenant_scope(session, principal.tenant_id):
                yield session


def request_digest(payload: Any) -> str:
    """Stable hash of a request body, for the idempotency ledger."""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def replay_or_reserve(
    session: Session,
    *,
    principal: Principal,
    endpoint: str,
    idempotency_key: str | None,
    payload: Any,
    now: dt.datetime,
    ttl_seconds: int,
) -> dict[str, Any] | None:
    """Return a stored response for a repeated request, or None to proceed.

    The same key with a *different* body is a conflict, not a replay: silently
    returning the first response would hide that the caller sent something else
    (ADR-007).
    """
    if idempotency_key is None:
        return None
    digest = request_digest(payload)
    existing = (
        session.query(IdempotencyRecord)
        .filter(
            IdempotencyRecord.tenant_id == principal.tenant_id,
            IdempotencyRecord.endpoint == endpoint,
            IdempotencyRecord.idempotency_key == idempotency_key,
        )
        .one_or_none()
    )
    if existing is None:
        return None
    if existing.request_sha256 != digest:
        raise InvError(
            GRAPH_IDEMPOTENCY_CONFLICT,
            "idempotency key was already used with a different request body",
        )
    return existing.response_body


def store_idempotent_response(
    session: Session,
    *,
    principal: Principal,
    endpoint: str,
    idempotency_key: str | None,
    payload: Any,
    response_status: int,
    response_body: dict[str, Any],
    now: dt.datetime,
    ttl_seconds: int,
) -> None:
    if idempotency_key is None:
        return
    session.add(
        IdempotencyRecord(
            record_id=new_id("idempotency"),
            tenant_id=principal.tenant_id,
            endpoint=endpoint,
            idempotency_key=idempotency_key,
            request_sha256=request_digest(payload),
            response_status=response_status,
            response_body=response_body,
            created_at=now,
            expires_at=now + dt.timedelta(seconds=ttl_seconds),
        )
    )
    session.flush()
