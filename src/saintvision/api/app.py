"""FastAPI application.

Boundaries kept: identity, resource and storage are separate routers over
separate service modules (PLAN-BACKEND-001). Everything shared by requests —
trace propagation, tenant scope, error shape, audit of denials — lives in the
middleware and the dependencies, not repeated per endpoint.
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Callable

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import Engine

from ..config import Settings, unresolved_s01_settings
from ..db.partitions import PartitionExhausted, assert_partitions_available
from ..errors import PROBLEM_CONTENT_TYPE, VAL_SCHEMA, InvError
from ..ids import is_id, is_trace_id, new_trace_id
from ..identity.principal import PrincipalVerifier
from ..services.audit import record_denial_out_of_band
from .audit_action import audit_action
from .problem import canonical_response, install_canonical_problem_handler, legacy_not_found_problem
from .v1 import adapters as adapters_router
from .v1 import nodes as nodes_router
from .v1 import pools as pools_router
from .v1 import projects as projects_router
from .v1 import readiness as readiness_router
from .v1 import release_acceptance as release_acceptance_router
from .v1 import release_manifests as release_manifests_router
from .v1 import settings as settings_router
from .v1 import storage as storage_router
from .v1 import storage_project as storage_project_router

TRACEPARENT_VERSION = "00"


def parse_traceparent(header: str | None) -> str:
    """Extract the trace-id from a W3C traceparent, or mint a new one.

    ADR-004: traceparent is the wire format; runId/stepId are business keys and
    are never used as trace or span IDs.
    """
    if header:
        parts = header.split("-")
        # An all-zero trace-id is invalid per W3C and is treated as absent
        # rather than propagated, or every such request would share one trace.
        if (
            len(parts) >= 3
            and parts[0] == TRACEPARENT_VERSION
            and is_trace_id(parts[1])
            and parts[1] != "0" * 32
        ):
            return parts[1]
    return new_trace_id()


def create_app(
    *,
    engine: Engine,
    settings: Settings,
    verifier: PrincipalVerifier,
    clock: Callable[[], dt.datetime] | None = None,
    check_partitions_on_startup: bool = True,
) -> FastAPI:
    now = clock or (lambda: dt.datetime.now(dt.timezone.utc))

    app = FastAPI(
        title="Saint Vision INV Control Plane",
        version="0.1.0",
        docs_url="/v1/docs",
        openapi_url="/v1/openapi.json",
    )
    app.state.engine = engine
    app.state.settings = settings
    app.state.verifier = verifier
    app.state.clock = now

    @app.on_event("startup")
    def _startup() -> None:
        # CR-06: refuse to serve rather than discover an exhausted partition at
        # the first insert, which would stop Runs from completing.
        if check_partitions_on_startup:
            with engine.connect() as connection:
                assert_partitions_available(
                    connection,
                    now=now(),
                    minimum_months=settings.partition_minimum_months,
                )
        app.state.unresolved_settings = unresolved_s01_settings()

    @app.middleware("http")
    async def _trace(request: Request, call_next):
        trace_id = getattr(request.state, "trace_id", None) or parse_traceparent(
            request.headers.get("traceparent")
        )
        request.state.trace_id = trace_id
        response = await call_next(request)
        response.headers["traceparent"] = f"{TRACEPARENT_VERSION}-{trace_id}-{'0'*16}-01"
        return response

    #: Denial categories that are audited (AC-02). Shared by both handlers.
    DENIAL_CATEGORIES = ("AUTH", "SEC")

    def _record_denial(request: Request, *, code: str, trace_id: str | None) -> None:
        """Record one denial, out of band, from what the request already proved.

        The single audit point for a refused request: the legacy ``InvError``
        handler and the canonical handler both call it, and no route records
        a denial itself (a route is inside a transaction that the refusal
        rolls back, and per-route recording drifts).

        * ``action`` is the bounded, identifier-free ``audit_action`` (#189).
        * The actor and the tenant come only from what ``get_principal`` pinned
          on ``request.state`` for a *verified* credential; nothing is parsed
          again from the header or the body. An unauthenticated request is
          therefore ``anonymous`` with no tenant.
        * The project target is the path's ``project_id`` only when it is a
          well-formed project id; caller text that is not one is not recorded
          anywhere. The tenant is always the caller's, never the project's.
        * ``detail`` is empty: every value belongs in its own column.

        Fail-closed: if the write fails the exception propagates and the
        request ends as a generic 500 with nothing privileged done -- an audit
        failure is not disguised as a successful refusal.
        """
        # A route may name the action its contract requires; otherwise it is the
        # bounded ``METHOD <template>`` (#189). Either way this is still the only place a
        # denial is written.
        declared = getattr(request.state, "denial_action", None)
        project_id = request.path_params.get("project_id")
        target = ("project", project_id) if is_id(project_id, "project") else (None, None)
        record_denial_out_of_band(
            engine,
            now=now(),
            actor_type=getattr(request.state, "actor_type", "anonymous"),
            actor_id=getattr(request.state, "actor_id", None),
            action=declared if isinstance(declared, str) and declared else audit_action(request),
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

    def _problem(request: Request, error: InvError, *, trace_id: str) -> JSONResponse:
        body = error.to_problem(trace_id=trace_id, instance=str(request.url.path))
        return JSONResponse(
            status_code=error.status or 500,
            content=body,
            media_type=PROBLEM_CONTENT_TYPE,
            headers={"WWW-Authenticate": "Bearer"} if error.status == 401 else {},
        )

    @app.exception_handler(InvError)
    async def _inv_error(request: Request, exc: InvError) -> JSONResponse:
        # AC-02 requires authentication failures to be recorded. The denial is
        # written in its own transaction so the request rollback cannot erase
        # it, and with the trace id the response carries.
        trace_id = getattr(request.state, "trace_id", None) or new_trace_id()
        not_found = legacy_not_found_problem(exc)
        if not_found is not None:
            return canonical_response(not_found, trace_id=trace_id)
        if exc.category.value in DENIAL_CATEGORIES:
            _record_denial(request, code=exc.code, trace_id=trace_id)
        return _problem(request, exc, trace_id=trace_id)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Field names are safe to return; submitted values are not, so only the
        # locations are echoed.
        locations = [".".join(str(p) for p in err["loc"]) for err in exc.errors()]
        error = InvError(
            VAL_SCHEMA, "request does not match the schema", extra={"fields": locations}
        )
        trace_id = getattr(request.state, "trace_id", None) or new_trace_id()
        return _problem(request, error, trace_id=trace_id)

    @app.get("/v1/health")
    def health() -> dict[str, Any]:
        """Liveness plus the honest configuration state.

        ``unresolvedSettings`` lists the S01-owned values that are still
        undecided, so a reader never has to guess whether OIDC is configured.
        """
        return {
            "status": "ok",
            "unresolvedSettings": unresolved_s01_settings(),
        }

    @app.get("/v1/readiness")
    def readiness() -> dict[str, Any]:
        with engine.connect() as connection:
            try:
                statuses = assert_partitions_available(
                    connection,
                    now=now(),
                    minimum_months=settings.partition_minimum_months,
                )
            except PartitionExhausted as exc:
                return {"status": "degraded", "reason": str(exc)}
        return {
            "status": "ok",
            "partitions": [{"table": s.table, "monthsAhead": s.months_ahead} for s in statuses],
        }

    # One registration, beside the existing handlers rather than replacing
    # them: legacy InvError stays on existing routes except for the closed set
    # of unambiguous not-found codes translated above.
    # The canonical handler records AUTH/SEC 401/403 through the same recorder
    # as the legacy handler; ``problem.py`` takes it as a callback so it keeps
    # no database dependency.
    install_canonical_problem_handler(app, on_denial=_record_denial)

    app.include_router(nodes_router.router)
    app.include_router(storage_router.router)
    app.include_router(storage_project_router.router)
    app.include_router(pools_router.router)
    app.include_router(settings_router.router)
    app.include_router(adapters_router.router)
    app.include_router(projects_router.router)
    app.include_router(readiness_router.router)
    app.include_router(release_manifests_router.router)
    # Registered so its contract can be exercised, and refused at the door until an
    # operator enables it and the prerequisites exist (design #282 §0-1.5).
    app.include_router(release_acceptance_router.router)
    return app
