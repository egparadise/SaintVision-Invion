"""The one place a refused request becomes an audit row (card 266).

This used to be a closure inside ``create_app``, which was fine while the core
app was the only app with handlers. The kernel's own handlers write **no** audit
row at all -- ``inv/app.py``'s ``problem()`` builds a ``ProblemDetails`` response
and stops -- so a kernel route that must be audited had two options: duplicate
the rule there, or share this one. Duplicating puts ``DENIAL_CATEGORIES``, the
bounded-action rule and the verified-credential rule in two files, and one of
them gets fixed alone. So it moved here, and both apps' handlers call it.

Three rules travel with it, unchanged from where it was born:

* **the actor comes only from what the request already proved.** ``get_principal``
  pins ``actor_type``/``actor_id``/``tenant_id`` on ``request.state`` for a
  *verified* credential; nothing is parsed again from the header or the body, so
  an unauthenticated request is ``anonymous`` with no tenant.
* **no route records a denial itself.** A route is inside a transaction that the
  refusal rolls back, and per-route recording drifts. The write happens out of
  band, in its own transaction, so the rollback cannot erase it.
* **fail-closed.** If the write fails the exception propagates and the request
  ends as a generic 500 with nothing privileged done. An audit failure is never
  disguised as a successful refusal.

``writer`` and ``action_for`` are parameters with the real defaults rather than
hard references, so each app's handler passes the names it resolves at call time
and the existing test seams keep working. The *rule* still lives only here; only
the two collaborators are injectable.
"""

from __future__ import annotations

import datetime as dt
from typing import Callable

from fastapi import Request
from sqlalchemy import Engine

from ..ids import is_id
from ..services.audit import record_denial_out_of_band
from .audit_action import audit_action

#: Denial categories that are audited (AC-02). An ``AUTH``/``SEC`` refusal is a
#: decision about this caller and is recorded; a ``RES`` 404 is an absence and a
#: ``GRAPH``/``SYS`` answer is a state, and neither is a denial. Keeping the set
#: here is the point: it must not come to mean two different things in two apps.
DENIAL_CATEGORIES = ("AUTH", "SEC")


def record_denial(
    engine: Engine,
    request: Request,
    *,
    code: str,
    trace_id: str | None,
    now: Callable[[], dt.datetime],
    writer: Callable[..., None] = record_denial_out_of_band,
    action_for: Callable[[Request], str] = audit_action,
) -> None:
    """Record one denial, out of band, from what the request already proved.

    ``action`` is the bounded, identifier-free ``audit_action`` (#189) unless the
    route declared its own on ``request.state.denial_action`` -- a route whose
    template exceeds the column takes the name-and-digest form instead, and
    either way it carries no project, model or approval id.

    The project target is the path's ``project_id`` only when it is a well-formed
    project id; caller text that is not one is recorded nowhere. The tenant is
    always the caller's, never the project's. ``detail`` is empty because every
    value belongs in its own column.
    """
    declared = getattr(request.state, "denial_action", None)
    project_id = request.path_params.get("project_id")
    target = ("project", project_id) if is_id(project_id, "project") else (None, None)
    writer(
        engine,
        now=now(),
        actor_type=getattr(request.state, "actor_type", "anonymous"),
        actor_id=getattr(request.state, "actor_id", None),
        action=declared if isinstance(declared, str) and declared else action_for(request),
        outcome="deny",
        tenant_id=getattr(request.state, "tenant_id", None),
        reason_code=code,
        trace_id=trace_id,
        target_type=target[0],
        target_id=target[1],
        detail={},
        source_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


def is_denial(category: str) -> bool:
    """Whether a canonical category is one AC-02 asks to be recorded.

    Called instead of comparing against the tuple at each handler, so a handler
    cannot accidentally widen the set for itself.
    """
    return category in DENIAL_CATEGORIES
