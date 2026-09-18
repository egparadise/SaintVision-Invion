"""A reference adapter with no network (S10-BE).

Not a mock for tests to assert against — it is the executable statement of what
the contract means. When the Codex and Claude adapters are written against real
transports, this is what they are compared to, and the conformance suite is
what does the comparing.

It deliberately declares a *narrow* capability set. An adapter that declares
everything and implements it locally would make the suite look satisfied while
proving nothing about a real provider.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import re
from typing import Any, Final

from ..ids import new_id
from .contract import (
    CONTRACT_VERSION,
    Attestation,
    AttestationResult,
    AuthResult,
    CancelOutcome,
    Capability,
    CollectResult,
    InstallReport,
    ProbeResult,
    RunHandle,
    Usage,
)

REDACTED: Final[str] = "[redacted]"

#: Patterns removed before content leaves an adapter (ADR-014, first pass).
#: Ordered longest-context-first so a bearer header is caught as a whole rather
#: than leaving "Authorization:" attached to a redacted tail.
_PATTERNS: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    (
        "private_key",
        re.compile(
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
            re.DOTALL,
        ),
    ),
    ("bearer", re.compile(r"(?i)\bauthorization\s*:\s*bearer\s+[A-Za-z0-9._\-]+")),
    ("presigned", re.compile(r"https?://\S*[?&](?i:x-amz-signature|signature|sig)=\S+")),
    ("api_key", re.compile(r"\b(?:sk|pk|rk)-[A-Za-z0-9._\-]{16,}")),
    ("token_assignment", re.compile(r"(?i)\b(token|secret|password)\s*[=:]\s*\S+")),
)


def recognised_secrets(content: str) -> tuple[str, ...]:
    """Labels of the patterns that match, never the text that matched.

    Returning the label and not the match is the point: the caller wants to
    refuse this content and say why, and putting the matched fragment into an
    error message or a log is the same leak the refusal exists to prevent.

    Recognising is not proving. An empty result means nothing here matched, not
    that the content holds no secret, and anything built on it must say so.
    """
    return tuple(label for label, pattern in _PATTERNS if pattern.search(content))


def redact_text(content: str) -> tuple[str, bool]:
    """Return ``(redacted, changed)``.

    Idempotent: the replacement contains nothing any pattern matches, so a
    second pass is a no-op. The conformance suite checks that, because a
    redactor that keeps changing its own output makes the application log and
    the collector log disagree.
    """
    out = content
    for _, pattern in _PATTERNS:
        out = pattern.sub(REDACTED, out)
    return out, out != content


class ReferenceAdapter:
    """In-memory adapter. No network, no credentials, no provider SDK."""

    name = "reference"
    contract_version = CONTRACT_VERSION
    capabilities = frozenset({Capability.USAGE_REPORTING, Capability.MODEL_PINNING})

    #: Not a real model. Named so it can never be mistaken for one.
    MODEL_ID = "reference-null-1"

    def __init__(self, *, clock: Any = None) -> None:
        self._clock = clock or (lambda: dt.datetime.now(dt.timezone.utc))
        self._runs: dict[str, dict[str, Any]] = {}

    # -- contract ---------------------------------------------------------

    def probe(self) -> ProbeResult:
        return ProbeResult(
            reachable=True,
            api_version=CONTRACT_VERSION,
            available_models=(self.MODEL_ID,),
            latency_ms=0,
        )

    def install(self) -> InstallReport:
        return InstallReport(ready=True)

    def authenticate(self, credential_ref: str) -> AuthResult:
        if not credential_ref:
            return AuthResult(authenticated=False, failure_code="AUTH-MISSING-CREDENTIAL")
        # A handle derived from the reference, not the reference itself: it must
        # be safe to log, and it must not be reversible into the credential.
        principal = hashlib.sha256(credential_ref.encode("utf-8")).hexdigest()[:16]
        return AuthResult(authenticated=True, principal_ref=f"ref_{principal}")

    def run(self, request: dict[str, Any]) -> RunHandle:
        handle_id = new_id("run")
        started = self._clock()
        payload = str(request.get("input", ""))
        self._runs[handle_id] = {
            "request": request,
            "started_at": started,
            "finished": False,
            "cancelled": False,
            "output": f"OK: {payload}",
        }
        return RunHandle(
            handle_id=handle_id,
            provider=self.name,
            model_id=self.MODEL_ID,
            started_at=started,
        )

    def cancel(self, handle: RunHandle) -> CancelOutcome:
        state = self._runs.get(handle.handle_id)
        if state is None:
            return CancelOutcome.UNKNOWN
        if state["finished"]:
            return CancelOutcome.ALREADY_FINISHED
        # This adapter has no server to ask, and says so rather than claiming a
        # stop it cannot verify.
        state["cancelled"] = True
        return CancelOutcome.NOT_SUPPORTED

    def collect(self, handle: RunHandle) -> CollectResult:
        state = self._runs.get(handle.handle_id)
        if state is None:
            return CollectResult(
                completed=False, content="", error_code="RES-RUN-NOT-FOUND"
            )
        state["finished"] = True
        content, changed = self.redact(state["output"])
        return CollectResult(
            completed=True,
            content=content,
            usage=Usage(
                input_tokens=max(1, len(str(state["request"])) // 4),
                output_tokens=max(1, len(content) // 4),
            ),
            stop_reason="end_turn",
            model_id=self.MODEL_ID,
            redacted=changed,
        )

    def redact(self, content: str) -> tuple[str, bool]:
        return redact_text(content)

    def attest(self, handle: RunHandle) -> Attestation:
        state = self._runs.get(handle.handle_id)
        if state is None:
            return Attestation(
                result=AttestationResult.UNVERIFIABLE, detail="unknown handle"
            )
        from .conformance import request_digest

        content, _ = self.redact(state["output"])
        return Attestation(
            result=AttestationResult.VERIFIED,
            request_sha256=request_digest(state["request"]),
            response_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            model_id=self.MODEL_ID,
            provider_claims={"deterministic": True},
        )
