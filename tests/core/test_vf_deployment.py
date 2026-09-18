"""Compose boundary validation uses synthetic values and never starts services."""
import json
import os
from pathlib import Path
import subprocess
import shutil
import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def require_docker_cli():
    if not shutil.which("docker"):
        pytest.skip("Docker CLI is required for Compose configuration validation")


def compose_env():
    # Explicitly replace every deployment input; never expose ambient operator settings.
    return {**{k: v for k, v in os.environ.items() if not k.startswith(('INV_', 'POSTGRES_', 'MINIO_'))},
        'INV_WEB_AUTH_CONFIG': str(ROOT / 'README.md'), 'INV_CONFIG_VOLUME': 'vf-synthetic-only',
        'INV_BUSINESS_DSN': 'postgresql+psycopg://synthetic:synthetic@postgres/test',
        'INV_RUNTIME_DSN': 'postgresql://synthetic:synthetic@postgres/test',
        'INV_RECOVERY_EPOCH': '11111111-1111-1111-1111-111111111111',
        'POSTGRES_PASSWORD': 'synthetic-only', 'MINIO_ROOT_USER': 'synthetic',
        'MINIO_ROOT_PASSWORD': 'synthetic-only'}


def test_internal_services_are_not_published_on_all_interfaces():
    result = subprocess.run(['docker', 'compose', '-f', 'docker-compose.prod.yml', 'config', '--format', 'json'],
                            cwd=ROOT, env=compose_env(), capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, 'Synthetic Compose validation failed'
    services = json.loads(result.stdout)['services']
    for service in ('control-plane', 'postgres', 'minio'):
        assert all(p['host_ip'] == '127.0.0.1' for p in services[service]['ports'])


def test_missing_database_password_cannot_fall_back_to_a_default():
    env = compose_env()
    env['POSTGRES_PASSWORD'] = ''
    result = subprocess.run(['docker', 'compose', '-f', 'docker-compose.prod.yml', 'config', '--quiet'],
                            cwd=ROOT, env=env, capture_output=True, text=True, timeout=20)
    assert result.returncode != 0
    assert 'POSTGRES_PASSWORD' in result.stderr
