"""Resolve an ``inv://`` URI to its catalogued location and the nodes serving it.

The inverse of cataloguing (VF-CL-02). ``build_uri`` writes the name,
``parse_uri`` reads it, and this resolves it against what the catalogue and the
replica table actually hold:

* **parse != resolve.** A well-formed URI is not a resolvable one. Resolution is
  a tenant-scoped lookup; a URI that parses but names nothing catalogued is a
  not-found, not an empty success.
* **catalogued != readable.** A location with no ``ready`` replica is known but
  not yet materialisable. This returns the location either way and the serving
  nodes separately, so a caller cannot mistake "we know of it" for "you can read
  it now".
* **choosing the node is not done here.** This returns the set of nodes that hold
  a ready copy; which one a workload runs against is the Scheduler's
  locality/placement decision (VF-CX-03), not the resolver's.

The model-manifest binding (a ``kind='model'`` URI that expands to shard URIs) is
deferred to the VF-CX-02 contract and is not resolved here yet.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models.locality import DataReplica
from ..db.models.storage import DataLocation, StorageContribution
from ..errors import InvError, RES_ARTIFACT_NOT_FOUND
from ..storage.pathsafe import ParsedUri, parse_uri


def resolve_location(session: Session, *, tenant_id: uuid.UUID, uri: str,
                     reader_user_id: str | None = None) -> DataLocation:
    """The catalogued :class:`DataLocation` a URI names, within one tenant.

    Parses first so a malformed URI is rejected as a value error before any
    lookup, then reads the ``(tenant_id, uri)`` unique row. RLS confines the
    lookup to the caller's tenant; a URI catalogued under another tenant is a
    not-found here, not another tenant's row. Public readers also pass their
    verified user ID: only their active contributions are visible. Omitting
    that filter is reserved for existing internal tenant maintenance callers.
    """
    parse_uri(uri)  # reject malformed before touching the database
    query = select(DataLocation).where(
        DataLocation.tenant_id == tenant_id,
        DataLocation.uri == uri,
    )
    if reader_user_id is not None:
        query = query.where(DataLocation.contribution_id.in_(
            select(StorageContribution.contribution_id).where(
                StorageContribution.tenant_id == tenant_id,
                StorageContribution.registered_by_user_id == reader_user_id,
                StorageContribution.status == "active",
            )
        ))
    location = session.scalar(query)
    if location is None:
        raise InvError(RES_ARTIFACT_NOT_FOUND, f"no catalogued location for {uri}")
    return location


def resolve(session: Session, *, tenant_id: uuid.UUID, uri: str) -> tuple[ParsedUri, DataLocation]:
    """Both the parsed components and the catalogued location, in one call."""
    parsed = parse_uri(uri)
    location = resolve_location(session, tenant_id=tenant_id, uri=uri)
    return parsed, location


def ready_replica_nodes(session: Session, *, tenant_id: uuid.UUID, uri: str) -> list[str]:
    """Nodes that hold a verified, ready copy of the item the URI names.

    Only ``ready`` replicas are returned: a ``transferring`` or ``stale`` copy is
    not something a workload can read. An empty list means the location is
    catalogued but not currently materialisable anywhere — a real, distinct
    answer from "no such location", which raises instead.
    """
    location = resolve_location(session, tenant_id=tenant_id, uri=uri)
    return list(
        session.scalars(
            select(DataReplica.node_id)
            .where(
                DataReplica.tenant_id == tenant_id,
                DataReplica.location_id == location.location_id,
                DataReplica.state == "ready",
            )
            .order_by(DataReplica.node_id)
        ).all()
    )


def is_materialisable(session: Session, *, tenant_id: uuid.UUID, uri: str) -> bool:
    """Whether at least one node holds a ready copy the caller could read now."""
    return bool(ready_replica_nodes(session, tenant_id=tenant_id, uri=uri))
