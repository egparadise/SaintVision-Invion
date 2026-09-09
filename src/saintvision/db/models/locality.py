"""Replicas, links and cache accounting: where the bytes actually are.

Pooling storage is not a matter of adding capacities together. What makes five
machines' disks useful for one job is knowing **which machine already holds the
bytes**, so work goes to the data instead of dragging the data to the work.

Three rules from PLAN-STORAGE-001 and ADR-011 are structural here, because each
one is a place where an optimistic default would silently produce a wrong
schedule:

* **An unmeasured link is unknown, not fast.** Transfer time is
  ``(requiredBytes − localBytes) × 8 / bitsPerSecond``. With no measured
  bandwidth there is no estimate, and the plan is explicit that it must not be
  called zero seconds.
* **An empty dataset has locality 0, not 1.** Zero bytes present is not "fully
  local"; it is nothing present. The division that would produce 1.0 is not
  performed.
* **A replica pinned by an active lease is never evicted.** LRU under the 60%
  cap chooses among the rest.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base, InvId, Sha256, TenantId, Utc

REPLICA_STATES = ("transferring", "ready", "stale", "corrupt", "evicted")

#: LRU may fill a contributed folder to this fraction and no further
#: (PLAN-STORAGE-001). The rest is the owner's headroom — the machine is theirs.
CACHE_FILL_LIMIT = 0.60

#: Concurrent transfers per node (PLAN-STORAGE-001). More would starve the
#: owner's own use of the machine.
MAX_CONCURRENT_TRANSFERS = 2


class DataReplica(Base):
    """A copy of a catalogued item held on one node.

    ``ready`` means the bytes are complete **and** the checksum matched what the
    catalogue recorded — not that a file of the right size exists. A replica
    that has not been verified is not a replica you can schedule onto.
    """

    __tablename__ = "data_replicas"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "location_id"],
            ["data_locations.tenant_id", "data_locations.location_id"],
        ),
        ForeignKeyConstraint(
            ["tenant_id", "node_id"], ["nodes.tenant_id", "nodes.node_id"]
        ),
        UniqueConstraint(
            "tenant_id", "replica_id", name="uq_data_replicas_tenant_id_replica_id"
        ),
        # One replica of one item per node. A second row would double-count the
        # bytes in every capacity and locality calculation.
        UniqueConstraint(
            "location_id", "node_id", name="uq_data_replicas_location_id_node_id"
        ),
        CheckConstraint(
            "state IN ('transferring','ready','stale','corrupt','evicted')",
            name="state_allowed",
        ),
        CheckConstraint("local_bytes >= 0", name="local_bytes_non_negative"),
        # Ready requires a verified checksum (ADR-011): presence is not
        # integrity, and scheduling onto unverified bytes is how a run produces
        # a confidently wrong result.
        CheckConstraint(
            "state <> 'ready' OR (checksum_sha256 IS NOT NULL AND verified_at IS NOT NULL)",
            name="ready_requires_verification",
        ),
        # A pin is what stops eviction, so it may only sit on a usable replica.
        CheckConstraint(
            "pinned_until IS NULL OR state = 'ready'", name="only_ready_replicas_pin"
        ),
        Index("ix_data_replicas_tenant_id_node_id", "tenant_id", "node_id"),
        Index("ix_data_replicas_tenant_id_location_id", "tenant_id", "location_id"),
        Index("ix_data_replicas_last_used_at", "last_used_at"),
    )

    replica_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column()
    location_id: Mapped[InvId] = mapped_column()
    node_id: Mapped[InvId] = mapped_column()
    #: Which contributed folder holds it, so eviction can be accounted per
    #: folder rather than per node.
    contribution_id: Mapped[InvId] = mapped_column()
    state: Mapped[str] = mapped_column(String(16), default="transferring")
    #: How many of the item's bytes are here. Partial during transfer.
    local_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    checksum_sha256: Mapped[Sha256 | None] = mapped_column(nullable=True)
    verified_at: Mapped[Utc | None] = mapped_column(nullable=True)
    #: An active lease pins its inputs; a pinned replica is never evicted.
    pinned_until: Mapped[Utc | None] = mapped_column(nullable=True)
    #: LRU key. Eviction takes the least recently used unpinned replica.
    last_used_at: Mapped[Utc] = mapped_column(server_default=text("now()"))
    created_at: Mapped[Utc] = mapped_column(server_default=text("now()"))


class NodeLink(Base):
    """Measured bandwidth between two nodes.

    Rows exist only for links someone actually measured. A missing row means
    unknown, and the estimator returns unknown rather than an optimistic
    number — an unmeasured link treated as instant is how a scheduler decides
    to move a hundred gigabytes across a slow segment.
    """

    __tablename__ = "node_links"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "from_node_id"], ["nodes.tenant_id", "nodes.node_id"]
        ),
        ForeignKeyConstraint(
            ["tenant_id", "to_node_id"], ["nodes.tenant_id", "nodes.node_id"]
        ),
        UniqueConstraint(
            "tenant_id", "from_node_id", "to_node_id", name="uq_node_links_pair"
        ),
        CheckConstraint("bits_per_second > 0", name="bandwidth_positive"),
        CheckConstraint("from_node_id <> to_node_id", name="link_is_between_two_nodes"),
        CheckConstraint(
            "sample_count >= 1", name="sample_count_positive"
        ),
        Index("ix_node_links_tenant_id_measured_at", "tenant_id", "measured_at"),
    )

    tenant_id: Mapped[TenantId] = mapped_column(primary_key=True)
    from_node_id: Mapped[InvId] = mapped_column(primary_key=True)
    to_node_id: Mapped[InvId] = mapped_column(primary_key=True)
    #: Effective throughput, not the interface's nominal rate. A 1 Gb/s NIC on a
    #: congested segment does not move a gigabit.
    bits_per_second: Mapped[int] = mapped_column(BigInteger)
    sample_count: Mapped[int] = mapped_column(Integer, default=1)
    measured_at: Mapped[Utc] = mapped_column(server_default=text("now()"))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
