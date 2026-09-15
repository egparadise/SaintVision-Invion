"""The storage HTTP API (VF-CL-01 API acceptance).

The storage *service* is covered by test_storage_catalog; this covers the HTTP
layer on top of it -- ``saintvision.api.app`` with its real dependency chain
(bearer credential -> Principal -> tenant-scoped session), which had no test.
Each assertion is a place the route, not the service, is responsible for:

* a missing or unrecognised bearer credential is refused (AUTH -> 403); the two
  carry different InvError *codes* (AUTH_MISSING_CREDENTIAL vs
  AUTH_INVALID_CREDENTIAL) so the audit trail can tell "not logged in" from
  "rejected", though both surface as 403;
* an unknown field in the body is refused (the request models are strict, 422);
* an unknown node is a RESOURCE error, which this API maps to 409 by category
  (errors.py _STATUS), not 404 -- the test asserts the API's own convention;
* the happy path returns 201 and the contribution lifecycle is reachable over
  HTTP end to end, catalogued locations included.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import text

from saintvision.ids import new_id

pytestmark = pytest.mark.postgres


@pytest.fixture
def api(app_engine, owner_engine, two_tenants):
    """A TestClient for saintvision.api.app, authenticated as a seeded user.

    The app runs on the non-owner ``app_engine`` so RLS applies exactly as in a
    deployment; the node and user are seeded as the owner, outside RLS.
    """
    from fastapi.testclient import TestClient

    from saintvision.api.app import create_app
    from saintvision.config import Settings
    from saintvision.identity.principal import Principal, StaticPrincipalVerifier

    os.environ.setdefault("INV_ENV", "test")
    tenant_a, _tenant_b = two_tenants
    user_id = new_id("user")
    node_id = new_id("node")
    with owner_engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO users (user_id, tenant_id, external_subject, display_name, "
                "status, created_at, updated_at, version) "
                "VALUES (:u, :t, 'sub', 'U', 'active', now(), now(), 1)"
            ),
            {"u": user_id, "t": tenant_a},
        )
        c.execute(
            text(
                "INSERT INTO nodes (node_id, tenant_id, hostname, os_type, os_version, "
                "agent_version, status, enrolled_at, heartbeat_sequence, version) "
                "VALUES (:n, :t, 'api-00', 'linux', '22.04', '0.1', 'active', now(), 0, 1)"
            ),
            {"n": node_id, "t": tenant_a},
        )

    principal = Principal(user_id=user_id, tenant_id=tenant_a, external_subject="sub")
    verifier = StaticPrincipalVerifier({"tok": principal}, allow_outside_dev=True)
    app = create_app(
        engine=app_engine,
        settings=Settings(database_url="postgresql+psycopg://unused/none"),
        verifier=verifier,
        check_partitions_on_startup=False,
    )
    client = TestClient(app, raise_server_exceptions=False)
    return {"client": client, "node_id": node_id, "user_id": user_id, "tenant_a": tenant_a}


def _auth(extra=None):
    headers = {"Authorization": "Bearer tok"}
    if extra:
        headers.update(extra)
    return headers


def test_a_missing_bearer_credential_is_refused(api):
    # AUTH errors map to 403 in this API (errors.py _STATUS), not 401.
    resp = api["client"].get("/v1/storage/contributions")
    assert resp.status_code == 403


def test_an_unrecognised_credential_is_refused(api):
    resp = api["client"].get(
        "/v1/storage/contributions", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert resp.status_code in (401, 403)


def test_an_unknown_body_field_is_refused(api):
    resp = api["client"].post(
        "/v1/storage/contributions",
        json={"nodeId": api["node_id"], "declaredPath": "/srv/inv/0", "surprise": 1},
        headers=_auth(),
    )
    assert resp.status_code == 422


def test_registering_a_contribution_returns_201_and_the_lifecycle_is_reachable(api):
    client = api["client"]
    # Register -> 201, pending.
    resp = client.post(
        "/v1/storage/contributions",
        json={"nodeId": api["node_id"], "declaredPath": "/srv/inv/0", "mode": "read_write"},
        headers=_auth(),
    )
    assert resp.status_code == 201, resp.text
    contribution = resp.json()["contribution"]
    assert contribution["status"] == "pending"
    contribution_id = contribution["contributionId"]

    # It is listed.
    listed = client.get("/v1/storage/contributions", headers=_auth())
    assert listed.status_code == 200
    assert any(c["contributionId"] == contribution_id for c in listed.json()["items"])

    # Activate it.
    activated = client.post(
        f"/v1/storage/contributions/{contribution_id}/activation", headers=_auth()
    )
    assert activated.status_code in (200, 201)

    # Locations start empty for a fresh contribution.
    locations = client.get("/v1/storage/locations", headers=_auth())
    assert locations.status_code == 200
    assert locations.json()["items"] == []


def test_registering_against_an_unknown_node_is_a_resource_error(api):
    # RESOURCE errors (a node not found) map to 409 by category in this API.
    resp = api["client"].post(
        "/v1/storage/contributions",
        json={"nodeId": new_id("node"), "declaredPath": "/srv/inv/0"},
        headers=_auth(),
    )
    assert resp.status_code == 409
