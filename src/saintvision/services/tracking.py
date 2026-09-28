"""MLflow mirror: enqueue in the canonical transaction, deliver through a sink.

Design PR #168 v1.3, decision B. Two entry points:

* :func:`enqueue_mirror` is called by the lineage and evaluation services
  *inside* the transaction that records the canonical change. With the sink
  configured it writes an outbox event and an ``mlflow_mirror_intents`` row;
  when the payload cannot be canonicalised it writes an ``mlflow_mirror_defects``
  row instead (``TRACK-0005``). In every case the canonical change commits:
  no mirror reason rolls back lineage. Only a failure to write the defect row
  itself -- a database failure -- fails the transaction.

* :func:`deliver_intent` is what the outbox consumer calls with a sink. It
  locks the intent row, returns an existing terminal attempt without touching
  the sink (duplicate delivery and competing consumers produce one row and
  zero extra runs), otherwise assigns ``attempt_no`` under that lock, asks the
  sink to ``find`` before it ``mirror``s, attests, and appends exactly one
  attempt row.

The real MLflow HTTP sink and the operator service credential are stage 2;
this module only ever sees a :class:`TrackingSink`.
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass
from typing import Any, Final, Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..adapters.contract import AttestationResult
from ..adapters.tracking import MirrorRecord, TrackingSink
from ..db.models.tracking import (
    MIRROR_SUBJECT_KINDS,
    MlflowMirrorAttempt,
    MlflowMirrorDefect,
    MlflowMirrorIntent,
)
from ..ids import new_id
from ..tracking.canonical import CanonicalizationError, canonical_payload, payload_sha256
from ..tracking.codes import (
    TRACK_MISMATCH,
    TRACK_PAYLOAD_INVALID,
    TRACK_UNAVAILABLE,
    MirrorStatus,
)
from ..tracking.config import TrackingConfiguration, TrackingSettings, resolve
from .evidence import enqueue_event

MIRROR_EVENT_TYPE: Final[str] = "inv.mlflow.mirror.requested"
MIRROR_AGGREGATE_TYPE: Final[str] = "mirror_intent"

#: Which intent column a subject kind fills. ``experiment`` fills none.
SUBJECT_COLUMN: Final[dict[str, str | None]] = {
    "experiment": None,
    "training_run": "run_id",
    "eval_run": "eval_run_id",
    "model_version": "model_version_id",
    "deployment": "deployment_id",
}


@dataclass(frozen=True, slots=True)
class EnqueueOutcome:
    """What :func:`enqueue_mirror` did. ``skipped`` carries the readiness value."""

    kind: Literal["intent", "existing", "defect", "skipped"]
    intent_id: str | None = None
    defect_id: str | None = None
    reason: str | None = None


def _subject_values(subject_kind: str, subject_id: str | None) -> dict[str, str]:
    if subject_kind not in MIRROR_SUBJECT_KINDS:
        raise ValueError(f"unknown subject kind {subject_kind!r}")
    column = SUBJECT_COLUMN[subject_kind]
    if column is None:
        if subject_id is not None:
            raise ValueError("an experiment intent has no subject id")
        return {}
    if not subject_id:
        raise ValueError(f"{subject_kind} needs a subject id")
    return {column: subject_id}


def enqueue_mirror(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    subject_kind: str,
    subject_id: str | None,
    project_id: str | None,
    payload: dict[str, Any],
    now: dt.datetime,
    trace_id: str | None = None,
    configuration: TrackingConfiguration | None = None,
) -> EnqueueOutcome:
    """Record the intent (or the defect) in the caller's transaction."""
    subject = _subject_values(subject_kind, subject_id)
    if subject_kind != "eval_run" and not project_id:
        raise ValueError(f"{subject_kind} must be bound to a project")

    configuration = resolve() if configuration is None else configuration
    if not configuration.readiness.configured:
        return EnqueueOutcome("skipped", reason=configuration.readiness.value)

    try:
        canonical = canonical_payload(payload)
    except CanonicalizationError as exc:
        defect = MlflowMirrorDefect(
            tenant_id=tenant_id,
            defect_id=new_id("mirror_defect"),
            project_id=project_id,
            subject_kind=subject_kind,
            error_code=TRACK_PAYLOAD_INVALID,
            reason_class=exc.reason_class,
            created_at=now,
            **subject,
        )
        session.add(defect)
        session.flush()
        return EnqueueOutcome("defect", defect_id=defect.defect_id, reason=exc.reason_class)

    digest = payload_sha256(canonical)
    existing = session.scalar(
        select(MlflowMirrorIntent).where(
            MlflowMirrorIntent.tenant_id == tenant_id,
            MlflowMirrorIntent.subject_kind == subject_kind,
            MlflowMirrorIntent.payload_sha256 == digest,
            *[getattr(MlflowMirrorIntent, column) == value for column, value in subject.items()],
            *([MlflowMirrorIntent.project_id == project_id] if not subject else []),
        )
    )
    if existing is not None:
        return EnqueueOutcome("existing", intent_id=existing.intent_id)

    intent_id = new_id("mirror_intent")
    event_id = enqueue_event(
        session,
        tenant_id=tenant_id,
        event_type=MIRROR_EVENT_TYPE,
        aggregate_type=MIRROR_AGGREGATE_TYPE,
        aggregate_id=intent_id,
        payload={"intentId": intent_id, "subjectKind": subject_kind, "payloadSha256": digest},
        now=now,
        trace_id=trace_id,
    )
    intent = MlflowMirrorIntent(
        tenant_id=tenant_id,
        intent_id=intent_id,
        project_id=project_id,
        subject_kind=subject_kind,
        payload=canonical,
        payload_sha256=digest,
        outbox_event_id=event_id,
        recovery_epoch=0,
        created_at=now,
        **subject,
    )
    session.add(intent)
    session.flush()
    return EnqueueOutcome("intent", intent_id=intent_id)


