"""The adapter contract and its conformance suite (S10-BE).

Half of this file tests the suite rather than an adapter. A conformance suite
that passes everything proves nothing, so each deliberately-broken adapter
below must fail the specific check that covers its defect — and only that one.
"""

from __future__ import annotations

import pytest

from saintvision.adapters.conformance import (
    CANONICAL_REQUEST,
    REDACTION_PROBES,
    compare_reports,
    run_conformance,
)
from saintvision.adapters.contract import (
    CONTRACT_VERSION,
    AttestationResult,
    CancelOutcome,
    Capability,
    ProviderAdapter,
)
from saintvision.adapters.reference import ReferenceAdapter, redact_text


def failing_check(report, name):
    return next(c for c in report.checks if c.name == name)


# --------------------------------------------------------------------------
# The reference adapter conforms
# --------------------------------------------------------------------------


def test_the_reference_adapter_is_conformant():
    report = run_conformance(ReferenceAdapter())
    assert report.conformant, [c.name for c in report.failures()]
    assert report.failed == 0
    assert report.passed >= 12


def test_the_reference_adapter_satisfies_the_protocol():
    assert isinstance(ReferenceAdapter(), ProviderAdapter)


def test_the_report_serialises_for_evidence():
    body = run_conformance(ReferenceAdapter()).to_dict()
    for field in ("adapter", "contractVersion", "total", "passed", "failed", "skipped"):
        assert field in body
    assert body["contractVersion"] == CONTRACT_VERSION
    # Skipped is reported separately, so a narrow adapter cannot pass itself off
    # as a complete one.
    assert body["skipped"] >= 1


# --------------------------------------------------------------------------
# Redaction
# --------------------------------------------------------------------------


@pytest.mark.parametrize("label,probe", REDACTION_PROBES, ids=[p[0] for p in REDACTION_PROBES])
def test_known_secret_shapes_are_removed(label, probe):
    redacted, changed = redact_text(probe)
    assert changed
    assert probe not in redacted


def test_redaction_is_idempotent():
    once, _ = redact_text(REDACTION_PROBES[1][1])
    twice, changed = redact_text(once)
    assert once == twice
    assert not changed


def test_redaction_leaves_ordinary_text_alone():
    text = "The build finished in 42 seconds with 3 warnings."
    redacted, changed = redact_text(text)
    assert redacted == text
    assert not changed


def test_a_multiline_private_key_is_removed_whole():
    content = "before\n-----BEGIN PRIVATE KEY-----\nMIIBpayload\n-----END PRIVATE KEY-----\nafter"
    redacted, _ = redact_text(content)
    assert "MIIBpayload" not in redacted
    assert redacted.startswith("before")
    assert redacted.endswith("after")


# --------------------------------------------------------------------------
# The suite must discriminate: one broken adapter per check
# --------------------------------------------------------------------------


class LeakyAdapter(ReferenceAdapter):
    """Returns raw content from collect, skipping redaction."""

    name = "leaky"

    def redact(self, content):  # noqa: D102
        return content, False


def test_a_leaky_adapter_fails_redaction_checks():
    report = run_conformance(LeakyAdapter())
    assert not report.conformant
    failed = {c.name for c in report.failures()}
    assert "redact_removes_known_secrets" in failed
    assert "collect_returns_redacted_content" in failed


class OverClaimingCancelAdapter(ReferenceAdapter):
    """Declares server-side cancel it does not have."""

    name = "over-claiming-cancel"
    capabilities = frozenset({Capability.SERVER_SIDE_CANCEL})


def test_declaring_a_capability_you_lack_fails():
    report = run_conformance(OverClaimingCancelAdapter())
    assert not report.conformant
    assert "declared_server_cancel_actually_stops" in {c.name for c in report.failures()}


class LyingCancelAdapter(ReferenceAdapter):
    """Claims it stopped a request that had already finished."""

    name = "lying-cancel"

    def cancel(self, handle):  # noqa: D102
        return CancelOutcome.STOPPED


def test_claiming_to_stop_a_finished_request_fails():
    report = run_conformance(LyingCancelAdapter())
    assert "cancel_after_completion_is_not_stopped" in {
        c.name for c in report.failures()
    }


class BooleanCancelAdapter(ReferenceAdapter):
    """Returns a boolean, losing the difference between not-stopped and unknown."""

    name = "boolean-cancel"

    def cancel(self, handle):  # noqa: D102
        return False


def test_a_boolean_cancel_fails_the_tri_state_check():
    report = run_conformance(BooleanCancelAdapter())
    assert "cancel_returns_a_tri_state" in {c.name for c in report.failures()}


class OverClaimingAttestAdapter(ReferenceAdapter):
    """Reports VERIFIED with nothing verified."""

    name = "over-claiming-attest"

    def attest(self, handle):  # noqa: D102
        from saintvision.adapters.contract import Attestation

        return Attestation(result=AttestationResult.VERIFIED)


def test_attesting_without_digests_fails():
    report = run_conformance(OverClaimingAttestAdapter())
    assert "attest_does_not_overclaim" in {c.name for c in report.failures()}


class UnverifiableAttestAdapter(ReferenceAdapter):
    """Honestly reports that it cannot verify. That is conformant."""

    name = "unverifiable-attest"

    def attest(self, handle):  # noqa: D102
        from saintvision.adapters.contract import Attestation

        return Attestation(
            result=AttestationResult.UNVERIFIABLE, detail="provider exposes nothing"
        )


def test_admitting_you_cannot_verify_is_conformant():
    """UNVERIFIABLE is a real answer; only claiming VERIFIED falsely is not."""
    report = run_conformance(UnverifiableAttestAdapter())
    assert report.conformant, [c.name for c in report.failures()]


