"""Discovery, pool and placement endpoints.

An agent may announce before node enrollment using either an authenticated
principal or a narrow tenant/installation-bound discovery grant. The
announcement remains deliberately least-powerful: it writes only one
unverified candidate. Admission and everything that changes what runs where
still require a user credential.
"""

from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...config import Settings
from ...db.models import (
    DiscoveryCredentialEvent,
    DiscoveryMachineCredential,
    NodeAnnouncement,
    ResourcePool,
    ResourcePoolMember,
    Run,
    Workload,
)
from ...db.session import make_session_factory, tenant_scope
from ...errors import (
    AUTH_INVALID_CREDENTIAL,
    AUTH_PROJECT_SCOPE,
    AUTH_TENANT_SCOPE,
    GRAPH_INVALID_TRANSITION,
    VAL_SCHEMA,
    InvError,
)
from ...identity.discovery_credentials import (
    reject_discovery_credential,
    token_sha256,
    validate_discovery_grant,
)
from ...identity.principal import Principal
from ...services import discovery as discovery_service
from ...services import pools as pool_service
from ...services import projects as project_service
from ...services import settings as settings_service
from ...services.audit import record_event
from ...units import CANONICAL_UNIT
from .. import schemas
from ..deps import get_now, get_principal, get_session, get_settings

router = APIRouter(prefix="/v1", tags=["pools"])

_POOL_UNIQUE_CONFLICTS = {
    "uq_resource_pools_tenant_id_name": "a resource pool with this name already exists",
    "uq_distributed_plans_run_id": "this run already has a distributed plan",
}
_POOL_MEMBER_PRIMARY_KEY = "resource_pool_members_pkey"


def _constraint_name(error: IntegrityError, known: set[str]) -> str | None:
    original = error.orig
    constraint = getattr(getattr(original, "diag", None), "constraint_name", None)
    if constraint is not None:
        return constraint
    detail = str(original)
    return next((name for name in known if name in detail), None)


def _translate_pool_conflict(error: IntegrityError) -> InvError | None:
    constraint = _constraint_name(error, set(_POOL_UNIQUE_CONFLICTS))
    if constraint in _POOL_UNIQUE_CONFLICTS:
        return InvError(
            GRAPH_INVALID_TRANSITION,
            _POOL_UNIQUE_CONFLICTS[constraint],
            status=409,
        )
    return None