# --------------------------------------------------------------------------
# Payloads (design #168 §1): references and digests only, never bytes
# --------------------------------------------------------------------------


def _timestamp_ms(now: dt.datetime) -> int:
    return int(now.timestamp() * 1000)


def model_version_mirror_payload(version: Any, *, model_name: str, now: dt.datetime) -> dict[str, Any]:
    return {
        "params": {
            "model_id": version.model_id,
            "model_name": model_name,
            "version": version.version,
            "content_sha256": version.content_sha256,
            "uri": version.uri,
            "byte_size": int(version.byte_size or 0),
            "produced_by_run_id": version.produced_by_run_id,
        },
        "tags": {
            "inv.model_version_id": version.model_version_id,
            "inv.content_sha256": version.content_sha256,
            "inv.stage": version.stage,
            "inv.model_id": version.model_id,
        },
        "recorded_at_ms": _timestamp_ms(now),
    }


def deployment_mirror_payload(deployment: Any, *, now: dt.datetime) -> dict[str, Any]:
    return {
        "params": {
            "environment": deployment.environment,
            "status": deployment.status,
            "image_id": deployment.image_id,
        },
        "tags": {
            "inv.deployment_id": deployment.deployment_id,
            "inv.deployed_digest": deployment.deployed_digest,
            "inv.approval_id": deployment.approval_id or "",
            "inv.model_version_id": deployment.model_version_id,
        },
        "recorded_at_ms": _timestamp_ms(now),
    }


def eval_run_mirror_payload(run: Any, *, now: dt.datetime) -> dict[str, Any]:
    stamp = _timestamp_ms(now)
    return {
        "params": {"suite_id": run.suite_id, "status": run.status},
        "tags": {"inv.eval_run_id": run.eval_run_id, "inv.suite_id": run.suite_id},
        "metrics": [
            {"key": "passed_cases", "value": int(run.passed_cases), "step": 0, "timestamp_ms": stamp},
            {"key": "total_cases", "value": int(run.total_cases), "step": 0, "timestamp_ms": stamp},
            {"key": "violations", "value": int(run.violations), "step": 0, "timestamp_ms": stamp},
            {"key": "gate_passed", "value": 1 if run.passed_gate else 0, "step": 0, "timestamp_ms": stamp},
        ],
    }


# --------------------------------------------------------------------------
# Delivery
# --------------------------------------------------------------------------


