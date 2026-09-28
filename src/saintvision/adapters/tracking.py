"""The tracking sink contract and its conformance suite (S10-BE, design #168 §3).

MLflow does not execute prompts, so it is not a :class:`ProviderAdapter` and
is not asked for the eight provider members. It is a *sink*: the mirror worker
hands it a record derived from the lineage database and asks it to store a
copy, find one it stored before, and attest what it holds. The same result
types as the provider contract are reused where they mean the same thing
(``ProbeResult``, ``AuthResult``, ``Attestation``), so the two contracts cannot
drift in how they say "reachable", "authenticated" or "verified".

The suite discriminates the same way :mod:`.conformance` does: a sink that
always attests ``VERIFIED``, echoes its credential, or forgets what it stored
fails the check that names that defect. ``tests/test_tracking_sink.py`` runs
it against sinks broken in exactly one way each.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol, runtime_checkable

from ..tracking.canonical import payload_sha256
from ..tracking.codes import MirrorStatus, check_pair
from .contract import Attestation, AttestationResult, AuthResult, ProbeResult

TRACKING_CONTRACT_VERSION = "1.0.0"

SUBJECT_KINDS: tuple[str, ...] = (
    "experiment",
    "training_run",
    "eval_run",
    "model_version",
    "deployment",
)


@dataclass(frozen=True, slots=True)
class MirrorRecord:
    """What the worker asks a sink to store. Derived from an intent row."""

    intent_id: str
    subject_kind: str
    #: Experiment name, already prefixed (``<prefix>/<tenant_short>/<project>``).
    experiment: str
    payload: dict[str, Any]
    payload_sha256: str

    def __post_init__(self) -> None:
        if self.subject_kind not in SUBJECT_KINDS:
            raise ValueError(f"unknown subject kind {self.subject_kind!r}")
        if payload_sha256(self.payload) != self.payload_sha256:
            raise ValueError("payload_sha256 does not match the payload")


@dataclass(frozen=True, slots=True)
class MirrorResult:
    """The outcome of one ``mirror`` call. ``reference_id`` is the server's id."""

    status: MirrorStatus
    reference_id: str | None = None
    response_payload_sha256: str | None = None
    error_code: str | None = None
    detail: str | None = None

    def __post_init__(self) -> None:
        # Exactly the design §5 pair: mirrored/None, unavailable/0001,
        # refused/0002, mismatch/0003. Anything else is refused here so a
        # refusal can never be recorded (and later read) as "unavailable".
        check_pair(self.status, self.error_code)
        if self.status is MirrorStatus.MIRRORED and not self.reference_id:
            raise ValueError("a mirrored result carries the sink's reference")


@runtime_checkable
class TrackingSink(Protocol):
    """The seven members every tracking sink implements."""

    name: str
    contract_version: str

    def probe(self) -> ProbeResult:
        """Reachability and API version, without credentials."""

    def authenticate(self, secret_handle: Any) -> AuthResult:
        """Authenticate from a worker-only handle. Never returns a token."""

    def find(self, intent_id: str) -> str | None:
        """The server reference tagged ``inv.intent_id``, or None."""

    def mirror(self, record: MirrorRecord) -> MirrorResult:
        """Store the record and return the reference, or a coded failure."""

    def redact(self, content: str) -> tuple[str, bool]:
        """ADR-014 first pass for run names and parameter values."""

    def attest(self, reference_id: str) -> Attestation:
        """Digest of the tag set the server holds for ``reference_id``."""


# --------------------------------------------------------------------------
# Conformance
# --------------------------------------------------------------------------

REDACTION_PROBES: tuple[tuple[str, str], ...] = (
    ("api_key", "key sk-test-000111222333444555666777888999"),
    ("bearer", "Authorization: Bearer abcdefghijklmnopqrstuvwxyz012345"),
    ("presigned_url", "https://store.example/o?X-Amz-Signature=deadbeefcafe"),
    ("private_key", "-----BEGIN PRIVATE KEY-----\nMIIB\n-----END PRIVATE KEY-----"),
)


