from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "run_s05_legacy_staircase", ROOT / "tools" / "run_s05_legacy_staircase.py"
)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)

HOSTED_SCOPE = "hosted-single-runner-legacy-only-postgresql16"


def report(
    *,
    concurrency: int = 20,
    code_sha: str = "a" * 40,
    fingerprint: str = "b" * 64,
    scope: str = HOSTED_SCOPE,
) -> dict:
    return {
        "schemaVersion": "1.7.0",
        "codeSHA": code_sha,
        "scope": scope,
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
            "fingerprintSha256": fingerprint,
            "nameExposed": False,
            "lifecycle": "unique-pytest-session-database",
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


def main_args(output_dir: Path) -> list[str]:
    return [
        "--output-dir",
        str(output_dir),
        "--run-purpose",
        "quality-regression-test",
        "--canonical-decision-evidence-run-id",
        "36362386530",
        "--measurement-scope",
        HOSTED_SCOPE,
    ]


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
        spec,
        python="python",
        output_dir=tmp_path,
        timeout_seconds=300,
        measurement_scope=HOSTED_SCOPE,
    )
    assert command[command.index("--requests") + 1] == "50"
    assert command[command.index("--concurrency") + 1] == "50"
    assert command[command.index("--rounds") + 1] == "1"
    assert command[command.index("--mode") + 1] == "legacy"
    assert command[command.index("--topology") + 1] == HOSTED_SCOPE
    assert "--project-semaphore" not in command


def test_report_validation_forbids_semaphore_evidence_and_requires_disposable_identity():
    evidence = report()
    module.validate_wave_report(module.WaveSpec(20, 1), evidence, "a" * 40, HOSTED_SCOPE)
    evidence["projectSemaphore"] = {"enabled": False}
    with pytest.raises(ValueError, match="semaphore evidence forbidden"):
        module.validate_wave_report(module.WaveSpec(20, 1), evidence, "a" * 40, HOSTED_SCOPE)


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
    metrics = module._wave_metrics(evidence)
    assert metrics["statementTimeout57014Count"] == 1
    assert metrics["lockTimeout55P03Count"] == 0
    assert metrics["sqlTimeoutCount"] == 1


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda item: item.pop("errorsBySqlState"), "errorsBySqlState is required"),
        (lambda item: item.pop("p95AllMs"), "round field p95AllMs is required"),
        (
            lambda item: item.update(failureCount=1, errorsBySqlState={}),
            "sum must equal failureCount",
        ),
        (
            lambda item: item.update(failureCount=1, errorsBySqlState={"40P01": 1}),
            "failureCount exceeds classified SQL timeout failures",
        ),
    ],
)
def test_wave_metrics_fail_closed_on_incomplete_failure_classification(mutation, message):
    evidence = report()
    mutation(evidence["rounds"][0])
    with pytest.raises(ValueError, match=message):
        module._wave_metrics(evidence)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("codeSHA", "c" * 40, "codeSHA"),
        ("scope", "development-PC", "measurement scope"),
    ],
)
def test_wave_report_rejects_wrong_provenance(field, value, message):
    evidence = report()
    evidence[field] = value
    with pytest.raises(ValueError, match=message):
        module.validate_wave_report(module.WaveSpec(20, 1), evidence, "a" * 40, HOSTED_SCOPE)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda database: database.update(fingerprintSha256="not-a-sha"),
            "fingerprint",
        ),
        (
            lambda database: database.update(lifecycle="shared-database"),
            "lifecycle",
        ),
    ],
)
def test_database_identity_rejects_bad_hash_and_lifecycle(mutation, message):
    evidence = report()
    mutation(evidence["disposableDatabase"])
    with pytest.raises(ValueError, match=message):
        module._database_fingerprint(evidence)


def test_code_sha_and_clean_checkout_are_fail_closed():
    with pytest.raises(SystemExit, match="full lowercase Git SHA"):
        module.validate_code_sha("A" * 40, "a" * 40)
    with pytest.raises(SystemExit, match="match the checked-out PR head"):
        module.validate_code_sha("a" * 40, "b" * 40)
    with pytest.raises(SystemExit, match="working tree must be clean"):
        module.validate_clean_checkout(" M tools/run_s05_legacy_staircase.py\n")


