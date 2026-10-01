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
import uuid
from typing import Annotated, Any, Literal, Union

from pydantic import AwareDatetime, BaseModel, BeforeValidator, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, StrictStr, field_validator, model_validator


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


class HeartbeatAcceptedResponse(Strict):
    node_id: StrictStr = Field(alias="nodeId")
    applied: StrictBool
    heartbeat_sequence: StrictInt = Field(ge=0, alias="heartbeatSequence")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class NodeLivenessSweepResponse(Strict):
    marked_lost: StrictInt = Field(ge=0, alias="markedLost")
    timeout_seconds: StrictInt = Field(gt=0, alias="timeoutSeconds")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ObservationPayload(Strict):
    capability_id: str = Field(max_length=30, alias="capabilityId")
    used_quantity: float = Field(ge=0, alias="usedQuantity")
    unit: str = Field(min_length=1, max_length=16)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


NodeStatusName = Literal["enrolling", "active", "draining", "lost", "retired"]


class NodeResponse(Strict):
    node_id: str = Field(alias="nodeId")
    hostname: str
    os_type: str = Field(alias="osType")
    os_version: str = Field(alias="osVersion")
    agent_version: str = Field(alias="agentVersion")
    status: NodeStatusName
    enrolled_at: dt.datetime = Field(alias="enrolledAt")
    last_heartbeat_at: dt.datetime | None = Field(default=None, alias="lastHeartbeatAt")
    heartbeat_sequence: int = Field(alias="heartbeatSequence")
    labels: dict[str, str] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class NodePageResponse(Strict):
    """Tenant-scoped node inventory page; telemetry is intentionally absent."""

    items: list[NodeResponse]
    next_cursor: str | None = Field(alias="nextCursor")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class NodeCapability(Strict):
    capability_id: str = Field(alias="capabilityId", max_length=30)
    kind: str = Field(pattern="^(cpu|gpu|ram|disk)$")
    device_index: int | None = Field(alias="deviceIndex", ge=0)
    vendor: str | None = Field(max_length=64)
    model: str | None = Field(max_length=128)
    total_quantity: float = Field(alias="totalQuantity", ge=0)
    unit: str = Field(min_length=1, max_length=16)
    divisible: bool

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class NodeDetailResponse(Strict):
    node: NodeResponse
    capabilities: list[NodeCapability]

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


ContributionMode = Literal["read_only", "read_write"]
ContributionStatusName = Literal["pending", "active", "revoked"]


class ContributionResponse(Strict):
    contribution_id: str = Field(alias="contributionId")
    node_id: str = Field(alias="nodeId")
    declared_path: str = Field(alias="declaredPath")
    normalized_path: str = Field(alias="normalizedPath")
    mode: ContributionMode
    status: ContributionStatusName
    capacity_bytes: int | None = Field(default=None, alias="capacityBytes")
    available_bytes: int | None = Field(default=None, alias="availableBytes")
    registered_at: dt.datetime = Field(alias="registeredAt")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ContributionRegistrationResponse(Strict):
    """Registration handle and normalized storage path returned to the caller."""

    contribution: ContributionResponse

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


class ContributionPageResponse(Strict):
    """Paginated storage contributions returned to the Resource Explorer."""

    items: list[ContributionResponse]
    next_cursor: str | None = Field(alias="nextCursor")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class DataLocationPageResponse(Strict):
    """Paginated catalog locations returned to the Resource Explorer."""

    items: list[DataLocationResponse]
    next_cursor: str | None = Field(alias="nextCursor")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


WorkspaceStatusName = Literal[
    "provisioning", "ready", "suspended", "deleting", "deleted"
]


class WorkspaceSummaryResponse(Strict):
    workspace_id: str = Field(alias="workspaceId")
    project_id: str = Field(alias="projectId")
    name: str
    status: WorkspaceStatusName
    node_id: str | None = Field(alias="nodeId")
    tool_name: str | None = Field(alias="toolName")
    created_at: dt.datetime = Field(alias="createdAt")
    allowed_next: list[WorkspaceStatusName] = Field(alias="allowedNext")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class WorkspaceStatusResponse(Strict):
    """Workspace lifecycle result, including the next legal transition choices."""

    workspace_id: StrictStr = Field(alias="workspaceId")
    status: WorkspaceStatusName
    allowed_next: list[WorkspaceStatusName] = Field(alias="allowedNext")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class WorkspaceToolReadinessResponse(Strict):
    adapter: str | None
    node_id: str | None = Field(alias="nodeId")
    ready: bool
    state: Literal["unknown"]
    measurement_scope: Literal["workspace-node"] = Field(alias="measurementScope")
    reason: str

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class WorkspaceToolResultResponse(Strict):
    """Workspace tool choice and its explicitly unmeasured current readiness."""

    workspace_id: str = Field(alias="workspaceId")
    project_id: str = Field(alias="projectId")
    name: str
    status: WorkspaceStatusName
    node_id: str | None = Field(alias="nodeId")
    tool_name: str | None = Field(alias="toolName")
    created_at: dt.datetime = Field(alias="createdAt")
    allowed_next: list[WorkspaceStatusName] = Field(alias="allowedNext")
    tool_readiness: WorkspaceToolReadinessResponse | None = Field(alias="toolReadiness")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ProjectWorkspacesResponse(Strict):
    project_id: str = Field(alias="projectId")
    workspaces: list[WorkspaceSummaryResponse]
    count: int = Field(ge=0)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ProjectListItemResponse(Strict):
    """Business project row shown in the project selector."""

    project_id: str = Field(alias="projectId")
    code: str
    display_name: str = Field(alias="displayName")
    status: str
    member_count: int = Field(ge=0, alias="memberCount")
    created_at: dt.datetime = Field(alias="createdAt")
    kernel_linked: bool = Field(alias="kernelLinked")
    kernel_enabled: bool = Field(alias="kernelEnabled")
    kernel_note: str | None = Field(default=None, alias="kernelNote")
    role_code: str = Field(alias="roleCode")
    can_request: bool = Field(alias="canRequest")
    can_approve: bool = Field(alias="canApprove")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ProjectListResponse(Strict):
    """Canonical business API envelope for GET /v1/projects."""

    projects: list[ProjectListItemResponse]
    count: int = Field(ge=0)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ProjectCreateResponse(Strict):
    """Body returned after creating a project (without list-only permissions)."""

    project_id: StrictStr = Field(alias="projectId")
    code: StrictStr
    display_name: StrictStr = Field(alias="displayName")
    status: StrictStr
    member_count: StrictInt = Field(ge=0, alias="memberCount")
    created_at: dt.datetime = Field(alias="createdAt")
    kernel_linked: StrictBool = Field(alias="kernelLinked")
    kernel_enabled: StrictBool = Field(alias="kernelEnabled")
    kernel_note: StrictStr | None = Field(default=None, alias="kernelNote")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class DiscoveryAdmissionResponse(Strict):
    """One-time enrollment credential returned after an operator admits a node."""

    announcement_id: StrictStr = Field(alias="announcementId")
    bootstrap_token: StrictStr = Field(min_length=16, max_length=256, alias="bootstrapToken")
    expires_at: dt.datetime = Field(alias="expiresAt")
    next: StrictStr

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class DiscoveryAnnouncementResponse(Strict):
    accepted: Literal[True]
    # Refresh does not revive or rewrite an existing admitted/declined/expired row.
    state: Literal["candidate", "admitted", "declined", "expired"]

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class DiscoveryDeclineResponse(Strict):
    announcement_id: StrictStr = Field(alias="announcementId")
    state: Literal["declined"]

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ProjectMemberRemovalResponse(Strict):
    project_id: StrictStr = Field(alias="projectId")
    user_id: StrictStr = Field(alias="userId")
    removed: Literal[True]

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class MemberRoleResultResponse(Strict):
    """Effective permissions after a membership role change."""

    project_id: StrictStr = Field(alias="projectId")
    user_id: StrictStr = Field(alias="userId")
    role_code: StrictStr = Field(alias="roleCode")
    project_status: StrictStr = Field(alias="projectStatus")
    user_status: StrictStr = Field(alias="userStatus")
    can_request: StrictBool = Field(alias="canRequest")
    can_approve: StrictBool = Field(alias="canApprove")
    can_administer: StrictBool = Field(alias="canAdminister")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ResourceOfferResultResponse(Strict):
    """Canonical offer and whether the execution kernel accepted it."""

    capability_id: StrictStr = Field(alias="capabilityId")
    node_id: StrictStr = Field(alias="nodeId")
    kind: Literal["cpu", "gpu", "ram", "disk"]
    unit: StrictStr
    offered_quantity: StrictFloat = Field(alias="offeredQuantity")
    total_quantity: StrictFloat = Field(alias="totalQuantity")
    previous_offered_quantity: StrictFloat | None = Field(alias="previousOfferedQuantity")
    effective_from: dt.datetime = Field(alias="effectiveFrom")
    note: StrictStr
    applied_to_kernel: StrictBool = Field(alias="appliedToKernel")
    kernel_resource_ids: list[StrictStr] = Field(alias="kernelResourceIds")
    kernel_resource_id: StrictStr | None = Field(alias="kernelResourceId")
    kernel_capacity: StrictFloat | None = Field(alias="kernelCapacity")
    kernel_reason_code: StrictStr | None = Field(alias="kernelReasonCode")
    execution_ready: StrictBool = Field(alias="executionReady")
    kernel_reason: StrictStr | None = Field(default=None, alias="kernelReason")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ExecutionReadinessCheckResponse(Strict):
    check: str
    satisfied: bool
    detail: str
    resolved_by: str | None = Field(default=None, alias="resolvedBy")
    remedy: str | None = None
    snapshot_bytes: int | None = Field(default=None, alias="snapshotBytes")
    max_snapshot_bytes: int | None = Field(default=None, alias="maxSnapshotBytes")
    max_content_bytes: int | None = Field(default=None, alias="maxContentBytes")
    run_id: str | None = Field(default=None, alias="runId")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class WorkspaceExecutionReadinessResponse(Strict):
    workspace_id: str = Field(alias="workspaceId")
    project_id: str = Field(alias="projectId")
    executable: Literal[False]
    scope: Literal["workspace-preconditions-not-execution-admission"]
    node_readiness: Literal["unknown"] = Field(alias="nodeReadiness")
    admission_required: Literal[True] = Field(alias="admissionRequired")
    checks: list[ExecutionReadinessCheckResponse]
    blocked_by: list[str] = Field(alias="blockedBy")
    summary: str

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class RecordedReplicaStates(Strict):
    ready: int = Field(ge=0)
    transferring: int = Field(ge=0)
    stale: int = Field(ge=0)
    corrupt: int = Field(ge=0)
    evicted: int = Field(ge=0)


