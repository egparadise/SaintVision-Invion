"""Issue, refresh and revoke bounded first-contact discovery credentials."""

from __future__ import annotations

import datetime as dt
import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import DiscoveryCredentialEvent, DiscoveryMachineCredential
from ..errors import AUTH_INVALID_CREDENTIAL, InvError
from ..identity.discovery_credentials import DISCOVERY_SCOPE, TOKEN_TTL, token_sha256
from ..ids import new_id


def new_secret() -> str:
    """Return a 256-bit opaque token; callers must never persist or log it."""
    return "dsc1_" + secrets.token_urlsafe(32)


def _event(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    credential_id: str,
    installation_id: str,
    actor: str,
    event_type: str,
    outcome: str,
    reason_code: str | None,
    now: dt.datetime,
) -> None:
    session.add(
        DiscoveryCredentialEvent(
            event_id=uuid.uuid4(),
            tenant_id=tenant_id,
            credential_id=credential_id,
            installation_id=installation_id,
            actor=actor,
            event_type=event_type,
            outcome=outcome,
            reason_code=reason_code,
            occurred_at=now,
        )
    )


def issue(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    installation_id: str,
    actor: str,
    secret: str,
    now: dt.datetime,
) -> DiscoveryMachineCredential:
    """Rotate any still-live grant, then persist only the digest of the new one."""
    digest = token_sha256(secret)
    active = session.scalars(
        select(DiscoveryMachineCredential)
        .where(
            DiscoveryMachineCredential.tenant_id == tenant_id,
            DiscoveryMachineCredential.installation_id == installation_id,
            DiscoveryMachineCredential.revoked_at.is_(None),
        )
        .with_for_update()
    ).all()
    links = {
        (previous.announcement_id, previous.last_announcement_at)
        for previous in active
        if previous.announcement_id is not None
    }
    if len(links) > 1:
        raise InvError(AUTH_INVALID_CREDENTIAL, "discovery credential state is inconsistent", 409)
    announcement_id, last_announcement_at = next(iter(links), (None, None))
    for previous in active:
        previous.revoked_at = now
        _event(
            session,
            tenant_id=tenant_id,
            credential_id=previous.credential_id,
            installation_id=installation_id,
            actor=actor,
            event_type="revoked",
            outcome="allow",
            reason_code="rotated",
            now=now,
        )
    grant = DiscoveryMachineCredential(
        credential_id=new_id("discovery_credential"),
        tenant_id=tenant_id,
        installation_id=installation_id,
        scope=DISCOVERY_SCOPE,
        token_sha256=digest,
        issued_by=actor,
        issued_at=now,
        expires_at=now + TOKEN_TTL,
        announcement_id=announcement_id,
        last_announcement_at=last_announcement_at,
    )
    session.add(grant)
    session.flush()
    _event(
        session,
        tenant_id=tenant_id,
        credential_id=grant.credential_id,
        installation_id=installation_id,
        actor=actor,
        event_type="issued",
        outcome="allow",
        reason_code="operator_cli",
        now=now,
    )
    return grant


def revoke(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    credential_id: str,
    actor: str,
    now: dt.datetime,
) -> bool:
    grant = session.scalar(
        select(DiscoveryMachineCredential)
        .where(
            DiscoveryMachineCredential.tenant_id == tenant_id,
            DiscoveryMachineCredential.credential_id == credential_id,
        )
        .with_for_update()
    )
    if grant is None:
        raise InvError(AUTH_INVALID_CREDENTIAL, "discovery credential was not found", 404)
    if grant.revoked_at is not None:
        return False
    grant.revoked_at = now
    _event(
        session,
        tenant_id=tenant_id,
        credential_id=credential_id,
        installation_id=grant.installation_id,
        actor=actor,
        event_type="revoked",
        outcome="allow",
        reason_code="operator_cli",
        now=now,
    )
    return True
