"""Card 266 r3 (Codex r2 F3): the production composition actually starts.

The earlier tests called ``configured_storage_sample_collector`` directly, which
proves the factory and proves nothing about whether a real settings file can reach
it. This one goes through ``create_configured_app()`` with a settings file, real
test PKI and the business surface, and asserts the route is registered -- so
removing ``storageSample`` from the strict allow-list, or dropping the route, fails
here rather than in a deployment.
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from psycopg.conninfo import conninfo_to_dict
from sqlalchemy.engine import URL

from inv.app import create_configured_app
from jwt_support import jwt_fixture
from pki_support import authority, credentials, issue
from test_server_container import business_login  # noqa: F401  (fixture)

pytestmark = pytest.mark.postgres

ROUTE = "/v1/projects/{project_id}/runs/{run_id}/storage-samples"


def _settings(tmp_path, env, identity, *, storage_sample=True):
    """A settings file of the shape production reads, with real PKI on disk."""
    ca = authority()
    peer = issue(ca, "spiffe://inv/test/collector")
    files = credentials(tmp_path, ca, peer, prefix="collector")
    body = {
        "identity": {
            "tenant_id": env.tenant,
            "issuer": identity.issuer,
            "audience": identity.audience,
            "client_ids": ["synthetic-web"],
            "jwks_file": str(identity.path),
        },
        "business": True,
    }
    if storage_sample:
        body["storageSample"] = {
            "caFile": str(files["ca_file"]),
            "certificateFile": str(files["certificate_file"]),
            "keyFile": str(files["key_file"]),
        }
    config = tmp_path / "api.json"
    config.write_text(json.dumps(body), encoding="utf-8")
    config.chmod(0o600)
    return config


def _environment(monkeypatch, env, business_login, config):
    info = conninfo_to_dict(env.runtime)
    role, password = business_login
    business_dsn = URL.create(
        "postgresql+psycopg", username=role, password=password,
        host=info["host"], port=int(info["port"]), database=info["dbname"],
    )
    monkeypatch.setenv("INV_API_CONFIG", str(config))
    monkeypatch.setenv("INV_RUNTIME_DSN", env.runtime)
    monkeypatch.setenv("INV_RECOVERY_EPOCH", env.epoch)
    monkeypatch.setenv("INV_BUSINESS_DSN", business_dsn.render_as_string(hide_password=False))


def _routes(api):
    return {getattr(route, "path", None) for route in api.routes}


def test_the_configured_app_starts_with_storage_sample_and_registers_the_route(
    tmp_path, env, business_login, monkeypatch
):
    """The whole point of F3: a settings file carrying ``storageSample`` must start.

    Before the allow-list fix this raised at startup, and without the key the route
    existed but could only answer 503 -- a branch no deployment could reach. Both
    halves are asserted here: it starts, and the route is on the app.
    """
    identity = jwt_fixture(tmp_path, env.tenant)
    config = _settings(tmp_path, env, identity, storage_sample=True)
    _environment(monkeypatch, env, business_login, config)
    api = create_configured_app()
    assert ROUTE in _routes(api)
    # A real project and Run, so the request reaches the collector's own judgement
    # rather than an infrastructure error on an id that names nothing. No grant
    # exists for this subject, so the honest answer is the project refusal -- which
    # only a *built* collector can give.
    run = env.runs.create(env.tenant, env.project)
    with TestClient(api) as client:
        response = client.post(
            ROUTE.format(project_id=env.project, run_id=run["runId"]),
            json={"contributionId": "stc_" + "0" * 26},
            headers={
                "Authorization": "Bearer " + identity.token(),
                "Idempotency-Key": "startup-k1",
            },
        )
    assert response.status_code == 403, response.text
    assert response.json()["code"] == "AUTH-0030"


def test_the_same_settings_without_storage_sample_still_starts_and_answers_503(
    tmp_path, env, business_login, monkeypatch
):
    """The other side of the allow-list: the block is optional, and its absence is
    a 503 rather than a crash -- a deployment that has not configured the mTLS
    material must come up and refuse, not fail to start."""
    identity = jwt_fixture(tmp_path, env.tenant)
    config = _settings(tmp_path, env, identity, storage_sample=False)
    _environment(monkeypatch, env, business_login, config)
    api = create_configured_app()
    assert ROUTE in _routes(api)
    with TestClient(api) as client:
        response = client.post(
            ROUTE.format(project_id="prj_" + "0" * 26, run_id="run_" + "0" * 26),
            json={"contributionId": "stc_" + "0" * 26},
            headers={
                "Authorization": "Bearer " + identity.token(),
                "Idempotency-Key": "startup-k2",
            },
        )
    assert response.status_code == 503, response.text
    assert response.json()["code"] == "SYS-0001"


def test_an_unknown_key_in_the_block_refuses_to_start(
    tmp_path, env, business_login, monkeypatch
):
    """Strict means strict: an extra key is a configuration error at startup."""
    identity = jwt_fixture(tmp_path, env.tenant)
    config = _settings(tmp_path, env, identity, storage_sample=True)
    body = json.loads(config.read_text(encoding="utf-8"))
    body["storageSample"]["unexpected"] = "x"
    config.write_text(json.dumps(body), encoding="utf-8")
    _environment(monkeypatch, env, business_login, config)
    with pytest.raises(RuntimeError, match="configuration unavailable"):
        create_configured_app()


def test_a_configured_collector_without_the_business_surface_refuses_to_start(
    tmp_path, env, business_login, monkeypatch
):
    """The collector needs the app-role engine for the boundary read and for the
    denial recorder, so ``storageSample`` without ``business`` must not come up."""
    identity = jwt_fixture(tmp_path, env.tenant)
    config = _settings(tmp_path, env, identity, storage_sample=True)
    body = json.loads(config.read_text(encoding="utf-8"))
    del body["business"]
    config.write_text(json.dumps(body), encoding="utf-8")
    _environment(monkeypatch, env, business_login, config)
    with pytest.raises(RuntimeError, match="configuration unavailable"):
        create_configured_app()


def test_unreadable_tls_material_refuses_to_start_rather_than_degrade(
    tmp_path, env, business_login, monkeypatch
):
    """A path that is not usable TLS material is a startup failure, not a route
    that quietly answers 503 forever."""
    identity = jwt_fixture(tmp_path, env.tenant)
    config = _settings(tmp_path, env, identity, storage_sample=True)
    body = json.loads(config.read_text(encoding="utf-8"))
    missing = tmp_path / "absent-ca.pem"
    body["storageSample"]["caFile"] = str(missing)
    config.write_text(json.dumps(body), encoding="utf-8")
    _environment(monkeypatch, env, business_login, config)
    with pytest.raises(RuntimeError, match="configuration unavailable"):
        create_configured_app()
