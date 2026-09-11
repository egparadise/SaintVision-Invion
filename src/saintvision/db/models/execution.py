"""Workspace, workload, run, attempt and step tables (S03-DB).

The Run is the *logical* execution and keeps one state from the eleven fixed by
ADR-001. A retry is not a new Run and does not reset the old one — it is a new
``run_attempts`` row, so the history of what was tried is never overwritten.

Concurrency and the lease/fencing invariants are Codex's (ADR-005/006, S05).
What is here is the shape of the record, and the constraints that keep an
impossible record from being stored at all.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
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

from ...runs.state import ALL_REASONS, ALL_STATES
from ..base import Base, InvId, Sha256, TenantId, TraceId, Utc

WORKSPACE_STATUSES = ("provisioning", "ready", "suspended", "deleting", "deleted")
VOLUME_KINDS = ("persistent", "ephemeral", "dataset_mount")
STEP_STATUSES = ("pending", "running", "succeeded", "failed", "skipped")

_STATE_LIST = ",".join(f"'{s}'" for s in ALL_STATES)
_REASON_LIST = ",".join(f"'{r}'" for r in ALL_REASONS)


class Workspace(Base):
    """A project-scoped working area. Separate from the physical node.

    ``node_id`` is where it currently sits, and it is nullable: a workspace
    exists independently of any node, which is what makes migration possible at
    all. Nothing here promises that uncommitted files survive a move
    (PLAN-STORAGE-001).
    """

    __tablename__ = "workspaces"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "project_id"],
            ["projects.tenant_id", "projects.project_id"],
        ),
        UniqueConstraint("tenant_id", "workspace_id", name="uq_workspaces_tenant_id_workspace_id"),
        UniqueConstraint("project_id", "name", name="uq_workspaces_project_id_name"),
        CheckConstraint(
            "status IN ('provisioning','ready','suspended','deleting','deleted')",
            name="status_allowed",
        ),
        CheckConstraint(
            "(status = 'deleted') = (deleted_at IS NOT NULL)", name="deletion_paired"
        ),
        Index("ix_workspaces_tenant_id_project_id", "tenant_id", "project_id"),
    )

    workspace_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column()
    project_id: Mapped[InvId] = mapped_column()
    name: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(16), default="provisioning")
    #: Current placement. NULL while unplaced or between placements.
    node_id: Mapped[InvId | None] = mapped_column(nullable=True)
    created_by_user_id: Mapped[InvId] = mapped_column()
    created_at: Mapped[Utc] = mapped_column(server_default=text("now()"))
    deleted_at: Mapped[Utc | None] = mapped_column(nullable=True)
    version: Mapped[int] = mapped_column(default=1)


class WorkspaceVolume(Base):
    """Storage attached to a workspace (S03-ST).

    ``persistent`` and ``ephemeral`` are kept apart deliberately: conflating
    them is how "it survived last time" becomes an assumption. A dataset mount
    is read-only by construction.
    """

    __tablename__ = "workspace_volumes"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "workspace_id"],
            ["workspaces.tenant_id", "workspaces.workspace_id"],
        ),
        UniqueConstraint("tenant_id", "volume_id", name="uq_workspace_volumes_tenant_id_volume_id"),
        UniqueConstraint("workspace_id", "mount_path", name="uq_workspace_volumes_workspace_id_mount_path"),
        CheckConstraint(
            "kind IN ('persistent','ephemeral','dataset_mount')", name="kind_allowed"
        ),
        CheckConstraint(
            "NOT (kind = 'dataset_mount' AND writable)",
            name="dataset_mount_is_read_only",
        ),
        CheckConstraint("size_bytes >= 0", name="size_non_negative"),
    )

    volume_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column()
    workspace_id: Mapped[InvId] = mapped_column()
    kind: Mapped[str] = mapped_column(String(16))
    #: Normalised by storage.pathsafe before it is stored.
    mount_path: Mapped[str] = mapped_column(Text)
    writable: Mapped[bool] = mapped_column(default=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    #: For a dataset mount, the immutable inv:// URI it resolves to.
    source_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[Utc] = mapped_column(server_default=text("now()"))
    version: Mapped[int] = mapped_column(default=1)


class Workload(Base):
    """The validated specification a Run executes.

    Stored separately from the Run so that the same spec can be run more than
    once and so that the spec a Run used is immutable: ``spec_sha256`` pins it.
    An AgentRunSpec is a WorkloadSpec plus tool and budget constraints, not a
    replacement schema (PLAN-BACKEND-001).
    """

    __tablename__ = "workloads"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "project_id"],
            ["projects.tenant_id", "projects.project_id"],
        ),
        UniqueConstraint("tenant_id", "workload_id", name="uq_workloads_tenant_id_workload_id"),
        CheckConstraint("kind IN ('batch','agent','service')", name="kind_allowed"),
        Index("ix_workloads_tenant_id_project_id", "tenant_id", "project_id"),
    )

    workload_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column()
    project_id: Mapped[InvId] = mapped_column()
    kind: Mapped[str] = mapped_column(String(16), default="batch")
    objective: Mapped[str] = mapped_column(Text)
    spec: Mapped[dict] = mapped_column(JSONB)
    #: SHA-256 of the canonical spec JSON. What an approval is bound to.
    spec_sha256: Mapped[Sha256]
    #: Contract version the spec validates against (SemVer, not the row version).
    contract_version: Mapped[str] = mapped_column(String(32))
    created_by_user_id: Mapped[InvId] = mapped_column()
    created_at: Mapped[Utc] = mapped_column(server_default=text("now()"))
    version: Mapped[int] = mapped_column(default=1)


class Run(Base):
    """A logical execution. One of eleven states, never a twelfth."""

    __tablename__ = "runs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "workload_id"],
            ["workloads.tenant_id", "workloads.workload_id"],
        ),
        ForeignKeyConstraint(
            ["tenant_id", "workspace_id"],
            ["workspaces.tenant_id", "workspaces.workspace_id"],
        ),
        UniqueConstraint("tenant_id", "run_id", name="uq_runs_tenant_id_run_id"),
        CheckConstraint(f"state IN ({_STATE_LIST})", name="state_allowed"),
        CheckConstraint(
            f"termination_reason IS NULL OR termination_reason IN ({_REASON_LIST})",
            name="termination_reason_allowed",
        ),
        # Terminal states carry a reason; non-terminal states must not, or the
        # record claims an ending that did not happen.
        CheckConstraint(
            "(state IN ('succeeded','failed','cancelled')) = (termination_reason IS NOT NULL)",
            name="reason_only_when_terminal",
        ),
        CheckConstraint(
            "(state IN ('succeeded','failed','cancelled')) = (ended_at IS NOT NULL)",
            name="ended_at_only_when_terminal",
        ),
        # Succeeding without Evidence is the failure ADR-008 exists to prevent.
        CheckConstraint(
            "state <> 'succeeded' OR evidence_id IS NOT NULL",
            name="success_requires_evidence",
        ),
        CheckConstraint("attempt_count >= 0", name="attempt_count_non_negative"),
        CheckConstraint("retry_budget >= 0", name="retry_budget_non_negative"),
        Index("ix_runs_tenant_id_state", "tenant_id", "state"),
        Index("ix_runs_tenant_id_workspace_id", "tenant_id", "workspace_id"),
        Index("ix_runs_trace_id", "trace_id"),
    )

    run_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column()
    workload_id: Mapped[InvId] = mapped_column()
    workspace_id: Mapped[InvId] = mapped_column()
    state: Mapped[str] = mapped_column(String(24), default="draft")
    termination_reason: Mapped[str | None] = mapped_column(String(24), nullable=True)
    #: Set only on success, and only in the transaction that writes it.
    evidence_id: Mapped[InvId | None] = mapped_column(nullable=True)
    requested_by_user_id: Mapped[InvId] = mapped_column()
    #: Business correlation key. Distinct from a span id (ADR-004).
    trace_id: Mapped[TraceId | None] = mapped_column(nullable=True)
    attempt_count: Mapped[int] = mapped_column(default=0)
    retry_budget: Mapped[int] = mapped_column(default=2)
    max_wall_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[Utc] = mapped_column(server_default=text("now()"))
    started_at: Mapped[Utc | None] = mapped_column(nullable=True)
    ended_at: Mapped[Utc | None] = mapped_column(nullable=True)
    version: Mapped[int] = mapped_column(default=1)


class RunAttempt(Base):
    """One try. Records what was true for *that* try and is never rewritten.

    PLAN-DB-001 requires snapshot, placement, fence and configuration versions
    per attempt. Without them a retry that behaved differently cannot be
    explained.
    """

    __tablename__ = "run_attempts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "run_id"], ["runs.tenant_id", "runs.run_id"]
        ),
        UniqueConstraint("tenant_id", "attempt_id", name="uq_run_attempts_tenant_id_attempt_id"),
        UniqueConstraint("run_id", "attempt_number", name="uq_run_attempts_run_id_attempt_number"),
        CheckConstraint("attempt_number >= 1", name="attempt_number_positive"),
        CheckConstraint(
            "outcome IS NULL OR outcome IN ('succeeded','failed','cancelled','abandoned')",
            name="outcome_allowed",
        ),
        Index("ix_run_attempts_tenant_id_run_id", "tenant_id", "run_id"),
    )

    attempt_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column()
    run_id: Mapped[InvId] = mapped_column()
    attempt_number: Mapped[int] = mapped_column(Integer)
    node_id: Mapped[InvId | None] = mapped_column(nullable=True)
    #: The resource snapshot the placement decision was made against.
    placement_snapshot: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    #: Lease fencing token for this attempt. Owned by S05; recorded here so the
    #: attempt history is complete when it arrives.
    fence_token: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    scheduler_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    policy_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    started_at: Mapped[Utc] = mapped_column(server_default=text("now()"))
    ended_at: Mapped[Utc | None] = mapped_column(nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(16), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Step(Base):
    """A node of the RunGraph as executed within one attempt."""

    __tablename__ = "steps"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "attempt_id"],
            ["run_attempts.tenant_id", "run_attempts.attempt_id"],
        ),
        UniqueConstraint("tenant_id", "step_id", name="uq_steps_tenant_id_step_id"),
        UniqueConstraint("attempt_id", "ordinal", name="uq_steps_attempt_id_ordinal"),
        CheckConstraint(
            "status IN ('pending','running','succeeded','failed','skipped')",
            name="status_allowed",
        ),
        CheckConstraint("ordinal >= 0", name="ordinal_non_negative"),
        Index("ix_steps_tenant_id_attempt_id", "tenant_id", "attempt_id"),
    )

    step_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column()
    attempt_id: Mapped[InvId] = mapped_column()
    ordinal: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(128))
    tool_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tool_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    started_at: Mapped[Utc | None] = mapped_column(nullable=True)
    ended_at: Mapped[Utc | None] = mapped_column(nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class Checkpoint(Base):
    """Written atomically at step completion (공통 계약 §8).

    ``step_ordinal`` rather than a step FK, because a checkpoint has to survive
    being read by a *later* attempt whose steps are different rows.
    """

    __tablename__ = "checkpoints"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "run_id"], ["runs.tenant_id", "runs.run_id"]
        ),
        UniqueConstraint("tenant_id", "checkpoint_id", name="uq_checkpoints_tenant_id_checkpoint_id"),
        UniqueConstraint("run_id", "step_ordinal", name="uq_checkpoints_run_id_step_ordinal"),
        CheckConstraint("step_ordinal >= 0", name="step_ordinal_non_negative"),
    )

    checkpoint_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column()
    run_id: Mapped[InvId] = mapped_column()
    step_ordinal: Mapped[int] = mapped_column(Integer)
    state_blob: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    created_at: Mapped[Utc] = mapped_column(server_default=text("now()"))


class Approval(Base):
    """A human decision bound to exact content.

    ADR: an approval carries a content digest, actor, scope and expiry, and a
    changed request may not reuse it. ``subject_sha256`` is that digest; the
    service compares it to the workload's current ``spec_sha256`` and refuses
    when they differ.
    """

    __tablename__ = "approvals"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "run_id"], ["runs.tenant_id", "runs.run_id"]
        ),
        UniqueConstraint("tenant_id", "approval_id", name="uq_approvals_tenant_id_approval_id"),
        CheckConstraint(
            "decision IN ('approved','rejected')", name="decision_allowed"
        ),
        CheckConstraint("risk_level BETWEEN 0 AND 3", name="risk_level_in_range"),
        CheckConstraint("expires_at > decided_at", name="expiry_after_decision"),
        # The execution core spells this `apr_` and enforces it. One approval id
        # has to be writable on both sides of the seam it crosses.
        CheckConstraint(
            "approval_id ~ '^apr_[0-9A-HJKMNP-TV-Z]{26}$'", name="approval_id_prefix"
        ),
        Index("ix_approvals_tenant_id_run_id", "tenant_id", "run_id"),
    )

    approval_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column()
    run_id: Mapped[InvId] = mapped_column()
    #: Digest of exactly what was approved.
    subject_sha256: Mapped[Sha256]
    decision: Mapped[str] = mapped_column(String(16))
    #: L0..L3 from the governance table (ADR-017).
    risk_level: Mapped[int] = mapped_column(Integer)
    scope: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    decided_by_user_id: Mapped[InvId] = mapped_column()
    decided_at: Mapped[Utc] = mapped_column(server_default=text("now()"))
    expires_at: Mapped[Utc]
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
