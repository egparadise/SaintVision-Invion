"""Replica health and repair planning (VF-CL-04, contract-independent part).

The Fabric design has two structural rules this service serves (ARCH-WEB-FABRIC-001,
PLAN-STORAGE-001):

* **a single lost copy must not lose the item** -- a catalogued location wants a
  policy number of ``ready`` replicas, and one below that is *under-replicated*,
  a state to repair, not a failure;
* **a node leaving marks its replicas unavailable, it does not destroy the item**
  -- the location and the manifest survive; only the copies on the departed node
  become unusable.

What this service does and does not do:

* it **assesses** health and **plans** repair -- which locations are short of
  ready copies and which nodes still hold one to copy from. It does not move
  bytes; establishing a new replica is a node-runtime transfer (VF-CX-03/04),
  and the plan is its input, not its replacement.
* the **replica factor** (how many ready copies a location should have) is a
  policy decision, not invented here: it is a parameter with a stated default,
  and the real per-classification policy is the operator's / Codex's to set.

Only ``ready`` counts as a usable copy. ``transferring`` is not yet readable,
``stale`` is a copy on a departed or unverified node, ``corrupt`` failed its
checksum, ``evicted`` was reclaimed for cache space -- none of them satisfy the
replica factor, which is the whole point of counting them separately.
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db.models.locality import DataReplica
from ..db.models.storage import DataLocation
from ..errors import InvError, RES_ARTIFACT_NOT_FOUND, VAL_SCHEMA

#: Default number of ``ready`` replicas a catalogued item should have. A policy
#: value, overridable per call; the real per-classification policy is set by the
#: operator, not fixed here.
DEFAULT_REPLICA_FACTOR = 2

#: Replica states that do not count toward the replica factor, with why.
UNUSABLE_STATES = ("transferring", "stale", "corrupt", "evicted")

#: When a node departs, these of its replicas become unavailable. An already
#: evicted or corrupt row is left as it is -- its state already tells the truth.
_LOSABLE_ON_DEPARTURE = ("ready", "transferring")


@dataclass(frozen=True)
class ReplicaHealth:
    """The replica picture for one catalogued location."""

    location_id: str
    ready: int
    unusable: dict[str, int]
    desired: int
    classification: str  # healthy | under_replicated | at_risk | unreplicated
    source_nodes: list[str] = field(default_factory=list)

    @property
    def needs_repair(self) -> bool:
        return self.classification != "healthy"

    @property
    def deficit(self) -> int:
        return max(0, self.desired - self.ready)


def _classify(ready: int, total: int, desired: int) -> str:
    if ready >= desired:
        return "healthy"
    if ready > 0:
        return "under_replicated"
    if total > 0:
        # Copies exist but none is usable (all transferring/stale/corrupt/evicted).
        return "at_risk"
    return "unreplicated"


def replica_health(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    location_id: str,
    desired: int = DEFAULT_REPLICA_FACTOR,
) -> ReplicaHealth:
    """Assess one location's replica health against the replica factor."""
    if desired < 1:
        raise InvError(VAL_SCHEMA, "replica factor must be at least 1")
    location = session.get(DataLocation, location_id)
    if location is None or location.tenant_id != tenant_id:
        raise InvError(RES_ARTIFACT_NOT_FOUND, "data location not found")

    rows = session.execute(
        select(DataReplica.state, func.count())
        .where(
            DataReplica.tenant_id == tenant_id,
            DataReplica.location_id == location_id,
        )
        .group_by(DataReplica.state)
    ).all()
    counts = {state: n for state, n in rows}
    ready = counts.get("ready", 0)
    total = sum(counts.values())
    unusable = {s: counts[s] for s in UNUSABLE_STATES if s in counts}

    source_nodes: list[str] = []
    if ready < desired and ready > 0:
        source_nodes = list(
            session.scalars(
                select(DataReplica.node_id)
                .where(
                    DataReplica.tenant_id == tenant_id,
                    DataReplica.location_id == location_id,
                    DataReplica.state == "ready",
                )
                .order_by(DataReplica.node_id)
            ).all()
        )

    return ReplicaHealth(
        location_id=location_id,
        ready=ready,
        unusable=unusable,
        desired=desired,
        classification=_classify(ready, total, desired),
        source_nodes=source_nodes,
    )


