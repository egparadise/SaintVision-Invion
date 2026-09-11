"""Backup, recovery drill, release and acceptance (S12-DB, S12-ST).

AC-12 asks for the whole pilot to be *recorded*: the release manifest, the user
acceptance, the recovery evidence, and the known limitations. So the shape of
these tables is mostly about not letting a record claim more than happened.

Three rules the constraints enforce:

* **Targets and measurements are separate columns.** PLAN-DB-001's RPO 15
  minutes and RTO 1 hour are targets; a drill measures. Storing one number and
  calling it both is how a target quietly becomes a result.
* **A database recovery drill that did not check fencing does not pass.**
  ERR-DESIGN-006: a PITR restore rewinds the fencing sequence while the Node
  Agents holding tokens do not rewind with it. A restore drill that verifies
  the data came back and stops there misses exactly that.
* **Acceptance is granted by a person.** ``accepted_by_user_id`` is a real
  foreign key to ``users``; the system cannot sign its own acceptance.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base, InvId, Sha256, TenantId, Utc

BACKUP_KINDS = ("base", "wal", "logical")
DRILL_SCOPES = ("database", "workspace", "artifact", "node")
DRILL_OUTCOMES = ("passed", "failed", "aborted")
ACCEPTANCE_OUTCOMES = ("accepted", "conditional", "rejected")

#: PLAN-DB-001. Targets, not measurements — kept here so a drill row records
#: what it was measured against rather than being compared to a number that
#: lives only in a document.
TARGET_RPO_SECONDS = 15 * 60
TARGET_RTO_SECONDS = 60 * 60
#: 35 day backup retention (PLAN-DB-001).
BACKUP_RETENTION_DAYS = 35


class BackupRecord(Base):
    """One backup that was actually taken.

    ``off_site`` is its own column and is not inferred from the location
    string: ADR-018 separates a locally durable write from a guarantee that
    survives losing the failure domain, and a backup sitting beside the
    database it protects is the case that distinction exists for.
    """

    __tablename__ = "backup_records"
    __table_args__ = (
        UniqueConstraint("tenant_id", "backup_id", name="uq_backup_records_tenant_id_backup_id"),
        CheckConstraint("kind IN ('base','wal','logical')", name="kind_allowed"),
        CheckConstraint("byte_size >= 0", name="byte_size_non_negative"),
        CheckConstraint(
            "completed_at IS NULL OR completed_at >= started_at",
            name="completion_after_start",
        ),
        # A backup nobody verified is a backup nobody has restored.
        CheckConstraint(
            "NOT verified OR (checksum_sha256 IS NOT NULL AND verified_at IS NOT NULL)",
            name="verified_requires_checksum",
        ),
        Index("ix_backup_records_tenant_id_started_at", "tenant_id", "started_at"),
        Index("ix_backup_records_retention_until", "retention_until"),
    )

    backup_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column()
    kind: Mapped[str] = mapped_column(String(16))
    #: Opaque reference to where it lives. Never a credential or a signed URL.
    location_ref: Mapped[str] = mapped_column(Text)
    #: Whether it is outside the failure domain of what it backs up (ADR-018).
    off_site: Mapped[bool] = mapped_column(default=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, default=0)
    checksum_sha256: Mapped[Sha256 | None] = mapped_column(nullable=True)
    verified: Mapped[bool] = mapped_column(default=False)
    verified_at: Mapped[Utc | None] = mapped_column(nullable=True)
    started_at: Mapped[Utc] = mapped_column(server_default=text("now()"))
    completed_at: Mapped[Utc | None] = mapped_column(nullable=True)
    retention_until: Mapped[Utc | None] = mapped_column(nullable=True)


class RecoveryDrill(Base):
    """A rehearsal of getting something back, and what it actually cost.

    ``measured_*`` and ``target_*`` are separate on purpose. A drill that
    exceeded the target is a real result worth keeping — rewriting the target
    to match is how a pilot reports success it did not have.

    ``fencing_verified`` exists because of ERR-DESIGN-006. Restoring the
    database to an earlier point rewinds the fencing sequence while Node Agents
    holding tokens do not rewind, so a restore can either reject live commands
    or accept stale ones. A database drill that has not checked this is not a
    pass, and the constraint says so.
    """

    __tablename__ = "recovery_drills"
    __table_args__ = (
        UniqueConstraint("tenant_id", "drill_id", name="uq_recovery_drills_tenant_id_drill_id"),
        CheckConstraint(
            "scope IN ('database','workspace','artifact','node')", name="scope_allowed"
        ),
        CheckConstraint("outcome IN ('passed','failed','aborted')", name="outcome_allowed"),
        CheckConstraint(
            "measured_rpo_seconds IS NULL OR measured_rpo_seconds >= 0",
            name="measured_rpo_non_negative",
        ),
        CheckConstraint(
            "measured_rto_seconds IS NULL OR measured_rto_seconds >= 0",
            name="measured_rto_non_negative",
        ),
        # A pass requires measurements. "It worked" without numbers is not
        # evidence for a quantitative target.
        CheckConstraint(
            "outcome <> 'passed' OR "
            "(measured_rpo_seconds IS NOT NULL AND measured_rto_seconds IS NOT NULL)",
            name="pass_requires_measurements",
        ),
        # ERR-DESIGN-006: a database restore that did not check fencing
        # monotonicity has not been shown to be safe.
        CheckConstraint(
            "outcome <> 'passed' OR scope <> 'database' OR fencing_verified",
            name="database_pass_requires_fencing_check",
        ),
        CheckConstraint("NOT met_targets OR outcome = 'passed'", name="met_targets_requires_passed"),
        # met_targets is a claim, and it must agree with the measurements.
        CheckConstraint(
            "NOT met_targets OR ("
            "measured_rpo_seconds IS NOT NULL AND measured_rto_seconds IS NOT NULL "
            "AND measured_rpo_seconds <= target_rpo_seconds "
            "AND measured_rto_seconds <= target_rto_seconds)",
            name="met_targets_agrees_with_measurements",
        ),
        Index("ix_recovery_drills_tenant_id_scope", "tenant_id", "scope"),
        Index("ix_recovery_drills_performed_at", "performed_at"),
    )

    drill_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column()
    scope: Mapped[str] = mapped_column(String(16))
    #: What was restored from, when the scope has one.
    backup_id: Mapped[InvId | None] = mapped_column(nullable=True)
    subject_id: Mapped[InvId | None] = mapped_column(nullable=True)
    outcome: Mapped[str] = mapped_column(String(16))
    #: How much data the restore point was behind the failure, in seconds.
    measured_rpo_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: How long until service was usable again.
    measured_rto_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_rpo_seconds: Mapped[int] = mapped_column(Integer, default=TARGET_RPO_SECONDS)
    target_rto_seconds: Mapped[int] = mapped_column(Integer, default=TARGET_RTO_SECONDS)
    met_targets: Mapped[bool] = mapped_column(default=False)
    #: ERR-DESIGN-006. False until someone has checked the fencing sequence was
    #: advanced past the highest token issued before the restore point.
    fencing_verified: Mapped[bool] = mapped_column(default=False)
    fencing_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Verified by checksum, not by the file being present.
    integrity_verified: Mapped[bool] = mapped_column(default=False)
    performed_by_user_id: Mapped[InvId] = mapped_column()
    performed_at: Mapped[Utc] = mapped_column(server_default=text("now()"))
    evidence_id: Mapped[InvId | None] = mapped_column(nullable=True)
    notes: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))


class StorageCheck(Base):
    """A health check of a contributed folder (S12-ST).

    Samples locations and re-hashes them. Presence is not health: the plan
    requires cache checksums be compared against the record before use and
    re-hashed periodically, and a check that only counted files would pass
    while the bytes rotted.
    """

    __tablename__ = "storage_checks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "contribution_id"],
            ["storage_contributions.tenant_id", "storage_contributions.contribution_id"],
        ),
        UniqueConstraint("tenant_id", "check_id", name="uq_storage_checks_tenant_id_check_id"),
        CheckConstraint("sampled_count >= 0", name="sampled_count_non_negative"),
        CheckConstraint("mismatch_count >= 0", name="mismatch_count_non_negative"),
        CheckConstraint(
            "mismatch_count <= sampled_count", name="mismatches_within_sample"
        ),
        CheckConstraint(
            "free_bytes IS NULL OR free_bytes >= 0", name="free_bytes_non_negative"
        ),
        # Any checksum mismatch means the folder is not healthy, whatever else
        # the check found. A corrupted byte is not outvoted by intact ones.
        CheckConstraint(
            "NOT healthy OR (reachable AND mismatch_count = 0)", name="healthy_requires_no_mismatch"
        ),
        Index("ix_storage_checks_tenant_id_checked_at", "tenant_id", "checked_at"),
    )

    check_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column()
    contribution_id: Mapped[InvId] = mapped_column()
    reachable: Mapped[bool] = mapped_column(default=False)
    #: How many catalogued locations were re-hashed for this check.
    sampled_count: Mapped[int] = mapped_column(Integer, default=0)
    mismatch_count: Mapped[int] = mapped_column(Integer, default=0)
    free_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    healthy: Mapped[bool] = mapped_column(default=False)
    checked_at: Mapped[Utc] = mapped_column(server_default=text("now()"))
    detail: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))


class ReleaseManifest(Base):
    """What a release consists of, pinned by digest.

    The manifest hash covers the component list, so "we shipped R4" is a
    checkable statement rather than a label. Same rule as the deployment
    digest: a name is not an identity.
    """

    __tablename__ = "release_manifests"
    __table_args__ = (
        UniqueConstraint("tenant_id", "release_id", name="uq_release_manifests_tenant_id_release_id"),
        UniqueConstraint("tenant_id", "version", name="uq_release_manifests_tenant_id_version"),
        CheckConstraint(
            "manifest_sha256 = lower(manifest_sha256)", name="manifest_hash_is_lowercase"
        ),
        CheckConstraint("component_count > 0", name="component_count_positive"),
        Index("ix_release_manifests_tenant_id_created_at", "tenant_id", "created_at"),
    )

    release_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column()
    version: Mapped[str] = mapped_column(String(64))
    #: [{name, kind, digest}, ...] — every entry carries a digest.
    components: Mapped[list] = mapped_column(JSONB)
    component_count: Mapped[int] = mapped_column(Integer)
    manifest_sha256: Mapped[Sha256] = mapped_column()
    created_by_user_id: Mapped[InvId] = mapped_column()
    created_at: Mapped[Utc] = mapped_column(server_default=text("now()"))


class AcceptanceRecord(Base):
    """A person accepting a release against one acceptance criterion.

    AC-12 requires the known limitations to be recorded, not only the verdict.
    A conditional acceptance with an empty limitation list is a plain
    acceptance wearing a hedge, so the constraint refuses it.

    ``accepted_by_user_id`` is a foreign key to a real user: the system cannot
    sign its own acceptance.
    """

    __tablename__ = "acceptance_records"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "release_id"],
            ["release_manifests.tenant_id", "release_manifests.release_id"],
        ),
        ForeignKeyConstraint(
            ["tenant_id", "accepted_by_user_id"], ["users.tenant_id", "users.user_id"]
        ),
        UniqueConstraint(
            "tenant_id", "acceptance_id", name="uq_acceptance_records_tenant_id_acceptance_id"
        ),
        UniqueConstraint(
            "release_id", "acceptance_id_ref", name="uq_acceptance_records_release_criterion"
        ),
        CheckConstraint(
            "outcome IN ('accepted','conditional','rejected')", name="outcome_allowed"
        ),
        # The manifest that was accepted, pinned. Accepting "R4" and shipping a
        # differently-composed R4 is the failure this prevents.
        CheckConstraint(
            "accepted_manifest_sha256 = lower(accepted_manifest_sha256)",
            name="accepted_hash_is_lowercase",
        ),
        CheckConstraint(
            "outcome <> 'conditional' OR jsonb_array_length(known_limitations) > 0",
            name="conditional_requires_limitations",
        ),
        Index("ix_acceptance_records_tenant_id_release_id", "tenant_id", "release_id"),
    )

    acceptance_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column()
    release_id: Mapped[InvId] = mapped_column()
    #: The acceptance criterion this covers, e.g. "AC-12".
    acceptance_id_ref: Mapped[str] = mapped_column(String(16))
    outcome: Mapped[str] = mapped_column(String(16))
    #: The manifest hash as it stood when accepted.
    accepted_manifest_sha256: Mapped[Sha256] = mapped_column()
    known_limitations: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    accepted_by_user_id: Mapped[InvId] = mapped_column()
    decided_at: Mapped[Utc] = mapped_column(server_default=text("now()"))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class PermissionSnapshot(Base):
    """Who could do what, at a moment, hashed.

    Taken at pilot acceptance so "권한" is an artefact rather than a memory.
    The digest lets a later snapshot be compared without diffing the payload by
    eye.
    """

    __tablename__ = "permission_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "snapshot_id", name="uq_permission_snapshots_tenant_id_snapshot_id"
        ),
        CheckConstraint(
            "subject_type IN ('user','role','node','app_role')", name="subject_type_allowed"
        ),
        CheckConstraint("digest_sha256 = lower(digest_sha256)", name="digest_is_lowercase"),
        Index("ix_permission_snapshots_tenant_id_taken_at", "tenant_id", "taken_at"),
    )

    snapshot_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column()
    subject_type: Mapped[str] = mapped_column(String(16))
    subject_id: Mapped[str] = mapped_column(String(64))
    grants: Mapped[list] = mapped_column(JSONB)
    digest_sha256: Mapped[Sha256] = mapped_column()
    taken_at: Mapped[Utc] = mapped_column(server_default=text("now()"))
