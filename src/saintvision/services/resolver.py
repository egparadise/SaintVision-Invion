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


# ---------------------------------------------------------------------------
# VF-CL-02: kind='model' URI -> ModelManifest shards / replicas (contract-free)
# ---------------------------------------------------------------------------

from dataclasses import dataclass, field  # noqa: E402
from typing import Any, Callable  # noqa: E402

from ..db.models.lineage import Model, ModelVersion  # noqa: E402

#: ``(tenant_id, model_id, version) -> ModelManifest dict | None``. The business role
#: cannot read the kernel's ``inv.model_manifests`` (no SELECT grant), so the manifest is
#: injected by the caller; how it is obtained in operation (grant / kernel HTTP / kernel
#: route) is a Codex decision. Without a reader the resolver reports ``unavailable`` --
#: it never fabricates an empty shard list.
ManifestReader = Callable[[uuid.UUID, str, str], "dict[str, Any] | None"]

_MANIFEST_KEYS = {"modelId", "version", "shards", "replicas"}
_SHARD_KEYS = {"index", "offset", "byteLength", "sha256"}
_REPLICA_KEYS = {"shardIndex", "locationId", "locationVersion", "nodeId", "state"}
_REPLICA_STATES = {"unverified", "verified", "unavailable"}


@dataclass(frozen=True)
class ReplicaResolution:
    location_id: str
    location_version: int
    node_id: str
    manifest_state: str
    location: DataLocation | None
    materialisable: bool
    reason: str  # ok | manifest-<state> | location-missing | location-version-drift | replica-not-ready


@dataclass(frozen=True)
class ShardResolution:
    index: int
    offset: int
    byte_length: int
    sha256: str
    replicas: list[ReplicaResolution]
    materialisable: bool
    reason: str  # ok | unrecorded | no-materialisable-replica


@dataclass(frozen=True)
class ModelResolution:
    parsed: ParsedUri
    model_version: ModelVersion
    location: DataLocation | None
    ready_nodes: list[str]
    shards: list[ShardResolution] | None
    manifest_source: str  # reader | unavailable
    reason: str
    fully_materialisable: bool = field(default=False)


def _check_manifest_shape(manifest: Any) -> None:
    """Refuse a reader result that is not ModelManifest-shaped.

    Not a schema validator: only the keys this resolver reads are required, so a
    contract-valid manifest passes and an ad-hoc dict cannot be mistaken for one.
    """
    if not isinstance(manifest, dict) or not _MANIFEST_KEYS <= set(manifest):
        raise ValueError("manifest reader must return a ModelManifest-shaped mapping")
    if not isinstance(manifest["shards"], list) or not manifest["shards"]:
        raise ValueError("ModelManifest.shards must be a non-empty list")
    for shard in manifest["shards"]:
        if not isinstance(shard, dict) or not _SHARD_KEYS <= set(shard):
            raise ValueError("ModelShard shape mismatch")
    for replica in manifest["replicas"]:
        if not isinstance(replica, dict) or not _REPLICA_KEYS <= set(replica):
            raise ValueError("ModelReplica shape mismatch")
        if replica["state"] not in _REPLICA_STATES:
            raise ValueError("ModelReplica.state outside the contract enum")


def _reader_scoped(query, tenant_id: uuid.UUID, reader_user_id: str | None):
    """The same public-reader scope :func:`resolve_location` applies (no bypass SQL)."""
    if reader_user_id is None:
        return query
    return query.where(DataLocation.contribution_id.in_(
        select(StorageContribution.contribution_id).where(
            StorageContribution.tenant_id == tenant_id,
            StorageContribution.registered_by_user_id == reader_user_id,
            StorageContribution.status == "active",
        )
    ))


