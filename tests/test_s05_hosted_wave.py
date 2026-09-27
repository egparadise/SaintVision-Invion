from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "run_s05_hosted_wave", ROOT / "tools" / "run_s05_hosted_wave.py"
)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


def report(*, candidate: bool, code_sha: str = "a" * 40, failures: int = 0) -> dict:
    successes = 20 - failures
    return {
        "schemaVersion": "1.8.0",
        "codeSHA": code_sha,
        "acceptanceClaim": False,
        "requestCount": 20,
        "concurrency": 20,
        "roundsRequested": 1,
        "rounds": [
            {
                "successCount": successes,
                "failureCount": failures,
                "p95AllMs": 100.0 if not candidate else 90.0,
                "p95SuccessMs": 95.0 if successes else None,
            }
        ],
        "uniqueFencingTokens": True,
        "noOverbooking": True,
        "projectSemaphore": {
            "enabled": candidate,
            "limit": 4,
            "permitWaitBudgetMs": 0,
            "permitHoldP95Ms": 20.0 if candidate else None,
            "registryEntryCountAfterWave": 0,
            "registryPermitCountAfterWave": 0,
        },
        "externalFailure": {
            "count": failures,
            "semaphoreRejectCount": failures if candidate else 0,
            "sqlTimeoutCount": 0 if candidate else failures,
        },
        "lockHold": {"commitP95Ms": 40.0 if not candidate else 30.0},
        "contentionObservation": {"candidateLimitLockTimeoutMs": 500},
    }


def wave(mode: str, ordinal: int, *, failures: int = 0) -> dict:
    candidate = mode == "candidate-b"
    item = report(candidate=candidate, failures=failures)
    return {
        "name": f"{mode}-{ordinal}",
        "mode": mode,
        "ordinal": ordinal,
        "metrics": module._wave_metrics(item),
    }


def test_wave_order_is_strictly_sequential():
    assert [spec.name for spec in module.wave_specs()] == [
        "legacy-1",
        "legacy-2",
        "legacy-3",
        "candidate-b-1",
        "candidate-b-2",
        "candidate-b-3",
    ]


def test_candidate_command_enables_only_approved_private_settings(tmp_path):
    command = module.benchmark_command(
        module.WaveSpec("candidate-b", 1),
        python="python",
        output_dir=tmp_path,
        timeout_seconds=240,
    )
    assert command[command.index("--requests") + 1] == "20"
    assert command[command.index("--concurrency") + 1] == "20"
    assert command[command.index("--rounds") + 1] == "1"
    assert "--project-semaphore" in command
    assert command[command.index("--project-semaphore-limit") + 1] == "4"
    assert command[command.index("--candidate-limit-lock-timeout-ms") + 1] == "500"
    assert "--queue-diagnostic" not in command


def test_legacy_command_keeps_flag_off(tmp_path):
    command = module.benchmark_command(
        module.WaveSpec("legacy", 1),
        python="python",
        output_dir=tmp_path,
        timeout_seconds=240,
    )
    assert command[command.index("--mode") + 1] == "legacy"
    assert "--project-semaphore" not in command


@pytest.mark.parametrize("candidate", [False, True])
def test_report_validation_accepts_complete_invariant_evidence(candidate):
    spec = module.WaveSpec("candidate-b" if candidate else "legacy", 1)
    module.validate_wave_report(spec, report(candidate=candidate), "a" * 40)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("uniqueFencingTokens", False, "fencing invariant"),
        ("noOverbooking", False, "no-overbooking invariant"),
        ("acceptanceClaim", True, "acceptance claim forbidden"),
    ],
)
def test_report_validation_fails_closed_on_invariant_or_claim(field, value, message):
    evidence = report(candidate=True)
    evidence[field] = value
    with pytest.raises(ValueError, match=message):
        module.validate_wave_report(module.WaveSpec("candidate-b", 1), evidence, "a" * 40)


