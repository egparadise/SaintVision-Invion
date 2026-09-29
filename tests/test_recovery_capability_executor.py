"""PG-free: the settings executors behind ``_recovery_capability`` (G-02 design v1.1 §2, §5, §6).

Each test is one reversion the design lists: the capability function ignoring
its injected executor, the docker-exec executor returning the archive command
text, a failure or a missing setting being swallowed into a report, and the
judgement being copied into a test. The judgement itself (``rpo_bound_from``)
is not called here; only the report's fields are read.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("recovery_drill", ROOT / "tools" / "recovery_drill.py")
drill = importlib.util.module_from_spec(spec)
spec.loader.exec_module(drill)

NAMES = drill._CAPABILITY_SETTING_NAMES


def _psql_stdout(**overrides) -> bytes:
    values = {
        "archive_command": "configured",
        "archive_library": "not configured",
        "archive_mode": "on",
        "archive_timeout": "300",
        "data_checksums": "off",
        "full_page_writes": "on",
        "wal_level": "replica",
    }
    values.update(overrides)
    return "".join(f"{k}\t{v}\n" for k, v in sorted(values.items())).encode()


def _fake_run(stdout: bytes = b"", *, returncode: int = 0, raise_exc: Exception | None = None):
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        if raise_exc is not None:
            raise raise_exc
        return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=b"server said: archive_command='/usr/bin/secret --token=abc'")

    run.calls = calls
    return run


# ---------------------------------------------------------------- the executor is honoured


def test_the_injected_executor_is_used_and_no_host_connection_is_made(monkeypatch):
    def refuse(_dsn):
        raise AssertionError("_conn must not be called when an executor is injected")

    monkeypatch.setattr(drill, "_conn", refuse)
    seen = []

    def execute():
        seen.append(True)
        return {name: value for name, value in zip(NAMES, ("replica", "on", "configured", "not configured", "300", "on", "on"))}

    report = drill._recovery_capability(execute=execute)
    assert seen == [True]
    assert report["archivingConfigured"] is True
    assert report["archiveSwitchTimeoutSeconds"] == 300
    assert report["dataChecksumsEnabled"] is True
    assert report["operationalRpoVerified"] is False and report["operationalRpoBoundSeconds"] is None
    # dsn is ignored when an executor is given -- the host is never contacted.
    drill._recovery_capability("postgresql://never@host/db", execute=execute)
    assert len(seen) == 2


def test_without_an_executor_the_dsn_path_is_the_default_and_both_are_required_somewhere(monkeypatch):
    with pytest.raises(ValueError):
        drill._recovery_capability()
    used = []

    def executor_factory(dsn):
        used.append(dsn)
        return lambda: {name: "on" if name != "archive_timeout" else "0" for name in NAMES}

    monkeypatch.setattr(drill, "psycopg_settings_executor", executor_factory)
    drill._recovery_capability("postgresql://host/db")
    assert used == ["postgresql://host/db"]


# ---------------------------------------------------------------- docker exec executor: wire and folding


def test_docker_exec_executor_asks_psql_inside_the_container_with_the_shared_sql():
    run = _fake_run(_psql_stdout())
    execute = drill.docker_exec_settings_executor("sv-rpo-abc", run=run)
    settings = execute()
    (argv, kwargs), = run.calls
    assert argv[:3] == ["docker", "exec", "sv-rpo-abc"]
    assert "psql" in argv and "-At" in argv and "ON_ERROR_STOP=1" in argv
    assert argv[argv.index("-c") + 1] == drill._CAPABILITY_SETTINGS_SQL      # one SQL text for every executor
    assert "'archive_command'" in drill._CAPABILITY_SETTINGS_SQL and "'not configured'" in drill._CAPABILITY_SETTINGS_SQL
    assert kwargs["capture_output"] is True and kwargs["timeout"] > 0
    assert settings == {
        "archive_command": "configured", "archive_library": "not configured", "archive_mode": "on",
        "archive_timeout": "300", "data_checksums": "off", "full_page_writes": "on", "wal_level": "replica",
    }


def test_the_archive_command_text_never_reaches_the_report():
    """The fold happens in SQL; an executor that returned the raw command would be a defect."""
    run = _fake_run(_psql_stdout())
    report = drill._recovery_capability(execute=drill.docker_exec_settings_executor("c", run=run))
    assert "secret" not in json.dumps(report) and "--token" not in json.dumps(report)
    assert report["settings"]["archive_command"] == "configured"
    # A row carrying a command instead of the fold is refused as a malformed answer
    # only if it is not one of the two fixed values -- the SQL guarantees the fold,
    # and nothing downstream re-derives it: the test reads the field, it does not compute it.
    assert set(report["settings"]) == set(NAMES)


# ---------------------------------------------------------------- fail-closed: no report without an observation


@pytest.mark.parametrize(
    "run,expected",
    [
        (_fake_run(b"", returncode=1), "psql exited 1"),
        (_fake_run(raise_exc=subprocess.TimeoutExpired(cmd="docker", timeout=20)), "TimeoutExpired"),
        (_fake_run(raise_exc=FileNotFoundError("docker")), "FileNotFoundError"),
        (_fake_run(b"".join(line + b"\n" for line in _psql_stdout().splitlines() if not line.startswith(b"wal_level"))), "settings not observed: wal_level"),
        (_fake_run(b"wal_level\treplica\textra\n"), "malformed settings line"),
        (_fake_run(b"not_a_setting\tvalue\n"), "unexpected settings row"),
    ],
)
def test_every_executor_failure_raises_and_leaks_no_server_text(run, expected):
    execute = drill.docker_exec_settings_executor("c", run=run)
    with pytest.raises(RuntimeError) as exc:
        drill._recovery_capability(execute=execute)
    message = str(exc.value)
    assert expected in message
    assert "secret" not in message and "--token" not in message and "server said" not in message


def test_a_missing_setting_is_not_reported_as_unset():
    """No default is invented: a report without wal_level would state a fact never read."""
    partial = {name: "on" for name in NAMES if name != "wal_level"}
    with pytest.raises(RuntimeError, match="wal_level"):
        drill._recovery_capability(execute=lambda: drill._settings_from_rows(list(partial.items()), source="test"))


# ---------------------------------------------------------------- the judgement is not copied here


def _called_names(source: str) -> set[str]:
    """Every callee name in ``source`` (bare names and attribute tails), via the AST."""
    import ast

    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            target = node.func
            if isinstance(target, ast.Name):
                names.add(target.id)
            elif isinstance(target, ast.Attribute):
                names.add(target.attr)
    return names


def test_this_file_and_the_live_case_read_the_report_and_never_call_the_judgement():
    """The fold and the judgement live in the tool; tests read fields, they do not compute them."""
    here = Path(__file__).read_text(encoding="utf-8")
    live = (ROOT / "tests" / "integration" / "test_recovery_drill.py").read_text(encoding="utf-8")
    assert "rpo_bound_from" not in _called_names(here)
    assert "rpo_bound_from" not in _called_names(live)
    assert "_settings_from_rows" not in _called_names(live)          # the live case injects, never re-folds
    tool = (ROOT / "tools" / "recovery_drill.py").read_text(encoding="utf-8")
    assert "rpo_bound_from" in _called_names(tool)                    # the only caller
    assert drill.rpo_bound_from.__module__ == drill.__name__


def test_a_duplicate_settings_row_is_refused_not_overwritten():
    rows = [(name, "on") for name in NAMES] + [("archive_mode", "off")]
    with pytest.raises(RuntimeError, match="duplicate settings row: archive_mode"):
        drill._settings_from_rows(rows, source="test")
    run = _fake_run(_psql_stdout() + b"archive_mode\toff\n")
    with pytest.raises(RuntimeError, match="duplicate settings row: archive_mode"):
        drill._recovery_capability(execute=drill.docker_exec_settings_executor("c", run=run))


def test_the_live_archiver_case_no_longer_needs_the_cx01_fixture():
    """The hosted skip barrier 1: the two live cases must not depend on ``args``."""
    source = (ROOT / "tests" / "integration" / "test_recovery_drill.py").read_text(encoding="utf-8")
    header = source[source.index("def test_live_archiver_configuration_cannot_certify_operational_rpo("):]
    header = header[: header.index(")")]
    assert "args" not in header.split("(", 1)[1]
    assert "archiver_image" in header
    body = source[source.index("def test_live_archiver_configuration_cannot_certify_operational_rpo("):]
    body = body[: body.index("@pytest.mark.parametrize(\"changed\"")]
    assert "psycopg.connect" not in body                      # no host connection at all
    assert "docker_exec_settings_executor" in body            # the tool's executor, not a copy
    assert "network\", \"create\", \"--internal\"" in body      # isolation kept
    assert "-p" not in body.split("\"docker\",\n                \"run\"")[1].split("archiver_image")[0]   # no published port
