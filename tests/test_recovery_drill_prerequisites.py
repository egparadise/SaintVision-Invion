import json
import runpy
from types import SimpleNamespace
from pathlib import Path

import pytest

from recovery_drill_prerequisites import resolve_owned_postgres_container


def _inspect_result(labels):
    payload = [{"Config": {"Labels": labels}}]
    return SimpleNamespace(returncode=0, stdout=json.dumps(payload).encode(), stderr=b"")


def test_missing_container_identity_is_a_reasoned_skip_without_inspect(monkeypatch):
    monkeypatch.delenv("CX01_CONTAINER", raising=False)
    calls = []

    with pytest.raises(pytest.skip.Exception, match="CX01_CONTAINER is unset"):
        resolve_owned_postgres_container(
            run=lambda *args, **kwargs: calls.append((args, kwargs)),
            which=lambda _: "docker.exe",
        )

    assert calls == []


def test_recovery_args_fixture_reports_missing_identity_as_skip(monkeypatch):
    monkeypatch.setenv("INV_TEST_ADMIN_DSN", "user=postgres dbname=postgres")
    monkeypatch.delenv("CX01_CONTAINER", raising=False)
    module = runpy.run_path(
        str(Path(__file__).resolve().parent / "integration" / "test_recovery_drill.py")
    )
    fixture_body = module["args"].__wrapped__
    fake_postgres = SimpleNamespace(owner="user=postgres dbname=inv_test_fixture")

    with pytest.raises(pytest.skip.Exception, match="CX01_CONTAINER is unset"):
        next(fixture_body(fake_postgres))


def test_absent_named_container_is_a_reasoned_skip(monkeypatch):
    monkeypatch.setenv("CX01_CONTAINER", "disposable-pg")
    result = SimpleNamespace(
        returncode=1,
        stdout=b"[]",
        stderr=b"Error: No such object: disposable-pg",
    )
    calls = []

    with pytest.raises(pytest.skip.Exception, match="CX01_CONTAINER is absent"):
        resolve_owned_postgres_container(
            run=lambda argv, **kwargs: (calls.append(argv) or result),
            which=lambda _: "docker.exe",
        )

    assert calls == [["docker", "inspect", "disposable-pg"]]


def test_missing_docker_cli_is_a_reasoned_skip(monkeypatch):
    monkeypatch.setenv("CX01_CONTAINER", "disposable-pg")
    calls = []

    with pytest.raises(pytest.skip.Exception, match="Docker CLI is unavailable"):
        resolve_owned_postgres_container(
            run=lambda *args, **kwargs: calls.append((args, kwargs)),
            which=lambda _: None,
        )

    assert calls == []


def test_docker_daemon_unavailable_is_a_reasoned_skip(monkeypatch):
    monkeypatch.setenv("CX01_CONTAINER", "disposable-pg")
    result = SimpleNamespace(
        returncode=1,
        stdout=b"",
        stderr=b"Cannot connect to the Docker daemon",
    )

    with pytest.raises(pytest.skip.Exception, match="Docker daemon is unavailable"):
        resolve_owned_postgres_container(
            run=lambda *args, **kwargs: result,
            which=lambda _: "docker.exe",
        )


def test_permission_denied_launching_docker_is_a_reasoned_skip(monkeypatch):
    monkeypatch.setenv("CX01_CONTAINER", "disposable-pg")

    def denied(*args, **kwargs):
        raise PermissionError("details intentionally not propagated")

    with pytest.raises(pytest.skip.Exception, match="Permission denied launching Docker inspect"):
        resolve_owned_postgres_container(run=denied, which=lambda _: "docker.exe")


def test_unknown_spawn_error_is_not_hidden_as_environment_skip(monkeypatch):
    monkeypatch.setenv("CX01_CONTAINER", "disposable-pg")

    def broken(*args, **kwargs):
        raise OSError("internal probe failure")

    with pytest.raises(pytest.fail.Exception, match=r"process failed unexpectedly \(OSError\)"):
        resolve_owned_postgres_container(run=broken, which=lambda _: "docker.exe")


def test_known_codex_disposable_owner_label_allows_test_body(monkeypatch):
    monkeypatch.setenv("CX01_CONTAINER", "codex-disposable-pg")
    result = _inspect_result(
        {
            "ai.saintvision.codex-db-test": "run-nonce",
            "ai.saintvision.created-by": "codex",
        }
    )
    body = []

    container = resolve_owned_postgres_container(
        run=lambda *args, **kwargs: result,
        which=lambda _: "docker.exe",
    )
    body.append("entered")

    assert container == "codex-disposable-pg"
    assert body == ["entered"]


def test_foreign_or_unrecognized_owner_label_is_a_failure_not_a_skip(monkeypatch):
    monkeypatch.setenv("CX01_CONTAINER", "other-project-pg")
    result = _inspect_result({"com.example.owner": "another-project"})

    with pytest.raises(pytest.fail.Exception, match="unowned/foreign resource"):
        resolve_owned_postgres_container(
            run=lambda *args, **kwargs: result,
            which=lambda _: "docker.exe",
        )


def test_codex_label_without_creator_attestation_is_not_owned(monkeypatch):
    monkeypatch.setenv("CX01_CONTAINER", "other-project-pg")
    result = _inspect_result({"ai.saintvision.codex-db-test": "some-run"})

    with pytest.raises(pytest.fail.Exception, match="unowned/foreign resource"):
        resolve_owned_postgres_container(
            run=lambda *args, **kwargs: result,
            which=lambda _: "docker.exe",
        )


