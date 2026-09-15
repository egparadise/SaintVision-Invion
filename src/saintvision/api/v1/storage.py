"""Contributed folder and data location endpoints (S02-ST).

Registering a contribution is the "important mutation" this sprint has, so it
carries the durable idempotency ledger (ADR-007): a retried registration returns
the first response instead of creating a second contribution, and the same key
with a different body is a conflict.
"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy.orm import Session

from ...config import Settings
from ...identity.principal import Principal
from ...errors import InvError, RES_ARTIFACT_NOT_FOUND, VAL_SCHEMA
from ...services import resolver
from ...services.replica_observation import observe_replicas
from ...services import storage as storage_service
from ...services.audit import record_event
from .. import schemas
from ..deps import (
    get_now,
    get_principal,
    get_session,
    get_settings,
    replay_or_reserve,
    store_idempotent_response,
)

router = APIRouter(prefix="/v1", tags=["storage"])


def _contribution_body(contribution) -> dict:
    return schemas.ContributionResponse(
        contributionId=contribution.contribution_id,
        nodeId=contribution.node_id,
        declaredPath=contribution.declared_path,
        normalizedPath=contribution.normalized_path,
        mode=contribution.mode,
        status=contribution.status,
        capacityBytes=contribution.capacity_bytes,
        availableBytes=contribution.available_bytes,
        registeredAt=contribution.registered_at,
    ).model_dump(by_alias=True, mode="json")


def _location_body(location) -> dict:
    return schemas.DataLocationResponse(
        locationId=location.location_id,
        contributionId=location.contribution_id,
        uri=location.uri,
        kind=location.kind,
        relativePath=location.relative_path,
        byteSize=location.byte_size,
        checksumSha256=location.checksum_sha256,
        ready=location.ready,
        verifiedAt=location.verified_at,
        retentionPinnedUntil=location.retention_pinned_until,
    ).model_dump(by_alias=True, mode="json")


@router.post("/storage/contributions", status_code=201)
def register_contribution(
    request: Request,
    payload: schemas.ContributionRequest,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    now: dt.datetime = Depends(get_now),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    endpoint = "POST /v1/storage/contributions"
    body_for_hash = payload.model_dump(by_alias=True, mode="json")

    replayed = replay_or_reserve(
        session,
        principal=principal,
        endpoint=endpoint,
        idempotency_key=idempotency_key,
        payload=body_for_hash,
        now=now,
        ttl_seconds=settings.idempotency_ttl_seconds,
        # Registering a contribution is tenant-wide: a folder belongs to a
        # node, not a project. Recorded as None so it collides with other
        # tenant-wide operations and not with a project's.
        project_id=None,
    )
    if replayed is not None:
        return replayed

    contribution = storage_service.register_contribution(
        session,
        tenant_id=principal.tenant_id,
        registered_by_user_id=principal.user_id,
        payload=storage_service.ContributionInput(
            node_id=payload.node_id,
            declared_path=payload.declared_path,
            mode=payload.mode,
            capacity_bytes=payload.capacity_bytes,
            available_bytes=payload.available_bytes,
        ),
        now=now,
    )
    body = {"contribution": _contribution_body(contribution)}

    record_event(
        session,
        now=now,
        actor_type="user",
        actor_id=principal.user_id,
        action="storage.contribution.register",
        outcome="allow",
        tenant_id=principal.tenant_id,
        trace_id=getattr(request.state, "trace_id", None),
        target_type="storage_contribution",
        target_id=contribution.contribution_id,
        # The normalised path is recorded; the raw declared string is not, since
        # it is attacker-influenced text.
        detail={"nodeId": contribution.node_id, "normalizedPath": contribution.normalized_path},
        source_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    store_idempotent_response(
        session,
        principal=principal,
        endpoint=endpoint,
        idempotency_key=idempotency_key,
        payload=body_for_hash,
        response_status=201,
        response_body=body,
        now=now,
        ttl_seconds=settings.idempotency_ttl_seconds,
        project_id=None,
    )
    return body


@router.post("/storage/contributions/{contribution_id}/activation")
def activate_contribution(
    contribution_id: str,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict:
    contribution = storage_service.activate_contribution(
        session, tenant_id=principal.tenant_id, contribution_id=contribution_id
    )
    return {"contribution": _contribution_body(contribution)}


@router.delete("/storage/contributions/{contribution_id}")
def revoke_contribution(
    contribution_id: str,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
    now: dt.datetime = Depends(get_now),
) -> dict:
    """Withdraw a contribution. The user's files are left alone."""
    contribution = storage_service.revoke_contribution(
        session, tenant_id=principal.tenant_id, contribution_id=contribution_id, now=now
    )
    return {"contribution": _contribution_body(contribution)}


@router.get("/storage/contributions")
def list_contributions(
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    node_id: str | None = Query(default=None, alias="nodeId"),
    limit: int | None = Query(default=None, ge=1),
    cursor: str | None = Query(default=None),
) -> dict:
    page = storage_service.list_contributions(
        session,
        tenant_id=principal.tenant_id,
        reader_user_id=principal.user_id,
        node_id=node_id,
        limit=limit,
        cursor=cursor,
        default_limit=settings.page_limit_default,
        max_limit=settings.page_limit_max,
    )
    return page.to_dict(_contribution_body)


@router.get("/storage/locations")
def list_locations(
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    contribution_id: str | None = Query(default=None, alias="contributionId"),
    kind: str | None = Query(default=None),
    ready_only: bool = Query(default=False, alias="readyOnly"),
    limit: int | None = Query(default=None, ge=1),
    cursor: str | None = Query(default=None),
) -> dict:
    page = storage_service.list_locations(
        session,
        tenant_id=principal.tenant_id,
        reader_user_id=principal.user_id,
        contribution_id=contribution_id,
        kind=kind,
        ready_only=ready_only,
        limit=limit,
        cursor=cursor,
        default_limit=settings.page_limit_default,
        max_limit=settings.page_limit_max,
    )
    return page.to_dict(_location_body)


@router.get("/storage/resolve")
def resolve_uri(
    uri: str = Query(min_length=1, max_length=2048),
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict:
    """Resolve owned active catalogue metadata; does not grant byte access."""
    try:
        location = resolver.resolve_location(
            session, tenant_id=principal.tenant_id, uri=uri,
            reader_user_id=principal.user_id,
        )
    except ValueError:
        raise InvError(VAL_SCHEMA, "invalid storage URI") from None
    except InvError as error:
        if error.code != RES_ARTIFACT_NOT_FOUND:
            raise
        # No existence oracle or reflection of an untrusted URI in diagnostics.
        raise InvError(RES_ARTIFACT_NOT_FOUND, "data location not found", status=404) from None
    return {"location": _location_body(location)}


@router.get("/storage/replica-status")
def replica_status(
    uri: str = Query(min_length=1, max_length=2048),
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict:
    """Recorded states for an owned location; current byte availability is unknown."""
    try:
        observation = observe_replicas(
            session, tenant_id=principal.tenant_id,
            reader_user_id=principal.user_id, uri=uri,
        )
    except ValueError:
        raise InvError(VAL_SCHEMA, "invalid storage URI") from None
    return {"observation": schemas.ReplicaObservationResponse.model_validate(
        observation
    ).model_dump(by_alias=True, mode="json")}
