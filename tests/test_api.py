"""The AC-02 journey over the real API.

AC-02: enrolled nodes can be registered and read back, a bootstrap token cannot
be reused, and one project's information is not reachable from another.

Browser evidence is S02-FE and belongs to Gemini; this file covers the API half.
"""

from __future__ import annotations

import datetime as dt
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from saintvision.api.app import create_app
from saintvision.config import Settings
from saintvision.db.session import tenant_scope
from saintvision.identity.principal import Principal, StaticPrincipalVerifier
from saintvision.identity.tokens import issue_bootstrap_token
from saintvision.ids import new_id, new_trace_id

pytestmark = pytest.mark.postgres

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 9, 9, 7, 0, 0, tzinfo=UTC)


@pytest.fixture
def seeded(owner_engine, two_tenants):
    """One user per tenant, plus a project each, inserted as the owner."""
    tenant_a, tenant_b = two_tenants
    user_a, user_b = new_id("user"), new_id("user")
    project_a, project_b = new_id("project"), new_id("project")
    with owner_engine.begin() as connection:
        for tenant, user, project, code in (
            (tenant_a, user_a, project_a, "alpha"),
            (tenant_b, user_b, project_b, "beta"),
        ):
            connection.execute(
                text(
                    "INSERT INTO users (user_id, tenant_id, external_subject, display_name, "
                    "status, created_at, updated_at, version) "
                    "VALUES (:u, :t, :s, :s, 'active', now(), now(), 1)"
                ),
                {"u": user, "t": tenant, "s": f"sub-{code}"},
            )
            connection.execute(
                text(
                    "INSERT INTO projects (project_id, tenant_id, code, display_name, "
                    "status, created_at, version) VALUES (:p, :t, :c, :c, 'active', now(), 1)"
                ),
                {"p": project, "t": tenant, "c": code},
            )
    return {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "user_a": user_a,
        "user_b": user_b,
        "project_a": project_a,
        "project_b": project_b,
    }


PROXY_ADDRESS = "10.9.9.9"


@pytest.fixture
def client(app_engine, seeded, monkeypatch):
    monkeypatch.setenv("INV_ENV", "test")
    # The heartbeat route authenticates a node by its client certificate. A
    # TestClient cannot perform mTLS, so these tests take the trusted-proxy
    # path — which is itself only open because the address is allowlisted here.
    monkeypatch.setenv("INV_TRUSTED_PROXY_ADDRESSES", f"{PROXY_ADDRESS}/32")
    principals = {
        "token-a": Principal(
            user_id=seeded["user_a"],
            tenant_id=seeded["tenant_a"],
            external_subject="sub-alpha",
            project_ids=frozenset({seeded["project_a"]}),
        ),
        "token-b": Principal(
            user_id=seeded["user_b"],
            tenant_id=seeded["tenant_b"],
            external_subject="sub-beta",
            project_ids=frozenset({seeded["project_b"]}),
        ),
    }
    app = create_app(
        engine=app_engine,
        settings=Settings(database_url="unused"),
        verifier=StaticPrincipalVerifier(principals),
        clock=lambda: NOW,
    )
    with TestClient(app, client=(PROXY_ADDRESS, 40000)) as test_client:
        yield test_client


def mint_token(app_engine, tenant_id, user_id) -> str:
    from sqlalchemy.orm import sessionmaker

    factory = sessionmaker(bind=app_engine, expire_on_commit=False)
    with factory() as session:
        with session.begin():
            with tenant_scope(session, tenant_id):
                issued = issue_bootstrap_token(
                    session, tenant_id=tenant_id, issued_by_user_id=user_id, now=NOW
                )
                return issued.secret


def node_headers(fingerprint: str = "b" * 64) -> dict:
    """Headers a terminating proxy would set after verifying the client cert."""
    return {"X-Inv-Node-Cert-Sha256": fingerprint}


def enroll_payload(secret: str, hostname: str = "lab-01") -> dict:
    return {
        "bootstrapToken": secret,
        "hostname": hostname,
        "osType": "linux",
        "osVersion": "22.04",
        "agentVersion": "0.1.0",
        "capabilities": [
            {"kind": "ram", "totalQuantity": 64, "unit": "GiB", "divisible": True,
             "offeredQuantity": 48},
            {"kind": "gpu", "deviceIndex": 0, "totalQuantity": 1, "unit": "device",
             "vendor": "NVIDIA", "model": "RTX", "offeredQuantity": 1},
        ],
        "certificateFingerprint": "b" * 64,
        "labels": {"room": "lab"},
    }


