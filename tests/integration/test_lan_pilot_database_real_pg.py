from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import uuid

import pytest

ROOT = Path(__file__).resolve().parents[2]
PREPARE = ROOT / "deploy" / "lan" / "prepare-pilot-database.sh"
VERIFY = ROOT / "deploy" / "lan" / "verify-pilot-database.sh"
IMAGE = os.environ.get("INV_TEST_LAN_DATABASE_IMAGE", "")


pytestmark = pytest.mark.skipif(
    not IMAGE or os.name == "nt" or shutil.which("docker") is None,
    reason="explicit hosted Linux PostgreSQL image is required",
)


def _run(*args: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*args],
        cwd=ROOT,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )


def _free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _owned(container: str, network: str) -> None:
    assert (
        _run(
            "docker",
            "container",
            "inspect",
            "--format",
            '{{index .Config.Labels "ai.saintvision.lan-pilot"}}',
            container,
        ).stdout.strip()
        == "card150"
    )
    assert (
        _run(
            "docker",
            "network",
            "inspect",
            "--format",
            '{{index .Labels "ai.saintvision.lan-pilot"}}',
            network,
        ).stdout.strip()
        == "card150"
    )


def test_prepare_verify_roundtrip_uses_real_psql_variable_semantics(tmp_path: Path) -> None:
    suffix = uuid.uuid4().hex[:10]
    container = f"saintvision-card297-{suffix}"
    network = f"saintvision-card297-{suffix}-network"
    database = f"saintvision_lan_card297_{suffix}"
    runtime_role = f"inv_lan_runtime_card297_{suffix}"
    volume = f"{container}-data"
    private_dir = tmp_path / "operator-private"
    port = _free_port()

    try:
        bootstrapped = _run(
            "bash",
            str(PREPARE),
            IMAGE,
            container,
            str(port),
            str(private_dir),
            network,
            "saintvision_lan",
        )
        assert bootstrapped.returncode == 0, "initial prepare failed with redacted diagnostics"

        # Reuse the already-hardened container while creating an isolated r3 database.
        prepared = _run(
            "bash",
            str(PREPARE),
            IMAGE,
            container,
            str(port),
            str(private_dir),
            network,
            database,
        )
        assert prepared.returncode == 0, "prepare failed with redacted diagnostics"
        prepare_receipt = json.loads(prepared.stdout)
        assert prepare_receipt["databaseName"] == database
        assert prepare_receipt["runtimeRole"] == runtime_role

        verified = _run("bash", str(VERIFY), container, network, database, str(private_dir))
        assert verified.returncode == 0, "verify failed with redacted diagnostics"
        receipt = json.loads(verified.stdout)
        assert receipt["databaseName"] == database
        assert receipt["runtimeRole"] == runtime_role
        assert receipt["missingCredentialRejected"] is True
        assert receipt["wrongCredentialRejected"] is True
        assert receipt["hostAuthentication"] == "scram-sha-256"

        scram = _run(
            "docker",
            "exec",
            "-i",
            container,
            "sh",
            "-ec",
            'PGPASSWORD=$(cat /run/secrets/postgres-password); export PGPASSWORD; exec psql -U postgres -d "$1" -v runtime_role="$2" -At',
            "_",
            database,
            runtime_role,
            input_text="SELECT rolpassword LIKE 'SCRAM-SHA-256$%' FROM pg_authid WHERE rolname = :'runtime_role';\n",
        )
        assert scram.returncode == 0 and scram.stdout.strip() == "t"

        # Exact regression mutant: psql does not expand -v variables inside -c.
        broken_c = _run(
            "docker",
            "exec",
            "-i",
            container,
            "sh",
            "-ec",
            'PGPASSWORD=$(cat /run/secrets/postgres-password); export PGPASSWORD; exec psql -U postgres -d "$1" -v runtime_role="$2" -Atqc "$3"',
            "_",
            database,
            runtime_role,
            "SELECT count(*) FROM pg_roles WHERE rolname = :'runtime_role'",
        )
        assert broken_c.returncode != 0

        elevated = _run(
            "docker",
            "exec",
            "-i",
            container,
            "sh",
            "-ec",
            'PGPASSWORD=$(cat /run/secrets/postgres-password); export PGPASSWORD; exec psql -U postgres -d "$1" -v ON_ERROR_STOP=1 -v runtime_role="$2"',
            "_",
            database,
            runtime_role,
            input_text="SELECT format('ALTER ROLE %I SUPERUSER', :'runtime_role') \\gexec\n",
        )
        assert elevated.returncode == 0
        rejected = _run("bash", str(VERIFY), container, network, database, str(private_dir))
        assert rejected.returncode == 1
        assert rejected.stderr.strip() == "Pilot runtime role has elevated privileges."
    finally:
        if _run("docker", "container", "inspect", container).returncode == 0:
            _owned(container, network)
            assert _run("docker", "rm", "--force", container).returncode == 0
        if _run("docker", "network", "inspect", network).returncode == 0:
            assert _run("docker", "network", "rm", network).returncode == 0
        if _run("docker", "volume", "inspect", volume).returncode == 0:
            assert _run("docker", "volume", "rm", volume).returncode == 0