@pytest.mark.parametrize(
    ("purpose", "run_id", "scope", "message"),
    [
        ("Not Kebab", "36362386530", HOSTED_SCOPE, "run-purpose"),
        ("valid-purpose", "not-a-run", HOSTED_SCOPE, "GitHub run ID"),
        ("valid-purpose", "36362386530", "hosted\nspoofed", "measurement-scope"),
    ],
)
def test_run_metadata_is_bounded_and_machine_readable(purpose, run_id, scope, message):
    with pytest.raises(SystemExit, match=message):
        module.validate_run_metadata(purpose, run_id, scope)


def test_workflow_is_opt_in_and_checks_out_the_pr_head():
    workflow = (ROOT / ".github" / "workflows" / "s05-legacy-staircase.yml").read_text(
        encoding="utf-8"
    )
    assert "run-s05-legacy-staircase" in workflow
    assert "github.event.pull_request.head.sha || github.sha" in workflow
    assert "pull_request:\n    types:\n      - labeled" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "--run-purpose clean-integration-base-execution-compatibility" in workflow
    assert "--measurement-scope hosted-single-runner-legacy-only-postgresql16" in workflow


def test_clean_base_lane_has_no_semaphore_product_dependency():
    runner = (ROOT / "tools" / "run_s05_legacy_staircase.py").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "s05-legacy-staircase.yml").read_text(
        encoding="utf-8"
    )
    benchmark = (ROOT / "tools" / "placement_benchmark.py").read_text(encoding="utf-8")
    assert "--project-semaphore" not in runner
    assert "--project-semaphore" not in workflow
    assert "--project-semaphore" not in benchmark


def test_integration_report_records_redacted_disposable_fingerprint():
    source = (ROOT / "tests" / "integration" / "test_placement_benchmark.py").read_text(
        encoding="utf-8"
    )
    assert '"fingerprintSha256"' in source
    assert '"nameExposed": False' in source
    assert "a.e.database_name.encode" in source
    assert "import hashlib" in source
    assert "INV_PLACEMENT_BENCHMARK_TOPOLOGY" in source


