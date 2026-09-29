"""Runtime settings.

Values that S01 has not decided are absent, not guessed. Reading one that has
not been supplied raises rather than falling back to a plausible default — a
wrong default here becomes a silent trust boundary (AC-01).
"""

from __future__ import annotations

import os
import re
import uuid
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


#: The widest freshness window a deployment may configure: one year. A
#: measurement older than that is evidence of the past, not of the bytes now.
MEASUREMENT_MAX_AGE_CEILING_SECONDS = 31_536_000


def validate_measurement_max_age(value: object) -> int:
    """A finite, positive number of seconds within the ceiling, or a refusal."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("model_measurement_max_age_seconds must be an integer number of seconds")
    if not 1 <= value <= MEASUREMENT_MAX_AGE_CEILING_SECONDS:
        raise ValueError(
            f"model_measurement_max_age_seconds must be between 1 and {MEASUREMENT_MAX_AGE_CEILING_SECONDS}"
        )
    return value


#: The one spelling ``INV_CONTROL_PLANE_HOST_ID`` accepts: canonical hyphenated
#: lowercase hex. No case folding, no whitespace stripping, no braces or
#: ``urn:`` form -- a value that is not already this is refused, so a hostname,
#: an address or a path can never become the host identity (design #218 §2-9).
_HOST_ID: Final[re.Pattern[str]] = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


def parse_control_plane_host_id(value: object) -> uuid.UUID:
    """Strict: exactly a canonical UUID string, or a refusal that repeats nothing.

    The offending value is deliberately not in the message. The same text can
    end up in a startup log or a 500 body, and the whole point of the strict
    form is that host-identifying strings do not travel.
    """
    if not isinstance(value, str) or not _HOST_ID.match(value):
        raise ValueError(
            "INV_CONTROL_PLANE_HOST_ID must be a canonical lowercase hyphenated UUID"
        )
    return uuid.UUID(value)


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
    #: ``SET LOCAL lock_timeout`` for every write transaction in the business
    #: lane (G-04 card 84; ``api/lock_wait.py``). Ordinary contention waits and
    #: proceeds on the committed row; a wait past this budget is answered
    #: ``SYS-0001/503/retryable``. Validated in ``__post_init__``: an integer
    #: between 1 and 600000 milliseconds.
    business_lock_timeout_ms: int = 5_000
    #: How old a kernel-recorded model measurement may be and still verify a
    #: model version (W3, design #209 v1.1 §6 freshness). Validated in
    #: ``__post_init__``: an integer number of seconds, 1..31536000.
    model_measurement_max_age_seconds: int = 86_400
    #: Base URL of the execution kernel, for the observations business routes
    #: read back over HTTP (VF-CL-03). Absent is a valid deployment: a route
    #: that needs an observation then refuses with 503 rather than guessing a
    #: host, which is the same rule the rest of this module follows.
    kernel_base_url: str | None = None
    #: The opaque identity of this control-plane host, under which conformance
    #: records are written and read (G-03 stage two, design #218 §2-9). Absent
    #: is a valid deployment for everything except that feature: the producer
    #: refuses to start and the read routes answer ``SYS-0002`` rather than
    #: reporting another host's records or pretending nothing was observed.
    #: Never inferred from the hostname or the address.
    control_plane_host_id: uuid.UUID | None = None

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

    def __post_init__(self) -> None:
        # Fail at construction, not at the first write: a deployment with a
        # nonsensical budget must not start and then refuse every write.
        from .api.lock_wait import validate_lock_timeout

        validate_lock_timeout(self.business_lock_timeout_ms)
        validate_measurement_max_age(self.model_measurement_max_age_seconds)
        if self.control_plane_host_id is not None and not isinstance(
            self.control_plane_host_id, uuid.UUID
        ):
            raise ValueError("control_plane_host_id must be a uuid.UUID or None")

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
            business_lock_timeout_ms=_get_int("INV_BUSINESS_LOCK_TIMEOUT_MS", 5_000),
            model_measurement_max_age_seconds=_get_int("INV_MODEL_MEASUREMENT_MAX_AGE_SECONDS", 86_400),
            tenant_id=os.environ.get("INV_TENANT_ID"),
            oidc_issuer=os.environ.get("INV_OIDC_ISSUER"),
            oidc_audience=os.environ.get("INV_OIDC_AUDIENCE"),
            oidc_client_ids=tuple(
                value.strip()
                for value in os.environ.get("INV_OIDC_CLIENT_IDS", "").split(",")
                if value.strip()
            ),
            oidc_jwks_file=os.environ.get("INV_OIDC_JWKS_FILE"),
            kernel_base_url=os.environ.get("INV_KERNEL_BASE_URL"),
            control_plane_host_id=_host_id_from_env(),
        )


def _host_id_from_env() -> uuid.UUID | None:
    raw = os.environ.get("INV_CONTROL_PLANE_HOST_ID")
    if raw is None:
        return None
    # Set but malformed is a configuration error, not "absent": the process
    # must not start on a value it would then silently ignore.
    return parse_control_plane_host_id(raw)


def unresolved_s01_settings() -> list[str]:
    """Return the S01-owned settings still missing, for the startup report."""
    return sorted(name for name in S01_PENDING if not os.environ.get(name))
