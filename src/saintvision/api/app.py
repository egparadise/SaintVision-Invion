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
from ..ids import is_trace_id, new_trace_id
from ..identity.principal import PrincipalVerifier
from ..services.audit import record_denial_out_of_band
from .v1 import adapters as adapters_router
from .v1 import nodes as nodes_router
from .v1 import pools as pools_router
from .v1 import projects as projects_router
from .v1 import settings as settings_router
from .v1 import storage as storage_router

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
        trace_id = getattr(request.state, "trace_id", None) or parse_traceparent(request.headers.get("traceparent"))
        request.state.trace_id = trace_id
        response = await call_next(request)
        response.headers["traceparent"] = f"{TRACEPARENT_VERSION}-{trace_id}-{'0'*16}-01"
        return response

    def _problem(request: Request, error: InvError) -> JSONResponse:
        trace_id = getattr(request.state, "trace_id", None) or new_trace_id()
        body = error.to_problem(trace_id=trace_id, instance=str(request.url.path))
        return JSONResponse(
            status_code=error.status or 500,
            content=body,
            media_type=PROBLEM_CONTENT_TYPE,
        )

    @app.exception_handler(InvError)
    async def _inv_error(request: Request, exc: InvError) -> JSONResponse:
        # AC-02 requires authentication failures to be recorded. The denial is
        # written in its own transaction so the request rollback cannot erase
        # it.
        if exc.category.value in ("AUTH", "SEC"):
            record_denial_out_of_band(
                engine,
                now=now(),
                actor_type=getattr(request.state, "actor_type", "anonymous"),
                actor_id=getattr(request.state, "actor_id", None),
                action=f"{request.method} {request.url.path}",
                outcome="deny",
                tenant_id=getattr(request.state, "tenant_id", None),
                reason_code=exc.code,
                trace_id=getattr(request.state, "trace_id", None),
                source_ip=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            )
        return _problem(request, exc)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Field names are safe to return; submitted values are not, so only the
        # locations are echoed.
        locations = [".".join(str(p) for p in err["loc"]) for err in exc.errors()]
        error = InvError(
            VAL_SCHEMA, "request does not match the schema", extra={"fields": locations}
        )
        return _problem(request, error)

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
            "partitions": [
                {"table": s.table, "monthsAhead": s.months_ahead} for s in statuses
            ],
        }

    app.include_router(nodes_router.router)
    app.include_router(storage_router.router)
    app.include_router(pools_router.router)
    app.include_router(settings_router.router)
    app.include_router(adapters_router.router)
    app.include_router(projects_router.router)
    return app
