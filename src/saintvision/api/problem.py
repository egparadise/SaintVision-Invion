"""Canonical ``ProblemDetails`` for new business routes, and the strict body reader.

Two things live here, and they are shared on purpose (VF-CL-03 design v1.3 §7):
the canonical error surface and the request-body boundary that feeds it.

**Why this is not ``InvError``.** The business error type cannot produce a
canonical body, in six separate ways measured against
``contracts/v1alpha1/core.schema.json::$defs.ProblemDetails``:

* ``errors.category_of()`` admits ten prefixes, so ``MODEL-0009`` and
  ``SYS-0002`` raise ``ValueError`` at construction;
* ``InvError.to_problem()`` emits ``type: "https://saintvision.invenio/..."``
  where the schema pins ``const: "about:blank"``;
* ``api.app._problem`` adds ``instance``, which the schema does not define and
  ``additionalProperties: false`` therefore rejects;
* ``detail`` is emitted only when ``public`` is true, although it is required;
* ``problem.update(self.extra)`` lifts arbitrary keys to the top level;
* ``RES`` defaults to 409 and ``retryable`` true, while ``RES-0004`` must be 404
  and false.

The canonical side blocks none of it -- ``category`` is ``^[A-Z]+$`` and the
kernel already serves ``MODEL-0001``..``MODEL-0008`` and ``SYS-0001`` through
``inv.app.problem``, which validates. So the fix is a separate exception whose
status and retryability are stated per code rather than derived from a category
table, validated against the same anchor the kernel uses.

**Existing errors are normally translated at the route boundary.** The same
``VAL-SCHEMA`` means a state precondition inside ``release_model_version`` and a
malformed digest on the lineage read routes, so each route passes its own table
and a code outside that table becomes ``SYS-0002`` rather than being dressed up
as something it is not. The one application-boundary exception is the closed
set of old ``*-NOT-FOUND`` codes below: each always means absent or
permission-masked and maps to the same non-disclosing ``RES-0004``. ``SYS-0001``
is deliberately not reused for an unmapped code: our own ledger records a
defect where an internal misclassification surfaced as 503, which made clients
retry and paged operators.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ..errors import (
    RES_ARTIFACT_NOT_FOUND,
    RES_CONTRIBUTION_NOT_FOUND,
    RES_NODE_NOT_FOUND,
    RES_RUN_NOT_FOUND,
    RES_WORKSPACE_NOT_FOUND,
    InvError,
)
from ..ids import new_trace_id

#: Exactly the canonical required key set. The body is built from this tuple so
#: a key cannot be added by accident, and the order is the schema's order.
CANONICAL_KEYS: tuple[str, ...] = (
    "type",
    "title",
    "status",
    "code",
    "category",
    "detail",
    "retryable",
    "traceId",
    "causeRef",
    "evidenceId",
)

PROBLEM_CONTENT_TYPE = "application/problem+json"
PROBLEM_TYPE = "about:blank"

_CODE = re.compile(r"^[A-Z]+-[0-9]{4}$")
_CATEGORY = re.compile(r"^[A-Z]+$")

#: The declared maximum for a request body on these routes. The kernel's 64 KiB
#: is a global ceiling for every kernel route; a body of two schema-bounded
#: strings is roughly 300 bytes, so the explicit bound here is much smaller.
#: Pre-registered from the schema, not measured.
MAX_REQUEST_BYTES: int = 8192

#: The only media type these routes accept. Parameters are ignored, so
#: ``application/json; charset=utf-8`` is accepted -- a deliberate difference
#: from the kernel's exact byte comparison, because these routes are called by
#: importers and people rather than by our own agents.
JSON_MEDIA_TYPE = "application/json"

#: Codes this module emits on its own behalf.
VAL_REQUEST = "VAL-0003"
AUTH_PROJECT = "AUTH-0030"
RES_NOT_FOUND = "RES-0004"
GRAPH_PRECONDITION = "GRAPH-0002"
#: State the caller described has moved: a digest, an expiry, a slot or a reference
#: binding is no longer what the request was built against. 409 and not retryable --
#: the same request cannot succeed, because what it refers to has changed (#282 §7).
GRAPH_STATE_DRIFT = "GRAPH-0003"
SYS_UPSTREAM_UNAVAILABLE = "SYS-0001"
SYS_UNMAPPED = "SYS-0002"
#: A deployed feature is registered but its operator-controlled prerequisites
#: are not bound.  Retrying the same request cannot repair deployment state.
SYS_PREREQUISITES_UNAVAILABLE = "SYS-0003"

# These historical service codes have one unambiguous public meaning: the
# named resource is absent or intentionally hidden from this caller. Other
# legacy codes remain route-local because their meaning can vary by operation.
LEGACY_NOT_FOUND_CODES: frozenset[str] = frozenset(
    {
        RES_NODE_NOT_FOUND,
        RES_CONTRIBUTION_NOT_FOUND,
        RES_RUN_NOT_FOUND,
        RES_WORKSPACE_NOT_FOUND,
        RES_ARTIFACT_NOT_FOUND,
    }
)


@dataclass(slots=True)
class CanonicalProblem(Exception):
    """A failure whose wire form is the canonical ``ProblemDetails``.

    ``detail`` is always present because the schema requires it, and it is the
    caller-visible string: nothing internal may be passed in. ``status`` and
    ``retryable`` are explicit rather than derived, because the category
    defaults in ``errors.py`` are wrong for several of these codes.
    """

    code: str
    status: int
    detail: str
    retryable: bool = False
    cause_ref: str | None = None
    evidence_id: str | None = None
    #: An action name for the denial audit, when this refusal is one a route's contract
    #: names. ``None`` keeps the generic ``METHOD <template>`` action. It exists so a
    #: contract that requires a specific audited action -- #282 §8's
    #: ``release.acceptance.denied`` -- gets it **without** a route writing its own audit
    #: row: the single audit point stays the shared handler, which is the rule
    #: ``app._record_denial`` is built on, and a per-route write would be a second row for
    #: one refusal.
    audit_action: str | None = None
    category: str = field(init=False)

    def __post_init__(self) -> None:
        if not _CODE.match(self.code):
            raise ValueError(f"error code {self.code!r} is not canonical")
        self.category = self.code.split("-", 1)[0]
        if not _CATEGORY.match(self.category):  # pragma: no cover - implied by _CODE
            raise ValueError(f"error category {self.category!r} is not canonical")
        if not (400 <= self.status <= 599):
            raise ValueError(f"status {self.status} is not an error status")
        if not self.detail:
            raise ValueError("detail is required by the canonical schema")
        Exception.__init__(self, self.detail)

    def body(self, *, trace_id: str) -> dict[str, Any]:
        """The canonical body, validated against the contract before it is sent.

        The same anchor the kernel uses (``inv.contracts.validate_contract``),
        so the two surfaces cannot drift: a body this project would reject from
        the kernel is also rejected here.
        """
        from inv.contracts import validate_contract

        values: dict[str, Any] = {
            "type": PROBLEM_TYPE,
            "title": self.code,
            "status": self.status,
            "code": self.code,
            "category": self.category,
            "detail": self.detail[:1000],
            "retryable": self.retryable,
            "traceId": trace_id,
            "causeRef": self.cause_ref,
            "evidenceId": self.evidence_id,
        }
        body = {key: values[key] for key in CANONICAL_KEYS}
        validate_contract("ProblemDetails", body)
        return body


def canonical_response(error: CanonicalProblem, *, trace_id: str) -> JSONResponse:
    headers = {"Cache-Control": "no-store"}
    if error.status == 401:
        headers["WWW-Authenticate"] = "Bearer"
    return JSONResponse(
        error.body(trace_id=trace_id),
        status_code=error.status,
        media_type=PROBLEM_CONTENT_TYPE,
        headers=headers,
    )


def legacy_not_found_problem(error: InvError) -> CanonicalProblem | None:
    """Map only the legacy codes whose public meaning is always absence."""
    if error.code not in LEGACY_NOT_FOUND_CODES:
        return None
    return CanonicalProblem(
        RES_NOT_FOUND,
        404,
        "No such resource.",
        retryable=False,
    )


#: Categories whose 401/403 refusals are audited (AC-02): the same two the
#: legacy ``InvError`` handler records.
DENIAL_CATEGORIES: frozenset[str] = frozenset({"AUTH", "SEC"})
DENIAL_STATUSES: frozenset[int] = frozenset({401, 403})

#: ``on_denial(request, code=..., trace_id=...)``: records one denial. Supplied
#: by ``create_app`` so this module keeps no database dependency.
DenialRecorder = Callable[..., None]


def is_audited_denial(error: CanonicalProblem) -> bool:
    """Whether a canonical problem is a denial the shared handler records.

    Two ways to be one: the historical rule -- an AUTH or SEC refusal at 401/403 -- or a
    refusal whose route named an ``audit_action``. The second exists because #282 §8
    requires the *state* refusals (a stale digest, an expired proposal) to be audited too,
    and those are GRAPH 409s that the first rule does not cover.
    """
    if error.audit_action:
        return True
    return error.category in DENIAL_CATEGORIES and error.status in DENIAL_STATUSES


def install_canonical_problem_handler(
    app: FastAPI, *, on_denial: DenialRecorder | None = None
) -> None:
    """Register the handler once. Existing handlers are left alone.

    ``on_denial`` is called exactly once, before the response is built, for a
    problem that :func:`is_audited_denial` -- and only there: no route records
    a denial itself. If the recorder raises, the exception propagates and the
    request ends as a generic 500 (fail-closed): an audit failure is not
    disguised as a successful refusal.
    """

    @app.exception_handler(CanonicalProblem)
    async def _canonical(request: Request, exc: CanonicalProblem) -> JSONResponse:
        trace_id = getattr(request.state, "trace_id", None) or new_trace_id()
        if on_denial is not None and is_audited_denial(exc):
            if exc.audit_action:
                request.state.denial_action = exc.audit_action
            on_denial(request, code=exc.code, trace_id=trace_id)
        return canonical_response(exc, trace_id=trace_id)


#: A route's translation entry: canonical code, status, retryability.
Mapped = tuple[str, int, bool]


def translate(
    error: InvError, *, table: Mapping[str, Mapped], detail: str | None = None
) -> CanonicalProblem:
    """Turn a business error into this route's canonical one.

    A code the route did not declare becomes ``SYS-0002``: it is our mapping
    that is missing, so the client learns nothing about their request and a
    retry would fail identically. A test enumerates the codes each route can
    reach and requires the table to cover them, so this branch stays unreached.
    """
    entry = table.get(error.code)
    if entry is None:
        return CanonicalProblem(
            SYS_UNMAPPED,
            500,
            "The service raised an error this route cannot represent.",
            retryable=False,
        )
    code, status, retryable = entry
    return CanonicalProblem(
        code,
        status,
        detail if detail is not None else error.message,
        retryable=retryable,
        cause_ref=error.cause_ref,
    )


def _media_type(content_type: str | None) -> str:
    return (content_type or "").split(";", 1)[0].strip().lower()


def strict_json_object(
    raw: bytes,
    *,
    content_type: str | None,
    content_encoding: str | None = None,
    max_bytes: int = MAX_REQUEST_BYTES,
) -> dict[str, Any]:
    """Read a request body as an unambiguous JSON object, or refuse.

    Parsing is delegated to ``inv.identity.strict_object``, which already
    rejects a duplicate key, a non-finite constant and a non-object top level.
    Reimplementing those rules here would let the two parsers disagree about
    what the same bytes mean depending on which door they came through, so this
    function only supplies the transport boundary and the translation.

    Every refusal is one ``VAL-0003``; only the status differs, which is the
    kernel's own practice for this code (415, 413, 422).
    """
    from inv.identity import strict_object

    if _media_type(content_type) != JSON_MEDIA_TYPE or content_encoding:
        raise CanonicalProblem(VAL_REQUEST, 415, "A JSON request body is required.")
    if len(raw) > max_bytes:
        raise CanonicalProblem(VAL_REQUEST, 413, "The request body is too large.")
    if not raw:
        raise CanonicalProblem(VAL_REQUEST, 422, "A request body is required.")
    try:
        return strict_object(raw)
    except (ValueError, TypeError, RecursionError, UnicodeError):
        raise CanonicalProblem(
            VAL_REQUEST, 422, "An unambiguous JSON object is required."
        ) from None


async def read_bounded_body(request: Request, *, max_bytes: int = MAX_REQUEST_BYTES) -> bytes:
    """Read the body, refusing as soon as it passes the bound.

    ``await request.body()`` buffers the whole payload and only then can its
    length be checked, which makes the bound a parser limit rather than an
    allocation limit: a caller could still make the process hold whatever they
    sent. Reading the stream and stopping at the first chunk that crosses the
    bound makes the limit mean what it says. The kernel does the same thing in
    its ASGI middleware; this is the per-route equivalent for an app that has no
    such middleware.
    """
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > max_bytes:
            raise CanonicalProblem(VAL_REQUEST, 413, "The request body is too large.")
        chunks.append(chunk)
    return b"".join(chunks)


def require_absent_body(raw: bytes) -> None:
    """Refuse a body on a route that has none.

    Discarding it quietly would let a caller believe something they sent was
    taken into account. One byte is enough to be ambiguous.
    """
    if raw:
        raise CanonicalProblem(VAL_REQUEST, 422, "This request takes no body.")


def validate_strict(model: type, payload: Mapping[str, Any]) -> Any:
    """Validate a parsed object against a ``schemas.Strict`` model.

    ``ValidationError.errors()`` is not serialised: it carries field paths and
    the submitted values, and neither belongs in a canonical body.
    """
    from pydantic import ValidationError

    try:
        return model.model_validate(dict(payload))
    except ValidationError:
        raise CanonicalProblem(
            VAL_REQUEST, 422, "The request body does not match the schema."
        ) from None