def test_report_validation_rejects_semaphore_residue():
    evidence = report(candidate=True)
    evidence["projectSemaphore"]["registryPermitCountAfterWave"] = 1
    with pytest.raises(ValueError, match="permit residue"):
        module.validate_wave_report(module.WaveSpec("candidate-b", 1), evidence, "a" * 40)


def test_evaluation_passes_only_when_all_three_gates_pass():
    waves = [wave("legacy", index) for index in range(1, 4)] + [
        wave("candidate-b", index) for index in range(1, 4)
    ]
    result = module.evaluate(waves)
    assert result["candidateDecision"] == "GATES_PASSED"
    assert all(result["gates"].values())
    assert result["promotionClaim"] is False
    assert result["s05StatusAfterRun"] == "in_progress"


def test_gate_two_uses_all_request_p95_not_success_only():
    legacy = [wave("legacy", index) for index in range(1, 4)]
    candidate = [wave("candidate-b", index) for index in range(1, 4)]
    for item in legacy:
        item["metrics"]["p95AllMs"] = 100.0
        item["metrics"]["p95SuccessMs"] = 10.0
    for item in candidate:
        item["metrics"]["p95AllMs"] = 90.0
        item["metrics"]["p95SuccessMs"] = 900.0
    result = module.evaluate(legacy + candidate)
    assert result["gates"]["allRequestP95MedianNonWorse"] is True
    assert result["candidateB"]["allRequestP95MedianMs"] == 90.0


def test_equal_metrics_are_non_worse_at_the_inclusive_boundary():
    legacy = [wave("legacy", index) for index in range(1, 4)]
    candidate = [wave("candidate-b", index) for index in range(1, 4)]
    for item in legacy + candidate:
        item["metrics"]["externalFailureCount"] = 0
        item["metrics"]["p95AllMs"] = 100.0
        item["metrics"]["postAcquireHoldP95Ms"] = 40.0
    result = module.evaluate(legacy + candidate)
    assert result["gates"] == {
        "externalFailureNonIncrease": True,
        "allRequestP95MedianNonWorse": True,
        "successfulPostAcquireHoldP95MedianNonWorse": True,
    }


def test_semaphore_rejects_are_counted_as_external_failures():
    waves = [wave("legacy", index) for index in range(1, 4)] + [
        wave("candidate-b", index, failures=16) for index in range(1, 4)
    ]
    result = module.evaluate(waves)
    assert result["candidateB"]["externalFailureTotal"] == 48
    assert result["gates"]["externalFailureNonIncrease"] is False
    assert result["candidateDecision"] == "GATES_FAILED"


def test_evaluation_requires_exactly_three_waves_per_mode():
    with pytest.raises(ValueError, match="three candidate-B waves required"):
        module.evaluate([wave("legacy", index) for index in range(1, 4)])


def test_aggregate_junit_reports_measurement_not_promotion(tmp_path):
    summary = {
        "codeSha": "b" * 40,
        "measurementTargetProductSha": "a" * 40,
        "evaluation": {
            "candidateDecision": "GATES_FAILED",
            "gates": {
                "externalFailureNonIncrease": False,
                "allRequestP95MedianNonWorse": True,
                "successfulPostAcquireHoldP95MedianNonWorse": True,
            },
        },
    }
    path = tmp_path / "summary.xml"
    module.write_junit(path, summary)
    text = path.read_text(encoding="utf-8")
    assert 'failures="0"' in text
    assert 'name="candidateDecision" value="GATES_FAILED"' in text
    assert 'name="measurementTargetProductSha" value="aaaaaaaa' in text
    assert 'name="promotionClaim" value="False"' in text


def test_summary_json_can_be_redacted_without_dsn(tmp_path):
    evidence = {
        "runner": module.runner_environment(),
        "directlyComparableWithLocalEvidence": False,
    }
    path = tmp_path / "summary.json"
    path.write_text(json.dumps(evidence), encoding="utf-8")
    assert "postgresql://" not in path.read_text(encoding="utf-8")
