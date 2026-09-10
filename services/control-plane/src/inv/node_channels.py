"""Operator-owned certificate bindings. Runtime can read/lock, never provision.

Network I/O runs outside DB transactions. Receipt commit rechecks a frozen proof.
Node enrollment, CA issuance and OIDC administration remain separate adapters.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import ipaddress
import re
from urllib.parse import urlsplit
from uuid import UUID
from psycopg.rows import tuple_row
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.x509.oid import ExtendedKeyUsageOID
from .errors import DomainError
from .tooling import NodePrincipal


def node_uri(node, epoch):
    return f"spiffe://saintvision.ai/tenant/{node.tenant_id}/node/{node.node_id}/epoch/{epoch}"


def endpoint_parts(endpoint):
    try:
        u = urlsplit(endpoint)
        host, port = u.hostname, 443 if u.port is None else u.port
        if (
            not isinstance(endpoint, str)
            or len(endpoint) > 2048
            or not endpoint.isascii()
            or any(c.isspace() or ord(c) < 32 for c in endpoint)
            or u.scheme != "https"
            or not host
            or u.username is not None
            or u.password is not None
            or u.path not in {"", "/"}
            or u.query
            or u.fragment
            or not 1 <= port <= 65535
        ):
            raise ValueError()
        try:
            ipaddress.ip_address(host)
        except ValueError:
            if not re.fullmatch(
                r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?", host
            ):
                raise ValueError()
        return host, port
    except (ValueError, TypeError, AttributeError):
        raise DomainError(
            "NODE-0031", "An explicit HTTPS origin is required", 422
        ) from None


def certificate_identity(der, node, epoch, *, now=None):
    now = now or datetime.now(timezone.utc)
    try:
        cert = x509.load_der_x509_certificate(der)
        uris = cert.extensions.get_extension_for_class(
            x509.SubjectAlternativeName
        ).value.get_values_for_type(x509.UniformResourceIdentifier)
        usages = cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
        constraints = cert.extensions.get_extension_for_class(
            x509.BasicConstraints
        ).value
        if (
            uris != [node_uri(node, epoch)]
            or constraints.ca
            or ExtendedKeyUsageOID.SERVER_AUTH not in usages
            or not cert.not_valid_before_utc <= now < cert.not_valid_after_utc
        ):
            raise ValueError()
        return cert.fingerprint(hashes.SHA256()).hex(), cert.not_valid_after_utc
    except (ValueError, TypeError, x509.ExtensionNotFound):
        raise DomainError(
            "NODE-0032", "Node certificate identity rejected", 403
        ) from None


@dataclass(frozen=True)
class ChannelProof:
    tenant_id: str
    node_id: str
    recovery_epoch: str
    version: int
    endpoint: str
    certificate_sha256: str


def proof(row):
    return ChannelProof(
        str(row["tenant_id"]),
        row["node_id"],
        str(row["recovery_epoch"]),
        row["version"],
        row["endpoint"],
        row["certificate_sha256"],
    )


def assert_channel(conn, expected):
    row = conn.execute(
        "SELECT * FROM inv.node_channels WHERE node_id=%s FOR SHARE",
        (expected.node_id,),
    ).fetchone()
    now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
    if (
        not row
        or not row["enabled"]
        or row["certificate_not_after"] <= now
        or proof(row) != expected
    ):
        raise DomainError("NODE-0033", "Node channel authority changed or expired", 403)
    return row


class NodeChannels:
    def __init__(self, database):
        self.db = database

    def snapshot(self, node, *, observation_only=False):
        with self.db.transaction(node.tenant_id) as conn:
            if not observation_only:
                from .containment import require_execution

                require_execution(conn)
            row = conn.execute(
                "SELECT *,clock_timestamp() AS now FROM inv.nodes WHERE node_id=%s FOR SHARE",
                (node.node_id,),
            ).fetchone()
            if not row or str(row["recovery_epoch"]) != self.db.recovery_epoch:
                raise DomainError("NODE-0033", "Node channel epoch differs", 403)
            if not observation_only and (
                row["status"] != "online"
                or not 0 <= (row["now"] - row["heartbeat_at"]).total_seconds() <= 15
            ):
                raise DomainError("NODE-0033", "Node is not current and online", 403)
            channel = conn.execute(
                "SELECT * FROM inv.node_channels WHERE node_id=%s", (node.node_id,)
            ).fetchone()
            if not channel or str(channel["recovery_epoch"]) != self.db.recovery_epoch:
                raise DomainError("NODE-0033", "Node channel is unavailable", 403)
            result = proof(channel)
            assert_channel(conn, result)
            return result


def provision_channel(
    conn, node: NodePrincipal, *, epoch, endpoint, certificate_der, expected_version
):
    """Trusted operator connection only; DB grants enforce that separation.

    Call within the operator's transaction/tenant context. No runtime HTTP route.
    The candidate certificate identity is derived from bytes, never a body hash.
    """
    endpoint_parts(endpoint)
    epoch = str(UUID(epoch))
    fingerprint, not_after = certificate_identity(certificate_der, node, epoch)
    with conn.transaction(), conn.cursor(row_factory=tuple_row) as cursor:
        current_epoch = cursor.execute(
            "SELECT epoch FROM inv.control_epoch WHERE singleton FOR SHARE"
        ).fetchone()
        if not current_epoch or str(current_epoch[0]) != epoch:
            raise DomainError("NODE-0033", "Operator epoch differs", 403)
        row = cursor.execute(
            "SELECT recovery_epoch FROM inv.nodes WHERE tenant_id=%s AND node_id=%s FOR UPDATE",
            (node.tenant_id, node.node_id),
        ).fetchone()
        if not row or str(row[0]) != epoch:
            raise DomainError("NODE-0033", "Node epoch differs", 403)
        previous = cursor.execute(
            "SELECT version FROM inv.node_channels WHERE tenant_id=%s AND node_id=%s FOR UPDATE",
            (node.tenant_id, node.node_id),
        ).fetchone()
        if type(expected_version) is not int or expected_version != (
            previous[0] if previous else 0
        ):
            raise DomainError("NODE-0034", "Channel version conflict", 409)
        version = expected_version + 1
        cursor.execute(
            """INSERT INTO inv.node_channels(tenant_id,node_id,recovery_epoch,version,endpoint,certificate_sha256,certificate_not_after,enabled)
            VALUES(%s,%s,%s,%s,%s,%s,%s,true) ON CONFLICT(tenant_id,node_id) DO UPDATE SET
            recovery_epoch=excluded.recovery_epoch,version=excluded.version,endpoint=excluded.endpoint,
            certificate_sha256=excluded.certificate_sha256,certificate_not_after=excluded.certificate_not_after,enabled=true""",
            (
                node.tenant_id,
                node.node_id,
                epoch,
                version,
                endpoint,
                fingerprint,
                not_after,
            ),
        )
        cursor.execute(
            "INSERT INTO inv.node_channel_audit(tenant_id,node_id,version,action,certificate_sha256) VALUES(%s,%s,%s,'provision',%s)",
            (node.tenant_id, node.node_id, version, fingerprint),
        )
        return version


def revoke_channel(conn, node: NodePrincipal, *, expected_version):
    with conn.transaction(), conn.cursor(row_factory=tuple_row) as cursor:
        cursor.execute(
            "SELECT node_id FROM inv.nodes WHERE tenant_id=%s AND node_id=%s FOR UPDATE",
            (node.tenant_id, node.node_id),
        ).fetchone()
        row = cursor.execute(
            "SELECT version,certificate_sha256 FROM inv.node_channels WHERE tenant_id=%s AND node_id=%s FOR UPDATE",
            (node.tenant_id, node.node_id),
        ).fetchone()
        if not row or type(expected_version) is not int or row[0] != expected_version:
            raise DomainError("NODE-0034", "Channel version conflict", 409)
        version = expected_version + 1
        cursor.execute(
            "UPDATE inv.node_channels SET enabled=false,version=%s WHERE tenant_id=%s AND node_id=%s",
            (version, node.tenant_id, node.node_id),
        )
        cursor.execute(
            "INSERT INTO inv.node_channel_audit(tenant_id,node_id,version,action,certificate_sha256) VALUES(%s,%s,%s,'revoke',%s)",
            (node.tenant_id, node.node_id, version, row[1]),
        )
        return version
