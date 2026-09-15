"""Production factory over real loopback HTTP and isolated PostgreSQL.

Synthetic issuer; this does not certify an operational identity provider.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from uuid import uuid4

import httpx
import psycopg
import pytest
from jwt_support import jwt_fixture

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.postgres


@contextmanager
def running_server(env, tmp_path, identity, *, epoch=None, allowed_origins=(), business=False):
    config = tmp_path / "api.json"
    config.write_text(json.dumps({"identity": {
        "tenant_id": env.tenant, "issuer": identity.issuer,
        "audience": identity.audience, "client_ids": ["synthetic-web"],
        "jwks_file": str(identity.path),
    }, "allowedOrigins": list(allowed_origins), **({"business": True} if business else {})}), encoding="utf-8")
    config.chmod(0o600)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    child_env = {**os.environ, "INV_API_CONFIG": str(config),
                 "INV_RUNTIME_DSN": env.runtime,
                 "INV_RECOVERY_EPOCH": epoch or env.epoch,
                 "PYTHONPATH": os.pathsep.join(str(ROOT / p) for p in
                                               ("src", "services/control-plane/src"))}
    # DSN stays in the environment; no credential-bearing diagnostics on failure.
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "saintvision.server:create_app", "--factory",
         "--host", "127.0.0.1", "--port", str(port), "--no-access-log", "--no-proxy-headers"],
        cwd=ROOT, env=child_env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False, timeout=3) as client:
            for _ in range(100):
                assert process.poll() is None, "Configured server exited before liveness"
                try:
                    if client.get("/healthz").status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                time.sleep(0.1)
            else:
                pytest.fail("Configured server did not become live")
            yield client
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)


def test_configured_http_authentication_and_database_grants(env, tmp_path):
    identity = jwt_fixture(tmp_path, env.tenant)
    with psycopg.connect(env.owner) as conn:
        conn.execute("INSERT INTO inv.project_grants"
                     "(tenant_id,project_id,subject_id,can_request,can_approve)"
                     " VALUES(%s,%s,%s,true,false)",
                     (env.tenant, env.project, identity.subject("requester")))
    with running_server(env, tmp_path, identity) as client:
        ready = client.get("/readyz")
        assert ready.status_code == 200
        assert ready.json()["workspaceAdmission"] == "not_configured"
        assert client.get("/v1/projects").status_code == 401
        assert client.get("/v1/projects", headers={"Authorization": "Bearer invalid"}).status_code == 401
        response = client.get("/v1/projects", headers={"Authorization": "Bearer " + identity.token()})
        assert response.status_code == 200
        assert response.json() == {"items": [{"projectId": env.project}]}
        response = client.get("/v1/projects", headers={"Authorization": "Bearer " + identity.token("outsider")})
        assert response.status_code == 200 and response.json() == {"items": []}
        # Same process must observe revoked grants, rather than serve a seeded/cache list.
        with psycopg.connect(env.owner) as conn:
            conn.execute("UPDATE inv.project_grants SET enabled=false WHERE tenant_id=%s", (env.tenant,))
        assert client.get("/v1/projects", headers={"Authorization": "Bearer " + identity.token()}).json() == {"items": []}


def test_configured_http_stale_epoch_is_live_but_not_ready(env, tmp_path):
    identity = jwt_fixture(tmp_path, env.tenant)
    with running_server(env, tmp_path, identity, epoch=str(uuid4())) as client:
        assert client.get("/healthz").status_code == 200
        response = client.get("/readyz")
        assert response.status_code == 503 and response.json()["code"] == "LEASE-0004"


def test_configured_http_trust_expiry_stops_readiness(env, tmp_path):
    identity = jwt_fixture(tmp_path, env.tenant)
    with running_server(env, tmp_path, identity) as client:
        assert client.get("/readyz").status_code == 200
        identity.bundle["expiresAt"] = int(time.time()) - 1
        identity.path.write_text(json.dumps(identity.bundle), encoding="utf-8")
        assert client.get("/healthz").status_code == 200
        assert client.get("/readyz").status_code == 503
        assert client.get("/v1/projects", headers={"Authorization": "Bearer " + identity.token()}).status_code == 401