def _require_pool_write_access(
    session: Session, *, tenant_id: uuid.UUID, pool_id: str, user_id: str
) -> ResourcePool:
    """Lock the project authority before the pool and revalidate both.

    The first read discovers the project's lock key only. Membership writers
    serialize on that project row, so taking it before the final permission
    check closes the revoke-vs-write race. The pool is then locked and its
    project binding is revalidated in the same transaction.
    """
    project_id = session.scalar(
        select(ResourcePool.project_id).where(
            ResourcePool.tenant_id == tenant_id,
            ResourcePool.pool_id == pool_id,
        )
    )
    if project_id is None:
        raise InvError(
            AUTH_PROJECT_SCOPE,
            "project is not accessible to this principal",
        )
    settings_service.lock_project(session, tenant_id, project_id)
    try:
        permission = project_service.require_project_access(
            session,
            tenant_id=tenant_id,
            project_id=project_id,
            user_id=user_id,
        )
    except InvError as error:
        if error.code != AUTH_PROJECT_SCOPE:
            raise
        # ``project_id`` was derived from a pool the caller cannot see.  Do not
        # expose it through require_project_access's otherwise useful extra.
        raise InvError(
            AUTH_PROJECT_SCOPE,
            "project is not accessible to this principal",
        ) from None
    if not permission["canRequest"]:
        raise InvError(
            AUTH_PROJECT_SCOPE,
            "project is not accessible to this principal",
        )
    pool = session.scalar(
        select(ResourcePool)
        .where(
            ResourcePool.tenant_id == tenant_id,
            ResourcePool.pool_id == pool_id,
            ResourcePool.project_id == project_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if pool is None:
        raise InvError(
            AUTH_PROJECT_SCOPE,
            "project is not accessible to this principal",
        )
    return pool


def _require_plan_write_access(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    pool_id: str,
    run_id: str,
    user_id: str,
) -> ResourcePool:
    pool = _require_pool_write_access(
        session,
        tenant_id=tenant_id,
        pool_id=pool_id,
        user_id=user_id,
    )
    run = session.scalar(
        select(Run)
        .where(Run.tenant_id == tenant_id, Run.run_id == run_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    workload = (
        session.get(Workload, run.workload_id, populate_existing=True) if run is not None else None
    )
    if (
        workload is None
        or workload.tenant_id != tenant_id
        or workload.project_id != pool.project_id
    ):
        raise InvError(
            AUTH_PROJECT_SCOPE,
            "project is not accessible to this principal",
        )
    return pool


def _tenant(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise InvError(VAL_SCHEMA, "X-Inv-Tenant must be a UUID") from None


@router.post(
    "/discovery/announcements",
    status_code=202,
    response_model=schemas.DiscoveryAnnouncementResponse,
)
def announce(
    request: Request,
    payload: schemas.AnnouncementRequest,
    tenant: str = Header(alias="X-Inv-Tenant"),
    authorization: str | None = Header(default=None),
    now: dt.datetime = Depends(get_now),
) -> dict:
    """A Node Agent announces itself on the internal network.

    An interactive caller's principal or a machine grant bound to one tenant
    supplies the authority; the caller-controlled tenant header is only a
    consistency assertion for the machine path. The row is still only a
    candidate that a person must admit. The source address is taken from the
    connection rather than the body — a field the announcer controls cannot
    be part of its own identity.

    The response deliberately carries no platform detail.
    """
    source_ip = request.client.host if request.client else "0.0.0.0"

    bearer = (
        authorization.split(" ", 1)[1].strip()
        if authorization and authorization.lower().startswith("bearer ")
        else None
    )
    if bearer and bearer.startswith("dsc1_"):
        digest = token_sha256(bearer)
        factory = make_session_factory(request.app.state.engine)
        denied = False
        response_state: str | None = None
        with factory() as session:
            with session.begin():
                # Digest-scoped lookup obtains tenant identity from the grant;
                # the caller's tenant header is checked only after this read.
                session.execute(
                    text("SELECT set_config('inv.discovery_token_sha256', :digest, true)"),
                    {"digest": digest},
                )
                grant = session.scalar(
                    select(DiscoveryMachineCredential)
                    .where(DiscoveryMachineCredential.token_sha256 == digest)
                    .with_for_update()
                )
                if grant is None:
                    denied = True
                else:
                    tenant_id = grant.tenant_id
                    with tenant_scope(session, tenant_id):
                        grant_data = {
                            "token_sha256": grant.token_sha256,
                            "tenant_id": grant.tenant_id,
                            "installation_id": grant.installation_id,
                            "scope": grant.scope,
                            "revoked_at": grant.revoked_at,
                            "expires_at": grant.expires_at,
                            "last_announcement_at": grant.last_announcement_at,
                        }
                        try:
                            validate_discovery_grant(
                                grant_data,
                                token=bearer,
                                asserted_tenant=tenant,
                                installation_id=payload.instance_id,
                                now=now,
                            )
                            if grant.announcement_id is None:
                                prior = session.scalar(
                                    select(NodeAnnouncement).where(
                                        NodeAnnouncement.tenant_id == tenant_id,
                                        NodeAnnouncement.instance_id == payload.instance_id,
                                        NodeAnnouncement.source_ip == source_ip,
                                    )
                                )
                                if prior is not None and prior.state != "candidate":
                                    reject_discovery_credential()
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
                                linked_announcement_id=grant.announcement_id,
                            )
                            if row.state != "candidate":
                                reject_discovery_credential()
                            grant.announcement_id = row.announcement_id
                            grant.last_announcement_at = now
                            response_state = row.state
                            session.add(
                                DiscoveryCredentialEvent(
                                    event_id=uuid.uuid4(),
                                    tenant_id=tenant_id,
                                    credential_id=grant.credential_id,
                                    installation_id=grant.installation_id,
                                    actor="machine",
                                    event_type="announced",
                                    outcome="allow",
                                    reason_code="discovery_refresh",
                                    occurred_at=now,
                                )
                            )
                        except InvError as error:
                            if error.code != AUTH_INVALID_CREDENTIAL:
                                raise
                            denied = True
                            session.add(
                                DiscoveryCredentialEvent(
                                    event_id=uuid.uuid4(),
                                    tenant_id=tenant_id,
                                    credential_id=grant.credential_id,
                                    installation_id=grant.installation_id,
                                    actor="machine",
                                    event_type="denied",
                                    outcome="deny",
                                    reason_code=getattr(error, "reason_code", "grant_rejected"),
                                    occurred_at=now,
                                )
                            )
        if denied:
            reject_discovery_credential()
        return {"accepted": True, "state": response_state}

    # Existing interactive/OIDC callers keep their current contract. This
    # discovery-only credential is not accepted by get_principal or any other
    # route.
    principal = get_principal(request, authorization)
    tenant_id = _tenant(tenant)
    if tenant_id != principal.tenant_id:
        raise InvError(
            AUTH_TENANT_SCOPE,
            "X-Inv-Tenant does not match the authenticated principal",
            403,
        )

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


@router.get("/discovery/candidates", response_model=schemas.DiscoveryCandidatesResponse)
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


@router.post(
    "/discovery/candidates/{announcement_id}/admission",
    status_code=201,
    response_model=schemas.DiscoveryAdmissionResponse,
)
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


@router.delete(
    "/discovery/candidates/{announcement_id}",
    response_model=schemas.DiscoveryDeclineResponse,
)
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


@router.get("/pools", response_model=schemas.PoolListResponse)
def list_pools(
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict:
    """List tenant pools; capacity remains a separate time-sensitive read."""
    return pool_service.list_pools(session, tenant_id=principal.tenant_id)


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
    try:
        pool = pool_service.create_pool(
            session,
            tenant_id=principal.tenant_id,
            project_id=payload.project_id,
            name=payload.name,
            description=payload.description,
            created_by_user_id=principal.user_id,
            now=now,
        )
    except IntegrityError as error:
        conflict = _translate_pool_conflict(error)
        if conflict is not None:
            raise conflict from None
        raise
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
    _require_pool_write_access(
        session,
        tenant_id=principal.tenant_id,
        pool_id=pool_id,
        user_id=principal.user_id,
    )
    try:
        with session.begin_nested():
            pool_service.add_member(
                session,
                tenant_id=principal.tenant_id,
                pool_id=pool_id,
                node_id=node_id,
                added_by_user_id=principal.user_id,
                now=now,
            )
    except IntegrityError as error:
        constraint = _constraint_name(error, {_POOL_MEMBER_PRIMARY_KEY})
        if constraint != _POOL_MEMBER_PRIMARY_KEY:
            raise
        # PUT is idempotent. After the savepoint rollback, accept only if the
        # exact membership that won the race is now visible.
        existing = session.get(
            ResourcePoolMember,
            (principal.tenant_id, pool_id, node_id),
            populate_existing=True,
        )
        if existing is None:
            raise
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
    _require_pool_write_access(
        session,
        tenant_id=principal.tenant_id,
        pool_id=pool_id,
        user_id=principal.user_id,
    )
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
    _require_plan_write_access(
        session,
        tenant_id=principal.tenant_id,
        pool_id=pool_id,
        run_id=payload.run_id,
        user_id=principal.user_id,
    )
    try:
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
    except IntegrityError as error:
        conflict = _translate_pool_conflict(error)
        if conflict is not None:
            raise conflict from None
        raise
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
