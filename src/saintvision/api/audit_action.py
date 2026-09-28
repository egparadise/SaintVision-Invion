"""The ``action`` recorded for a denied request: bounded, identifier-free.

``audit_events.action`` is ``VARCHAR(64)`` (0001 baseline). The denial handler
used to record the raw ``METHOD /path``; with prefixed identifiers in the path
(``prj_`` + 26, ``run_`` + 26) a route such as ``GET /v1/projects/{p}/runs/{r}/record``
is 90 characters, so the denial INSERT itself failed and an authentication
failure that should have been a 401 surfaced as a 500 (Codex #184 F3).

The action is therefore derived from the *matched route*, never from the URL:

* a matched route records ``METHOD template`` when that fits the column,
  where the template carries placeholders (``{project_id}``), never values;
* a matched route whose template is itself too long records ``METHOD name``
  (the route's registered name, a Python identifier);
* an unmatched path records ``METHOD /unmatched`` -- nothing from the URL,
  because an unmatched path is caller-controlled text.

Every branch is bounded by :data:`AUDIT_ACTION_LIMIT` and every registered
route is pinned to fit by ``tests/core/test_audit_action.py``.
"""

from __future__ import annotations

from typing import Final

from starlette.requests import Request

#: ``audit_events.action`` column width (0001_s02_baseline).
AUDIT_ACTION_LIMIT: Final[int] = 64

#: Recorded in place of a path that matched no route.
UNMATCHED: Final[str] = "/unmatched"


def audit_action(request: Request) -> str:
    """The bounded, identifier-free action for a denial on ``request``."""
    method = request.method.upper()
    route = request.scope.get("route")
    template = getattr(route, "path", None)
    if not isinstance(template, str) or not template:
        return _bounded(f"{method} {UNMATCHED}")
    action = f"{method} {template}"
    if len(action) <= AUDIT_ACTION_LIMIT:
        return action
    name = getattr(route, "name", None)
    if isinstance(name, str) and name:
        return _bounded(f"{method} {name}")
    return _bounded(f"{method} {UNMATCHED}")


def _bounded(action: str) -> str:
    # Reached only by strings that carry no request-controlled text; the cut is
    # a last defence for the column, not a way to fit a path.
    return action[:AUDIT_ACTION_LIMIT]
