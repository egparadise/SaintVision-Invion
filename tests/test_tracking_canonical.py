"""PG-free: canonical payload, tracking URI, the TRACK code table and readiness.

Design PR #168 v1.3 §2.1, §2.2, §4, §5. Each determinism claim is a test with
its negative beside it, because a canonicalisation that cannot refuse anything
would also never notice a mismatch.
"""

from __future__ import annotations

import decimal
import unicodedata

import pytest

from saintvision.tracking import canonical, codes, config
from saintvision.tracking.canonical import (
    CanonicalizationError,
    UriError,
    canonical_bytes,
    normalize_tracking_uri,
    payload_sha256,
    tracking_uri_sha256,
)
from saintvision.tracking.codes import MirrorStatus, Verdict


# ---------------------------------------------------------------- §2.1 determinism


def test_key_order_does_not_change_the_digest():
    assert payload_sha256({"b": 1, "a": {"y": 2, "x": 3}}) == payload_sha256({"a": {"x": 3, "y": 2}, "b": 1})


def test_nfd_and_nfc_agree_for_keys_values_and_nested_values():
    nfc = "é"
    nfd = unicodedata.normalize("NFD", nfc)
    assert nfc != nfd
    assert payload_sha256({nfc: nfc, "n": {nfc: [nfc]}}) == payload_sha256({nfd: nfd, "n": {nfd: [nfd]}})


def test_keys_that_collide_after_nfc_are_refused():
    nfc = "é"
    nfd = unicodedata.normalize("NFD", nfc)
    with pytest.raises(CanonicalizationError) as exc:
        payload_sha256({nfc: 1, nfd: 2})
    assert exc.value.reason_class == "key-collision"


@pytest.mark.parametrize("left,right", [(1.0, 1), (-0.0, 0), (1e3, 1000), (2.0**53, 2**53)])
def test_integral_floats_canonicalize_to_integers(left, right):
    assert payload_sha256({"v": left}) == payload_sha256({"v": right})
    assert canonical_bytes({"v": left}) == canonical_bytes({"v": right})


def test_large_integers_stay_exact_and_never_pass_through_float():
    big = 2**53 + 1
    assert canonical_bytes({"v": big}) == b'{"v":%d}' % big
    assert payload_sha256({"v": big}) != payload_sha256({"v": float(big)})


def test_bool_is_not_a_number():
    assert payload_sha256({"v": True}) != payload_sha256({"v": 1})
    assert canonical_bytes({"v": True}) == b'{"v":true}'


def test_non_integral_floats_use_repr():
    assert canonical_bytes({"v": 0.1}) == b'{"v":"0.1"}'
    assert canonical_bytes({"v": 1e-7}) == b'{"v":"1e-07"}'


def test_none_drops_the_field_but_none_in_a_list_is_refused():
    assert canonical_bytes({"a": None, "b": 1}) == b'{"b":1}'
    with pytest.raises(CanonicalizationError) as exc:
        canonical_bytes({"a": [1, None]})
    assert exc.value.reason_class == "list-null"


@pytest.mark.parametrize(
    "value,reason",
    [
        (float("nan"), "nan-or-infinity"),
        (float("inf"), "nan-or-infinity"),
        (float("-inf"), "nan-or-infinity"),
        (decimal.Decimal("1.5"), "unsupported-type"),
        (b"bytes", "unsupported-type"),
    ],
)
def test_unrepresentable_values_are_refused_with_a_reason_class(value, reason):
    with pytest.raises(CanonicalizationError) as exc:
        payload_sha256({"v": value})
    assert exc.value.reason_class == reason
    assert reason in canonical.REASON_CLASSES


def test_non_string_dict_keys_are_refused():
    with pytest.raises(CanonicalizationError) as exc:
        payload_sha256({1: "a"})
    assert exc.value.reason_class == "unsupported-type"