class ReplicaObservationResponse(Strict):
    location_id: str = Field(alias="locationId")
    location_version: int = Field(ge=1, alias="locationVersion")
    observed_at: dt.datetime = Field(alias="observedAt")
    recorded_states: RecordedReplicaStates = Field(alias="recordedStates")
    total_records: int = Field(ge=0, alias="totalRecords")
    current_availability: Literal["unknown"] = Field(alias="currentAvailability")
    requires_execution_revalidation: Literal[True] = Field(alias="requiresExecutionRevalidation")


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


class DiscoveryCandidateResponse(Strict):
    """One unverified announcement offered for operator admission."""

    announcement_id: str = Field(alias="announcementId")
    instance_id: str = Field(alias="instanceId")
    source_ip: str = Field(alias="sourceIp")
    claimed_hostname: str = Field(alias="claimedHostname")
    claimed_os_type: str = Field(alias="claimedOsType")
    claimed_cpu_cores: int = Field(ge=0, alias="claimedCpuCores")
    claimed_ram_bytes: int = Field(ge=0, alias="claimedRamBytes")
    claimed_gpu_count: int = Field(ge=0, alias="claimedGpuCount")
    first_seen_at: dt.datetime = Field(alias="firstSeenAt")
    last_seen_at: dt.datetime = Field(alias="lastSeenAt")
    announce_count: int = Field(ge=1, alias="announceCount")
    stale: bool
    state: Literal["candidate"]
    verified: Literal[False]

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class DiscoveryCandidatesResponse(Strict):
    items: list[DiscoveryCandidateResponse]
    note: str

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class PoolRequest(Strict):
    project_id: str = Field(max_length=30, alias="projectId")
    name: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=2000)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class PoolResourceAmounts(Strict):
    cpu_millicores: float = Field(ge=0, alias="cpuMillicores")
    ram_bytes: float = Field(ge=0, alias="ramBytes")
    gpu_devices: float = Field(ge=0, alias="gpuDevices")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class PoolCapacityNodeResponse(Strict):
    node_id: str = Field(alias="nodeId")
    hostname: str
    offered: PoolResourceAmounts
    used: PoolResourceAmounts
    spare: PoolResourceAmounts
    measured: bool

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class PoolCapacityResponse(Strict):
    pool_id: str = Field(alias="poolId")
    name: str
    member_count: int = Field(ge=0, alias="memberCount")
    active_member_count: int = Field(ge=0, alias="activeMemberCount")
    total_offered: PoolResourceAmounts = Field(alias="totalOffered")
    largest_single_node: PoolResourceAmounts = Field(alias="largestSingleNode")
    spare_now: PoolResourceAmounts = Field(alias="spareNow")
    unmeasured_nodes: list[str] = Field(alias="unmeasuredNodes")
    nodes: list[PoolCapacityNodeResponse]
    units: dict[str, str]
    note: str

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class PlacementPreviewCandidateResponse(Strict):
    node_id: str = Field(alias="nodeId")
    hostname: str
    spare: PoolResourceAmounts
    headroom: float = Field(ge=0, allow_inf_nan=False)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class PlacementPreviewResponse(Strict):
    pool_id: str = Field(alias="poolId")
    candidates: list[PlacementPreviewCandidateResponse]
    candidate_count: int = Field(ge=0, alias="candidateCount")
    units: dict[str, str]

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class PoolListItemResponse(Strict):
    pool_id: str = Field(alias="poolId")
    project_id: str = Field(alias="projectId")
    name: str
    status: Literal["active", "archived"]
    member_count: int = Field(ge=0, alias="memberCount")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class PoolListResponse(Strict):
    items: list[PoolListItemResponse]
    count: int = Field(ge=0)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class PoolCreatedResponse(Strict):
    pool_id: str = Field(alias="poolId")
    name: str

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class PoolMemberResponse(Strict):
    pool_id: str = Field(alias="poolId")
    node_id: str = Field(alias="nodeId")
    member: Literal[True]

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class PoolMemberRemovalResponse(Strict):
    pool_id: str = Field(alias="poolId")
    node_id: str = Field(alias="nodeId")
    removed: bool

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class DistributedPlanPlacementResponse(Strict):
    shard_index: int = Field(ge=0, alias="shardIndex")
    node_id: str = Field(alias="nodeId")
    assigned_cpu_millicores: int = Field(ge=0, alias="assignedCpuMillicores")
    assigned_ram_bytes: int = Field(ge=0, alias="assignedRamBytes")
    assigned_gpu_devices: int = Field(ge=0, alias="assignedGpuDevices")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class DistributedPlanResponse(Strict):
    plan_id: str = Field(alias="planId")
    run_id: str = Field(alias="runId")
    strategy: Literal["single_node", "data_parallel", "sharded"]
    shard_count: int = Field(ge=1, alias="shardCount")
    units: dict[str, str]
    placements: list[DistributedPlanPlacementResponse]

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class DistributedPlanRequest(Strict):
    """How to spread one Run over a pool.

    ``splittableDeclared`` has no default of convenience: splitting a program
    that is not shard-aware produces a wrong answer, so the caller states it.
    """

    run_id: str = Field(max_length=30, alias="runId")
    strategy: Literal["single_node", "data_parallel", "sharded"]
    shard_count: int = Field(default=1, ge=1, le=1024, alias="shardCount")
    splittable_declared: bool = Field(default=False, alias="splittableDeclared")
    #: In the canonical units, and named after them. These are compared against
    #: a node's spare capacity, so a field called ``shardCpuCores`` sitting next
    #: to capacity measured in millicores is an invitation to be wrong by a
    #: factor of a thousand — see ``saintvision.units``.
    shard_cpu_millicores: int = Field(default=0, ge=0, alias="shardCpuMillicores")
    shard_ram_bytes: int = Field(default=0, ge=0, alias="shardRamBytes")
    shard_gpu_devices: int = Field(default=0, ge=0, alias="shardGpuDevices")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