@dataclass(frozen=True, slots=True)
class Check:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class TrackingConformanceReport:
    sink: str
    contract_version: str
    checks: list[Check] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for c in self.checks if c.passed)

    @property
    def failed(self) -> int:
        return sum(1 for c in self.checks if not c.passed)

    @property
    def conformant(self) -> bool:
        return self.failed == 0 and self.passed > 0

    def failures(self) -> list[Check]:
        return [c for c in self.checks if not c.passed]

    def to_dict(self) -> dict[str, Any]:
        return {
            "sink": self.sink,
            "contractVersion": self.contract_version,
            "total": len(self.checks),
            "passed": self.passed,
            "failed": self.failed,
            "conformant": self.conformant,
            "checks": [{"name": c.name, "passed": c.passed, "detail": c.detail} for c in self.checks],
        }


def _check(name: str, fn: Callable[[], tuple[bool, str]]) -> Check:
    try:
        passed, detail = fn()
    except Exception as exc:  # noqa: BLE001 - a sink may raise anything
        return Check(name=name, passed=False, detail=f"{type(exc).__name__}: {exc}")
    return Check(name=name, passed=passed, detail=detail)


def canonical_record(intent_id: str = "mmi_00000000000000000000000000") -> MirrorRecord:
    payload = {
        "params": {"suite": "conformance", "version": "1.0.0"},
        "tags": {"inv.intent_id": intent_id, "inv.tenant_id": "t"},
        "metrics": [{"key": "gate_passed", "value": 1, "step": 0, "timestamp_ms": 0}],
    }
    return MirrorRecord(
        intent_id=intent_id,
        subject_kind="eval_run",
        experiment="conf/t/prj_00000000000000000000000000",
        payload=payload,
        payload_sha256=payload_sha256(payload),
    )


def run_tracking_conformance(
    sink: TrackingSink, *, secret_handle: Any = "conformance://dummy-handle"
) -> TrackingConformanceReport:
    report = TrackingConformanceReport(
        sink=getattr(sink, "name", type(sink).__name__),
        contract_version=getattr(sink, "contract_version", "unknown"),
    )
    add = report.checks.append
    add(_check("declares_contract_version", lambda: _declares_version(sink)))
    add(_check("implements_every_member", lambda: _implements_members(sink)))
    add(_check("probe_without_credentials", lambda: _probe(sink)))
    add(_check("authenticate_does_not_echo_the_handle", lambda: _authenticate(sink, secret_handle)))
    add(_check("find_is_none_before_mirror", lambda: _find_before(sink)))
    add(_check("mirror_returns_a_coded_result", lambda: _mirror(sink)))
    add(_check("find_is_idempotent_after_mirror", lambda: _find_after(sink)))
    add(_check("redact_removes_known_secrets", lambda: _redact(sink)))
    add(_check("redact_is_idempotent", lambda: _redact_idempotent(sink)))
    add(_check("attest_matches_what_was_mirrored", lambda: _attest_matches(sink)))
    add(_check("attest_does_not_overclaim", lambda: _attest_unknown(sink)))
    add(_check("attest_surfaces_mismatch", lambda: _attest_mismatch(sink)))
    return report


def _declares_version(sink: TrackingSink) -> tuple[bool, str]:
    version = getattr(sink, "contract_version", None)
    if version != TRACKING_CONTRACT_VERSION:
        return False, f"declares {version!r}, suite implements {TRACKING_CONTRACT_VERSION!r}"
    return True, version


def _implements_members(sink: TrackingSink) -> tuple[bool, str]:
    required = ("probe", "authenticate", "find", "mirror", "redact", "attest")
    missing = [m for m in required if not callable(getattr(sink, m, None))]
    if not isinstance(getattr(sink, "name", None), str) or not sink.name:
        missing.append("name")
    return (not missing), ("missing: " + ", ".join(missing) if missing else "all present")


def _probe(sink: TrackingSink) -> tuple[bool, str]:
    result = sink.probe()
    if not isinstance(result, ProbeResult):
        return False, "probe did not return a ProbeResult"
    return True, f"reachable={result.reachable}"


def _authenticate(sink: TrackingSink, handle: Any) -> tuple[bool, str]:
    result = sink.authenticate(handle)
    if not isinstance(result, AuthResult):
        return False, "authenticate did not return an AuthResult"
    rendered = str(handle)
    for value in (result.principal_ref, result.failure_code):
        if value is not None and rendered and rendered in str(value):
            return False, "the secret handle is echoed in the result"
    if not result.authenticated and not result.failure_code:
        return False, "failed authentication without a failure code"
    return True, f"authenticated={result.authenticated}"


