"""What the business surface must hold to drive the execution core.

The chain a request actually travels is: check the project permission, stop
editing, freeze the inputs, obtain a fresh approval, reserve resources, queue
the execution, run it, store the result. Steps three onward belong to the
execution core and are implemented there. The first two, and the record that
ties the whole chain to one moment in time, belong here — and did not exist.

Two tables, each answering a question that was previously answered by assuming.

``workspace_edit_locks`` — **stop editing.** "Freeze the inputs" is only
meaningful if something stopped them changing first. Without a lock, the freeze
captures whatever the workspace happened to contain when the read ran, and a
save that lands a millisecond later produces a run whose approved inputs are
not the inputs anyone looked at. The lock also records the content hash at the
moment editing stopped, so the freeze can prove it captured *that* state rather
than a later one.

``execution_bindings`` — **the identity and epoch mapping.** A public Run and an
``inv`` Run share an id: both are ``run_`` plus the same 26-character Crockford
ULID, and the prefixes agree for projects, nodes and workspaces too. What does
not travel with the id is *when* — the execution core roll a recovery epoch
whenever an operator reconciles after a control-plane restart, and every lease,
claim and delivery is bound to the epoch in force when it was made. A binding
prepared before a roll must not execute after one; it describes a world that no
longer exists.

So the binding records which epoch and which ``inv`` run version the frozen
inputs and the approval were tied to. Every later step compares. That comparison
is the whole reason the table exists: an id alone cannot say whether the thing
it names is still the thing that was approved.
"""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base, BigInteger, InvId, Sha256, TenantId, Utc

#: What a binding has reached. Deliberately not the Run's own state: a Run is
#: ``recovering`` for the whole of this chain, and these are the steps inside it.
BINDING_STATES = ("frozen", "approved", "queued", "executing", "settled", "abandoned")


class WorkspaceEditLock(Base):
    """Editing is stopped on this workspace, and this is what it contained.

    One lock at a time per workspace, enforced by a partial unique index rather
    than by the service — two callers quiescing the same workspace for two
    different runs is exactly the race the lock exists to prevent, and a check
    in application code loses that race.
    """

    __tablename__ = "workspace_edit_locks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "workspace_id"],
            ["workspaces.tenant_id", "workspaces.workspace_id"],
        ),
        ForeignKeyConstraint(
            ["tenant_id", "run_id"], ["runs.tenant_id", "runs.run_id"]
        ),
        UniqueConstraint(
            "tenant_id", "lock_id", name="uq_workspace_edit_locks_tenant_id_lock_id"
        ),
        # One held lock per workspace. Released ones accumulate as history.
        Index(
            "uq_workspace_edit_locks_held",
            "tenant_id",
            "workspace_id",
            unique=True,
            postgresql_where=text("released_at IS NULL"),
        ),
        CheckConstraint(
            "released_at IS NULL OR released_at >= acquired_at",
            name="release_follows_acquisition",
        ),
        CheckConstraint(
            "content_sha256 = lower(content_sha256)", name="digest_is_lowercase"
        ),
        Index("ix_workspace_edit_locks_tenant_id_run_id", "tenant_id", "run_id"),
    )

    lock_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column()
    workspace_id: Mapped[InvId] = mapped_column()
    #: The run this quiesce is for. A lock held for no particular run is a lock
    #: nobody can tell when to release.
    run_id: Mapped[InvId] = mapped_column()
    held_by_user_id: Mapped[InvId] = mapped_column()
    #: What the workspace contained when editing stopped. The freeze that
    #: follows must produce this same digest, or it captured a later state.
    content_sha256: Mapped[Sha256] = mapped_column()
    reason: Mapped[str] = mapped_column(String(64), default="execution")
    acquired_at: Mapped[Utc] = mapped_column(server_default=text("now()"))
    released_at: Mapped[Utc | None] = mapped_column(nullable=True)
    version: Mapped[int] = mapped_column(default=1)