HeartbeatRequest.model_rebuild()


class MemberRoleRequest(Strict):
    """Grant or change one project membership.

    The role vocabulary is a contract with the execution kernel, which reads
    ``public.project_members.role_code`` before it will start anything. A value
    outside the set saves and then means nothing, so the pattern is closed
    rather than free text.
    """

    role_code: str = Field(
        pattern="^(owner|maintainer|operator|approver|viewer)$", alias="roleCode"
    )

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class UserStatusRequest(Strict):
    status: str = Field(pattern="^(active|suspended|retired)$")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class UserStatusResponse(Strict):
    user_id: StrictStr = Field(alias="userId")
    status: Literal["active", "suspended", "retired"]

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ProjectStatusRequest(Strict):
    status: str = Field(pattern="^(active|archived)$")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ProjectStatusResponse(Strict):
    project_id: StrictStr = Field(alias="projectId")
    status: Literal["active", "archived"]

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class WorkspaceStatusRequest(Strict):
    status: str = Field(
        pattern="^(provisioning|ready|suspended|deleting|deleted)$"
    )

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ResourceOfferRequest(Strict):
    """How much of one capability the platform may use.

    ``unit`` is whatever the calling screen measures in — cores, GiB, devices.
    It is converted once, here, so two screens describing the same machine
    cannot store two different numbers.
    """

    offered_quantity: float = Field(ge=0, alias="offeredQuantity")
    unit: str = Field(min_length=1, max_length=16)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ProjectCreateRequest(Strict):
    """Create a project. The caller becomes its owner.

    ``code`` is constrained because it appears in URLs and in operator
    conversation; a project called "My Project (v2)!" is one nobody can refer to
    unambiguously.
    """

    code: str = Field(pattern="^[a-z][a-z0-9-]{1,62}[a-z0-9]$")
    display_name: str = Field(min_length=1, max_length=200, alias="displayName")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class WorkspaceCreateRequest(Strict):
    name: str = Field(min_length=2, max_length=128)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class WorkspaceToolRequest(Strict):
    """Choose the development tool a workspace uses.

    ``null`` clears the choice. The name is one of the adapters the platform
    knows; ``GET /v1/adapters`` lists them with whether each is usable right
    now, which is a property of a node rather than of this record.
    """

    tool_name: str | None = Field(
        default=None,
        pattern="^(claude-code|codex-cli|gemini-cli|antigravity)$",
        alias="toolName",
    )

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ModelReleaseRequest(Strict):
    """An importer's claim about what it is releasing (VF-CL-03).

    The two fields and their constraints are copied from the kernel's
    ``ModelManifest``, because the point of the request is to be compared
    against that immutable declaration for exact equality. ``extra="forbid"``
    is load-bearing here rather than conventional: a proposal carrying a field
    the declaration does not have is itself a mismatch.

    The request carries a required ``Idempotency-Key`` header (card 113). The
    same key with this same body and path replays the stored
    ``ModelReleaseResponse``; the same key with a different body or path is
    ``GRAPH-0002``/409; a version that is already released is ``GRAPH-0002``/409
    under any other key.
    """

    license_policy: str = Field(min_length=1, max_length=200, alias="licensePolicy")
    classification: str = Field(pattern="^(public|internal|restricted)$")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ModelReleaseResponse(Strict):
    """The released version, echoed back by identity.

    ``stage`` is a literal rather than a free string: the only state this
    response can describe is the one the route just established, so a future
    change that returns a different stage under the same type breaks the
    contract instead of quietly widening it.

    Python field names avoid the ``model_`` prefix because Pydantic reserves
    that namespace; the wire names are the aliases.
    """

    version_id: str = Field(alias="modelVersionId")
    parent_model_id: str = Field(alias="modelId")
    version: str = Field(min_length=1, max_length=64)
    stage: Literal["released"]
    content_sha256: str = Field(pattern="^[0-9a-f]{64}$", alias="contentSha256")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ModelVersionRegisterRequest(Strict):
    """What an importer must state to register one model build (G-04 W2).

    The fields are exactly ``register_model_version``'s own required arguments,
    and nothing more: the service is the judge of what a registration means, so
    a field here that it does not take would be this route inventing state.

    ``contentSha256`` carries the service's rule as a pattern rather than
    trusting it: the service raises ``VAL-SCHEMA`` for a non-lowercase digest
    and the column has ``checksum_is_lowercase``, so a caller who sends
    ``ABC...`` gets a request error at the boundary instead of a service error
    translated later. Both defences stay.

    ``uri`` is **not** here (Codex #191 F2). A caller-supplied URI was accepted
    and stored verbatim, so ``https://user:secret@host``, ``javascript:...`` and
    another model version's ``inv://`` address all persisted -- and the kernel
    manifest's join key assumes the URI's version *is* the row's version. The
    canonical address is fully determined by the model's name and the version, so
    the server derives it instead of validating a string that has no reason to
    vary.

    ``producedByRunId`` and ``lineage`` are deliberately absent -- see the
    module docstring of ``api/v1/model_versions.py`` for why neither can be
    bound to the path's project on this branch.
    """

    version: str = Field(min_length=1, max_length=64)
    content_sha256: str = Field(pattern="^[0-9a-f]{64}$", alias="contentSha256")
    byte_size: int = Field(default=0, ge=0, alias="byteSize")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ModelVersionResponse(Strict):
    """The registered build, echoed back by identity.

    ``stage`` is a literal: registration creates a draft and nothing else, so a
    change that returns a released version under this type breaks the contract
    rather than widening it quietly. There is no person and no free text here --
    the same rule ``LineageDeployment`` states.

    Python field names avoid the ``model_`` prefix because Pydantic reserves
    that namespace; the wire names are the aliases.
    """

    version_id: str = Field(alias="modelVersionId")
    parent_model_id: str = Field(alias="modelId")
    version: str = Field(min_length=1, max_length=64)
    stage: Literal["draft"]
    content_sha256: str = Field(pattern="^[0-9a-f]{64}$", alias="contentSha256")
    byte_size: int = Field(ge=0, alias="byteSize")
    uri: str = Field(min_length=1)
    created_at: dt.datetime = Field(alias="createdAt")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class AdapterReadinessResponse(Strict):
    """One agent CLI's install, login and reachability state (G-01 follow-up).

    #180 recorded that both adapter routes were declared ``-> dict``, so
    ``export_schemas`` generated nothing for them and a change to the response
    shape broke no gate. This closes that for the single-adapter route, where the
    shape is one row and has no variants.

    The fields and their types are **observed**, not inferred: ``agents.readiness()``
    was run and its rows read (eleven keys, the same key set for all four tools),
    and ``probe()`` was run for ``reachable`` and ``latencyMs``. The nullable ones
    are nullable because the tool may be absent (``path``, ``version``), present
    elsewhere (``installedElsewhere``) or have nothing to say
    (``instructions``, ``latencyMs`` when unreachable).

    ``loginDetail`` is the one unbounded field: it is whatever the adapter's
    ``login_state()`` returned, which comes from CLI output. Declaring it as an
    open mapping is honest about that rather than pretending a shape; narrowing it
    -- and deciding whether tool output belongs in a screen-facing response at all
    -- is a separate question this card does not answer.

    The **list** route keeps ``-> dict`` on purpose. Its rows have two shapes: the
    eleven-key row above, and a five-key row when one tool raises
    (``adapter``, ``executable``, ``installed``, ``loginState``, ``error``). A
    response model would fill the missing keys with defaults and so change the
    wire shape a screen sees for a broken tool, which is a public change owned by
    the frontend rather than a side effect of canonicalising a 404.
    """

    adapter: str = Field(min_length=1, max_length=64)
    executable: str = Field(min_length=1, max_length=128)
    installed: bool
    path: str | None = None
    installed_elsewhere: str | None = Field(default=None, alias="installedElsewhere")
    version: str | None = None
    login_state: str = Field(pattern="^(logged_in|logged_out|unknown)$", alias="loginState")
    login_detail: dict[str, Any] = Field(default_factory=dict, alias="loginDetail")
    headless: bool
    missing: list[str] = Field(default_factory=list)
    instructions: str | None = None
    reachable: bool
    latency_ms: int | None = Field(default=None, ge=0, alias="latencyMs")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class EvalRunStartRequest(Strict):
    """What a caller may choose when starting an eval run (G-05 W5).

    Three fields, and what is *absent* matters as much as what is here.

    ``adapter`` is a **name**, not an endpoint or a credential. The server resolves
    it through ``adapters.agents.adapter_for``, whose ``BY_NAME`` is the configured
    allowlist, so a caller can pick one of the platform's four CLIs and nothing
    else. A request that could name a URL would let the caller point this route --
    which spends money -- at a host of their choosing.

    ``componentVersions`` is part of the run's identity: "the agent scored 72%"
    means nothing without which prompt, context and model produced it. It is
    bounded, and the three keys the service fills in itself are **refused**:
    ``run_suite`` merges them with ``setdefault``, so a caller who sent
    ``{"adapter": "something-else"}`` would have their own value recorded as the
    identity of the run. Refusing them is the only place that can be stopped
    without changing the service's signature.

    ``requireModelPinning`` defaults to **true**, which is the service's own
    default: a score from an adapter that cannot say which model build produced it
    is not reproducible. Passing false is allowed and is recorded on the run
    (``modelPinned: "false"``) rather than merely decided at the call site.
    """

    adapter: str = Field(min_length=1, max_length=64, pattern="^[a-z0-9-]+$")
    require_model_pinning: bool = Field(default=True, alias="requireModelPinning")
    component_versions: dict[str, str] = Field(
        default_factory=dict, alias="componentVersions", max_length=32
    )

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class RetentionPinRequest(Strict):
    """What a caller asks of W4: keep this version at least until ``until``.

    One field, because ``pin_retention`` takes one: the service decides what the
    request means (extend, never shorten). The instant must carry an offset --
    a naive time would be compared with the stored aware value by whatever the
    driver assumes, and "retained until when?" is not a question to answer with
    an assumption.
    """

    until: AwareDatetime

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class EvalRunResponse(Strict):
    """The finished run, by identity and by count.

    No case content and no model output: ``eval_results.observed`` is a redacted
    summary and this response does not carry even that. What a caller needs from
    starting a run is which run it was and whether it passed.

    ``passedGate`` is its own field rather than something a reader derives from
    the counts, because the row's own rule is stricter than "passed == total": a
    run with any forbidden-behaviour violation is not a pass whatever the score
    says.
    """

    eval_run_id: str = Field(alias="evalRunId")
    suite_id: str = Field(alias="suiteId")
    status: Literal["running", "completed", "aborted"]
    total_cases: int = Field(ge=0, alias="totalCases")
    passed_cases: int = Field(ge=0, alias="passedCases")
    violations: int = Field(ge=0)
    passed_gate: bool = Field(alias="passedGate")
    component_versions: dict[str, str] = Field(alias="componentVersions")
    started_at: dt.datetime = Field(alias="startedAt")
    ended_at: dt.datetime | None = Field(default=None, alias="endedAt")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class RetentionPinResponse(Strict):
    """The version's retention after the request was judged.

    ``retentionPinnedUntil`` is the committed value, which is the requested one
    only when it extended the pin; ``extended`` says which, so a no-op is
    visible to the caller instead of looking like success by coincidence.
    ``stage`` is whatever the row is in -- a released version can still be
    extended (design §5-3) -- and is the closed set the column allows.
    """

    version_id: str = Field(alias="modelVersionId")
    parent_model_id: str = Field(alias="modelId")
    version: str = Field(min_length=1, max_length=64)
    stage: Literal["draft", "candidate", "released", "retired"]
    retention_pinned_until: AwareDatetime = Field(alias="retentionPinnedUntil")
    extended: bool

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