def _find_before(sink: TrackingSink) -> tuple[bool, str]:
    found = sink.find("mmi_7ZZZZZZZZZZZZZZZZZZZZZZZZZ")
    if found is not None:
        return False, "find returned a reference for an intent never mirrored"
    return True, "none"


def _mirror(sink: TrackingSink) -> tuple[bool, str]:
    result = sink.mirror(canonical_record("mmi_0000000000000000000000000A"))
    if not isinstance(result, MirrorResult):
        return False, "mirror did not return a MirrorResult"
    if result.status is MirrorStatus.MIRRORED and not result.reference_id:
        return False, "mirrored without a reference"
    return True, result.status.value


def _find_after(sink: TrackingSink) -> tuple[bool, str]:
    record = canonical_record("mmi_0000000000000000000000000B")
    result = sink.mirror(record)
    if result.status is not MirrorStatus.MIRRORED:
        return True, f"not mirrored ({result.status.value}); find not exercised"
    first = sink.find(record.intent_id)
    second = sink.find(record.intent_id)
    if first != result.reference_id or second != first:
        return False, "find does not return the mirrored reference stably"
    again = sink.mirror(record)
    if again.status is MirrorStatus.MIRRORED and again.reference_id != first:
        return False, "mirroring the same intent twice created a second reference"
    return True, first


def _redact(sink: TrackingSink) -> tuple[bool, str]:
    leaked = []
    for label, probe in REDACTION_PROBES:
        redacted, changed = sink.redact(probe)
        if probe in redacted or not changed:
            leaked.append(label)
    return (not leaked), ("leaked: " + ", ".join(leaked) if leaked else "all removed")


def _redact_idempotent(sink: TrackingSink) -> tuple[bool, str]:
    once, _ = sink.redact(REDACTION_PROBES[0][1])
    twice, changed_again = sink.redact(once)
    if once != twice or changed_again:
        return False, "redaction is not stable under a second pass"
    return True, "stable"


def _attest_matches(sink: TrackingSink) -> tuple[bool, str]:
    record = canonical_record("mmi_0000000000000000000000000C")
    result = sink.mirror(record)
    if result.status is not MirrorStatus.MIRRORED:
        return True, f"not mirrored ({result.status.value}); attest not exercised"
    attestation = sink.attest(result.reference_id)
    if attestation.result is AttestationResult.VERIFIED:
        if attestation.response_sha256 != record.payload_sha256:
            return False, "VERIFIED with a digest that is not the mirrored payload's"
        return True, "verified"
    if attestation.result is AttestationResult.MISMATCH:
        return False, "attest reports MISMATCH for an untouched record"
    return True, attestation.result.value


def _attest_unknown(sink: TrackingSink) -> tuple[bool, str]:
    attestation = sink.attest("ref-that-was-never-mirrored")
    if attestation.result is AttestationResult.VERIFIED:
        return False, "claims VERIFIED for a reference it never stored"
    return True, attestation.result.value


def _attest_mismatch(sink: TrackingSink) -> tuple[bool, str]:
    """A sink that can be tampered with must say so; one that cannot may pass.

    The reference sink exposes ``tamper`` for exactly this check. A production
    sink has no such hook, and the check then only requires that VERIFIED is
    not asserted without a matching digest.
    """
    tamper = getattr(sink, "tamper", None)
    record = canonical_record("mmi_0000000000000000000000000D")
    result = sink.mirror(record)
    if result.status is not MirrorStatus.MIRRORED:
        return True, f"not mirrored ({result.status.value}); mismatch not exercised"
    if not callable(tamper):
        attestation = sink.attest(result.reference_id)
        if attestation.result is AttestationResult.VERIFIED and (
            attestation.response_sha256 != record.payload_sha256
        ):
            return False, "VERIFIED with a foreign digest"
        return True, "no tamper hook; overclaim not observed"
    tamper(result.reference_id)
    attestation = sink.attest(result.reference_id)
    if attestation.result is not AttestationResult.MISMATCH:
        return False, f"tampered record attested {attestation.result.value}"
    return True, "mismatch surfaced"


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)
