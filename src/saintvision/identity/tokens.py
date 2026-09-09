"""Node bootstrap tokens.

A bootstrap token is what a node presents once, to exchange for an enrolled
identity. AC-02 requires that presenting it a second time fails.

The token is a 256 bit random string. Only its SHA-256 is stored, so a database
read does not yield a usable credential. Comparison is by hash lookup, and the
consumption is an atomic conditional UPDATE — checking then updating in two
statements would let two concurrent enrollments both pass the check.

No dependency is taken on a JWT library: the runtime dependency set is locked in
S01 (PLAN-BACKEND-001), and this needs nothing beyond hashlib and secrets.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import secrets
import uuid
from dataclasses import dataclass

from sqlalchemy import update
from sqlalchemy.orm import Session

from ..errors import (
    AUTH_BOOTSTRAP_TOKEN_CONSUMED,
    AUTH_BOOTSTRAP_TOKEN_EXPIRED,
    AUTH_BOOTSTRAP_TOKEN_INVALID,
    InvError,
)
from ..ids import new_id
from ..db.models import NodeBootstrapToken

#: 43 characters of URL-safe base64 over 32 random bytes.
TOKEN_BYTES = 32


@dataclass(frozen=True, slots=True)
class IssuedToken:
    """The only object that ever holds the plaintext.

    ``secret`` is returned to the caller once and never persisted or logged
    (ADR-014). Everything downstream works from ``token_id``.
    """

    token_id: str
    secret: str
    expires_at: dt.datetime


def token_digest(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def issue_bootstrap_token(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    issued_by_user_id: str,
    now: dt.datetime,
    ttl_seconds: int = 900,
) -> IssuedToken:
    secret = secrets.token_urlsafe(TOKEN_BYTES)
    expires_at = now + dt.timedelta(seconds=ttl_seconds)
    record = NodeBootstrapToken(
        token_id=new_id("bootstrap_token"),
        tenant_id=tenant_id,
        token_sha256=token_digest(secret),
        issued_by_user_id=issued_by_user_id,
        issued_at=now,
        expires_at=expires_at,
    )
    session.add(record)
    session.flush()
    return IssuedToken(token_id=record.token_id, secret=secret, expires_at=expires_at)


def consume_bootstrap_token(
    session: Session, *, secret: str, node_id: str, now: dt.datetime
) -> NodeBootstrapToken:
    """Claim a token for ``node_id``, or raise.

    The claim is a single UPDATE guarded by ``consumed_at IS NULL``. Two racing
    enrollments both issue it; PostgreSQL serialises them on the row, and the
    loser updates zero rows and is told the token is already consumed.

    A hash miss and an expired token are reported as distinct codes because
    they mean different things operationally, and both are audited.
    """
    digest = token_digest(secret)

    claimed = session.execute(
        update(NodeBootstrapToken)
        .where(
            NodeBootstrapToken.token_sha256 == digest,
            NodeBootstrapToken.consumed_at.is_(None),
            NodeBootstrapToken.expires_at > now,
        )
        .values(consumed_at=now, consumed_by_node_id=node_id)
        .returning(NodeBootstrapToken)
    ).scalar_one_or_none()

    if claimed is not None:
        return claimed

    # Nothing was claimed. Find out why, without leaking whether a hash exists
    # to an unauthenticated caller — the distinction is recorded in the audit
    # trail, and the API maps every branch to the same 403 shape.
    existing = (
        session.query(NodeBootstrapToken)
        .filter(NodeBootstrapToken.token_sha256 == digest)
        .one_or_none()
    )
    if existing is None:
        raise InvError(AUTH_BOOTSTRAP_TOKEN_INVALID, "bootstrap token is not recognised")
    if existing.consumed_at is not None:
        raise InvError(
            AUTH_BOOTSTRAP_TOKEN_CONSUMED,
            "bootstrap token has already been used",
            cause_ref=existing.token_id,
        )
    raise InvError(
        AUTH_BOOTSTRAP_TOKEN_EXPIRED,
        "bootstrap token has expired",
        cause_ref=existing.token_id,
    )
