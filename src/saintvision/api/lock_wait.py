"""One bound on lock waits for every write in the business lane (G-04 card 84).

Every write route in this lane takes locks it can wait on: the idempotency
advisory lock (``deps.serialise_idempotent_write``), then a resource row
``FOR UPDATE`` (a run, a model version, artifacts). PostgreSQL waits for a
lock without a deadline unless the session says otherwise, so a key or a row
held by a long transaction would hold every later request on it for as long
as it liked. W1 (#201) introduced the bound for its own transaction; this
module is that bound for the whole lane, so no route invents its own and
none is left without one (W2's docstring used to carry the gap as a note).

**What is bounded.** ``SET LOCAL lock_timeout`` for the write transaction
(``Settings.business_lock_timeout_ms``, default 5 s). ``lock_timeout`` applies
to every heavyweight lock acquisition in the transaction -- advisory locks
included -- so the serialisation point and the row locks are covered by the
one setting. Ordinary contention waits and then proceeds on the committed
row; only a wait past the budget is refused.

**What is not.** ``statement_timeout`` is deliberately not set here. It would
cancel a statement that is *working* (a long index scan, a large flush), not
one that is *waiting*, and the lane's writes are short by design; a statement
budget is a separate operational decision with its own failure semantics,
and setting it silently under a lock bound would make a slow statement look
like contention. Stated so it is a decision, not an omission.

**How a refusal is answered.** A lock wait past the budget is SQLSTATE
``55P03`` (``lock_not_available``); a deadlock the server broke is ``40P01``.
Both are answered as ``SYS-0001/503/retryable=true`` with a fixed detail that
carries no value from the database (no key, no id, no SQL), because the
caller can simply retry and nothing about their request was wrong. Any other
operational failure is left to propagate: a broken connection or an outage is
a defect or an incident, and calling it "retry later" would hide it.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Final

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from .problem import SYS_UPSTREAM_UNAVAILABLE, CanonicalProblem

#: PostgreSQL SQLSTATEs answered as a retryable 503 rather than a 500.
LOCK_WAIT_SQLSTATES: Final[frozenset[str]] = frozenset({"55P03", "40P01"})

#: Bounds on the budget: below a millisecond is meaningless, above ten
#: minutes is "unbounded" with extra steps.
MIN_LOCK_TIMEOUT_MS: Final[int] = 1
MAX_LOCK_TIMEOUT_MS: Final[int] = 600_000

#: The one detail a caller sees. Fixed text: nothing from the database.
LOCK_WAIT_DETAIL: Final[str] = "The resource is locked by another request; retry."


def validate_lock_timeout(timeout_ms: object) -> int:
    """The budget as a positive integer within bounds, or ``ValueError``.

    ``bool`` is excluded explicitly: ``True`` is an ``int`` in Python and would
    silently mean "one millisecond".
    """
    if isinstance(timeout_ms, bool) or not isinstance(timeout_ms, int):
        raise ValueError("business_lock_timeout_ms must be an integer number of milliseconds")
    if not MIN_LOCK_TIMEOUT_MS <= timeout_ms <= MAX_LOCK_TIMEOUT_MS:
        raise ValueError(
            f"business_lock_timeout_ms must be between {MIN_LOCK_TIMEOUT_MS} and "
            f"{MAX_LOCK_TIMEOUT_MS}"
        )
    return timeout_ms


def bound_lock_wait(session: Session, *, timeout_ms: int) -> None:
    """``SET LOCAL lock_timeout`` for this transaction only.

    ``SET`` takes no bind parameters, so the value is formatted -- after
    :func:`validate_lock_timeout`, which is what makes the formatting safe.
    """
    value = validate_lock_timeout(timeout_ms)
    session.execute(text(f"SET LOCAL lock_timeout = '{value}ms'"))


def lock_wait_problem(error: OperationalError) -> CanonicalProblem | None:
    """A lock timeout or deadlock as the canonical retryable 503, else ``None``."""
    state = getattr(getattr(error, "orig", None), "sqlstate", None)
    if state in LOCK_WAIT_SQLSTATES:
        return CanonicalProblem(SYS_UPSTREAM_UNAVAILABLE, 503, LOCK_WAIT_DETAIL, retryable=True)
    return None


@contextmanager
def bounded_lock_wait(session: Session, *, timeout_ms: int) -> Iterator[None]:
    """Bound every lock wait in the enclosed block and answer a refusal canonically.

    Use around the whole write transaction body, after ``session.begin()`` and
    the tenant scope: the ``SET LOCAL`` must be inside the transaction, and the
    mapping must see the ``OperationalError`` before the transaction's
    ``__exit__`` turns it into a rollback. Any other ``OperationalError`` is
    re-raised unchanged.
    """
    bound_lock_wait(session, timeout_ms=timeout_ms)
    try:
        yield
    except OperationalError as error:
        problem = lock_wait_problem(error)
        if problem is None:
            raise
        raise problem from None
