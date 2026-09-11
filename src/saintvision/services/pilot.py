"""Pilot operations: backups, recovery drills, release and acceptance (S12).

AC-12 wants the pilot recorded — the release manifest, the acceptance, the
recovery evidence and the known limitations. The job of this module is to make
those records honest, which mostly means refusing to write a claim that the
measurements do not support.

The one piece of judgement worth stating: a database recovery drill must check
that the fencing sequence was advanced past the highest token issued before the
restore point. That is ERR-DESIGN-006, raised in the HO-DOC-CLAUDE-001 review
and still awaiting an ADR from Codex. Until that decision lands, the drill
refuses to pass without the check — an open design question should block a
claim of success, not be silently assumed away.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db.models import (
    TARGET_RPO_SECONDS,
    TARGET_RTO_SECONDS,
    AcceptanceRecord,
    BackupRecord,
    DataLocation,
    PermissionSnapshot,
    RecoveryDrill,
    ReleaseManifest,
    StorageCheck,
    StorageContribution,
)
from ..errors import RES_ARTIFACT_NOT_FOUND, VAL_SCHEMA, InvError
from ..ids import new_id

BACKUP_KINDS = ("base", "wal", "logical")
DRILL_SCOPES = ("database", "workspace", "artifact", "node")


@dataclass(frozen=True, slots=True)
class DrillMeasurement:
    """What a drill actually measured.

    Both fields are required for a pass. "The restore worked" without numbers
    is not evidence for a quantitative target.
    """

    rpo_seconds: int
    rto_seconds: int

    def validate(self) -> None:
        if self.rpo_seconds < 0 or self.rto_seconds < 0:
            raise InvError(VAL_SCHEMA, "measured durations must not be negative")


@dataclass(frozen=True, slots=True)
class ReleaseComponent:
    name: str
    kind: str
    digest: str

    def validate(self) -> None:
        if not self.name or not self.kind:
            raise InvError(VAL_SCHEMA, "a release component needs a name and a kind")
        if not self.digest:
            # A component without a digest makes the manifest unverifiable, and
            # the manifest is the whole point.
            raise InvError(
                VAL_SCHEMA, f"release component {self.name!r} has no digest"
            )


def canonical_digest(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def record_backup(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    kind: str,
    location_ref: str,
    now: dt.datetime,
    off_site: bool = False,
    byte_size: int = 0,
    retention_days: int = 35,
) -> BackupRecord:
    """Record a backup that was taken.

    ``off_site`` is the caller's assertion and is stored as one. ADR-018
    separates a locally durable write from surviving the loss of the failure
    domain, and a backup beside the database it protects is why that
    distinction is in the plan.
    """
    if kind not in BACKUP_KINDS:
        raise InvError(VAL_SCHEMA, f"unknown backup kind: {kind!r}")

    row = BackupRecord(
        backup_id=new_id("backup"),
        tenant_id=tenant_id,
        kind=kind,
        location_ref=location_ref,
        off_site=off_site,
        byte_size=byte_size,
        started_at=now,
        retention_until=now + dt.timedelta(days=retention_days),
    )
    session.add(row)
    session.flush()
    return row


def verify_backup(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    backup_id: str,
    checksum_sha256: str,
    now: dt.datetime,
) -> BackupRecord:
    """Mark a backup verified. Requires a checksum — presence is not verification."""
    row = session.get(BackupRecord, backup_id)
    if row is None or row.tenant_id != tenant_id:
        raise InvError(RES_ARTIFACT_NOT_FOUND, "backup not found")
    if (
        len(checksum_sha256 or "") != 64
        or not all(c in "0123456789abcdef" for c in checksum_sha256)
    ):
        raise InvError(VAL_SCHEMA, "checksum must be a lowercase hex SHA-256")
    row.checksum_sha256 = checksum_sha256
    row.verified = True
    row.verified_at = now
    session.flush()
    return row


def record_recovery_drill(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    scope: str,
    outcome: str,
    performed_by_user_id: str,
    now: dt.datetime,
    measurement: DrillMeasurement | None = None,
    backup_id: str | None = None,
    subject_id: str | None = None,
    fencing_verified: bool = False,
    fencing_note: str | None = None,
    integrity_verified: bool = False,
    evidence_id: str | None = None,
    target_rpo_seconds: int = TARGET_RPO_SECONDS,
    target_rto_seconds: int = TARGET_RTO_SECONDS,
    notes: dict[str, Any] | None = None,
) -> RecoveryDrill:
    """Record a recovery rehearsal.

    ``met_targets`` is computed from the measurements rather than accepted from
    the caller, so the flag and the numbers cannot disagree. A drill that
    exceeded the target is still recorded as a pass if it restored correctly —
    it just did not meet the target, and both facts are kept.
    """
    if scope not in DRILL_SCOPES:
        raise InvError(VAL_SCHEMA, f"unknown drill scope: {scope!r}")
    if outcome not in ("passed", "failed", "aborted"):
        raise InvError(VAL_SCHEMA, f"unknown drill outcome: {outcome!r}")

    if outcome == "passed":
        if measurement is None:
            raise InvError(
                VAL_SCHEMA,
                "a passing drill must carry measured RPO and RTO; "
                "'it worked' is not evidence for a quantitative target",
            )
        if not integrity_verified:
            raise InvError(
                VAL_SCHEMA,
                "a passing drill must have verified integrity by checksum, "
                "not by the data being present",
            )
        if scope == "database" and not fencing_verified:
            # ERR-DESIGN-006, still awaiting an ADR. An open design question
            # blocks the claim rather than being assumed away.
            raise InvError(
                VAL_SCHEMA,
                "a database recovery drill cannot pass without verifying that the "
                "fencing sequence was advanced past the last token issued before "
                "the restore point (ERR-DESIGN-006)",
            )
    if measurement is not None:
        measurement.validate()

    met = bool(
        outcome == "passed"
        and measurement
        and measurement.rpo_seconds <= target_rpo_seconds
        and measurement.rto_seconds <= target_rto_seconds
    )

    row = RecoveryDrill(
        drill_id=new_id("drill"),
        tenant_id=tenant_id,
        scope=scope,
        backup_id=backup_id,
        subject_id=subject_id,
        outcome=outcome,
        measured_rpo_seconds=measurement.rpo_seconds if measurement else None,
        measured_rto_seconds=measurement.rto_seconds if measurement else None,
        target_rpo_seconds=target_rpo_seconds,
        target_rto_seconds=target_rto_seconds,
        met_targets=met,
        fencing_verified=fencing_verified,
        fencing_note=fencing_note,
        integrity_verified=integrity_verified,
        performed_by_user_id=performed_by_user_id,
        performed_at=now,
        evidence_id=evidence_id,
        notes=notes or {},
    )
    session.add(row)
    session.flush()
    return row


def record_storage_check(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    contribution_id: str,
    now: dt.datetime,
    reachable: bool,
    sampled_count: int = 0,
    mismatch_count: int = 0,
    free_bytes: int | None = None,
    detail: dict[str, Any] | None = None,
) -> StorageCheck:
    """Record a contributed folder health check.

    ``healthy`` is derived: any checksum mismatch makes the folder unhealthy
    however many files were intact. A corrupted byte is not outvoted.
    """
    contribution = session.get(StorageContribution, contribution_id)
    if contribution is None or contribution.tenant_id != tenant_id:
        raise InvError(RES_ARTIFACT_NOT_FOUND, "storage contribution not found")
    if mismatch_count > sampled_count:
        raise InvError(VAL_SCHEMA, "more mismatches than samples")

    row = StorageCheck(
        check_id=new_id("storage_check"),
        tenant_id=tenant_id,
        contribution_id=contribution_id,
        reachable=reachable,
        sampled_count=sampled_count,
        mismatch_count=mismatch_count,
        free_bytes=free_bytes,
        healthy=bool(reachable and mismatch_count == 0),
        checked_at=now,
        detail=detail or {},
    )
    session.add(row)
    session.flush()
    return row


def contributions_needing_attention(
    session: Session, *, tenant_id: uuid.UUID, now: dt.datetime, stale_after_days: int = 7
) -> list[dict[str, Any]]:
    """Active contributions that are unhealthy or have not been checked lately.

    A folder that was healthy a month ago and has not been looked at since is
    reported alongside one that failed, because both mean the same thing
    operationally: nobody currently knows.
    """
    cutoff = now - dt.timedelta(days=stale_after_days)
    latest = (
        select(
            StorageCheck.contribution_id.label("contribution_id"),
            func.max(StorageCheck.checked_at).label("last_checked"),
        )
        .where(StorageCheck.tenant_id == tenant_id)
        .group_by(StorageCheck.contribution_id)
        .subquery()
    )
    rows = session.execute(
        select(StorageContribution, latest.c.last_checked)
        .join(
            latest,
            latest.c.contribution_id == StorageContribution.contribution_id,
            isouter=True,
        )
        .where(
            StorageContribution.tenant_id == tenant_id,
            StorageContribution.status == "active",
        )
    ).all()

    out: list[dict[str, Any]] = []
    for contribution, last_checked in rows:
        if last_checked is None:
            reason = "never checked"
        elif last_checked < cutoff:
            reason = "stale"
        else:
            healthy = session.scalar(
                select(StorageCheck.healthy)
                .where(
                    StorageCheck.tenant_id == tenant_id,
                    StorageCheck.contribution_id == contribution.contribution_id,
                )
                .order_by(StorageCheck.checked_at.desc())
                .limit(1)
            )
            if healthy:
                continue
            reason = "unhealthy"
        out.append(
            {
                "contributionId": contribution.contribution_id,
                "nodeId": contribution.node_id,
                "reason": reason,
                "lastChecked": last_checked,
            }
        )
    return out


def create_release_manifest(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    version: str,
    components: list[ReleaseComponent],
    created_by_user_id: str,
    now: dt.datetime,
) -> ReleaseManifest:
    """Pin what a release consists of.

    Every component carries a digest, so "we shipped R4" becomes checkable
    rather than a label. The manifest hash covers the ordered component list.
    """
    if not components:
        raise InvError(VAL_SCHEMA, "a release manifest needs at least one component")
    for component in components:
        component.validate()

    payload = [
        {"name": c.name, "kind": c.kind, "digest": c.digest}
        for c in sorted(components, key=lambda c: (c.kind, c.name))
    ]
    row = ReleaseManifest(
        release_id=new_id("release"),
        tenant_id=tenant_id,
        version=version,
        components=payload,
        component_count=len(payload),
        manifest_sha256=canonical_digest(payload),
        created_by_user_id=created_by_user_id,
        created_at=now,
    )
    session.add(row)
    session.flush()
    return row


def record_acceptance(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    release_id: str,
    acceptance_criterion: str,
    outcome: str,
    accepted_by_user_id: str,
    now: dt.datetime,
    known_limitations: list[str] | None = None,
    notes: str | None = None,
) -> AcceptanceRecord:
    """Record a person's decision on a release.

    The manifest hash is read from the release, not supplied: accepting "R4"
    and shipping a differently-composed R4 is the failure this prevents.

    A conditional acceptance without limitations is refused — that is a plain
    acceptance wearing a hedge, and AC-12 asks for the limitations to be
    recorded.
    """
    if outcome not in ("accepted", "conditional", "rejected"):
        raise InvError(VAL_SCHEMA, f"unknown acceptance outcome: {outcome!r}")

    release = session.get(ReleaseManifest, release_id)
    if release is None or release.tenant_id != tenant_id:
        raise InvError(RES_ARTIFACT_NOT_FOUND, "release manifest not found")

    limitations = list(known_limitations or [])
    if outcome == "conditional" and not limitations:
        raise InvError(
            VAL_SCHEMA,
            "a conditional acceptance must record what it is conditional on",
        )

    row = AcceptanceRecord(
        acceptance_id=new_id("acceptance"),
        tenant_id=tenant_id,
        release_id=release_id,
        acceptance_id_ref=acceptance_criterion,
        outcome=outcome,
        accepted_manifest_sha256=release.manifest_sha256,
        known_limitations=limitations,
        accepted_by_user_id=accepted_by_user_id,
        decided_at=now,
        notes=notes,
    )
    session.add(row)
    session.flush()
    return row


def take_permission_snapshot(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    subject_type: str,
    subject_id: str,
    grants: list[dict[str, Any]],
    now: dt.datetime,
) -> PermissionSnapshot:
    if subject_type not in ("user", "role", "node", "app_role"):
        raise InvError(VAL_SCHEMA, f"unknown subject type: {subject_type!r}")

    ordered = sorted(grants, key=lambda g: json.dumps(g, sort_keys=True, default=str))
    row = PermissionSnapshot(
        snapshot_id=new_id("permission_snapshot"),
        tenant_id=tenant_id,
        subject_type=subject_type,
        subject_id=subject_id,
        grants=ordered,
        digest_sha256=canonical_digest(ordered),
        taken_at=now,
    )
    session.add(row)
    session.flush()
    return row


def pilot_readiness(
    session: Session, *, tenant_id: uuid.UUID, release_id: str, now: dt.datetime
) -> dict[str, Any]:
    """Whether the evidence AC-12 requires actually exists for this release.

    Returns the gaps, not a verdict dressed as one. Every ``blocker`` is
    something that has not been recorded — the function does not decide whether
    the pilot is good, only whether it can be shown.
    """
    release = session.get(ReleaseManifest, release_id)
    if release is None or release.tenant_id != tenant_id:
        raise InvError(RES_ARTIFACT_NOT_FOUND, "release manifest not found")

    acceptances = list(
        session.scalars(
            select(AcceptanceRecord).where(
                AcceptanceRecord.tenant_id == tenant_id,
                AcceptanceRecord.release_id == release_id,
            )
        ).all()
    )
    database_drills = list(
        session.scalars(
            select(RecoveryDrill).where(
                RecoveryDrill.tenant_id == tenant_id,
                RecoveryDrill.scope == "database",
                RecoveryDrill.outcome == "passed",
            )
        ).all()
    )
    verified_backups = session.scalar(
        select(func.count())
        .select_from(BackupRecord)
        .where(BackupRecord.tenant_id == tenant_id, BackupRecord.verified.is_(True))
    )
    off_site_backups = session.scalar(
        select(func.count())
        .select_from(BackupRecord)
        .where(
            BackupRecord.tenant_id == tenant_id,
            BackupRecord.verified.is_(True),
            BackupRecord.off_site.is_(True),
        )
    )
    unhealthy = contributions_needing_attention(session, tenant_id=tenant_id, now=now)

    blockers: list[str] = []
    if not acceptances:
        blockers.append("no acceptance record for this release")
    if any(a.outcome == "rejected" for a in acceptances):
        blockers.append("a rejected acceptance stands against this release")
    if any(a.accepted_manifest_sha256 != release.manifest_sha256 for a in acceptances):
        blockers.append("an acceptance refers to a different manifest than the current one")
    if not database_drills:
        blockers.append("no passing database recovery drill")
    if not verified_backups:
        blockers.append("no verified backup")
    if not off_site_backups:
        # ADR-018: local durability is not recovery from losing the domain.
        blockers.append("no verified off-site backup")
    if unhealthy:
        blockers.append(f"{len(unhealthy)} contributed folder(s) need attention")

    limitations: list[str] = []
    for record in acceptances:
        limitations.extend(record.known_limitations or [])
    missed_targets = [
        {
            "drillId": d.drill_id,
            "measuredRpoSeconds": d.measured_rpo_seconds,
            "measuredRtoSeconds": d.measured_rto_seconds,
            "targetRpoSeconds": d.target_rpo_seconds,
            "targetRtoSeconds": d.target_rto_seconds,
        }
        for d in database_drills
        if not d.met_targets
    ]

    return {
        "releaseId": release_id,
        "version": release.version,
        "manifestSha256": release.manifest_sha256,
        "acceptances": [
            {"criterion": a.acceptance_id_ref, "outcome": a.outcome} for a in acceptances
        ],
        "knownLimitations": limitations,
        # A drill can pass and still miss the target. Both are reported.
        "drillsMissingTargets": missed_targets,
        "contributionsNeedingAttention": unhealthy,
        "blockers": blockers,
        "evidenceComplete": not blockers,
    }