def locations_needing_repair(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    desired: int = DEFAULT_REPLICA_FACTOR,
    limit: int | None = None,
) -> list[ReplicaHealth]:
    """Every catalogued location with fewer than ``desired`` ready replicas.

    Locations with no replica at all are included: ``unreplicated`` is the most
    urgent repair, not an item to skip because it has nothing to count.
    """
    location_ids = list(
        session.scalars(
            select(DataLocation.location_id)
            .where(DataLocation.tenant_id == tenant_id)
            .order_by(DataLocation.location_id)
        ).all()
    )
    out: list[ReplicaHealth] = []
    for location_id in location_ids:
        health = replica_health(
            session, tenant_id=tenant_id, location_id=location_id, desired=desired
        )
        if health.needs_repair:
            out.append(health)
            if limit is not None and len(out) >= limit:
                break
    return out


@dataclass(frozen=True)
class FleetReplicaSummary:
    """Replica health across a tenant's whole catalogue, for metrics/runbook.

    ``at_risk`` and ``unreplicated`` are the numbers a runbook pages on: an item
    with no usable copy is one node-loss or one corruption from being gone. They
    are reported separately from ``under_replicated`` because the response
    differs -- repair soon versus repair now.
    """

    locations: int
    healthy: int
    under_replicated: int
    at_risk: int
    unreplicated: int

    @property
    def needing_repair(self) -> int:
        return self.under_replicated + self.at_risk + self.unreplicated

    def to_dict(self) -> dict[str, int]:
        return {
            "locations": self.locations,
            "healthy": self.healthy,
            "underReplicated": self.under_replicated,
            "atRisk": self.at_risk,
            "unreplicated": self.unreplicated,
            "needingRepair": self.needing_repair,
        }


def fleet_replica_summary(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    desired: int = DEFAULT_REPLICA_FACTOR,
) -> FleetReplicaSummary:
    """Aggregate every catalogued location's classification into one summary.

    The observability source for VF-CL-04: a metrics endpoint or runbook reads
    this rather than recomputing per-location classification itself, so the
    definition of "at risk" lives in one place.
    """
    if desired < 1:
        raise InvError(VAL_SCHEMA, "replica factor must be at least 1")
    tally = {"healthy": 0, "under_replicated": 0, "at_risk": 0, "unreplicated": 0}
    location_ids = list(
        session.scalars(
            select(DataLocation.location_id).where(DataLocation.tenant_id == tenant_id)
        ).all()
    )
    for location_id in location_ids:
        health = replica_health(
            session, tenant_id=tenant_id, location_id=location_id, desired=desired
        )
        tally[health.classification] += 1
    return FleetReplicaSummary(
        locations=len(location_ids),
        healthy=tally["healthy"],
        under_replicated=tally["under_replicated"],
        at_risk=tally["at_risk"],
        unreplicated=tally["unreplicated"],
    )


def mark_node_replicas_unavailable(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    node_id: str,
    now: dt.datetime,
) -> int:
    """A node has departed: mark its usable replicas ``stale``, keep the items.

    Implements the rule that node loss touches copies, not catalogue: the
    ``data_locations`` rows and their manifests are untouched, and only the
    ``ready``/``transferring`` replicas on the departed node move to ``stale``.
    Returns how many replicas were marked, so the caller can see the blast
    radius. The decision that the node has departed is the caller's
    (heartbeat/containment); this only records its storage consequence.
    """
    replicas = list(
        session.scalars(
            select(DataReplica).where(
                DataReplica.tenant_id == tenant_id,
                DataReplica.node_id == node_id,
                DataReplica.state.in_(_LOSABLE_ON_DEPARTURE),
            )
        ).all()
    )
    for replica in replicas:
        replica.state = "stale"
    if replicas:
        session.flush()
    return len(replicas)