INV_ID = r"^[a-z]{3}_[0-9A-HJKMNP-TV-Z]{26}$"
MEASUREMENT_ID = r"^mvm_[0-9A-HJKMNP-TV-Z]{26}$"


class ModelVerifyRequest(Strict):
    """What a caller asks of W3: apply this kernel-recorded measurement.

    One field, and ``extra="forbid"`` is load-bearing: a digest, a size or a
    URI in the body would be a value the caller supplied, and verification
    is exactly the thing a caller's value must not be able to establish
    (design #209 v1.1 §6).
    """

    measurement_id: str = Field(pattern=MEASUREMENT_ID, alias="measurementId")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ModelMeasurementObservation(Strict):
    """The kernel's record of one signed node measurement, as the W3 route reads it.

    Served by ``GET /v1/projects/{p}/models/{m}/versions/{v}/measurements/{id}``
    on the kernel (PR A-2 of design #209 v1.1). Every field is what
    ``inv.model_version_measurements`` holds for the identity, the channel
    binding, the storage snapshot and the observation itself; the route
    re-binds each of them before it writes. Unknown keys are refused: an
    observation carrying something this contract does not name is not one
    the route decides on.
    """

    measurement_id: str = Field(pattern=MEASUREMENT_ID, alias="measurementId")
    tenant_id: uuid.UUID = Field(alias="tenantId")
    project_id: str = Field(pattern=INV_ID, alias="projectId")
    model_id: str = Field(pattern=INV_ID, alias="modelId")
    version_id: str = Field(pattern=INV_ID, alias="modelVersionId")
    uri: str = Field(min_length=1, max_length=2048)
    contribution_id: str = Field(pattern=INV_ID, alias="contributionId")
    contribution_version: StrictInt = Field(ge=1, alias="contributionVersion")
    location_id: str = Field(pattern=INV_ID, alias="locationId")
    location_version: StrictInt = Field(ge=1, alias="locationVersion")
    relative_path: str = Field(min_length=1, max_length=4096, alias="relativePath")
    node_id: str = Field(pattern=INV_ID, alias="nodeId")
    recovery_epoch: uuid.UUID = Field(alias="recoveryEpoch")
    channel_version: StrictInt = Field(ge=1, alias="channelVersion")
    certificate_sha256: str = Field(pattern="^[0-9a-f]{64}$", alias="certificateSha256")
    sha256: str = Field(pattern="^[0-9a-f]{64}$")
    byte_size: StrictInt = Field(ge=0, alias="byteSize")
    observed_at: AwareDatetime = Field(alias="observedAt")
    recorded_at: AwareDatetime = Field(alias="recordedAt")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ModelVerifyResponse(Strict):
    """The version after the measurement was bound (or found already bound).

    ``newlyVerified`` is false when the row was already verified by this very
    measurement, so a repeat with a fresh idempotency key is visible as the
    no-op it was.
    """

    version_id: str = Field(alias="modelVersionId")
    parent_model_id: str = Field(alias="modelId")
    version: str = Field(min_length=1, max_length=64)
    stage: Literal["draft", "candidate", "released", "retired"]
    verified_at: AwareDatetime = Field(alias="verifiedAt")
    verified_measurement_id: str = Field(pattern=MEASUREMENT_ID, alias="verifiedMeasurementId")
    content_sha256: str = Field(pattern="^[0-9a-f]{64}$", alias="contentSha256")
    newly_verified: bool = Field(alias="newlyVerified")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class LineageDatasetVersion(Strict):
    dataset_version_id: str = Field(alias="datasetVersionId")
    version: str = Field(min_length=1, max_length=64)
    content_sha256: str = Field(pattern="^[0-9a-f]{64}$", alias="contentSha256")
    uri: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ConformanceCheckDescriptor(Strict):
    """One check the conformance contract defines, named and gated.

    A descriptor, not a result: there is no ``passed`` here because nothing has
    been observed. Read from ``adapters.conformance.CHECKLIST``, which is the
    single source for the list.
    """

    name: str = Field(min_length=1, max_length=100)
    capability_gated: bool = Field(alias="capabilityGated")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class LineageDeployment(Strict):
    """A deployment of the traced version.

    ``deployedByUserId`` and ``notes`` are on the row and are deliberately not
    here: reading lineage does not need a person's identifier or free text.
    """

    deployment_id: str = Field(alias="deploymentId")
    environment: str = Field(pattern="^(lab|staging|pilot)$")
    status: str = Field(pattern="^(pending|active|superseded|rolled_back|failed)$")
    deployed_digest: str = Field(pattern="^[0-9a-f]{64}$", alias="deployedDigest")
    image_id: str | None = Field(default=None, alias="imageId")
    approval_id: str | None = Field(default=None, alias="approvalId")
    deployed_at: dt.datetime = Field(alias="deployedAt")
    superseded_at: dt.datetime | None = Field(default=None, alias="supersededAt")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class LineageUnresolved(Strict):
    """How many subjects of one kind this response does not describe.

    A count and a kind, and nothing else. An identifier would leak another
    project's row, and a reason would tell the caller whether a hidden
    identifier exists -- which is the same disclosure by a longer route.
    """

    kind: str = Field(min_length=1, max_length=32)
    count: int = Field(ge=1)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class RunRecordSealRequest(Strict):
    """What a caller may say when sealing a run (G-04 W1, design §5-2).

    Only the *role* of each server-derived artifact. The sealed set, the
    digests, the bundle and the component versions are derived from the rows
    the server locks; a request cannot add, omit or name any of them. An
    artifact the mapping leaves out is sealed as ``other``; an id outside the
    server's set is refused.
    """

    roles: dict[str, str] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @field_validator("roles")
    @classmethod
    def _roles_are_known(cls, value: dict[str, str]) -> dict[str, str]:
        allowed = {"diff", "test_report", "trace", "log", "model", "dataset", "other"}
        for artifact_id, role in value.items():
            if not (isinstance(artifact_id, str) and artifact_id.startswith("art_") and len(artifact_id) == 30):
                raise ValueError("roles keys must be artifact ids")
            if role not in allowed:
                raise ValueError("unknown artifact role")
        if len(value) > 1000:
            raise ValueError("too many role mappings")
        return value
