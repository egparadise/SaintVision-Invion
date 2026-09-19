"""Fail-closed Docker ownership preconditions for recovery-drill integration tests."""

from __future__ import annotations

import json
import os
import shutil
import subprocess

import pytest


def resolve_owned_postgres_container(*, run=subprocess.run, which=shutil.which) -> str:
    """Resolve only an explicitly named disposable test container.

    Missing execution prerequisites are visible skips. An existing container with
    no recognized test-owner labels is a safety failure, never a skip.
    """
    name = os.getenv("CX01_CONTAINER", "").strip()
    if not name:
        pytest.skip(
            "CX01_CONTAINER is unset; container identity/ownership cannot be verified"
        )
    if which("docker") is None:
        pytest.skip("Docker CLI is unavailable; cannot inspect the configured test container")

    try:
        result = run(["docker", "inspect", name], capture_output=True, timeout=20)
    except FileNotFoundError:
        pytest.skip("Docker CLI disappeared before inspect; configured container was not checked")
    except subprocess.TimeoutExpired:
        pytest.skip("Docker inspect timed out; container availability is unverified")
    except PermissionError:
        pytest.skip("Permission denied launching Docker inspect; container ownership is unverified")
    except OSError as exc:
        pytest.fail(
            "Docker inspect process failed unexpectedly "
            f"({type(exc).__name__}); refusing to classify an unknown error as a skip"
        )

    stderr = (
        result.stderr.decode("utf-8", errors="replace")
        if isinstance(result.stderr, bytes)
        else (result.stderr or "")
    )
    if result.returncode != 0:
        lower = stderr.lower()
        if "no such object" in lower or "no such container" in lower:
            pytest.skip("Configured CX01_CONTAINER is absent; recovery-drill container prerequisite is unavailable")
        daemon_unavailable = (
            "cannot connect to the docker daemon" in lower
            or "is the docker daemon running" in lower
            or "error during connect" in lower
        )
        if daemon_unavailable:
            pytest.skip("Docker daemon is unavailable; configured container ownership was not checked")
        pytest.fail(
            f"Docker inspect failed for configured CX01_CONTAINER (exit {result.returncode}); "
            "refusing to treat an unknown inspect error as a skip"
        )

    stdout = (
        result.stdout.decode("utf-8", errors="replace")
        if isinstance(result.stdout, bytes)
        else (result.stdout or "")
    )
    try:
        inspected = json.loads(stdout)
    except (TypeError, json.JSONDecodeError):
        pytest.fail("Docker inspect returned invalid JSON for configured CX01_CONTAINER")
    if not isinstance(inspected, list) or len(inspected) != 1 or not isinstance(inspected[0], dict):
        pytest.fail("Docker inspect did not return exactly one configured container")
    labels = (inspected[0].get("Config") or {}).get("Labels") or {}
    if not isinstance(labels, dict):
        pytest.fail("Configured container has malformed Docker labels")

    cx01_owned = bool(labels.get("ai.saintvision.cx01"))
    kernel_owned = bool(labels.get("ai.saintvision.kernel-test"))
    codex_db_owned = bool(labels.get("ai.saintvision.codex-db-test")) and labels.get(
        "ai.saintvision.created-by"
    ) == "codex"
    if not (cx01_owned or kernel_owned or codex_db_owned):
        pytest.fail(
            "Configured container exists but lacks a recognized disposable-test owner label; "
            "refusing to run recovery drills against an unowned/foreign resource"
        )
    return name
