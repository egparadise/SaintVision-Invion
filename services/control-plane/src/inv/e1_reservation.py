"""E1 transaction prerequisite. No production fence provider is installed."""
import base64
import hashlib
import json
import re
from uuid import UUID

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.x509.oid import NameOID
from psycopg import Rollback
from psycopg.pq import TransactionStatus
from psycopg.types.json import Jsonb

PC1 = "nod_00000000000000000000000PC1"
FIELDS = {"tenantID", "epoch", "pc", "nodeID", "csrSHA256", "planDigest",
          "fenceToken", "rowsReadbackSHA256", "nodeStateEmpty"}


def canonical_digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def csr_key(encoded, expected_digest):
    if not isinstance(encoded, str) or len(encoded) > 16384:
        return None
    try:
        raw = base64.b64decode(encoded, validate=True)
        csr = x509.load_der_x509_csr(raw)
        key = csr.public_key()
        names = csr.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        if (hashlib.sha256(raw).hexdigest() != expected_digest or len(names) != 1
                or names[0].value != PC1 or not isinstance(key, Ed25519PublicKey)
                or not csr.is_signature_valid):
            return None
        spki = key.public_bytes(serialization.Encoding.DER,
                                serialization.PublicFormat.SubjectPublicKeyInfo)
        return hashlib.sha256(spki).hexdigest()
    except (ValueError, TypeError):
        return None


def eligible(binding, evidence, key):
    """Evidence is read from the authenticated provider under its tenant lock."""
    manifest = evidence.get("manifest")
    if (not isinstance(manifest, str) or not re.fullmatch("[0-9a-f]{64}", manifest)
            or evidence.get("a7") != [binding["planDigest"], manifest, "COMMITTED"]
            or evidence.get("epoch") != binding["epoch"]
            or not isinstance(evidence.get("operation"), str)
            or not 0 < len(evidence["operation"]) <= 256):
        return False
    rows = evidence.get("rows")
    rotation = evidence.get("rotationKeys")
    if (evidence.get("authenticatedAllHistory") is not True or not isinstance(rows, list)
            or not isinstance(rotation, list) or len(rotation) != 3
            or any(not isinstance(k, str) or not re.fullmatch("[0-9a-f]{64}", k) for k in rotation)
            or evidence.get("plannedPublicKey") != key or key in rotation or canonical_digest(rows) != binding["rowsReadbackSHA256"]):
        return False
    for row in rows:
        if (not isinstance(row, dict) or not row.get("nodeID") or not row.get("status")
                or any(not isinstance(row.get(field), str)
                       or not re.fullmatch("[0-9a-f]{64}", row[field])
                       for field in ("publicKeySHA256", "channelCertificateSHA256"))
                or PC1 == row["nodeID"] or key == row["publicKeySHA256"]):
            return False
    return True


