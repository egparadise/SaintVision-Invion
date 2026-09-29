"""Request dependencies: authentication, tenant scope, idempotency.

Order matters. The credential is verified first, the tenant scope is opened from
the *verified* principal — never from a header the caller controls — and only
then does any query run.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from fastapi import Depends, Header, Request
from sqlalchemy import text
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


def get_principal(request: Request, authorization: str | None = Header(default=None)) -> Principal:
    """Verify the caller's credential.

    A missing header and an unrecognised credential are different codes so the
    audit trail can tell "not logged in" from "rejected", but both are denials
    and both are recorded.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise InvError(AUTH_MISSING_CREDENTIAL, "a bearer credential is required", status=401)
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


def get_write_session(
    request: Request, principal: Principal = Depends(get_principal)
) -> Iterator[Session]:
    """Yield a tenant-scoped legacy write transaction with bounded lock waits.

    Read routes retain :func:`get_session`; mutation routes use this dependency
    unless an idempotency span already applies the same bound. PostgreSQL lock
    timeout/deadlock errors become canonical retryable ``SYS-0001/503``.
    """
    from .lock_wait import bounded_lock_wait

    factory = make_session_factory(request.app.state.engine)
    with factory() as session:
        with session.begin():
            with (
                tenant_scope(session, principal.tenant_id),
                bounded_lock_wait(
                    session,
                    timeout_ms=request.app.state.settings.business_lock_timeout_ms,
                ),
            ):
                yield session


#: Namespace for the idempotency advisory lock. Part of the hashed material so
#: this project's locks cannot collide with another user of the same database's.
IDEMPOTENCY_LOCK_NAMESPACE = "saintvision.idempotency.v1"


def serialise_idempotent_write(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    endpoint: str,
    idempotency_key: str,
    project_id: str | None = None,
) -> int:
    """Serialise concurrent first requests that carry the same idempotency key.

    ``replay_or_reserve`` below reserves nothing: it reads the ledger and
    returns. Two concurrent first requests with the same key therefore both
    read "absent", both call the service, and one of them loses on the ledger's
    unique index -- after its write has already happened. The ledger cannot fix
    this by itself, because the row it would need to take a lock on does not
    exist yet.

    A transaction-scoped advisory lock on the *key* rather than on a row closes
    it: the second transaction waits for the first to commit, and then finds the
    stored response and replays it. The key is derived, not stored, so there is
    nothing to clean up and no migration; the lock is released by commit or
    rollback either way.

    Every write route takes this lock **before** any resource row, so the lock
    order across the business lane is one: this serialisation point, then the
    row. Returns the lock key so a test can assert which key was taken.

    The wait here is bounded by the caller's ``SET LOCAL lock_timeout``
    (``api/lock_wait.bounded_lock_wait``, card 84): ``pg_advisory_xact_lock``
    is a heavyweight lock and honours it, so a key held by a long transaction
    is refused with ``SYS-0001/503`` after the budget instead of waited on
    forever. This function sets no timeout of its own, because the budget
    belongs to the transaction, not to one lock in it.
    """
    # A separator that cannot occur in any of the parts, so ("a", "bc") and
    # ("ab", "c") hash to different material rather than the same lock.
    material = "\x1f".join(
        [
            IDEMPOTENCY_LOCK_NAMESPACE,
            str(tenant_id),
            project_id or "",
            endpoint,
            idempotency_key,
        ]
    )
    digest = hashlib.sha256(material.encode("utf-8")).digest()
    # ``pg_advisory_xact_lock`` takes a signed bigint, so the first eight bytes
    # are read as one rather than truncated from a larger integer.
    key = int.from_bytes(digest[:8], "big", signed=True)
    session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
    return key


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
    project_id: str | None = None,
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
            (
                IdempotencyRecord.project_id.is_(None)
                if project_id is None
                else IdempotencyRecord.project_id == project_id
            ),
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
    project_id: str | None = None,
) -> None:
    if idempotency_key is None:
        return
    session.add(
        IdempotencyRecord(
            record_id=new_id("idempotency"),
            tenant_id=principal.tenant_id,
            project_id=project_id,
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


@contextmanager
def optional_idempotent_write(
    session: Session,
    *,
    principal: Principal,
    endpoint: str,
    idempotency_key: str | None,
    payload: Any,
    now: dt.datetime,
    ttl_seconds: int,
    lock_timeout_ms: int,
    project_id: str | None = None,
) -> Iterator[tuple[dict[str, Any] | None, Callable[[dict[str, Any], int], None]]]:
    """Bound and optionally replay a legacy write without changing its schema.

    The web client already sends ``Idempotency-Key`` on mutations. Legacy
    handlers historically ignored it and therefore repeated audit rows and
    version/timestamp writes. When a key is present, the shared advisory lock
    closes the concurrent-first gap before reading the durable ledger. When it
    is absent, the route retains its existing behavior while lock waits are
    still bounded.
    """
    from .lock_wait import bounded_lock_wait

    with bounded_lock_wait(session, timeout_ms=lock_timeout_ms):
        if idempotency_key is not None:
            serialise_idempotent_write(
                session,
                tenant_id=principal.tenant_id,
                endpoint=endpoint,
                idempotency_key=idempotency_key,
                project_id=project_id,
            )
        replay = replay_or_reserve(
            session,
            principal=principal,
            endpoint=endpoint,
            idempotency_key=idempotency_key,
            payload=payload,
            now=now,
            ttl_seconds=ttl_seconds,
            project_id=project_id,
        )

        def finish(response_body: dict[str, Any], response_status: int = 200) -> None:
            store_idempotent_response(
                session,
                principal=principal,
                endpoint=endpoint,
                idempotency_key=idempotency_key,
                payload=payload,
                response_status=response_status,
                response_body=response_body,
                now=now,
                ttl_seconds=ttl_seconds,
                project_id=project_id,
            )

        yield replay, finish
