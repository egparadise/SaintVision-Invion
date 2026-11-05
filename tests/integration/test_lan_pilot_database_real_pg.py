from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time
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


def test_prepare_waits_for_final_tcp_after_temporary_unix_server(tmp_path: Path) -> None:
    """Pause the shipped init flow before target DB creation, without faking PG."""
    suffix = uuid.uuid4().hex[:10]
    container = f"saintvision-readiness-{suffix}"
    network = f"{container}-network"
    database = f"saintvision_lan_readiness_{suffix}"
    private_dir = tmp_path / "operator-private"
    gate = tmp_path / "gate"
    gate.mkdir(mode=0o777)
    gate.chmod(0o777)  # The disposable image's postgres user writes only phase markers.
    hook = tmp_path / "delayed-entrypoint.sh"
    hook.write_text(
        """#!/usr/bin/env bash
set -Eeo pipefail
source /usr/local/bin/docker-entrypoint.sh
if [[ "$(id -u)" == 0 ]]; then
    docker_setup_env
    docker_create_db_directories
    exec gosu postgres "$0" "$@"
fi
# Retain the image's actual DB-creation implementation and intercept only its call.
eval "$(declare -f docker_setup_db | sed '1s/docker_setup_db/readiness_original_setup_db/')"
docker_setup_db() {
    touch /readiness-gate/temporary-unix-ready
    for ((attempt=0; attempt<300; attempt++)); do
        if [[ -f /readiness-gate/release ]]; then
            readiness_original_setup_db "$@"
            return
        fi
        sleep 0.1
    done
    return 98
}
_main "$@"
""",
        encoding="utf-8",
    )
    hook.chmod(0o755)
    real_docker = shutil.which("docker")
    assert real_docker is not None
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    shim = fake_bin / "docker"
    shim.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
if [[ "$1" == run ]]; then
    shift
    exec "$READINESS_REAL_DOCKER" run \
        --entrypoint /readiness-entrypoint.sh \
        --mount "type=bind,source=$READINESS_HOOK,target=/readiness-entrypoint.sh,readonly" \
        --mount "type=bind,source=$READINESS_GATE,target=/readiness-gate" "$@" postgres
fi
exec "$READINESS_REAL_DOCKER" "$@"
""",
        encoding="utf-8",
    )
    shim.chmod(0o700)
    report: dict[str, object] = {
        "image": IMAGE,
        "prepareSha256": hashlib.sha256(PREPARE.read_bytes()).hexdigest(),
        "hookSha256": hashlib.sha256(hook.read_bytes()).hexdigest(),
        "temporaryUnixSql": False,
        "temporaryTcpRejected": False,
        "targetDatabaseAbsent": False,
        "pendingBeforeRelease": False,
        "cleanup": "pending",
    }
    process = subprocess.Popen(
        ["bash", str(PREPARE), IMAGE, container, str(_free_port()), str(private_dir), network, database],
        cwd=ROOT,
        env={
            **os.environ,
            "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
            "READINESS_REAL_DOCKER": real_docker,
            "READINESS_HOOK": str(hook),
            "READINESS_GATE": str(gate),
        },
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    def query(host: str, db: str, sql: str) -> subprocess.CompletedProcess[str]:
        return _run(
            real_docker, "exec", container, "sh", "-ec",
            'PGPASSWORD=$(cat /run/secrets/postgres-password); export PGPASSWORD; '
            'export PGCONNECT_TIMEOUT=2; exec psql -w -h "$1" -U postgres -d "$2" -Atqc "$3"',
            "_", host, db, sql,
        )

    try:
        deadline = time.monotonic() + 45
        while not (gate / "temporary-unix-ready").exists() and time.monotonic() < deadline:
            assert process.poll() is None, "prepare exited before controlled init phase"
            time.sleep(0.1)
        assert (gate / "temporary-unix-ready").exists(), "controlled init phase was not reached"
        _owned(container, network)
        image_id = _run(real_docker, "container", "inspect", "--format", "{{.Image}}", container)
        assert image_id.returncode == 0
        report["imageId"] = image_id.stdout.strip()
        entrypoint = _run(real_docker, "exec", container, "sha256sum", "/usr/local/bin/docker-entrypoint.sh")
        assert entrypoint.returncode == 0
        report["shippedEntrypointSha256"] = entrypoint.stdout.split()[0]
        unix = query("/var/run/postgresql", "postgres", "SELECT 1")
        tcp = query("127.0.0.1", "postgres", "SELECT 1")
        absent = query("/var/run/postgresql", "postgres", f"SELECT count(*) FROM pg_database WHERE datname = '{database}'")
        report["temporaryUnixSql"] = unix.returncode == 0 and unix.stdout.strip() == "1"
        report["temporaryTcpRejected"] = tcp.returncode != 0
        report["targetDatabaseAbsent"] = absent.returncode == 0 and absent.stdout.strip() == "0"
        assert report["temporaryUnixSql"] is True
        assert report["temporaryTcpRejected"] is True
        assert report["targetDatabaseAbsent"] is True
        # Give the real preparation loop several opportunities to encounter this phase.
        deadline = time.monotonic() + 4
        while process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.1)
        report["prepareExitBeforeRelease"] = process.poll()
        report["pendingBeforeRelease"] = process.poll() is None
        assert report["pendingBeforeRelease"] is True, "prepare crossed temporary Unix readiness before final TCP"
        (gate / "release").touch()
        stdout, _stderr = process.communicate(timeout=60)
        report["prepareExitAfterRelease"] = process.returncode
        assert process.returncode == 0, "prepare failed after final server release (diagnostics redacted)"
        assert json.loads(stdout)["databaseName"] == database
        final = query("127.0.0.1", database, "SELECT 1")
        report["finalTargetTcpSql"] = final.returncode == 0 and final.stdout.strip() == "1"
        assert report["finalTargetTcpSql"] is True
        verified = _run("bash", str(VERIFY), container, network, database, str(private_dir))
        report["verifyExit"] = verified.returncode
        assert verified.returncode == 0, "final role/authentication verification failed (diagnostics redacted)"
        receipt = json.loads(verified.stdout)
        assert receipt["wrongCredentialRejected"] is True
        assert receipt["missingCredentialRejected"] is True
        assert receipt["hostAuthentication"] == "scram-sha-256"
    finally:
        (gate / "release").touch()
        try:
            process.communicate(timeout=60)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate(timeout=10)
        report["prepareFinalExit"] = process.returncode
        try:
            if _run(real_docker, "container", "inspect", container).returncode == 0:
                _owned(container, network)
                mounts = _run(real_docker, "container", "inspect", "--format", "{{json .Mounts}}", container)
                assert mounts.returncode == 0
                assert any(m["Name"] == f"{container}-data" and m["Destination"] == "/var/lib/postgresql/data"
                           for m in json.loads(mounts.stdout) if m["Type"] == "volume")
                assert _run(real_docker, "rm", "--force", container).returncode == 0
                assert _run(real_docker, "volume", "rm", f"{container}-data").returncode == 0
                assert _run(real_docker, "network", "rm", network).returncode == 0
                for kind, name in (("container", container), ("volume", f"{container}-data"), ("network", network)):
                    assert _run(real_docker, kind, "inspect", name).returncode != 0
                report["cleanup"] = "owned-resources-removed-and-reinspected"
        finally:
            evidence_dir = os.environ.get("INV_TEST_EVIDENCE_DIR")
            if evidence_dir:
                destination = Path(evidence_dir) / "lan-database-readiness-phases.json"
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


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
