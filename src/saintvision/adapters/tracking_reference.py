"""An in-memory tracking sink with no network (S10-BE, design #168 §3).

The executable statement of what :class:`TrackingSink` means, and the sink
the PG tests deliver against. It keeps what it was given, finds it again by
``inv.intent_id``, and attests by re-digesting the stored tag set -- so an
attestation can fail, which is what makes it one.

Fault injection is explicit and named, never ambient: ``fail_with`` makes the
next mirror calls return a coded failure (``unavailable`` for a server that is
down, ``refused`` for a credential the server rejects), ``tamper`` rewrites a
stored record so attest reports ``MISMATCH``. The conformance suite uses
``tamper``; the delivery tests use both.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from ..tracking.canonical import payload_sha256
from ..tracking.codes import MirrorStatus, code_for_status
from .contract import Attestation, AttestationResult, AuthResult, ProbeResult
from .reference import redact_text
from .tracking import TRACKING_CONTRACT_VERSION, MirrorRecord, MirrorResult


@dataclass
class _Stored:
    intent_id: str
    experiment: str
    payload: dict[str, Any]


@dataclass
class ReferenceSink:
    name: str = "reference-tracking"
    contract_version: str = TRACKING_CONTRACT_VERSION
    #: Injected failure for the next ``mirror`` calls: (status, remaining count).
    _fault: tuple[MirrorStatus, int] | None = field(default=None, repr=False)
    _records: dict[str, _Stored] = field(default_factory=dict, repr=False)
    _by_intent: dict[str, str] = field(default_factory=dict, repr=False)
    _tampered: set[str] = field(default_factory=set, repr=False)
    #: Counts of calls, for the duplicate-delivery tests (find once, mirror 0).
    calls: dict[str, int] = field(default_factory=lambda: {"find": 0, "mirror": 0, "attest": 0})

    # ---------------------------------------------------------------- faults

    def fail_with(self, status: MirrorStatus, *, times: int = 1) -> None:
        if status is MirrorStatus.MIRRORED:
            raise ValueError("a fault is a failure status")
        self._fault = (status, times)

    def tamper(self, reference_id: str) -> None:
        if reference_id not in self._records:
            raise KeyError(reference_id)
        self._tampered.add(reference_id)

    # -------------------------------------------------------------- contract

    def probe(self) -> ProbeResult:
        return ProbeResult(reachable=True, api_version="reference", latency_ms=0)

    def authenticate(self, secret_handle: Any) -> AuthResult:
        # The handle is consumed, not stored and not echoed.
        if secret_handle is None:
            return AuthResult(authenticated=False, failure_code="TRACK-0002")
        return AuthResult(authenticated=True, principal_ref="reference-principal")

    def find(self, intent_id: str) -> str | None:
        self.calls["find"] += 1
        return self._by_intent.get(intent_id)

    def mirror(self, record: MirrorRecord) -> MirrorResult:
        self.calls["mirror"] += 1
        if self._fault is not None:
            status, remaining = self._fault
            self._fault = (status, remaining - 1) if remaining > 1 else None
            return MirrorResult(status=status, error_code=code_for_status(status), detail="injected")
        existing = self._by_intent.get(record.intent_id)
        if existing is not None:
            return MirrorResult(
                status=MirrorStatus.MIRRORED,
                reference_id=existing,
                response_payload_sha256=self._digest(existing),
            )
        reference_id = "ref-" + hashlib.sha256(record.intent_id.encode()).hexdigest()[:16]
        self._records[reference_id] = _Stored(record.intent_id, record.experiment, dict(record.payload))
        self._by_intent[record.intent_id] = reference_id
        return MirrorResult(
            status=MirrorStatus.MIRRORED,
            reference_id=reference_id,
            response_payload_sha256=self._digest(reference_id),
        )

    def redact(self, content: str) -> tuple[str, bool]:
        return redact_text(content)

    def attest(self, reference_id: str) -> Attestation:
        self.calls["attest"] += 1
        stored = self._records.get(reference_id)
        if stored is None:
            return Attestation(result=AttestationResult.UNVERIFIABLE, detail="unknown reference")
        digest = self._digest(reference_id)
        expected = payload_sha256(stored.payload)
        result = AttestationResult.VERIFIED if digest == expected else AttestationResult.MISMATCH
        return Attestation(
            result=result,
            request_sha256=expected,
            response_sha256=digest,
            provider_claims={"inv.intent_id": stored.intent_id},
        )

    # --------------------------------------------------------------- helpers

    def _digest(self, reference_id: str) -> str:
        stored = self._records[reference_id]
        if reference_id in self._tampered:
            tampered = dict(stored.payload)
            tampered["tags"] = {**tampered.get("tags", {}), "inv.tampered": "1"}
            return payload_sha256(tampered)
        return payload_sha256(stored.payload)