def test_metric_order_does_not_change_the_digest_and_step_defaults_to_zero():
    a = {"metrics": [{"key": "b", "value": 1, "timestamp_ms": 5}, {"key": "a", "value": 2.0, "step": 1, "timestamp_ms": 5}]}
    b = {"metrics": [{"key": "a", "value": 2, "step": 1, "timestamp_ms": 5}, {"key": "b", "value": 1, "step": 0, "timestamp_ms": 5}]}
    assert payload_sha256(a) == payload_sha256(b)


@pytest.mark.parametrize(
    "metric",
    [{"key": "a"}, {"value": 1}, {"key": 1, "value": 1}, {"key": "a", "value": 1, "step": 1.5},
     {"key": "a", "value": True}, {"key": "a", "value": "x"}, "not-a-dict"],
)
def test_malformed_metrics_are_refused(metric):
    with pytest.raises(CanonicalizationError):
        payload_sha256({"metrics": [metric]})


def test_tags_must_be_string_to_string():
    with pytest.raises(CanonicalizationError) as exc:
        payload_sha256({"tags": {"k": 1}})
    assert exc.value.reason_class == "non-string-tag"
    with pytest.raises(CanonicalizationError):
        payload_sha256({"tags": ["k"]})


def test_canonical_bytes_are_compact_sorted_utf8_json():
    assert canonical_bytes({"z": "é", "a": [1, "b"]}) == '{"a":[1,"b"],"z":"é"}'.encode("utf-8")


def test_canonicalization_is_idempotent_including_non_integral_float_metrics():
    """hosted 36375872884: the hook canonicalises, then hashes the canonical form again."""
    payload = {
        "params": {"x": 0.1, "n": 2.0},
        "tags": {"k": "v"},
        "metrics": [{"key": "category.a.mean_score", "value": 0.9, "step": 0, "timestamp_ms": 5},
                    {"key": "rate", "value": 1.0, "step": 0, "timestamp_ms": 5}],
    }
    once = canonical.canonical_payload(payload)
    assert once["metrics"][0]["value"] == "0.9" and once["metrics"][1]["value"] == 1
    twice = canonical.canonical_payload(once)
    assert twice == once
    assert payload_sha256(once) == payload_sha256(payload) == payload_sha256(twice)
    # Only a float's exact repr is accepted back; any other string is not numeric.
    for bad in ("0.90", " 0.9", "abc", "1e3", "nan", "inf"):
        with pytest.raises(CanonicalizationError):
            canonical.canonical_payload({"metrics": [{"key": "m", "value": bad}]})


def test_the_pair_predicate_is_null_safe():
    """A failure status with a NULL code must fail the CHECK, not pass through NULL."""
    predicate = codes.sql_pair_check()
    assert "IS NOT DISTINCT FROM 'TRACK-0001'" in predicate
    assert "error_code = 'TRACK" not in predicate


def test_canonicalize_does_not_mutate_its_input():
    payload = {"b": {"y": None, "x": 1.0}, "a": [1]}
    before = repr(payload)
    canonical.canonical_payload(payload)
    assert repr(payload) == before


# ---------------------------------------------------------------- §2.2 URI


def test_equivalent_uris_share_a_digest():
    assert normalize_tracking_uri("HTTPS://Host.Example:443/mlflow/") == "https://host.example/mlflow"
    assert tracking_uri_sha256("HTTPS://Host.Example:443/mlflow/") == tracking_uri_sha256("https://host.example/mlflow")
    assert normalize_tracking_uri("https://host.example/") == "https://host.example"


@pytest.mark.parametrize(
    "left,right",
    [
        ("https://host.example/mlflow", "https://host.example/other"),
        ("https://host.example/mlflow", "https://host.example:8443/mlflow"),
        ("https://host.example/mlflow", "https://other.example/mlflow"),
    ],
)
def test_different_uris_have_different_digests(left, right):
    assert tracking_uri_sha256(left) != tracking_uri_sha256(right)


@pytest.mark.parametrize(
    "uri",
    ["http://host.example/mlflow", "https://user:pw@host.example/", "https://host.example/?x=1",
     "https://host.example/#frag", "", "https:///path", "ftp://host.example/"],
)
def test_unacceptable_uris_are_refused(uri):
    with pytest.raises(UriError):
        normalize_tracking_uri(uri)