class ContextBundleItemSummary(Strict):
    """One bundle item without its content: what was read, in what version,
    and the digest and byte length of the text -- never the text itself and
    not the caller-written source URI."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    ordinal: int = Field(ge=0)
    item_id: str = Field(min_length=1, max_length=255, alias="itemId")
    item_version: int = Field(ge=1, alias="itemVersion")
    kind: str = Field(pattern="^(document|code|message|tool_output|summary)$")
    content_hash: str = Field(pattern="^[0-9a-f]{64}$", alias="contentHash")
    byte_size: int = Field(ge=0, alias="byteSize")
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    redacted: bool


class ContextBundleResponse(Strict):
    """A run's context bundle as metadata (G-04 R3).

    ``hashVerified`` is ``verify_bundle``'s answer, reported as a fact: false
    means the stored content no longer reproduces the bundle hash. ``sealed``
    says whether this is the bundle the run's sealed record pins (true) or the
    run's most recently built bundle (false). ``itemCount``/``totalBytes`` are
    the bundle's own columns; ``items`` is the ordered item list. No content,
    no person, no free text.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    bundle_id: str = Field(alias="bundleId")
    run_id: str = Field(alias="runId")
    bundle_hash: str = Field(pattern="^[0-9a-f]{64}$", alias="bundleHash")
    hash_verified: bool = Field(alias="hashVerified")
    sealed: bool
    item_count: int = Field(ge=0, alias="itemCount")
    total_bytes: int = Field(ge=0, alias="totalBytes")
    retrieval_strategy: str = Field(pattern="^(lexical|metadata|hybrid|explicit)$", alias="retrievalStrategy")
    component_versions: dict[str, str] = Field(alias="componentVersions")
    token_estimate: int | None = Field(default=None, ge=0, alias="tokenEstimate")
    built_at: dt.datetime = Field(alias="builtAt")
    items: list[ContextBundleItemSummary]


class RunRecordResponse(Strict):
    """The sealed record of a run, reduced to identifiers, digests and counts.

    No person and no free text: who requested the run and what it produced are
    other routes' business. ``bundleId``/``bundleHash`` are null when the run
    was sealed without a context bundle; that is a fact about the record, not a
    gap in this response.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    record_id: str = Field(alias="recordId")
    run_id: str = Field(alias="runId")
    final_state: str = Field(min_length=1, max_length=16, alias="finalState")
    termination_reason: str = Field(min_length=1, max_length=24, alias="terminationReason")
    evidence_id: str | None = Field(default=None, alias="evidenceId")
    bundle_id: str | None = Field(default=None, alias="bundleId")
    bundle_hash: str | None = Field(default=None, pattern="^[0-9a-f]{64}$", alias="bundleHash")
    workload_spec_sha256: str = Field(pattern="^[0-9a-f]{64}$", alias="workloadSpecSha256")
    component_versions: dict[str, str] = Field(alias="componentVersions")
    attempt_count: int = Field(ge=0, alias="attemptCount")
    sealed_at: dt.datetime = Field(alias="sealedAt")


class RunRecordArtifactPin(Strict):
    """One artifact as the record pinned it: reference, digest and size, no content."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    artifact_id: str = Field(alias="artifactId")
    role: str = Field(pattern="^(diff|test_report|trace|log|model|dataset|other)$")
    uri: str = Field(min_length=1)
    checksum_sha256: str = Field(pattern="^[0-9a-f]{64}$", alias="checksumSha256")
    object_version: str | None = Field(default=None, alias="objectVersion")
    byte_size: int = Field(ge=0, alias="byteSize")


class RunRecordArtifactPageResponse(Strict):
    """One bounded page of the artifacts pinned into a sealed record.

    A record pins the run's whole artifact set, which has no bound of its own,
    so the list is paged: at most ``limit`` (default 50, maximum 200) items in
    stable ``artifactId`` order. ``count`` is the number of items in *this
    page*, never the record's total. ``nextCursor`` is the last item's
    ``artifactId`` when more follow, and null on the last page. ``role`` echoes
    the filter, which holds across pages.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    record_id: str = Field(alias="recordId")
    run_id: str = Field(alias="runId")
    role: str | None = Field(default=None, pattern="^(diff|test_report|trace|log|model|dataset|other)$")
    items: list[RunRecordArtifactPin] = Field(max_length=200)
    count: int = Field(ge=0, le=200)
    next_cursor: str | None = Field(default=None, alias="nextCursor")


class ArtifactPinVerificationResponse(Strict):
    """Whether a pinned artifact still matches the digest sealed into the record.

    ``verified: false`` is a reported fact, not an error: the record stays the
    account of what was true at sealing, and a changed object is an integrity
    finding for the caller.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    record_id: str = Field(alias="recordId")
    run_id: str = Field(alias="runId")
    artifact_id: str = Field(alias="artifactId")
    verified: bool
    #: Required: a pin exists whenever verification ran (the service is 404
    #: otherwise) and its checksum is non-null in the database, so a missing or
    #: null value here would be a fail-open integrity answer (Codex #188 F1).
    pinned_checksum_sha256: str = Field(pattern="^[0-9a-f]{64}$", alias="pinnedChecksumSha256")


