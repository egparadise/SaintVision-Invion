"""The public restore verdict must fail closed and preserve measurement meaning."""

import datetime as dt
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

SPEC = importlib.util.spec_from_file_location(
    "recovery_verdict", Path(__file__).resolve().parents[2] / "tools/recovery_drill.py"
)
drill = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(drill)


def good_report():
    return dict(
        restoreExitCode=0,
        integrityVerified=True,
        fencingVerified=True,
        measuredRpoSeconds=0,
        measuredRtoSeconds=0.001,
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("restoreExitCode", 1),
        ("restoreExitCode", None),
        ("restoreExitCode", False),
        ("integrityVerified", "true"),
        ("fencingVerified", 1),
        *[
            (key, value)
            for key in ("measuredRpoSeconds", "measuredRtoSeconds")
            for value in (-1, float("nan"), float("inf"), None, True, "0")
        ],
    ],
)
def test_invalid_or_unknown_verdict_cannot_pass(field, value):
    report = good_report()
    assert drill._passed(report)
    report[field] = value
    assert not drill._passed(report)


def test_recovery_point_is_age_at_restore_start_and_requires_known_timezone():
    start = dt.datetime(2026, 9, 11, tzinfo=dt.timezone.utc)
    assert drill._recovery_point_age(start - dt.timedelta(seconds=60), start) == 60
    for invalid in (None, start.replace(tzinfo=None), start + dt.timedelta(microseconds=1)):
        assert drill._recovery_point_age(invalid, start) is None


@pytest.mark.parametrize("container", [None, "owned-drill-test"])
def test_pg_password_never_enters_child_argv(monkeypatch, container):
    calls = []

    def capture(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, b"", b"")

    monkeypatch.setattr(drill.subprocess, "run", capture)
    secret = "synthetic password with ' quotes"
    from psycopg.conninfo import make_conninfo

    drill.Postgres(container).run(
        "pg_dump", ["--dbname", make_conninfo(user="operator", password=secret, dbname="test")]
    )
    argv, options = calls[0]
    assert secret not in " ".join(argv)
    assert "password=" not in " ".join(argv)
    assert options["env"]["PGPASSWORD"] == secret
    if container:
        assert argv[:5] == ["docker", "exec", "-i", "--env", "PGPASSWORD"]


def test_cli_observation_failure_does_not_emit_exception_bytes(monkeypatch, capsys):
    def fail(_):
        raise RuntimeError("postgresql://operator:synthetic-secret@database sensitive-row")

    monkeypatch.setattr(drill, "rehearse", fail)
    monkeypatch.setattr(
        sys, "argv", ["recovery_drill.py", "--source", "test", "--admin", "test", "--json"]
    )
    assert drill.main() == 2
    assert json.loads(capsys.readouterr().out) == {"status": "unavailable", "error": "RuntimeError"}


def test_sequence_called_state_and_late_high_water_are_required():
    before = dict(
        sequenceLastValue=500, sequenceCalled=True, sequenceIncrement=1, highestHeldToken=500
    )
    target = dict(before, sequenceCalled=False)
    result = drill._fencing_verdict(before, before, target)
    assert not result["fencingVerified"]
    assert result["fencingAdvanceRequired"] == 1
    assert result["fencingNextValue"] == 500
    after = dict(before, sequenceLastValue=501)
    assert not drill._fencing_verdict(before, after, before)["fencingVerified"]
    assert not drill._fencing_verdict(before, before, dict(before, sequenceCalled=None))[
        "fencingVerified"
    ]
    assert drill._fencing_verdict(before, before, before)["fencingVerified"]