def test_aggregate_junit_records_measurement_not_promotion(tmp_path):
    summary = {
        "codeSha": "a" * 40,
        "runPurpose": "clean-integration-base-execution-compatibility",
        "canonicalDecisionEvidenceRunId": "36362386530",
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
    assert 'name="canonicalDecisionEvidenceRunId" value="36362386530"' in text
    assert 'name="semaphoreProductCodeExpected" value="False"' in text
    assert "NO_DEGRADE_THROUGH_50_CLOSE_SEMAPHORE_LINE" in text


def test_main_fails_closed_and_stops_after_first_degraded_rung(tmp_path, monkeypatch, capsys):
    code_sha = "a" * 40
    output_dir = tmp_path / "evidence"
    output_dir.mkdir()
    for spec in module.rung_specs(20):
        (output_dir / f"{spec.name}.json").write_text("stale", encoding="utf-8")
        (output_dir / f"{spec.name}.xml").write_text("stale", encoding="utf-8")
    (output_dir / "s05-legacy-staircase-summary.json").write_text("stale", encoding="utf-8")
    (output_dir / "s05-legacy-staircase-summary.xml").write_text("stale", encoding="utf-8")

    calls: list[list[str]] = []

    def fake_check_output(command, **_kwargs):
        if command[:3] == ["git", "rev-parse", "HEAD"]:
            return f"{code_sha}\n"
        if command[:3] == ["git", "status", "--porcelain"]:
            return ""
        raise AssertionError(command)

    def fake_run(command, **_kwargs):
        calls.append(command)
        concurrency = int(command[command.index("--concurrency") + 1])
        report_path = Path(command[command.index("--report") + 1])
        junit_path = Path(command[command.index("--junit") + 1])
        assert not report_path.exists()
        assert not junit_path.exists()
        ordinal = len(calls)
        if ordinal == 1:
            assert not (output_dir / "s05-legacy-staircase-summary.json").exists()
            assert not (output_dir / "s05-legacy-staircase-summary.xml").exists()
        evidence = report(
            concurrency=concurrency,
            code_sha=code_sha,
            fingerprint=f"{ordinal:064x}",
        )
        if ordinal == 1:
            evidence["rounds"][0].update(
                successCount=concurrency - 1,
                failureCount=1,
                errorsBySqlState={"57014": 1},
            )
        report_path.write_text(json.dumps(evidence), encoding="utf-8")
        junit_path.write_text("<testsuite/>", encoding="utf-8")
        return SimpleNamespace(returncode=1 if ordinal == 1 else 0)

    monkeypatch.setattr(module.subprocess, "check_output", fake_check_output)
    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(module, "owned_disposable_count", lambda _dsn: 0)
    monkeypatch.setattr(module, "runner_environment", lambda: {"runnerOS": "test"})
    monkeypatch.setattr(module, "postgres_environment", lambda _dsn: {"serverVersion": "16"})
    monkeypatch.setenv("INV_TEST_ADMIN_DSN", "postgresql://redacted")
    monkeypatch.setenv("INV_EVIDENCE_CODE_SHA", code_sha)

    result = module.main(main_args(output_dir))

    assert result == 0
    assert len(calls) == 3
    summary = json.loads((output_dir / "s05-legacy-staircase-summary.json").read_text())
    assert summary["evaluation"]["decision"] == "DEGRADE_AT_20"
    assert summary["evaluation"]["firstDegradeConcurrency"] == 20
    assert summary["waves"][0]["metrics"]["sqlTimeoutCount"] == 1
    assert summary["runPurpose"] == "quality-regression-test"
    assert summary["measurementScope"] == HOSTED_SCOPE
    assert summary["semaphoreProductCodeExpected"] is False
    assert "DEGRADE_AT_20" in capsys.readouterr().out


def test_main_rejects_reused_database_fingerprint(tmp_path, monkeypatch):
    code_sha = "a" * 40
    output_dir = tmp_path / "duplicate"

    def fake_check_output(command, **_kwargs):
        return f"{code_sha}\n" if command[1] == "rev-parse" else ""

    call_count = 0

    def fake_run(command, **_kwargs):
        nonlocal call_count
        call_count += 1
        concurrency = int(command[command.index("--concurrency") + 1])
        report_path = Path(command[command.index("--report") + 1])
        junit_path = Path(command[command.index("--junit") + 1])
        report_path.write_text(
            json.dumps(report(concurrency=concurrency, code_sha=code_sha)),
            encoding="utf-8",
        )
        junit_path.write_text("<testsuite/>", encoding="utf-8")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(module.subprocess, "check_output", fake_check_output)
    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(module, "owned_disposable_count", lambda _dsn: 0)
    monkeypatch.setenv("INV_TEST_ADMIN_DSN", "postgresql://redacted")
    monkeypatch.setenv("INV_EVIDENCE_CODE_SHA", code_sha)

    with pytest.raises(ValueError, match="database was reused"):
        module.main(main_args(output_dir))
    assert call_count == 2


def test_main_rejects_unexpected_benchmark_exit(tmp_path, monkeypatch):
    code_sha = "a" * 40
    output_dir = tmp_path / "bad-exit"

    def fake_check_output(command, **_kwargs):
        return f"{code_sha}\n" if command[1] == "rev-parse" else ""

    def fake_run(command, **_kwargs):
        concurrency = int(command[command.index("--concurrency") + 1])
        report_path = Path(command[command.index("--report") + 1])
        junit_path = Path(command[command.index("--junit") + 1])
        report_path.write_text(
            json.dumps(report(concurrency=concurrency, code_sha=code_sha)),
            encoding="utf-8",
        )
        junit_path.write_text("<testsuite/>", encoding="utf-8")
        return SimpleNamespace(returncode=2)

    monkeypatch.setattr(module.subprocess, "check_output", fake_check_output)
    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(module, "owned_disposable_count", lambda _dsn: 0)
    monkeypatch.setenv("INV_TEST_ADMIN_DSN", "postgresql://redacted")
    monkeypatch.setenv("INV_EVIDENCE_CODE_SHA", code_sha)

    with pytest.raises(SystemExit, match="unexpected exit 2"):
        module.main(main_args(output_dir))
