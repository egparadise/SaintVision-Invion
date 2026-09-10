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
S01_PENDING: Final[frozenset[str]] = frozenset(
    {
        "INV_OIDC_ISSUER",
        "INV_OIDC_AUDIENCE",
        "INV_OIDC_JWKS_URL",
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
        )


def unresolved_s01_settings() -> list[str]:
    """Return the S01-owned settings still missing, for the startup report."""
    return sorted(name for name in S01_PENDING if not os.environ.get(name))
