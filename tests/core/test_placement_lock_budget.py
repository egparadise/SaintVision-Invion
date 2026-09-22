"""PG-free boundaries for the private candidate limits-lock budget."""

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from inv.db import BoundDatabase, Database
from tools import placement_benchmark


def _database(**kwargs):
    return Database("postgresql://not-connected", recovery_epoch=str(uuid4()), **kwargs)


def test_database_and_bound_database_keep_private_budget_explicit():
    default = _database()
    assert default.placement_candidate_limit_lock_timeout_ms == 500

    candidate = _database(
        placement_short_commit=True,
        placement_candidate_limit_lock_timeout_ms=1500,
    )
    bound = BoundDatabase(candidate, str(uuid4()), object())
    assert candidate.placement_candidate_limit_lock_timeout_ms == 1500
    assert bound.placement_candidate_limit_lock_timeout_ms == 1500


@pytest.mark.parametrize("value", [False, True, 0, -1, 1901, 500.0, "1500", None])
def test_candidate_limit_budget_rejects_non_integer_or_out_of_range(value):
    with pytest.raises(
        ValueError,
        match="placement_candidate_limit_lock_timeout_ms must be an integer between 1 and 1900",
    ):
        _database(placement_candidate_limit_lock_timeout_ms=value)


@pytest.mark.parametrize("value", [1, 500, 1500, 1900])
def test_candidate_limit_budget_accepts_documented_range(value):
    assert (
        _database(
            placement_candidate_limit_lock_timeout_ms=value
        ).placement_candidate_limit_lock_timeout_ms
        == value
    )


def test_benchmark_cli_restricts_budget_to_candidate_mode(monkeypatch, tmp_path: Path):
    seen = []
    monkeypatch.setattr(
        placement_benchmark,
        "_run_pytest_adapter",
        lambda args: seen.append(args.candidate_limit_lock_timeout_ms) or 0,
    )
    common = [
        "--requests",
        "1",
        "--concurrency",
        "1",
        "--junit",
        str(tmp_path / "result.xml"),
        "--report",
        str(tmp_path / "result.json"),
    ]

    assert (
        placement_benchmark.main(
            common
            + [
                "--mode",
                "short-commit",
                "--candidate-limit-lock-timeout-ms",
                "1900",
            ]
        )
        == 0
    )
    assert seen == [1900]

    with pytest.raises(SystemExit, match="only valid with --mode short-commit"):
        placement_benchmark.main(common + ["--candidate-limit-lock-timeout-ms", "1500"])
    with pytest.raises(SystemExit, match="must be between 1 and 1900"):
        placement_benchmark.main(
            common
            + [
                "--mode",
                "short-commit",
                "--candidate-limit-lock-timeout-ms",
                "1901",
            ]
        )


def test_benchmark_adapter_passes_private_budget_only_through_test_env(monkeypatch, tmp_path: Path):
    captured = {}
    monkeypatch.setattr(
        placement_benchmark.subprocess,
        "check_output",
        lambda *args, **kwargs: "abc123\n",
    )

    def completed(command, *, cwd, env, timeout):
        captured.update({"command": command, "cwd": cwd, "env": env, "timeout": timeout})
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(placement_benchmark.subprocess, "run", completed)
    args = placement_benchmark.parse_args(
        [
            "--requests",
            "1",
            "--concurrency",
            "1",
            "--mode",
            "short-commit",
            "--candidate-limit-lock-timeout-ms",
            "1500",
            "--junit",
            str(tmp_path / "result.xml"),
            "--report",
            str(tmp_path / "result.json"),
        ]
    )

    assert placement_benchmark._run_pytest_adapter(args) == 0
    assert captured["env"]["INV_PLACEMENT_SHORT_COMMIT"] == "1"
    assert captured["env"]["INV_PLACEMENT_CANDIDATE_LIMIT_LOCK_TIMEOUT_MS"] == "1500"
    assert "tests/integration/test_placement_benchmark.py" in captured["command"]
