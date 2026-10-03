"""Compose must refuse missing deployment credentials before starting services."""

import os
import json
from pathlib import Path
import shutil
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[2]
REQUIRED = {
    "INV_BUSINESS_DSN": "postgresql+psycopg://example:example@postgres/saintvision",
    "INV_RUNTIME_DSN": "postgresql://kernel:example@postgres/saintvision",
    "INV_RECOVERY_EPOCH": "11111111-1111-4111-8111-111111111111",
    "INV_CONFIG_VOLUME": "synthetic-config-volume",
    "INV_WORKER_CONFIG_VOLUME": "synthetic-worker-config-volume",
    "INV_WEB_AUTH_CONFIG": "./synthetic-auth-config.js",
    "POSTGRES_PASSWORD": "synthetic-admin-only",
    "MINIO_ROOT_USER": "synthetic-admin",
    "SAINTVISION_DEV_CERT_DIR": "C:/SaintVision/secrets/saintvision-dev",
    "MINIO_ROOT_PASSWORD": "synthetic-storage-only",
}


@pytest.mark.parametrize("missing", [None, *REQUIRED])
def test_compose_requires_explicit_credentials(tmp_path, missing):
    if not shutil.which("docker"):
        pytest.skip("Docker Compose unavailable")
    if subprocess.run(["docker", "compose", "version"], capture_output=True).returncode:
        pytest.skip("Docker Compose unavailable")
    env = dict(os.environ)
    for key in REQUIRED:
        env.pop(key, None)
    env.update({k: v for k, v in REQUIRED.items() if k != missing})
    empty = tmp_path / "empty.env"
    empty.write_text("")
    result = subprocess.run(
        [
            "docker",
            "compose",
            "--env-file",
            str(empty),
            "-f",
            str(ROOT / "docker-compose.prod.yml"),
            "config",
            "--quiet",
        ],
        env=env,
        capture_output=True,
        timeout=30,
    )
    assert (result.returncode == 0) == (missing is None)
    if missing:
        assert missing.encode() in result.stderr


@pytest.mark.parametrize("volume", [None, "synthetic-preprovisioned-volume"])
def test_workspace_overlay_requires_external_volume(tmp_path, volume):
    if not shutil.which("docker"):
        pytest.skip("Docker Compose unavailable")
    env = {**os.environ, **REQUIRED}
    env.pop("INV_WORKSPACE_VOLUME", None)
    if volume:
        env["INV_WORKSPACE_VOLUME"] = volume
    empty = tmp_path / "empty.env"
    empty.write_text("")
    result = subprocess.run(
        [
            "docker",
            "compose",
            "--env-file",
            str(empty),
            "-f",
            str(ROOT / "docker-compose.prod.yml"),
            "-f",
            str(ROOT / "docker-compose.workspace.yml"),
            "config",
            "--format",
            "json",
        ],
        env=env,
        capture_output=True,
        timeout=30,
    )
    if volume is None:
        assert result.returncode != 0 and b"INV_WORKSPACE_VOLUME" in result.stderr
        return
    assert result.returncode == 0
    config = json.loads(result.stdout)
    auth_mount = next(
        v
        for v in config["services"]["web"]["volumes"]
        if v["target"] == "/usr/share/nginx/html/auth-config.js"
    )
    assert auth_mount["type"] == "bind" and auth_mount["read_only"] is True
    # Compose omits false booleans in its normalized JSON output.
    assert auth_mount.get("bind", {}).get("create_host_path", False) is False
    assert config["volumes"]["workspace_data"]["external"] is True
    assert config["volumes"]["workspace_data"]["name"] == volume
    backend = config["services"]["control-plane"]
    assert backend["environment"]["INV_BUSINESS_DSN"] == REQUIRED["INV_BUSINESS_DSN"]
    assert "INV_DATABASE_URL" not in backend["environment"]
    mount = next(v for v in backend["volumes"] if v["target"] == "/workspaces")
    assert mount["volume"]["nocopy"] is True


