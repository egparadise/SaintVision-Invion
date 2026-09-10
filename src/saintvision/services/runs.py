"""Run lifecycle (S03-DB).

Everything that moves a Run between states goes through here, so the eleven
states of ADR-001 and the Evidence invariant of ADR-008 have exactly one
enforcement point.

The invariant, stated plainly: a Run becomes ``succeeded`` only in a
transaction that also writes its EvidenceEnvelope and its outbox row. It is
held three times over — by :func:`complete_run` being the only path,
by ``runs.evidence_id`` being NOT NULL when the state is ``succeeded``, and by
these functions never opening or committing a transaction of their own.

Scheduling, placement and leases are Codex's (ADR-005/006, S05). This module
records that an attempt happened; it does not decide where.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Approval, Run, RunAttempt, Step, Workload, Workspace
from ..errors import (
    AUTH_APPROVAL_DIGEST_MISMATCH,
    AUTH_APPROVAL_EXPIRED,
    BUDGET_RETRY_EXHAUSTED,
    RES_RUN_NOT_FOUND,
    RES_WORKSPACE_NOT_FOUND,
    VAL_SCHEMA,
    InvError,
)
from ..ids import new_id
from ..runs.state import RunState, TerminationReason, assert_transition, is_terminal
from .evidence import canonical_sha256, enqueue_event, record_evidence
from .pagination import Page, build_page, clamp_limit, validate_cursor


def create_run(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    workload_id: str,
    workspace_id: str,
    requested_by_user_id: str,
    now: dt.datetime,
    trace_id: str | None = None,
    retry_budget: int = 2,
    max_wall_time_seconds: int | None = None,
) -> Run:
    """Create a Run in ``draft``.

    A Run always starts at draft even when everything needed is already known:
    skipping straight to validated would leave no record that validation ran.
    """
    workload = session.get(Workload, workload_id)
    if workload is None or workload.tenant_id != tenant_id:
        raise InvError(RES_RUN_NOT_FOUND, "workload not found")
    workspace = session.get(Workspace, workspace_id)
    if workspace is None or workspace.tenant_id != tenant_id:
        raise InvError(RES_WORKSPACE_NOT_FOUND, "workspace not found")
    if workspace.status in ("deleting", "deleted"):
        raise InvError(VAL_SCHEMA, "workspace is being removed")
    if retry_budget < 0:
        raise InvError(VAL_SCHEMA, "retry_budget must not be negative")

    run = Run(
        run_id=new_id("run"),
        tenant_id=tenant_id,
        workload_id=workload_id,
        workspace_id=workspace_id,
        state=RunState.DRAFT.value,
        requested_by_user_id=requested_by_user_id,
        trace_id=trace_id,
        attempt_count=0,
        retry_budget=retry_budget,
        max_wall_time_seconds=max_wall_time_seconds,
        created_at=now,
    )
    session.add(run)
    session.flush()
    return run


def get_run(session: Session, *, tenant_id: uuid.UUID, run_id: str) -> Run:
    run = session.get(Run, run_id)
    if run is None or run.tenant_id != tenant_id:
        raise InvError(RES_RUN_NOT_FOUND, "run not found")
    return run


def advance(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    run_id: str,
    target: RunState | str,
    now: dt.datetime,
    reason: TerminationReason | str | None = None,
) -> Run:
    """Move a Run to a non-success state.

    ``succeeded`` is refused here — it must go through :func:`complete_run`,
    which is the only place that can guarantee Evidence in the same
    transaction.
    """
    run = get_run(session, tenant_id=tenant_id, run_id=run_id)
    destination = assert_transition(run.state, target, reason=reason, run_id=run_id)

    run.state = destination.value
    if destination is RunState.RUNNING and run.started_at is None:
        run.started_at = now
    if is_terminal(destination):
        run.termination_reason = (
            reason.value if isinstance(reason, TerminationReason) else str(reason)
        )
        run.ended_at = now
    run.version += 1
    session.flush()
    return run


def cancel_run(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    run_id: str,
    now: dt.datetime,
    reason: TerminationReason | str = TerminationReason.CANCELLED_BY_USER,
) -> Run:
    """Cancel a Run, idempotently.

    Cancelling an already-cancelled Run returns it unchanged rather than
    failing: a user clicking twice is not an error, and a cancel that can fail
    is a cancel people stop trusting.
    """
    run = get_run(session, tenant_id=tenant_id, run_id=run_id)
    if run.state == RunState.CANCELLED.value:
        return run
    if is_terminal(run.state):
        raise InvError(
            VAL_SCHEMA,
            f"run already ended as {run.state}",
            cause_ref=run_id,
        )
    return advance(
        session, tenant_id=tenant_id, run_id=run_id, target=RunState.CANCELLED,
        now=now, reason=reason,
    )


def start_attempt(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    run_id: str,
    now: dt.datetime,
    node_id: str | None = None,
    placement_snapshot: dict[str, Any] | None = None,
    fence_token: int | None = None,
    scheduler_version: str | None = None,
    policy_version: str | None = None,
) -> RunAttempt:
    """Record a new attempt and move the Run to ``running``.

    The retry budget is checked here rather than at the retry site, because the
    budget is a property of the Run and there is more than one path back to
    ``scheduled``.
    """
    run = get_run(session, tenant_id=tenant_id, run_id=run_id)
    if run.state != RunState.SCHEDULED.value:
        raise InvError(
            VAL_SCHEMA,
            f"an attempt can only start from scheduled, not {run.state}",
            cause_ref=run_id,
        )
    # attempt_count counts attempts already made; the first is free, each
    # subsequent one spends budget.
    if run.attempt_count > run.retry_budget:
        raise InvError(
            BUDGET_RETRY_EXHAUSTED,
            "retry budget is exhausted",
            cause_ref=run_id,
        )

    attempt = RunAttempt(
        attempt_id=new_id("attempt"),
        tenant_id=tenant_id,
        run_id=run_id,
        attempt_number=run.attempt_count + 1,
        node_id=node_id,
        placement_snapshot=placement_snapshot or {},
        fence_token=fence_token,
        scheduler_version=scheduler_version,
        policy_version=policy_version,
        started_at=now,
    )
    session.add(attempt)
    run.attempt_count += 1
    session.flush()

    advance(session, tenant_id=tenant_id, run_id=run_id, target=RunState.RUNNING, now=now)
    return attempt


def finish_attempt(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    attempt_id: str,
    outcome: str,
    now: dt.datetime,
    error_code: str | None = None,
) -> RunAttempt:
    attempt = session.get(RunAttempt, attempt_id)
    if attempt is None or attempt.tenant_id != tenant_id:
        raise InvError(RES_RUN_NOT_FOUND, "attempt not found")
    if outcome not in ("succeeded", "failed", "cancelled", "abandoned"):
        raise InvError(VAL_SCHEMA, f"unknown attempt outcome: {outcome!r}")
    attempt.outcome = outcome
    attempt.ended_at = now
    attempt.error_code = error_code
    session.flush()
    return attempt


def complete_run(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    run_id: str,
    now: dt.datetime,
    actor_type: str,
    actor_id: str,
    action: str,
    input_schema: str,
    input_payload: Any,
    output_schema: str | None = None,
    output_ref: str | None = None,
    telemetry: dict[str, Any] | None = None,
    component_versions: dict[str, str] | None = None,
    policy_id: str | None = None,
    approval_id: str | None = None,
) -> tuple[Run, str, str]:
    """Move ``verifying -> succeeded`` with its Evidence and its event.

    This is the only path to ``succeeded``. All three writes happen in the
    caller's transaction, so a crash between them cannot leave a Run reported
    successful with no Evidence behind it (ADR-008).

    Returns the run, the evidence id and the outbox event id.
    """
    run = get_run(session, tenant_id=tenant_id, run_id=run_id)
    if run.state != RunState.VERIFYING.value:
        raise InvError(
            VAL_SCHEMA,
            f"a run can only succeed from verifying, not {run.state}",
            cause_ref=run_id,
        )

    evidence_id = record_evidence(
        session,
        tenant_id=tenant_id,
        run_id=run_id,
        action=action,
        actor_type=actor_type,
        actor_id=actor_id,
        input_schema=input_schema,
        input_payload=input_payload,
        result="succeeded",
        now=now,
        trace_id=run.trace_id,
        policy_id=policy_id,
        approval_id=approval_id,
        output_schema=output_schema,
        output_ref=output_ref,
        telemetry=telemetry,
        component_versions=component_versions,
    )

    run.state = RunState.SUCCEEDED.value
    run.termination_reason = TerminationReason.COMPLETED.value
    run.evidence_id = evidence_id
    run.ended_at = now
    run.version += 1

    event_id = enqueue_event(
        session,
        tenant_id=tenant_id,
        event_type="inv.run.succeeded",
        aggregate_type="run",
        aggregate_id=run_id,
        payload={"runId": run_id, "evidenceId": evidence_id},
        now=now,
        trace_id=run.trace_id,
    )

    session.flush()
    return run, evidence_id, event_id


def fail_run(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    run_id: str,
    reason: TerminationReason | str,
    now: dt.datetime,
    actor_type: str = "system",
    actor_id: str = "control-plane",
    action: str = "run.fail",
    input_payload: Any = None,
    error_code: str | None = None,
) -> tuple[Run, str]:
    """End a Run as failed, with Evidence for the failure too.

    A failure is as much a thing that happened as a success; recording only
    successes would make the audit trail a highlight reel.
    """
    run = advance(
        session, tenant_id=tenant_id, run_id=run_id, target=RunState.FAILED,
        now=now, reason=reason,
    )
    evidence_id = record_evidence(
        session,
        tenant_id=tenant_id,
        run_id=run_id,
        action=action,
        actor_type=actor_type,
        actor_id=actor_id,
        input_schema="RunFailure@1",
        input_payload=input_payload if input_payload is not None else {"runId": run_id},
        result="failed",
        now=now,
        trace_id=run.trace_id,
        telemetry={"errorCode": error_code} if error_code else None,
    )
    enqueue_event(
        session,
        tenant_id=tenant_id,
        event_type="inv.run.failed",
        aggregate_type="run",
        aggregate_id=run_id,
        payload={
            "runId": run_id,
            "reason": run.termination_reason,
            "errorCode": error_code,
        },
        now=now,
        trace_id=run.trace_id,
    )
    session.flush()
    return run, evidence_id


def record_approval(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    run_id: str,
    decision: str,
    risk_level: int,
    decided_by_user_id: str,
    now: dt.datetime,
    expires_at: dt.datetime,
    scope: dict[str, Any] | None = None,
    note: str | None = None,
) -> Approval:
    """Record a human decision, bound to the exact spec it was made against.

    The digest comes from the workload rather than from the caller, so an
    approval cannot be recorded against content the approver never saw.
    """
    run = get_run(session, tenant_id=tenant_id, run_id=run_id)
    workload = session.get(Workload, run.workload_id)
    if decision not in ("approved", "rejected"):
        raise InvError(VAL_SCHEMA, f"unknown decision: {decision!r}")
    if not 0 <= risk_level <= 3:
        raise InvError(VAL_SCHEMA, "risk_level must be L0..L3")
    if expires_at <= now:
        raise InvError(VAL_SCHEMA, "an approval must expire in the future")

    approval = Approval(
        approval_id=new_id("approval"),
        tenant_id=tenant_id,
        run_id=run_id,
        subject_sha256=workload.spec_sha256,
        decision=decision,
        risk_level=risk_level,
        scope=scope or {},
        decided_by_user_id=decided_by_user_id,
        decided_at=now,
        expires_at=expires_at,
        note=note,
    )
    session.add(approval)
    session.flush()
    return approval


def assert_approval_valid(
    session: Session, *, tenant_id: uuid.UUID, run_id: str, now: dt.datetime
) -> Approval:
    """Check that a live approval covers the workload as it stands now.

    Two ways this fails, and they are different problems: the approval has
    expired, or the spec changed after it was given. The second is the one that
    matters — reusing an approval for edited content is exactly what the ADR
    forbids.
    """
    run = get_run(session, tenant_id=tenant_id, run_id=run_id)
    workload = session.get(Workload, run.workload_id)
    approval = session.scalars(
        select(Approval)
        .where(
            Approval.tenant_id == tenant_id,
            Approval.run_id == run_id,
            Approval.decision == "approved",
        )
        .order_by(Approval.decided_at.desc())
        .limit(1)
    ).one_or_none()

    if approval is None:
        raise InvError(
            AUTH_APPROVAL_DIGEST_MISMATCH, "no approval recorded for this run",
            cause_ref=run_id,
        )
    if approval.expires_at <= now:
        raise InvError(
            AUTH_APPROVAL_EXPIRED, "the approval has expired", cause_ref=approval.approval_id
        )
    if approval.subject_sha256 != workload.spec_sha256:
        raise InvError(
            AUTH_APPROVAL_DIGEST_MISMATCH,
            "the workload changed after it was approved",
            cause_ref=approval.approval_id,
        )
    return approval


def list_runs(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    workspace_id: str | None = None,
    state: str | None = None,
    limit: int | None = None,
    cursor: str | None = None,
    default_limit: int = 50,
    max_limit: int = 200,
) -> Page:
    effective = clamp_limit(limit, default=default_limit, maximum=max_limit)
    after = validate_cursor(cursor)
    query = select(Run).where(Run.tenant_id == tenant_id)
    if workspace_id is not None:
        query = query.where(Run.workspace_id == workspace_id)
    if state is not None:
        query = query.where(Run.state == state)
    if after is not None:
        query = query.where(Run.run_id > after)
    rows = session.scalars(query.order_by(Run.run_id).limit(effective + 1)).all()
    return build_page(rows, limit=effective, id_attr="run_id")


def list_steps(session: Session, *, tenant_id: uuid.UUID, attempt_id: str) -> list[Step]:
    return list(
        session.scalars(
            select(Step)
            .where(Step.tenant_id == tenant_id, Step.attempt_id == attempt_id)
            .order_by(Step.ordinal)
        ).all()
    )


def workload_digest(spec: dict[str, Any]) -> str:
    """The digest an approval binds to."""
    return canonical_sha256(spec)