def test_recognized_cx01_label_is_accepted(monkeypatch):
    monkeypatch.setenv("CX01_CONTAINER", "cx01-pg")
    result = _inspect_result({"ai.saintvision.cx01": "codex-owned"})

    assert resolve_owned_postgres_container(
        run=lambda *args, **kwargs: result,
        which=lambda _: "docker.exe",
    ) == "cx01-pg"


def _archiver_failure_classifier():
    module = runpy.run_path(
        str(Path(__file__).resolve().parent / "integration" / "test_recovery_drill.py")
    )
    return module["_classify_archiver_connection_failure"]


def _archiver_probe(state, logs, *, inspect_return=0, logs_return=0, port_bindings=None):
    name = "sv-rpo-test"
    payload = [{
        "Config": {"Labels": {"ai.saintvision.rpo-test": name}},
        "State": state,
        "RestartCount": state.get("RestartCount", 0),
        "HostConfig": {"PortBindings": port_bindings or {}},
    }]

    def run(argv, **kwargs):
        if argv[1] == "inspect":
            return SimpleNamespace(
                returncode=inspect_return,
                stdout=json.dumps(payload).encode(),
                stderr=b"inspect failed" if inspect_return else b"",
            )
        if argv[1] == "logs":
            return SimpleNamespace(
                returncode=logs_return,
                stdout=logs.encode(),
                stderr=b"logs failed" if logs_return else b"",
            )
        raise AssertionError("unexpected Docker command: " + " ".join(argv))

    return name, run


def test_running_ready_internal_archiver_is_a_reasoned_host_network_skip():
    classify = _archiver_failure_classifier()
    name, run = _archiver_probe(
        {"Status": "running", "Running": True, "Restarting": False, "ExitCode": 0, "RestartCount": 0},
        "database system is ready to accept connections",
    )

    with pytest.raises(pytest.skip.Exception, match="internal network has no published host port"):
        classify(name, run=run)


def test_exited_archiver_with_startup_error_is_failure_not_skip():
    classify = _archiver_failure_classifier()
    name, run = _archiver_probe(
        {"Status": "exited", "Running": False, "Restarting": False, "ExitCode": 1, "RestartCount": 0},
        "FATAL: data directory permission denied",
    )

    with pytest.raises(AssertionError, match=r"startup failed:.*exitCode=1.*FATAL: data directory permission denied"):
        classify(name, run=run)


def test_postgresql_error_marker_cannot_be_overridden_by_a_later_ready_line():
    classify = _archiver_failure_classifier()
    name, run = _archiver_probe(
        {"Status": "running", "Running": True, "Restarting": False, "ExitCode": 0, "RestartCount": 0},
        "FATAL: startup configuration failed\ndatabase system is ready to accept connections",
    )

    with pytest.raises(AssertionError, match="PostgreSQL startup reported an error: FATAL:"):
        classify(name, run=run)


def test_restarted_archiver_is_failure_even_if_latest_logs_include_ready():
    classify = _archiver_failure_classifier()
    name, run = _archiver_probe(
        {"Status": "running", "Running": True, "Restarting": False, "ExitCode": 0, "RestartCount": 2},
        "database system is ready to accept connections",
    )

    with pytest.raises(AssertionError, match=r"startup failed:.*restartCount=2"):
        classify(name, run=run)


def test_running_archiver_without_ready_or_error_marker_is_unclassified_failure():
    classify = _archiver_failure_classifier()
    name, run = _archiver_probe(
        {"Status": "running", "Running": True, "Restarting": False, "ExitCode": 0, "RestartCount": 0},
        "database system is starting",
    )

    with pytest.raises(AssertionError, match="neither PostgreSQL-ready nor a startup-error marker"):
        classify(name, run=run)


def test_archiver_inspect_or_logs_failure_is_not_misreported_as_network_skip():
    classify = _archiver_failure_classifier()
    name, run = _archiver_probe(
        {"Status": "running", "Running": True, "Restarting": False, "ExitCode": 0, "RestartCount": 0},
        "database system is ready to accept connections",
        inspect_return=1,
    )
    with pytest.raises(AssertionError, match="docker inspect returned 1"):
        classify(name, run=run)

    name, run = _archiver_probe(
        {"Status": "running", "Running": True, "Restarting": False, "ExitCode": 0, "RestartCount": 0},
        "database system is ready to accept connections",
        logs_return=1,
    )
    with pytest.raises(AssertionError, match="docker logs returned 1"):
        classify(name, run=run)


def test_archiver_classifier_command_spawn_failures_are_not_skips():
    classify = _archiver_failure_classifier()

    def inspect_timeout(argv, **kwargs):
        raise TimeoutError("inspect timeout detail suppressed")

    with pytest.raises(AssertionError, match=r"docker inspect failed \(TimeoutError\)"):
        classify("sv-rpo-test", run=inspect_timeout)

    name, unused = _archiver_probe(
        {"Status": "running", "Running": True, "Restarting": False, "ExitCode": 0, "RestartCount": 0},
        "database system is ready to accept connections",
    )

    def logs_timeout(argv, **kwargs):
        if argv[1] == "inspect":
            return unused(argv, **kwargs)
        raise TimeoutError("logs timeout detail suppressed")

    with pytest.raises(AssertionError, match=r"docker logs failed \(TimeoutError\)"):
        classify(name, run=logs_timeout)


def test_ready_archiver_with_published_host_port_is_failure_not_internal_network_skip():
    classify = _archiver_failure_classifier()
    name, run = _archiver_probe(
        {"Status": "running", "Running": True, "Restarting": False, "ExitCode": 0, "RestartCount": 0},
        "database system is ready to accept connections",
        port_bindings={"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": "54321"}]},
    )

    with pytest.raises(AssertionError, match="with a published host port, but host connection still failed"):
        classify(name, run=run)
