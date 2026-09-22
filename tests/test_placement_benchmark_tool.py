from pathlib import Path

import pytest

from tools.placement_benchmark import percentile_nearest_rank, run_round, write_junit


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


def test_round_keeps_success_and_failure_latency_evidence():
    def reserve(index):
        if index == 2:
            error = RuntimeError("synthetic")
            error.code = "RES-0003"
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
    assert evidence.first_failure_completion_order is not None
    assert len(samples) == 4
