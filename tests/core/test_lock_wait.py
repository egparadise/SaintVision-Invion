"""The lane's one lock-wait bound (card 84): what it sets, what it answers, where it is used.

PG-free. Whether PostgreSQL actually refuses a held lock within the budget
is ``tests/integration/test_lock_wait_real_pg.py``.
"""

from __future__ import annotations

import inspect

import pytest
from sqlalchemy.exc import OperationalError

from saintvision.api import lock_wait
from saintvision.api.lock_wait import (
    LOCK_WAIT_DETAIL,
    MAX_LOCK_TIMEOUT_MS,
    MIN_LOCK_TIMEOUT_MS,
    bound_lock_wait,
    bounded_lock_wait,
    lock_wait_problem,
    validate_lock_timeout,
)
from saintvision.api.problem import CanonicalProblem
from saintvision.api.v1 import conformance_status, eval_runs, model_release, model_retention, model_verify, model_versions, run_seal
from saintvision.config import Settings


class _Session:
    def __init__(self):
        self.statements: list[str] = []

    def execute(self, statement, params=None):
        self.statements.append(str(statement))


def _operational(sqlstate):
    class Orig(Exception):
        pass

    orig = Orig("locked")
    orig.sqlstate = sqlstate
    return OperationalError("SELECT ... FOR UPDATE", {}, orig)


# ---------------------------------------------------------------- the budget


@pytest.mark.parametrize("value", [1, 250, 5_000, MAX_LOCK_TIMEOUT_MS])
def test_a_budget_within_bounds_is_accepted(value):
    assert validate_lock_timeout(value) == value


@pytest.mark.parametrize("value", [0, -1, MIN_LOCK_TIMEOUT_MS - 1, MAX_LOCK_TIMEOUT_MS + 1, True, False, "5000", 5.0, None])
def test_a_budget_that_is_not_a_positive_integer_within_bounds_is_refused(value):
    with pytest.raises(ValueError):
        validate_lock_timeout(value)


def test_settings_refuse_a_nonsensical_budget_at_construction():
    for bad in (0, -5, MAX_LOCK_TIMEOUT_MS + 1, True):
        with pytest.raises(ValueError):
            Settings(database_url="unused", business_lock_timeout_ms=bad)
    assert Settings(database_url="unused").business_lock_timeout_ms == 5_000


def test_the_default_budget_is_five_seconds_and_from_env_validates(monkeypatch):
    monkeypatch.setenv("INV_DATABASE_URL", "postgresql://unused")
    monkeypatch.setenv("INV_BUSINESS_LOCK_TIMEOUT_MS", "0")
    with pytest.raises(ValueError):
        Settings.from_env()
    monkeypatch.setenv("INV_BUSINESS_LOCK_TIMEOUT_MS", "750")
    assert Settings.from_env().business_lock_timeout_ms == 750


# ---------------------------------------------------------------- the SET LOCAL


def test_bound_lock_wait_sets_a_local_lock_timeout_for_the_transaction():
    session = _Session()
    bound_lock_wait(session, timeout_ms=250)
    assert session.statements == ["SET LOCAL lock_timeout = '250ms'"]


def test_bound_lock_wait_refuses_before_issuing_anything_for_a_bad_budget():
    session = _Session()
    with pytest.raises(ValueError):
        bound_lock_wait(session, timeout_ms=0)
    assert session.statements == []


# ---------------------------------------------------------------- the answer


@pytest.mark.parametrize("sqlstate", ["55P03", "40P01"])
def test_a_lock_timeout_or_deadlock_is_the_canonical_retryable_503_with_a_fixed_detail(sqlstate):
    problem = lock_wait_problem(_operational(sqlstate))
    assert isinstance(problem, CanonicalProblem)
    assert (problem.code, problem.status, problem.retryable) == ("SYS-0001", 503, True)
    assert problem.detail == LOCK_WAIT_DETAIL
    assert "55P03" not in problem.detail and "SELECT" not in problem.detail


@pytest.mark.parametrize("sqlstate", ["57P01", "08006", None])
def test_any_other_operational_failure_is_not_a_lock_wait(sqlstate):
    assert lock_wait_problem(_operational(sqlstate)) is None


def test_the_context_manager_sets_the_bound_then_maps_a_wait_and_reraises_anything_else():
    session = _Session()
    with pytest.raises(CanonicalProblem) as raised:
        with bounded_lock_wait(session, timeout_ms=300):
            raise _operational("55P03")
    assert raised.value.status == 503 and raised.value.retryable is True
    assert session.statements == ["SET LOCAL lock_timeout = '300ms'"]

    with pytest.raises(OperationalError):
        with bounded_lock_wait(_Session(), timeout_ms=300):
            raise _operational("57P01")

    with pytest.raises(ValueError):
        with bounded_lock_wait(_Session(), timeout_ms=300):
            raise ValueError("not operational")


# ---------------------------------------------------------------- one helper, every write route


@pytest.mark.parametrize(
    "module", [run_seal, model_retention, model_versions, model_release, model_verify, conformance_status, eval_runs]
)
def test_every_transaction_span_of_every_write_route_is_bounded_and_no_copy_exists(module):
    """Structure, not a substring (Codex #211 F1): each route opens N sessions
    (the permission preflight and the write) and every one of them enters
    ``bounded_lock_wait`` beside its tenant scope; a bare tenant scope is a
    span that could wait forever."""
    import re

    source = inspect.getsource(module)
    spans = source.count("with factory() as session:")
    assert spans >= 2, module.__name__
    assert source.count("bounded_lock_wait(") == spans, module.__name__
    assert not re.search(r"with tenant_scope\(session, principal\.tenant_id\):\n", source), module.__name__
    assert "SET LOCAL lock_timeout = '" not in source, module.__name__  # no private copy of the bound
    assert "55P03" not in source and "40P01" not in source, module.__name__


def test_the_deadline_harness_returns_on_timeout_instead_of_waiting_for_the_blocked_call():
    """Codex #211 F2: a reverted bound must fail the test by its deadline, not
    hang CI on an executor shutdown that waits for the blocked worker."""
    import threading
    import time

    from lock_wait_harness import DeadlineExceeded, within_deadline

    release = threading.Event()
    started = time.monotonic()
    with pytest.raises(DeadlineExceeded):
        within_deadline(release.wait, seconds=0.5)
    assert time.monotonic() - started < 3.0                         # returned promptly, did not join the worker
    release.set()                                                    # let the worker finish
    result, elapsed = within_deadline(lambda: "ok", seconds=5)
    assert result == "ok" and elapsed < 5


def test_statement_timeout_is_a_stated_decision_not_an_omission():
    assert "statement_timeout" in (lock_wait.__doc__ or "")
    assert "SET LOCAL statement_timeout" not in inspect.getsource(lock_wait)
