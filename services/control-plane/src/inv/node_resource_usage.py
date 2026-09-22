"""Capability-specific allocation usage for one registered Node (decision #2 A).

Serves ``GET /v1/projects/{project}/nodes/{node_id}/resource-usage`` as the strict
``NodeResourceUsageResponse`` contract. This is a READ MODEL over the kernel's own
observations -- ``inv.resources`` (capacity/offered), unreleased ``inv.resource_leases``
(reserved) and the authorized, fresh ``inv.node_resource_snapshots`` row (observation
time). Reservation never reads this; it rechecks offers and leases under row locks.

Honesty rules (contract + F4 lesson "capacity must not degrade to 0"):

* A resource whose Node has NO fresh, authorized observation is reported with
  ``measured=false`` and ``reserved/spare/observedAt=null``. Nothing is synthesized
  as 0. "Fresh, authorized" is exactly the predicate ``capacity.py`` uses (same
  recovery epoch, channel version, enabled channel, unexpired certificate, snapshot
  and heartbeat within 15 seconds) so the two read models cannot disagree about
  whether a Node is observed.
* ``reserved`` is the sum of unreleased lease amounts; ``spare = offered - reserved``.
  If the stored state violates ``0 <= reserved <= offered`` the response is refused
  loudly (500-class DomainError) instead of clamping, because a clamped number would
  be a plausible lie.
* Discovery claims are never projected: only ``inv.resources`` rows of a Node that is
  linked to the project (``inv.project_nodes.enabled``) are returned; an unlinked or
  unknown Node is 404 to the project, not an empty list.
* Units are a property of the kind (canonical since migration 0010); the mapping is
  fixed here and the contract enum rejects anything else.

Owner: Claude (middle-difficulty read API). The kernel route in ``app.py`` only
delegates to :func:`serve`.
"""

from __future__ import annotations

from .contracts import validate_contract
from .errors import DomainError

#: Canonical unit per resource kind (matches ``inv.resources.kind`` CHECK and the
#: ``ResourceUsageMeasurement.unit`` enum). Not configurable: the unit is the kind.
UNITS = {
    "cpu": "millicores",
    "memory": "bytes",
    "gpu": "devices",
    "storage": "bytes",
    "network": "bitsPerSecond",
}

FRESH_WINDOW_SECONDS = 15


def serve(control, principal, project, node_id):
    """HTTP handler body: authorize the project grant, then build the read model."""
    validate_contract("NodeId", node_id)
    with control.db.transaction(principal.tenant_id) as conn:
        control.grant(conn, principal, project)
        return node_resource_usage(conn, project, node_id, control.db.recovery_epoch)


def node_resource_usage(conn, project, node_id, epoch):
    """Build and contract-check one ``NodeResourceUsageResponse`` inside ``conn``."""
    linked = conn.execute(
        "SELECT 1 FROM inv.project_nodes p JOIN inv.nodes n USING(tenant_id,node_id) "
        "WHERE p.project_id=%s AND p.node_id=%s AND p.enabled",
        (project, node_id),
    ).fetchone()
    if not linked:
        raise DomainError("RES-0004", "Node unavailable", 404)
    rows = conn.execute(
        """SELECT r.resource_id,r.kind,r.capacity,r.offered,
        coalesce((SELECT sum(l.amount) FROM inv.resource_leases l
                  WHERE l.tenant_id=r.tenant_id AND l.resource_id=r.resource_id AND l.released_at IS NULL),0) AS reserved,
        CASE WHEN s.recovery_epoch=%s::uuid AND s.channel_version=c.version AND c.enabled
        AND c.certificate_not_after>clock_timestamp() AND c.recovery_epoch=s.recovery_epoch
        AND s.received_at BETWEEN clock_timestamp()-make_interval(secs => %s) AND clock_timestamp()
        AND n.heartbeat_at BETWEEN clock_timestamp()-make_interval(secs => %s) AND clock_timestamp()
        AND n.recovery_epoch=s.recovery_epoch THEN s.received_at END AS observed_at
        FROM inv.resources r JOIN inv.nodes n USING(tenant_id,node_id)
        LEFT JOIN inv.node_resource_snapshots s USING(tenant_id,node_id)
        LEFT JOIN inv.node_channels c USING(tenant_id,node_id)
        WHERE r.node_id=%s ORDER BY r.resource_id""",
        (epoch, FRESH_WINDOW_SECONDS, FRESH_WINDOW_SECONDS, node_id),
    ).fetchall()
    resources = []
    state_as_of = None
    for row in rows:
        kind = row["kind"]
        if kind not in UNITS:
            raise DomainError("RES-0010", "Resource kind outside the canonical set", 500)
        capacity = int(row["capacity"])
        offered = int(row["offered"])
        reserved = int(row["reserved"])
        if not 0 <= reserved <= offered <= capacity:
            # Refuse rather than clamp: the invariant is the contract's meaning.
            raise DomainError("RES-0011", "Resource allocation invariant violated", 500)
        observed = row["observed_at"]
        measured = observed is not None
        if measured and (state_as_of is None or observed > state_as_of):
            state_as_of = observed
        resources.append(
            {
                "resourceId": row["resource_id"],
                "kind": kind,
                "unit": UNITS[kind],
                "capacity": capacity,
                "offered": offered,
                "reserved": reserved if measured else None,
                "spare": offered - reserved if measured else None,
                "measured": measured,
                "observedAt": observed.isoformat() if measured else None,
            }
        )
    response = {
        "source": "execution-kernel",
        "nodeId": node_id,
        "stateAsOf": state_as_of.isoformat() if state_as_of is not None else None,
        "resources": resources,
    }
    validate_contract("NodeResourceUsageResponse", response)
    return response
