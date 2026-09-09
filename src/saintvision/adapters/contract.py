"""The provider adapter contract (S10-BE).

PLAN-BACKEND-001: external providers connect through one
``probe/install/authenticate/run/cancel/collect/redact/attest`` contract, and
AC-10 requires the Codex and Claude adapters to satisfy *the same* contract —
which is only checkable if the contract is a real object with a conformance
suite behind it, not a paragraph everyone implements slightly differently.

No provider SDK is imported here, and none is a dependency of this package.
Two reasons, both deliberate:

* The runtime dependency set is locked in S01 (PLAN-BACKEND-001). Adding one
  vendor's SDK now would preempt that decision and tilt the contract toward
  whichever one landed first.
* Credentials arrive through a credential provider reference (PLAN-STORAGE-001)
  and that provider is an S01 decision. An adapter that reads an API key from
  the environment would be a different security model than the one specified.

**Cancellation is the part worth reading closely.** Providers differ in whether
cancelling actually stops work: a streaming HTTP request can be closed by the
client while the server keeps generating and keeps billing, and some providers
offer no server-side cancel at all. So :meth:`ProviderAdapter.cancel` returns a
tri-state, never a boolean. ``UNKNOWN`` is a real outcome, and it is what stops
the orchestrator from automatically retrying — PLAN-BACKEND-001 is explicit
that an unverifiable external side effect must not be retried on its own.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterator, Protocol, runtime_checkable

CONTRACT_VERSION = "1.0.0"


class Capability(str, Enum):
    """What an adapter can do. Declared, then verified by conformance."""

    STREAMING = "streaming"
    TOOL_USE = "tool_use"
    STRUCTURED_OUTPUT = "structured_output"
    #: The provider can stop work server-side, not merely close the connection.
    SERVER_SIDE_CANCEL = "server_side_cancel"
    #: The provider reports token usage on the response.
    USAGE_REPORTING = "usage_reporting"
    #: The provider returns a stable identifier for the exact model build.
    MODEL_PINNING = "model_pinning"


class CancelOutcome(str, Enum):
    """Whether cancellation actually stopped the work.

    Deliberately not a boolean. Closing a stream is not the same as stopping
    generation, and reporting "cancelled" when the provider kept going would
    make the Run record wrong and the bill surprising.
    """

    STOPPED = "stopped"
    #: The request had already finished; nothing to stop.
    ALREADY_FINISHED = "already_finished"
    #: The adapter asked, and the provider said no or offers no mechanism.
    NOT_SUPPORTED = "not_supported"
    #: The adapter could not determine what happened. Blocks automatic retry.
    UNKNOWN = "unknown"


class AttestationResult(str, Enum):
    VERIFIED = "verified"
    #: The provider does not expose enough to verify. Not the same as failure.
    UNVERIFIABLE = "unverifiable"
    MISMATCH = "mismatch"


@dataclass(frozen=True, slots=True)
class ProbeResult:
    """What ``probe`` learned about the provider without authenticating."""

    reachable: bool
    #: Provider-reported version or API date. None when it does not publish one.
    api_version: str | None = None
    #: Model identifiers the provider advertises. Never invented by the adapter.
    available_models: tuple[str, ...] = ()
    latency_ms: int | None = None
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AuthResult:
    """The outcome of authenticating. Never carries the credential itself."""

    authenticated: bool
    #: Opaque handle the adapter uses internally. Not a token, not logged.
    principal_ref: str | None = None
    expires_at: dt.datetime | None = None
    #: Scopes the provider granted, when it reports them.
    scopes: tuple[str, ...] = ()
    failure_code: str | None = None


@dataclass(frozen=True, slots=True)
class RunHandle:
    """A started request. Enough to cancel and collect it, and nothing more."""

    handle_id: str
    provider: str
    #: The exact model build in force, when the provider pins one.
    model_id: str | None = None
    started_at: dt.datetime | None = None


@dataclass(frozen=True, slots=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    #: Provider-reported cost when available. Never inferred from a price table
    #: the adapter carries, which would go stale silently.
    reported_cost: float | None = None
    currency: str | None = None


@dataclass(frozen=True, slots=True)
class CollectResult:
    """The finished output of a run.

    ``content`` has already been through :meth:`ProviderAdapter.redact`. The
    conformance suite checks that, because an adapter that returns raw content
    here defeats the first redaction pass ADR-014 requires.
    """

    completed: bool
    content: str
    usage: Usage = field(default_factory=Usage)
    stop_reason: str | None = None
    #: The exact model build that produced this, for the RunRecord.
    model_id: str | None = None
    #: True when redaction removed something. Recorded, not hidden.
    redacted: bool = False
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class Attestation:
    """Evidence about what actually ran.

    ``UNVERIFIABLE`` is a legitimate result and must not be reported as
    ``VERIFIED``. An attestation that cannot fail is not an attestation.
    """

    result: AttestationResult
    #: Digest of the request as sent, so the Evidence hash can be matched.
    request_sha256: str | None = None
    response_sha256: str | None = None
    model_id: str | None = None
    #: What the provider itself asserts, when it asserts anything.
    provider_claims: dict[str, Any] = field(default_factory=dict)
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class InstallReport:
    """Whether the local prerequisites for this adapter are present.

    ``install`` never installs anything by itself. Reaching out to a package
    index during a Run would be an unreviewed side effect and an L2 action
    under the governance table; the adapter reports and the operator decides.
    """

    ready: bool
    missing: tuple[str, ...] = ()
    instructions: str | None = None


@runtime_checkable
class ProviderAdapter(Protocol):
    """The eight members every provider adapter implements.

    An adapter is not free to add a ninth that the orchestrator depends on:
    the point of the contract is that Codex and Claude are interchangeable at
    this boundary (AC-10).
    """

    #: Stable adapter name, used as the lineage key. Not a display name.
    name: str
    #: SemVer of the contract this adapter implements.
    contract_version: str
    capabilities: frozenset[Capability]

    def probe(self) -> ProbeResult:
        """Reachability and advertised models, without credentials."""

    def install(self) -> InstallReport:
        """Report local prerequisites. Does not install."""

    def authenticate(self, credential_ref: str) -> AuthResult:
        """Authenticate using a credential *reference*, never a raw secret."""

    def run(self, request: dict[str, Any]) -> RunHandle:
        """Start a request and return a handle."""

    def cancel(self, handle: RunHandle) -> CancelOutcome:
        """Attempt to stop the work. Returns what actually happened."""

    def collect(self, handle: RunHandle) -> CollectResult:
        """Collect the finished result, already redacted."""

    def redact(self, content: str) -> tuple[str, bool]:
        """Return ``(redacted, changed)``. The first pass required by ADR-014."""

    def attest(self, handle: RunHandle) -> Attestation:
        """Report verifiable facts about what ran."""


def stream_or_collect(
    adapter: ProviderAdapter, handle: RunHandle
) -> Iterator[str] | CollectResult:
    """Prefer streaming where the adapter declares it.

    Long outputs on a non-streaming call are the usual cause of a request that
    times out at the HTTP layer after the provider has already been paid for
    the work. Where an adapter cannot stream, this falls back rather than
    pretending.
    """
    if Capability.STREAMING in adapter.capabilities and hasattr(adapter, "stream"):
        return adapter.stream(handle)  # type: ignore[attr-defined]
    return adapter.collect(handle)