def resolve_model(session: Session, *, tenant_id: uuid.UUID, uri: str,
                  reader_user_id: str | None = None,
                  manifest_reader: ManifestReader | None = None) -> ModelResolution:
    """Resolve ``inv://models/<name>@<version>/...`` into its registered version and, when
    a manifest is available, into per-shard replica locations the caller could read now.

    Order: parse (a non-model or malformed URI is a ``ValueError`` before any lookup) ->
    join key ``models.name`` + ``model_versions.version`` under tenant RLS (missing ->
    ``RES_ARTIFACT_NOT_FOUND``) -> optional catalogued location of the URI itself ->
    shard expansion through the injected reader. Each replica the manifest names is
    checked against the business catalogue with the SAME reader scope as
    :func:`resolve_location`: the location must exist in this tenant (RLS: another
    tenant's is "missing", not theirs), its ``version`` must equal the manifest's
    ``locationVersion`` (else drift), the manifest state must be ``verified``, and a
    ``ready`` ``DataReplica`` must exist on that node. Anything else is reported with
    its reason; nothing is rounded up to "ok".
    """
    parsed = parse_uri(uri)
    if parsed.kind != "model":
        raise ValueError(f"resolve_model expects a model URI, got kind={parsed.kind!r}")
    model = session.scalar(select(Model).where(Model.tenant_id == tenant_id, Model.name == parsed.name))
    version = None
    if model is not None:
        version = session.scalar(select(ModelVersion).where(
            ModelVersion.tenant_id == tenant_id,
            ModelVersion.model_id == model.model_id,
            ModelVersion.version == parsed.version,
        ))
    if version is None:
        raise InvError(RES_ARTIFACT_NOT_FOUND, f"no registered model version for {uri}")
    location = session.scalar(_reader_scoped(
        select(DataLocation).where(DataLocation.tenant_id == tenant_id, DataLocation.uri == uri),
        tenant_id, reader_user_id))
    ready_nodes: list[str] = []
    if location is not None:
        ready_nodes = list(session.scalars(
            select(DataReplica.node_id).where(
                DataReplica.tenant_id == tenant_id,
                DataReplica.location_id == location.location_id,
                DataReplica.state == "ready",
            ).order_by(DataReplica.node_id)
        ).all())
    if manifest_reader is None:
        return ModelResolution(
            parsed=parsed, model_version=version, location=location, ready_nodes=ready_nodes,
            shards=None, manifest_source="unavailable",
            reason="kernel manifest not readable from the business role and no manifest_reader "
                   "was injected; shard expansion is unavailable (not empty)",
        )
    manifest = manifest_reader(tenant_id, model.model_id, parsed.version)
    if manifest is None:
        return ModelResolution(
            parsed=parsed, model_version=version, location=location, ready_nodes=ready_nodes,
            shards=None, manifest_source="unavailable",
            reason="manifest reader returned no manifest for this (model, version)",
        )
    _check_manifest_shape(manifest)
    by_shard: dict[int, list[dict[str, Any]]] = {}
    for replica in manifest["replicas"]:
        by_shard.setdefault(int(replica["shardIndex"]), []).append(replica)
    shards: list[ShardResolution] = []
    for shard in sorted(manifest["shards"], key=lambda s: int(s["index"])):
        resolved: list[ReplicaResolution] = []
        for replica in by_shard.get(int(shard["index"]), []):
            loc = session.scalar(_reader_scoped(
                select(DataLocation).where(
                    DataLocation.tenant_id == tenant_id,
                    DataLocation.location_id == replica["locationId"],
                ), tenant_id, reader_user_id))
            state = replica["state"]
            if state != "verified":
                reason = f"manifest-{state}"
            elif loc is None:
                reason = "location-missing"
            elif int(loc.version) != int(replica["locationVersion"]):
                reason = "location-version-drift"
            else:
                ready = session.scalar(select(DataReplica.replica_id).where(
                    DataReplica.tenant_id == tenant_id,
                    DataReplica.location_id == loc.location_id,
                    DataReplica.node_id == replica["nodeId"],
                    DataReplica.state == "ready",
                ))
                reason = "ok" if ready is not None else "replica-not-ready"
            resolved.append(ReplicaResolution(
                location_id=replica["locationId"], location_version=int(replica["locationVersion"]),
                node_id=replica["nodeId"], manifest_state=state, location=loc,
                materialisable=reason == "ok", reason=reason,
            ))
        if not resolved:
            shard_reason = "unrecorded"
        elif any(r.materialisable for r in resolved):
            shard_reason = "ok"
        else:
            shard_reason = "no-materialisable-replica"
        shards.append(ShardResolution(
            index=int(shard["index"]), offset=int(shard["offset"]), byte_length=int(shard["byteLength"]),
            sha256=shard["sha256"], replicas=resolved, materialisable=shard_reason == "ok", reason=shard_reason,
        ))
    return ModelResolution(
        parsed=parsed, model_version=version, location=location, ready_nodes=ready_nodes,
        shards=shards, manifest_source="reader",
        reason="expanded from the injected manifest; per-shard reasons are authoritative",
        fully_materialisable=all(s.materialisable for s in shards),
    )
