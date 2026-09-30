"""PG-free mutation guards for the canonical core Run cancellation audit."""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace
import uuid

import pytest

from saintvision.runs.state import RunState, TerminationReason
from saintvision.services import runs as run_service


NOW = dt.datetime(2026, 9, 30, 3, 0, 0, tzinfo=dt.timezone.utc)
TENANT = uuid.UUID("11111111-1111-4111-8111-111111111111")
RUN_ID = "run_01KERNELCANCELAUDIT00000000"
USER_ID = "usr_01KERNELCANCELAUDIT00000000"
TRACE_ID = "a" * 32


def test_first_cancel_records_one_exact_audit_in_the_same_session(monkeypatch):
    session = object()
    current = SimpleNamespace(state=RunState.DRAFT.value)
    cancelled = SimpleNamespace(state=RunState.CANCELLED.value)
    calls: list[tuple[str, object, dict]] = []

    def get_run(*_args, **kwargs):
        assert kwargs["for_update"] is True
        return current

    monkeypatch.setattr(run_service, "get_run", get_run)

    def advance(received_session, received_run, **kwargs):
        assert received_run is current
        calls.append(("advance", received_session, kwargs))
        return cancelled

    def record_event(received_session, **kwargs):
        calls.append(("audit", received_session, kwargs))
        return "audit_event_01KERNELCANCELAUDIT"

    monkeypatch.setattr(run_service, "_advance_locked_run", advance)
    monkeypatch.setattr(run_service, "record_event", record_event)

    result = run_service.cancel_run(
        session,
        tenant_id=TENANT,
        run_id=RUN_ID,
        now=NOW,
        actor_type="user",
        actor_id=USER_ID,
        trace_id=TRACE_ID,
    )

    assert result is cancelled
    assert [call[0] for call in calls] == ["advance", "audit"]
    assert calls[0][1] is calls[1][1] is session
    audit = calls[1][2]
    assert audit == {
        "now": NOW,
        "actor_type": "user",
        "actor_id": USER_ID,
        "action": "run.cancel.requested",
        "outcome": "allow",
        "tenant_id": TENANT,
        "trace_id": TRACE_ID,
        "target_type": "run",
        "target_id": RUN_ID,
        "detail": {"reason": TerminationReason.CANCELLED_BY_USER.value},
    }


def test_cancel_replay_does_not_advance_or_duplicate_audit(monkeypatch):
    cancelled = SimpleNamespace(state=RunState.CANCELLED.value)
    monkeypatch.setattr(run_service, "get_run", lambda *_args, **_kwargs: cancelled)
    monkeypatch.setattr(
        run_service,
        "_advance_locked_run",
        lambda *_args, **_kwargs: pytest.fail("cancel replay advanced state"),
    )
    monkeypatch.setattr(
        run_service,
        "record_event",
        lambda *_args, **_kwargs: pytest.fail("cancel replay duplicated audit"),
    )

    assert (
        run_service.cancel_run(
            object(),
            tenant_id=TENANT,
            run_id=RUN_ID,
            now=NOW,
            actor_type="user",
            actor_id=USER_ID,
        )
        is cancelled
    )


@pytest.mark.parametrize(
    ("actor_type", "actor_id"),
    (("anonymous", None), ("anonymous", USER_ID), ("user", None), ("unknown", USER_ID)),
)
def test_cancel_rejects_unattributed_or_unsupported_actors_before_mutation(
    monkeypatch, actor_type, actor_id
):
    monkeypatch.setattr(
        run_service,
        "get_run",
        lambda *_args, **_kwargs: pytest.fail("invalid actor reached the run"),
    )
    with pytest.raises(ValueError):
        run_service.cancel_run(
            object(),
            tenant_id=TENANT,
            run_id=RUN_ID,
            now=NOW,
            actor_type=actor_type,
            actor_id=actor_id,
        )


def test_audit_failure_is_not_swallowed(monkeypatch):
    current = SimpleNamespace(state=RunState.DRAFT.value)
    cancelled = SimpleNamespace(state=RunState.CANCELLED.value)
    monkeypatch.setattr(run_service, "get_run", lambda *_args, **_kwargs: current)
    monkeypatch.setattr(run_service, "_advance_locked_run", lambda *_args, **_kwargs: cancelled)

    def fail_audit(*_args, **_kwargs):
        raise RuntimeError("audit insert failed")

    monkeypatch.setattr(run_service, "record_event", fail_audit)
    with pytest.raises(RuntimeError, match="audit insert failed"):
        run_service.cancel_run(
            object(),
            tenant_id=TENANT,
            run_id=RUN_ID,
            now=NOW,
            actor_type="system",
            actor_id=None,
        )
