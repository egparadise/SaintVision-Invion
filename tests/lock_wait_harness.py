"""Deadline harness for lock-wait tests: a blocked call fails the test, it never hangs it.

``ThreadPoolExecutor`` used as a context manager calls ``shutdown(wait=True)``
on exit, so a call that is blocked on a lock the test holds would make the
test's own timeout wait on the lock it is supposed to release afterwards
(Codex #211 F2). The executor here is managed by hand: on timeout it is shut
down without waiting and with pending futures cancelled, the ``TimeoutError``
propagates, and the caller's ``finally`` releases the lock -- after which the
blocked thread finishes on its own and the interpreter can exit.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from typing import Callable, TypeVar

T = TypeVar("T")


class DeadlineExceeded(AssertionError):
    """The call did not return within the deadline (a reverted bound waits forever)."""


def within_deadline(call: Callable[[], T], *, seconds: float) -> tuple[T, float]:
    """Run ``call`` on a worker thread and return ``(result, elapsed)``.

    Raises :class:`DeadlineExceeded` after ``seconds`` **without** waiting for
    the worker: the executor is released with ``wait=False`` so the thread is
    left to finish when whatever blocks it is released by the caller.
    """
    started = time.monotonic()
    pool = ThreadPoolExecutor(max_workers=1)
    future = pool.submit(call)
    try:
        result = future.result(timeout=seconds)
    except FutureTimeout:
        pool.shutdown(wait=False, cancel_futures=True)
        raise DeadlineExceeded(f"the call did not return within {seconds}s") from None
    pool.shutdown(wait=False)
    return result, time.monotonic() - started
