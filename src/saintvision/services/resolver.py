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

The model-manifest binding accepts either the immutable ``ModelManifest`` used
by the kernel internally or its strict project-authorized execution observation.
The latter is the production boundary: the business role still rechecks every
reported location/version/ready node through its own RLS-scoped catalogue.
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

#: ``(tenant_id, model_id, version) -> manifest observation dict | None``. The business role
#: cannot read the kernel's ``inv.model_manifests`` (no SELECT grant), so the manifest is
#: injected by the caller.  Production injects the project-authorized kernel
#: ``ModelExecutionManifestObservation``; unit callers may still inject the immutable
#: ``ModelManifest``. Without a reader the resolver reports ``unavailable`` -- it never
#: fabricates an empty shard list.
ManifestReader = Callable[[uuid.UUID, str, str], "dict[str, Any] | None"]

_MANIFEST_KEYS = {"modelId", "version", "shards", "replicas"}
_SHARD_KEYS = {"index", "offset", "byteLength", "sha256"}
_REPLICA_KEYS = {"shardIndex", "locationId", "locationVersion", "nodeId", "state"}
_REPLICA_STATES = {"unverified", "verified", "unavailable"}
_OBSERVATION_KEYS = {
    "projectId", "modelId", "version", "manifestHash", "observedAt", "shards",
    "shardLocations", "licensePolicy", "classification", "materialisable",
    "executionAuthorized", "requiresExecutionRevalidation",
}
_OBSERVATION_LOCATION_KEYS = {
    "shardIndex", "locationId", "locationVersion", "readyNodes", "materialisable",
}


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
class LocationResolution:
    """Business-role recheck of one kernel shard/location observation."""

    shard_index: int
    location_id: str
    location_version: int
    ready_nodes: list[str]
    location: DataLocation | None
    materialisable: bool
    reason: str  # ok | location-missing | location-version-drift | replica-not-ready


@dataclass(frozen=True)
class ModelResolution:
    parsed: ParsedUri
    model_version: ModelVersion
    location: DataLocation | None
    ready_nodes: list[str]
    shards: list[ShardResolution] | None
    manifest_source: str  # reader | unavailable
    reason: str
    locations: list[LocationResolution] | None = field(default=None)
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


def _is_execution_observation(manifest: Any) -> bool:
    return isinstance(manifest, dict) and _OBSERVATION_KEYS <= set(manifest)


def _check_observation_shape(observation: Any, *, project_id: str | None,
                             model_id: str, version: str) -> None:
    """Check the invariants the resolver relies on after boundary schema validation."""
    if not _is_execution_observation(observation):
        raise ValueError("manifest reader must return a ModelManifest or execution observation")
    if observation["executionAuthorized"] is not False or (
        observation["requiresExecutionRevalidation"] is not True
    ):
        raise ValueError("execution observation cannot carry execution authority")
    if (observation["modelId"], observation["version"]) != (model_id, version):
        raise ValueError("execution observation identity mismatch")
    if project_id is not None and observation["projectId"] != project_id:
        raise ValueError("execution observation project mismatch")
    if not isinstance(observation["shards"], list) or not observation["shards"]:
        raise ValueError("execution observation shards must be non-empty")
    if not isinstance(observation["shardLocations"], list) or not observation["shardLocations"]:
        raise ValueError("execution observation shardLocations must be non-empty")
    for item in observation["shardLocations"]:
        if not isinstance(item, dict) or not _OBSERVATION_LOCATION_KEYS <= set(item):
            raise ValueError("execution observation shard location shape mismatch")
        if bool(item["readyNodes"]) != bool(item["materialisable"]):
            raise ValueError("execution observation materialisable flag mismatch")


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
                  project_id: str | None = None,
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
    model_query = select(Model).where(Model.tenant_id == tenant_id, Model.name == parsed.name)
    if project_id is not None:
        model_query = model_query.where(Model.project_id == project_id)
    model = session.scalar(model_query)
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
    if _is_execution_observation(manifest):
        _check_observation_shape(
            manifest, project_id=project_id, model_id=model.model_id, version=parsed.version
        )
        return _resolve_execution_observation(
            session,
            tenant_id=tenant_id,
            parsed=parsed,
            version=version,
            location=location,
            ready_nodes=ready_nodes,
            reader_user_id=reader_user_id,
            observation=manifest,
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


def _resolve_execution_observation(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    parsed: ParsedUri,
    version: ModelVersion,
    location: DataLocation | None,
    ready_nodes: list[str],
    reader_user_id: str | None,
    observation: dict[str, Any],
) -> ModelResolution:
    """Intersect a kernel observation with what the restricted business role sees now."""
    checked_locations: list[LocationResolution] = []
    replicas_by_shard: dict[int, list[ReplicaResolution]] = {}
    for item in sorted(
        observation["shardLocations"],
        key=lambda value: (int(value["shardIndex"]), value["locationId"]),
    ):
        shard_index = int(item["shardIndex"])
        loc = session.scalar(_reader_scoped(
            select(DataLocation).where(
                DataLocation.tenant_id == tenant_id,
                DataLocation.location_id == item["locationId"],
            ),
            tenant_id,
            reader_user_id,
        ))
        if loc is None:
            reason = "location-missing"
            verified_nodes: list[str] = []
        elif int(loc.version) != int(item["locationVersion"]):
            reason = "location-version-drift"
            verified_nodes = []
        else:
            candidates = sorted(set(item["readyNodes"]))
            verified_nodes = list(session.scalars(
                select(DataReplica.node_id).where(
                    DataReplica.tenant_id == tenant_id,
                    DataReplica.location_id == loc.location_id,
                    DataReplica.node_id.in_(candidates),
                    DataReplica.state == "ready",
                ).order_by(DataReplica.node_id)
            ).all()) if candidates else []
            reason = "ok" if verified_nodes else "replica-not-ready"
        checked_locations.append(LocationResolution(
            shard_index=shard_index,
            location_id=item["locationId"],
            location_version=int(item["locationVersion"]),
            ready_nodes=verified_nodes,
            location=loc,
            materialisable=bool(verified_nodes),
            reason=reason,
        ))
        for node_id in item["readyNodes"]:
            node_ok = node_id in verified_nodes
            replicas_by_shard.setdefault(shard_index, []).append(ReplicaResolution(
                location_id=item["locationId"],
                location_version=int(item["locationVersion"]),
                node_id=node_id,
                manifest_state="verified",
                location=loc,
                materialisable=node_ok,
                reason="ok" if node_ok else reason,
            ))

    mapped_shards = {item.shard_index for item in checked_locations}
    shards: list[ShardResolution] = []
    for shard in sorted(observation["shards"], key=lambda value: int(value["index"])):
        shard_index = int(shard["index"])
        candidates = [item for item in checked_locations if item.shard_index == shard_index]
        materialisable = any(item.materialisable for item in candidates)
        shards.append(ShardResolution(
            index=shard_index,
            offset=int(shard["offset"]),
            byte_length=int(shard["byteLength"]),
            sha256=shard["sha256"],
            replicas=replicas_by_shard.get(shard_index, []),
            materialisable=materialisable,
            reason="ok" if materialisable else (
                "no-materialisable-replica" if shard_index in mapped_shards else "unrecorded"
            ),
        ))
    return ModelResolution(
        parsed=parsed,
        model_version=version,
        location=location,
        ready_nodes=ready_nodes,
        shards=shards,
        manifest_source="reader",
        reason="kernel observation rechecked through the restricted business catalogue",
        locations=checked_locations,
        fully_materialisable=all(shard.materialisable for shard in shards),
    )
