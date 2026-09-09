import base64
import json
import time
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from inv.app import create_app
from inv.errors import DomainError
from inv.identity import public_subject
from jwt_support import jwt_fixture


@pytest.fixture
def auth(tmp_path):
    return jwt_fixture(tmp_path, str(uuid4()))


def test_access_identity_comes_from_verified_issuer_and_configured_tenant(auth):
    identity = auth.auth.verify(
        auth.token(claims={"tenantId": str(uuid4()), "roles": ["admin"]})
    )
    assert identity.principal.tenant_id == auth.tenant
    assert identity.principal.subject_id == auth.subject("requester")
    assert public_subject(auth.issuer, "requester") != public_subject(
        "https://other.invalid", "requester"
    )


@pytest.mark.parametrize(
    "claims",
    [
        {"iss": "https://attacker.invalid"},
        {"aud": "another-api"},
        {"aud": ["saintvision-api", "other"]},
        {"exp": 0},
        {"iat": int(time.time()) + 1000},
        {"exp": int(time.time()) + 7200},
        {"exp": True},
        {"iat": 1.5},
        {"nbf": int(time.time()) + 1000},
        {"sub": ""},
        {"sub": 42},
        {"client_id": "attacker"},
        {"scope": "other"},
        {"jti": ""},
        {"nbf": True},
    ],
)
def test_bad_access_claims_are_rejected(auth, claims):
    with pytest.raises(DomainError) as error:
        auth.auth.verify(auth.token(claims=claims))
    assert error.value.status == 401


@pytest.mark.parametrize(
    "headers",
    [
        {"typ": "JWT"},
        {"typ": "id+jwt"},
        {"kid": "unknown"},
        {"jku": "https://attacker.invalid"},
        {"crit": ["b64"]},
    ],
)
def test_token_header_has_no_control_over_trust(auth, headers):
    with pytest.raises(DomainError):
        auth.auth.verify(auth.token(headers=headers))


def test_live_jwks_removal_and_expiry_do_not_fall_back(auth):
    token = auth.token()
    auth.auth.verify(token)
    auth.bundle["keys"] = []
    auth.path.write_text(json.dumps(auth.bundle), "utf-8")
    with pytest.raises(DomainError):
        auth.auth.verify(token)
    auth.path.unlink()
    with pytest.raises(DomainError):
        auth.auth.verify(token)


def test_ambiguous_signed_json_and_signature_tampering_are_rejected(auth):
    token = auth.token()
    head, body, sig = token.split(".")
    raw = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)).decode()
    body = (
        base64.urlsafe_b64encode((raw[:-1] + ',"sub":"attacker"}').encode())
        .decode()
        .rstrip("=")
    )
    with pytest.raises(DomainError):
        auth.auth.verify(head + "." + body + "." + sig)
    with pytest.raises(DomainError):
        auth.auth.verify(token[:-10] + "AAAAAAAAAA")


def test_http_boundary_rejects_unconfigured_identity_oversize_and_ambiguous_json():
    client = TestClient(create_app(), raise_server_exceptions=False)
    assert client.get("/healthz").status_code == 200
    assert client.get("/readyz").status_code == 503
    assert client.get("/v1/projects", headers={"X-Subject": "admin"}).status_code == 503
    for body, status in [
        ('{"a":1,"a":2}', 422),
        ('{"secret":"' + ("x" * 65536) + '"}', 413),
        ("[]", 422),
    ]:
        r = client.post(
            "/v1/projects", content=body, headers={"Content-Type": "application/json"}
        )
        assert r.status_code == status and "secret" not in r.text
    assert (
        client.get(
            "/v1/projects",
            headers=[("Authorization", "Bearer a"), ("Authorization", "Bearer b")],
        ).status_code
        == 400
    )
    assert (
        client.get(
            "/v1/projects", headers={"Origin": "https://attacker.invalid"}
        ).status_code
        == 403
    )