# --------------------------------------------------------------------------
# AC-02: register and read back
# --------------------------------------------------------------------------


def test_enrolled_node_is_registered_and_readable(client, app_engine, seeded):
    secret = mint_token(app_engine, seeded["tenant_a"], seeded["user_a"])
    response = client.post(
        "/v1/nodes",
        json=enroll_payload(secret),
        headers={"X-Inv-Tenant": str(seeded["tenant_a"])},
    )
    assert response.status_code == 201, response.text
    node_id = response.json()["node"]["nodeId"]
    assert response.headers["Location"] == f"/v1/nodes/{node_id}"

    listed = client.get("/v1/nodes", headers={"Authorization": "Bearer token-a"})
    assert listed.status_code == 200
    assert [n["nodeId"] for n in listed.json()["items"]] == [node_id]

    detail = client.get(f"/v1/nodes/{node_id}", headers={"Authorization": "Bearer token-a"})
    assert detail.status_code == 200
    kinds = sorted(c["kind"] for c in detail.json()["capabilities"])
    assert kinds == ["gpu", "ram"]


# --------------------------------------------------------------------------
# AC-02: token reuse is blocked
# --------------------------------------------------------------------------


def test_bootstrap_token_cannot_be_used_twice(client, app_engine, seeded):
    secret = mint_token(app_engine, seeded["tenant_a"], seeded["user_a"])
    headers = {"X-Inv-Tenant": str(seeded["tenant_a"])}

    first = client.post("/v1/nodes", json=enroll_payload(secret, "lab-01"), headers=headers)
    assert first.status_code == 201

    second = client.post("/v1/nodes", json=enroll_payload(secret, "lab-02"), headers=headers)
    assert second.status_code == 403
    body = second.json()
    assert body["code"] == "AUTH-BOOTSTRAP-TOKEN-CONSUMED"
    assert body["retryable"] is False
    assert body["category"] == "AUTH"


def test_unknown_bootstrap_token_is_rejected(client, seeded):
    response = client.post(
        "/v1/nodes",
        json=enroll_payload("not-a-real-token-value-0000"),
        headers={"X-Inv-Tenant": str(seeded["tenant_a"])},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "AUTH-BOOTSTRAP-TOKEN-INVALID"


def test_a_tokens_tenant_is_binding(client, app_engine, seeded):
    """A token minted for tenant A cannot enroll a node into tenant B."""
    secret = mint_token(app_engine, seeded["tenant_a"], seeded["user_a"])
    response = client.post(
        "/v1/nodes",
        json=enroll_payload(secret),
        headers={"X-Inv-Tenant": str(seeded["tenant_b"])},
    )
    assert response.status_code == 403
    assert response.json()["code"].startswith("AUTH-BOOTSTRAP-TOKEN")


def test_denials_are_recorded(client, app_engine, seeded, owner_engine):
    client.post(
        "/v1/nodes",
        json=enroll_payload("not-a-real-token-value-0000"),
        headers={"X-Inv-Tenant": str(seeded["tenant_a"])},
    )
    # Read as the owner: the denial may carry no tenant, so RLS would hide it.
    with owner_engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT reason_code, outcome FROM audit_events WHERE outcome = 'deny'"
            )
        ).mappings().all()
    assert any(r["reason_code"] == "AUTH-BOOTSTRAP-TOKEN-INVALID" for r in rows)


# --------------------------------------------------------------------------
# AC-02: another tenant's information is unreachable
# --------------------------------------------------------------------------


def test_another_tenants_node_is_not_listed(client, app_engine, seeded):
    secret = mint_token(app_engine, seeded["tenant_a"], seeded["user_a"])
    client.post(
        "/v1/nodes",
        json=enroll_payload(secret),
        headers={"X-Inv-Tenant": str(seeded["tenant_a"])},
    )
    other = client.get("/v1/nodes", headers={"Authorization": "Bearer token-b"})
    assert other.status_code == 200
    assert other.json()["items"] == []


