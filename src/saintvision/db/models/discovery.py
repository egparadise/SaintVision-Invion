"""Node discovery and resource pools.

A Node Agent announces itself on the internal network; the Control Plane
records the announcement as a **candidate** and nothing more. Three properties
this schema is built to keep:

* **Announcing grants nothing.** A candidate is inert until a person admits it,
  and admission goes through the existing one-time bootstrap token. Discovery
  makes a machine easy to find; it does not make it trusted.
* **What a machine says about itself is a claim, not a fact.** Every
  self-reported field is prefixed ``claimed_``. The authoritative capabilities
  are the ones reported after enrollment over an authenticated channel and
  stored in ``node_capabilities``.
* **A pool total is not what one workload can use.** The final plan forbids
  presenting physical RAM/VRAM as a single memory, so the capacity query
  returns the per-kind sum *and* the largest single node beside it. A caller
  cannot honestly show only the sum.
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
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base, InvId, TenantId, Utc

ANNOUNCEMENT_STATES = ("candidate", "admitted", "declined", "expired")
POOL_STATUSES = ("active", "archived")

#: An announcement older than this is stale: the machine stopped announcing and
#: should not keep appearing as if it were there.
ANNOUNCEMENT_TTL_SECONDS = 300

#: Cap per tenant. Even authenticated callers must not be able to fill the
#: candidate table with thousands of claimed identities.
MAX_CANDIDATES_PER_TENANT = 500


class NodeAnnouncement(Base):
    """A machine that announced itself and has not been admitted.

    ``instance_id`` is the agent's self-assigned stable identifier. It is
    spoofable, which is why it is only a deduplication key and never an
    authorisation: two announcements with the same instance id are treated as
    the same candidate so a restarting agent does not pile up rows, and that is
    all it does.
    """

    __tablename__ = "node_announcements"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "announcement_id", name="uq_node_announcements_tenant_id_announcement_id"
        ),
        # Dedup on what the agent claims plus where it came from. Neither is
        # trusted; together they keep a restarting agent to one row.
        UniqueConstraint(
            "tenant_id", "instance_id", "source_ip",
            name="uq_node_announcements_tenant_instance_source",
        ),
        CheckConstraint(
            "state IN ('candidate','admitted','declined','expired')", name="state_allowed"
        ),
        CheckConstraint(
            "claimed_os_type IN ('windows','linux')", name="claimed_os_type_allowed"
        ),
        CheckConstraint("claimed_cpu_cores >= 0", name="claimed_cpu_cores_non_negative"),
        CheckConstraint("claimed_ram_bytes >= 0", name="claimed_ram_bytes_non_negative"),
        CheckConstraint("claimed_gpu_count >= 0", name="claimed_gpu_count_non_negative"),
        CheckConstraint("announce_count >= 1", name="announce_count_positive"),
        # An admitted candidate points at the node it became; anything else
        # must not, or the record claims an enrolment that did not happen.
        CheckConstraint(
            "(state = 'admitted') = (admitted_node_id IS NOT NULL)",
            name="admission_paired_with_node",
        ),
        Index("ix_node_announcements_tenant_id_state", "tenant_id", "state"),
        Index("ix_node_announcements_last_seen_at", "last_seen_at"),
    )

    announcement_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column()
    state: Mapped[str] = mapped_column(String(16), default="candidate")
    #: Self-assigned by the agent. Spoofable; a dedup key only.
    instance_id: Mapped[str] = mapped_column(String(128))
    #: Observed by the server from the connection, not taken from the body.
    source_ip: Mapped[str] = mapped_column(INET)
    #: Everything below is what the machine says about itself.
    claimed_hostname: Mapped[str] = mapped_column(String(253))
    claimed_os_type: Mapped[str] = mapped_column(String(16))
    claimed_os_version: Mapped[str] = mapped_column(String(64))
    claimed_agent_version: Mapped[str] = mapped_column(String(64))
    claimed_cpu_cores: Mapped[int] = mapped_column(Integer, default=0)
    claimed_ram_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    claimed_gpu_count: Mapped[int] = mapped_column(Integer, default=0)
    claimed_labels: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    first_seen_at: Mapped[Utc] = mapped_column(server_default=text("now()"))
    last_seen_at: Mapped[Utc] = mapped_column(server_default=text("now()"))
    announce_count: Mapped[int] = mapped_column(Integer, default=1)
    #: Set when a person admits the candidate and enrolment completes.
    admitted_node_id: Mapped[InvId | None] = mapped_column(nullable=True)
    admitted_by_user_id: Mapped[InvId | None] = mapped_column(nullable=True)
    decided_at: Mapped[Utc | None] = mapped_column(nullable=True)
    decline_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class ResourcePool(Base):
    """A named set of nodes a project draws capacity from.

    A pool is an accounting boundary, not a machine. Nothing here implies that
    a workload can span its members.
    """

    __tablename__ = "resource_pools"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "project_id"],
            ["projects.tenant_id", "projects.project_id"],
        ),
        UniqueConstraint("tenant_id", "pool_id", name="uq_resource_pools_tenant_id_pool_id"),
        UniqueConstraint("tenant_id", "name", name="uq_resource_pools_tenant_id_name"),
        CheckConstraint("status IN ('active','archived')", name="status_allowed"),
        Index("ix_resource_pools_tenant_id_project_id", "tenant_id", "project_id"),
    )

    pool_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column()
    project_id: Mapped[InvId] = mapped_column()
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_by_user_id: Mapped[InvId] = mapped_column()
    created_at: Mapped[Utc] = mapped_column(server_default=text("now()"))
    version: Mapped[int] = mapped_column(default=1)


class ResourcePoolMember(Base):
    """A node's membership in a pool.

    A node may belong to several pools — the machine is not consumed by
    joining one — so capacity reported for two overlapping pools counts the
    same hardware twice. :func:`services.pools.pool_capacity` says so rather
    than pretending otherwise.
    """

    __tablename__ = "resource_pool_members"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "pool_id"],
            ["resource_pools.tenant_id", "resource_pools.pool_id"],
        ),
        ForeignKeyConstraint(
            ["tenant_id", "node_id"], ["nodes.tenant_id", "nodes.node_id"]
        ),
        Index("ix_resource_pool_members_tenant_id_node_id", "tenant_id", "node_id"),
    )

    tenant_id: Mapped[TenantId] = mapped_column(primary_key=True)
    pool_id: Mapped[InvId] = mapped_column(primary_key=True)
    node_id: Mapped[InvId] = mapped_column(primary_key=True)
    added_by_user_id: Mapped[InvId] = mapped_column()
    added_at: Mapped[Utc] = mapped_column(server_default=text("now()"))
