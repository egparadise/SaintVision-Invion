"""Check a live OIDC realm against the control plane's token contract.

``deploy/intranet/idp-realm.sh`` sets the realm up. That is not the same as knowing
the realm is still set up: an admin console click, a restored backup or a half-applied
change can relax any of these settings, and the script would keep exiting 0 because
the objects it creates all exist. So the script ends by dumping the live
configuration and handing it to this checker, which fails closed.

Every rule here exists because ``inv.identity.AccessTokens.verify`` refuses a token
without it, or because a browser client without it is exploitable:

* ``accessTokenLifespan`` at most 3600s -- ``verify`` rejects a longer window -- and
  exactly the pinned value, so a silent widening is drift rather than taste;
* the API client can not log anyone in: no standard flow, no direct grant, no
  implicit flow, no service account. It exists to name an audience;
* the portal client is public, so PKCE ``S256`` is mandatory and a direct grant is
  not available -- a password grant from a public client is a credential funnel;
* the RFC 9068 token type, or the header says ``typ: JWT`` and ``verify`` refuses it;
* the ``roles`` scope is absent, or its audience-resolve mapper turns ``aud`` into a
  list and ``verify`` uses ``strict_aud``, which forbids lists;
* an audience mapper naming the API client, and a ``client_id`` claim, which Keycloak
  does not emit on its own -- it emits ``azp``;
* the ``inv.api`` scope, without which ``verify`` refuses the token;
* every redirect URI and web origin is https, or loopback. Loopback never crosses the
  network, which is why native-app flows are allowed to use it; a plaintext origin on
  a real hostname is a credential path over the LAN.

Input: one JSON object, ``--config FILE`` or stdin, of the shape
``deploy/intranet/idp-realm.sh`` assembles. Exit 0 when the realm matches, 1 on drift
(every failing rule is listed), 2 when the input itself is unusable.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
from pathlib import Path
import sys
from typing import Any
from urllib.parse import urlsplit

MAX_TOKEN_LIFESPAN = 3600  # inv.identity.verify: 0 < exp - iat <= 3600
PINNED_TOKEN_LIFESPAN = 300
RFC9068_ATTRIBUTE = "access.token.header.type.rfc9068"
PKCE_ATTRIBUTE = "pkce.code.challenge.method"
FORBIDDEN_SCOPES = ("roles",)  # its audience-resolve mapper makes aud a list
LOGIN_FLAGS = (
    "standardFlowEnabled",
    "directAccessGrantsEnabled",
    "implicitFlowEnabled",
    "serviceAccountsEnabled",
)


class ConfigUnusable(ValueError):
    """The snapshot cannot be judged, which is not the same as the realm being wrong."""


def _loopback(host: str) -> bool:
    if host in {"localhost", "localhost.localdomain"}:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def insecure_url(value: str) -> bool:
    """True when this redirect or origin would carry a code over plaintext."""
    parts = urlsplit(value)
    if parts.scheme == "https":
        return False
    host = (parts.hostname or "").lower()
    return not (parts.scheme == "http" and _loopback(host))


def _client(config: Any, name: str) -> dict[str, Any]:
    clients = config.get("clients")
    if not isinstance(clients, dict):
        raise ConfigUnusable("config.clients must be an object")
    client = clients.get(name)
    if not isinstance(client, dict):
        raise ConfigUnusable(f"config.clients[{name}] is missing")
    return client


def _mappers(client: dict[str, Any]) -> dict[str, dict[str, Any]]:
    mappers = client.get("protocolMappers") or []
    if not isinstance(mappers, list):
        raise ConfigUnusable("protocolMappers must be a list")
    return {
        entry.get("name"): entry
        for entry in mappers
        if isinstance(entry, dict) and isinstance(entry.get("name"), str)
    }


def drift(config: Any, *, realm: str, api_client: str, portal_client: str, scope: str) -> list[str]:
    """Every way this realm departs from the contract, in one list."""
    if not isinstance(config, dict):
        raise ConfigUnusable("config must be an object")
    realm_config = config.get("realm")
    if not isinstance(realm_config, dict):
        raise ConfigUnusable("config.realm must be an object")

    findings: list[str] = []

    if realm_config.get("realm") != realm:
        findings.append(f"realm name is not {realm}")
    if realm_config.get("enabled") is not True:
        findings.append("realm is not enabled")
    lifespan = realm_config.get("accessTokenLifespan")
    if not isinstance(lifespan, int) or isinstance(lifespan, bool):
        findings.append("accessTokenLifespan is not an integer")
    elif lifespan > MAX_TOKEN_LIFESPAN:
        findings.append(f"accessTokenLifespan {lifespan}s exceeds the verifier's {MAX_TOKEN_LIFESPAN}s")
    elif lifespan != PINNED_TOKEN_LIFESPAN:
        findings.append(f"accessTokenLifespan drifted to {lifespan}s from {PINNED_TOKEN_LIFESPAN}s")

    api = _client(config, api_client)
    if api.get("publicClient") is not False:
        findings.append(f"{api_client} is a public client")
    for flag in LOGIN_FLAGS:
        if api.get(flag) is not False:
            findings.append(f"{api_client} has {flag} enabled; it must not log anyone in")

    portal = _client(config, portal_client)
    if portal.get("publicClient") is not True:
        findings.append(f"{portal_client} is not a public client")
    if portal.get("standardFlowEnabled") is not True:
        findings.append(f"{portal_client} has the authorization code flow disabled")
    for flag in ("directAccessGrantsEnabled", "implicitFlowEnabled", "serviceAccountsEnabled"):
        if portal.get(flag) is not False:
            findings.append(f"{portal_client} has {flag} enabled")

    attributes = portal.get("attributes")
    if not isinstance(attributes, dict):
        findings.append(f"{portal_client} has no attributes")
        attributes = {}
    if attributes.get(PKCE_ATTRIBUTE) != "S256":
        findings.append(f"{portal_client} does not require PKCE S256")
    if str(attributes.get(RFC9068_ATTRIBUTE)).lower() != "true":
        findings.append(f"{portal_client} does not emit RFC 9068 access tokens (typ=at+jwt)")

    scopes = portal.get("defaultClientScopes")
    if not isinstance(scopes, list):
        findings.append(f"{portal_client} has no defaultClientScopes")
        scopes = []
    if scope not in scopes:
        findings.append(f"{portal_client} is missing the {scope} default scope")
    for forbidden in FORBIDDEN_SCOPES:
        if forbidden in scopes:
            findings.append(
                f"{portal_client} still has the {forbidden} scope, which makes aud a list"
            )

    mappers = _mappers(portal)
    audience = next(
        (
            entry
            for entry in mappers.values()
            if entry.get("protocolMapper") == "oidc-audience-mapper"
            and (entry.get("config") or {}).get("included.client.audience") == api_client
        ),
        None,
    )
    if audience is None:
        findings.append(f"{portal_client} has no audience mapper naming {api_client}")
    elif str((audience.get("config") or {}).get("access.token.claim")).lower() != "true":
        findings.append("the audience mapper does not write to the access token")

    client_id = next(
        (
            entry
            for entry in mappers.values()
            if (entry.get("config") or {}).get("claim.name") == "client_id"
        ),
        None,
    )
    if client_id is None:
        findings.append("no mapper emits the required client_id claim")
    else:
        mapper_config = client_id.get("config") or {}
        if mapper_config.get("claim.value") != portal_client:
            findings.append(f"the client_id claim is not {portal_client}")
        if str(mapper_config.get("access.token.claim")).lower() != "true":
            findings.append("the client_id mapper does not write to the access token")

    for field in ("redirectUris", "webOrigins"):
        values = portal.get(field)
        if values is None:
            findings.append(f"{portal_client} has no {field}")
            continue
        if not isinstance(values, list):
            findings.append(f"{portal_client}.{field} is not a list")
            continue
        for value in values:
            if not isinstance(value, str) or not value.strip():
                findings.append(f"{portal_client}.{field} has an empty entry")
            elif value == "*" or insecure_url(value):
                findings.append(f"{portal_client}.{field} allows plaintext or wildcard: {value}")

    return findings


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n", 1)[0])
    result.add_argument("--config", type=Path, help="live realm snapshot; default stdin")
    result.add_argument("--realm", default="saintvision")
    result.add_argument("--api-client", default="sv-api")
    result.add_argument("--portal-client", default="sv-portal")
    result.add_argument("--scope", default="inv.api")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        raw = args.config.read_text(encoding="utf-8") if args.config else sys.stdin.read()
        config = json.loads(raw)
        findings = drift(
            config,
            realm=args.realm,
            api_client=args.api_client,
            portal_client=args.portal_client,
            scope=args.scope,
        )
    except ConfigUnusable as error:
        print(f"unusable: {error}", file=sys.stderr)
        return 2
    except Exception as error:
        print(f"unusable: {type(error).__name__}", file=sys.stderr)
        return 2
    if findings:
        for finding in findings:
            print(f"drift: {finding}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "realm": args.realm,
                "portalClient": args.portal_client,
                "audience": args.api_client,
                "scope": args.scope,
                "status": "matches the verifier's token contract",
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
