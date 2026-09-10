"""Distributed placement: using several machines for one job.

**What this is not.** It is not a transparent shared memory across the network.
Local RAM answers in tens of nanoseconds; a LAN round trip is tens of
microseconds to milliseconds — three to five orders of magnitude slower. A
system that let a process address a remote machine's RAM as if it were its own
would be slower than not doing it, and the final plan forbids presenting
physical RAM/VRAM as one memory for that reason. Nothing here does.

**What it is.** The way several machines' memory is actually used for one job:
the job is split into shards, each shard runs inside one node's memory, and the
shards run at the same time. A job whose working set exceeds any single machine
becomes runnable, and a job that parallelises finishes sooner. That is the real
version of "use all the machines", and it is what these tables record.

The distinction shows up in the capacity numbers. A pool reports three, never
one:

* ``totalOffered`` — the sum. What the pool can do across many tasks.
* ``largestSingleNode`` — the ceiling for one task that cannot be split.
* ``spareNow`` — what is idle right now, which is what idle-first placement
  ranks on.

Reporting only the sum is the misrepresentation the plan prohibits.
"""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base, BigInteger, InvId, TenantId, Utc

#: How a job uses more than one machine.
#:
#: ``single_node``   — one shard. The default and the only safe choice when the
#:                     work has not been shown to split.
#: ``data_parallel`` — the same computation over disjoint slices of input. Each
#:                     shard holds the whole model and part of the data.
#: ``sharded``       — the state itself is split, so no shard holds all of it.
#:                     This is what makes a job larger than one machine's memory
#:                     runnable, and it is the honest reading of "pool the
#:                     memory". It requires the workload to support it; the
#:                     platform cannot impose it on an arbitrary program.
PLAN_STRATEGIES = ("single_node", "data_parallel", "sharded")
PLAN_STATES = ("planned", "placed", "running", "completed", "failed", "cancelled")
PLACEMENT_STATES = ("planned", "running", "succeeded", "failed", "skipped")


class DistributedPlan(Base):
    """How one Run was spread over the pool.

    Kept separately from the Run so the placement decision is a record in its
    own right: which nodes, why those, and what each was asked to hold.
    """

    __tablename__ = "distributed_plans"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "run_id"], ["runs.tenant_id", "runs.run_id"]
        ),
        ForeignKeyConstraint(
            ["tenant_id", "pool_id"],
            ["resource_pools.tenant_id", "resource_pools.pool_id"],
        ),
        UniqueConstraint("tenant_id", "plan_id", name="uq_distributed_plans_tenant_id_plan_id"),
        UniqueConstraint("run_id", name="uq_distributed_plans_run_id"),
        CheckConstraint(
            "strategy IN ('single_node','data_parallel','sharded')", name="strategy_allowed"
        ),
        CheckConstraint(
            "state IN ('planned','placed','running','completed','failed','cancelled')",
            name="state_allowed",
        ),
        CheckConstraint("shard_count >= 1", name="shard_count_positive"),
        # The API said le=1024 and the table said nothing. A bound that
        # only one entry point enforces is not a bound.
        CheckConstraint("shard_count <= 1024", name="shard_count_bounded"),
        # A single-node plan with several shards is a contradiction, and it is
        # the contradiction that would quietly turn "run it here" into "spread
        # it around".
        CheckConstraint(
            "strategy <> 'single_node' OR shard_count = 1", name="single_node_has_one_shard"
        ),
        # Splitting work the caller never said was splittable is how a platform
        # corrupts results while looking fast.
        CheckConstraint(
            "shard_count = 1 OR splittable_declared", name="splitting_requires_declaration"
        ),
        Index("ix_distributed_plans_tenant_id_pool_id", "tenant_id", "pool_id"),
    )

    plan_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column()
    run_id: Mapped[InvId] = mapped_column()
    pool_id: Mapped[InvId] = mapped_column()
    strategy: Mapped[str] = mapped_column(String(16), default="single_node")
    state: Mapped[str] = mapped_column(String(16), default="planned")
    shard_count: Mapped[int] = mapped_column(Integer, default=1)
    #: The workload declared that it can be split this way. The platform never
    #: infers it: a program that is not shard-aware produces wrong answers when
    #: split, not slow ones.
    splittable_declared: Mapped[bool] = mapped_column(default=False)
    #: What one shard needs, in the same canonical units a node's spare
    #: capacity is measured in (``saintvision.units``). These are compared with
    #: ``>=`` against that spare capacity, so they cannot be in cores while the
    #: capacity is in millicores — that comparison is the placement decision.
    shard_cpu_millicores: Mapped[int] = mapped_column(BigInteger, default=0)
    shard_ram_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    shard_gpu_devices: Mapped[int] = mapped_column(Integer, default=0)
    #: Why these nodes: the spare-capacity ranking at decision time, kept so a
    #: placement can be explained afterwards (PLAN-BACKEND-001 "explain").
    ranking_snapshot: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    created_at: Mapped[Utc] = mapped_column(server_default=text("now()"))
    version: Mapped[int] = mapped_column(default=1)


class PlanPlacement(Base):
    """One shard on one node.

    ``shard_index`` is unique per plan; a node may hold more than one shard
    when it has the capacity, which is why there is no unique on node.
    """

    __tablename__ = "plan_placements"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "plan_id"],
            ["distributed_plans.tenant_id", "distributed_plans.plan_id"],
        ),
        ForeignKeyConstraint(
            ["tenant_id", "node_id"], ["nodes.tenant_id", "nodes.node_id"]
        ),
        UniqueConstraint("plan_id", "shard_index", name="uq_plan_placements_plan_id_shard_index"),
        CheckConstraint("shard_index >= 0", name="shard_index_non_negative"),
        CheckConstraint(
            "state IN ('planned','running','succeeded','failed','skipped')", name="state_allowed"
        ),
        CheckConstraint("assigned_cpu_millicores >= 0", name="assigned_cpu_non_negative"),
        CheckConstraint("assigned_ram_bytes >= 0", name="assigned_ram_non_negative"),
        CheckConstraint("assigned_gpu_devices >= 0", name="assigned_gpu_non_negative"),
        Index("ix_plan_placements_tenant_id_node_id", "tenant_id", "node_id"),
    )

    tenant_id: Mapped[TenantId] = mapped_column(primary_key=True)
    plan_id: Mapped[InvId] = mapped_column(primary_key=True)
    shard_index: Mapped[int] = mapped_column(Integer, primary_key=True)
    node_id: Mapped[InvId] = mapped_column()
    assigned_cpu_millicores: Mapped[int] = mapped_column(BigInteger, default=0)
    assigned_ram_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    assigned_gpu_devices: Mapped[int] = mapped_column(Integer, default=0)
    #: The node's spare capacity when it was chosen, for the explain trail.
    spare_at_placement: Mapped[dict] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb")
    )
    state: Mapped[str] = mapped_column(String(16), default="planned")
    placed_at: Mapped[Utc] = mapped_column(server_default=text("now()"))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
