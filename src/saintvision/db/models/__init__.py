"""SQLAlchemy models for the S02, S03, S09, S10 and S12 scope, plus node
discovery and resource pools.

Importing this package registers every table on ``Base.metadata``, which is what
Alembic's autogenerate and the RLS helper both walk.
"""

from .artifacts import (
    ARTIFACT_STATUSES,
    DEFAULT_PART_BYTES,
    MAX_ARTIFACT_BYTES,
    UPLOAD_STATUSES,
    Artifact,
    UploadSession,
)
from .context import (
    CONTEXT_ITEM_KINDS,
    SNAPSHOT_SOFT_LIMIT_BYTES,
    ContextBundle,
    ContextBundleItem,
    ContextSnapshot,
    RunRecord,
    RunRecordArtifact,
)
from .discovery import (
    ANNOUNCEMENT_STATES,
    ANNOUNCEMENT_TTL_SECONDS,
    MAX_CANDIDATES_PER_TENANT,
    POOL_STATUSES,
    NodeAnnouncement,
    ResourcePool,
    ResourcePoolMember,
)
from .evaluation import (
    EVAL_CATEGORIES,
    EVAL_OUTCOMES,
    EvalCase,
    EvalResult,
    EvalRun,
    EvalSuite,
)
from .evidence import (
    EVIDENCE_RESULTS,
    OUTBOX_STATUSES,
    EvidenceEnvelope,
    InboxEvent,
    OutboxEvent,
)
from .execution import (
    STEP_STATUSES,
    VOLUME_KINDS,
    WORKSPACE_STATUSES,
    Approval,
    Checkpoint,
    Run,
    RunAttempt,
    Step,
    Workload,
    Workspace,
    WorkspaceVolume,
)
from .lineage import (
    DEPLOYMENT_ENVIRONMENTS,
    DEPLOYMENT_STATUSES,
    LINEAGE_KINDS,
    CodeCommit,
    ContainerImage,
    Dataset,
    DatasetVersion,
    Deployment,
    Model,
    ModelLineage,
    ModelVersion,
)
from .identity import (
    PROJECT_STATUSES,
    USER_STATUSES,
    Project,
    ProjectMember,
    Role,
    Tenant,
    User,
    UserRole,
)
from .handoff import (
    BINDING_STATES,
    ExecutionBinding,
    WorkspaceEditLock,
)
from .locality import (
    CACHE_FILL_LIMIT,
    MAX_CONCURRENT_TRANSFERS,
    REPLICA_STATES,
    DataReplica,
    NodeLink,
)
from .operations import ACTOR_TYPES, AUDIT_OUTCOMES, AuditEvent, IdempotencyRecord
from .operations_pilot import (
    ACCEPTANCE_OUTCOMES,
    BACKUP_KINDS,
    BACKUP_RETENTION_DAYS,
    DRILL_OUTCOMES,
    DRILL_SCOPES,
    TARGET_RPO_SECONDS,
    TARGET_RTO_SECONDS,
    AcceptanceRecord,
    BackupRecord,
    PermissionSnapshot,
    RecoveryDrill,
    ReleaseManifest,
    StorageCheck,
)
from .placement import (
    PLACEMENT_STATES,
    PLAN_STATES,
    PLAN_STRATEGIES,
    DistributedPlan,
    PlanPlacement,
)
from .resource import (
    CAPABILITY_KINDS,
    NODE_STATUSES,
    Node,
    NodeBootstrapToken,
    NodeCapability,
    ResourceOffer,
    ResourceSnapshot,
)
from .storage import (
    CONTRIBUTION_MODES,
    CONTRIBUTION_STATUSES,
    LOCATION_KINDS,
    DataLocation,
    StorageContribution,
)

#: Tables carrying a mandatory tenant_id. RLS is enabled and forced on exactly
#: these, and the migration test asserts the two lists agree.
TENANT_SCOPED_TABLES: tuple[str, ...] = (
    "users",
    "roles",
    "user_roles",
    "projects",
    "project_members",
    "workspace_edit_locks",
    "execution_bindings",
    "nodes",
    "node_bootstrap_tokens",
    "node_capabilities",
    "resource_offers",
    "resource_snapshots",
    "storage_contributions",
    "data_locations",
    "idempotency_records",
    # S03
    "workspaces",
    "workspace_volumes",
    "workloads",
    "runs",
    "run_attempts",
    "steps",
    "checkpoints",
    "approvals",
    "evidence_envelopes",
    "outbox_events",
    "inbox_events",
    "artifacts",
    "upload_sessions",
    # S09
    "context_snapshots",
    "context_bundles",
    "context_bundle_items",
    "run_records",
    "run_record_artifacts",
    "eval_suites",
    "eval_cases",
    "eval_runs",
    "eval_results",
    # S10
    "datasets",
    "dataset_versions",
    "code_commits",
    "container_images",
    "models",
    "model_versions",
    "model_lineage",
    "deployments",
    # S12
    "backup_records",
    "recovery_drills",
    "storage_checks",
    "release_manifests",
    "acceptance_records",
    "permission_snapshots",
    # discovery and pools
    "node_announcements",
    "resource_pools",
    "resource_pool_members",
    "distributed_plans",
    "plan_placements",
    "data_replicas",
    "node_links",
)

