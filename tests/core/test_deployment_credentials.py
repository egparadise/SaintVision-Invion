"""Compose must refuse missing deployment credentials before starting services."""
import os
from pathlib import Path
import shutil
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[2]
REQUIRED = {"INV_DATABASE_URL": "postgresql://example:example@postgres/saintvision",
            "POSTGRES_PASSWORD": "synthetic-admin-only", "MINIO_ROOT_USER": "synthetic-admin",
            "MINIO_ROOT_PASSWORD": "synthetic-storage-only"}


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
    result = subprocess.run(["docker", "compose", "--env-file", str(empty), "-f",
                             str(ROOT / "docker-compose.prod.yml"), "config", "--quiet"],
                            env=env, capture_output=True, timeout=30)
    assert (result.returncode == 0) == (missing is None)
    if missing:
        assert missing.encode() in result.stderr