def test_tls_file_mounts_never_create_host_directories():
    import yaml

    compose = yaml.safe_load((ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8"))
    mounts = compose["services"]["web"]["volumes"]
    tls = {
        mount["target"]: mount
        for mount in mounts
        if isinstance(mount, dict)
        and mount.get("target", "").endswith(("saintvision.crt", "saintvision.key"))
    }
    assert set(tls) == {"/etc/ssl/certs/saintvision.crt", "/etc/ssl/private/saintvision.key"}
    for mount in tls.values():
        assert mount["type"] == "bind"
        assert mount["read_only"] is True
        assert mount["bind"]["create_host_path"] is False


def test_tls_file_mounts_require_external_certificate_directory():
    import yaml

    compose = yaml.safe_load((ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8"))
    mounts = compose["services"]["web"]["volumes"]
    tls_sources = {
        mount["target"]: mount["source"]
        for mount in mounts
        if isinstance(mount, dict)
        and mount.get("target", "").endswith(("saintvision.crt", "saintvision.key"))
    }
    assert tls_sources == {
        "/etc/ssl/certs/saintvision.crt": "${SAINTVISION_DEV_CERT_DIR:?Set an existing external development TLS certificate directory}/saintvision.crt",
        "/etc/ssl/private/saintvision.key": "${SAINTVISION_DEV_CERT_DIR:?Set an existing external development TLS certificate directory}/saintvision.key",
    }


def test_worker_service_is_private_configured_and_build_dispatch_defaults_off():
    import yaml

    compose = yaml.safe_load((ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8"))
    worker = compose["services"]["worker"]
    assert worker["command"] == ["python", "-m", "inv.worker"]
    assert "ports" not in worker
    environment = worker["environment"]
    assert environment.count("INV_WORKER_CONFIG=/run/saintvision-worker/worker.json") == 1
    assert environment.count("INV_API_CONFIG=/run/saintvision/api.json") == 1
    build_flags = [item for item in environment if item.startswith("INV_BUILDKIT_PRODUCT_ENABLED=")]
    assert build_flags == ["INV_BUILDKIT_PRODUCT_ENABLED=${INV_BUILDKIT_PRODUCT_ENABLED:-0}"]
    assert not any(item.startswith("INV_BUSINESS_DSN=") for item in environment)
    mounts = {item["target"]: item for item in worker["volumes"]}
    assert set(mounts) == {"/run/saintvision", "/run/saintvision-worker"}
    assert mounts["/run/saintvision"]["source"] == "api_config"
    assert mounts["/run/saintvision-worker"]["source"] == "worker_config"
    assert all(
        mount["read_only"] is True and mount["volume"]["nocopy"] is True
        for mount in mounts.values()
    )
    control = compose["services"]["control-plane"]
    assert "INV_WORKER_CONFIG" not in "\n".join(control["environment"])
    control_mounts = {item["target"]: item for item in control["volumes"]}
    assert set(control_mounts) == {"/run/saintvision"}
    assert control_mounts["/run/saintvision"]["source"] == "api_config"
    assert worker["depends_on"]["postgres"]["condition"] == "service_healthy"


@pytest.mark.parametrize(
    "overlays",
    [
        (),
        ("docker-compose.workspace.yml",),
        ("docker-compose.pitr.yml",),
        ("docker-compose.workspace.yml", "docker-compose.pitr.yml"),
    ],
)
def test_rendered_compose_limits_config_volumes_to_intended_services(tmp_path, overlays):
    if not shutil.which("docker"):
        pytest.skip("Docker Compose unavailable")
    if subprocess.run(["docker", "compose", "version"], capture_output=True).returncode:
        pytest.skip("Docker Compose unavailable")
    empty = tmp_path / "empty.env"
    empty.write_text("")
    compose_files = [ROOT / "docker-compose.prod.yml", *(ROOT / item for item in overlays)]
    command = ["docker", "compose", "--env-file", str(empty)]
    for compose_file in compose_files:
        command.extend(["-f", str(compose_file)])
    command.extend(["config", "--format", "json"])
    result = subprocess.run(
        command,
        env={
            **os.environ,
            **REQUIRED,
            "INV_WORKSPACE_VOLUME": "synthetic-workspace-volume",
            "INV_WAL_ARCHIVE_VOLUME": "synthetic-wal-archive-volume",
        },
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    config = json.loads(result.stdout)
    api_consumers = set()
    worker_consumers = set()
    for service_name, service in config["services"].items():
        mounts = service.get("volumes", [])
        api_mounts = [mount for mount in mounts if mount["target"] == "/run/saintvision"]
        worker_mounts = [
            mount
            for mount in mounts
            if mount["target"] == "/run/saintvision-worker"
            or mount.get("source") == REQUIRED["INV_WORKER_CONFIG_VOLUME"]
        ]
        if api_mounts:
            api_consumers.add(service_name)
            assert len(api_mounts) == 1 and api_mounts[0]["read_only"] is True
        if worker_mounts:
            worker_consumers.add(service_name)
            assert len(worker_mounts) == 1
            assert worker_mounts[0]["target"] == "/run/saintvision-worker"
            assert worker_mounts[0]["read_only"] is True
    assert api_consumers == {"control-plane", "worker"}
    assert worker_consumers == {"worker"}
    assert config["volumes"]["api_config"]["name"] == REQUIRED["INV_CONFIG_VOLUME"]
    assert config["volumes"]["worker_config"]["name"] == REQUIRED["INV_WORKER_CONFIG_VOLUME"]