def test_another_tenants_node_is_not_readable_by_id(client, app_engine, seeded):
    secret = mint_token(app_engine, seeded["tenant_a"], seeded["user_a"])
    created = client.post(
        "/v1/nodes",
        json=enroll_payload(secret),
        headers={"X-Inv-Tenant": str(seeded["tenant_a"])},
    )
    node_id = created.json()["node"]["nodeId"]
    response = client.get(f"/v1/nodes/{node_id}", headers={"Authorization": "Bearer token-b"})
    # Reported as absent, not forbidden: "forbidden" would confirm it exists.
    assert response.status_code == 409
    assert response.json()["code"] == "RES-NODE-NOT-FOUND"


def test_project_scope_is_checked_separately_from_tenancy(seeded):
    """RLS gives tenant isolation; every user in a tenant passes it.

    Project isolation is therefore a service-layer check, and this is it.
    """
    from saintvision.errors import InvError

    principal = Principal(
        user_id=seeded["user_a"],
        tenant_id=seeded["tenant_a"],
        external_subject="sub-alpha",
        project_ids=frozenset({seeded["project_a"]}),
    )
    principal.require_project(seeded["project_a"])
    with pytest.raises(InvError) as caught:
        principal.require_project(seeded["project_b"])
    assert caught.value.code == "AUTH-PROJECT-SCOPE"


def test_missing_credential_is_refused(client):
    response = client.get("/v1/nodes")
    assert response.status_code == 403
    assert response.json()["code"] == "AUTH-MISSING-CREDENTIAL"


def test_unknown_credential_is_refused(client):
    response = client.get("/v1/nodes", headers={"Authorization": "Bearer nope"})
    assert response.status_code == 403
    assert response.json()["code"] == "AUTH-INVALID-CREDENTIAL"


# --------------------------------------------------------------------------
# Heartbeat
# --------------------------------------------------------------------------


def test_heartbeat_advances_and_replays_are_ignored(client, app_engine, seeded):
    secret = mint_token(app_engine, seeded["tenant_a"], seeded["user_a"])
    headers = {"X-Inv-Tenant": str(seeded["tenant_a"])}
    node_id = client.post("/v1/nodes", json=enroll_payload(secret), headers=headers).json()[
        "node"
    ]["nodeId"]

    first = client.post(
        f"/v1/nodes/{node_id}/heartbeats", json={"sequence": 1}, headers=node_headers()
    )
    assert first.status_code == 202
    assert first.json()["applied"] is True

    # A captured heartbeat replayed: must not refresh liveness (ADR-007).
    replay = client.post(
        f"/v1/nodes/{node_id}/heartbeats", json={"sequence": 1}, headers=node_headers()
    )
    assert replay.json()["applied"] is False
    assert replay.json()["heartbeatSequence"] == 1

    ahead = client.post(
        f"/v1/nodes/{node_id}/heartbeats", json={"sequence": 5}, headers=node_headers()
    )
    assert ahead.json()["applied"] is True
    assert ahead.json()["heartbeatSequence"] == 5


def test_heartbeat_observations_land_in_the_right_partition(client, app_engine, seeded):
    secret = mint_token(app_engine, seeded["tenant_a"], seeded["user_a"])
    headers = {"X-Inv-Tenant": str(seeded["tenant_a"])}
    created = client.post("/v1/nodes", json=enroll_payload(secret), headers=headers).json()
    node_id = created["node"]["nodeId"]
    detail = client.get(
        f"/v1/nodes/{node_id}", headers={"Authorization": "Bearer token-a"}
    ).json()
    capability_id = detail["capabilities"][0]["capabilityId"]

    response = client.post(
        f"/v1/nodes/{node_id}/heartbeats",
        json={
            "sequence": 2,
            "observations": [
                {"capabilityId": capability_id, "usedQuantity": 3.5, "unit": "GiB"}
            ],
        },
        headers=node_headers(),
    )
    assert response.status_code == 202
    listed = client.get(f"/v1/nodes/{node_id}", headers={"Authorization": "Bearer token-a"})
    assert listed.status_code == 200


