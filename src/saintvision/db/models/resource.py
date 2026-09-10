"""Node, capability, offer and snapshot tables (S02-DB).

Scope note: this sprint records what a node *offers* and what was *observed*.
Reservation (leases, allocations, fencing) is ADR-005/006 and belongs to Codex
in S05; nothing here should be read as a reservation contract.
"""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base, BigInteger, InvId, Sha256, TenantId, Utc

NODE_STATUSES = ("enrolling", "active", "draining", "lost", "retired")
CAPABILITY_KINDS = ("cpu", "gpu", "ram", "disk")


class Node(Base):
    __tablename__ = "nodes"
    __table_args__ = (
        UniqueConstraint("tenant_id", "hostname"),
        UniqueConstraint("tenant_id", "node_id", name="uq_nodes_tenant_id_node_id"),
        # Fingerprints are unique when present. NULL means "enrollment has not
        # completed", which is a state many nodes legitimately share, so this is
        # a partial index rather than NULLS NOT DISTINCT — the latter would cap
        # the whole platform at one unenrolled node.
        Index(
            "uq_nodes_certificate_fingerprint",
            "certificate_fingerprint",
            unique=True,
            postgresql_where=text("certificate_fingerprint IS NOT NULL"),
        ),
        CheckConstraint(
            "status IN ('enrolling','active','draining','lost','retired')",
            name="status_allowed",
        ),
        CheckConstraint(
            "heartbeat_sequence >= 0", name="heartbeat_sequence_non_negative"
        ),
        Index("ix_nodes_tenant_id_status", "tenant_id", "status"),
        Index("ix_nodes_tenant_id_last_heartbeat_at", "tenant_id", "last_heartbeat_at"),
    )

    node_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column(ForeignKey("tenants.tenant_id"))
    hostname: Mapped[str] = mapped_column(String(253))
    os_type: Mapped[str] = mapped_column(String(16))
    os_version: Mapped[str] = mapped_column(String(64))
    agent_version: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="enrolling")
    #: SHA-256 of the node client certificate presented over mTLS. NULL until
    #: the CA is decided in S01 and the node completes enrollment.
    certificate_fingerprint: Mapped[Sha256 | None] = mapped_column(nullable=True)
    labels: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    enrolled_at: Mapped[Utc] = mapped_column(server_default=text("now()"))
    last_heartbeat_at: Mapped[Utc | None] = mapped_column(nullable=True)
    #: Monotonic per node. A heartbeat whose sequence is not greater than the
    #: stored one is a replay and is rejected rather than applied (ADR-007).
    heartbeat_sequence: Mapped[int] = mapped_column(default=0)
    version: Mapped[int] = mapped_column(default=1)


class NodeBootstrapToken(Base):
    """One-time enrollment token.

    Only the hash is stored. ``consumed_at`` is what makes reuse detectable, and
    the paired-consumption check keeps a half-recorded consumption from looking
    like an unused token (AC-02: token reuse must be blocked).
    """

    __tablename__ = "node_bootstrap_tokens"
    __table_args__ = (
        UniqueConstraint("token_sha256", name="uq_node_bootstrap_tokens_token_sha256"),
        CheckConstraint(
            "(consumed_at IS NULL) = (consumed_by_node_id IS NULL)",
            name="consumption_paired",
        ),
        Index(
            "ix_node_bootstrap_tokens_tenant_id_expires_at", "tenant_id", "expires_at"
        ),
    )

    token_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column(ForeignKey("tenants.tenant_id"))
    token_sha256: Mapped[Sha256]
    issued_by_user_id: Mapped[InvId] = mapped_column()
    issued_at: Mapped[Utc] = mapped_column(server_default=text("now()"))
    expires_at: Mapped[Utc]
    consumed_at: Mapped[Utc | None] = mapped_column(nullable=True)
    consumed_by_node_id: Mapped[InvId | None] = mapped_column(nullable=True)


