"""Contributed folder registration and the data location catalogue (S02-ST).

The transfer path — presigned multipart upload, trusted-worker checksum
verification, quota reservation — needs an S3-compatible product, and S01-ST
owns that decision after MinIO was found archived on 2026-09-09. What does not
depend on the product is here: which folders are contributed, what lives in
them, how they are addressed, and what "ready" means.

``ready`` is never set by this module from client-supplied metadata. It is set
only by :func:`mark_verified`, which requires a checksum computed over actual
bytes (ADR-011), and the table constraint refuses the row otherwise.
"""

from __future__ import annotations

import datetime as dt
import re
import uuid
from dataclasses import dataclass

from sqlalchemy import select

from ..db.models import DataLocation, Node, StorageContribution
from ..errors import (
    RES_CONTRIBUTION_NOT_FOUND,
    RES_NODE_NOT_FOUND,
    VAL_PATH_UNSAFE,
    VAL_SCHEMA,
    InvError,
)
from ..ids import new_id
from ..storage.pathsafe import UnsafePath, build_uri, normalize_contribution_path, validate_relative_path
from .pagination import Page, build_page, clamp_limit, validate_cursor

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class ContributionInput:
    node_id: str
    declared_path: str
    mode: str = "read_only"
    capacity_bytes: int | None = None
    available_bytes: int | None = None


def register_contribution(
    session,
    *,
    tenant_id: uuid.UUID,
    registered_by_user_id: str,
    payload: ContributionInput,
    now: dt.datetime,
) -> StorageContribution:
    """Register a folder a node owner has offered.

    The path is normalised against the node's own OS, not the control plane's:
    the same string means different things on Windows and Linux, and getting
    that wrong is how a traversal check passes on the wrong platform.
    """
    if payload.mode not in ("read_only", "read_write"):
        raise InvError(VAL_SCHEMA, f"unknown mode: {payload.mode!r}")

    node = session.get(Node, payload.node_id)
    if node is None or node.tenant_id != tenant_id:
        raise InvError(RES_NODE_NOT_FOUND, "node not found")

    try:
        normalized = normalize_contribution_path(payload.declared_path, node.os_type)
    except UnsafePath as exc:
        # The rule is public; the rejected path is not echoed back.
        raise InvError(
            VAL_PATH_UNSAFE, f"contributed path rejected: {exc.rule}"
        ) from None

    contribution = StorageContribution(
        contribution_id=new_id("storage_contribution"),
        tenant_id=tenant_id,
        node_id=payload.node_id,
        declared_path=payload.declared_path,
        normalized_path=normalized.normalized,
        mode=payload.mode,
        status="pending",
        capacity_bytes=payload.capacity_bytes,
        available_bytes=payload.available_bytes,
        registered_by_user_id=registered_by_user_id,
        registered_at=now,
    )
    session.add(contribution)
    session.flush()
    return contribution


def activate_contribution(
    session, *, tenant_id: uuid.UUID, contribution_id: str
) -> StorageContribution:
    """Move a contribution to active once the node has confirmed the folder."""
    contribution = _load_contribution(session, tenant_id=tenant_id, contribution_id=contribution_id)
    if contribution.status == "revoked":
        raise InvError(VAL_SCHEMA, "a revoked contribution cannot be reactivated")
    contribution.status = "active"
    session.flush()
    return contribution


def revoke_contribution(
    session, *, tenant_id: uuid.UUID, contribution_id: str, now: dt.datetime
) -> StorageContribution:
    """Withdraw a contribution.

    The catalogue rows are kept. Deleting them would destroy the record of what
    had been referenced, and the folder belongs to the user either way — the
    platform stops using it, it does not clean it up.
    """
    contribution = _load_contribution(session, tenant_id=tenant_id, contribution_id=contribution_id)
    contribution.status = "revoked"
    contribution.revoked_at = now
    session.flush()
    return contribution


def catalogue_location(
    session,
    *,
    tenant_id: uuid.UUID,
    contribution_id: str,
    kind: str,
    relative_path: str,
    byte_size: int,
    name: str = "",
    version: str = "",
    run_id: str = "",
    artifact_id: str = "",
    workspace_id: str = "",
    now: dt.datetime,
) -> DataLocation:
    """Record an item inside a contribution, addressed by an ``inv://`` URI.

    Catalogued means known, not usable. ``ready`` stays false until a checksum
    over the real bytes is recorded.
    """
    contribution = _load_contribution(session, tenant_id=tenant_id, contribution_id=contribution_id)
    if contribution.status != "active":
        raise InvError(VAL_SCHEMA, "contribution is not active")
    if byte_size < 0:
        raise InvError(VAL_SCHEMA, "byte_size must not be negative")

    node = session.get(Node, contribution.node_id)
    try:
        safe_relative = validate_relative_path(relative_path, node.os_type)
    except UnsafePath as exc:
        raise InvError(VAL_PATH_UNSAFE, f"path rejected: {exc.rule}") from None

    try:
        uri = build_uri(
            kind,
            name=name,
            version=version,
            relative_path=safe_relative,
            run_id=run_id,
            artifact_id=artifact_id,
            workspace_id=workspace_id,
        )
    except ValueError as exc:
        raise InvError(VAL_SCHEMA, str(exc)) from None

    location = DataLocation(
        location_id=new_id("data_location"),
        tenant_id=tenant_id,
        contribution_id=contribution_id,
        uri=uri,
        kind=kind,
        relative_path=safe_relative,
        byte_size=byte_size,
        ready=False,
        catalogued_at=now,
    )
    session.add(location)
    session.flush()
    return location


