"""The ``action`` recorded for a denied request: bounded, identifier-free.

``audit_events.action`` is ``VARCHAR(64)`` (0001 baseline). The denial handler
used to record the raw ``METHOD /path``; with prefixed identifiers in the path
(``prj_`` + 26, ``run_`` + 26) a route such as ``GET /v1/projects/{p}/runs/{r}/record``
is 90 characters, so the denial INSERT itself failed and an authentication
failure that should have been a 401 surfaced as a 500 (Codex #184 F3; hosted
run 36386560565: ``StringDataRightTruncation``).

The action is therefore derived from the *matched route*, never from the URL:

* a matched route records ``METHOD template`` when that fits the column,
  where the template carries placeholders (``{project_id}``), never values;
* a matched route whose template is itself too long records
  ``METHOD <name prefix>#<digest>``: the route's registered name cut to the
  budget, plus a fixed-length digest of the template, so two long routes
  never share an action (Codex #189 F2);
* an unmatched path records ``METHOD /unmatched`` -- nothing from the URL,
  because an unmatched path is caller-controlled text.

The method is ASGI scope input too, so it is admitted only as an upper-case
HTTP token and recorded as ``UNKNOWN`` otherwise. Every branch is bounded by
:data:`AUDIT_ACTION_LIMIT`; ``tests/core/test_audit_action.py`` pins every
registered route to fit, to carry no identifier, and to map to a distinct
action.
"""

from __future__ import annotations

import hashlib
import re
from typing import Final

from starlette.requests import Request

#: ``audit_events.action`` column width (0001_s02_baseline).
AUDIT_ACTION_LIMIT: Final[int] = 64

#: Recorded in place of a path that matched no route.
UNMATCHED: Final[str] = "/unmatched"

#: Recorded in place of a method that is not an HTTP token.
UNKNOWN_METHOD: Final[str] = "UNKNOWN"

#: Hex characters of the template digest kept in the long-template form.
TEMPLATE_DIGEST_LENGTH: Final[int] = 12

_METHOD_TOKEN: Final[re.Pattern[str]] = re.compile(r"^[A-Z]{1,16}$")


def audit_action(request: Request) -> str:
    """The bounded, identifier-free action for a denial on ``request``."""
    method = _method(request)
    route = request.scope.get("route")
    template = getattr(route, "path", None)
    if not isinstance(template, str) or not template:
        return f"{method} {UNMATCHED}"
    action = f"{method} {template}"
    if len(action) <= AUDIT_ACTION_LIMIT:
        return action
    return long_template_action(method, template, getattr(route, "name", None))


def long_template_action(method: str, template: str, name: object) -> str:
    """``METHOD <name prefix>#<digest>`` for a template that does not fit.

    The digest is of the template alone, so it depends on nothing the caller
    sent; the name prefix is for the reader, the digest is the identity.
    """
    digest = hashlib.sha256(template.encode("utf-8")).hexdigest()[:TEMPLATE_DIGEST_LENGTH]
    label = name if isinstance(name, str) and name else "route"
    budget = AUDIT_ACTION_LIMIT - len(method) - 1 - 1 - TEMPLATE_DIGEST_LENGTH
    return f"{method} {label[:budget]}#{digest}"


def _method(request: Request) -> str:
    raw = request.scope.get("method")
    if isinstance(raw, str):
        method = raw.upper()
        if _METHOD_TOKEN.fullmatch(method):
            return method
    return UNKNOWN_METHOD
