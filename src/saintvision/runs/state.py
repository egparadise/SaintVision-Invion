"""The Run state machine.

ADR-001 fixes eleven states and forbids inventing more. This module is the only
place that decides whether a transition is legal, so the API, the services and
the database check constraint all agree by construction.

Three rules from the ADR that are easy to get wrong and are encoded here:

* ``timeout`` and ``lost`` are **termination reasons**, not states. A run that
  times out ends in ``failed`` with ``reason='timeout'``. Adding a state for
  each way of ending is how a state machine becomes unreadable.
* Every non-terminal state can reach ``cancelled``. There is no state a user is
  stuck in.
* ``verifying -> succeeded`` is special: it is legal only when the result and
  the required Evidence are written in the same transaction. That condition
  cannot be expressed here — it belongs to the service — so
  :func:`assert_transition` refuses to approve it on its own and the caller
  must go through :func:`saintvision.services.runs.complete_run`.
"""

from __future__ import annotations

from enum import Enum
from typing import Final

from ..errors import GRAPH_INVALID_TRANSITION, InvError


class RunState(str, Enum):
    DRAFT = "draft"
    VALIDATED = "validated"
    PLANNED = "planned"
    AWAITING_APPROVAL = "awaiting_approval"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    VERIFYING = "verifying"
    RECOVERING = "recovering"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


#: Order matters only for readability; the DB stores the string.
ALL_STATES: Final[tuple[str, ...]] = tuple(s.value for s in RunState)

TERMINAL_STATES: Final[frozenset[RunState]] = frozenset(
    {RunState.SUCCEEDED, RunState.FAILED, RunState.CANCELLED}
)

#: The forward graph, without the universal cancel and fail edges which are
#: added below. Keeping them separate makes the table readable: these are the
#: transitions that represent progress.
_FORWARD: Final[dict[RunState, frozenset[RunState]]] = {
    RunState.DRAFT: frozenset({RunState.VALIDATED}),
    RunState.VALIDATED: frozenset({RunState.PLANNED}),
    RunState.PLANNED: frozenset({RunState.AWAITING_APPROVAL, RunState.SCHEDULED}),
    RunState.AWAITING_APPROVAL: frozenset({RunState.SCHEDULED}),
    RunState.SCHEDULED: frozenset({RunState.RUNNING}),
    RunState.RUNNING: frozenset({RunState.VERIFYING, RunState.RECOVERING}),
    RunState.VERIFYING: frozenset({RunState.SUCCEEDED, RunState.RECOVERING}),
    RunState.RECOVERING: frozenset({RunState.SCHEDULED}),
    RunState.SUCCEEDED: frozenset(),
    RunState.FAILED: frozenset(),
    RunState.CANCELLED: frozenset(),
}


def _build() -> dict[RunState, frozenset[RunState]]:
    graph: dict[RunState, frozenset[RunState]] = {}
    for state, forward in _FORWARD.items():
        if state in TERMINAL_STATES:
            graph[state] = frozenset()
            continue
        # Cancellation is reachable from every non-terminal state, and a
        # verification failure, a policy refusal or an exhausted budget can end
        # a run from wherever it currently is (ADR-001).
        graph[state] = forward | {RunState.CANCELLED, RunState.FAILED}
    return graph


TRANSITIONS: Final[dict[RunState, frozenset[RunState]]] = _build()


class TerminationReason(str, Enum):
    """Why a run ended. Never a state (ADR-001)."""

    COMPLETED = "completed"
    VERIFY_FAILED = "verify_failed"
    POLICY_DENIED = "policy_denied"
    BUDGET_EXHAUSTED = "budget_exhausted"
    TIMEOUT = "timeout"
    NODE_LOST = "node_lost"
    CANCELLED_BY_USER = "cancelled_by_user"
    APPROVAL_EXPIRED = "approval_expired"
    UNRECOVERABLE_ERROR = "unrecoverable_error"


ALL_REASONS: Final[tuple[str, ...]] = tuple(r.value for r in TerminationReason)

#: Which reasons may accompany which terminal state. A run cannot be
#: ``succeeded`` because it timed out.
_REASONS_FOR: Final[dict[RunState, frozenset[TerminationReason]]] = {
    RunState.SUCCEEDED: frozenset({TerminationReason.COMPLETED}),
    RunState.FAILED: frozenset(
        {
            TerminationReason.VERIFY_FAILED,
            TerminationReason.POLICY_DENIED,
            TerminationReason.BUDGET_EXHAUSTED,
            TerminationReason.TIMEOUT,
            TerminationReason.NODE_LOST,
            TerminationReason.UNRECOVERABLE_ERROR,
        }
    ),
    RunState.CANCELLED: frozenset(
        {TerminationReason.CANCELLED_BY_USER, TerminationReason.APPROVAL_EXPIRED}
    ),
}


def is_terminal(state: RunState | str) -> bool:
    return RunState(state) in TERMINAL_STATES


def can_transition(current: RunState | str, target: RunState | str) -> bool:
    return RunState(target) in TRANSITIONS[RunState(current)]


def assert_transition(
    current: RunState | str,
    target: RunState | str,
    *,
    reason: TerminationReason | str | None = None,
    run_id: str | None = None,
) -> RunState:
    """Validate a transition, or raise ``GRAPH-INVALID-TRANSITION``.

    ``verifying -> succeeded`` is rejected here on purpose: success requires
    Evidence in the same transaction (ADR-008), which this function cannot
    observe. Only ``services.runs.complete_run`` may make that move.
    """
    source, destination = RunState(current), RunState(target)

    if source is RunState.VERIFYING and destination is RunState.SUCCEEDED:
        raise InvError(
            GRAPH_INVALID_TRANSITION,
            "verifying -> succeeded must go through complete_run so that the "
            "result and its Evidence commit together",
            cause_ref=run_id,
        )

    if destination not in TRANSITIONS[source]:
        raise InvError(
            GRAPH_INVALID_TRANSITION,
            f"{source.value} -> {destination.value} is not a legal transition",
            cause_ref=run_id,
            extra={"from": source.value, "to": destination.value},
        )

    _assert_reason(destination, reason, run_id=run_id)
    return destination


def _assert_reason(
    destination: RunState,
    reason: TerminationReason | str | None,
    *,
    run_id: str | None,
) -> None:
    if destination not in TERMINAL_STATES:
        if reason is not None:
            raise InvError(
                GRAPH_INVALID_TRANSITION,
                "a termination reason is only meaningful on a terminal state",
                cause_ref=run_id,
            )
        return
    if reason is None:
        raise InvError(
            GRAPH_INVALID_TRANSITION,
            f"{destination.value} requires a termination reason",
            cause_ref=run_id,
        )
    value = TerminationReason(reason)
    if value not in _REASONS_FOR[destination]:
        raise InvError(
            GRAPH_INVALID_TRANSITION,
            f"{value.value} cannot terminate a run as {destination.value}",
            cause_ref=run_id,
            extra={"state": destination.value, "reason": value.value},
        )


def reachable_from(state: RunState | str) -> frozenset[RunState]:
    """States reachable in one step. Used by the API to advertise options."""
    return TRANSITIONS[RunState(state)]


def sql_check_constraint(column: str = "state") -> str:
    """Render the CHECK constraint so the DB and this module cannot diverge."""
    values = ",".join(f"'{s}'" for s in ALL_STATES)
    return f"{column} IN ({values})"
