"""Synthetic access-token fixtures. Private keys stay in process memory."""

from types import SimpleNamespace
from pathlib import Path
import json
import time
from uuid import uuid4
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from inv.identity import AccessTokens, public_subject


def jwt_fixture(path, tenant):
    a = SimpleNamespace(
        tenant=tenant,
        issuer="https://synthetic-idp.invalid/realm",
        audience="saintvision-api",
        path=Path(path) / "jwks.json",
    )
    a.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(a.key.public_key()))
    jwk.update(kid="synthetic-1", alg="RS256", use="sig")
    a.bundle = {"issuer": a.issuer, "expiresAt": int(time.time()) + 3600, "keys": [jwk]}
    a.path.write_text(json.dumps(a.bundle), "utf-8")
    a.path.chmod(0o600)
    a.auth = AccessTokens(
        tenant_id=tenant,
        issuer=a.issuer,
        audience=a.audience,
        client_ids=["synthetic-web"],
        jwks_file=a.path,
    )

    def token(subject="requester", *, claims=None, headers=None, key=None):
        now = int(time.time())
        data = {
            "iss": a.issuer,
            "aud": a.audience,
            "sub": subject,
            "iat": now,
            "exp": now + 300,
            "jti": str(uuid4()),
            "client_id": "synthetic-web",
            "scope": "inv.api",
        }
        data.update(claims or {})
        return jwt.encode(
            data,
            key or a.key,
            algorithm="RS256",
            headers={"kid": "synthetic-1", "typ": "at+jwt", **(headers or {})},
        )

    a.token = token
    a.subject = lambda value: public_subject(a.issuer, value)
    return a
