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
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, StrictStr


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
    state: Literal["candidate"]

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
