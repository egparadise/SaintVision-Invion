"""Locality: send the work to the bytes, and say honestly what it costs.

This is what turns a set of disks into pooled storage. A pool that only sums
capacities tells you nothing about where a job should run; knowing which node
already holds the inputs does, and moving a hundred gigabytes across a slow
segment is usually more expensive than waiting for a busier machine.

The estimator refuses to guess. ADR-011 fixes the formula as
``(requiredBytes − localBytes) × 8 / bitsPerSecond`` and forbids two shortcuts
that would each produce a confident wrong answer:

* An **unmeasured link** yields no estimate, not zero seconds.
* An **empty dataset** has locality 0, not 1. Zero bytes present is nothing
  present, and the division that would return 1.0 is never performed.
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db.models import (
    CACHE_FILL_LIMIT,
    MAX_CONCURRENT_TRANSFERS,
    DataLocation,
    DataReplica,
    Node,
    NodeLink,
    StorageContribution,
)
from ..errors import RES_ARTIFACT_NOT_FOUND, VAL_SCHEMA, InvError
from ..ids import new_id

#: A bandwidth sample older than this is not used. Networks change, and an
#: estimate from a month ago is a guess wearing a number.
LINK_FRESHNESS_DAYS = 30


@dataclass(frozen=True, slots=True)
class TransferEstimate:
    """How long moving the missing bytes would take, or that we cannot say."""

    bytes_missing: int
    seconds: float | None
    #: False when no fresh measured link exists between the two nodes.
    measured: bool
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "bytesMissing": self.bytes_missing,
            # None, never 0, when the link is unmeasured. A caller that sorts on
            # this must handle unknown rather than treat it as instant.
            "seconds": self.seconds,
            "measured": self.measured,
            "reason": self.reason,
        }


def register_replica(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    location_id: str,
    node_id: str,
    contribution_id: str,
    now: dt.datetime,
    local_bytes: int = 0,
) -> DataReplica:
    """Record that a node is holding (or fetching) a copy.

    Starts as ``transferring``. It becomes usable only through
    :func:`mark_replica_ready`, which requires a checksum.
    """
    location = session.get(DataLocation, location_id)
    if location is None or location.tenant_id != tenant_id:
        raise InvError(RES_ARTIFACT_NOT_FOUND, "data location not found")
    if local_bytes < 0:
        raise InvError(VAL_SCHEMA, "local_bytes must not be negative")

    existing = session.scalar(
        select(DataReplica).where(
            DataReplica.tenant_id == tenant_id,
            DataReplica.location_id == location_id,
            DataReplica.node_id == node_id,
        )
    )
    if existing is not None:
        existing.local_bytes = local_bytes
        existing.last_used_at = now
        session.flush()
        return existing

    replica = DataReplica(
        replica_id=new_id("replica"),
        tenant_id=tenant_id,
        location_id=location_id,
        node_id=node_id,
        contribution_id=contribution_id,
        state="transferring",
        local_bytes=local_bytes,
        last_used_at=now,
        created_at=now,
    )
    session.add(replica)
    session.flush()
    return replica


def mark_replica_ready(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    replica_id: str,
    checksum_sha256: str,
    now: dt.datetime,
) -> DataReplica:
    """Promote a replica once its bytes hashed to what the catalogue recorded.

    The comparison is against the catalogue, not against what the node reports
    about itself. A node claiming its own copy is fine proves nothing.
    """
    replica = session.get(DataReplica, replica_id)
    if replica is None or replica.tenant_id != tenant_id:
        raise InvError(RES_ARTIFACT_NOT_FOUND, "replica not found")

    location = session.get(DataLocation, replica.location_id)
    if location.checksum_sha256 is None:
        raise InvError(
            VAL_SCHEMA,
            "the catalogue has no verified checksum for this item, so a replica "
            "of it cannot be verified either",
            cause_ref=replica.location_id,
        )
    if checksum_sha256 != location.checksum_sha256:
        replica.state = "corrupt"
        session.flush()
        raise InvError(
            VAL_SCHEMA,
            "replica checksum does not match the catalogue; marked corrupt",
            cause_ref=replica_id,
        )
    if replica.local_bytes != location.byte_size:
        raise InvError(
            VAL_SCHEMA,
            "replica is short of the catalogued size",
            cause_ref=replica_id,
            extra={"localBytes": replica.local_bytes, "expected": location.byte_size},
        )

    replica.state = "ready"
    replica.checksum_sha256 = checksum_sha256
    replica.verified_at = now
    replica.last_used_at = now
    session.flush()
    return replica


def record_link(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    from_node_id: str,
    to_node_id: str,
    bits_per_second: int,
    now: dt.datetime,
    note: str | None = None,
) -> NodeLink:
    """Record a measured throughput between two nodes.

    Stores effective throughput, not an interface's nominal rate: a 1 Gb/s NIC
    on a congested segment does not move a gigabit, and planning on the label
    is how a transfer estimate becomes fiction.
    """
    if bits_per_second <= 0:
        raise InvError(VAL_SCHEMA, "bits_per_second must be positive")
    if from_node_id == to_node_id:
        raise InvError(VAL_SCHEMA, "a link is between two different nodes")

    existing = session.get(NodeLink, (tenant_id, from_node_id, to_node_id))
    if existing is not None:
        existing.bits_per_second = bits_per_second
        existing.sample_count += 1
        existing.measured_at = now
        existing.note = note
        session.flush()
        return existing

    link = NodeLink(
        tenant_id=tenant_id,
        from_node_id=from_node_id,
        to_node_id=to_node_id,
        bits_per_second=bits_per_second,
        sample_count=1,
        measured_at=now,
        note=note,
    )
    session.add(link)
    session.flush()
    return link


def locality(
    session: Session, *, tenant_id: uuid.UUID, location_id: str, node_id: str
) -> float:
    """Fraction of the item already present on the node, in ``[0, 1]``.

    An item of zero bytes returns **0.0**, not 1.0. ADR-011 is explicit: an
    empty dataset has locality zero. Returning 1.0 would rank every node as
    perfectly local for an item nobody has.
    """
    location = session.get(DataLocation, location_id)
    if location is None or location.tenant_id != tenant_id:
        raise InvError(RES_ARTIFACT_NOT_FOUND, "data location not found")
    if location.byte_size <= 0:
        return 0.0

    replica = session.scalar(
        select(DataReplica).where(
            DataReplica.tenant_id == tenant_id,
            DataReplica.location_id == location_id,
            DataReplica.node_id == node_id,
            DataReplica.state == "ready",
        )
    )
    if replica is None:
        return 0.0
    return min(1.0, replica.local_bytes / location.byte_size)


def estimate_transfer(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    location_id: str,
    target_node_id: str,
    now: dt.datetime,
    freshness_days: int = LINK_FRESHNESS_DAYS,
) -> TransferEstimate:
    """Seconds to bring the missing bytes to ``target_node_id``.

    Picks the fastest measured link from a node that already holds a ready
    copy. With no such link the estimate is **unknown** — the plan forbids
    treating an unmeasured link as zero seconds, because that is what makes a
    scheduler decide to drag a hundred gigabytes across a segment nobody has
    tested.
    """
    location = session.get(DataLocation, location_id)
    if location is None or location.tenant_id != tenant_id:
        raise InvError(RES_ARTIFACT_NOT_FOUND, "data location not found")

    present = locality(
        session, tenant_id=tenant_id, location_id=location_id, node_id=target_node_id
    )
    missing = max(0, location.byte_size - int(location.byte_size * present))
    if missing == 0:
        return TransferEstimate(bytes_missing=0, seconds=0.0, measured=True,
                                reason="already local")

    sources = list(
        session.scalars(
            select(DataReplica.node_id).where(
                DataReplica.tenant_id == tenant_id,
                DataReplica.location_id == location_id,
                DataReplica.state == "ready",
                DataReplica.node_id != target_node_id,
            )
        ).all()
    )
    if not sources:
        return TransferEstimate(
            bytes_missing=missing,
            seconds=None,
            measured=False,
            reason="no node holds a ready copy",
        )

    cutoff = now - dt.timedelta(days=freshness_days)
    fastest = session.scalar(
        select(func.max(NodeLink.bits_per_second)).where(
            NodeLink.tenant_id == tenant_id,
            NodeLink.from_node_id.in_(sources),
            NodeLink.to_node_id == target_node_id,
            NodeLink.measured_at >= cutoff,
        )
    )
    if not fastest:
        return TransferEstimate(
            bytes_missing=missing,
            seconds=None,
            measured=False,
            # Said plainly, because the caller must not substitute a zero.
            reason="no fresh measured link from a node holding a copy",
        )

    # ADR-011: bytes x 8 / bits-per-second.
    return TransferEstimate(
        bytes_missing=missing,
        seconds=(missing * 8) / fastest,
        measured=True,
    )


def rank_by_locality(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    candidates: list[dict[str, Any]],
    location_ids: list[str],
    now: dt.datetime,
) -> list[dict[str, Any]]:
    """Re-rank idle-first candidates by how much of the input they already hold.

    Takes the output of :func:`services.pools.rank_idle_first` and adds the
    data cost. Nodes are ordered by total estimated transfer seconds ascending,
    and **a node whose cost is unknown sorts after every node with a known
    cost** — not first, and not treated as zero.

    Idleness still breaks ties, so between two nodes that hold the data the
    quieter one wins.
    """
    if not location_ids:
        return candidates

    ranked: list[dict[str, Any]] = []
    for candidate in candidates:
        node_id = candidate["nodeId"]
        estimates = [
            estimate_transfer(
                session,
                tenant_id=tenant_id,
                location_id=location_id,
                target_node_id=node_id,
                now=now,
            )
            for location_id in location_ids
        ]
        unknown = [e for e in estimates if e.seconds is None]
        total_seconds = sum(e.seconds or 0.0 for e in estimates)
        bytes_missing = sum(e.bytes_missing for e in estimates)
        ranked.append(
            {
                **candidate,
                "transferSeconds": None if unknown else total_seconds,
                "bytesMissing": bytes_missing,
                "unknownTransfers": len(unknown),
                "locality": [e.to_dict() for e in estimates],
            }
        )

    ranked.sort(
        key=lambda c: (
            # Unknown cost sorts last, never first.
            c["transferSeconds"] is None,
            c["transferSeconds"] if c["transferSeconds"] is not None else 0.0,
            -c.get("headroom", 0.0),
            c["nodeId"],
        )
    )
    return ranked


def cache_usage(
    session: Session, *, tenant_id: uuid.UUID, contribution_id: str
) -> dict[str, Any]:
    """How much of a contributed folder the platform's cache is occupying.

    The limit is 60% of what was contributed (PLAN-STORAGE-001). The rest is
    the owner's headroom — the machine is theirs, and filling their disk is the
    fastest way to lose a contributor.
    """
    contribution = session.get(StorageContribution, contribution_id)
    if contribution is None or contribution.tenant_id != tenant_id:
        raise InvError(RES_ARTIFACT_NOT_FOUND, "storage contribution not found")

    used = session.scalar(
        select(func.coalesce(func.sum(DataReplica.local_bytes), 0)).where(
            DataReplica.tenant_id == tenant_id,
            DataReplica.contribution_id == contribution_id,
            # Unavailable/corrupt bytes still occupy storage until eviction.
            DataReplica.state != "evicted",
        )
    )
    capacity = contribution.capacity_bytes
    limit = int(capacity * CACHE_FILL_LIMIT) if capacity else None
    return {
        "contributionId": contribution_id,
        "capacityBytes": capacity,
        "cacheLimitBytes": limit,
        "cacheUsedBytes": int(used),
        "overLimit": bool(limit is not None and used > limit),
        "fillLimit": CACHE_FILL_LIMIT,
    }


def eviction_candidates(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    contribution_id: str,
    now: dt.datetime,
    bytes_needed: int = 0,
) -> list[dict[str, Any]]:
    """Least recently used replicas that may be evicted, oldest first.

    Pinned replicas are excluded entirely rather than ranked last: an active
    lease pinned its inputs, and evicting them would fail a running job to make
    room for a queued one.

    Returns only as many as are needed to free ``bytes_needed`` (or to get back
    under the fill limit), so a caller cannot evict the whole cache by
    accident.
    """
    usage = cache_usage(session, tenant_id=tenant_id, contribution_id=contribution_id)
    to_free = bytes_needed
    if usage["cacheLimitBytes"] is not None:
        to_free = max(to_free, usage["cacheUsedBytes"] - usage["cacheLimitBytes"])
    if to_free <= 0:
        return []

    rows = session.scalars(
        select(DataReplica)
        .where(
            DataReplica.tenant_id == tenant_id,
            DataReplica.contribution_id == contribution_id,
            DataReplica.state == "ready",
            # A pin from an active lease is absolute.
            (DataReplica.pinned_until.is_(None)) | (DataReplica.pinned_until <= now),
        )
        .order_by(DataReplica.last_used_at)
    ).all()

    chosen: list[dict[str, Any]] = []
    freed = 0
    for replica in rows:
        if freed >= to_free:
            break
        chosen.append(
            {
                "replicaId": replica.replica_id,
                "locationId": replica.location_id,
                "nodeId": replica.node_id,
                "bytes": replica.local_bytes,
                "lastUsedAt": replica.last_used_at,
            }
        )
        freed += replica.local_bytes
    return chosen


def active_transfers(session: Session, *, tenant_id: uuid.UUID, node_id: str) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(DataReplica)
            .where(
                DataReplica.tenant_id == tenant_id,
                DataReplica.node_id == node_id,
                DataReplica.state == "transferring",
            )
        )
        or 0
    )


def may_start_transfer(
    session: Session, *, tenant_id: uuid.UUID, node_id: str
) -> bool:
    """Whether a node has a free transfer slot.

    Two at a time (PLAN-STORAGE-001). More would saturate the owner's link and
    make the machine unpleasant to use, which is how contributors withdraw.
    """
    return active_transfers(session, tenant_id=tenant_id, node_id=node_id) < MAX_CONCURRENT_TRANSFERS
