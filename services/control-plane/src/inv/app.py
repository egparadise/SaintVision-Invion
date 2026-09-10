"""Authenticated browser API factory; explicit deployment configuration required."""

import asyncio
import json
import os
import time
from threading import BoundedSemaphore
from fastapi import FastAPI, Request, Depends
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException
from . import __version__
from .contracts import validate_contract
from .control import Control
from .db import Database
from .errors import DomainError
from .identity import AccessTokens, strict_object, trusted_file
from .tracing import request_trace, nonzero_id


def problem(error, trace_id=None):
    return JSONResponse(
        {
            "type": "about:blank",
            "title": "Request rejected",
            "status": error.status,
            "code": error.code,
            "category": error.code.split("-", 1)[0],
            "detail": error.detail,
            "retryable": error.retryable,
            "traceId": trace_id or nonzero_id(16),
            "causeRef": None,
            "evidenceId": None,
        },
        status_code=error.status,
        headers={
            "Cache-Control": "no-store",
            **({"WWW-Authenticate": "Bearer"} if error.status == 401 else {}),
        },
        media_type="application/problem+json",
    )


class Boundary:
    def __init__(self, app, origins):
        self.app, self.origins = app, frozenset(origins)
        self.slots = BoundedSemaphore(64)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        trace_id, parent = request_trace(scope["headers"])
        scope.setdefault("state", {})["trace_id"] = trace_id

        async def traced_send(message):
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                headers[:] = [
                    (k, v)
                    for k, v in headers
                    if k not in {b"traceparent", b"cache-control", b"x-content-type-options"}
                ]
                headers.extend(
                    [
                        (b"traceparent", parent.encode("ascii")),
                        (b"cache-control", b"no-store"),
                        (b"x-content-type-options", b"nosniff"),
                    ]
                )
            await send(message)

        if not self.slots.acquire(blocking=False):
            return await problem(
                DomainError("RES-0007", "Request capacity reached", 429), trace_id
            )(scope, receive, traced_send)
        try:
            return await self.handle(scope, receive, traced_send)
        finally:
            self.slots.release()

    async def handle(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        started = False

        async def safe_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            if sum(len(k) + len(v) for k, v in scope["headers"]) > 32768:
                raise DomainError("VAL-0003", "Request headers exceed limit", 431)
            headers = {}
            for name, value in scope["headers"]:
                if (
                    name
                    in {
                        b"authorization",
                        b"origin",
                        b"content-type",
                        b"content-length",
                        b"idempotency-key",
                        b"last-event-id",
                    }
                    and name in headers
                ):
                    raise DomainError("VAL-0003", "Ambiguous request headers", 400)
                headers[name] = value
            if b"origin" in headers and headers[b"origin"].decode("latin1") not in self.origins:
                raise DomainError("AUTH-0051", "Browser origin rejected", 403)
            if (
                scope["path"].startswith("/v1/")
                and b"access_token" in scope.get("query_string", b"").lower()
            ):
                raise DomainError("AUTH-0050", "Use the Authorization header", 401)
            chunks, length = [], 0

            async def read_body():
                nonlocal length
                while True:
                    message = await receive()
                    if message["type"] != "http.request":
                        raise DomainError("VAL-0003", "Request interrupted", 400)
                    chunk = message.get("body", b"")
                    length += len(chunk)
                    if length > 65536:
                        raise DomainError("VAL-0003", "Request exceeds limit", 413)
                    chunks.append(chunk)
                    if not message.get("more_body", False):
                        return

            await asyncio.wait_for(read_body(), 5)
            body = b"".join(chunks)
            if scope["method"] in {"POST", "PUT", "PATCH"}:
                if (
                    headers.get(b"content-type") != b"application/json"
                    or b"content-encoding" in headers
                ):
                    raise DomainError("VAL-0003", "JSON content type required", 415)
                try:
                    strict_object(body)
                except (ValueError, TypeError, RecursionError, UnicodeError):
                    raise DomainError("VAL-0003", "Unambiguous JSON object required", 422) from None
            sent = False

            async def replay():
                nonlocal sent
                if not sent:
                    sent = True
                    return {"type": "http.request", "body": body, "more_body": False}
                return await receive()

            await self.app(scope, replay, safe_send)
        except Exception as error:
            if started:
                return  # No internal diagnostics after streaming has begun.
            if not isinstance(error, DomainError):
                error = DomainError("SYS-0001", "Service temporarily unavailable", 503)
            await problem(error, scope["state"]["trace_id"])(scope, receive, send)


def create_app(database=None, tokens=None, *, allowed_origins=(), workspace=None):
    api = FastAPI(
        title="Saint Vision INV Control Plane",
        version=__version__,
        docs_url=None,
        redoc_url=None,
    )
    api.add_middleware(Boundary, origins=allowed_origins)
    control = Control(database) if database else None

    @api.exception_handler(DomainError)
    async def domain_error(request, error):
        return problem(error, request.state.trace_id)

    @api.exception_handler(RequestValidationError)
    async def invalid(request, error):
        return problem(DomainError("VAL-0003", "Invalid request", 422), request.state.trace_id)

    @api.exception_handler(HTTPException)
    async def http_error(request, error):
        return problem(
            DomainError("HTTP-0001", "Request unavailable", error.status_code),
            request.state.trace_id,
        )

    def authenticated(request: Request):
        if control is None or tokens is None:
            raise DomainError("AUTH-0050", "Identity configuration unavailable", 503)
        header = request.headers.get("authorization", "")
        if not header.startswith("Bearer ") or header.count(" ") != 1:
            raise DomainError("AUTH-0050", "A current access token is required", 401)
        return tokens.verify(header[7:])

    def key(request):
        value = request.headers.get("idempotency-key")
        if not value or len(value) > 200 or any(ord(c) < 33 or ord(c) > 126 for c in value):
            raise DomainError("VAL-0003", "Idempotency-Key required", 422)
        return value

    @api.get("/healthz")
    def health():
        return {"status": "ok", "version": __version__}

    @api.get("/readyz")
    def ready():
        if control is None or tokens is None:
            return JSONResponse(
                {
                    "status": "not_ready",
                    "reason": "identity-and-database-configuration-pending",
                },
                status_code=503,
            )
        tokens._keys()
        with database.transaction(tokens.tenant_id) as conn:
            conn.execute("SELECT event_sequence FROM inv.runs LIMIT 0")
        return {
            "status": "ready",
            "scope": "authenticated-control-api",
            "executionDispatcher": "external-worker-required" if workspace else "not_configured",
            "workspaceAdmission": "configured" if workspace else "not_configured",
        }

    @api.get("/v1/projects")
    def projects(identity=Depends(authenticated)):
        return control.projects(identity.principal)

    @api.get("/v1/operations/kill-switch")
    def kill_status(identity=Depends(authenticated)):
        from .containment import Containment

        return Containment(database).get(identity.principal)

    @api.post("/v1/operations/containment-approvals", status_code=201)
    async def propose_containment(request: Request, identity=Depends(authenticated)):
        from .containment_approvals import ControlApprovals

        return await run_in_threadpool(
            ControlApprovals(database).propose,
            identity.principal,
            await request.json(),
            key(request),
        )

    @api.get("/v1/operations/containment-approvals/{approval_id}")
    def containment_approval(approval_id: str, identity=Depends(authenticated)):
        from .containment_approvals import ControlApprovals

        return ControlApprovals(database).get(identity.principal, approval_id)

    @api.post("/v1/operations/containment-approvals/{approval_id}/challenge")
    async def containment_challenge(
        approval_id: str, request: Request, identity=Depends(authenticated)
    ):
        from .containment_approvals import ControlApprovals

        validate_contract("EmptyRequest", await request.json())
        return await run_in_threadpool(
            ControlApprovals(database).challenge, identity.principal, approval_id
        )

    @api.post("/v1/operations/containment-approvals/{approval_id}/decision")
    async def decide_containment(
        approval_id: str, request: Request, identity=Depends(authenticated)
    ):
        from .containment_approvals import ControlApprovals

        return await run_in_threadpool(
            ControlApprovals(database).decide,
            identity.principal,
            approval_id,
            await request.json(),
            key(request),
        )

    @api.post("/v1/operations/kill-switch", status_code=202)
    async def kill_switch(request: Request, identity=Depends(authenticated)):
        from .containment import Containment

        return await run_in_threadpool(
            Containment(database).change,
            identity.principal,
            "kill",
            await request.json(),
            key(request),
        )

    @api.post("/v1/operations/kill-switch/clear")
    async def clear_kill_switch(request: Request, identity=Depends(authenticated)):
        from .containment import Containment

        return await run_in_threadpool(
            Containment(database).change,
            identity.principal,
            "clear",
            await request.json(),
            key(request),
        )

    @api.get("/v1/nodes/{node_id}/control")
    def node_control(node_id: str, identity=Depends(authenticated)):
        from .containment import Containment

        return Containment(database).get(identity.principal, node_id)

    @api.post("/v1/nodes/{node_id}/drain", status_code=202)
    async def drain_node(node_id: str, request: Request, identity=Depends(authenticated)):
        from .containment import Containment

        return await run_in_threadpool(
            Containment(database).change,
            identity.principal,
            "drain",
            await request.json(),
            key(request),
            node_id,
        )

    @api.post("/v1/nodes/{node_id}/resume")
    async def resume_node(node_id: str, request: Request, identity=Depends(authenticated)):
        from .containment import Containment

        return await run_in_threadpool(
            Containment(database).change,
            identity.principal,
            "resume",
            await request.json(),
            key(request),
            node_id,
        )

    @api.get("/v1/projects/{project}/runs")
    def runs(
        project: str,
        after: str | None = None,
        limit: int = 50,
        identity=Depends(authenticated),
    ):
        return control.list_runs(identity.principal, project, after=after, limit=limit)

    @api.post("/v1/projects/{project}/runs", status_code=201)
    async def create(project: str, request: Request, identity=Depends(authenticated)):
        validate_contract("EmptyRequest", await request.json())
        return await run_in_threadpool(control.create, identity.principal, project, key(request))

    @api.get("/v1/projects/{project}/runs/{run_id}")
    def run(project: str, run_id: str, identity=Depends(authenticated)):
        return control.get(identity.principal, project, run_id)

    @api.post("/v1/projects/{project}/runs/{run_id}/cancel")
    async def cancel(project: str, run_id: str, request: Request, identity=Depends(authenticated)):
        data = await request.json()
        validate_contract("RunCancelInput", data)
        return await run_in_threadpool(
            control.cancel,
            identity.principal,
            project,
            run_id,
            data["expectedVersion"],
            key(request),
        )

    @api.get("/v1/projects/{project}/nodes")
    def nodes(project: str, identity=Depends(authenticated)):
        return control.nodes(identity.principal, project)

    @api.get("/v1/projects/{project}/capacity")
    def capacity(project: str, identity=Depends(authenticated)):
        return control.capacity(identity.principal, project)

    @api.post("/v1/projects/{project}/approvals/{approval_id}/challenge")
    async def challenge(
        project: str,
        approval_id: str,
        request: Request,
        identity=Depends(authenticated),
    ):
        validate_contract("EmptyRequest", await request.json())
        validate_contract("ProjectId", project)
        validate_contract("ApprovalId", approval_id)
        return await run_in_threadpool(
            control.approvals.challenge, identity.principal, project, approval_id
        )

    @api.post("/v1/projects/{project}/approvals/{approval_id}/decision")
    async def decision(
        project: str,
        approval_id: str,
        request: Request,
        identity=Depends(authenticated),
    ):
        data = await request.json()
        validate_contract("ApprovalDecisionInput", data)
        return await run_in_threadpool(
            control.approvals.decide,
            identity.principal,
            project,
            approval_id,
            data["decision"],
            data["nonce"],
            action_digest=data["actionDigest"],
            key=key(request),
        )

    def workspace_service():
        if workspace is None:
            raise DomainError("SYS-0001", "Workspace admission is not configured", 503)
        return workspace

    def business_service():
        from .business_handoff import BusinessHandoff

        return BusinessHandoff(workspace_service())

    @api.get("/v1/projects/{project}/permission")
    def business_permission(project: str, identity=Depends(authenticated)):
        from .business_auth import permission

        with database.transaction(identity.principal.tenant_id) as conn:
            effective = control.grant(conn, identity.principal, project)
            value = permission(conn, project, identity.principal.subject_id, linked=True)
            return {
                "projectId": project,
                "userId": value["userId"],
                "roleCode": value["roleCode"],
                "canRequest": effective["can_request"],
                "canApprove": effective["can_approve"],
            }

    @api.post("/v1/workspaces/{workspace_id}/edit-lock", status_code=201)
    async def stop_business_editing(
        workspace_id: str, request: Request, identity=Depends(authenticated)
    ):
        return await run_in_threadpool(
            business_service().stop,
            identity.principal,
            workspace_id,
            await request.json(),
            key(request),
        )

    @api.delete("/v1/edit-locks/{lock_id}")
    async def release_business_editing(
        lock_id: str, request: Request, identity=Depends(authenticated)
    ):
        return await run_in_threadpool(
            business_service().release, identity.principal, lock_id, key(request)
        )

    @api.post("/v1/runs/{run_id}/bindings", status_code=201)
    async def prepare_business_binding(
        run_id: str, request: Request, identity=Depends(authenticated)
    ):
        return await run_in_threadpool(
            business_service().prepare,
            identity.principal,
            run_id,
            await request.json(),
            key(request),
        )

    @api.get("/v1/bindings/{binding_id}")
    def business_binding(binding_id: str, identity=Depends(authenticated)):
        return business_service().get(identity.principal, binding_id)

    @api.post("/v1/bindings/{binding_id}/approval")
    async def business_approval(binding_id: str, request: Request, identity=Depends(authenticated)):
        return await run_in_threadpool(
            business_service().approved, identity.principal, binding_id, await request.json()
        )

    @api.post("/v1/bindings/{binding_id}/enqueue", status_code=202)
    async def enqueue_business_binding(
        binding_id: str, request: Request, identity=Depends(authenticated)
    ):
        validate_contract("EmptyRequest", await request.json())
        return await run_in_threadpool(
            business_service().enqueue, identity.principal, binding_id, key(request)
        )

    @api.post("/v1/bindings/{binding_id}/reconcile")
    async def reconcile_business_binding(
        binding_id: str, request: Request, identity=Depends(authenticated)
    ):
        validate_contract("EmptyRequest", await request.json())
        return await run_in_threadpool(
            business_service().reconcile, identity.principal, binding_id, key(request)
        )

    @api.post("/v1/bindings/{binding_id}/state")
    async def reject_business_state(
        binding_id: str, request: Request, identity=Depends(authenticated)
    ):
        await run_in_threadpool(business_service().get, identity.principal, binding_id)
        raise DomainError("AUTH-0045", "Binding state is derived from execution evidence", 403)

    @api.post("/v1/projects/{project}/runs/{run_id}/resume/prepare", status_code=201)
    async def prepare_workspace(
        project: str, run_id: str, request: Request, identity=Depends(authenticated)
    ):
        data = await request.json()
        return await run_in_threadpool(
            workspace_service().prepare, identity.principal, project, run_id, data, key(request)
        )

    @api.post("/v1/projects/{project}/runs/{run_id}/resume/enqueue", status_code=202)
    async def enqueue_workspace(
        project: str, run_id: str, request: Request, identity=Depends(authenticated)
    ):
        data = await request.json()
        return await run_in_threadpool(
            workspace_service().enqueue, identity.principal, project, run_id, data, key(request)
        )

    @api.get("/v1/projects/{project}/runs/{run_id}/resumptions/{resume_id}")
    def workspace_status(
        project: str, run_id: str, resume_id: str, identity=Depends(authenticated)
    ):
        return workspace_service().get(identity.principal, project, run_id, resume_id)

    @api.get("/v1/projects/{project}/runs/{run_id}/events")
    async def events(project: str, run_id: str, request: Request, identity=Depends(authenticated)):
        cursor = request.headers.get("last-event-id")
        await run_in_threadpool(control.events, identity.principal, project, run_id, cursor)
        bearer = request.headers["authorization"][7:]

        async def stream():
            current, deadline = cursor, time.monotonic() + 25
            while time.monotonic() < deadline:
                try:
                    fresh = await run_in_threadpool(tokens.verify, bearer)
                    if fresh.principal != identity.principal:
                        return
                    pending = await run_in_threadpool(
                        control.events, fresh.principal, project, run_id, current
                    )
                except Exception:
                    yield 'event: inv.stream.closed\ndata: {"reason":"authorization-or-service-unavailable"}\n\n'
                    return
                for item in pending:
                    current = item["id"]
                    yield "id: " + current + "\nevent: inv.event\ndata: " + json.dumps(
                        item, separators=(",", ":")
                    ) + "\n\n"
                if len(pending) < 200:
                    yield ": keepalive\n\n"
                    await asyncio.sleep(1)
            yield ": reconnect\n\n"

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )

    return api


app = create_app()


def create_configured_app():
    """Production factory: explicit operator configuration, never seeded demo data."""
    try:
        settings = strict_object(trusted_file(os.environ["INV_API_CONFIG"]))
        if not {"identity"} <= settings.keys() <= {"identity", "allowedOrigins", "workspace"}:
            raise ValueError()
        identity = AccessTokens(**settings["identity"])
        database = Database(
            os.environ["INV_RUNTIME_DSN"], recovery_epoch=os.environ["INV_RECOVERY_EPOCH"]
        )
        workspace = None
        if "workspace" in settings:
            from .workspace_config import configured_workspace

            workspace = configured_workspace(database, identity.tenant_id, settings["workspace"])
        return create_app(
            database,
            identity,
            allowed_origins=settings.get("allowedOrigins", []),
            workspace=workspace,
        )
    except Exception:
        raise RuntimeError(
            "Explicit Control Plane identity/database/Workspace configuration unavailable"
        ) from None


def main():
    import uvicorn

    uvicorn.run(
        create_configured_app(),
        host="127.0.0.1",
        port=8080,
        proxy_headers=False,
        access_log=False,
        limit_concurrency=64,
        timeout_keep_alive=5,
        h11_max_incomplete_event_size=32768,
    )
