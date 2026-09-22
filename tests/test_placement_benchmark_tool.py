from pathlib import Path

import pytest

from tools.placement_benchmark import (
    RoundEvidence,
    percentile_nearest_rank,
    run_round,
    summarize,
    write_junit,
)


def test_nearest_rank_p95_is_reproducible():
    assert percentile_nearest_rank(list(range(1, 51)), 0.95) == 48
    with pytest.raises(ValueError):
        percentile_nearest_rank([], 0.95)


def test_junit_writer_exposes_scope_and_invariants(tmp_path: Path):
    report = {
        "scope": "preliminary",
        "requestCount": 50,
        "concurrency": 50,
        "p95SuccessfulMsWorstRound": 123.4,
        "benchmarkComplete": True,
        "deterministicExplainAndSnapshot": True,
        "snapshotIdStableOnIdempotentReplay": True,
        "uniqueFencingTokens": True,
        "noOverbooking": True,
        "fiveNodeAC05": "not_evaluated",
    }
    output = tmp_path / "benchmark.xml"
    write_junit(output, report)
    text = output.read_text(encoding="utf-8")
    assert 'failures="0"' in text
    assert 'name="fiveNodeAC05" value="not_evaluated"' in text


def test_one_round_marks_repeatability_unmeasured_without_junit_failure(tmp_path: Path):
    first = RoundEvidence(
        "round-1",
        1,
        1,
        1,
        0,
        10.0,
        10.0,
        None,
        10.0,
        ("snapshot",),
        ("node",),
        (("snapshot", "node"),),
        ("fence",),
        (),
        None,
        {},
        {},
        (),
    )
    report = summarize(
        first,
        None,
        topology="preliminary",
        code_sha="abc",
        active_after_first={"cpu": 1},
        active_after_rounds=[{"cpu": 1}],
        expected_active_rounds=[{"cpu": 1}],
        snapshot_replay_stable=None,
        rounds_requested=1,
    )
    assert report["secondRoundStatus"] == "not_requested"
    assert report["deterministicExplainAndSnapshot"] is None
    output = tmp_path / "one-round.xml"
    write_junit(output, report)
    assert 'failures="0"' in output.read_text(encoding="utf-8")


def test_round_keeps_success_and_failure_latency_evidence():
    def reserve(index):
        if index == 2:
            error = RuntimeError("synthetic")
            error.code = "RES-0003"
            error.status = 503
            error.retryable = True
            cause = RuntimeError("lock timeout")
            cause.sqlstate = "55P03"
            error.__cause__ = cause
            raise error
        return {
            "placement": {"snapshotId": f"snap-{index}", "nodeId": "nod_test"},
            "leases": [{"fencingToken": f"epoch:{index}"}],
        }

    evidence, samples = run_round(name="test", request_count=4, concurrency=4, reserve=reserve)
    assert evidence.success_count == 3
    assert evidence.failure_count == 1
    assert evidence.failure_request_indexes == (2,)
    assert evidence.errors_by_code == {"RES-0003": 1}
    assert evidence.errors_by_sqlstate == {"55P03": 1}
    assert evidence.first_failure_completion_order is not None
    assert len(samples) == 4
    failed = next(sample for sample in samples if sample.error_code)
    assert failed.error_status == 503 and failed.error_retryable is True
    assert failed.cause_type == "RuntimeError" and failed.sqlstate == "55P03"
    assert failed.timeout_kind == "lock_timeout"
