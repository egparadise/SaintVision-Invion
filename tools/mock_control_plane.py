"""
SaintVision Standalone Mock Control Plane Gateway
Provides live HTTP REST & SSE streaming endpoints on port 8000 for frontend E2E validation.
Strictly conforms to W3C Trace Context and RFC 9457 Problem Details.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import secrets
from typing import Any, AsyncGenerator

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import uvicorn

app = FastAPI(
    title="SaintVision Live Control Plane Gateway (Mock)",
    version="0.1.0",
    docs_url="/v1/docs",
    openapi_url="/v1/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage seeded with the 5 project nodes
NODES: list[dict[str, Any]] = [
    {
        "nodeId": "nod_01JABCDEF01",
        "hostname": "Node-01-WinMain",
        "osType": "windows",
        "osVersion": "11 Pro 23H2",
        "agentVersion": "0.1.0",
        "status": "online",
        "enrolledAt": "2026-09-01T00:00:00Z",
        "lastHeartbeatAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "heartbeatSequence": 1042,
        "labels": {"role": "control-plane", "gpu": "RTX-4090"},
    },
    {
        "nodeId": "nod_01JABCDEF02",
        "hostname": "Node-02-WinWork",
        "osType": "windows",
        "osVersion": "11 Pro 23H2",
        "agentVersion": "0.1.0",
        "status": "online",
        "enrolledAt": "2026-09-01T00:00:00Z",
        "lastHeartbeatAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "heartbeatSequence": 984,
        "labels": {"role": "sandbox", "gpu": "RTX-3080"},
    },
    {
        "nodeId": "nod_01JABCDEF03",
        "hostname": "Node-03-WinDev",
        "osType": "windows",
        "osVersion": "11 Pro 23H2",
        "agentVersion": "0.1.0",
        "status": "online",
        "enrolledAt": "2026-09-01T00:00:00Z",
        "lastHeartbeatAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "heartbeatSequence": 876,
        "labels": {"role": "editor"},
    },
    {
        "nodeId": "nod_01JABCDEF04",
        "hostname": "Node-04-LinuxBuild",
        "osType": "linux",
        "osVersion": "Ubuntu 22.04 LTS",
        "agentVersion": "0.1.0",
        "status": "online",
        "enrolledAt": "2026-09-01T00:00:00Z",
        "lastHeartbeatAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "heartbeatSequence": 1120,
        "labels": {"role": "build-farm", "lease": "monotonic"},
    },
    {
        "nodeId": "nod_01JABCDEF05",
        "hostname": "Node-05-LinuxTrain",
        "osType": "linux",
        "osVersion": "Ubuntu 22.04 LTS",
        "agentVersion": "0.1.0",
        "status": "online",
        "enrolledAt": "2026-09-01T00:00:00Z",
        "lastHeartbeatAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "heartbeatSequence": 940,
        "labels": {"role": "gpu-mlops", "gpu": "A4000"},
    },
]

RUNS: list[dict[str, Any]] = [
    {
        "id": "run_01JABCDE0001",
        "projectId": "prj_01JABCDE",
        "workspaceId": "wsp_01JABCDE001",
        "objective": "SaintVision PACS Core 빌드 및 단위 테스트",
        "state": "running",
        "requestedBy": "usr_developer_01",
        "createdAt": (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=15)).isoformat(),
        "updatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
    },
    {
        "id": "run_01JABCDE0002",
        "projectId": "prj_01JABCDE",
        "workspaceId": "wsp_01JABCDE001",
        "objective": "합성 데이터셋 전처리 및 로컬 분할 검증",
        "state": "awaiting_approval",
        "requestedBy": "usr_researcher_02",
        "createdAt": (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=30)).isoformat(),
        "updatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
    },
]

APPROVALS: list[dict[str, Any]] = [
    {
        "id": "apr_01JXYZ987654",
        "runId": "run_01JABCDE0002",
        "workspaceId": "wsp_01JABCDE001",
        "nodeId": "nod_01JABCDEF01",
        "riskLevel": "L2",
        "target": "Workspace [wsp-saint-pilot] on Node-01",
        "command": "git.deploy --release prod-v1.0.0",
        "estimatedCostKrw": 3200,
        "remainingBudgetKrw": 46800,
        "blastRadius": "workspace_isolated",
        "status": "pending",
        "nonce": "nonce_987654321",
        "expiresAt": (dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=10)).isoformat(),
        "policyReason": "외부 접근 포트 변경 및 TLS 암호화 활성화 정책에 따른 L2 승인 요구 (Rule #304)",
        "createdAt": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
]


@app.middleware("http")
async def w3c_traceparent_middleware(request: Request, call_next):
    raw_traceparent = request.headers.get("traceparent")
    if raw_traceparent and len(raw_traceparent.split("-")) == 4:
        parts = raw_traceparent.split("-")
        trace_id = parts[1]
    else:
        trace_id = secrets.token_hex(16)
    span_id = secrets.token_hex(8)

    request.state.trace_id = trace_id
    response = await call_next(request)
    response.headers["traceparent"] = f"00-{trace_id}-{span_id}-01"
    response.headers["X-Trace-Id"] = trace_id
    return response


@app.get("/v1/health")
def health_check(request: Request):
    return {
        "status": "healthy",
        "service": "SaintVision Control Plane Gateway",
        "version": "0.1.0",
        "traceId": request.state.trace_id,
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
    }


@app.get("/v1/nodes")
def list_nodes():
    return {"items": NODES, "total": len(NODES)}


@app.get("/v1/nodes/{node_id}")
def get_node(node_id: str, request: Request):
    for node in NODES:
        if node["nodeId"] == node_id:
            return node
    return JSONResponse(
        status_code=404,
        media_type="application/problem+json",
        content={
            "type": "https://saintvision.invenio/problems/node-not-found",
            "title": "Node Not Found",
            "status": 404,
            "detail": f"Node with ID '{node_id}' does not exist in cluster.",
            "code": "RES-NODE-404",
            "category": "RES",
            "traceId": request.state.trace_id,
        },
    )


@app.post("/v1/nodes/{node_id}/heartbeats")
def node_heartbeat(node_id: str, request: Request):
    for node in NODES:
        if node["nodeId"] == node_id:
            node["heartbeatSequence"] += 1
            node["lastHeartbeatAt"] = dt.datetime.now(dt.timezone.utc).isoformat()
            return {
                "nodeId": node_id,
                "status": "acknowledged",
                "sequence": node["heartbeatSequence"],
                "receivedAt": node["lastHeartbeatAt"],
            }
    return JSONResponse(
        status_code=404,
        media_type="application/problem+json",
        content={
            "type": "https://saintvision.invenio/problems/node-not-found",
            "title": "Node Not Found",
            "status": 404,
            "detail": f"Node with ID '{node_id}' is not enrolled.",
            "code": "RES-NODE-404",
            "category": "RES",
            "traceId": request.state.trace_id,
        },
    )


@app.get("/v1/runs")
def list_runs():
    return {"items": RUNS, "total": len(RUNS)}


@app.get("/v1/approvals")
def list_approvals():
    return {"items": APPROVALS, "total": len(APPROVALS)}


@app.post("/v1/approvals/{approval_id}/approve")
def approve_request(approval_id: str, payload: dict, request: Request):
    nonce = payload.get("nonce")
    for apprv in APPROVALS:
        if apprv["id"] == approval_id:
            if apprv["status"] != "pending":
                return JSONResponse(
                    status_code=409,
                    media_type="application/problem+json",
                    content={
                        "type": "https://saintvision.invenio/problems/already-decided",
                        "title": "Approval Already Decided",
                        "status": 409,
                        "detail": f"Approval '{approval_id}' has already been processed.",
                        "code": "VAL-ALREADY-DECIDED",
                        "category": "VAL",
                        "traceId": request.state.trace_id,
                    },
                )
            if apprv["nonce"] != nonce:
                return JSONResponse(
                    status_code=400,
                    media_type="application/problem+json",
                    content={
                        "type": "https://saintvision.invenio/problems/invalid-nonce",
                        "title": "Invalid Idempotency Nonce",
                        "status": 400,
                        "detail": "Supplied approval nonce does not match current valid nonce.",
                        "code": "SEC-NONCE-INVALID",
                        "category": "SEC",
                        "traceId": request.state.trace_id,
                    },
                )
            apprv["status"] = "approved"
            return {"approvalId": approval_id, "status": "approved", "nonce": nonce}

    return JSONResponse(
        status_code=404,
        media_type="application/problem+json",
        content={
            "type": "https://saintvision.invenio/problems/approval-not-found",
            "title": "Approval Not Found",
            "status": 404,
            "detail": f"Approval '{approval_id}' was not found.",
            "code": "RES-404",
            "category": "RES",
            "traceId": request.state.trace_id,
        },
    )


async def sse_event_generator() -> AsyncGenerator[str, None]:
    """Generates continuous Server-Sent Events for frontend telemetry."""
    while True:
        event_data = {
            "type": "heartbeat_tick",
            "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
            "activeNodes": len([n for n in NODES if n["status"] == "online"]),
            "totalNodes": len(NODES),
        }
        yield f"event: heartbeat\ndata: {json.dumps(event_data)}\n\n"
        await asyncio.sleep(4.0)


@app.get("/v1/events")
async def events_sse_stream():
    """SSE streaming endpoint with buffering disabled."""
    return StreamingResponse(
        sse_event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8080, log_level="info")
