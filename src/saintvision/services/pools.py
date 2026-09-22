"""Resource pools: aggregating what the machines offer, and spreading work.

This is the product's purpose — connect the CPU, GPU, RAM and folders that five
machines offer and use them together. Two things make that honest rather than a
number on a dashboard.

**Three capacity figures, never one.**

``totalOffered``
    The sum across the pool. What it can do across many concurrent tasks.
``largestSingleNode``
    The ceiling for one task that cannot be split. A pool with five 32 GB
    machines does not run a 64 GB job that has not been sharded.
``spareNow``
    What is idle right now, from the latest resource snapshots. This is what
    idle-first placement ranks on.

Reporting only the sum would tell someone their 160 GB pool can run a 64 GB
job. It cannot, unless the job shards — and then it runs as five pieces, each
inside one machine.

**Idle-first placement.** Nodes are ranked by spare capacity, so work lands
where the machines are resting rather than on whichever node was found first.
Ties break on ``node_id`` so the same inputs give the same placement, which is
what makes a placement decision explainable afterwards (ADR-005 uses the same
tie-break rule).
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db.models import (
    DistributedPlan,
    Node,
    NodeCapability,
    PlanPlacement,
    ResourceOffer,
    ResourcePool,
    ResourcePoolMember,
    ResourceSnapshot,
)
from ..errors import RES_NODE_NOT_FOUND, VAL_SCHEMA, InvError
from ..ids import new_id
from ..units import CANONICAL_UNIT, KINDS

#: How far back a utilisation snapshot still counts as "now". Older than this
#: and the node's spare capacity is unknown rather than zero — treating an
#: unmeasured node as idle is how work lands on a busy machine.
SNAPSHOT_FRESHNESS_SECONDS = 120


@dataclass(frozen=True, slots=True)
class ShardRequirement:
    """What one shard needs. Must fit inside a single node — that is the point.

    In the canonical units (``saintvision.units``), because every field here is
    compared with ``>=`` against a node's spare capacity and that comparison is
    the placement decision. A requirement in cores against spare capacity in
    millicores would not fail loudly; it would place a thousand-fold too much
    work on one machine, or find no candidate at all in a pool that is idle.
    """

    cpu_millicores: int = 0
    ram_bytes: int = 0
    gpu_devices: int = 0

    def validate(self) -> None:
        for name, value in (
            ("cpu_millicores", self.cpu_millicores),
            ("ram_bytes", self.ram_bytes),
            ("gpu_devices", self.gpu_devices),
        ):
            if value < 0:
                raise InvError(VAL_SCHEMA, f"{name} must not be negative")

    def per_kind(self) -> dict[str, float]:
        """The requirement keyed the way spare capacity is keyed."""
        return {
            "cpu": self.cpu_millicores,
            "ram": self.ram_bytes,
            "gpu": self.gpu_devices,
        }


@dataclass
class NodeSpare:
    node_id: str
    hostname: str
    offered: dict[str, float] = field(default_factory=dict)
    used: dict[str, float] = field(default_factory=dict)
    spare: dict[str, float] = field(default_factory=dict)
    #: False when no fresh snapshot exists. Spare is then unknown, and an
    #: unknown node is not treated as idle.
    measured: bool = True


def create_pool(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    project_id: str,
    name: str,
    created_by_user_id: str,
    now: dt.datetime,
    description: str | None = None,
) -> ResourcePool:
    pool = ResourcePool(
        pool_id=new_id("pool"),
        tenant_id=tenant_id,
        project_id=project_id,
        name=name,
        description=description,
        status="active",
        created_by_user_id=created_by_user_id,
        created_at=now,
    )
    session.add(pool)
    session.flush()
    return pool


def add_member(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    pool_id: str,
    node_id: str,
    added_by_user_id: str,
    now: dt.datetime,
) -> ResourcePoolMember:
    """Put a node in a pool. Idempotent — adding twice is not an error."""
    pool = session.get(ResourcePool, pool_id)
    if pool is None or pool.tenant_id != tenant_id:
        raise InvError(RES_NODE_NOT_FOUND, "pool not found")
    node = session.get(Node, node_id)
    if node is None or node.tenant_id != tenant_id:
        raise InvError(RES_NODE_NOT_FOUND, "node not found")

    existing = session.get(ResourcePoolMember, (tenant_id, pool_id, node_id))
    if existing is not None:
        return existing

    member = ResourcePoolMember(
        tenant_id=tenant_id,
        pool_id=pool_id,
        node_id=node_id,
        added_by_user_id=added_by_user_id,
        added_at=now,
    )
    session.add(member)
    session.flush()
    return member


def remove_member(
    session: Session, *, tenant_id: uuid.UUID, pool_id: str, node_id: str
) -> bool:
    member = session.get(ResourcePoolMember, (tenant_id, pool_id, node_id))
    if member is None:
        return False
    session.delete(member)
    session.flush()
    return True


def node_spare(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    node_ids: list[str],
    now: dt.datetime,
    freshness_seconds: int = SNAPSHOT_FRESHNESS_SECONDS,
) -> list[NodeSpare]:
    """Offered minus currently used, per node, per resource kind.

    A node with no fresh snapshot is returned with ``measured=False`` and zero
    spare. Assuming an unmeasured machine is idle is how a job lands on the one
    node that is already saturated.
    """
    if not node_ids:
        return []
    cutoff = now - dt.timedelta(seconds=freshness_seconds)

    offered_rows = session.execute(
        select(
            NodeCapability.node_id,
            NodeCapability.kind,
            func.sum(ResourceOffer.offered_quantity),
        )
        .join(
            ResourceOffer,
            (ResourceOffer.tenant_id == NodeCapability.tenant_id)
            & (ResourceOffer.capability_id == NodeCapability.capability_id),
        )
        .where(
            NodeCapability.tenant_id == tenant_id,
            NodeCapability.node_id.in_(node_ids),
            ResourceOffer.effective_from <= now,
            (ResourceOffer.effective_to.is_(None)) | (ResourceOffer.effective_to > now),
        )
        .group_by(NodeCapability.node_id, NodeCapability.kind)
    ).all()

    # Latest snapshot per (node, capability), then summed per kind. Summing all
    # snapshots would count every historical sample.
    latest = (
        select(
            ResourceSnapshot.node_id.label("node_id"),
            ResourceSnapshot.capability_id.label("capability_id"),
            func.max(ResourceSnapshot.observed_at).label("observed_at"),
        )
        .where(
            ResourceSnapshot.tenant_id == tenant_id,
            ResourceSnapshot.node_id.in_(node_ids),
            ResourceSnapshot.observed_at >= cutoff,
        )
        .group_by(ResourceSnapshot.node_id, ResourceSnapshot.capability_id)
        .subquery()
    )
    used_rows = session.execute(
        select(
            ResourceSnapshot.node_id,
            NodeCapability.kind,
            func.sum(ResourceSnapshot.used_quantity),
        )
        .join(
            latest,
            (latest.c.node_id == ResourceSnapshot.node_id)
            & (latest.c.capability_id == ResourceSnapshot.capability_id)
            & (latest.c.observed_at == ResourceSnapshot.observed_at),
        )
        .join(
            NodeCapability,
            (NodeCapability.tenant_id == ResourceSnapshot.tenant_id)
            & (NodeCapability.capability_id == ResourceSnapshot.capability_id),
        )
        .where(ResourceSnapshot.tenant_id == tenant_id)
        .group_by(ResourceSnapshot.node_id, NodeCapability.kind)
    ).all()

    nodes = {
        n.node_id: n
        for n in session.scalars(
            select(Node).where(Node.tenant_id == tenant_id, Node.node_id.in_(node_ids))
        ).all()
    }

    offered: dict[str, dict[str, float]] = {}
    for node_id, kind, total in offered_rows:
        offered.setdefault(node_id, {})[kind] = float(total or 0)
    used: dict[str, dict[str, float]] = {}
    for node_id, kind, total in used_rows:
        used.setdefault(node_id, {})[kind] = float(total or 0)

    out: list[NodeSpare] = []
    for node_id in sorted(node_ids):
        node = nodes.get(node_id)
        if node is None:
            continue
        node_offered = offered.get(node_id, {})
        node_used = used.get(node_id, {})
        measured = node_id in used
        spare = {
            kind: max(0.0, node_offered.get(kind, 0.0) - node_used.get(kind, 0.0))
            if measured
            else 0.0
            for kind in KINDS
        }
        out.append(
            NodeSpare(
                node_id=node_id,
                hostname=node.hostname,
                offered={k: node_offered.get(k, 0.0) for k in KINDS},
                used={k: node_used.get(k, 0.0) for k in KINDS},
                spare=spare,
                measured=measured,
            )
        )
    return out


def pool_members(session: Session, *, tenant_id: uuid.UUID, pool_id: str) -> list[str]:
    return list(
        session.scalars(
            select(ResourcePoolMember.node_id).where(
                ResourcePoolMember.tenant_id == tenant_id,
                ResourcePoolMember.pool_id == pool_id,
            )
        ).all()
    )


def list_pools(session: Session, *, tenant_id: uuid.UUID) -> dict[str, Any]:
    """Return the tenant's pool inventory without inventing capacity values.

    Capacity is time-sensitive and has its own endpoint. The inventory route
    intentionally returns identity and membership count only so a caller cannot
    mistake a list snapshot for a capacity observation.
    """
    rows = session.scalars(
        select(ResourcePool)
        .where(ResourcePool.tenant_id == tenant_id)
        .order_by(ResourcePool.created_at, ResourcePool.pool_id)
    ).all()
    items = [
        {
            "poolId": pool.pool_id,
            "projectId": pool.project_id,
            "name": pool.name,
            "status": pool.status,
            "memberCount": len(pool_members(session, tenant_id=tenant_id, pool_id=pool.pool_id)),
        }
        for pool in rows
    ]
    return {"items": items, "count": len(items)}


def pool_capacity(
    session: Session, *, tenant_id: uuid.UUID, pool_id: str, now: dt.datetime
) -> dict[str, Any]:
    """The three figures, plus the per-node breakdown.

    ``largestSingleNode`` sits beside ``totalOffered`` so a caller cannot
    present the sum as though one job could use it. Only nodes in ``active``
    status count: a lost or draining machine's capacity is not available, and
    including it would overstate the pool exactly when it matters.
    """
    pool = session.get(ResourcePool, pool_id)
    if pool is None or pool.tenant_id != tenant_id:
        raise InvError(RES_NODE_NOT_FOUND, "pool not found")

    member_ids = pool_members(session, tenant_id=tenant_id, pool_id=pool_id)
    active_ids = list(
        session.scalars(
            select(Node.node_id).where(
                Node.tenant_id == tenant_id,
                Node.node_id.in_(member_ids) if member_ids else False,
                Node.status == "active",
            )
        ).all()
    )
    spares = node_spare(session, tenant_id=tenant_id, node_ids=active_ids, now=now)

    total = {kind: 0.0 for kind in KINDS}
    largest = {kind: 0.0 for kind in KINDS}
    spare_now = {kind: 0.0 for kind in KINDS}
    for entry in spares:
        for kind in KINDS:
            total[kind] += entry.offered.get(kind, 0.0)
            largest[kind] = max(largest[kind], entry.offered.get(kind, 0.0))
            spare_now[kind] += entry.spare.get(kind, 0.0)

    unmeasured = [e.node_id for e in spares if not e.measured]
    return {
        "poolId": pool_id,
        "name": pool.name,
        "memberCount": len(member_ids),
        "activeMemberCount": len(active_ids),
        "totalOffered": total,
        # The ceiling for one task that cannot be split. Never omit this.
        "largestSingleNode": largest,
        "spareNow": spare_now,
        #: Nodes with no fresh utilisation snapshot. Their spare is counted as
        #: zero, so the pool understates rather than overstates.
        "unmeasuredNodes": unmeasured,
        "nodes": [
            {
                "nodeId": e.node_id,
                "hostname": e.hostname,
                "offered": e.offered,
                "used": e.used,
                "spare": e.spare,
                "measured": e.measured,
            }
            for e in spares
        ],
        # Every figure above is a bare number until this says what it counts.
        # A consumer that infers the unit from the field name eventually infers
        # it wrong, and these numbers decide where work runs.
        "units": dict(CANONICAL_UNIT),
        "note": (
            "totalOffered is the sum across the pool. One task that cannot be "
            "split is bounded by largestSingleNode. Memory is not shared across "
            "machines."
        ),
    }


def rank_idle_first(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    pool_id: str,
    requirement: ShardRequirement,
    now: dt.datetime,
) -> list[dict[str, Any]]:
    """Nodes that can hold one shard, most idle first.

    A node is a candidate only if its *spare* capacity fits the whole shard —
    not its offered capacity. Placing on offered capacity is how two jobs end
    up on the machine that was already busy.
    """
    requirement.validate()
    member_ids = pool_members(session, tenant_id=tenant_id, pool_id=pool_id)
    if not member_ids:
        return []
    active_ids = list(
        session.scalars(
            select(Node.node_id).where(
                Node.tenant_id == tenant_id,
                Node.node_id.in_(member_ids),
                Node.status == "active",
            )
        ).all()
    )
    spares = node_spare(session, tenant_id=tenant_id, node_ids=active_ids, now=now)

    candidates = []
    for entry in spares:
        if not entry.measured:
            continue
        wanted = requirement.per_kind()
        if any(entry.spare.get(kind, 0.0) < need for kind, need in wanted.items()):
            continue
        # Score on the least-loaded dimension that the shard actually needs, so
        # a GPU job is not sent to the node with the most free RAM.
        ratios = [entry.spare[kind] / need for kind, need in wanted.items() if need > 0]
        # With no requested resource dimension there is no meaningful ratio.
        # A finite neutral score keeps the default preview a valid JSON response
        # and preserves the node-id tie break below.
        headroom = min(ratios) if ratios else 0.0
        candidates.append(
            {
                "nodeId": entry.node_id,
                "hostname": entry.hostname,
                "spare": entry.spare,
                "headroom": headroom,
            }
        )

    # Most headroom first; ties on nodeId so the same inputs place the same way
    # and the decision can be explained afterwards.
    candidates.sort(key=lambda c: (-c["headroom"], c["nodeId"]))
    return candidates


def plan_distributed_run(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    run_id: str,
    pool_id: str,
    strategy: str,
    shard_count: int,
    requirement: ShardRequirement,
    now: dt.datetime,
    splittable_declared: bool = False,
    allow_multiple_shards_per_node: bool = True,
) -> tuple[DistributedPlan, list[PlanPlacement]]:
    """Place ``shard_count`` shards on the idlest nodes that fit.

    Refuses to split work the caller did not declare splittable. A program that
    is not shard-aware does not run faster when split — it produces a wrong
    answer, and the platform has no way to tell from the outside.

    Refuses if fewer nodes fit than shards are needed. A partial placement that
    silently ran three of five shards would report success for a job that did
    not happen.
    """
    if strategy not in ("single_node", "data_parallel", "sharded"):
        raise InvError(VAL_SCHEMA, f"unknown strategy: {strategy!r}")
    if shard_count < 1:
        raise InvError(VAL_SCHEMA, "shard_count must be at least 1")
    if strategy == "single_node" and shard_count != 1:
        raise InvError(VAL_SCHEMA, "a single_node plan has exactly one shard")
    if shard_count > 1 and not splittable_declared:
        raise InvError(
            VAL_SCHEMA,
            "splitting requires the workload to declare it can be split; "
            "the platform does not infer it because a non-shard-aware program "
            "produces wrong answers when split, not slow ones",
        )
    requirement.validate()

    ranked = rank_idle_first(
        session, tenant_id=tenant_id, pool_id=pool_id, requirement=requirement, now=now
    )
    chosen: list[dict[str, Any]] = []
    if allow_multiple_shards_per_node:
        # Walk the ranking repeatedly, spending a node's spare capacity as it is
        # used, so a big machine can take several shards.
        remaining = {c["nodeId"]: dict(c["spare"]) for c in ranked}
        order = [c for c in ranked]
        while len(chosen) < shard_count:
            placed_this_round = False
            for candidate in order:
                if len(chosen) >= shard_count:
                    break
                spare = remaining[candidate["nodeId"]]
                wanted = requirement.per_kind()
                if all(
                    spare.get(kind, 0.0) >= need for kind, need in wanted.items()
                ):
                    chosen.append({**candidate, "spare": dict(spare)})
                    for kind, need in wanted.items():
                        spare[kind] -= need
                    placed_this_round = True
            if not placed_this_round:
                break
    else:
        chosen = ranked[:shard_count]

    if len(chosen) < shard_count:
        raise InvError(
            VAL_SCHEMA,
            f"the pool has room for {len(chosen)} of {shard_count} shards right now; "
            "a partial placement would report success for a job that did not run",
            extra={"placeable": len(chosen), "required": shard_count},
        )

    plan = DistributedPlan(
        plan_id=new_id("plan"),
        tenant_id=tenant_id,
        run_id=run_id,
        pool_id=pool_id,
        strategy=strategy,
        state="placed",
        shard_count=shard_count,
        splittable_declared=splittable_declared,
        shard_cpu_millicores=requirement.cpu_millicores,
        shard_ram_bytes=requirement.ram_bytes,
        shard_gpu_devices=requirement.gpu_devices,
        # Kept so the placement can be explained later, not recomputed.
        ranking_snapshot={"ranked": ranked},
        created_at=now,
    )
    session.add(plan)
    session.flush()

    placements: list[PlanPlacement] = []
    for index, candidate in enumerate(chosen[:shard_count]):
        placement = PlanPlacement(
            tenant_id=tenant_id,
            plan_id=plan.plan_id,
            shard_index=index,
            node_id=candidate["nodeId"],
            assigned_cpu_millicores=requirement.cpu_millicores,
            assigned_ram_bytes=requirement.ram_bytes,
            assigned_gpu_devices=requirement.gpu_devices,
            spare_at_placement=candidate["spare"],
            state="planned",
            placed_at=now,
        )
        session.add(placement)
        placements.append(placement)
    session.flush()
    return plan, placements
