"""Test-only helpers for exercising the Node delivery uncertainty contract."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from inv.errors import DomainError


def deliver_once_then_observe(
    delivery: Any,
    node: dict[str, Any],
    envelope: dict[str, Any],
    *,
    observation_attempts: int = 3,
    sleeper: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Execute once, then reconcile an uncertain acknowledgement without re-execution.

    ``NODE-0030`` means the caller cannot prove whether the Node accepted the
    command.  Retrying the execution endpoint is therefore unsafe.  The receipt
    endpoint is observation-only and can be retried while the first handler is
    finishing.  Exhaustion remains fail-closed with ``NODE-0030``.
    """

    if observation_attempts < 1:
        raise ValueError("observation_attempts must be positive")

    try:
        return delivery.deliver(node, envelope)
    except DomainError as exc:
        if exc.code != "NODE-0030":
            raise
        last_error = exc

    for attempt in range(observation_attempts):
        try:
            return delivery.deliver(node, envelope, observation_only=True)
        except DomainError as exc:
            if exc.code != "NODE-0030":
                raise
            last_error = exc
            if attempt + 1 < observation_attempts:
                sleeper(0.1 * (attempt + 1))

    raise last_error
