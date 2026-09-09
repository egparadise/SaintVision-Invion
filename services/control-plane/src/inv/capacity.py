"""Three distinct CPU/memory capacity figures from authorized current observations.

Read model only. Reservation always rechecks offers and Leases under row locks.
Measured busy capacity and reservations are conservatively subtracted separately.
"""

from .contracts import validate_contract


def project_capacity(conn, project, epoch):
    rows = conn.execute(
        """SELECT n.node_id,n.status,r.kind,r.capacity,r.offered,
        coalesce((SELECT sum(l.amount) FROM inv.resource_leases l WHERE l.tenant_id=r.tenant_id AND l.resource_id=r.resource_id AND l.released_at IS NULL),0) AS reserved,
        CASE WHEN s.recovery_epoch=%s::uuid AND s.channel_version=c.version AND c.enabled
        AND c.certificate_not_after>clock_timestamp() AND c.recovery_epoch=s.recovery_epoch
        AND s.received_at BETWEEN clock_timestamp()-interval '15 seconds' AND clock_timestamp()
        AND n.heartbeat_at BETWEEN clock_timestamp()-interval '15 seconds' AND clock_timestamp()
        AND n.recovery_epoch=s.recovery_epoch THEN s.snapshot END AS snapshot
        FROM inv.project_nodes p JOIN inv.nodes n USING(tenant_id,node_id)
        JOIN inv.resources r USING(tenant_id,node_id)
        LEFT JOIN inv.node_resource_snapshots s USING(tenant_id,node_id)
        LEFT JOIN inv.node_channels c USING(tenant_id,node_id)
        WHERE p.project_id=%s AND p.enabled AND n.status='online' AND r.kind IN ('cpu','memory')
        ORDER BY n.node_id,r.resource_id""",
        (epoch, project),
    ).fetchall()
    nodes = {}
    for row in rows:
        node = nodes.setdefault(
            row["node_id"],
            {
                "nodeId": row["node_id"],
                "offered": {"cpuMillis": 0, "memoryBytes": 0},
                "spare": {"cpuMillis": 0, "memoryBytes": 0},
                "measured": True,
            },
        )
        key = "cpuMillis" if row["kind"] == "cpu" else "memoryBytes"
        node["offered"][key] += row["offered"]
        snapshot = row["snapshot"]
        if snapshot is None:
            node["measured"] = False
            continue
        validate_contract("NodeResourceSnapshot", snapshot)
        if (
            snapshot["cpuBusyMillis"] > snapshot["cpuCapacityMillis"]
            or snapshot["memoryAvailableBytes"] > snapshot["memoryCapacityBytes"]
        ):
            node["measured"] = False
            continue
        available = (
            snapshot["cpuCapacityMillis"] - snapshot["cpuBusyMillis"]
            if key == "cpuMillis"
            else snapshot["memoryAvailableBytes"]
        )
        node["spare"][key] += max(
            0, min(row["offered"], available) - int(row["reserved"])
        )
    # A host observation cannot be counted twice if an operator defines several
    # resources of the same kind. Cap aggregate spare at measured host capacity.
    for node in nodes.values():
        samples = [
            r["snapshot"]
            for r in rows
            if r["node_id"] == node["nodeId"] and r["snapshot"]
        ]
        if not node["measured"] or not samples:
            node["spare"] = {"cpuMillis": 0, "memoryBytes": 0}
        else:
            sample = samples[0]
            for key, kind, available in [
                (
                    "cpuMillis",
                    "cpu",
                    sample["cpuCapacityMillis"] - sample["cpuBusyMillis"],
                ),
                ("memoryBytes", "memory", sample["memoryAvailableBytes"]),
            ]:
                reserved = sum(
                    int(r["reserved"])
                    for r in rows
                    if r["node_id"] == node["nodeId"] and r["kind"] == kind
                )
                node["spare"][key] = max(
                    0, min(node["spare"][key], available - reserved)
                )
    result = {
        "projectId": project,
        "totalOffered": {},
        "largestSingleNode": {},
        "spareNow": {},
        "nodes": list(nodes.values()),
        "unmeasuredNodes": [n["nodeId"] for n in nodes.values() if not n["measured"]],
    }
    for key in ("cpuMillis", "memoryBytes"):
        result["totalOffered"][key] = sum(n["offered"][key] for n in nodes.values())
        result["largestSingleNode"][key] = max(
            (n["offered"][key] for n in nodes.values()), default=0
        )
        result["spareNow"][key] = sum(n["spare"][key] for n in nodes.values())
    result["note"] = (
        "CPU/memory only; per-dimension maxima are not a joint fit or shared RAM. Snapshot estimates do not reserve capacity."
    )
    return result
