import argparse
from types import SimpleNamespace

import pytest

from tools import measure_s07_recovery
from tools.measure_s07_recovery import percentile, summarize, validated_config


def config(**changes):
    values = dict(
        nodes=5,
        repetitions=3,
        liveness_timeout_seconds=60.0,
        poll_interval_seconds=0.5,
        max_detection_seconds=61.0,
        target_recovery_success_rate=0.95,
        json_out=__import__("pathlib").Path("result.json"),
        junit_out=__import__("pathlib").Path("result.xml"),
    )
    values.update(changes)
    return argparse.Namespace(**values)


def test_validation_rejects_non_reproducible_or_unsafe_shapes():
    for changes in (
        {"nodes": 2},
        {"repetitions": 101},
        {"poll_interval_seconds": 61.0},
        {"max_detection_seconds": 59.0},
        {"junit_out": __import__("pathlib").Path("result.json")},
    ):
        with pytest.raises(ValueError):
            validated_config(config(**changes))


def test_summary_uses_nearest_rank_and_never_claims_operational_acceptance():
    cfg = validated_config(config())
    cfg["provenance"] = {
        "codeSha": "a" * 40,
        "integrationSha": "a" * 40,
        "integrationInSync": True,
        "workingTreeClean": True,
        "contentClean": True,
        "capturedAtKst": "2026-09-22T23:25:00+09:00",
        "executor": "Codex",
    }
    rounds = [
        {
            "detected": True,
            "detectionDelaySeconds": delay,
            "freshReplacementCandidates": 0,
            "shardsAttempted": 2,
            "shardsRecovered": recovered,
        }
        for delay, recovered in ((60.1, 2), (60.2, 2), (60.9, 1))
    ]
    result = summarize(cfg, rounds)
    assert result["detectionDelaySeconds"] == {
        "min": 60.1,
        "p50": 60.2,
        "p95": 60.9,
        "max": 60.9,
    }
    assert result["syntheticShardRecoverySuccessRate"] == pytest.approx(5 / 6, abs=1e-6)
    assert result["operationalAcceptanceAssessed"] is False
    assert result["acceptanceShapeRequested"] is True
    assert result["codeSha"] == "a" * 40
    assert result["provenance"] == cfg["provenance"]
    assert result["measurementClock"] == "harness-process-wall-clock-utc"
    assert {finding["id"] for finding in result["findings"]} == {
        "F-S07-01",
        "F-S07-02",
        "F-S07-03",
    }
    assert percentile([], 0.95) is None


def test_default_detection_limit_is_timeout_plus_poll_interval():
    result = validated_config(config(max_detection_seconds=None))

    assert result["maxDetectionSeconds"] == 60.5
    assert result["detectionLimitSource"] == "liveness-timeout-plus-poll-default"


def test_failed_rerun_cannot_reuse_stale_evidence(tmp_path, monkeypatch):
    json_out = tmp_path / "stale.json"
    junit_out = tmp_path / "stale.xml"
    json_out.write_text('{"stale":true}', encoding="utf-8")
    junit_out.write_text("<stale/>", encoding="utf-8")
    monkeypatch.setattr(
        measure_s07_recovery.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0),
    )
    monkeypatch.setattr(
        measure_s07_recovery,
        "measurement_provenance",
        lambda: {"codeSha": "a" * 40},
    )

    result = measure_s07_recovery.main(
        [
            "--nodes",
            "3",
            "--repetitions",
            "1",
            "--liveness-timeout-seconds",
            "1",
            "--max-detection-seconds",
            "1",
            "--json-out",
            str(json_out),
            "--junit-out",
            str(junit_out),
        ]
    )

    assert result == 2
    assert not json_out.exists()
    assert not junit_out.exists()