def experiment_name(settings: TrackingSettings, tenant_id: uuid.UUID, project_id: str | None) -> str:
    return f"{settings.experiment_prefix}/{str(tenant_id)[:8]}/{project_id or 'no-project'}"


def _terminal_attempt(session: Session, tenant_id: uuid.UUID, intent_id: str) -> MlflowMirrorAttempt | None:
    return session.scalar(
        select(MlflowMirrorAttempt)
        .where(
            MlflowMirrorAttempt.tenant_id == tenant_id,
            MlflowMirrorAttempt.intent_id == intent_id,
            MlflowMirrorAttempt.status != MirrorStatus.UNAVAILABLE.value,
        )
        .order_by(MlflowMirrorAttempt.attempt_no)
        .limit(1)
    )


def deliver_intent(
    session: Session,
    sink: TrackingSink,
    *,
    tenant_id: uuid.UUID,
    intent_id: str,
    outbox_event_id: str,
    delivery_no: int,
    settings: TrackingSettings,
    worker_id: str,
    now: dt.datetime,
) -> MlflowMirrorAttempt:
    """Deliver one intent through ``sink`` and append exactly one attempt row.

    Runs inside the consumer's transaction. The intent row is locked first, so
    a competing consumer waits and then sees the terminal attempt this one
    wrote. A terminal attempt is returned as-is: no ``find``, no ``mirror``.
    """
    if delivery_no < 1:
        raise ValueError("delivery_no starts at 1")
    intent = session.scalar(
        select(MlflowMirrorIntent)
        .where(
            MlflowMirrorIntent.tenant_id == tenant_id,
            MlflowMirrorIntent.intent_id == intent_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if intent is None:
        raise LookupError(f"intent {intent_id} not found for tenant")

    terminal = _terminal_attempt(session, tenant_id, intent_id)
    if terminal is not None:
        return terminal

    attempt_no = (
        session.scalar(
            select(func.coalesce(func.max(MlflowMirrorAttempt.attempt_no), 0)).where(
                MlflowMirrorAttempt.tenant_id == tenant_id,
                MlflowMirrorAttempt.intent_id == intent_id,
            )
        )
        or 0
    ) + 1

    started = now
    status, error_code, reference_id, response_digest = _push(sink, intent, settings)
    attempt = MlflowMirrorAttempt(
        tenant_id=tenant_id,
        attempt_id=new_id("mirror_attempt"),
        intent_id=intent_id,
        attempt_no=attempt_no,
        outbox_event_id=outbox_event_id,
        delivery_no=delivery_no,
        status=status.value,
        error_code=error_code,
        tracking_uri_sha256=settings.tracking_uri_sha256,
        reference_id=reference_id,
        response_payload_sha256=response_digest,
        worker_id=worker_id,
        started_at=started,
        finished_at=now,
    )
    session.add(attempt)
    session.flush()
    return attempt


def _push(
    sink: TrackingSink, intent: MlflowMirrorIntent, settings: TrackingSettings
) -> tuple[MirrorStatus, str | None, str | None, str | None]:
    """find -> (mirror) -> attest. Returns (status, error_code, reference, digest)."""
    reference_id = sink.find(intent.intent_id)
    if reference_id is None:
        record = MirrorRecord(
            intent_id=intent.intent_id,
            subject_kind=intent.subject_kind,
            experiment=experiment_name(settings, intent.tenant_id, intent.project_id),
            payload=dict(intent.payload),
            payload_sha256=intent.payload_sha256,
        )
        result = sink.mirror(record)
        if result.status is not MirrorStatus.MIRRORED:
            return result.status, result.error_code, None, None
        reference_id = result.reference_id

    attestation = sink.attest(reference_id)
    if attestation.result is AttestationResult.UNVERIFIABLE:
        # Cannot tell what the server holds: not a mismatch, not a success.
        return MirrorStatus.UNAVAILABLE, TRACK_UNAVAILABLE, reference_id, None
    digest = attestation.response_sha256
    if attestation.result is AttestationResult.MISMATCH or digest != intent.payload_sha256:
        return MirrorStatus.MISMATCH, TRACK_MISMATCH, reference_id, digest
    return MirrorStatus.MIRRORED, None, reference_id, digest
