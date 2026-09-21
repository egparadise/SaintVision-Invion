"""Discovery, pool and placement endpoints.

The announcement endpoint is the only one here that an unenrolled machine may
call, and it is deliberately the least powerful: it writes a candidate row and
returns nothing about the platform. Everything that changes what runs where
requires a user credential.
"""

from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from sqlalchemy.orm import Session

from ...config import Settings
from ...db.session import make_session_factory, tenant_scope
from ...errors import VAL_SCHEMA, InvError
from ...identity.principal import Principal
from ...services import discovery as discovery_service
from ...services import pools as pool_service
from ...services import projects as project_service
from ...services.audit import record_event
from ...units import CANONICAL_UNIT
from .. import schemas
from ..deps import get_now, get_principal, get_session, get_settings

router = APIRouter(prefix="/v1", tags=["pools"])


def _tenant(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise InvError(VAL_SCHEMA, "X-Inv-Tenant must be a UUID") from None


@router.post("/discovery/announcements", status_code=202)
def announce(
    request: Request,
    payload: schemas.AnnouncementRequest,
    tenant: str = Header(alias="X-Inv-Tenant"),
    now: dt.datetime = Depends(get_now),
) -> dict:
    """A Node Agent announces itself on the internal network.

    Unenrolled machines call this, so it grants nothing: the row it writes is a
    candidate a person must still admit. The source address is taken from the
    connection rather than the body — a field the announcer controls cannot be
    part of its own identity.

    The response deliberately carries no platform detail. An unauthenticated
    caller learns only that the announcement was accepted.
    """
    tenant_id = _tenant(tenant)
    request.state.actor_type = "node"
    request.state.tenant_id = tenant_id
    source_ip = request.client.host if request.client else "0.0.0.0"

    factory = make_session_factory(request.app.state.engine)
    with factory() as session:
        with session.begin():
            with tenant_scope(session, tenant_id):
                row = discovery_service.record_announcement(
                    session,
                    tenant_id=tenant_id,
                    source_ip=source_ip,
                    announcement=discovery_service.Announcement(
                        instance_id=payload.instance_id,
                        hostname=payload.hostname,
                        os_type=payload.os_type,
                        os_version=payload.os_version,
                        agent_version=payload.agent_version,
                        cpu_cores=payload.cpu_cores,
                        ram_bytes=payload.ram_bytes,
                        gpu_count=payload.gpu_count,
                        labels=payload.labels,
                    ),
                    now=now,
                )
                state = row.state
    return {"accepted": True, "state": state}


@router.get(
    "/discovery/candidates", response_model=schemas.DiscoveryCandidatesResponse
)
def list_candidates(
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
    now: dt.datetime = Depends(get_now),
    include_stale: bool = Query(default=False, alias="includeStale"),
) -> schemas.DiscoveryCandidatesResponse:
    """Machines a person can choose to admit.

    Every self-reported field is named ``claimed*`` and every row carries
    ``verified: false``, so a screen cannot present an announcement as a
    measurement.
    """
    items = discovery_service.list_candidates(
        session, tenant_id=principal.tenant_id, now=now, include_stale=include_stale
    )
    return schemas.DiscoveryCandidatesResponse(
        items=items,
        note="All claimed* values are self-reported by the machine and unverified.",
    )


@router.post("/discovery/candidates/{announcement_id}/admission", status_code=201)
def admit(
    request: Request,
    announcement_id: str,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    now: dt.datetime = Depends(get_now),
) -> dict:
    """Admit a candidate: mint its one-time enrollment token.

    The token is returned once and never stored in plaintext. Admission does
    not create the node — the agent still exchanges the token through
    ``POST /v1/nodes``, where identity and capabilities are established over an
    authenticated channel.
    """
    issued = discovery_service.admit_candidate(
        session,
        tenant_id=principal.tenant_id,
        announcement_id=announcement_id,
        admitted_by_user_id=principal.user_id,
        now=now,
        ttl_seconds=settings.bootstrap_token_ttl_seconds,
    )
    record_event(
        session,
        now=now,
        actor_type="user",
        actor_id=principal.user_id,
        action="discovery.candidate.admit",
        outcome="allow",
        tenant_id=principal.tenant_id,
        trace_id=getattr(request.state, "trace_id", None),
        target_type="announcement",
        target_id=announcement_id,
    )
    return {
        "announcementId": announcement_id,
        # Returned once. Never logged, never stored in plaintext.
        "bootstrapToken": issued.secret,
        "expiresAt": issued.expires_at.isoformat(),
        "next": "POST /v1/nodes with this token to complete enrollment",
    }


@router.delete("/discovery/candidates/{announcement_id}")
def decline(
    announcement_id: str,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
    now: dt.datetime = Depends(get_now),
    reason: str | None = Query(default=None),
) -> dict:
    row = discovery_service.decline_candidate(
        session,
        tenant_id=principal.tenant_id,
        announcement_id=announcement_id,
        now=now,
        reason=reason,
    )
    return {"announcementId": row.announcement_id, "state": row.state}


@router.post("/pools", status_code=201, response_model=schemas.PoolCreatedResponse)
def create_pool(
    payload: schemas.PoolRequest,
    response: Response,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
    now: dt.datetime = Depends(get_now),
) -> dict:
    # Read now, not from the credential: a project created a moment ago
    # belongs to its creator, and a membership revoked a moment ago is
    # gone. A set fixed at sign-in expresses neither.
    project_service.require_project_access(
        session,
        tenant_id=principal.tenant_id,
        project_id=payload.project_id,
        user_id=principal.user_id,
    )
    pool = pool_service.create_pool(
        session,
        tenant_id=principal.tenant_id,
        project_id=payload.project_id,
        name=payload.name,
        description=payload.description,
        created_by_user_id=principal.user_id,
        now=now,
    )
    response.headers["Location"] = f"/v1/pools/{pool.pool_id}"
    return {"poolId": pool.pool_id, "name": pool.name}


@router.put(
    "/pools/{pool_id}/members/{node_id}",
    status_code=200,
    response_model=schemas.PoolMemberResponse,
)
def add_member(
    pool_id: str,
    node_id: str,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
    now: dt.datetime = Depends(get_now),
) -> dict:
    pool_service.add_member(
        session,
        tenant_id=principal.tenant_id,
        pool_id=pool_id,
        node_id=node_id,
        added_by_user_id=principal.user_id,
        now=now,
    )
    return {"poolId": pool_id, "nodeId": node_id, "member": True}


@router.delete(
    "/pools/{pool_id}/members/{node_id}",
    response_model=schemas.PoolMemberRemovalResponse,
)
def remove_member(
    pool_id: str,
    node_id: str,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict:
    removed = pool_service.remove_member(
        session, tenant_id=principal.tenant_id, pool_id=pool_id, node_id=node_id
    )
    return {"poolId": pool_id, "nodeId": node_id, "removed": removed}


@router.get("/pools/{pool_id}/capacity", response_model=schemas.PoolCapacityResponse)
def pool_capacity(
    pool_id: str,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
    now: dt.datetime = Depends(get_now),
) -> dict:
    """Aggregate capacity — three figures, never one.

    ``totalOffered`` is the sum, ``largestSingleNode`` is the ceiling for one
    task that cannot be split, and ``spareNow`` is what is idle. A caller that
    showed only the sum would be telling someone a 160 GB pool runs a 64 GB
    job; it does not, unless the job shards.
    """
    return pool_service.pool_capacity(
        session, tenant_id=principal.tenant_id, pool_id=pool_id, now=now
    )


@router.get(
    "/pools/{pool_id}/placement-preview",
    response_model=schemas.PlacementPreviewResponse,
)
def placement_preview(
    pool_id: str,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
    now: dt.datetime = Depends(get_now),
    cpu_millicores: int = Query(default=0, ge=0, alias="cpuMillicores"),
    ram_bytes: int = Query(default=0, ge=0, alias="ramBytes"),
    gpu_devices: int = Query(default=0, ge=0, alias="gpuDevices"),
) -> dict:
    """Which nodes could hold one shard, idlest first, without placing anything."""
    ranked = pool_service.rank_idle_first(
        session,
        tenant_id=principal.tenant_id,
        pool_id=pool_id,
        requirement=pool_service.ShardRequirement(
            cpu_millicores=cpu_millicores,
            ram_bytes=ram_bytes,
            gpu_devices=gpu_devices,
        ),
        now=now,
    )
    return {
        "poolId": pool_id,
        "candidates": ranked,
        "candidateCount": len(ranked),
        "units": dict(CANONICAL_UNIT),
    }


@router.post(
    "/pools/{pool_id}/plans",
    status_code=201,
    response_model=schemas.DistributedPlanResponse,
)
def create_plan(
    pool_id: str,
    payload: schemas.DistributedPlanRequest,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
    now: dt.datetime = Depends(get_now),
) -> dict:
    """Spread one Run over the idlest nodes that fit.

    Refuses to split work the caller has not declared splittable, and refuses a
    partial placement — three of five shards running would report success for a
    job that did not happen.
    """
    plan, placements = pool_service.plan_distributed_run(
        session,
        tenant_id=principal.tenant_id,
        run_id=payload.run_id,
        pool_id=pool_id,
        strategy=payload.strategy,
        shard_count=payload.shard_count,
        requirement=pool_service.ShardRequirement(
            cpu_millicores=payload.shard_cpu_millicores,
            ram_bytes=payload.shard_ram_bytes,
            gpu_devices=payload.shard_gpu_devices,
        ),
        splittable_declared=payload.splittable_declared,
        now=now,
    )
    return {
        "planId": plan.plan_id,
        "runId": plan.run_id,
        "strategy": plan.strategy,
        "shardCount": plan.shard_count,
        "units": dict(CANONICAL_UNIT),
        "placements": [
            {
                "shardIndex": p.shard_index,
                "nodeId": p.node_id,
                "assignedCpuMillicores": p.assigned_cpu_millicores,
                "assignedRamBytes": p.assigned_ram_bytes,
                "assignedGpuDevices": p.assigned_gpu_devices,
            }
            for p in placements
        ],
    }