class ModelLineageTraceResponse(Strict):
    """AC-10's traceback, reduced to what a project member may be shown.

    ``commits``, ``images``, ``evaluations`` and ``approvals`` are absent rather
    than empty. An empty array would read as "nothing was recorded", which is a
    different and much more alarming statement than "this route cannot prove who
    owns those rows"; the second is what ``unresolved`` and ``countOnlyKinds``
    say.

    ``deployments: []`` *is* an empty array, because it means something
    complete: nothing has been deployed. That difference is the reason the two
    are shaped differently.
    """

    model_version_id: str = Field(alias="modelVersionId")
    version: str = Field(min_length=1, max_length=64)
    stage: str = Field(pattern="^(draft|candidate|released|retired)$")
    content_sha256: str = Field(pattern="^[0-9a-f]{64}$", alias="contentSha256")
    produced_by_run_id: str | None = Field(default=None, alias="producedByRunId")
    datasets: list[LineageDatasetVersion] = Field(max_length=200)
    deployments: list[LineageDeployment] = Field(max_length=200)
    missing: list[str] = Field(max_length=16)
    unresolved: list[LineageUnresolved] = Field(max_length=16)
    truncated: dict[str, int] = Field(default_factory=dict)
    fully_traceable: bool = Field(alias="fullyTraceable")
    traceability_limited_by_scope: bool = Field(alias="traceabilityLimitedByScope")
    detailed_kinds: list[str] = Field(alias="detailedKinds", max_length=16)
    count_only_kinds: list[str] = Field(alias="countOnlyKinds", max_length=16)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ModelVersionByDigest(Strict):
    model_version_id: str = Field(alias="modelVersionId")
    parent_model_id: str = Field(alias="modelId")
    version: str = Field(min_length=1, max_length=64)
    stage: str = Field(pattern="^(draft|candidate|released|retired)$")
    content_sha256: str = Field(pattern="^[0-9a-f]{64}$", alias="contentSha256")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ModelVersionByDatasetDigestPageResponse(Strict):
    """Model versions built from one set of bytes.

    ``datasetVersionIds`` is the set the items were derived from, bounded and
    echoed so a caller can check the derivation rather than take it on trust. It
    is a list because the same bytes may be registered as more than one dataset
    version, and narrowing it to one value would silently drop model versions.
    """

    content_sha256: str = Field(pattern="^[0-9a-f]{64}$", alias="contentSha256")
    dataset_version_ids: list[str] = Field(alias="datasetVersionIds", max_length=200)
    items: list[ModelVersionByDigest] = Field(max_length=200)
    next_cursor: str | None = Field(default=None, alias="nextCursor")
    unresolved_model_versions: int = Field(ge=0, alias="unresolvedModelVersions")
    truncated: dict[str, int] = Field(default_factory=dict)
    complete: bool

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ConformanceStatusResponse(Strict):
    """What this platform can honestly say about adapter conformance (G-03).

    Phase one says **NOT_OBSERVED** and nothing more, because nothing is stored:
    ``run_conformance`` has no product caller and no table. The consequences are
    in the field list rather than in a comment --

    * ``status`` is ``Literal["NOT_OBSERVED"]``, one value. A widened literal
      would advertise ``RECORDED`` in the generated schema before any code can
      produce it; phase two brings that branch in with the counts that make it
      mean something.
    * there is **no** ``conformant`` boolean. A boolean has no third value, so
      "not measured" would have to be spelled ``false``, which reads as "it was
      run and it failed".
    * there are **no counts**. ``passed: 0`` is not the absence of a
      measurement; it is a measurement of zero.
    * ``recordedAt`` is typed ``None``: the only honest value is null, so the
      contract says so rather than trusting the route.

    ``scope`` is the same word ``GET /v1/adapters`` uses. The project in the path
    is who may read this, not who owns it: conformance is a property of the
    control-plane host, not of a tenant's data.
    """

    status: Literal["NOT_OBSERVED"]
    reason: str = Field(min_length=1, max_length=300)
    scope: Literal["control-plane-host"]
    contract_version: str = Field(min_length=1, max_length=32, alias="contractVersion")
    #: The adapters the suite would run against -- a target list, not a result.
    adapters: list[str]
    checks: list[ConformanceCheckDescriptor]
    #: Required, and only ever null: a consumer can rely on the key being
    #: there, and the one value it may hold is the absence of a measurement.
    recorded_at: None = Field(alias="recordedAt")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


# -- G-03 stage two: the RECORDED branches (design #218 v1.2 §4-1) ------------
#
# ``ConformanceStatusResponse`` above keeps its name, its seven keys and its
# contract file: with no record stored the list route still answers exactly
# that shape (only the ``reason`` text moved on, because "does not persist"
# stopped being true). Everything below is what a stored record adds. The two
# union aliases are not ``Strict`` subclasses, so the exporter never sees them
# and each branch is its own contract file.

CONFORMANCE_SUBJECT = Literal["fixture-adapter"]
CONFORMANCE_PROVENANCE = Literal["in-server"]


class ConformanceCheckOutcome(Strict):
    """One check's result as stored: name, passed, skipped. No ``detail``: the
    suite's detail is stringified exceptions and host process output, and this
    row is readable by every project's members (§2-5)."""

    name: str = Field(min_length=1, max_length=100)
    passed: StrictBool
    skipped: StrictBool

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @model_validator(mode="after")
    def _not_both(self) -> "ConformanceCheckOutcome":
        if self.passed and self.skipped:
            raise ValueError("a check cannot be both passed and skipped")
        return self


def _counts_agree(total: int, passed: int, failed: int, skipped: int, outcomes: list) -> None:
    """The response side of §2-8: the four counts and the outcome list must be
    one measurement, not four numbers that merely look like one."""
    if passed + failed + skipped != total:
        raise ValueError("passed + failed + skipped must equal total")
    if len(outcomes) != total:
        raise ValueError("outcomes must have exactly total entries")
    recount = (
        sum(1 for o in outcomes if o.passed and not o.skipped),
        sum(1 for o in outcomes if not o.passed and not o.skipped),
        sum(1 for o in outcomes if o.skipped),
    )
    if recount != (passed, failed, skipped):
        raise ValueError("counts do not match the outcomes")


class ConformanceRecordItem(Strict):
    """One stored record inside ``records[]``. Nested, not a contract file."""

    adapter: str = Field(min_length=1, max_length=64)
    subject: CONFORMANCE_SUBJECT
    provenance: CONFORMANCE_PROVENANCE
    contract_version: str = Field(min_length=1, max_length=32, alias="contractVersion")
    suite_contract_version: str = Field(
        min_length=1, max_length=32, alias="suiteContractVersion"
    )
    total: StrictInt = Field(ge=0)
    passed: StrictInt = Field(ge=0)
    failed: StrictInt = Field(ge=0)
    skipped: StrictInt = Field(ge=0)
    #: Named ``outcomes`` so it is never confused with ``checks`` (descriptors).
    outcomes: list[ConformanceCheckOutcome]
    recorded_at: AwareDatetime = Field(alias="recordedAt")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @model_validator(mode="after")
    def _consistent(self) -> "ConformanceRecordItem":
        _counts_agree(self.total, self.passed, self.failed, self.skipped, self.outcomes)
        return self


class ConformanceStatusRecordedResponse(Strict):
    """The list route when at least one record exists.

    ``records`` follows the order of ``adapters`` and holds only adapters that
    have a record: absence from ``records`` is the absence of a measurement,
    so there is no per-adapter NOT_OBSERVED entry. ``latestRecordedAt`` is the
    maximum of the items' ``recordedAt`` -- the aggregate freshness -- and the
    key is deliberately not ``recordedAt``, which in the NOT_OBSERVED branch is
    always null (§4-1, R2). No ``reason``: nothing is being explained.
    """

    status: Literal["RECORDED"]
    scope: Literal["control-plane-host"]
    contract_version: str = Field(min_length=1, max_length=32, alias="contractVersion")
    adapters: list[str]
    checks: list[ConformanceCheckDescriptor]
    records: list[ConformanceRecordItem] = Field(min_length=1)
    latest_recorded_at: AwareDatetime = Field(alias="latestRecordedAt")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @model_validator(mode="after")
    def _records_are_a_subset_in_order(self) -> "ConformanceStatusRecordedResponse":
        names = [r.adapter for r in self.records]
        if len(set(names)) != len(names):
            raise ValueError("an adapter may appear once in records")
        if [a for a in self.adapters if a in set(names)] != names:
            raise ValueError("records must follow the adapters order and name only listed adapters")
        if self.latest_recorded_at != max(r.recorded_at for r in self.records):
            raise ValueError("latestRecordedAt must be the latest recordedAt")
        return self


class AdapterConformanceNotObservedResponse(Strict):
    """The single-adapter route when the adapter is known but has no record.

    200, not 404: "no such adapter" and "no measurement of this adapter" are
    different facts, and folding the second into the first makes it read as
    the first (§4-3).
    """

    status: Literal["NOT_OBSERVED"]
    reason: str = Field(min_length=1, max_length=300)
    scope: Literal["control-plane-host"]
    adapter: str = Field(min_length=1, max_length=64)
    contract_version: str = Field(min_length=1, max_length=32, alias="contractVersion")
    checks: list[ConformanceCheckDescriptor]
    recorded_at: None = Field(alias="recordedAt")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class AdapterConformanceRecordedResponse(Strict):
    """The single-adapter route's record. Its own class rather than the list
    item, so one side's needs cannot drag the other's contract; the field
    names and types are the item's exactly (§4-1)."""

    status: Literal["RECORDED"]
    scope: Literal["control-plane-host"]
    adapter: str = Field(min_length=1, max_length=64)
    subject: CONFORMANCE_SUBJECT
    provenance: CONFORMANCE_PROVENANCE
    contract_version: str = Field(min_length=1, max_length=32, alias="contractVersion")
    suite_contract_version: str = Field(
        min_length=1, max_length=32, alias="suiteContractVersion"
    )
    total: StrictInt = Field(ge=0)
    passed: StrictInt = Field(ge=0)
    failed: StrictInt = Field(ge=0)
    skipped: StrictInt = Field(ge=0)
    outcomes: list[ConformanceCheckOutcome]
    recorded_at: AwareDatetime = Field(alias="recordedAt")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @model_validator(mode="after")
    def _consistent(self) -> "AdapterConformanceRecordedResponse":
        _counts_agree(self.total, self.passed, self.failed, self.skipped, self.outcomes)
        return self