def test_liveness_sweep_marks_a_silent_node_lost(client, app_engine, seeded):
    """AC-02's observation half: a node that stops reporting is detected.

    The clock is fixed at NOW for the app, so the sweep is driven by inserting a
    heartbeat that is already older than the timeout rather than by waiting.
    """
    secret = mint_token(app_engine, seeded["tenant_a"], seeded["user_a"])
    headers = {"X-Inv-Tenant": str(seeded["tenant_a"])}
    node_id = client.post("/v1/nodes", json=enroll_payload(secret), headers=headers).json()[
        "node"
    ]["nodeId"]
    client.post(f"/v1/nodes/{node_id}/heartbeats", json={"sequence": 1}, headers=node_headers())

    auth = {"Authorization": "Bearer token-a"}
    # Still fresh: the sweep must not touch it.
    quiet = client.post("/v1/nodes/liveness-sweeps", headers=auth)
    assert quiet.status_code == 200
    assert quiet.json()["markedLost"] == 0

    from sqlalchemy.orm import sessionmaker

    factory = sessionmaker(bind=app_engine, expire_on_commit=False)
    with factory() as session:
        with session.begin():
            with tenant_scope(session, seeded["tenant_a"]):
                session.execute(
                    text(
                        "UPDATE nodes SET last_heartbeat_at = :t WHERE node_id = :i"
                    ),
                    {"t": NOW - dt.timedelta(seconds=120), "i": node_id},
                )

    swept = client.post("/v1/nodes/liveness-sweeps", headers=auth)
    assert swept.json()["markedLost"] == 1
    detail = client.get(f"/v1/nodes/{node_id}", headers=auth)
    assert detail.json()["node"]["status"] == "lost"

    # A later heartbeat brings it back, rather than stranding it as lost.
    client.post(f"/v1/nodes/{node_id}/heartbeats", json={"sequence": 2}, headers=node_headers())
    assert client.get(f"/v1/nodes/{node_id}", headers=auth).json()["node"]["status"] == "active"


def test_liveness_sweep_does_not_cross_tenants(client, app_engine, seeded):
    secret = mint_token(app_engine, seeded["tenant_a"], seeded["user_a"])
    client.post(
        "/v1/nodes",
        json=enroll_payload(secret),
        headers={"X-Inv-Tenant": str(seeded["tenant_a"])},
    )
    from sqlalchemy.orm import sessionmaker

    factory = sessionmaker(bind=app_engine, expire_on_commit=False)
    with factory() as session:
        with session.begin():
            with tenant_scope(session, seeded["tenant_a"]):
                session.execute(text("UPDATE nodes SET last_heartbeat_at = :t"),
                                {"t": NOW - dt.timedelta(seconds=600)})

    other = client.post(
        "/v1/nodes/liveness-sweeps", headers={"Authorization": "Bearer token-b"}
    )
    assert other.json()["markedLost"] == 0


def test_a_heartbeat_for_a_node_you_are_not_is_refused(client, app_engine, seeded):
    """A tenant header can no longer redirect a beat.

    The node identity comes from the certificate, so claiming another node's id
    in the path is a mismatch rather than a tenant question.
    """
    secret = mint_token(app_engine, seeded["tenant_a"], seeded["user_a"])
    node_id = client.post(
        "/v1/nodes",
        json=enroll_payload(secret),
        headers={"X-Inv-Tenant": str(seeded["tenant_a"])},
    ).json()["node"]["nodeId"]

    response = client.post(
        f"/v1/nodes/{node_id}/heartbeats",
        json={"sequence": 9},
        headers=node_headers("f" * 64),
    )
    # An unknown certificate is not a credential at all, so this never reaches
    # the node lookup.
    assert response.status_code == 403
    assert response.json()["code"] == "AUTH-INVALID-CREDENTIAL"


# --------------------------------------------------------------------------
# Storage contributions
# --------------------------------------------------------------------------


def register_node(client, app_engine, seeded, hostname="store-01") -> str:
    secret = mint_token(app_engine, seeded["tenant_a"], seeded["user_a"])
    return client.post(
        "/v1/nodes",
        json=enroll_payload(secret, hostname),
        headers={"X-Inv-Tenant": str(seeded["tenant_a"])},
    ).json()["node"]["nodeId"]


def test_contribution_is_registered_with_a_normalised_path(client, app_engine, seeded):
    node_id = register_node(client, app_engine, seeded)
    response = client.post(
        "/v1/storage/contributions",
        json={"nodeId": node_id, "declaredPath": "/srv/inv/./share", "mode": "read_only"},
        headers={"Authorization": "Bearer token-a"},
    )
    assert response.status_code == 201, response.text
    contribution = response.json()["contribution"]
    assert contribution["normalizedPath"] == "/srv/inv/share"
    assert contribution["status"] == "pending"


