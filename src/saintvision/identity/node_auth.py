"""Authenticating an inbound Node request.

The heartbeat endpoint had no authentication: any caller who knew a node id
could post a heartbeat for it and keep a removed machine looking alive, or
inject utilisation figures that steer placement. This module is what the route
now depends on.

**The fingerprint must come from the transport, never from the request.** A
header a caller controls is not a credential — if the client could set
``X-Client-Cert-Sha256`` itself, authentication would be a formality. Two
sources are accepted and both are transport facts:

``asgi``
    The TLS layer verified a client certificate and the server passes it in the
    ASGI scope. This is direct mTLS with no intermediary.
``proxy``
    A reverse proxy terminated mTLS and forwards the verified fingerprint.
    Accepted **only** when the immediate peer address is in the configured
    allowlist, because otherwise the header is exactly the forgeable thing
    above.

With neither configured the verifier refuses every request. That is deliberate:
the CA and the proxy topology are S01-BE decisions (``config.S01_PENDING``), and
a node endpoint that authenticates nothing until someone remembers to configure
it is worse than one that is visibly closed.

Codex's ``node_channels`` holds the same fingerprint for the outbound direction
(ADR-029/030), where the Control Plane dials the node and checks the peer. This
is the inbound mirror of that check; the two must agree on the same certificate.
"""

from __future__ import annotations

import hashlib
import ipaddress
import os
import re
import uuid
from dataclasses import dataclass
from typing import Any, Final

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Node
from ..errors import (
    AUTH_INVALID_CREDENTIAL,
    AUTH_MISSING_CREDENTIAL,
    AUTH_NODE_MISMATCH,
    InvError,
)

_SHA256: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")

#: Header a trusted terminating proxy uses to pass the verified fingerprint.
PROXY_FINGERPRINT_HEADER: Final[str] = "x-inv-node-cert-sha256"

#: Comma-separated addresses permitted to set that header.
TRUSTED_PROXY_ENV: Final[str] = "INV_TRUSTED_PROXY_ADDRESSES"


class NodeAuthUnconfigured(InvError):
    """No source of verified client certificates has been configured."""

    def __init__(self) -> None:
        super().__init__(
            AUTH_MISSING_CREDENTIAL,
            "node authentication is not configured: neither direct mTLS nor a "
            "trusted terminating proxy is available, so no inbound node request "
            "can be authenticated",
            public=False,
        )


@dataclass(frozen=True, slots=True)
class NodePrincipal:
    """An authenticated node. Produced only from a transport-verified certificate."""

    node_id: str
    tenant_id: uuid.UUID
    certificate_sha256: str
    hostname: str
    #: Which transport fact proved it, for the audit trail.
    source: str

    def require_node(self, node_id: str) -> None:
        """A node may only act as itself.

        Without this a legitimately enrolled machine could heartbeat on behalf
        of any other node in the tenant — keeping a decommissioned machine
        looking alive, or feeding utilisation that steers placement onto it.
        """
        if node_id != self.node_id:
            raise InvError(
                AUTH_NODE_MISMATCH,
                "the authenticated node may only act for itself",
                extra={"requestedNodeId": node_id},
            )


def trusted_proxies() -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    """Networks whose forwarded fingerprint header is believed.

    Empty by default. An empty allowlist means the proxy path is closed, not
    that every proxy is trusted.
    """
    raw = os.environ.get(TRUSTED_PROXY_ENV, "").strip()
    if not raw:
        return ()
    networks = []
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        # A bare address is a /32 or /128; strict=False would silently widen a
        # typo like 10.0.0.1/8 into the whole private range.
        networks.append(ipaddress.ip_network(entry, strict=True))
    return tuple(networks)


def fingerprint_from_scope(scope: dict[str, Any]) -> str | None:
    """Read the peer certificate the TLS layer verified, if there is one."""
    extensions = scope.get("extensions") or {}
    tls = extensions.get("tls") or {}
    chain = tls.get("client_cert_chain") or ()
    if not chain:
        return None
    leaf = chain[0]
    if isinstance(leaf, str):
        # PEM. Strip the armour and hash the DER, which is what a fingerprint is.
        import base64

        body = "".join(
            line for line in leaf.splitlines() if not line.startswith("-----")
        )
        try:
            der = base64.b64decode(body, validate=True)
        except Exception:
            return None
    elif isinstance(leaf, (bytes, bytearray)):
        der = bytes(leaf)
    else:
        return None
    return hashlib.sha256(der).hexdigest()


def fingerprint_from_proxy(
    headers: dict[str, str], peer_address: str | None
) -> str | None:
    """Read a forwarded fingerprint, but only from an allowlisted peer.

    The check is on the *immediate* peer, not on ``X-Forwarded-For``: a
    forwarded-for chain is written by the same party whose honesty is in
    question.
    """
    value = headers.get(PROXY_FINGERPRINT_HEADER)
    if not value:
        return None
    networks = trusted_proxies()
    if not networks or peer_address is None:
        return None
    try:
        address = ipaddress.ip_address(peer_address)
    except ValueError:
        return None
    if not any(address in network for network in networks):
        return None
    return value.strip().lower()


def resolve_node(
    session: Session, *, fingerprint: str, source: str
) -> NodePrincipal:
    """Find the enrolled node holding this certificate.

    Looks up by fingerprint alone rather than by a caller-supplied node id, so
    the credential decides the identity instead of confirming a claim.
    """
    if not _SHA256.match(fingerprint or ""):
        raise InvError(
            AUTH_INVALID_CREDENTIAL, "certificate fingerprint is malformed", public=False
        )

    node = session.scalar(
        select(Node).where(Node.certificate_fingerprint == fingerprint)
    )
    if node is None:
        raise InvError(
            AUTH_INVALID_CREDENTIAL,
            "no enrolled node holds this certificate",
            public=False,
        )
    if node.status == "retired":
        # A retired machine's certificate must stop working, or retirement is
        # only a label.
        raise InvError(
            AUTH_INVALID_CREDENTIAL, "the node is retired", public=False
        )
    return NodePrincipal(
        node_id=node.node_id,
        tenant_id=node.tenant_id,
        certificate_sha256=fingerprint,
        hostname=node.hostname,
        source=source,
    )


def authenticate_node(
    session: Session,
    *,
    scope: dict[str, Any],
    headers: dict[str, str],
    peer_address: str | None,
) -> NodePrincipal:
    """Authenticate an inbound node request, or raise.

    Tries direct mTLS first: it involves no third party and cannot be forged by
    the caller. The proxy path is a fallback for deployments that terminate TLS
    at the edge, and it is closed unless an allowlist is configured.
    """
    fingerprint = fingerprint_from_scope(scope)
    source = "mtls"
    if fingerprint is None:
        fingerprint = fingerprint_from_proxy(headers, peer_address)
        source = "trusted-proxy"

    if fingerprint is None:
        if not trusted_proxies() and not (scope.get("extensions") or {}).get("tls"):
            # Nothing is configured at all — say so distinctly, because
            # "misconfigured" and "rejected" need different operator responses.
            raise NodeAuthUnconfigured()
        raise InvError(
            AUTH_MISSING_CREDENTIAL,
            "no verified client certificate was presented",
            public=False,
        )

    return resolve_node(session, fingerprint=fingerprint, source=source)
