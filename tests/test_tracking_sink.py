"""PG-free: the tracking sink contract, its conformance suite, and the reference sink.

As with ``test_adapters.py``, half of this file tests the suite: each sink
below is broken in exactly one way and must fail the check that names it.
"""

from __future__ import annotations

import dataclasses

import pytest

from saintvision.adapters.contract import Attestation, AttestationResult, AuthResult
from saintvision.adapters.tracking import (
    TRACKING_CONTRACT_VERSION,
    MirrorRecord,
    MirrorResult,
    TrackingSink,
    canonical_record,
    run_tracking_conformance,
)
from saintvision.adapters.tracking_reference import ReferenceSink
from saintvision.tracking.canonical import payload_sha256
from saintvision.tracking.codes import MirrorStatus


def failing(report, name):
    return next(c for c in report.checks if c.name == name)


def test_the_reference_sink_is_conformant_and_satisfies_the_protocol():
    sink = ReferenceSink()
    report = run_tracking_conformance(sink)
    assert report.conformant, [(c.name, c.detail) for c in report.failures()]
    assert report.failed == 0 and report.passed == 12
    assert isinstance(sink, TrackingSink)
    assert report.to_dict()["contractVersion"] == TRACKING_CONTRACT_VERSION


# ---------------------------------------------------------------- the suite discriminates


class _AlwaysVerified(ReferenceSink):
    def attest(self, reference_id):  # noqa: D401
        return Attestation(result=AttestationResult.VERIFIED, request_sha256="a" * 64, response_sha256="a" * 64)


def test_a_sink_that_always_attests_verified_fails():
    report = run_tracking_conformance(_AlwaysVerified())
    assert not failing(report, "attest_does_not_overclaim").passed
    assert not failing(report, "attest_matches_what_was_mirrored").passed
    assert not failing(report, "attest_surfaces_mismatch").passed


class _EchoesHandle(ReferenceSink):
    def authenticate(self, secret_handle):
        return AuthResult(authenticated=True, principal_ref=f"principal:{secret_handle}")


def test_a_sink_that_echoes_the_secret_handle_fails():
    report = run_tracking_conformance(_EchoesHandle(), secret_handle="file:///run/secrets/x.secret")
    assert not failing(report, "authenticate_does_not_echo_the_handle").passed
    assert failing(report, "mirror_returns_a_coded_result").passed


class _Forgetful(ReferenceSink):
    def find(self, intent_id):
        return None


def test_a_sink_that_cannot_find_what_it_mirrored_fails():
    report = run_tracking_conformance(_Forgetful())
    assert not failing(report, "find_is_idempotent_after_mirror").passed


class _Duplicating(ReferenceSink):
    """Creates a fresh remote run on every mirror call, even for a known intent."""

    def mirror(self, record):
        result = super().mirror(record)
        fresh = f"{result.reference_id}-{self.calls['mirror']}"
        self._records[fresh] = self._records[result.reference_id]
        self._by_intent[record.intent_id] = fresh
        return MirrorResult(MirrorStatus.MIRRORED, reference_id=fresh,
                            response_payload_sha256=result.response_payload_sha256)


def test_a_sink_that_creates_a_second_run_for_the_same_intent_fails():
    report = run_tracking_conformance(_Duplicating())
    assert not failing(report, "find_is_idempotent_after_mirror").passed


class _NoRedaction(ReferenceSink):
    def redact(self, content):
        return content, False


def test_a_sink_that_does_not_redact_fails():
    report = run_tracking_conformance(_NoRedaction())
    assert not failing(report, "redact_removes_known_secrets").passed


def test_a_sink_with_another_contract_version_fails():
    report = run_tracking_conformance(ReferenceSink(contract_version="0.9.0"))
    assert not failing(report, "declares_contract_version").passed


class _Raises(ReferenceSink):
    def probe(self):
        raise RuntimeError("boom")


def test_an_exception_is_a_failed_check_not_a_crashed_suite():
    report = run_tracking_conformance(_Raises())
    check = failing(report, "probe_without_credentials")
    assert not check.passed and "RuntimeError" in check.detail


