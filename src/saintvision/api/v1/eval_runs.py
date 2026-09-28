"""W5: run an eval suite (G-04·G-05 design §2, PR 8 of 8 — the last one).

``POST /projects/{project_id}/eval/suites/{suite_id}/runs``

``run_suite`` has been in ``services/eval_execution.py`` since S09 with no HTTP
request reaching it. This is that request path, and its signature is unchanged.

**This route spends money.** It drives a provider adapter once per case, so the
things that would be merely untidy on a read route are load-bearing here:

* the grade is ``canApprove`` (design §2, Codex F1 final), and it is re-checked
  **immediately before** the adapter runs -- not only at the start of the request.
  A membership revoked while the request was waiting for its idempotency lock must
  not be able to buy anything;
* the caller names an **adapter**, never an endpoint or a credential.
  ``agents.adapter_for`` resolves the name against ``BY_NAME``, the configured
  allowlist, so the worst a caller can do is pick one of the platform's four CLIs.
  An unknown name is a request error before anything runs;
* a repeated request with the same idempotency key **replays** rather than running
  the suite again, which is the difference between a retry and a second bill.

**The project in the path is bound to the suite** through ``eval_suites.project_id``
(migration ``0053``). That column is nullable, because a suite made before ``0053``
has none -- and this route treats NULL as *absent*, not as *every project's*. A
suite of another project, another tenant, or one with no project at all are the
same 404 as a suite that does not exist; anything else would let a path variable
probe for suites the caller cannot see.

**Two transaction spans.** Permission first in its own short transaction, then the
body read with nothing open, then one atomic transaction for the work. The body
arrives at the caller's pace and the suite run itself is long; the split is what
keeps a transaction from being held open across either.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from ...adapters import agents
from ...config import Settings
from ...db.models.evaluation import EvalSuite
from ...db.session import make_session_factory, tenant_scope
from ...errors import AUTH_PROJECT_SCOPE, GRAPH_IDEMPOTENCY_CONFLICT, VAL_SCHEMA, InvError
from ...identity.principal import Principal
from ...services import projects as project_service
from ...services.audit import record_event
from ...services.eval_execution import run_suite
from .. import schemas
from ..lock_wait import bounded_lock_wait
from ..deps import (
    get_principal,
    get_settings,
    replay_or_reserve,
    serialise_idempotent_write,
    store_idempotent_response,
)
from ..problem import (
    AUTH_PROJECT,
    GRAPH_PRECONDITION,
    RES_NOT_FOUND,
    VAL_REQUEST,
    CanonicalProblem,
    read_bounded_body,
    strict_json_object,
    translate,
    validate_strict,
)

EVAL_RUN_PATH = "/projects/{project_id}/eval/suites/{suite_id}/runs"

#: The idempotency ledger's ``endpoint`` for this route (IDEM-2). A constant, so a
#: renamed path cannot silently start a new key space.
ENDPOINT = "POST /v1/projects/{project_id}/eval/suites/{suite_id}/runs"

#: The same answer for every way the path can fail to name a suite this caller may
#: run. Held here so the raise sites cannot drift apart.
NO_SUCH_SUITE = "No such eval suite."

#: What an ``Idempotency-Key`` may be: the ledger column is ``String(128)`` and the
#: lock material is separated by ``\x1f``, so a key that does not fit either would
#: be a database error or an ambiguous lock instead of a request error.
IDEMPOTENCY_KEY_PATTERN = r"[A-Za-z0-9._:-]{1,128}"

#: ``run_suite`` fills these in with ``setdefault``, so a caller who sent one would
#: have *their* value recorded as the identity of the run. Refused at the boundary.
SERVICE_OWNED_VERSIONS = ("adapter", "contractVersion", "modelPinned")

#: Every ``InvError`` reachable from the calls below, and its canonical form. A code
#: missing here becomes ``SYS-0002``; a test enumerates what the calls can raise.
#:
#: ``VAL-SCHEMA`` is what ``run_suite`` raises when the chosen adapter cannot report
#: which model build produced a result, which is a **state precondition** at this
#: call site rather than a malformed request -- so it becomes ``GRAPH-0002``. The
#: same code from ``start_eval_run`` means "eval suite not found", which this route
#: has already ruled out by binding the suite, so it cannot reach that branch; the
#: table maps the code once and the detail says which of the two it is.
TRANSLATION: Mapping[str, tuple[str, int, bool]] = {
    AUTH_PROJECT_SCOPE: (AUTH_PROJECT, 403, False),
    VAL_SCHEMA: (GRAPH_PRECONDITION, 409, False),
    GRAPH_IDEMPOTENCY_CONFLICT: (GRAPH_PRECONDITION, 409, False),
}


def _require_approval(session: Session, *, principal: Principal, project_id: str) -> None:
    """Live project access plus the approval grade, or a canonical refusal.

    ``Principal.require_project`` is the sign-in snapshot and says so itself: a
    membership revoked since then would still pass it.
    """
    try:
        permission = project_service.require_project_access(
            session,
            tenant_id=principal.tenant_id,
            project_id=project_id,
            user_id=principal.user_id,
        )
    except InvError as error:
        raise translate(
            error, table=TRANSLATION, detail="This project is not accessible."
        ) from None
    if not permission.get("canApprove"):
        raise CanonicalProblem(
            AUTH_PROJECT, 403, "Running an eval suite requires approval permission."
        )


def _require_idempotency_key(raw: str | None) -> str:
    """Required on every write in this lane (IDEM-1), and doubly so here.

    Optional would mean a retry of a request whose answer never arrived could run
    the whole suite a second time and bill for it.
    """
    if raw is None or not re.fullmatch(IDEMPOTENCY_KEY_PATTERN, raw):
        raise CanonicalProblem(
            VAL_REQUEST,
            422,
            "An Idempotency-Key header of up to 128 identifier characters is required.",
        )
    return raw


def _reject_service_owned_versions(versions: Mapping[str, str]) -> None:
    """The service decides these three; a caller who sets one forges the identity."""
    offending = sorted(set(versions) & set(SERVICE_OWNED_VERSIONS))
    if offending:
        raise CanonicalProblem(
            VAL_REQUEST,
            422,
            "componentVersions may not contain "
            + ", ".join(offending)
            + ": the platform records those itself.",
        )


def _suite_in_project(
    session: Session, *, tenant_id, project_id: str, suite_id: str
) -> EvalSuite:
    """Resolve ``(project, suite)`` to one row, or the one 404.

    ``project_id`` is nullable on ``eval_suites`` (0053), and NULL means *this suite
    belongs to no project* rather than *to all of them*. Absent, another tenant's,
    another project's and project-less all answer the same way, which is the rule
    ``require_project_access`` already states for projects themselves.
    """
    suite = session.get(EvalSuite, suite_id, populate_existing=True)
    if (
        suite is None
        or suite.tenant_id != tenant_id
        # Redundant with the comparison below -- ``None != project_id`` is already
        # true for a path value, which is always a string. It is written out
        # because the decision is not obvious from the comparison: 0053 left the
        # column nullable, and "NULL matches nothing" rather than "NULL matches
        # everything" is the choice being made. A test cannot tell the two forms
        # apart, so the code says it instead.
        or suite.project_id is None
        or suite.project_id != project_id
    ):
        raise CanonicalProblem(RES_NOT_FOUND, 404, NO_SUCH_SUITE)
    return suite


def _adapter(name: str):
    """The configured allowlist, by name. An unknown name runs nothing."""
    try:
        return agents.adapter_for(name)
    except KeyError:
        raise CanonicalProblem(
            VAL_REQUEST, 422, "No adapter by that name is configured."
        ) from None


def _response(run) -> schemas.EvalRunResponse:
    return schemas.EvalRunResponse(
        evalRunId=run.eval_run_id,
        suiteId=run.suite_id,
        status=run.status,
        totalCases=int(run.total_cases),
        passedCases=int(run.passed_cases),
        violations=int(run.violations),
        passedGate=bool(run.passed_gate),
        componentVersions=dict(run.component_versions or {}),
        startedAt=run.started_at,
        endedAt=run.ended_at,
    )


async def start_eval_run(
    project_id: str,
    suite_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
    settings: Settings = Depends(get_settings),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> Any:
    """Run every case in the suite once, and report the closed run.

    The body is parsed here rather than declared as a parameter: FastAPI validates
    a declared model before the handler runs and its ``RequestValidationError``
    handler adds a top-level ``fields`` key the canonical schema forbids. The clock
    is read inside the write span for the same reason it is in the register route --
    a dependency would fix it before the body and the lock.
    """
    factory = make_session_factory(request.app.state.engine)

    # (1) Permission first, in its own short transaction. A caller who may not run
    # a suite learns nothing from how their key or their body is judged, and
    # nothing is held open while the body arrives.
    with factory() as session:
        with session.begin():
            with tenant_scope(session, principal.tenant_id), bounded_lock_wait(
                session, timeout_ms=settings.business_lock_timeout_ms
            ):
                _require_approval(session, principal=principal, project_id=project_id)

    key = _require_idempotency_key(idempotency_key)
    payload = strict_json_object(
        await read_bounded_body(request),
        content_type=request.headers.get("content-type"),
        content_encoding=request.headers.get("content-encoding"),
    )
    proposal = validate_strict(schemas.EvalRunStartRequest, payload)
    _reject_service_owned_versions(proposal.component_versions)

    # The path is part of what the key identifies: the same key used for another
    # suite is a conflict, not a replay of this one's answer.
    ledger_payload = {
        "suiteId": suite_id,
        "request": proposal.model_dump(by_alias=True, mode="json"),
    }

    # (2) One atomic transaction: serialise, re-check, replay-or-proceed, bind,
    # resolve the adapter, re-check again, then spend.
    with factory() as session:
        with session.begin():
            with tenant_scope(session, principal.tenant_id), bounded_lock_wait(
                session, timeout_ms=settings.business_lock_timeout_ms
            ):
                # IDEM-6: the serialisation point comes before any resource row, in
                # every route, so the lock order in this lane is one order.
                serialise_idempotent_write(
                    session,
                    tenant_id=principal.tenant_id,
                    endpoint=ENDPOINT,
                    idempotency_key=key,
                    project_id=project_id,
                )
                # Guards the replay: a membership revoked between the two spans must
                # not be able to read a stored result either.
                _require_approval(session, principal=principal, project_id=project_id)
                try:
                    replayed = replay_or_reserve(
                        session,
                        principal=principal,
                        endpoint=ENDPOINT,
                        idempotency_key=key,
                        payload=ledger_payload,
                        now=request.app.state.clock(),
                        ttl_seconds=settings.idempotency_ttl_seconds,
                        project_id=project_id,
                    )
                except InvError as error:
                    raise translate(
                        error,
                        table=TRANSLATION,
                        detail="That idempotency key was used with a different request.",
                    ) from None
                if replayed is not None:
                    # Exact replay: the stored body, and the status this route always
                    # returns. A retry must not buy a second run.
                    return replayed

                _suite_in_project(
                    session,
                    tenant_id=principal.tenant_id,
                    project_id=project_id,
                    suite_id=suite_id,
                )
                adapter = _adapter(proposal.adapter)
                # Re-checked once more, here, because the next call spends money on
                # an external provider. Everything between this line and it is a
                # local read.
                _require_approval(session, principal=principal, project_id=project_id)
                now = request.app.state.clock()
                try:
                    run = run_suite(
                        session,
                        tenant_id=principal.tenant_id,
                        suite_id=suite_id,
                        adapter=adapter,
                        now=now,
                        component_versions=dict(proposal.component_versions),
                        require_model_pinning=proposal.require_model_pinning,
                    )
                except InvError as error:
                    raise translate(error, table=TRANSLATION) from None
                body = _response(run).model_dump(by_alias=True, mode="json")
                record_event(
                    session,
                    now=now,
                    actor_type="user",
                    actor_id=principal.user_id,
                    action="eval_run.execute",
                    outcome="allow",
                    tenant_id=principal.tenant_id,
                    trace_id=getattr(request.state, "trace_id", None),
                    target_type="eval_run",
                    target_id=run.eval_run_id,
                    # Identifiers and counts. No case content and no model output:
                    # the audit trail is read widely and a leaked result in it is
                    # still a leak.
                    detail={
                        "projectId": project_id,
                        "suiteId": suite_id,
                        "adapter": adapter.name,
                        "requireModelPinning": proposal.require_model_pinning,
                        "totalCases": int(run.total_cases),
                        "passedGate": bool(run.passed_gate),
                    },
                    source_ip=request.client.host if request.client else None,
                    user_agent=request.headers.get("user-agent"),
                )
                store_idempotent_response(
                    session,
                    principal=principal,
                    endpoint=ENDPOINT,
                    idempotency_key=key,
                    payload=ledger_payload,
                    response_status=201,
                    response_body=body,
                    now=now,
                    ttl_seconds=settings.idempotency_ttl_seconds,
                    project_id=project_id,
                )
    return body


def register(router: APIRouter) -> None:
    """Add the route to the projects router.

    ``inv.business_surface.BusinessDispatch`` selects business traffic by reading
    ``projects.router.routes``, and ``include_router`` on an ``APIRouter`` leaves
    only a lazy placeholder there, so the route has to be added with
    ``add_api_route`` to be served at all.
    """
    router.add_api_route(
        EVAL_RUN_PATH,
        start_eval_run,
        methods=["POST"],
        status_code=201,
        response_model=schemas.EvalRunResponse,
        tags=["evaluation"],
        name="start_eval_run",
    )
