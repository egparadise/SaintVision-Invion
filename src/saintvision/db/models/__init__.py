"""SQLAlchemy models for the S02 scope.

Importing this package registers every table on ``Base.metadata``, which is what
Alembic's autogenerate and the RLS helper both walk.
"""

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
from .operations import ACTOR_TYPES, AUDIT_OUTCOMES, AuditEvent, IdempotencyRecord
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
    "nodes",
    "node_bootstrap_tokens",
    "node_capabilities",
    "resource_offers",
    "resource_snapshots",
    "storage_contributions",
    "data_locations",
    "idempotency_records",
)

#: Range partitioned by month. Both are covered by the partition manager.
PARTITIONED_TABLES: dict[str, str] = {
    "resource_snapshots": "observed_at",
    "audit_events": "occurred_at",
}

__all__ = [
    "ACTOR_TYPES",
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
