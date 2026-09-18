"""Quarantined legacy fixture tests: NOT production authentication or DB evidence."""
"""
Tests for saintvision.server authentication integrity and zero-mock token verification.
Verifies:
1. /v1/auth/userinfo returns 401 when Authorization header is absent.
2. /v1/auth/userinfo returns 401 (AUTH-0050) when a junk Bearer token is provided.
3. /v1/auth/token rejects invalid PKCE code_challenge / code_verifier mismatch (SEC-PKCE-INVALID).
4. /v1/auth/token issues valid Bearer access token on valid PKCE exchange.
5. /v1/auth/userinfo returns 200 and authentic identity when presented with the issued token.
"""

import base64
import hashlib
import secrets
from fastapi.testclient import TestClient
import pytest

from fixtures.legacy_control import app


def _base64url_sha256(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


@pytest.fixture
def client():
    return TestClient(app)


def test_userinfo_requires_authorization_header(client):
    res = client.get("/v1/auth/userinfo")
    assert res.status_code == 401
    problem = res.json()
    assert problem["code"] == "AUTH-0050"


def test_userinfo_rejects_junk_bearer_token(client):
    res = client.get(
        "/v1/auth/userinfo",
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert res.status_code == 401
    problem = res.json()
    assert problem["code"] == "AUTH-0050"
    assert "untrusted" in problem["detail"].lower() or "invalid" in problem["detail"].lower()


def test_token_exchange_rejects_mismatching_pkce(client):
    verifier = secrets.token_urlsafe(32)
    res = client.post(
        "/v1/auth/token",
        json={
            "grant_type": "authorization_code",
            "code": "auth_code_test",
            "code_verifier": verifier,
            "code_challenge": "mismatching_challenge",
            "code_challenge_method": "S256",
            "client_id": "saintvision-web",
            "idp": "internal-keycloak",
        },
    )
    assert res.status_code == 401
    problem = res.json()
    assert problem["code"] == "SEC-PKCE-INVALID"


def test_token_exchange_and_authenticated_userinfo(client):
    verifier = secrets.token_urlsafe(32)
    challenge = _base64url_sha256(verifier)

    res = client.post(
        "/v1/auth/token",
        json={
            "grant_type": "authorization_code",
            "code": f"auth_code_{secrets.token_hex(8)}",
            "code_verifier": verifier,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "client_id": "saintvision-web",
            "idp": "internal-keycloak",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["token_type"] == "Bearer"
    token = data["access_token"]
    assert bool(token)

    # Calling userinfo with valid token succeeds
    userinfo_res = client.get(
        "/v1/auth/userinfo",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert userinfo_res.status_code == 200
    user = userinfo_res.json()
    assert user["sub"] == "usr_01JABCDEF_ADMIN"
    assert "cluster:admin" in user["roles"]
