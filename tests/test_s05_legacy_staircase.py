from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "run_s05_legacy_staircase", ROOT / "tools" / "run_s05_legacy_staircase.py"
)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


def report(*, concurrency: int = 20, code_sha: str = "a" * 40) -> dict:
    return {
        "schemaVersion": "1.8.0",
        "codeSHA": code_sha,
        "acceptanceClaim": False,
        "requestCount": concurrency,
        "concurrency": concurrency,
        "roundsRequested": 1,
        "rounds": [
            {
                "successCount": concurrency,
                "failureCount": 0,
                "p95AllMs": 400.0,
                "p95SuccessMs": 400.0,
                "maxMs": 450.0,
                "errorsBySqlState": {},
            }
        ],
        "uniqueFencingTokens": True,
        "noOverbooking": True,
        "disposableDatabase": {
            "fingerprintSha256": "b" * 64,
            "nameExposed": False,
            "lifecycle": "unique-pytest-session-database",
        },
        "projectSemaphore": {
            "enabled": False,
            "registryEntryCountAfterWave": 0,
            "registryPermitCountAfterWave": 0,
        },
        "externalFailure": {
            "count": 0,
            "semaphoreRejectCount": 0,
            "sqlTimeoutCount": 0,
        },
        "lockHold": {"commitP95Ms": 12.0, "commitMaxMs": 15.0},
        "legacyLockWait": {"p95Ms": 350.0, "maxMs": 400.0},
        "contentionObservation": {"candidateLimitLockTimeoutMs": 500},
    }


def wave(concurrency: int, ordinal: int, *, p95: float = 400.0, timeout: int = 0) -> dict:
    return {
        "name": f"legacy-c{concurrency}-{ordinal}",
        "concurrency": concurrency,
        "ordinal": ordinal,
        "metrics": {
            "p95AllMs": p95,
            "sqlTimeoutCount": timeout,
        },
    }


def test_rungs_and_waves_are_preregistered_in_ascending_order():
    assert module.RUNGS == (20, 35, 50)
    assert [item.name for item in module.rung_specs(35)] == [
        "legacy-c35-1",
        "legacy-c35-2",
        "legacy-c35-3",
    ]


def test_benchmark_command_is_legacy_only_and_uses_full_barrier(tmp_path):
    spec = module.WaveSpec(50, 2)
    command = module.benchmark_command(
        spec, python="python", output_dir=tmp_path, timeout_seconds=300
    )
    assert command[command.index("--requests") + 1] == "50"
    assert command[command.index("--concurrency") + 1] == "50"
    assert command[command.index("--rounds") + 1] == "1"
    assert command[command.index("--mode") + 1] == "legacy"
    assert "--project-semaphore" not in command


def test_report_validation_requires_flag_off_and_disposable_identity():
    evidence = report()
    module.validate_wave_report(module.WaveSpec(20, 1), evidence, "a" * 40)
    evidence["projectSemaphore"]["enabled"] = True
    with pytest.raises(ValueError, match="flag must stay off"):
        module.validate_wave_report(module.WaveSpec(20, 1), evidence, "a" * 40)


def test_database_identity_is_redacted_and_hash_shaped():
    evidence = report()
    assert module._database_fingerprint(evidence) == "b" * 64
    evidence["disposableDatabase"]["nameExposed"] = True
    with pytest.raises(ValueError, match="name must stay redacted"):
        module._database_fingerprint(evidence)


def test_criterion_one_uses_any_wave_max_while_criterion_two_uses_median():
    waves = [
        wave(20, 1, p95=2100.0, timeout=1),
        wave(20, 2, p95=300.0),
        wave(20, 3, p95=400.0),
    ]
    result = module.evaluate_rung(20, waves)
    assert result["maximumWaveSqlTimeoutCount"] == 1
    assert result["medianRequestP95AllMs"] == 400.0
    assert result["criteria"] == {
        "anyWaveHas55P03Or57014": True,
        "medianCumulativeRequestP95AllExceeds2000Ms": False,
    }
    assert result["degraded"] is True


def test_cumulative_p95_threshold_is_strict_and_can_trigger_without_sql_timeout():
    boundary = [wave(35, index, p95=2000.0) for index in range(1, 4)]
    above = [wave(35, index, p95=2000.001) for index in range(1, 4)]
    assert module.evaluate_rung(35, boundary)["degraded"] is False
    result = module.evaluate_rung(35, above)
    assert result["criteria"]["medianCumulativeRequestP95AllExceeds2000Ms"] is True
    assert result["criteria"]["anyWaveHas55P03Or57014"] is False


def test_sqlstate_counts_are_not_merged_with_success_latency():
    evidence = report()
    evidence["rounds"][0]["successCount"] = 19
    evidence["rounds"][0]["failureCount"] = 1
    evidence["rounds"][0]["errorsBySqlState"] = {"57014": 1}
    evidence["externalFailure"]["count"] = 1
    evidence["externalFailure"]["sqlTimeoutCount"] = 1
    metrics = module._wave_metrics(evidence)
    assert metrics["statementTimeout57014Count"] == 1
    assert metrics["lockTimeout55P03Count"] == 0


def test_workflow_is_opt_in_and_checks_out_the_pr_head():
    workflow = (ROOT / ".github" / "workflows" / "s05-legacy-staircase.yml").read_text(
        encoding="utf-8"
    )
    assert "run-s05-legacy-staircase" in workflow
    assert "github.event.pull_request.head.sha || github.sha" in workflow
    assert "pull_request:\n    types:\n      - labeled" in workflow


def test_integration_report_records_redacted_disposable_fingerprint():
    source = (ROOT / "tests" / "integration" / "test_placement_benchmark.py").read_text(
        encoding="utf-8"
    )
    assert '"fingerprintSha256"' in source
    assert '"nameExposed": False' in source
    assert "a.e.database_name.encode" in source
    assert "import hashlib" in source


def test_aggregate_junit_records_measurement_not_promotion(tmp_path):
    summary = {
        "codeSha": "a" * 40,
        "evaluation": {
            "decision": "NO_DEGRADE_THROUGH_50_CLOSE_SEMAPHORE_LINE",
            "firstDegradeConcurrency": None,
        },
    }
    path = tmp_path / "summary.xml"
    module.write_junit(path, summary)
    text = path.read_text(encoding="utf-8")
    assert 'failures="0"' in text
    assert 'name="promotionClaim" value="False"' in text
    assert "NO_DEGRADE_THROUGH_50_CLOSE_SEMAPHORE_LINE" in text
