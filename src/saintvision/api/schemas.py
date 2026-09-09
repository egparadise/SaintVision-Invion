"""Request and response models for /v1.

PLAN-BACKEND-001 makes JSON Schema the single source and forbids hand-editing
generated types. Until the generator pipeline lands in S03, these Pydantic
models are the source, and ``tools/export_schemas.py`` emits the JSON Schema
from them — one direction, so the two cannot disagree.

``extra="forbid"`` everywhere: the contract says unknown fields are rejected by
default (공통 계약 §3).
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CapabilityPayload(Strict):
    kind: str = Field(pattern="^(cpu|gpu|ram|disk)$")
    total_quantity: float = Field(ge=0, alias="totalQuantity")
    unit: str = Field(min_length=1, max_length=16)
    device_index: int | None = Field(default=None, ge=0, alias="deviceIndex")
    vendor: str | None = Field(default=None, max_length=64)
    model: str | None = Field(default=None, max_length=128)
    divisible: bool = False
    offered_quantity: float | None = Field(default=None, ge=0, alias="offeredQuantity")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class NodeEnrollRequest(Strict):
    bootstrap_token: str = Field(min_length=16, max_length=256, alias="bootstrapToken")
    hostname: str = Field(min_length=1, max_length=253)
    os_type: str = Field(pattern="^(windows|linux)$", alias="osType")
    os_version: str = Field(max_length=64, alias="osVersion")
    agent_version: str = Field(max_length=64, alias="agentVersion")
    capabilities: list[CapabilityPayload] = Field(default_factory=list, max_length=64)
    certificate_fingerprint: str | None = Field(
        default=None, pattern="^[0-9a-f]{64}$", alias="certificateFingerprint"
    )
    labels: dict[str, str] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class HeartbeatRequest(Strict):
    #: Monotonic per node. A value that does not advance is a replay.
    sequence: int = Field(ge=0)
    observations: list["ObservationPayload"] = Field(default_factory=list, max_length=256)


class ObservationPayload(Strict):
    capability_id: str = Field(max_length=30, alias="capabilityId")
    used_quantity: float = Field(ge=0, alias="usedQuantity")
    unit: str = Field(min_length=1, max_length=16)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class NodeResponse(Strict):
    node_id: str = Field(alias="nodeId")
    hostname: str
    os_type: str = Field(alias="osType")
    os_version: str = Field(alias="osVersion")
    agent_version: str = Field(alias="agentVersion")
    status: str
    enrolled_at: dt.datetime = Field(alias="enrolledAt")
    last_heartbeat_at: dt.datetime | None = Field(default=None, alias="lastHeartbeatAt")
    heartbeat_sequence: int = Field(alias="heartbeatSequence")
    labels: dict[str, str] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class NodeEnrollResponse(Strict):
    node: NodeResponse


class ContributionRequest(Strict):
    node_id: str = Field(max_length=30, alias="nodeId")
    declared_path: str = Field(min_length=1, max_length=4096, alias="declaredPath")
    mode: str = Field(default="read_only", pattern="^(read_only|read_write)$")
    capacity_bytes: int | None = Field(default=None, ge=0, alias="capacityBytes")
    available_bytes: int | None = Field(default=None, ge=0, alias="availableBytes")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ContributionResponse(Strict):
    contribution_id: str = Field(alias="contributionId")
    node_id: str = Field(alias="nodeId")
    declared_path: str = Field(alias="declaredPath")
    normalized_path: str = Field(alias="normalizedPath")
    mode: str
    status: str
    capacity_bytes: int | None = Field(default=None, alias="capacityBytes")
    available_bytes: int | None = Field(default=None, alias="availableBytes")
    registered_at: dt.datetime = Field(alias="registeredAt")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class DataLocationResponse(Strict):
    location_id: str = Field(alias="locationId")
    contribution_id: str = Field(alias="contributionId")
    uri: str
    kind: str
    relative_path: str = Field(alias="relativePath")
    byte_size: int = Field(alias="byteSize")
    checksum_sha256: str | None = Field(default=None, alias="checksumSha256")
    ready: bool
    verified_at: dt.datetime | None = Field(default=None, alias="verifiedAt")
    retention_pinned_until: dt.datetime | None = Field(
        default=None, alias="retentionPinnedUntil"
    )

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class PageResponse(Strict):
    items: list[dict]
    next_cursor: str | None = Field(default=None, alias="nextCursor")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)




class AnnouncementRequest(Strict):
    """What a Node Agent says about itself when announcing.

    Every field is a claim. The server records them prefixed ``claimed_`` and
    never treats them as measured; the source address is taken from the
    connection, not from here.
    """

    instance_id: str = Field(min_length=1, max_length=128, alias="instanceId")
    hostname: str = Field(min_length=1, max_length=253)
    os_type: str = Field(pattern="^(windows|linux)$", alias="osType")
    os_version: str = Field(max_length=64, alias="osVersion")
    agent_version: str = Field(max_length=64, alias="agentVersion")
    cpu_cores: int = Field(default=0, ge=0, alias="cpuCores")
    ram_bytes: int = Field(default=0, ge=0, alias="ramBytes")
    gpu_count: int = Field(default=0, ge=0, alias="gpuCount")
    labels: dict[str, str] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class PoolRequest(Strict):
    project_id: str = Field(max_length=30, alias="projectId")
    name: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=2000)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class DistributedPlanRequest(Strict):
    """How to spread one Run over a pool.

    ``splittableDeclared`` has no default of convenience: splitting a program
    that is not shard-aware produces a wrong answer, so the caller states it.
    """

    run_id: str = Field(max_length=30, alias="runId")
    strategy: str = Field(pattern="^(single_node|data_parallel|sharded)$")
    shard_count: int = Field(default=1, ge=1, le=1024, alias="shardCount")
    splittable_declared: bool = Field(default=False, alias="splittableDeclared")
    shard_cpu_cores: float = Field(default=0, ge=0, alias="shardCpuCores")
    shard_ram_bytes: int = Field(default=0, ge=0, alias="shardRamBytes")
    shard_gpu_count: int = Field(default=0, ge=0, alias="shardGpuCount")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


HeartbeatRequest.model_rebuild()
