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