# ---------------------------------------------------------------- §5 codes


def test_the_track_table_is_fixed():
    table = {c.code: (c.status, c.retryable, c.mirror_status, c.verdict) for c in codes.TRACK_CODES}
    assert table == {
        "TRACK-0001": (503, True, MirrorStatus.UNAVAILABLE, Verdict.NOT_OBSERVED),
        "TRACK-0002": (403, False, MirrorStatus.REFUSED, Verdict.MEASURED_FAIL),
        "TRACK-0003": (409, False, MirrorStatus.MISMATCH, Verdict.MEASURED_FAIL),
        "TRACK-0004": (422, False, None, Verdict.INVALID_RUN),
        "TRACK-0005": (422, False, None, Verdict.INVALID_RUN),
    }
    for code in codes.TRACK_CODES:
        assert codes.CANONICAL_CODE.match(code.code)
        assert code.category == "TRACK"


@pytest.mark.parametrize("bad", ["TRACK-MLFLOW-UNAVAILABLE", "track-0001", "TRACK-001", "TRACK-00010", "VAL-0001", "TRACK-0009"])
def test_old_lowercase_short_and_unknown_codes_are_refused(bad):
    with pytest.raises(ValueError):
        codes.entry(bad)


def test_track_code_construction_refuses_non_canonical_shapes():
    with pytest.raises(ValueError):
        codes.TrackCode("TRACK-MLFLOW", 503, True, None, Verdict.NOT_OBSERVED, "x")
    with pytest.raises(ValueError):
        codes.TrackCode("TRACK-0001", 200, True, None, Verdict.NOT_OBSERVED, "x")


def test_verdict_for_attempt_follows_the_table_and_refuses_inconsistent_rows():
    assert codes.verdict_for_attempt("mirrored", None) is Verdict.MIRRORED
    assert codes.verdict_for_attempt("unavailable", "TRACK-0001") is Verdict.NOT_OBSERVED
    assert codes.verdict_for_attempt("refused", "TRACK-0002") is Verdict.MEASURED_FAIL
    assert codes.verdict_for_attempt("mismatch", "TRACK-0003") is Verdict.MEASURED_FAIL
    with pytest.raises(ValueError):
        codes.verdict_for_attempt("mirrored", "TRACK-0001")
    with pytest.raises(ValueError):
        codes.verdict_for_attempt("unavailable", None)


ALL_CODES = ("TRACK-0001", "TRACK-0002", "TRACK-0003", "TRACK-0004", "TRACK-0005", None)


@pytest.mark.parametrize("status", list(MirrorStatus))
@pytest.mark.parametrize("code", ALL_CODES)
def test_every_wrong_status_code_pair_is_refused_and_every_right_one_accepted(status, code):
    """Codex #172 finding 2: a refusal must never be readable as 'unavailable'."""
    expected = codes.STATUS_CODE_PAIRS[status]
    if code == expected:
        assert codes.check_pair(status, code) is status
        codes.verdict_for_attempt(status.value, code)
    else:
        with pytest.raises(ValueError):
            codes.check_pair(status, code)
        with pytest.raises(ValueError):
            codes.verdict_for_attempt(status.value, code)


def test_there_is_no_invalid_attempt_status_and_0004_0005_have_no_attempt():
    assert [s.value for s in MirrorStatus] == ["mirrored", "unavailable", "refused", "mismatch"]
    assert codes.entry("TRACK-0004").mirror_status is None
    assert codes.entry("TRACK-0005").mirror_status is None
    assert set(codes.STATUS_CODE_PAIRS.values()) == {None, "TRACK-0001", "TRACK-0002", "TRACK-0003"}


