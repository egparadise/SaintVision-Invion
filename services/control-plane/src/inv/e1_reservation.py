"""E1 transaction prerequisite. No production fence provider is installed."""
import hashlib
import json
import re
from uuid import UUID

from psycopg.types.json import Jsonb

PC1 = "nod_00000000000000000000000PC1"
FIELDS = {"tenantID", "epoch", "pc", "nodeID", "csrSHA256", "planDigest",
          "fenceToken", "rowsReadbackSHA256", "nodeStateEmpty"}


def reserve_pc1(conn, request_id, holder, generation, binding, *, lock_authority=None):
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
    canonical = json.dumps(binding, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    with conn.transaction():
        authority = lock_authority(conn, tenant)
        if authority is None:
            return "HOLD_AUTHORITY_UNAVAILABLE"
        active_holder, active_generation, approved_binding = authority
        if (holder, generation) != (active_holder, active_generation):
            return "HOLD_WRITER_FENCE"
        if binding != approved_binding:
            return "HOLD_RESERVATION_MISMATCH"
        row = conn.execute("""
            INSERT INTO e1.reservations
                (tenant_id, pc, node_id, request_id, holder, generation, binding, digest)
            VALUES (%s, 'PC1', %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING RETURNING digest
        """, (tenant, PC1, request, holder, generation, Jsonb(binding), digest)).fetchone()
        if row:
            return "RESERVED"
        exact = conn.execute("""
            SELECT 1 FROM e1.reservations WHERE tenant_id=%s AND request_id=%s
            AND holder=%s AND generation=%s AND binding=%s AND digest=%s
        """, (tenant, request, holder, generation, Jsonb(binding), digest)).fetchone()
        return "EXACT_RETRY" if exact else "HOLD_RESERVATION_MISMATCH"
