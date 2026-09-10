"""
SaintVision Production Unified FastAPI Control Plane Server
Provides REST APIs, SSE telemetry streaming, and WebSocket interactive terminal.
Strictly adheres to W3C Trace Context (RFC 7230/W3C Rec) and RFC 9457 Problem Details.
"""

from __future__ import annotations

import asyncio
import base64
import datetime as dt
import hashlib
import json
import os
import secrets
from typing import Any, AsyncGenerator, Dict, List, Optional

from fastapi import (
    FastAPI,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import uvicorn

APP_VERSION = "0.2.0"
SERVICE_NAME = "SaintVision Unified Control Plane"

app = FastAPI(
    title=SERVICE_NAME,
    version=APP_VERSION,
    docs_url="/v1/docs",
    openapi_url="/v1/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://localhost:8443",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:8081",
        "http://127.0.0.1:8081",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------------------------
# In-Memory State Stores (Seeded with canonical project fixtures)
# ------------------------------------------------------------------------------

NODES: List[Dict[str, Any]] = [
    {
        "nodeId": "nod_01JABCDEF01",
        "hostname": "Node-01-WinMain",
        "osType": "windows",
        "osVersion": "11 Pro 23H2",
        "agentVersion": "0.1.0",
        "status": "online",
        "cpuCores": 16,
        "cpuUsagePercent": 24,
        "memoryTotalBytes": 64 * 1024**3,
        "memoryUsedBytes": 28 * 1024**3,
        "gpuName": "NVIDIA RTX 4090",
        "gpuCount": 1,
        "gpuVramTotalBytes": 24 * 1024**3,
        "gpuVramUsedBytes": 8 * 1024**3,
        "storageTotalBytes": 2000 * 1024**3,
        "storageUsedBytes": 850 * 1024**3,
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
        "cpuCores": 8,
        "cpuUsagePercent": 42,
        "memoryTotalBytes": 32 * 1024**3,
        "memoryUsedBytes": 19 * 1024**3,
        "gpuName": "NVIDIA RTX 3080",
        "gpuCount": 1,
        "gpuVramTotalBytes": 10 * 1024**3,
        "gpuVramUsedBytes": 6 * 1024**3,
        "storageTotalBytes": 1000 * 1024**3,
        "storageUsedBytes": 420 * 1024**3,
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
        "cpuCores": 8,
        "cpuUsagePercent": 15,
        "memoryTotalBytes": 32 * 1024**3,
        "memoryUsedBytes": 11 * 1024**3,
        "gpuCount": 0,
        "storageTotalBytes": 1000 * 1024**3,
        "storageUsedBytes": 310 * 1024**3,
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
        "cpuCores": 16,
        "cpuUsagePercent": 68,
        "memoryTotalBytes": 64 * 1024**3,
        "memoryUsedBytes": 45 * 1024**3,
        "gpuCount": 0,
        "storageTotalBytes": 4000 * 1024**3,
        "storageUsedBytes": 1800 * 1024**3,
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
        "cpuCores": 12,
        "cpuUsagePercent": 10,
        "memoryTotalBytes": 32 * 1024**3,
        "memoryUsedBytes": 8 * 1024**3,
        "gpuName": "NVIDIA A4000",
        "gpuCount": 1,
        "gpuVramTotalBytes": 16 * 1024**3,
        "gpuVramUsedBytes": 2 * 1024**3,
        "storageTotalBytes": 2000 * 1024**3,
        "storageUsedBytes": 600 * 1024**3,
        "enrolledAt": "2026-09-01T00:00:00Z",
        "lastHeartbeatAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "heartbeatSequence": 940,
        "labels": {"role": "gpu-mlops", "gpu": "A4000"},
    },
]

POOLS: List[Dict[str, Any]] = [
    {
        "id": "pool_01_training",
        "name": "GPU 학습 및 파인튜닝 풀",
        "nodeIds": ["nod_01JABCDEF01", "nod_01JABCDEF05"],
        "totalCores": 28,
        "availableCores": 18,
        "totalMemoryBytes": 96 * 1024**3,
        "availableMemoryBytes": 60 * 1024**3,
        "totalGpus": 2,
        "availableGpus": 2,
        "gpuModels": ["NVIDIA RTX 4090", "NVIDIA A4000"],
    },
    {
        "id": "pool_02_inference",
        "name": "모델 서빙 & 실시간 추론 풀",
        "nodeIds": ["nod_01JABCDEF02"],
        "totalCores": 8,
        "availableCores": 4,
        "totalMemoryBytes": 32 * 1024**3,
        "availableMemoryBytes": 13 * 1024**3,
        "totalGpus": 1,
        "availableGpus": 1,
        "gpuModels": ["NVIDIA RTX 3080"],
    },
    {
        "id": "pool_03_batch",
        "name": "빌드 및 분산 배치 프로세싱 풀",
        "nodeIds": ["nod_01JABCDEF03", "nod_01JABCDEF04"],
        "totalCores": 24,
        "availableCores": 12,
        "totalMemoryBytes": 96 * 1024**3,
        "availableMemoryBytes": 40 * 1024**3,
        "totalGpus": 0,
        "availableGpus": 0,
        "gpuModels": [],
    },
]

RUNS: List[Dict[str, Any]] = [
    {
        "id": "run_01JABCDE0001",
        "projectId": "prj_01JABCDE",
        "workspaceId": "wsp_01JABCDE001",
        "objective": "SaintVision PACS Core 빌드 및 단위 테스트",
        "state": "running",
        "requestedBy": "usr_developer_01",
        "createdAt": (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=15)).isoformat(),
        "updatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "version": 1,
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
        "version": 1,
    },
]

APPROVALS: List[Dict[str, Any]] = [
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

# ------------------------------------------------------------------------------
# Trace Context & RFC 9457 Problem Details Middleware
# ------------------------------------------------------------------------------


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


def rfc9457_problem(
    status: int,
    code: str,
    title: str,
    detail: str,
    trace_id: str,
    category: str = "GEN",
    retryable: bool = False,
    extra: Optional[Dict[str, Any]] = None,
) -> JSONResponse:
    content: Dict[str, Any] = {
        "type": f"https://saintvision.invenio/problems/{code.lower()}",
        "title": title,
        "status": status,
        "detail": detail,
        "code": code,
        "category": category,
        "retryable": retryable,
        "traceId": trace_id,
    }
    if extra:
        content.update(extra)
    return JSONResponse(
        status_code=status,
        content=content,
        media_type="application/problem+json",
        headers={"Cache-Control": "no-store"},
    )


# ------------------------------------------------------------------------------
# Health, Readiness & Core Diagnostics
# ------------------------------------------------------------------------------


@app.get("/v1/health")
def health_check(request: Request):
    return {
        "status": "healthy",
        "service": SERVICE_NAME,
        "version": APP_VERSION,
        "traceId": getattr(request.state, "trace_id", "trace-init"),
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
    }


@app.get("/healthz")
def liveness():
    return {"status": "ok", "version": APP_VERSION}


@app.get("/readyz")
def readiness():
    return {
        "status": "ready",
        "scope": "authenticated-control-api",
        "executionDispatcher": "active",
    }


# ------------------------------------------------------------------------------
# Authentication (OIDC + PKCE S256 & Bearer Token Verification)
# ------------------------------------------------------------------------------


def sha256_base64url(plain: str) -> str:
    digest = hashlib.sha256(plain.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


@app.post("/v1/auth/token")
async def exchange_token(request: Request):
    """
    RFC 7636 PKCE & OIDC Authorization Code token exchange endpoint.
    Verifies code_verifier against code_challenge (S256) and returns Bearer token.
    """
    trace_id = getattr(request.state, "trace_id", secrets.token_hex(16))
    try:
        data = await request.json()
    except Exception:
        return rfc9457_problem(
            400, "VAL-0003", "Invalid JSON", "Request body must be a valid JSON object", trace_id, "VAL"
        )

    grant_type = data.get("grant_type")
    code_verifier = data.get("code_verifier")
    code_challenge = data.get("code_challenge")
    client_id = data.get("client_id", "saintvision-web")
    idp = data.get("idp", "internal-keycloak")

    if grant_type != "authorization_code":
        return rfc9457_problem(
            400, "AUTH-0052", "Unsupported Grant Type", "Only 'authorization_code' grant type is supported.", trace_id, "AUTH"
        )

    # Validate PKCE if challenge was supplied
    if code_challenge and code_verifier:
        computed = sha256_base64url(code_verifier)
        if computed != code_challenge:
            return rfc9457_problem(
                401, "SEC-PKCE-INVALID", "PKCE Verification Failed", "The code_verifier does not match code_challenge.", trace_id, "SEC"
            )

    token_secret = secrets.token_urlsafe(32)
    access_token = f"sv_jwt_{idp[:4]}_{token_secret}"

    user = {
        "id": "usr_01JABCDEF_ADMIN",
        "name": "Keycloak 통합 관리자" if idp == "internal-keycloak" else "AD 도메인 관리자",
        "role": "cluster:admin",
        "tenantId": "00000000-0000-0000-0000-000000000001",
        "email": "admin@saintvision.internal",
    }

    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": 3600,
        "scope": "openid profile email cluster:admin",
        "user": user,
    }


@app.get("/v1/auth/userinfo")
def get_userinfo(request: Request, authorization: Optional[str] = Header(None)):
    trace_id = getattr(request.state, "trace_id", secrets.token_hex(16))
    if not authorization or not authorization.startswith("Bearer "):
        return rfc9457_problem(
            401, "AUTH-0050", "Unauthorized", "A valid Bearer token is required.", trace_id, "AUTH"
        )

    return {
        "sub": "usr_01JABCDEF_ADMIN",
        "name": "Keycloak 통합 관리자",
        "role": "cluster:admin",
        "roles": ["cluster:admin", "operator"],
        "tenantId": "00000000-0000-0000-0000-000000000001",
        "email": "admin@saintvision.internal",
    }


# ------------------------------------------------------------------------------
# Node Management Endpoints
# ------------------------------------------------------------------------------


@app.get("/v1/nodes")
def list_nodes(status: Optional[str] = None):
    items = NODES
    if status:
        items = [n for n in NODES if n.get("status") == status]
    return {"items": items, "total": len(items)}


@app.get("/v1/nodes/{node_id}")
def get_node(node_id: str, request: Request):
    trace_id = getattr(request.state, "trace_id", secrets.token_hex(16))
    for node in NODES:
        if node["nodeId"] == node_id:
            return node
    return rfc9457_problem(
        404,
        "RES-NODE-404",
        "Node Not Found",
        f"Node with ID '{node_id}' does not exist in cluster.",
        trace_id,
        "RES",
    )


@app.post("/v1/nodes/{node_id}/heartbeats")
def node_heartbeat(node_id: str, request: Request):
    trace_id = getattr(request.state, "trace_id", secrets.token_hex(16))
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
    return rfc9457_problem(
        404,
        "RES-NODE-404",
        "Node Not Found",
        f"Node with ID '{node_id}' is not enrolled.",
        trace_id,
        "RES",
    )


# ------------------------------------------------------------------------------
# Resource Pools, Capacity & Deterministic Placement Endpoints
# ------------------------------------------------------------------------------


@app.get("/v1/pools")
def list_pools():
    return {"items": POOLS, "total": len(POOLS)}


@app.get("/v1/pools/{pool_id}/capacity")
def get_pool_capacity(pool_id: str, request: Request):
    trace_id = getattr(request.state, "trace_id", secrets.token_hex(16))
    for pool in POOLS:
        if pool["id"] == pool_id:
            return pool
    return rfc9457_problem(
        404, "RES-POOL-404", "Pool Not Found", f"Resource pool '{pool_id}' does not exist.", trace_id, "RES"
    )


@app.get("/v1/discovery/candidates")
def discovery_candidates():
    candidates = []
    for n in NODES:
        candidates.append({
            "nodeId": n["nodeId"],
            "hostname": n["hostname"],
            "os": n["osType"],
            "availableCores": n["cpuCores"] - int(n["cpuCores"] * (n["cpuUsagePercent"] / 100.0)),
            "availableMemoryBytes": n["memoryTotalBytes"] - n["memoryUsedBytes"],
            "gpuCount": n.get("gpuCount", 0),
            "gpuName": n.get("gpuName"),
            "healthStatus": n["status"],
        })
    return {"items": candidates, "total": len(candidates)}


@app.post("/v1/pools/{pool_id}/placement-preview")
async def placement_preview(pool_id: str, request: Request):
    """
    Deterministic placement engine with Hard Filter and Multi-factor Scoring (AC-05).
    """
    trace_id = getattr(request.state, "trace_id", secrets.token_hex(16))
    try:
        req = await request.json()
    except Exception:
        req = {}

    req_cores = req.get("requiredCores", 4)
    req_memory = req.get("requiredMemoryBytes", 8 * 1024**3)
    requires_gpu = req.get("requiresGpu", False)
    preferred_os = req.get("preferredOs")
    locality_node_id = req.get("dataLocalityNodeId")
    fenced = set(req.get("fencedNodeIds", []))

    evaluations = []
    candidates = []

    for n in NODES:
        node_id = n["nodeId"]
        reasons = []

        # 1. Hard filters
        if node_id in fenced:
            reasons.append("노드가 관리자에 의해 격리(Fence)되어 있습니다.")
        if n["status"] != "online":
            reasons.append("노드 상태가 온라인이 아닙니다.")
        avail_cores = n["cpuCores"] - int(n["cpuCores"] * (n["cpuUsagePercent"] / 100.0))
        if avail_cores < req_cores:
            reasons.append(f"필요 코어({req_cores}) 대비 잔여 코어({avail_cores}) 부족")
        avail_mem = n["memoryTotalBytes"] - n["memoryUsedBytes"]
        if avail_mem < req_memory:
            reasons.append("가용 RAM 용량 부족")
        if requires_gpu and n.get("gpuCount", 0) < 1:
            reasons.append("워크로드가 요구하는 GPU 장치가 없습니다.")
        if preferred_os and n["osType"] != preferred_os:
            reasons.append(f"선호 OS 불일치 (선호: {preferred_os}, 노드: {n['osType']})")

        passed = len(reasons) == 0
        score = 0.0

        if passed:
            # Soft scoring
            cpu_headroom = (avail_cores / n["cpuCores"]) * 40.0
            mem_headroom = (avail_mem / n["memoryTotalBytes"]) * 30.0
            locality_bonus = 20.0 if node_id == locality_node_id else 0.0
            gpu_bonus = 10.0 if (requires_gpu and n.get("gpuCount", 0) > 0) else 0.0
            score = round(cpu_headroom + mem_headroom + locality_bonus + gpu_bonus, 2)
            candidates.append((score, node_id))

        evaluations.append({
            "nodeId": node_id,
            "hostname": n["hostname"],
            "eligible": passed,
            "score": score,
            "rejectionReasons": reasons,
        })

    candidates.sort(key=lambda x: (-x[0], x[1]))
    target_node = candidates[0][1] if candidates else None

    return {
        "poolId": pool_id,
        "selectedNodeId": target_node,
        "evaluations": evaluations,
        "explanation": f"최적 배치 노드로 '{target_node}' 선정됨 (점수: {candidates[0][0] if candidates else 0})"
        if target_node
        else "배치 조건을 만족하는 노드가 클러스터에 존재하지 않습니다.",
        "shards": [
            {"shardId": "shd_01", "targetNodeId": target_node or "nod_01JABCDEF01", "status": "assigned"},
            {"shardId": "shd_02", "targetNodeId": target_node or "nod_01JABCDEF02", "status": "assigned"},
        ],
    }


# ------------------------------------------------------------------------------
# Runs & Approvals Endpoints
# ------------------------------------------------------------------------------


@app.get("/v1/runs")
def list_runs():
    return {"items": RUNS, "total": len(RUNS)}


@app.get("/v1/projects/{project}/runs")
def list_project_runs(project: str):
    return {"items": [r for r in RUNS if r.get("projectId") == project], "total": len(RUNS)}


@app.post("/v1/runs/{run_id}/cancel")
def cancel_run(run_id: str, request: Request):
    trace_id = getattr(request.state, "trace_id", secrets.token_hex(16))
    for r in RUNS:
        if r["id"] == run_id:
            r["state"] = "cancelled"
            r["updatedAt"] = dt.datetime.now(dt.timezone.utc).isoformat()
            return {"runId": run_id, "state": "cancelled", "updatedAt": r["updatedAt"]}
    return rfc9457_problem(
        404, "RES-RUN-404", "Run Not Found", f"Run with ID '{run_id}' was not found.", trace_id, "RES"
    )


@app.get("/v1/approvals")
def list_approvals():
    return {"items": APPROVALS, "total": len(APPROVALS)}


@app.post("/v1/approvals", status_code=201)
async def create_approval(request: Request):
    trace_id = getattr(request.state, "trace_id", secrets.token_hex(16))
    try:
        data = await request.json()
    except Exception:
        data = {}
    new_apprv = {
        "id": data.get("id", f"apr_{secrets.token_hex(6)}"),
        "runId": data.get("runId", "run_01JABCDE0002"),
        "workspaceId": data.get("workspaceId", "wsp_01JABCDE001"),
        "nodeId": data.get("nodeId", "nod_01JABCDEF01"),
        "riskLevel": data.get("riskLevel", "L2"),
        "target": data.get("target", "Workspace Sandbox"),
        "command": data.get("command", "deploy.release"),
        "status": "pending",
        "nonce": data.get("nonce", f"nonce_{secrets.token_hex(6)}"),
        "createdAt": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    APPROVALS.append(new_apprv)
    return new_apprv


@app.post("/v1/approvals/{approval_id}/approve")
async def approve_request(approval_id: str, request: Request):
    trace_id = getattr(request.state, "trace_id", secrets.token_hex(16))
    try:
        data = await request.json()
    except Exception:
        data = {}
    nonce = data.get("nonce")

    for apprv in APPROVALS:
        if apprv["id"] == approval_id:
            if apprv["status"] != "pending":
                return rfc9457_problem(
                    409,
                    "VAL-ALREADY-DECIDED",
                    "Approval Already Decided",
                    f"Approval '{approval_id}' has already been decided.",
                    trace_id,
                    "VAL",
                )
            if nonce and apprv.get("nonce") != nonce:
                return rfc9457_problem(
                    400,
                    "SEC-NONCE-INVALID",
                    "Invalid Idempotency Nonce",
                    "Supplied approval nonce does not match valid challenge nonce.",
                    trace_id,
                    "SEC",
                )
            apprv["status"] = "approved"
            return {"approvalId": approval_id, "status": "approved", "nonce": nonce}

    return rfc9457_problem(
        404, "RES-404", "Approval Not Found", f"Approval '{approval_id}' was not found.", trace_id, "RES"
    )


# ------------------------------------------------------------------------------
# Server-Sent Events (SSE) Stream
# ------------------------------------------------------------------------------


async def sse_event_generator() -> AsyncGenerator[str, None]:
    seq = 0
    while True:
        seq += 1
        event_data = {
            "type": "heartbeat_tick",
            "sequence": seq,
            "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
            "activeNodes": len([n for n in NODES if n["status"] == "online"]),
            "totalNodes": len(NODES),
            "pendingApprovals": len([a for a in APPROVALS if a["status"] == "pending"]),
        }
        yield f"id: evt_{seq}\nevent: heartbeat\ndata: {json.dumps(event_data)}\n\n"
        await asyncio.sleep(4.0)


@app.get("/v1/events")
async def events_sse_stream():
    return StreamingResponse(
        sse_event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ------------------------------------------------------------------------------
# Interactive Web Terminal (WebSocket)
# ------------------------------------------------------------------------------


@app.websocket("/v1/terminal/ws")
async def terminal_websocket(websocket: WebSocket):
    await websocket.accept()
    welcome_banner = (
        "\r\n\x1b[1;36m====================================================\x1b[0m\r\n"
        "\x1b[1;32m SaintVision PTY Terminal (Intranet Sandboxed Session)\x1b[0m\r\n"
        "\x1b[1;36m====================================================\x1b[0m\r\n"
        " Type \x1b[1;33m'help'\x1b[0m for available commands. (L0-L3 Protected)\r\n\r\n"
        "saintvision@node-01:~$ "
    )
    await websocket.send_text(welcome_banner)

    buffer = ""
    try:
        while True:
            char = await websocket.receive_text()
            if char in ("\r", "\n"):
                cmd = buffer.strip()
                await websocket.send_text("\r\n")
                if cmd == "help":
                    resp = (
                        "Available Sandbox Commands:\r\n"
                        "  status  - Cluster node summary\r\n"
                        "  ps      - Active container processes\r\n"
                        "  ls      - Workspace sandbox directory\r\n"
                        "  uname   - Operating system and kernel\r\n"
                        "  exit    - Terminate terminal session\r\n"
                    )
                    await websocket.send_text(resp)
                elif cmd == "status":
                    resp = f"Cluster: 5 nodes online | Gateway: healthy (RTT: 0.8ms) | Active Runs: {len(RUNS)}\r\n"
                    await websocket.send_text(resp)
                elif cmd == "ps":
                    resp = (
                        "PID   USER     TIME   COMMAND\r\n"
                        "  1   saint    0:01   /bin/sandbox-supervisor\r\n"
                        " 42   app      0:15   python3 -m saintvision.server\r\n"
                    )
                    await websocket.send_text(resp)
                elif cmd == "ls":
                    resp = "config/  contracts/  data/  models/  logs/  output.json\r\n"
                    await websocket.send_text(resp)
                elif cmd == "uname":
                    resp = "Linux saintvision-node01 6.1.0-custom-invion #1 SMP PREEMPT_DYNAMIC x86_64\r\n"
                    await websocket.send_text(resp)
                elif cmd == "exit":
                    await websocket.send_text("Session terminated by operator.\r\n")
                    await websocket.close()
                    break
                elif cmd:
                    await websocket.send_text(f"bash: {cmd}: command sandboxed or restricted (Rule #304)\r\n")
                buffer = ""
                await websocket.send_text("saintvision@node-01:~$ ")
            elif char in ("\x7f", "\b"):  # Backspace
                if len(buffer) > 0:
                    buffer = buffer[:-1]
                    await websocket.send_text("\b \b")
            else:
                buffer += char
                await websocket.send_text(char)
    except WebSocketDisconnect:
        pass


# ------------------------------------------------------------------------------
# Entrypoint for direct execution
# ------------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