#: Range partitioned by month. Both are covered by the partition manager.
PARTITIONED_TABLES: dict[str, str] = {
    "resource_snapshots": "observed_at",
    "audit_events": "occurred_at",
    "evidence_envelopes": "recorded_at",
}

#: Tables the application role may INSERT and SELECT but never UPDATE or
#: DELETE. Append-only for the application; not a WORM claim (PLAN-DB-001).
APPEND_ONLY_TABLES: tuple[str, ...] = (
    "audit_events",
    "evidence_envelopes",
    # A sealed RunRecord is the account of what happened; rewriting one
    # after the fact is exactly what it exists to prevent.
    "run_records",
    "run_record_artifacts",
    # Snapshots are immutable by construction — the hash is part of the
    # key — so UPDATE is meaningless and DELETE belongs to the orphan
    # collector, which runs as the owner, not the application.
    "context_snapshots",
)

#: Tables whose *identity* is immutable but whose lifecycle advances. The
#: application role gets column-level UPDATE on exactly these columns and no
#: others, so content_sha256 and version cannot be rewritten while stage,
#: verification and the retention pin can still move forward.
#:
#: Blanket append-only was the first attempt and was wrong: a model version has
#: to become verified, pinned and released after it is inserted, and CI caught
#: the contradiction as "permission denied for table model_versions".
LIFECYCLE_UPDATE_COLUMNS: dict[str, tuple[str, ...]] = {
    "dataset_versions": ("retention_pinned_until",),
    "model_versions": ("stage", "verified_at", "retention_pinned_until"),
}

__all__ = [
    "BINDING_STATES",
    "ExecutionBinding",
    "WorkspaceEditLock",
    "ACCEPTANCE_OUTCOMES",
    "CACHE_FILL_LIMIT",
    "DataReplica",
    "MAX_CONCURRENT_TRANSFERS",
    "NodeLink",
    "REPLICA_STATES",
    "DistributedPlan",
    "PLACEMENT_STATES",
    "PLAN_STATES",
    "PLAN_STRATEGIES",
    "PlanPlacement",
    "ANNOUNCEMENT_STATES",
    "ANNOUNCEMENT_TTL_SECONDS",
    "MAX_CANDIDATES_PER_TENANT",
    "NodeAnnouncement",
    "POOL_STATUSES",
    "ResourcePool",
    "ResourcePoolMember",
    "ACTOR_TYPES",
    "AcceptanceRecord",
    "BACKUP_KINDS",
    "BACKUP_RETENTION_DAYS",
    "BackupRecord",
    "DRILL_OUTCOMES",
    "DRILL_SCOPES",
    "PermissionSnapshot",
    "RecoveryDrill",
    "ReleaseManifest",
    "StorageCheck",
    "TARGET_RPO_SECONDS",
    "TARGET_RTO_SECONDS",
    "LIFECYCLE_UPDATE_COLUMNS",
    "CodeCommit",
    "ContainerImage",
    "DEPLOYMENT_ENVIRONMENTS",
    "DEPLOYMENT_STATUSES",
    "Dataset",
    "DatasetVersion",
    "Deployment",
    "LINEAGE_KINDS",
    "Model",
    "ModelLineage",
    "ModelVersion",
    "CONTEXT_ITEM_KINDS",
    "ContextBundle",
    "ContextBundleItem",
    "ContextSnapshot",
    "EVAL_CATEGORIES",
    "EVAL_OUTCOMES",
    "EvalCase",
    "EvalResult",
    "EvalRun",
    "EvalSuite",
    "RunRecord",
    "RunRecordArtifact",
    "SNAPSHOT_SOFT_LIMIT_BYTES",
    "APPEND_ONLY_TABLES",
    "ARTIFACT_STATUSES",
    "Approval",
    "Artifact",
    "Checkpoint",
    "DEFAULT_PART_BYTES",
    "EVIDENCE_RESULTS",
    "EvidenceEnvelope",
    "InboxEvent",
    "MAX_ARTIFACT_BYTES",
    "OUTBOX_STATUSES",
    "OutboxEvent",
    "Run",
    "RunAttempt",
    "STEP_STATUSES",
    "Step",
    "UPLOAD_STATUSES",
    "UploadSession",
    "VOLUME_KINDS",
    "WORKSPACE_STATUSES",
    "Workload",
    "Workspace",
    "WorkspaceVolume",
    "AUDIT_OUTCOMES",
    "AuditEvent",
    "CAPABILITY_KINDS",
    "CONTRIBUTION_MODES",
    "CONTRIBUTION_STATUSES",
    "DataLocation",
    "IdempotencyRecord",
    "LOCATION_KINDS",
    "NODE_STATUSES",
    "Node",
    "NodeBootstrapToken",
    "NodeCapability",
    "PARTITIONED_TABLES",
    "PROJECT_STATUSES",
    "Project",
    "ProjectMember",
    "ResourceOffer",
    "ResourceSnapshot",
    "Role",
    "StorageContribution",
    "TENANT_SCOPED_TABLES",
    "Tenant",
    "USER_STATUSES",
    "User",
    "UserRole",
]
