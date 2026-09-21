"""Narrow opaque credentials used only for first-contact Node discovery."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import re
from typing import Any, Mapping
import uuid

from ..errors import AUTH_INVALID_CREDENTIAL, InvError

TOKEN_RE = re.compile(r"^dsc1_[A-Za-z0-9_-]{43}$")
TOKEN_BYTES = 32
TOKEN_TTL = timedelta(minutes=15)
ANNOUNCEMENT_INTERVAL = timedelta(seconds=30)
DISCOVERY_SCOPE = "discovery:announce"


class DiscoveryGrantRejected(InvError):
    """Same public denial for every failed check; reason is audit-only metadata."""

    _REASONS = frozenset(
        {
            "token_format",
            "tenant_claim",
            "grant_unknown",
            "digest_mismatch",
            "scope_mismatch",
            "tenant_mismatch",
            "installation_mismatch",
            "revoked",
            "expiry_unavailable",
            "expired",
            "announcement_time_unavailable",
            "refresh_too_soon",
            "grant_rejected",
        }
    )

    def __init__(self, reason_code: str = "grant_rejected"):
        self.reason_code = reason_code if reason_code in self._REASONS else "grant_rejected"
        super().__init__(
            AUTH_INVALID_CREDENTIAL,
            "discovery credential is not valid",
            status=403,
        )


def token_sha256(token: str) -> str:
    if not isinstance(token, str) or not TOKEN_RE.fullmatch(token):
        raise DiscoveryGrantRejected("token_format")
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def reject_discovery_credential(reason_code: str = "grant_rejected") -> None:
    """Raise one public denial; reason code contains no credential material."""
    raise DiscoveryGrantRejected(reason_code)


def validate_discovery_grant(
    row: Mapping[str, Any] | None,
    *,
    token: str,
    asserted_tenant: str,
    installation_id: str,
    now: datetime,
) -> Mapping[str, Any]:
    """Check tenant, install, scope, status, expiry and cadence fail-closed."""
    try:
        digest = token_sha256(token)
        tenant_id = uuid.UUID(asserted_tenant)
    except DiscoveryGrantRejected:
        raise
    except (ValueError, TypeError, AttributeError):
        reject_discovery_credential("tenant_claim")
    if not row:
        reject_discovery_credential("grant_unknown")
    if not hmac.compare_digest(str(row.get("token_sha256", "")), digest):
        reject_discovery_credential("digest_mismatch")
    if row.get("scope") != DISCOVERY_SCOPE:
        reject_discovery_credential("scope_mismatch")
    if str(row.get("tenant_id")) != str(tenant_id):
        reject_discovery_credential("tenant_mismatch")
    if row.get("installation_id") != installation_id:
        reject_discovery_credential("installation_mismatch")
    if row.get("revoked_at") is not None:
        reject_discovery_credential("revoked")
    expires_at = row.get("expires_at")
    if (
        not isinstance(expires_at, datetime)
        or expires_at.tzinfo is None
        or expires_at.utcoffset() is None
        or not isinstance(now, datetime)
        or now.tzinfo is None
        or now.utcoffset() is None
    ):
        reject_discovery_credential("expiry_unavailable")
    current = now.astimezone(timezone.utc)
    if expires_at.astimezone(timezone.utc) <= current:
        reject_discovery_credential("expired")
    last_announcement_at = row.get("last_announcement_at")
    if last_announcement_at is not None:
        if (
            not isinstance(last_announcement_at, datetime)
            or last_announcement_at.tzinfo is None
            or last_announcement_at.utcoffset() is None
        ):
            reject_discovery_credential("announcement_time_unavailable")
        last = last_announcement_at.astimezone(timezone.utc)
        if current < last + ANNOUNCEMENT_INTERVAL:
            reject_discovery_credential("refresh_too_soon")
    return row