class EchoingAuthAdapter(ReferenceAdapter):
    """Puts the credential reference into the principal handle."""

    name = "echoing-auth"

    def authenticate(self, credential_ref):  # noqa: D102
        from saintvision.adapters.contract import AuthResult

        return AuthResult(authenticated=True, principal_ref=credential_ref)


def test_echoing_the_credential_reference_fails():
    report = run_conformance(EchoingAuthAdapter())
    assert "authenticate_takes_a_reference" in {c.name for c in report.failures()}


class SilentFailureAdapter(ReferenceAdapter):
    """Fails authentication without saying why."""

    name = "silent-failure"

    def authenticate(self, credential_ref):  # noqa: D102
        from saintvision.adapters.contract import AuthResult

        return AuthResult(authenticated=False)


def test_failing_without_a_code_fails():
    report = run_conformance(SilentFailureAdapter())
    assert "authenticate_takes_a_reference" in {c.name for c in report.failures()}


class WrongVersionAdapter(ReferenceAdapter):
    name = "wrong-version"
    contract_version = "0.9.0"


def test_a_stale_contract_version_fails():
    report = run_conformance(WrongVersionAdapter())
    assert "declares_contract_version" in {c.name for c in report.failures()}


class RaisingAdapter(ReferenceAdapter):
    """Raises instead of returning. The suite must record it, not crash."""

    name = "raising"

    def probe(self):  # noqa: D102
        raise RuntimeError("provider exploded")


def test_an_adapter_that_raises_is_recorded_as_a_failure():
    report = run_conformance(RaisingAdapter())
    check = failing_check(report, "probe_without_credentials")
    assert not check.passed
    assert "RuntimeError" in check.detail
    # The rest of the suite still ran.
    assert report.total > 5


class InstallLiarAdapter(ReferenceAdapter):
    """Says it is ready while listing missing prerequisites."""

    name = "install-liar"

    def install(self):  # noqa: D102
        from saintvision.adapters.contract import InstallReport

        return InstallReport(ready=True, missing=("docker",))


def test_contradictory_install_report_fails():
    report = run_conformance(InstallLiarAdapter())
    assert "install_reports_without_installing" in {c.name for c in report.failures()}


class NoUsageAdapter(ReferenceAdapter):
    """Declares usage reporting and reports zeros."""

    name = "no-usage"
    capabilities = frozenset({Capability.USAGE_REPORTING})

    def collect(self, handle):  # noqa: D102
        from saintvision.adapters.contract import CollectResult, Usage

        return CollectResult(completed=True, content="ok", usage=Usage())


def test_declared_usage_reporting_must_report_something():
    report = run_conformance(NoUsageAdapter())
    assert "declared_usage_is_reported" in {c.name for c in report.failures()}


class DisagreeingModelAdapter(ReferenceAdapter):
    """The handle and the result name different models."""

    name = "disagreeing-model"
    capabilities = frozenset({Capability.MODEL_PINNING})

    def collect(self, handle):  # noqa: D102
        result = super().collect(handle)
        from dataclasses import replace

        return replace(result, model_id="something-else")


def test_the_handle_and_result_must_agree_on_the_model():
    report = run_conformance(DisagreeingModelAdapter())
    assert "declared_model_pinning_returns_an_id" in {c.name for c in report.failures()}


# --------------------------------------------------------------------------
# AC-10: two adapters, one contract
# --------------------------------------------------------------------------


class SecondReferenceAdapter(ReferenceAdapter):
    """A structurally different adapter with the same declared capabilities."""

    name = "reference-b"
    MODEL_ID = "reference-null-2"


def test_two_conformant_adapters_answer_the_same_contract():
    """AC-10's "Codex/Claude 계약 동일", expressed as a check.

    Both passing is not enough — they must also have run the same checks. An
    adapter that skips a check its counterpart ran is where interoperability
    quietly breaks.
    """
    reports = [run_conformance(ReferenceAdapter()), run_conformance(SecondReferenceAdapter())]
    comparison = compare_reports(reports)
    assert comparison["allConformant"]
    assert comparison["identical"]
    assert comparison["divergentChecks"] == {}
    assert comparison["adapters"] == ["reference", "reference-b"]


def test_a_capability_difference_shows_up_as_divergence():
    class BroaderAdapter(ReferenceAdapter):
        name = "broader"
        capabilities = frozenset(
            {Capability.USAGE_REPORTING, Capability.MODEL_PINNING, Capability.SERVER_SIDE_CANCEL}
        )

        def cancel(self, handle):
            state = self._runs.get(handle.handle_id)
            if state is None:
                return CancelOutcome.UNKNOWN
            if state["finished"]:
                return CancelOutcome.ALREADY_FINISHED
            state["cancelled"] = True
            return CancelOutcome.STOPPED

    reports = [run_conformance(ReferenceAdapter()), run_conformance(BroaderAdapter())]
    comparison = compare_reports(reports)
    assert comparison["allConformant"]
    # Both pass, but they are not interchangeable, and the report says so.
    assert not comparison["identical"]
    assert comparison["divergentChecks"]["broader"] == [
        "declared_server_cancel_actually_stops"
    ]


def test_comparing_nothing_is_not_a_pass():
    assert compare_reports([])["identical"] is False


def test_the_canonical_request_is_provider_neutral():
    """No provider-specific parameter names in the shared request.

    The moment the canonical request carries one vendor's field names, the
    other adapter is translating rather than conforming.
    """
    vendor_fields = {
        "model", "messages", "system", "max_tokens", "thinking", "temperature",
        "prompt", "stop_sequences", "tools", "tool_choice",
    }
    assert not (set(CANONICAL_REQUEST) & vendor_fields)