class ExecutionBinding(Base):
    """One public Run, tied to one execution-core epoch and run version.

    The unique key is ``(tenant, run, epoch, bound version)``: a Run may be
    bound more than once — that is what a recovery attempt is — but never twice
    within the same epoch at the same version, which would be two approvals for
    one moment.
    """

    __tablename__ = "execution_bindings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "run_id"], ["runs.tenant_id", "runs.run_id"]
        ),
        ForeignKeyConstraint(
            ["tenant_id", "project_id"],
            ["projects.tenant_id", "projects.project_id"],
        ),
        ForeignKeyConstraint(
            ["tenant_id", "lock_id"],
            ["workspace_edit_locks.tenant_id", "workspace_edit_locks.lock_id"],
        ),
        UniqueConstraint(
            "tenant_id", "binding_id", name="uq_execution_bindings_tenant_id_binding_id"
        ),
        UniqueConstraint(
            "tenant_id",
            "run_id",
            "recovery_epoch",
            "bound_run_version",
            name="uq_execution_bindings_run_epoch_version",
        ),
        CheckConstraint(
            "state IN ('frozen','approved','queued','executing','settled','abandoned')",
            name="state_allowed",
        ),
        CheckConstraint("bound_run_version > 0", name="bound_version_positive"),
        CheckConstraint("source_attempt >= 1", name="source_attempt_positive"),
        CheckConstraint("input_size_bytes >= 0", name="input_size_non_negative"),
        CheckConstraint(
            "input_sha256 = lower(input_sha256)", name="digest_is_lowercase"
        ),
        # The execution core's approval id, when one has been obtained. Present
        # exactly when the binding has moved past `frozen`.
        CheckConstraint(
            "(state = 'frozen') = (approval_id IS NULL)", name="approval_paired_to_state"
        ),
        CheckConstraint(
            "approval_id IS NULL OR approval_id ~ '^apr_[0-9A-HJKMNP-TV-Z]{26}$'",
            name="approval_id_is_a_core_approval",
        ),
        CheckConstraint(
            "(state IN ('settled','abandoned')) = (settled_at IS NOT NULL)",
            name="settlement_paired",
        ),
        Index("ix_execution_bindings_tenant_id_state", "tenant_id", "state"),
        Index(
            "ix_execution_bindings_tenant_id_recovery_epoch",
            "tenant_id",
            "recovery_epoch",
        ),
    )

    binding_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column()
    project_id: Mapped[InvId] = mapped_column()
    #: The same value on both sides of the seam. `run_` plus the same ULID.
    run_id: Mapped[InvId] = mapped_column()
    workspace_id: Mapped[InvId] = mapped_column()
    #: The lock under which the inputs were frozen. Without it the binding
    #: cannot say the inputs were still when it read them.
    lock_id: Mapped[InvId] = mapped_column()

    #: `inv.control_epoch.epoch` at the moment of freezing. Every later step
    #: compares against the epoch then in force and refuses if it moved.
    recovery_epoch: Mapped[str] = mapped_column(UUID(as_uuid=False))
    #: `inv.runs.version` the approval binds to (`bound_run_version`).
    bound_run_version: Mapped[int] = mapped_column(BigInteger)
    #: `inv.runs.attempt` the checkout came from.
    source_attempt: Mapped[int] = mapped_column(Integer)

    #: `inv.workspace_resumptions.resume_id` and the checkout it froze.
    resume_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True)
    checkout_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True)
    #: The frozen bytes, as the execution core will verify them.
    input_sha256: Mapped[Sha256] = mapped_column()
    input_size_bytes: Mapped[int] = mapped_column(BigInteger)
    step_id: Mapped[str] = mapped_column(String(200))

    #: `inv.approval_requests.approval_id`. NULL until an approval is requested.
    approval_id: Mapped[str | None] = mapped_column(String(30), nullable=True)
    #: Which permission decision authorised this, recorded rather than recomputed.
    permission_snapshot_id: Mapped[InvId | None] = mapped_column(nullable=True)

    state: Mapped[str] = mapped_column(String(16), default="frozen")
    created_by_user_id: Mapped[InvId] = mapped_column()
    created_at: Mapped[Utc] = mapped_column(server_default=text("now()"))
    settled_at: Mapped[Utc | None] = mapped_column(nullable=True)
    #: Why it ended, when it ended without executing.
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    version: Mapped[int] = mapped_column(default=1)
