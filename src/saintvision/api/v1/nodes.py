"""Node registration, heartbeat and listing endpoints (S02-BE).

Subresource naming follows PLAN-BACKEND-001: ``/heartbeats`` rather than a verb
on the node itself.

Enrollment authenticates with a bootstrap token in the body, not with a user
credential: the node agent has no user identity until it is enrolled. That is
the "different authentication context" the ADR calls out, and it is why this one
endpoint does not depend on ``get_principal``.
"""

from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from sqlalchemy.orm import Session

from ...config import Settings
from ...db.session import make_session_factory, tenant_scope
from ...errors import VAL_SCHEMA, InvError
from ...identity.node_auth import authenticate_node
from ...identity.principal import Principal
from ...services import nodes as node_service
from ...services.audit import record_event
from .. import schemas
from ..deps import get_now, get_principal, get_session, get_settings

router = APIRouter(prefix="/v1", tags=["nodes"])


def _node_body(node) -> dict:
    return schemas.NodeResponse(
        nodeId=node.node_id,
        hostname=node.hostname,
        osType=node.os_type,
        osVersion=node.os_version,
        agentVersion=node.agent_version,
        status=node.status,
        enrolledAt=node.enrolled_at,
        lastHeartbeatAt=node.last_heartbeat_at,
        heartbeatSequence=node.heartbeat_sequence,
        labels=node.labels or {},
    ).model_dump(by_alias=True, mode="json")