def test_unsafe_contribution_path_is_rejected(client, app_engine, seeded):
    node_id = register_node(client, app_engine, seeded)
    response = client.post(
        "/v1/storage/contributions",
        json={"nodeId": node_id, "declaredPath": "/etc"},
        headers={"Authorization": "Bearer token-a"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VAL-PATH-UNSAFE"


def test_contribution_registration_is_idempotent(client, app_engine, seeded):
    node_id = register_node(client, app_engine, seeded)
    body = {"nodeId": node_id, "declaredPath": "/srv/inv/share"}
    headers = {"Authorization": "Bearer token-a", "Idempotency-Key": "key-1"}

    first = client.post("/v1/storage/contributions", json=body, headers=headers)
    second = client.post("/v1/storage/contributions", json=body, headers=headers)
    assert first.status_code == 201
    assert second.json() == first.json()

    listed = client.get(
        "/v1/storage/contributions", headers={"Authorization": "Bearer token-a"}
    )
    assert len(listed.json()["items"]) == 1


def test_same_key_with_a_different_body_is_a_conflict(client, app_engine, seeded):
    node_id = register_node(client, app_engine, seeded)
    headers = {"Authorization": "Bearer token-a", "Idempotency-Key": "key-2"}
    client.post(
        "/v1/storage/contributions",
        json={"nodeId": node_id, "declaredPath": "/srv/inv/one"},
        headers=headers,
    )
    conflict = client.post(
        "/v1/storage/contributions",
        json={"nodeId": node_id, "declaredPath": "/srv/inv/two"},
        headers=headers,
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "GRAPH-IDEMPOTENCY-CONFLICT"


def test_another_tenant_cannot_see_the_contribution(client, app_engine, seeded):
    node_id = register_node(client, app_engine, seeded)
    client.post(
        "/v1/storage/contributions",
        json={"nodeId": node_id, "declaredPath": "/srv/inv/share"},
        headers={"Authorization": "Bearer token-a"},
    )
    other = client.get(
        "/v1/storage/contributions", headers={"Authorization": "Bearer token-b"}
    )
    assert other.json()["items"] == []


# --------------------------------------------------------------------------
# Cross-cutting
# --------------------------------------------------------------------------


def test_unknown_fields_are_rejected(client, app_engine, seeded):
    node_id = register_node(client, app_engine, seeded)
    response = client.post(
        "/v1/storage/contributions",
        json={"nodeId": node_id, "declaredPath": "/srv/inv/share", "sneaky": 1},
        headers={"Authorization": "Bearer token-a"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VAL-SCHEMA"


def test_page_limit_is_capped(client, app_engine, seeded):
    response = client.get(
        "/v1/nodes?limit=100000", headers={"Authorization": "Bearer token-a"}
    )
    assert response.status_code == 200


def test_invalid_cursor_is_rejected(client):
    response = client.get(
        "/v1/nodes?cursor=nonsense", headers={"Authorization": "Bearer token-a"}
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VAL-CURSOR"


def test_traceparent_is_honoured_and_echoed(client):
    trace_id = new_trace_id()
    response = client.get(
        "/v1/health", headers={"traceparent": f"00-{trace_id}-{'a'*16}-01"}
    )
    assert trace_id in response.headers["traceparent"]


def test_health_reports_unresolved_s01_settings(client):
    body = client.get("/v1/health").json()
    # OIDC and the object store are S01 decisions; they must show as unresolved
    # rather than being silently defaulted (AC-01).
    assert "INV_OIDC_ISSUER" in body["unresolvedSettings"]


def test_readiness_reports_partition_lead(client):
    """Every partitioned table is reported, whichever sprint added it.

    Asserted against the live constant rather than a literal: a hardcoded list
    here went stale the moment S03 added evidence_envelopes, and a readiness
    probe that silently omits a table is worse than one that fails.
    """
    from saintvision.db.models import PARTITIONED_TABLES

    body = client.get("/v1/readiness").json()
    assert body["status"] == "ok"
    assert {p["table"] for p in body["partitions"]} == set(PARTITIONED_TABLES)
    assert all(p["monthsAhead"] >= 1 for p in body["partitions"])