class NodeCapability(Base):
    __tablename__ = "node_capabilities"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "node_id"], ["nodes.tenant_id", "nodes.node_id"]
        ),
        UniqueConstraint(
            "tenant_id",
            "capability_id",
            name="uq_node_capabilities_tenant_id_capability_id",
        ),
        # device_index is NULL for whole-host resources (cpu, ram). Without
        # NULLS NOT DISTINCT a node could register "the RAM" twice.
        UniqueConstraint(
            "node_id",
            "kind",
            "device_index",
            name="uq_node_capabilities_node_id_kind_device_index",
            postgresql_nulls_not_distinct=True,
        ),
        CheckConstraint(
            "kind IN ('cpu','gpu','ram','disk')", name="kind_allowed"
        ),
        CheckConstraint(
            "total_quantity >= 0", name="total_non_negative"
        ),
        CheckConstraint(
            "(kind = 'gpu') = (device_index IS NOT NULL)",
            name="device_index_gpu_only",
        ),
        # The unit is a property of the kind, not something the node chooses.
        # Free text here meant `offered - used` could subtract MB from GiB and
        # report a busy machine as idle — see migration 0010.
        CheckConstraint(
            "(kind = 'cpu'  AND unit = 'millicores') OR "
            "(kind = 'ram'  AND unit = 'bytes') OR "
            "(kind = 'disk' AND unit = 'bytes') OR "
            "(kind = 'gpu'  AND unit = 'devices')",
            name="unit_matches_kind",
        ),
        # Target of the resource_snapshots foreign key: an observation may only
        # name a capability belonging to the node that reported it.
        UniqueConstraint(
            "tenant_id",
            "node_id",
            "capability_id",
            name="uq_node_capabilities_tenant_id_node_id_capability_id",
        ),
    )

    capability_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column()
    node_id: Mapped[InvId] = mapped_column()
    kind: Mapped[str] = mapped_column(String(8))
    #: Present for per-device resources (GPU), NULL for whole-host resources.
    device_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vendor: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    #: In the canonical unit for ``kind`` — millicores, bytes or devices.
    #: ``bigint`` because each of those counts something indivisible, and
    #: because it is the type ``inv.resources.capacity`` uses.
    total_quantity: Mapped[int] = mapped_column(BigInteger)
    #: Constrained to the canonical unit for this kind (``unit_matches_kind``).
    #: The offer and the observation do not repeat it; they join for it, so
    #: there is nowhere for two units to disagree. See ``saintvision.units``.
    unit: Mapped[str] = mapped_column(String(16))
    #: Whether the resource can be split across allocations. A GPU is not
    #: divisible in this pilot; RAM is. The scheduler in S05 relies on this.
    divisible: Mapped[bool] = mapped_column(default=False)
    detected_at: Mapped[Utc] = mapped_column(server_default=text("now()"))
    version: Mapped[int] = mapped_column(default=1)


class ResourceOffer(Base):
    """How much of a capability the node's owner allows the platform to use.

    The offer is a ceiling, never a promise: the node owner keeps their machine.
    """

    __tablename__ = "resource_offers"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "capability_id"],
            ["node_capabilities.tenant_id", "node_capabilities.capability_id"],
        ),
        UniqueConstraint(
            "tenant_id", "offer_id", name="uq_resource_offers_tenant_id_offer_id"
        ),
        CheckConstraint(
            "offered_quantity >= 0", name="offered_non_negative"
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to > effective_from",
            name="effective_range_ordered",
        ),
        Index("ix_resource_offers_tenant_id_capability_id", "tenant_id", "capability_id"),
    )

    offer_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column()
    capability_id: Mapped[InvId] = mapped_column()
    #: In the capability's canonical unit. Deliberately not accompanied by a
    #: unit column: the capability owns the unit.
    offered_quantity: Mapped[int] = mapped_column(BigInteger)
    effective_from: Mapped[Utc] = mapped_column(server_default=text("now()"))
    effective_to: Mapped[Utc | None] = mapped_column(nullable=True)
    version: Mapped[int] = mapped_column(default=1)


class ResourceSnapshot(Base):
    """Observed utilisation, range partitioned by month.

    Retention is 90 days (PLAN-DB-001) and there is deliberately no DEFAULT
    partition: a missing partition must fail the insert loudly rather than pile
    rows into a bucket that then blocks attaching the real partition (CR-06).
    """

    __tablename__ = "resource_snapshots"
    __table_args__ = (
        CheckConstraint(
            "used_quantity >= 0", name="used_non_negative"
        ),
        # Without this an authenticated node could post utilisation against
        # any capability in its tenant, including another machine's — which
        # placement reads as that machine being busy, or this one being idle.
        ForeignKeyConstraint(
            ["tenant_id", "node_id", "capability_id"],
            [
                "node_capabilities.tenant_id",
                "node_capabilities.node_id",
                "node_capabilities.capability_id",
            ],
        ),
        Index("ix_resource_snapshots_tenant_id_observed_at", "tenant_id", "observed_at"),
        Index("ix_resource_snapshots_node_id_observed_at", "node_id", "observed_at"),
        {"postgresql_partition_by": "RANGE (observed_at)"},
    )

    snapshot_id: Mapped[InvId] = mapped_column(primary_key=True)
    #: Part of the primary key because PostgreSQL requires the partition key in
    #: every unique constraint on a partitioned table.
    observed_at: Mapped[Utc] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column()
    node_id: Mapped[InvId] = mapped_column()
    capability_id: Mapped[InvId] = mapped_column()
    #: In the capability's canonical unit, like the offer it is compared with.
    used_quantity: Mapped[int] = mapped_column(BigInteger)
    detail: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