def test_the_migration_states_the_same_pairs_as_the_live_table():
    """0049 pins the predicate literally; it must equal the generated one."""
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "migrations" / "versions" / "0049_mlflow_mirror.py"
    spec = importlib.util.spec_from_file_location("rev0049", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.STATUS_CODE_PAIR == codes.sql_pair_check()
    assert tuple(module.ATTEMPT_STATUSES) == tuple(s.value for s in MirrorStatus)


def test_verdict_for_unattempted_changes():
    v = codes.verdict_for_unattempted
    assert v(configured="absent", has_intent=False, has_defect=False) is Verdict.NOT_OBSERVED
    assert v(configured="invalid", has_intent=False, has_defect=False) is Verdict.INVALID_RUN
    assert v(configured="configured", has_intent=True, has_defect=False) is Verdict.NOT_OBSERVED   # pending
    assert v(configured="configured", has_intent=False, has_defect=True) is Verdict.INVALID_RUN
    assert v(configured="configured", has_intent=False, has_defect=False) is Verdict.INVALID_RUN   # enqueue defect
    with pytest.raises(ValueError):
        v(configured="maybe", has_intent=False, has_defect=False)


def test_terminal_statuses():
    assert not MirrorStatus.UNAVAILABLE.terminal
    assert all(s.terminal for s in MirrorStatus if s is not MirrorStatus.UNAVAILABLE)
    assert codes.code_for_status(MirrorStatus.MIRRORED) is None
    assert codes.code_for_status(MirrorStatus.REFUSED) == "TRACK-0002"


# ---------------------------------------------------------------- §4 readiness


GOOD = {
    "INV_MLFLOW_TRACKING_URI": "https://Host.Example:443/mlflow/",
    "INV_MLFLOW_DESTINATION": "lab-mlflow",
    "INV_MLFLOW_EXPERIMENT_PREFIX": "inv",
}


def test_absent_requires_every_variable_unset():
    assert config.resolve({}).readiness.value == "absent"
    assert config.resolve({"INV_MLFLOW_TRACKING_URI": "  "}).readiness.value == "absent"
    partial = config.resolve({"INV_MLFLOW_DESTINATION": "lab"})
    assert (partial.readiness.value, partial.readiness.detail) == ("invalid", "partial")


def test_configured_normalises_the_uri_and_binds_its_digest():
    resolved = config.resolve(GOOD, client_present=lambda: True)
    assert resolved.readiness.configured and resolved.settings is not None
    assert resolved.settings.tracking_uri == "https://host.example/mlflow"
    assert resolved.settings.tracking_uri_sha256 == tracking_uri_sha256("https://host.example/mlflow")
    assert resolved.settings.timeout_seconds == 5


@pytest.mark.parametrize(
    "override,detail",
    [
        ({"INV_MLFLOW_TRACKING_URI": "http://host.example/"}, "uri:https"),
        ({"INV_MLFLOW_TRACKING_URI": "https://u:p@host.example/"}, "uri:userinfo"),
        ({"INV_MLFLOW_TRACKING_URI": "https://host.example/?a=1"}, "uri:query"),
        ({"INV_MLFLOW_DESTINATION": "Lab"}, "destination"),
        ({"INV_MLFLOW_DESTINATION": ""}, "destination"),
        ({"INV_MLFLOW_EXPERIMENT_PREFIX": "Inv/x"}, "prefix"),
        ({"INV_MLFLOW_TIMEOUT_SECONDS": "0"}, "timeout"),
        ({"INV_MLFLOW_TIMEOUT_SECONDS": "five"}, "timeout"),
    ],
)
def test_invalid_configuration_is_track_0004_with_a_detail(override, detail):
    resolved = config.resolve({**GOOD, **override}, client_present=lambda: True)
    assert resolved.readiness.value == "invalid"
    assert resolved.readiness.detail == detail
    assert resolved.readiness.error_code == "TRACK-0004"
    assert resolved.settings is None


def test_configured_uri_without_the_client_is_invalid_not_absent():
    resolved = config.resolve(GOOD, client_present=lambda: False)
    assert resolved.readiness.to_dict() == {"value": "invalid", "detail": "client-missing", "errorCode": "TRACK-0004"}


def test_readiness_shape_is_consistent():
    with pytest.raises(ValueError):
        config.TrackingReadiness("invalid")                       # invalid needs a detail
    with pytest.raises(ValueError):
        config.TrackingReadiness("absent", detail="x")
    with pytest.raises(ValueError):
        config.TrackingReadiness("invalid", detail="x", error_code="TRACK-0001")
