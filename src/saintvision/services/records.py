"""Sealing a RunRecord and pinning its artifacts (S09-DB, S09-ST).

A RunRecord is written once, when a Run reaches a terminal state, and is never
revised. That is why the application role has INSERT and SELECT on it and
nothing else: an amendable record of what happened is not a record.

Pinning matters as much as sealing. ADR-010 requires the *resolved* object
version and digest to be fixed into the record — storing only the ``inv://``
name would let a later overwrite quietly change what a finished run referred
to, and the run would still look reproducible.
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Artifact, ContextBundle, Run, RunRecord, RunRecordArtifact, Workload
from ..errors import (
    RES_ARTIFACT_NOT_FOUND,
    RES_RUN_NOT_FOUND,
    VAL_SCHEMA,
    InvError,
)
from ..ids import new_id
from ..runs.state import is_terminal

ARTIFACT_ROLES = ("diff", "test_report", "trace", "log", "model", "dataset", "other")


@dataclass(frozen=True, slots=True)
class ArtifactPin:
    artifact_id: str
    role: str


def seal_run_record(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    run_id: str,
    now: dt.datetime,
    component_versions: dict[str, str] | None = None,
    artifacts: list[ArtifactPin] | None = None,
    bundle_id: str | None = None,
) -> RunRecord:
    """Write the immutable record of a finished Run.

    Refuses on a Run that has not ended: a record of an unfinished run would
    have to be updated later, which is the thing sealing prevents.

    Only verified artifacts can be pinned. An artifact without a checksum has
    not been proven to be what it claims (ADR-011), and pinning it would put an
    unverified digest into the permanent record.
    """
    run = session.get(Run, run_id)
    if run is None or run.tenant_id != tenant_id:
        raise InvError(RES_RUN_NOT_FOUND, "run not found")
    if not is_terminal(run.state):
        raise InvError(
            VAL_SCHEMA,
            f"a run record can only be sealed for a finished run, not one in {run.state}",
            cause_ref=run_id,
        )

    existing = session.scalar(select(RunRecord).where(RunRecord.run_id == run_id))
    if existing is not None:
        # Not an error the caller must handle: sealing twice usually means a
        # retried request, and the record is identical either way.
        return existing

    workload = session.get(Workload, run.workload_id)

    resolved_bundle_hash: str | None = None
    if bundle_id is not None:
        bundle = session.get(ContextBundle, bundle_id)
        if bundle is None or bundle.tenant_id != tenant_id or bundle.run_id != run_id:
            raise InvError(VAL_SCHEMA, "bundle does not belong to this run")
        resolved_bundle_hash = bundle.bundle_hash

    record = RunRecord(
        record_id=new_id("run_record"),
        tenant_id=tenant_id,
        run_id=run_id,
        final_state=run.state,
        termination_reason=run.termination_reason,
        evidence_id=run.evidence_id,
        bundle_id=bundle_id,
        bundle_hash=resolved_bundle_hash,
        workload_spec_sha256=workload.spec_sha256,
        component_versions=component_versions or {},
        attempt_count=run.attempt_count,
        sealed_at=now,
    )
    session.add(record)
    session.flush()

    for pin in artifacts or []:
        _pin_artifact(session, tenant_id=tenant_id, record=record, pin=pin)

    session.flush()
    return record


def _pin_artifact(
    session: Session, *, tenant_id: uuid.UUID, record: RunRecord, pin: ArtifactPin
) -> RunRecordArtifact:
    if pin.role not in ARTIFACT_ROLES:
        raise InvError(VAL_SCHEMA, f"unknown artifact role: {pin.role!r}")

    artifact = session.get(Artifact, pin.artifact_id)
    if artifact is None or artifact.tenant_id != tenant_id:
        raise InvError(RES_ARTIFACT_NOT_FOUND, "artifact not found")
    if artifact.run_id != record.run_id:
        raise InvError(VAL_SCHEMA, "artifact belongs to a different run")
    if artifact.checksum_sha256 is None or artifact.status != "active":
        raise InvError(
            VAL_SCHEMA,
            "only a verified, active artifact can be pinned into a run record",
            cause_ref=pin.artifact_id,
        )

    pinned = RunRecordArtifact(
        tenant_id=tenant_id,
        record_id=record.record_id,
        artifact_id=artifact.artifact_id,
        role=pin.role,
        uri=f"inv://artifacts/{record.run_id}/{artifact.artifact_id}",
        checksum_sha256=artifact.checksum_sha256,
        object_version=artifact.object_version,
        byte_size=artifact.byte_size,
    )
    session.add(pinned)
    return pinned


def get_record(session: Session, *, tenant_id: uuid.UUID, run_id: str) -> RunRecord:
    record = session.scalar(
        select(RunRecord).where(
            RunRecord.tenant_id == tenant_id, RunRecord.run_id == run_id
        )
    )
    if record is None:
        raise InvError(RES_RUN_NOT_FOUND, "no sealed record for this run")
    return record


def list_pinned_artifacts(
    session: Session, *, tenant_id: uuid.UUID, record_id: str, role: str | None = None
) -> list[RunRecordArtifact]:
    """The queryable form of "diff·테스트·trace Artifact 연결"."""
    query = select(RunRecordArtifact).where(
        RunRecordArtifact.tenant_id == tenant_id,
        RunRecordArtifact.record_id == record_id,
    )
    if role is not None:
        if role not in ARTIFACT_ROLES:
            raise InvError(VAL_SCHEMA, f"unknown artifact role: {role!r}")
        query = query.where(RunRecordArtifact.role == role)
    return list(session.scalars(query.order_by(RunRecordArtifact.artifact_id)).all())


def verify_pin(
    session: Session, *, tenant_id: uuid.UUID, record_id: str, artifact_id: str
) -> bool:
    """Whether the artifact still matches the digest the record pinned.

    A false here means the object changed after the run finished. That is not a
    reason to update the record — the record is the account of what was true
    then — it is a reason to raise an integrity alarm.
    """
    pinned = session.get(RunRecordArtifact, (tenant_id, record_id, artifact_id))
    if pinned is None:
        raise InvError(RES_ARTIFACT_NOT_FOUND, "artifact is not pinned to this record")
    artifact = session.get(Artifact, artifact_id)
    if artifact is None:
        return False
    return artifact.checksum_sha256 == pinned.checksum_sha256
