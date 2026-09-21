"""The tenant header on discovery announcements cannot override caller identity."""

import uuid

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from saintvision.api.v1 import pools
from saintvision.errors import InvError
from saintvision.identity.principal import Principal, StaticPrincipalVerifier


def _app(*, principal=None):
    app = FastAPI()
    app.include_router(pools.router)
    app.state.clock = lambda: None
    app.state.verifier = StaticPrincipalVerifier(
        {"synthetic-user-token": principal} if principal is not None else {}
    )

    @app.exception_handler(InvError)
    async def render_problem(_request, error):
        return JSONResponse(
            status_code=error.status,
            content={"code": error.code},
        )

    return app


def test_announcement_rejects_header_for_a_different_authenticated_tenant(monkeypatch):
    monkeypatch.setenv("INV_ENV", "test")
    tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
    principal = Principal(
        user_id="usr_test",
        tenant_id=tenant_a,
        external_subject="synthetic-user",
    )
    writes = []

    def record(*args, **kwargs):
        writes.append((args, kwargs))
        raise AssertionError("a mismatched tenant must be rejected before DB work")

    monkeypatch.setattr(pools.discovery_service, "record_announcement", record)
    monkeypatch.setattr(
        pools,
        "make_session_factory",
        lambda *_args: (_ for _ in ()).throw(
            AssertionError("a mismatched tenant must be rejected before opening a session")
        ),
    )

    with TestClient(_app(principal=principal), raise_server_exceptions=False) as client:
        response = client.post(
            "/v1/discovery/announcements",
            headers={
                "Authorization": "Bearer synthetic-user-token",
                "X-Inv-Tenant": str(tenant_b),
            },
            json={
                "instanceId": "synthetic-agent",
                "hostname": "synthetic-host",
                "osType": "linux",
                "osVersion": "synthetic",
                "agentVersion": "0.0-test",
            },
        )

    assert response.status_code == 403
    assert response.json()["code"] == "AUTH-TENANT-SCOPE"
    assert writes == []


def test_announcement_requires_authentication_even_with_a_well_formed_tenant_header(monkeypatch):
    monkeypatch.setenv("INV_ENV", "test")
    with TestClient(_app(), raise_server_exceptions=False) as client:
        response = client.post(
            "/v1/discovery/announcements",
            headers={"X-Inv-Tenant": str(uuid.uuid4())},
            json={
                "instanceId": "synthetic-agent",
                "hostname": "synthetic-host",
                "osType": "linux",
                "osVersion": "synthetic",
                "agentVersion": "0.0-test",
            },
        )

    assert response.status_code == 401
    assert response.json()["code"] == "AUTH-MISSING-CREDENTIAL"
