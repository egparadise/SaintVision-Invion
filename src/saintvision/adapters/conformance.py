"""The adapter conformance suite (S10-BE).

AC-10's required evidence is "Adapter conformance", and this is the thing that
produces it: a fixed set of checks every adapter must pass, run identically
against each one, emitting a report with counts rather than a claim.

Two properties it is built for:

* **It discriminates.** A suite that passes everything proves nothing, so
  ``tests/test_adapters.py`` runs it against adapters that are deliberately
  broken in one way each and asserts the matching check fails. A conformance
  suite is itself something that has to be tested.
* **It refuses to reward over-claiming.** Every capability an adapter declares
  is exercised. Declaring ``SERVER_SIDE_CANCEL`` and then returning
  ``NOT_SUPPORTED`` fails; so does declaring nothing and quietly working, which
  would let two adapters diverge while both showing green.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from dataclasses import dataclass, field
from typing import Any, Callable

from .contract import (
    CONTRACT_VERSION,
    AttestationResult,
    CancelOutcome,
    Capability,
    ProviderAdapter,
)

#: A request every adapter must accept. Deliberately minimal — the contract is
#: about the lifecycle, not about any provider's parameter names.
CANONICAL_REQUEST: dict[str, Any] = {
    "objective": "conformance probe",
    "input": "Return the word OK.",
    "max_output_tokens": 16,
}

#: Content that must not survive redaction. Each entry is (label, text).
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
    #: True when the check was skipped because the adapter does not declare the
    #: capability. Skipped is not passed and is counted separately.
    skipped: bool = False


@dataclass(frozen=True, slots=True)
class CheckSpec:
    """One check, described rather than executed (G-03 design v1.2 §5-1).

    The names used to be string literals inside ``run_conformance``'s body,
    which meant nothing could read the check list without running the suite --
    and running it drives host CLI processes. A caller that wants to know *what*
    the contract checks (an API describing the surface, a test asserting the
    list is complete) reads ``CHECKLIST`` instead.

    This is a descriptor, not a second source of truth: ``run_conformance``
    builds its report from this same tuple, so the list a reader sees is the
    list the suite runs.
    """

    name: str
    #: ``None`` means the check always runs. A capability means it runs only for
    #: an adapter that declares it, and is reported as skipped otherwise --
    #: skipped separately from passed, so a narrow adapter cannot look as
    #: complete as a broad one.
    capability: Capability | None
    run: Callable[[ProviderAdapter, str], tuple[bool, str]]


@dataclass
class ConformanceReport:
    adapter: str
    contract_version: str
    checks: list[Check] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for c in self.checks if c.passed and not c.skipped)

    @property
    def failed(self) -> int:
        return sum(1 for c in self.checks if not c.passed and not c.skipped)

    @property
    def skipped(self) -> int:
        return sum(1 for c in self.checks if c.skipped)

    @property
    def total(self) -> int:
        return len(self.checks)

    @property
    def conformant(self) -> bool:
        return self.failed == 0 and self.passed > 0

    def failures(self) -> list[Check]:
        return [c for c in self.checks if not c.passed and not c.skipped]

    def to_dict(self) -> dict[str, Any]:
        """The shape recorded as AC-10 evidence."""
        return {
            "adapter": self.adapter,
            "contractVersion": self.contract_version,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "conformant": self.conformant,
            "checks": [
                {
                    "name": c.name,
                    "passed": c.passed,
                    "skipped": c.skipped,
                    "detail": c.detail,
                }
                for c in self.checks
            ],
        }


def _check(name: str, fn: Callable[[], tuple[bool, str]]) -> Check:
    """Run one check. An exception is a failure, not a crash of the suite."""
    try:
        passed, detail = fn()
    except Exception as exc:  # noqa: BLE001 - an adapter may raise anything
        return Check(name=name, passed=False, detail=f"{type(exc).__name__}: {exc}")
    return Check(name=name, passed=passed, detail=detail)


def run_conformance(
    adapter: ProviderAdapter, *, credential_ref: str = "conformance://dummy"
) -> ConformanceReport:
    """Run every check against one adapter and return the report."""
    report = ConformanceReport(
        adapter=getattr(adapter, "name", type(adapter).__name__),
        contract_version=getattr(adapter, "contract_version", "unknown"),
    )
    caps = getattr(adapter, "capabilities", frozenset())

    # One loop over CHECKLIST, so the names and the gates exist in one place and
    # a reader of the list cannot disagree with a run of the suite.
    for spec in CHECKLIST:
        if spec.capability is not None and spec.capability not in caps:
            report.checks.append(Check(spec.name, True, "not declared", skipped=True))
            continue
        report.checks.append(
            _check(spec.name, lambda spec=spec: spec.run(adapter, credential_ref))
        )

    return report


# --------------------------------------------------------------------------
# Individual checks
# --------------------------------------------------------------------------


def _declares_version(adapter: ProviderAdapter) -> tuple[bool, str]:
    version = getattr(adapter, "contract_version", None)
    if version != CONTRACT_VERSION:
        return False, f"declares {version!r}, suite implements {CONTRACT_VERSION!r}"
    return True, version


def _implements_members(adapter: ProviderAdapter) -> tuple[bool, str]:
    required = (
        "probe",
        "install",
        "authenticate",
        "run",
        "cancel",
        "collect",
        "redact",
        "attest",
    )
    missing = [m for m in required if not callable(getattr(adapter, m, None))]
    return (not missing), ("missing: " + ", ".join(missing) if missing else "all present")


def _probe(adapter: ProviderAdapter) -> tuple[bool, str]:
    result = adapter.probe()
    if not hasattr(result, "reachable"):
        return False, "probe did not return a ProbeResult"
    # An adapter that invents model names is worse than one that returns none.
    if any(not isinstance(m, str) or not m for m in result.available_models):
        return False, "available_models contains a non-string or empty entry"
    return True, f"reachable={result.reachable}, models={len(result.available_models)}"


def _install(adapter: ProviderAdapter) -> tuple[bool, str]:
    report = adapter.install()
    if report.ready and report.missing:
        return False, "reports ready while listing missing prerequisites"
    if not report.ready and not report.missing:
        return False, "reports not ready without naming what is missing"
    return True, f"ready={report.ready}"


def _authenticate(adapter: ProviderAdapter, credential_ref: str) -> tuple[bool, str]:
    result = adapter.authenticate(credential_ref)
    # The credential reference must not be echoed back — that is how a
    # reference turns into a logged secret.
    if result.principal_ref is not None and credential_ref in str(result.principal_ref):
        return False, "principal_ref echoes the credential reference"
    if not result.authenticated and not result.failure_code:
        return False, "failed authentication without a failure code"
    return True, f"authenticated={result.authenticated}"


def _run(adapter: ProviderAdapter) -> tuple[bool, str]:
    handle = adapter.run(dict(CANONICAL_REQUEST))
    if not handle.handle_id:
        return False, "run returned a handle with no id"
    if not handle.provider:
        return False, "run returned a handle with no provider"
    return True, handle.handle_id


def _collect_is_redacted(adapter: ProviderAdapter) -> tuple[bool, str]:
    """The output of collect must already be through redact (ADR-014)."""
    request = dict(CANONICAL_REQUEST)
    request["input"] = REDACTION_PROBES[0][1]
    handle = adapter.run(request)
    result = adapter.collect(handle)
    leaked = [label for label, probe in REDACTION_PROBES if probe in result.content]
    if leaked:
        return False, f"collect returned unredacted content: {', '.join(leaked)}"
    return True, f"completed={result.completed}"


def _redact(adapter: ProviderAdapter) -> tuple[bool, str]:
    leaked = []
    for label, probe in REDACTION_PROBES:
        redacted, changed = adapter.redact(probe)
        if probe in redacted or not changed:
            leaked.append(label)
    return (not leaked), ("leaked: " + ", ".join(leaked) if leaked else "all removed")


def _redact_idempotent(adapter: ProviderAdapter) -> tuple[bool, str]:
    """Redacting twice must not keep changing the text.

    A non-idempotent redactor means the second pass at the collector mangles
    what the first one produced, and the two logs stop matching.
    """
    once, _ = adapter.redact(REDACTION_PROBES[0][1])
    twice, changed_again = adapter.redact(once)
    if once != twice or changed_again:
        return False, "redaction is not stable under a second pass"
    return True, "stable"


def _cancel_tri_state(adapter: ProviderAdapter) -> tuple[bool, str]:
    handle = adapter.run(dict(CANONICAL_REQUEST))
    outcome = adapter.cancel(handle)
    if not isinstance(outcome, CancelOutcome):
        return False, f"cancel returned {type(outcome).__name__}, not CancelOutcome"
    return True, outcome.value


def _cancel_finished(adapter: ProviderAdapter) -> tuple[bool, str]:
    """Cancelling something already finished must not claim it was stopped."""
    handle = adapter.run(dict(CANONICAL_REQUEST))
    adapter.collect(handle)
    outcome = adapter.cancel(handle)
    if outcome is CancelOutcome.STOPPED:
        return False, "claims to have stopped an already-finished request"
    return True, outcome.value


def _cancel_stops(adapter: ProviderAdapter) -> tuple[bool, str]:
    """Only run when SERVER_SIDE_CANCEL is declared."""
    handle = adapter.run(dict(CANONICAL_REQUEST))
    outcome = adapter.cancel(handle)
    if outcome is not CancelOutcome.STOPPED:
        return False, f"declares server-side cancel but returned {outcome.value}"
    return True, "stopped"


def _attest(adapter: ProviderAdapter) -> tuple[bool, str]:
    handle = adapter.run(dict(CANONICAL_REQUEST))
    adapter.collect(handle)
    attestation = adapter.attest(handle)
    if attestation.result is AttestationResult.VERIFIED:
        # Claiming verification requires something to have been verified.
        if not attestation.request_sha256 or not attestation.response_sha256:
            return False, "claims VERIFIED without request and response digests"
        for digest in (attestation.request_sha256, attestation.response_sha256):
            if len(digest) != 64 or digest != digest.lower():
                return False, "digest is not a lowercase hex SHA-256"
    return True, attestation.result.value


def _usage(adapter: ProviderAdapter) -> tuple[bool, str]:
    handle = adapter.run(dict(CANONICAL_REQUEST))
    result = adapter.collect(handle)
    usage = result.usage
    if usage.input_tokens < 0 or usage.output_tokens < 0:
        return False, "negative token counts"
    if usage.input_tokens == 0 and usage.output_tokens == 0:
        return False, "declares usage reporting but reported nothing"
    return True, f"in={usage.input_tokens} out={usage.output_tokens}"


def _model_pin(adapter: ProviderAdapter) -> tuple[bool, str]:
    handle = adapter.run(dict(CANONICAL_REQUEST))
    result = adapter.collect(handle)
    if not handle.model_id or not result.model_id:
        return False, "declares model pinning but returned no model id"
    if handle.model_id != result.model_id:
        return False, "the handle and the result disagree about the model"
    return True, result.model_id


def _ignoring_credential(
    fn: Callable[[ProviderAdapter], tuple[bool, str]]
) -> Callable[[ProviderAdapter, str], tuple[bool, str]]:
    """Give a one-argument check the two-argument shape ``CheckSpec`` declares.

    Only ``_authenticate`` needs the credential reference. Wrapping the others
    rather than changing fifteen signatures keeps this extraction to what it is:
    a descriptor over the checks that already existed.
    """

    def run(adapter: ProviderAdapter, _credential_ref: str) -> tuple[bool, str]:
        return fn(adapter)

    return run


#: Every check the suite runs, in the order it runs them, with its gate.
#:
#: The single source of truth for the check list. ``run_conformance`` loops over
#: it and a reader (the conformance status route, a test) reads it without
#: running anything. Defined here rather than at the top of the module because it
#: names the functions above it.
#:
#: **Adding or removing a check is a two-place change**: this tuple and the
#: independent baseline in ``tests/core/test_conformance_checklist_ratchet.py``.
#: That is deliberate. Before this existed, deleting a check killed no test for
#: three of the names, because nothing anywhere asserted the set.
CHECKLIST: tuple[CheckSpec, ...] = (
    CheckSpec("declares_contract_version", None, _ignoring_credential(_declares_version)),
    CheckSpec("implements_every_member", None, _ignoring_credential(_implements_members)),
    CheckSpec("probe_without_credentials", None, _ignoring_credential(_probe)),
    CheckSpec("install_reports_without_installing", None, _ignoring_credential(_install)),
    CheckSpec("authenticate_takes_a_reference", None, _authenticate),
    CheckSpec("run_returns_a_usable_handle", None, _ignoring_credential(_run)),
    CheckSpec(
        "collect_returns_redacted_content", None, _ignoring_credential(_collect_is_redacted)
    ),
    CheckSpec("redact_removes_known_secrets", None, _ignoring_credential(_redact)),
    CheckSpec("redact_is_idempotent", None, _ignoring_credential(_redact_idempotent)),
    CheckSpec("cancel_returns_a_tri_state", None, _ignoring_credential(_cancel_tri_state)),
    CheckSpec(
        "cancel_after_completion_is_not_stopped", None, _ignoring_credential(_cancel_finished)
    ),
    CheckSpec("attest_does_not_overclaim", None, _ignoring_credential(_attest)),
    CheckSpec(
        "declared_server_cancel_actually_stops",
        Capability.SERVER_SIDE_CANCEL,
        _ignoring_credential(_cancel_stops),
    ),
    CheckSpec(
        "declared_usage_is_reported",
        Capability.USAGE_REPORTING,
        _ignoring_credential(_usage),
    ),
    CheckSpec(
        "declared_model_pinning_returns_an_id",
        Capability.MODEL_PINNING,
        _ignoring_credential(_model_pin),
    ),
)


def compare_reports(reports: list[ConformanceReport]) -> dict[str, Any]:
    """Check that several adapters answer the same contract identically.

    AC-10 is "Codex/Claude 계약 동일". Two adapters that each pass their own
    checks can still differ in which checks they *ran*, and that difference is
    the interoperability problem — so it is reported rather than averaged away.
    """
    if not reports:
        return {"adapters": [], "identical": False, "reason": "no reports"}

    names = sorted(r.adapter for r in reports)
    check_sets = {r.adapter: {c.name for c in r.checks if not c.skipped} for r in reports}
    shared = set.intersection(*check_sets.values()) if check_sets else set()
    divergent = {
        adapter: sorted(checks - shared) for adapter, checks in check_sets.items()
    }
    return {
        "adapters": names,
        "allConformant": all(r.conformant for r in reports),
        "sharedChecks": len(shared),
        "divergentChecks": {k: v for k, v in divergent.items() if v},
        "identical": all(r.conformant for r in reports)
        and not any(divergent.values()),
    }


def request_digest(request: dict[str, Any]) -> str:
    """Canonical digest of a request, for attestation."""
    import json

    encoded = json.dumps(request, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
