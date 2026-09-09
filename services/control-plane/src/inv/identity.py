"""Offline OAuth resource-server verification. No discovery or token-header URLs.

The operator supplies a short-lived public JWKS bundle and the trusted tenant.
Project permissions come from the DB, never JWT roles or browser identity headers.
"""

import base64
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time
from uuid import UUID
import jwt
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from .approvals import Principal
from .errors import DomainError


def strict_object(raw):
    def pairs(values):
        obj = {}
        for key, value in values:
            if key in obj:
                raise ValueError("duplicate JSON key")
            obj[key] = value
        return obj

    def invalid(value):
        raise ValueError("non-finite JSON")

    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)
    if not isinstance(value, dict):
        raise ValueError("JSON object required")
    return value


def public_subject(issuer, subject):
    # Stable across token/key rotation; identical sub in different issuers is distinct.
    return (
        "oidc:"
        + hashlib.sha256(
            json.dumps([issuer, subject], separators=(",", ":")).encode()
        ).hexdigest()
    )


def trusted_file(path):
    p = Path(path)
    info = p.lstat()
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_size > 65536
        or (os.name != "nt" and info.st_mode & 0o022)
    ):
        raise ValueError("operator-owned regular public configuration required")
    return p.read_bytes()


@dataclass(frozen=True)
class Identity:
    principal: Principal
    expires_at: int


class AccessTokens:
    def __init__(self, *, tenant_id, issuer, audience, client_ids, jwks_file):
        self.tenant_id = str(UUID(tenant_id))
        if (
            not isinstance(issuer, str)
            or not issuer.startswith("https://")
            or not audience
            or not client_ids
        ):
            raise ValueError("Explicit issuer, audience and clients required")
        self.issuer, self.audience = issuer, audience
        self.client_ids = frozenset(client_ids)
        self.jwks_file = Path(jwks_file)
        self._keys()  # Refuse startup with incomplete trust; no dev fallback.

    def _keys(self):
        bundle = strict_object(trusted_file(self.jwks_file))
        now = time.time()
        if (
            set(bundle) != {"issuer", "expiresAt", "keys"}
            or bundle["issuer"] != self.issuer
            or type(bundle["expiresAt"]) is not int
            or not now < bundle["expiresAt"] <= now + 7 * 86400
        ):
            raise ValueError("trust bundle expired or scoped incorrectly")
        if not isinstance(bundle["keys"], list) or not 1 <= len(bundle["keys"]) <= 8:
            raise ValueError("bounded trusted signing keys required")
        keys = {}
        for value in bundle["keys"]:
            if (
                not isinstance(value, dict)
                or value.get("kty") != "RSA"
                or value.get("alg") != "RS256"
                or value.get("use") != "sig"
                or "d" in value
            ):
                raise ValueError("RS256 public signing key required")
            kid = value.get("kid")
            if not isinstance(kid, str) or not 1 <= len(kid) <= 128 or kid in keys:
                raise ValueError("unique key ID required")
            key = jwt.PyJWK.from_dict(value, algorithm="RS256").key
            if not isinstance(key, RSAPublicKey) or not 2048 <= key.key_size <= 4096:
                raise ValueError("RSA key size rejected")
            keys[kid] = key
        return keys

    def verify(self, token):
        try:
            if not isinstance(token, str) or len(token) > 16384:
                raise ValueError()
            segments = token.split(".")
            if len(segments) != 3 or any(
                not re.fullmatch(r"[A-Za-z0-9_-]+", s) for s in segments
            ):
                raise ValueError()
            decoded = [
                base64.urlsafe_b64decode(s + "=" * (-len(s) % 4)) for s in segments
            ]
            if any(
                base64.urlsafe_b64encode(b).decode().rstrip("=") != s
                for b, s in zip(decoded, segments)
            ):
                raise ValueError()
            header, untrusted = strict_object(decoded[0]), strict_object(decoded[1])
            if (
                set(header) != {"alg", "typ", "kid"}
                or header["alg"] != "RS256"
                or header["typ"] not in {"at+jwt", "application/at+jwt"}
            ):
                raise ValueError()
            claims = jwt.decode(
                token,
                self._keys()[header["kid"]],
                algorithms=["RS256"],
                issuer=self.issuer,
                audience=self.audience,
                options={
                    "require": ["iss", "aud", "sub", "iat", "exp", "jti", "client_id"],
                    "strict_aud": True,
                },
            )
            if claims != untrusted or any(
                type(claims[k]) is not int for k in ["iat", "exp"]
            ):
                raise ValueError()
            if "nbf" in claims and type(claims["nbf"]) is not int:
                raise ValueError()
            if (
                not 0 < claims["exp"] - claims["iat"] <= 3600
                or claims["client_id"] not in self.client_ids
            ):
                raise ValueError()
            if any(
                not isinstance(claims[k], str) or not 1 <= len(claims[k]) <= 200
                for k in ["sub", "jti"]
            ):
                raise ValueError()
            scope = claims.get("scope")
            if not isinstance(scope, str) or "inv.api" not in scope.split(" "):
                raise ValueError()
            return Identity(
                Principal(self.tenant_id, public_subject(self.issuer, claims["sub"])),
                claims["exp"],
            )
        except (
            ValueError,
            TypeError,
            KeyError,
            OSError,
            RecursionError,
            jwt.PyJWTError,
        ):
            raise DomainError(
                "AUTH-0050", "A current access token is required", 401
            ) from None