#: The list route's response: one of two branches, told apart by ``status``.
ConformanceStatusUnion = Annotated[
    Union[ConformanceStatusResponse, ConformanceStatusRecordedResponse],
    Field(discriminator="status"),
]

#: The single-adapter route's response.
AdapterConformanceUnion = Annotated[
    Union[AdapterConformanceNotObservedResponse, AdapterConformanceRecordedResponse],
    Field(discriminator="status"),
]


class ReleaseComponentResponse(Strict):
    """One pinned component of a release.

    Every entry carries a digest because the manifest hash covers the list: a
    name is not an identity, so "we shipped R4" has to be checkable rather than
    asserted (``operations_pilot.ReleaseManifest``).
    """

    name: StrictStr = Field(min_length=1, max_length=200)
    kind: StrictStr = Field(min_length=1, max_length=64)
    digest: StrictStr = Field(min_length=1, max_length=200)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ReleaseAcceptanceResponse(Strict):
    """One recorded acceptance decision, without the person who made it.

    The accepting user is deliberately absent. ``accepted_by_user_id`` is a real
    foreign key precisely so the system cannot sign its own acceptance, but a
    read surface that names people turns an audit column into a directory;
    ``RunRecordResponse`` set that rule first and this follows it. ``notes`` is
    free text and is absent for the same reason.

    ``manifestMatches`` is computed, not stored: an acceptance pins the manifest
    hash as it stood when it was granted, and accepting one composition while
    shipping another is the failure that pinning exists to catch. A reader that
    only saw ``outcome`` could not tell the two apart.
    """

    acceptance_id: StrictStr = Field(alias="acceptanceId", min_length=1, max_length=64)
    acceptance_id_ref: StrictStr = Field(alias="acceptanceIdRef", min_length=1, max_length=16)
    outcome: Literal["accepted", "conditional", "rejected"]
    accepted_manifest_sha256: StrictStr = Field(
        alias="acceptedManifestSha256", pattern="^[0-9a-f]{64}$"
    )
    manifest_matches: StrictBool = Field(alias="manifestMatches")
    known_limitations: list[StrictStr] = Field(
        alias="knownLimitations", default_factory=list, max_length=64
    )
    decided_at: AwareDatetime = Field(alias="decidedAt")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


ReleaseAcceptanceOutcome = Literal["accepted", "conditional", "rejected"]
ReleaseAcceptanceReasonCode = Annotated[StrictStr, Field(pattern="^[A-Z][A-Z0-9_]{2,63}$")]
ReleaseAcceptanceLimitation = Annotated[StrictStr, Field(min_length=1, max_length=300)]


def _exact_lower_hex_sha256(value: Any) -> Any:
    """Reject input that would only match after ``Strict`` whitespace stripping."""

    if not isinstance(value, str) or len(value) != 64 or any(
        char not in "0123456789abcdef" for char in value
    ):
        raise ValueError("must be exactly 64 lowercase hexadecimal characters")
    return value


ReleaseAcceptanceSha256 = Annotated[
    StrictStr,
    Field(min_length=64, max_length=64, pattern="^[0-9a-f]{64}$"),
    BeforeValidator(_exact_lower_hex_sha256),
]


class ReleaseAcceptanceTargetRef(Strict):
    """A desired acceptance target, not evidence that it was measured."""

    target_id: StrictStr = Field(alias="targetId", pattern="^[A-Za-z][A-Za-z0-9_.:/-]{0,127}$")
    target_sha256: ReleaseAcceptanceSha256 = Field(alias="targetSha256")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ReleaseAcceptanceMeasurementRef(Strict):
    """One observed Evidence object, kept distinct from a target declaration."""

    evidence_id: StrictStr = Field(alias="evidenceId", pattern="^[A-Za-z][A-Za-z0-9_.:/-]{0,127}$")
    evidence_sha256: ReleaseAcceptanceSha256 = Field(alias="evidenceSha256")
    observed_at: AwareDatetime = Field(alias="observedAt")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ReleaseAcceptanceDecisionRequest(Strict):
    """The bounded, non-secret content an operator decides on.

    Identity and fresh-authentication proof are deliberately absent: the server
    derives both from the verified access token.  Targets say what was required;
    measurements say what was observed.  Neither may be replaced by free text.
    """

    acceptance_id_ref: StrictStr = Field(alias="acceptanceIdRef", pattern="^[A-Z][A-Z0-9-]{1,15}$")
    outcome: ReleaseAcceptanceOutcome
    target_manifest_sha256: ReleaseAcceptanceSha256 = Field(alias="targetManifestSha256")
    reason_code: ReleaseAcceptanceReasonCode = Field(alias="reasonCode")
    target_refs: list[ReleaseAcceptanceTargetRef] = Field(
        alias="targetRefs", min_length=1, max_length=64
    )
    measurement_refs: list[ReleaseAcceptanceMeasurementRef] = Field(
        alias="measurementRefs", min_length=1, max_length=64
    )
    known_limitations: list[ReleaseAcceptanceLimitation] = Field(
        alias="knownLimitations", max_length=64
    )

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        json_schema_extra={
            "allOf": [
                {
                    "if": {
                        "properties": {"outcome": {"const": "conditional"}},
                        "required": ["outcome"],
                    },
                    "then": {"properties": {"knownLimitations": {"minItems": 1}}},
                    "else": {"properties": {"knownLimitations": {"maxItems": 0}}},
                }
            ]
        },
    )

    @model_validator(mode="after")
    def _decision_is_bounded_and_unambiguous(self) -> "ReleaseAcceptanceDecisionRequest":
        if self.outcome == "conditional" and not self.known_limitations:
            raise ValueError("conditional acceptance requires knownLimitations")
        if self.outcome != "conditional" and self.known_limitations:
            raise ValueError("knownLimitations are allowed only for a conditional decision")
        target_ids = [item.target_id for item in self.target_refs]
        if len(set(target_ids)) != len(target_ids):
            raise ValueError("targetRefs must have unique targetId values")
        evidence_ids = [item.evidence_id for item in self.measurement_refs]
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("measurementRefs must have unique evidenceId values")
        return self