def mark_verified(
    session,
    *,
    tenant_id: uuid.UUID,
    location_id: str,
    checksum_sha256: str,
    byte_size: int,
    now: dt.datetime,
) -> DataLocation:
    """Record a checksum computed by a trusted worker and mark the item ready.

    The checksum is required to be a lowercase hex SHA-256. An ETag or any
    other server-supplied metadata is not accepted in its place (ADR-011).
    """
    if not _SHA256_RE.match(checksum_sha256 or ""):
        raise InvError(VAL_SCHEMA, "checksum must be a lowercase hex SHA-256")
    location = session.get(DataLocation, location_id)
    if location is None or location.tenant_id != tenant_id:
        raise InvError(RES_CONTRIBUTION_NOT_FOUND, "data location not found")
    if location.ready and location.checksum_sha256 != checksum_sha256:
        # A verified item whose bytes now hash differently is a corruption or a
        # substitution. Refuse and leave the record intact for investigation.
        raise InvError(
            VAL_SCHEMA,
            "checksum conflicts with the previously verified value",
            cause_ref=location.location_id,
        )
    location.checksum_sha256 = checksum_sha256
    location.byte_size = byte_size
    location.verified_at = now
    location.ready = True
    session.flush()
    return location


def pin_retention(
    session, *, tenant_id: uuid.UUID, location_id: str, until: dt.datetime
) -> DataLocation:
    """Hold an item past the ordinary artifact lifetime (ADR-012).

    A pin only ever extends. Shortening one would let a later, weaker claim
    release something Evidence still depends on.
    """
    location = session.get(DataLocation, location_id)
    if location is None or location.tenant_id != tenant_id:
        raise InvError(RES_CONTRIBUTION_NOT_FOUND, "data location not found")
    current = location.retention_pinned_until
    if current is None or until > current:
        location.retention_pinned_until = until
        session.flush()
    return location


def list_contributions(
    session,
    *,
    tenant_id: uuid.UUID,
    reader_user_id: str | None = None,
    node_id: str | None = None,
    limit: int | None = None,
    cursor: str | None = None,
    default_limit: int = 50,
    max_limit: int = 200,
) -> Page:
    effective = clamp_limit(limit, default=default_limit, maximum=max_limit)
    after = validate_cursor(cursor)
    query = select(StorageContribution).where(StorageContribution.tenant_id == tenant_id)
    if reader_user_id is not None:
        query = query.where(StorageContribution.registered_by_user_id == reader_user_id)
    if node_id is not None:
        query = query.where(StorageContribution.node_id == node_id)
    if after is not None:
        query = query.where(StorageContribution.contribution_id > after)
    rows = session.scalars(
        query.order_by(StorageContribution.contribution_id).limit(effective + 1)
    ).all()
    return build_page(rows, limit=effective, id_attr="contribution_id")


def list_locations(
    session,
    *,
    tenant_id: uuid.UUID,
    reader_user_id: str | None = None,
    contribution_id: str | None = None,
    kind: str | None = None,
    ready_only: bool = False,
    limit: int | None = None,
    cursor: str | None = None,
    default_limit: int = 50,
    max_limit: int = 200,
) -> Page:
    effective = clamp_limit(limit, default=default_limit, maximum=max_limit)
    after = validate_cursor(cursor)
    query = select(DataLocation).where(DataLocation.tenant_id == tenant_id)
    if reader_user_id is not None:
        query = query.where(DataLocation.contribution_id.in_(
            select(StorageContribution.contribution_id).where(
                StorageContribution.tenant_id == tenant_id,
                StorageContribution.registered_by_user_id == reader_user_id,
                StorageContribution.status == "active",
            )
        ))
    if contribution_id is not None:
        query = query.where(DataLocation.contribution_id == contribution_id)
    if kind is not None:
        query = query.where(DataLocation.kind == kind)
    if ready_only:
        query = query.where(DataLocation.ready.is_(True))
    if after is not None:
        query = query.where(DataLocation.location_id > after)
    rows = session.scalars(
        query.order_by(DataLocation.location_id).limit(effective + 1)
    ).all()
    return build_page(rows, limit=effective, id_attr="location_id")


def _load_contribution(session, *, tenant_id: uuid.UUID, contribution_id: str) -> StorageContribution:
    contribution = session.get(StorageContribution, contribution_id)
    if contribution is None or contribution.tenant_id != tenant_id:
        raise InvError(RES_CONTRIBUTION_NOT_FOUND, "storage contribution not found")
    return contribution