@router.post("/nodes", status_code=201)
def enroll_node(
    request: Request,
    payload: schemas.NodeEnrollRequest,
    response: Response,
    tenant: str = Header(alias="X-Inv-Tenant"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    now: dt.datetime = Depends(get_now),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Exchange a one-time bootstrap token for an enrolled node.

    The tenant comes from a header here because the caller is a node agent with
    no principal yet. That is safe only because the bootstrap token is itself
    tenant-bound: a token from tenant A presented with tenant B's header fails
    to consume, since the UPDATE runs inside B's scope and cannot see A's row.
    """
    try:
        tenant_id = uuid.UUID(tenant)
    except ValueError:
        raise InvError(VAL_SCHEMA, "X-Inv-Tenant must be a UUID") from None

    request.state.actor_type = "node"
    request.state.tenant_id = tenant_id

    factory = make_session_factory(request.app.state.engine)
    with factory() as session:
        with session.begin():
            with tenant_scope(session, tenant_id):
                capabilities = [
                    node_service.CapabilityInput(
                        kind=c.kind,
                        total_quantity=c.total_quantity,
                        unit=c.unit,
                        device_index=c.device_index,
                        vendor=c.vendor,
                        model=c.model,
                        divisible=c.divisible,
                        offered_quantity=c.offered_quantity,
                    )
                    for c in payload.capabilities
                ]
                node = node_service.enroll_node(
                    session,
                    tenant_id=tenant_id,
                    bootstrap_secret=payload.bootstrap_token,
                    hostname=payload.hostname,
                    os_type=payload.os_type,
                    os_version=payload.os_version,
                    agent_version=payload.agent_version,
                    capabilities=capabilities,
                    certificate_fingerprint=payload.certificate_fingerprint,
                    labels=payload.labels,
                    now=now,
                )
                body = {"node": _node_body(node)}
                record_event(
                    session,
                    now=now,
                    actor_type="node",
                    actor_id=node.node_id,
                    action="node.enroll",
                    outcome="allow",
                    tenant_id=tenant_id,
                    trace_id=getattr(request.state, "trace_id", None),
                    target_type="node",
                    target_id=node.node_id,
                    detail={"hostname": node.hostname, "osType": node.os_type},
                    source_ip=request.client.host if request.client else None,
                    user_agent=request.headers.get("user-agent"),
                )
    response.headers["Location"] = f"/v1/nodes/{body['node']['nodeId']}"
    return body


@router.post("/nodes/{node_id}/heartbeats", status_code=202)
def post_heartbeat(
    request: Request,
    node_id: str,
    payload: schemas.HeartbeatRequest,
    now: dt.datetime = Depends(get_now),
) -> dict:
    """Record a heartbeat and any observations that came with it.

    Authenticated by the node's client certificate, not by a header. The tenant
    and the node identity both come from the verified certificate: previously
    this route took ``X-Inv-Tenant`` and a path id and checked neither, so any
    caller who knew a node id could keep a removed machine looking alive or
    inject utilisation figures that steer placement onto it.

    Idempotent by sequence rather than by an Idempotency-Key header: heartbeats
    are frequent and self-numbering, and a replayed one must be ignored, not
    replayed back (ADR-007).
    """
    factory = make_session_factory(request.app.state.engine)

    # Authenticate before opening a tenant scope: the credential decides which
    # tenant this is, so a scope opened first would be a scope chosen by the
    # caller.
    with factory() as auth_session:
        with auth_session.begin():
            principal = authenticate_node(
                auth_session,
                scope=request.scope,
                headers={k.lower(): v for k, v in request.headers.items()},
                peer_address=request.client.host if request.client else None,
            )
    principal.require_node(node_id)
    tenant_id = principal.tenant_id

    request.state.actor_type = "node"
    request.state.actor_id = principal.node_id
    request.state.tenant_id = tenant_id

    with factory() as session:
        with session.begin():
            with tenant_scope(session, tenant_id):
                principal.lock_current(session)
                # The read-then-compare that used to decide `applied` is gone.
                # Two heartbeats arriving together both read the old sequence
                # and both concluded they had advanced it; the database now
                # decides, once, while holding the row.
                outcome = node_service.record_heartbeat(
                    session,
                    tenant_id=tenant_id,
                    node_id=principal.node_id,
                    sequence=payload.sequence,
                    now=now,
                )
                if outcome.applied:
                    # Observations ride on the beat that won. Recording them for
                    # a stale beat would file utilisation under a timestamp the
                    # node has already moved past, and placement reads these.
                    node_service.record_observations(
                        session,
                        tenant_id=tenant_id,
                        node_id=principal.node_id,
                        observations=[
                            node_service.ObservationInput(
                                capability_id=o.capability_id,
                                used_quantity=o.used_quantity,
                                unit=o.unit,
                            )
                            for o in payload.observations
                        ],
                        now=now,
                    )
                result = {
                    "nodeId": outcome.node.node_id,
                    "applied": outcome.applied,
                    "heartbeatSequence": outcome.node.heartbeat_sequence,
                }
    return result


@router.post("/nodes/liveness-sweeps", status_code=200)
def sweep_liveness(
    request: Request,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    now: dt.datetime = Depends(get_now),
) -> dict:
    """Mark nodes whose heartbeat has aged out as lost.

    Exposed as an endpoint rather than hidden inside a GET, because it mutates:
    a read that quietly changes status is a read you cannot trust or repeat.

    Who calls it on a timer is the same open question as the monthly partition
    job — the scheduler is an S01-BE decision (config.S01_PENDING). The 60
    second detection target in the final plan is met only once something does
    call it at that cadence; this endpoint makes that possible, it does not by
    itself satisfy the target.
    """
    changed = node_service.mark_lost_nodes(
        session,
        tenant_id=principal.tenant_id,
        now=now,
        timeout_seconds=settings.heartbeat_timeout_seconds,
    )
    if changed:
        record_event(
            session,
            now=now,
            actor_type="system",
            actor_id=principal.user_id,
            action="node.liveness.sweep",
            outcome="allow",
            tenant_id=principal.tenant_id,
            trace_id=getattr(request.state, "trace_id", None),
            detail={"markedLost": changed, "timeoutSeconds": settings.heartbeat_timeout_seconds},
        )
    return {
        "markedLost": changed,
        "timeoutSeconds": settings.heartbeat_timeout_seconds,
    }


@router.get("/nodes", response_model=schemas.NodePageResponse)
def list_nodes(
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    limit: int | None = Query(default=None, ge=1),
    cursor: str | None = Query(default=None),
    status: str | None = Query(default=None),
) -> dict:
    page = node_service.list_nodes(
        session,
        tenant_id=principal.tenant_id,
        limit=limit,
        cursor=cursor,
        status=status,
        default_limit=settings.page_limit_default,
        max_limit=settings.page_limit_max,
    )
    return page.to_dict(_node_body)


@router.get("/nodes/{node_id}", response_model=schemas.NodeDetailResponse)
def get_node(
    node_id: str,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict:
    node = node_service.get_node(session, tenant_id=principal.tenant_id, node_id=node_id)
    capabilities = node_service.list_capabilities(
        session, tenant_id=principal.tenant_id, node_id=node_id
    )
    return {
        "node": _node_body(node),
        "capabilities": [
            {
                "capabilityId": c.capability_id,
                "kind": c.kind,
                "deviceIndex": c.device_index,
                "vendor": c.vendor,
                "model": c.model,
                "totalQuantity": float(c.total_quantity),
                "unit": c.unit,
                "divisible": c.divisible,
            }
            for c in capabilities
        ],
    }