class ReleaseAcceptanceConfirmationRequest(Strict):
    """A second operator confirms one exact accepted proposal and manifest."""

    proposal_digest: ReleaseAcceptanceSha256 = Field(alias="proposalDigest")
    target_manifest_sha256: ReleaseAcceptanceSha256 = Field(alias="targetManifestSha256")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ReleaseAcceptanceProposalResponse(Strict):
    """An accepted decision awaiting a distinct second human operator."""

    proposal_id: StrictStr = Field(alias="proposalId", min_length=1, max_length=64)
    release_id: StrictStr = Field(alias="releaseId", min_length=1, max_length=64)
    acceptance_id_ref: StrictStr = Field(alias="acceptanceIdRef", pattern="^[A-Z][A-Z0-9-]{1,15}$")
    outcome: Literal["accepted"]
    state: Literal["pending_second_operator"]
    target_manifest_sha256: ReleaseAcceptanceSha256 = Field(alias="targetManifestSha256")
    proposal_digest: ReleaseAcceptanceSha256 = Field(alias="proposalDigest")
    required_distinct_operator_count: Literal[2] = Field(alias="requiredDistinctOperatorCount")
    proposal_confirmation_count: Literal[1] = Field(alias="proposalConfirmationCount")
    decision_sign_off: Literal[False] = Field(alias="decisionSignOff")
    expires_at: AwareDatetime = Field(alias="expiresAt")
    replayed: StrictBool

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ReleaseAcceptanceProposalReviewResponse(Strict):
    """The exact pending content a distinct confirmer must review before voting."""

    proposal_id: StrictStr = Field(alias="proposalId", min_length=1, max_length=64)
    release_id: StrictStr = Field(alias="releaseId", min_length=1, max_length=64)
    acceptance_id_ref: StrictStr = Field(alias="acceptanceIdRef", pattern="^[A-Z][A-Z0-9-]{1,15}$")
    outcome: Literal["accepted"]
    state: Literal["pending_second_operator"]
    target_manifest_sha256: ReleaseAcceptanceSha256 = Field(alias="targetManifestSha256")
    proposal_digest: ReleaseAcceptanceSha256 = Field(alias="proposalDigest")
    reason_code: ReleaseAcceptanceReasonCode = Field(alias="reasonCode")
    target_refs: list[ReleaseAcceptanceTargetRef] = Field(
        alias="targetRefs", min_length=1, max_length=64
    )
    measurement_refs: list[ReleaseAcceptanceMeasurementRef] = Field(
        alias="measurementRefs", min_length=1, max_length=64
    )
    known_limitations: list[ReleaseAcceptanceLimitation] = Field(
        alias="knownLimitations", max_length=0
    )
    required_distinct_operator_count: Literal[2] = Field(alias="requiredDistinctOperatorCount")
    proposal_confirmation_count: Literal[1] = Field(alias="proposalConfirmationCount")
    decision_sign_off: Literal[False] = Field(alias="decisionSignOff")
    expires_at: AwareDatetime = Field(alias="expiresAt")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ReleaseAcceptanceProposalReviewPageResponse(Strict):
    """Pending proposals discoverable by an authorized second operator."""

    items: list[ReleaseAcceptanceProposalReviewResponse] = Field(max_length=100)
    next_cursor: StrictStr | None = Field(default=None, alias="nextCursor", min_length=1, max_length=256)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ReleaseAcceptanceRecordedResponse(Strict):
    """A final decision; only two-person ``accepted`` has decision sign-off."""

    acceptance_id: StrictStr = Field(alias="acceptanceId", min_length=1, max_length=64)
    release_id: StrictStr = Field(alias="releaseId", min_length=1, max_length=64)
    acceptance_id_ref: StrictStr = Field(alias="acceptanceIdRef", pattern="^[A-Z][A-Z0-9-]{1,15}$")
    outcome: ReleaseAcceptanceOutcome
    state: Literal["recorded"]
    accepted_manifest_sha256: ReleaseAcceptanceSha256 = Field(alias="acceptedManifestSha256")
    manifest_matches: Literal[True] = Field(alias="manifestMatches")
    decision_sign_off: StrictBool = Field(alias="decisionSignOff")
    decision_confirmation_count: StrictInt = Field(alias="decisionConfirmationCount", ge=1, le=2)
    decided_at: AwareDatetime = Field(alias="decidedAt")
    replayed: StrictBool

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        json_schema_extra={
            "allOf": [
                {
                    "if": {
                        "properties": {"outcome": {"const": "accepted"}},
                        "required": ["outcome"],
                    },
                    "then": {
                        "properties": {
                            "decisionConfirmationCount": {"const": 2},
                            "decisionSignOff": {"const": True},
                        }
                    },
                    "else": {
                        "properties": {
                            "decisionConfirmationCount": {"const": 1},
                            "decisionSignOff": {"const": False},
                        }
                    },
                }
            ]
        },
    )

    @model_validator(mode="after")
    def _quorum_controls_sign_off(self) -> "ReleaseAcceptanceRecordedResponse":
        if self.outcome == "accepted":
            if not self.decision_sign_off or self.decision_confirmation_count != 2:
                raise ValueError("accepted requires two confirmations and decisionSignOff=true")
        elif self.decision_sign_off or self.decision_confirmation_count != 1:
            raise ValueError("conditional and rejected decisions never have decision sign-off")
        return self


class ReleaseAcceptanceWithdrawalRequest(Strict):
    """Withdraw a final decision without deleting or rewriting its history."""

    accepted_manifest_sha256: ReleaseAcceptanceSha256 = Field(alias="acceptedManifestSha256")
    reason_code: Literal[
        "manifest-superseded", "acceptance-error", "security-concern", "operator-request"
    ] = Field(alias="reasonCode")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ReleaseAcceptanceWithdrawalResponse(Strict):
    """An append-only withdrawal receipt with release-scope aggregate sign-off."""

    withdrawal_id: StrictStr = Field(alias="withdrawalId", min_length=1, max_length=64)
    acceptance_id: StrictStr = Field(alias="acceptanceId", min_length=1, max_length=64)
    release_id: StrictStr = Field(alias="releaseId", min_length=1, max_length=64)
    state: Literal["withdrawn"]
    accepted_manifest_sha256: ReleaseAcceptanceSha256 = Field(alias="acceptedManifestSha256")
    withdrawn_acceptance_counts_toward_sign_off: Literal[False] = Field(
        alias="withdrawnAcceptanceCountsTowardSignOff"
    )
    operator_sign_off: StrictBool = Field(alias="operatorSignOff")
    reason_code: Literal[
        "manifest-superseded", "acceptance-error", "security-concern", "operator-request"
    ] = Field(alias="reasonCode")
    withdrawn_at: AwareDatetime = Field(alias="withdrawnAt")
    replayed: StrictBool

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ReleaseManifestResponse(Strict):
    """A recorded release, and what is recorded about accepting it.

    ``operatorSignOff`` is **``Literal[False]``**: this reader cannot emit true,
    and the contract says so rather than the docstring promising it.

    The first version of this model computed it from the acceptance rows and
    called an ``accepted`` row with a matching hash a sign-off, on the reasoning
    that ``acceptance_records.accepted_by_user_id`` is a foreign key to ``users``
    so "the system cannot sign its own acceptance". **That reasoning was wrong,
    and Codex measured it**: ``users`` draws no line between a person and a
    service -- ``identity.py`` builds a Principal from any ``external_subject``
    -- and the foreign key proves only that the row names a user that exists. A
    principal whose subject was ``svc:release-bot`` wrote an ``accepted`` row and
    the field read true. A key that proves existence was read as proof of
    humanity.

    So the field is pinned false until there is a contract for attesting that a
    person decided. ``requiredDistinctOperatorCount`` and
    ``confirmedOperatorCount`` carry a release-wide recorded fact in the
    meantime: the number of distinct users across matching legacy accepted rows.
    They deliberately do not reuse the write contract's proposal-scoped
    ``proposalConfirmationCount`` or decision-scoped
    ``decisionConfirmationCount`` names, and are not sign-off however they were
    written.
    """

    release_id: StrictStr = Field(alias="releaseId", min_length=1, max_length=64)
    version: StrictStr = Field(min_length=1, max_length=64)
    component_count: StrictInt = Field(alias="componentCount", ge=1)
    manifest_sha256: StrictStr = Field(alias="manifestSha256", pattern="^[0-9a-f]{64}$")
    components: list[ReleaseComponentResponse] = Field(default_factory=list, max_length=512)
    created_at: AwareDatetime = Field(alias="createdAt")
    #: Pinned false. Only the write contract may ever make this true, and only
    #: with an attestation that a person decided -- which does not exist yet.
    operator_sign_off: Literal[False] = Field(alias="operatorSignOff")
    #: Why it is false, in the response, so a reader is not left to guess whether
    #: the answer is "nobody signed" or "this surface cannot tell".
    operator_sign_off_blocked_by: Literal["human-attestation-contract-absent"] = Field(
        alias="operatorSignOffBlockedBy"
    )
    #: The quorum the write contract requires. A constant here so a reader sees
    #: "1 of 2" rather than a bare count whose target lives in another document.
    required_distinct_operator_count: Literal[2] = Field(alias="requiredDistinctOperatorCount")
    #: Distinct users with an `accepted` row whose pinned hash matches this
    #: manifest. A recorded fact, not an attestation: a service principal can
    #: contribute to this count, which is exactly why it is not sign-off.
    confirmed_operator_count: StrictInt = Field(alias="confirmedOperatorCount", ge=0)
    acceptance_count: StrictInt = Field(alias="acceptanceCount", ge=0)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ReleaseManifestDetailResponse(Strict):
    """One release with every acceptance decision recorded against it."""

    release: ReleaseManifestResponse
    acceptances: list[ReleaseAcceptanceResponse] = Field(default_factory=list, max_length=256)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ReleaseManifestPageResponse(Strict):
    """A page of releases. An empty tenant is an empty list, not a 404."""

    items: list[ReleaseManifestResponse] = Field(default_factory=list, max_length=200)
    next_cursor: str | None = Field(default=None, alias="nextCursor")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)
