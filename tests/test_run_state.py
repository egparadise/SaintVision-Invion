"""The Run state machine (ADR-001), without a database.

Pinned here because every later sprint reads these rules, and a quietly added
twelfth state or a missing cancel edge would not show up as a test failure
anywhere else.
"""

from __future__ import annotations

import pytest

from saintvision.errors import InvError
from saintvision.runs.state import (
    ALL_STATES,
    TERMINAL_STATES,
    TRANSITIONS,
    RunState,
    TerminationReason,
    assert_transition,
    can_transition,
    is_terminal,
    reachable_from,
    sql_check_constraint,
)

NON_TERMINAL = [s for s in RunState if s not in TERMINAL_STATES]


def test_there_are_exactly_the_eleven_states():
    assert len(ALL_STATES) == 11
    assert set(ALL_STATES) == {
        "draft",
        "validated",
        "planned",
        "awaiting_approval",
        "scheduled",
        "running",
        "verifying",
        "recovering",
        "succeeded",
        "failed",
        "cancelled",
    }


def test_terminal_states_are_the_three_endings():
    assert {s.value for s in TERMINAL_STATES} == {"succeeded", "failed", "cancelled"}


@pytest.mark.parametrize("state", NON_TERMINAL, ids=lambda s: s.value)
def test_every_non_terminal_state_can_be_cancelled(state):
    """ADR-001: there is no state a user is stuck in."""
    assert RunState.CANCELLED in reachable_from(state)


@pytest.mark.parametrize("state", NON_TERMINAL, ids=lambda s: s.value)
def test_every_non_terminal_state_can_fail(state):
    """Policy refusal, exhausted budget or an unrecoverable error can end a run
    from wherever it is."""
    assert RunState.FAILED in reachable_from(state)


@pytest.mark.parametrize("state", sorted(TERMINAL_STATES, key=lambda s: s.value), ids=lambda s: s.value)
def test_terminal_states_go_nowhere(state):
    assert reachable_from(state) == frozenset()
    assert is_terminal(state)


def test_failed_run_is_terminal_and_cannot_enter_a_retry_transition():
    """A retry feature must change this contract deliberately, not appear silently."""
    assert is_terminal(RunState.FAILED)
    assert reachable_from(RunState.FAILED) == frozenset()
    for retry_target in (RunState.SCHEDULED, RunState.RUNNING, RunState.RECOVERING):
        assert not can_transition(RunState.FAILED, retry_target)
        with pytest.raises(InvError, match="not a legal transition"):
            assert_transition(RunState.FAILED, retry_target)


def test_the_happy_path_is_walkable():
    path = [
        RunState.DRAFT,
        RunState.VALIDATED,
        RunState.PLANNED,
        RunState.SCHEDULED,
        RunState.RUNNING,
        RunState.VERIFYING,
    ]
    for source, target in zip(path, path[1:]):
        assert can_transition(source, target), f"{source} -> {target}"


def test_the_approval_path_is_walkable():
    assert can_transition(RunState.PLANNED, RunState.AWAITING_APPROVAL)
    assert can_transition(RunState.AWAITING_APPROVAL, RunState.SCHEDULED)


def test_recovery_returns_through_scheduled_not_straight_to_running():
    """A retry is re-placed, not resumed in place: it needs a fresh lease."""
    assert can_transition(RunState.RUNNING, RunState.RECOVERING)
    assert can_transition(RunState.VERIFYING, RunState.RECOVERING)
    assert can_transition(RunState.RECOVERING, RunState.SCHEDULED)
    assert not can_transition(RunState.RECOVERING, RunState.RUNNING)


@pytest.mark.parametrize(
    "source,target",
    [
        ("draft", "running"),
        ("draft", "succeeded"),
        ("scheduled", "verifying"),
        ("planned", "running"),
        ("succeeded", "running"),
        ("failed", "scheduled"),
        ("cancelled", "running"),
        ("running", "scheduled"),
    ],
)
def test_illegal_transitions_are_refused(source, target):
    with pytest.raises(InvError) as caught:
        assert_transition(source, target, reason="completed" if target in
                          ("succeeded",) else None)
    assert caught.value.code == "GRAPH-INVALID-TRANSITION"


def test_success_cannot_be_reached_through_the_plain_transition_check():
    """The Evidence invariant is not expressible here, so this refuses to
    approve the move and points at complete_run (ADR-008)."""
    with pytest.raises(InvError) as caught:
        assert_transition("verifying", "succeeded", reason="completed")
    assert caught.value.code == "GRAPH-INVALID-TRANSITION"
    assert "complete_run" in caught.value.message


def test_a_terminal_state_requires_a_reason():
    with pytest.raises(InvError):
        assert_transition("running", "failed")
    assert assert_transition("running", "failed", reason="timeout") is RunState.FAILED


def test_a_non_terminal_state_refuses_a_reason():
    with pytest.raises(InvError):
        assert_transition("draft", "validated", reason="completed")


@pytest.mark.parametrize(
    "state,reason,allowed",
    [
        ("failed", "timeout", True),
        ("failed", "node_lost", True),
        ("failed", "verify_failed", True),
        ("failed", "budget_exhausted", True),
        ("cancelled", "cancelled_by_user", True),
        ("cancelled", "approval_expired", True),
        # A run does not succeed because it timed out, and it is not cancelled
        # because verification failed.
        ("failed", "completed", False),
        ("cancelled", "timeout", False),
    ],
)
def test_reasons_must_match_the_ending(state, reason, allowed):
    if allowed:
        assert assert_transition("running", state, reason=reason)
    else:
        with pytest.raises(InvError):
            assert_transition("running", state, reason=reason)


def test_timeout_and_lost_are_reasons_not_states():
    """ADR-001 is explicit: they are how a run ended, not where it is."""
    assert "timeout" not in ALL_STATES
    assert "lost" not in ALL_STATES
    assert TerminationReason.TIMEOUT.value == "timeout"
    assert TerminationReason.NODE_LOST.value == "node_lost"


def test_check_constraint_lists_every_state():
    rendered = sql_check_constraint()
    for state in ALL_STATES:
        assert f"'{state}'" in rendered
    assert rendered.startswith("state IN (")


def test_the_graph_has_no_unreachable_state():
    """Every state is reachable from draft, or it is dead code in a contract."""
    seen = {RunState.DRAFT}
    frontier = [RunState.DRAFT]
    while frontier:
        current = frontier.pop()
        for nxt in TRANSITIONS[current]:
            if nxt not in seen:
                seen.add(nxt)
                frontier.append(nxt)
    # succeeded is reachable only through complete_run, which bypasses
    # assert_transition, so it is added explicitly rather than left looking
    # unreachable.
    assert seen | {RunState.SUCCEEDED} == set(RunState)