def reserve_pc1(conn, request_id, holder, generation, binding, *, csr_der=None, lock_authority=None):
    """Caller commits the encompassing transaction before acknowledging the result.

    The trusted adapter must lock the current tenant authority on this connection
    through commit and derive the eligible R2 binding from verified A7, node and
    inventory evidence. An unavailable or unverified precondition returns None.
    """
    if lock_authority is None or conn is None:
        return "HOLD_AUTHORITY_UNAVAILABLE"
    if not isinstance(binding, dict) or set(binding) != FIELDS:
        return "HOLD_RESERVATION_MISMATCH"
    proof = binding["nodeStateEmpty"]
    if (binding["pc"] != "PC1" or binding["nodeID"] != PC1
            or not isinstance(proof, dict) or proof.get("verified") is not True
            or not isinstance(proof.get("evidenceRef"), str) or not proof["evidenceRef"].strip()
            or not isinstance(holder, str) or not holder.strip()
            or type(generation) is not int or generation < 1
            or not isinstance(binding["fenceToken"], str) or not binding["fenceToken"].strip()):
        return "HOLD_RESERVATION_MISMATCH"
    for field in ("csrSHA256", "planDigest", "rowsReadbackSHA256"):
        if not re.fullmatch("[0-9a-f]{64}", str(binding[field])):
            return "HOLD_RESERVATION_MISMATCH"
    try:
        tenant = UUID(binding["tenantID"])
        epoch = UUID(binding["epoch"])
        request = UUID(request_id)
    except (ValueError, TypeError, AttributeError):
        return "HOLD_RESERVATION_MISMATCH"
    if str(tenant) != binding["tenantID"] or str(epoch) != binding["epoch"]:
        return "HOLD_RESERVATION_MISMATCH"
    digest = canonical_digest(binding)
    key = csr_key(csr_der, binding["csrSHA256"])
    if key is None:
        return "HOLD_RESERVATION_MISMATCH"
    with conn.transaction() as transaction:
        # Tenant context is supplied by the authenticated operator connection.
        context = conn.execute("SELECT current_setting('inv.tenant_id',true)").fetchone()[0]
        if context != str(tenant):
            return "HOLD_AUTHORITY_UNAVAILABLE"
        authority = lock_authority(conn, tenant)
        if authority is None:
            return "HOLD_AUTHORITY_UNAVAILABLE"
        active_holder, active_generation, approved_binding, evidence = authority
        if (holder, generation) != (active_holder, active_generation):
            return "HOLD_WRITER_FENCE"
        if not isinstance(evidence, dict) or evidence.get("freshFence") is not True:
            return "HOLD_WRITER_FENCE"
        if binding != approved_binding:
            return "HOLD_RESERVATION_MISMATCH"
        if not isinstance(evidence, dict) or not eligible(binding, evidence, key):
            return "HOLD_AUTHORITY_UNAVAILABLE"
        manifest, operation = evidence["manifest"], evidence["operation"]
        receipt = (tenant, PC1, request, holder, generation, Jsonb(binding), digest,
                   key, manifest, operation)
        created = conn.execute("""
            INSERT INTO e1.reservations
                (tenant_id, pc, node_id, request_id, holder, generation, binding, digest,
                 public_key_sha256, manifest_digest, operation_id)
            VALUES (%s, 'PC1', %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING RETURNING digest
        """, receipt).fetchone()
        if created:
            conn.execute("""
                INSERT INTO e1.reservation_audit (tenant_id,operation_id,manifest_digest,digest)
                VALUES (%s,%s,%s,%s)
            """, (tenant, operation, manifest, digest))
        exact = conn.execute("""
            SELECT 1 FROM e1.reservations r JOIN e1.reservation_audit a
                USING (tenant_id, operation_id, manifest_digest, digest)
            WHERE tenant_id=%s AND node_id=%s AND request_id=%s AND holder=%s
              AND generation=%s AND binding=%s AND digest=%s AND public_key_sha256=%s
              AND manifest_digest=%s AND operation_id=%s
        """, receipt).fetchone()
        if not exact:
            if created:
                raise RuntimeError("E1 journal readback failed")
            return "HOLD_RESERVATION_MISMATCH"
        if lock_authority(conn, tenant) != authority:
            raise Rollback(transaction)
        return "RESERVED" if created else "EXACT_RETRY"
    return "HOLD_WRITER_FENCE"


def reconcile_pc1(conn, request_id, holder, generation, binding, public_key, manifest, operation):
    """Resolve a lost acknowledgement on a fresh, authenticated reader connection."""
    if (conn is None or not conn.autocommit
            or conn.info.transaction_status != TransactionStatus.IDLE):
        return "UNKNOWN_RECONCILE_REQUIRED"
    digest = canonical_digest(binding)
    with conn.transaction():
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        context = conn.execute("SELECT current_setting('inv.tenant_id',true)").fetchone()[0]
        if context != binding["tenantID"]:
            return "HOLD_AUTHORITY_UNAVAILABLE"
        row = conn.execute("""
            SELECT r.request_id::text,r.holder,r.generation,r.binding,r.digest,r.public_key_sha256,
                   r.manifest_digest,r.operation_id,a.digest
            FROM e1.reservations r LEFT JOIN e1.reservation_audit a
              USING (tenant_id,operation_id,manifest_digest,digest)
            WHERE tenant_id=%s AND pc='PC1'
        """, (context,)).fetchone()
        if row is None:
            return "UNKNOWN_RECONCILE_REQUIRED"
        expected = (request_id, holder, generation, binding, digest, public_key,
                    manifest, operation, digest)
        return "COMMITTED" if row == expected else "HOLD_RESERVATION_MISMATCH"
