"""Reclaim only cancelled Runs for which no execution permit was ever issued.

Caller holds the Run lock used by ToolGateway, then locks Nodes/resources in
global order. A sent, queued, expired or ambiguous claim always needs Node proof.
"""

from uuid import uuid4
from .leases import fence
from .runs import event


def reclaim_unclaimed(conn, tenant, row, epoch, *, reason, proofs=None):
    if (
        row["state"] != "cancelled"
        or conn.execute(
            "SELECT 1 FROM inv.tool_claims WHERE run_id=%s", (row["run_id"],)
        ).fetchone()
        or conn.execute(
            "SELECT 1 FROM inv.run_attempts WHERE run_id=%s", (row["run_id"],)
        ).fetchone()
    ):
        return False
    leases = conn.execute(
        "SELECT * FROM inv.resource_leases WHERE run_id=%s AND released_at IS NULL ORDER BY lease_id",
        (row["run_id"],),
    ).fetchall()
    if not leases:
        return False
    if any(str(l["recovery_epoch"]) != epoch for l in leases):
        return False
    if proofs is not None and proofs != {l["lease_id"]: fence(l) for l in leases}:
        return False
    receipt = uuid4()
    conn.execute(
        "INSERT INTO inv.reservation_aborts(tenant_id,project_id,run_id,abort_id,reason,recovery_epoch) VALUES(%s,%s,%s,%s,%s,%s)",
        (tenant, row["project_id"], row["run_id"], receipt, reason, epoch),
    )
    conn.execute(
        "UPDATE inv.resource_leases SET released_at=clock_timestamp(),reservation_abort=%s WHERE lease_id=ANY(%s)",
        (receipt, [l["lease_id"] for l in leases]),
    )
    event(
        conn,
        tenant,
        row["run_id"],
        "inv.reservation.reclaimed",
        {"runId": row["run_id"], "reason": reason, "abortId": str(receipt)},
    )
    return True