# ---------------------------------------------------------------- reference sink behaviour


def test_injected_faults_are_coded_and_bounded():
    sink = ReferenceSink()
    sink.fail_with(MirrorStatus.UNAVAILABLE, times=1)
    first = sink.mirror(canonical_record("mmi_0000000000000000000000000E"))
    assert (first.status, first.error_code, first.reference_id) == (MirrorStatus.UNAVAILABLE, "TRACK-0001", None)
    second = sink.mirror(canonical_record("mmi_0000000000000000000000000E"))
    assert second.status is MirrorStatus.MIRRORED and second.reference_id
    sink.fail_with(MirrorStatus.REFUSED)
    assert sink.mirror(canonical_record("mmi_0000000000000000000000000F")).error_code == "TRACK-0002"
    with pytest.raises(ValueError):
        sink.fail_with(MirrorStatus.MIRRORED)


def test_tamper_surfaces_a_mismatch_and_attest_binds_the_payload_digest():
    sink = ReferenceSink()
    record = canonical_record("mmi_0000000000000000000000000G")
    result = sink.mirror(record)
    good = sink.attest(result.reference_id)
    assert good.result is AttestationResult.VERIFIED and good.response_sha256 == record.payload_sha256
    sink.tamper(result.reference_id)
    bad = sink.attest(result.reference_id)
    assert bad.result is AttestationResult.MISMATCH and bad.response_sha256 != record.payload_sha256
    assert sink.attest("never").result is AttestationResult.UNVERIFIABLE
    with pytest.raises(KeyError):
        sink.tamper("never")


def test_authenticate_never_returns_the_handle():
    result = ReferenceSink().authenticate("file:///run/secrets/abc.secret")
    assert result.authenticated and "secret" not in (result.principal_ref or "")
    assert ReferenceSink().authenticate(None).failure_code == "TRACK-0002"


# ---------------------------------------------------------------- record and result shapes


def test_mirror_record_binds_its_digest_and_kind():
    payload = {"tags": {"a": "b"}}
    MirrorRecord("mmi_x", "model_version", "p/t/prj", payload, payload_sha256(payload))
    with pytest.raises(ValueError):
        MirrorRecord("mmi_x", "model_version", "p/t/prj", payload, "0" * 64)
    with pytest.raises(ValueError):
        MirrorRecord("mmi_x", "experiment_run", "p/t/prj", payload, payload_sha256(payload))


def test_mirror_result_is_consistent():
    MirrorResult(MirrorStatus.MIRRORED, reference_id="r")
    MirrorResult(MirrorStatus.UNAVAILABLE, error_code="TRACK-0001")
    MirrorResult(MirrorStatus.REFUSED, error_code="TRACK-0002")
    MirrorResult(MirrorStatus.MISMATCH, error_code="TRACK-0003")
    with pytest.raises(ValueError):
        MirrorResult(MirrorStatus.MIRRORED)                                      # no reference
    with pytest.raises(ValueError):
        MirrorResult(MirrorStatus.MIRRORED, reference_id="r", error_code="TRACK-0001")
    with pytest.raises(ValueError):
        MirrorResult(MirrorStatus.REFUSED)                                       # no code
    with pytest.raises(ValueError):
        MirrorResult(MirrorStatus.REFUSED, error_code="TRACK-MLFLOW-REFUSED")   # old shape
    assert dataclasses.is_dataclass(MirrorResult)


@pytest.mark.parametrize(
    "status,code",
    [
        (MirrorStatus.REFUSED, "TRACK-0001"),       # Codex #172 finding 2: the exact counter-example
        (MirrorStatus.UNAVAILABLE, "TRACK-0002"),
        (MirrorStatus.MISMATCH, "TRACK-0001"),
        (MirrorStatus.UNAVAILABLE, "TRACK-0004"),
        (MirrorStatus.REFUSED, "TRACK-0005"),
        (MirrorStatus.MISMATCH, None),
    ],
)
def test_a_wrong_status_code_pair_cannot_be_constructed(status, code):
    with pytest.raises(ValueError):
        MirrorResult(status, error_code=code)
