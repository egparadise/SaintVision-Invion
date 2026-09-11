"""Runtime settings.

Values that S01 has not decided are absent, not guessed. Reading one that has
not been supplied raises rather than falling back to a plausible default — a
wrong default here becomes a silent trust boundary (AC-01).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Final

#: Settings that S01 owns and that this sprint must not invent.
#: Documented in docs/vault/30_Development/Claude 영역 구현 준비.md.
#:
#: ``INV_OIDC_JWKS_URL`` was here and has been removed, because the decision it
#: was waiting for was made and went the other way: the verifier is offline by
#: design (``inv.identity.AccessTokens``) and takes an operator-supplied trust
#: bundle from a *file*. A URL is the thing that design rejects — fetching keys
#: at verification time makes the identity provider's availability a dependency
#: of every request and its DNS a trust boundary. Leaving the name here would
#: have kept a decided question looking open and pointed at the wrong answer.
S01_PENDING: Final[frozenset[str]] = frozenset(
    {
        "INV_NODE_MTLS_CA_BUNDLE",
        "INV_OBJECT_STORE_ENDPOINT",
    }
)


class SettingUnresolved(RuntimeError):
    """A required setting has no value and no defensible default."""


def _get(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if value is None:
        hint = " (owned by S01, not yet decided)" if name in S01_PENDING else ""
        raise SettingUnresolved(f"{name} is not set{hint}")
    return value


def _get_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return default if raw is None else int(raw)


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    #: Months of resource/audit partitions kept ahead of now (CR-06).
    partition_lead_months: int = 3
    #: Startup refuses below this many months of remaining partitions (CR-06).
    partition_minimum_months: int = 1
    #: Heartbeat older than this marks a node lost (AC-02 target is <=60s).
    heartbeat_timeout_seconds: int = 60
    #: Bootstrap enrollment token lifetime.
    bootstrap_token_ttl_seconds: int = 900
    #: Cursor pagination (PLAN-BACKEND-001).
    page_limit_default: int = 50
    page_limit_max: int = 200
    #: Idempotency ledger retention.
    idempotency_ttl_seconds: int = 86_400

    #: Real login. Absent means the static development verifier, which refuses
    #: to be constructed outside dev and test — so a deployment either has all
    #: four of these or has no way to authenticate anyone at all.
    tenant_id: str | None = None
    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_client_ids: tuple[str, ...] = ()
    #: A file, not a URL. Fetching keys at verification time makes the identity
    #: provider's availability a dependency of every request.
    oidc_jwks_file: str | None = None

    @property
    def login_configured(self) -> bool:
        return all(
            (
                self.tenant_id,
                self.oidc_issuer,
                self.oidc_audience,
                self.oidc_client_ids,
                self.oidc_jwks_file,
            )
        )

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_url=_get("INV_DATABASE_URL"),
            partition_lead_months=_get_int("INV_PARTITION_LEAD_MONTHS", 3),
            partition_minimum_months=_get_int("INV_PARTITION_MINIMUM_MONTHS", 1),
            heartbeat_timeout_seconds=_get_int("INV_HEARTBEAT_TIMEOUT_SECONDS", 60),
            bootstrap_token_ttl_seconds=_get_int("INV_BOOTSTRAP_TOKEN_TTL_SECONDS", 900),
            page_limit_default=_get_int("INV_PAGE_LIMIT_DEFAULT", 50),
            page_limit_max=_get_int("INV_PAGE_LIMIT_MAX", 200),
            idempotency_ttl_seconds=_get_int("INV_IDEMPOTENCY_TTL_SECONDS", 86_400),
            tenant_id=os.environ.get("INV_TENANT_ID"),
            oidc_issuer=os.environ.get("INV_OIDC_ISSUER"),
            oidc_audience=os.environ.get("INV_OIDC_AUDIENCE"),
            oidc_client_ids=tuple(
                value
                for value in os.environ.get("INV_OIDC_CLIENT_IDS", "").split(",")
                if value.strip()
            ),
            oidc_jwks_file=os.environ.get("INV_OIDC_JWKS_FILE"),
        )


def unresolved_s01_settings() -> list[str]:
    """Return the S01-owned settings still missing, for the startup report."""
    return sorted(name for name in S01_PENDING if not os.environ.get(name))
