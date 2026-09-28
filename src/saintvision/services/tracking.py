"""MLflow mirror: enqueue in the canonical transaction, deliver through a sink.

Design PR #168 v1.3, decision B. Two entry points:

* :func:`enqueue_mirror` is called by the lineage, evaluation and run services
  *inside* the transaction that records the canonical change. With the sink
  configured it writes an outbox event and an ``mlflow_mirror_intents`` row;
  when the payload cannot be canonicalised it writes an ``mlflow_mirror_defects``
  row instead (``TRACK-0005``). In every case the canonical change commits:
  no mirror reason rolls back lineage. Only a failure to write the defect row
  itself -- a database failure -- fails the transaction. The first intent for
  a project also enqueues that project's ``experiment`` intent (design §1).

* :func:`deliver_intent` is what the outbox consumer calls with a sink. It
  serialises on the intent (a transaction-scoped advisory lock keyed by the
  intent, see below), refuses a delivery whose event is not the one the intent
  was enqueued with, returns an existing terminal attempt without touching the
  sink (duplicate delivery and competing consumers produce one row and zero
  extra runs), otherwise assigns ``attempt_no`` under that lock, asks the sink
  to ``find`` before it ``mirror``s, attests, and appends exactly one attempt
  row.

**Why an advisory lock and not ``SELECT ... FOR UPDATE``.** The design wrote
``FOR UPDATE`` on the intent row. PostgreSQL grants a row lock only to a role
holding UPDATE privilege on the table, and the intents table is append-only
for the application role by design (INSERT and SELECT). Granting UPDATE, even
on one column, to obtain the lock would contradict the invariant the table
exists for. ``pg_advisory_xact_lock`` keyed by ``(tenant_id, intent_id)`` gives
the same serialisation -- a competing consumer waits, then sees the terminal
attempt the first one wrote -- with SELECT privilege only, and the UNIQUE on
``(tenant_id, intent_id, attempt_no)`` remains the second line of defence.

The real MLflow HTTP sink and the operator service credential are stage 2;
this module only ever sees a :class:`TrackingSink`.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import uuid
from dataclasses import dataclass
from typing import Any, Final, Literal

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from ..adapters.contract import AttestationResult
from ..adapters.tracking import MirrorFailure, MirrorRecord, TrackingSink
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
    check_pair,
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


class DeliveryIdentityError(ValueError):
    """The delivery names an event that is not the intent's own (fail-closed)."""


@dataclass(frozen=True, slots=True)
class EnqueueOutcome:
    """What :func:`enqueue_mirror` did. ``skipped`` carries the readiness value."""

    kind: Literal["intent", "existing", "defect", "skipped"]
    intent_id: str | None = None
    defect_id: str | None = None
    reason: str | None = None
    #: The experiment intent enqueued alongside, when this was the project's first.
    experiment_intent_id: str | None = None


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


def _existing_intent(
    session: Session, tenant_id: uuid.UUID, subject_kind: str, subject: dict[str, str],
    project_id: str | None, digest: str | None,
) -> MlflowMirrorIntent | None:
    conditions = [
        MlflowMirrorIntent.tenant_id == tenant_id,
        MlflowMirrorIntent.subject_kind == subject_kind,
        *[getattr(MlflowMirrorIntent, column) == value for column, value in subject.items()],
    ]
    if not subject:
        conditions.append(MlflowMirrorIntent.project_id == project_id)
    if digest is not None:
        conditions.append(MlflowMirrorIntent.payload_sha256 == digest)
    return session.scalar(select(MlflowMirrorIntent).where(*conditions).limit(1))


def _advisory_key(*parts: object) -> int:
    digest = hashlib.sha256(":".join(str(p) for p in parts).encode("utf-8")).digest()[:8]
    return int.from_bytes(digest, "big", signed=True)


def _serialize_enqueue(session: Session, tenant_id: uuid.UUID, scope: str) -> None:
    """Transaction-scoped advisory lock: one enqueue scope at a time per tenant."""
    session.execute(
        text("SELECT pg_advisory_xact_lock(:key)"), {"key": _advisory_key("enqueue", tenant_id, scope)}
    )


def _insert_intent(
    session: Session, *, tenant_id: uuid.UUID, subject_kind: str, subject: dict[str, str],
    project_id: str | None, canonical: dict[str, Any], digest: str, now: dt.datetime,
    trace_id: str | None,
) -> str:
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
    session.add(
        MlflowMirrorIntent(
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
    )
    session.flush()
    return intent_id


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

    # Serialise enqueue per project (per subject for an eval run) for the rest
    # of this transaction. Two canonical mutations of one project that race to
    # make its *first* intent would otherwise both observe "no experiment yet"
    # and both insert one; the unique index would then roll one canonical
    # mutation back for a mirror reason, which decision B forbids (Codex #172
    # r2). Under the lock the second waits for the first to commit and sees
    # its experiment intent. Same lock covers the subject intent's own
    # existence check, so an identical concurrent intent is "existing", not an
    # IntegrityError.
    _serialize_enqueue(session, tenant_id, project_id if project_id is not None else f"eval_run:{subject_id}")

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
    existing = _existing_intent(session, tenant_id, subject_kind, subject, project_id, digest)
    if existing is not None:
        return EnqueueOutcome("existing", intent_id=existing.intent_id)

    # Design §1: a project is an experiment. The first intent under a project
    # enqueues the experiment itself, in the same transaction, so the worker
    # never has to invent one.
    experiment_intent_id = None
    if subject_kind != "experiment" and project_id is not None:
        if _existing_intent(session, tenant_id, "experiment", {}, project_id, None) is None:
            experiment_payload = canonical_payload(experiment_mirror_payload(project_id, tenant_id))
            experiment_intent_id = _insert_intent(
                session, tenant_id=tenant_id, subject_kind="experiment", subject={},
                project_id=project_id, canonical=experiment_payload,
                digest=payload_sha256(experiment_payload), now=now, trace_id=trace_id,
            )

    intent_id = _insert_intent(
        session, tenant_id=tenant_id, subject_kind=subject_kind, subject=subject,
        project_id=project_id, canonical=canonical, digest=digest, now=now, trace_id=trace_id,
    )
    return EnqueueOutcome("intent", intent_id=intent_id, experiment_intent_id=experiment_intent_id)


# --------------------------------------------------------------------------
# Payloads (design #168 §1): references and digests only, never bytes
# --------------------------------------------------------------------------


def _timestamp_ms(now: dt.datetime) -> int:
    return int(now.timestamp() * 1000)


def experiment_mirror_payload(project_id: str, tenant_id: uuid.UUID) -> dict[str, Any]:
    return {
        "tags": {"inv.tenant_id": str(tenant_id), "inv.project_id": project_id},
    }


def training_run_mirror_payload(
    run: Any, workload: Any, *, evidence_id: str | None, now: dt.datetime
) -> dict[str, Any]:
    return {
        "params": {
            "workload_id": workload.workload_id,
            "objective": workload.objective,
            "contract_version": workload.contract_version,
            "workload_spec_sha256": workload.spec_sha256,
            "termination_reason": run.termination_reason,
        },
        "tags": {
            "inv.run_id": run.run_id,
            "inv.workload_spec_sha256": workload.spec_sha256,
            "inv.evidence_id": evidence_id or "",
            "inv.state": run.state,
        },
        "recorded_at_ms": _timestamp_ms(now),
    }


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


def release_mirror_payload(version: Any, *, now: dt.datetime) -> dict[str, Any]:
    """The stage transition: our stage as a tag, never MLflow's stage API (§1)."""
    return {
        "params": {
            "content_sha256": version.content_sha256,
            "verified_at_ms": _timestamp_ms(version.verified_at) if version.verified_at else None,
            "retention_pinned_until_ms": (
                _timestamp_ms(version.retention_pinned_until) if version.retention_pinned_until else None
            ),
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


def eval_run_mirror_payload(
    run: Any, *, suite: Any, report: dict[str, Any], now: dt.datetime
) -> dict[str, Any]:
    """Suite identity, the gate, and one metric per category (design §1)."""
    stamp = _timestamp_ms(now)
    metrics = [
        {"key": "passed_cases", "value": int(run.passed_cases), "step": 0, "timestamp_ms": stamp},
        {"key": "total_cases", "value": int(run.total_cases), "step": 0, "timestamp_ms": stamp},
        {"key": "violations", "value": int(run.violations), "step": 0, "timestamp_ms": stamp},
        {"key": "gate_passed", "value": 1 if run.passed_gate else 0, "step": 0, "timestamp_ms": stamp},
    ]
    for name, bucket in sorted(report.get("categories", {}).items()):
        metrics.append({"key": f"category.{name}.pass_rate", "value": float(bucket["passRate"]),
                        "step": 0, "timestamp_ms": stamp})
        if bucket.get("meanScore") is not None:
            metrics.append({"key": f"category.{name}.mean_score", "value": float(bucket["meanScore"]),
                            "step": 0, "timestamp_ms": stamp})
    return {
        "params": {
            "suite_id": run.suite_id,
            "suite_name": suite.name,
            "suite_version": suite.version,
            "suite_definition_sha256": suite.definition_sha256,
            "status": run.status,
        },
        "tags": {"inv.eval_run_id": run.eval_run_id, "inv.suite_id": run.suite_id},
        "metrics": metrics,
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


def _lock_intent(session: Session, tenant_id: uuid.UUID, intent_id: str) -> None:
    """Transaction-scoped advisory lock keyed by the intent (see module docstring)."""
    key = hashlib.sha256(f"{tenant_id}:{intent_id}".encode("utf-8")).digest()[:8]
    session.execute(
        text("SELECT pg_advisory_xact_lock(:key)"),
        {"key": int.from_bytes(key, "big", signed=True)},
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

    Runs inside the consumer's transaction. Order: lock, load, verify the
    delivery identity, return a terminal attempt if any, otherwise push. The
    identity check precedes every sink call so a wrong event id costs nothing
    external and leaves no row.
    """
    if delivery_no < 1:
        raise ValueError("delivery_no starts at 1")
    _lock_intent(session, tenant_id, intent_id)
    intent = session.scalar(
        select(MlflowMirrorIntent)
        .where(
            MlflowMirrorIntent.tenant_id == tenant_id,
            MlflowMirrorIntent.intent_id == intent_id,
        )
        .execution_options(populate_existing=True)
    )
    if intent is None:
        raise LookupError(f"intent {intent_id} not found for tenant")
    if outbox_event_id != intent.outbox_event_id:
        raise DeliveryIdentityError(
            "delivery names an outbox event that is not the intent's own; refusing before any sink call"
        )

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
    check_pair(status, error_code)
    attempt = MlflowMirrorAttempt(
        tenant_id=tenant_id,
        attempt_id=new_id("mirror_attempt"),
        intent_id=intent_id,
        attempt_no=attempt_no,
        outbox_event_id=intent.outbox_event_id,
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


# --------------------------------------------------------------------------
# Worker path (stage 2): configuration -> credential -> sink -> deliver_intent
# --------------------------------------------------------------------------


class RefusingSink:
    """A sink whose credential was refused: every mirror is ``TRACK-0002``.

    Used so a credential refusal is recorded through the same ``deliver_intent``
    path as any other outcome (one attempt row, terminal, no retry), without a
    single network call.
    """

    name = "refused-credential"
    contract_version = "1.0.0"

    def probe(self):  # pragma: no cover - never reached
        raise AssertionError("a refusing sink is not probed")

    def authenticate(self, secret_handle):  # pragma: no cover - never reached
        raise AssertionError("a refusing sink is not authenticated")

    def find(self, intent_id: str) -> str | None:
        return None

    def mirror(self, record: MirrorRecord):
        from ..adapters.tracking import MirrorResult
        from ..tracking.codes import TRACK_REFUSED

        return MirrorResult(MirrorStatus.REFUSED, error_code=TRACK_REFUSED, detail="service credential refused")

    def redact(self, content: str) -> tuple[str, bool]:
        return content, False

    def attest(self, reference_id: str):  # pragma: no cover - never reached (no mirror succeeds)
        raise AssertionError("a refusing sink never attests")


@dataclass(frozen=True, slots=True)
class WorkerIdentity:
    """Who the worker is and where its secret files live."""

    worker_principal: str
    recovery_epoch: int
    credentials_root: str


def resolve_sink(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    settings: TrackingSettings,
    identity: WorkerIdentity,
    now: dt.datetime,
    sink_factory=None,
) -> TrackingSink:
    """The sink for one delivery, authenticated from the service credential.

    ``sink_factory(settings)`` builds the unauthenticated sink (the real
    ``MlflowSink`` by default; tests inject the reference sink). A refused or
    missing credential yields :class:`RefusingSink`, so the outcome is recorded
    as ``TRACK-0002`` without contacting the server. The 0035 run-bound
    registry is never consulted here.
    """
    from ..credentials.contract import CredentialDenied
    from ..tracking.service_credentials import (
        PURPOSE_MLFLOW_MIRROR,
        LookupRequest,
        ServiceCredentialRegistry,
        ServiceRegistryAdapter,
        worker_context,
    )

    request = LookupRequest(
        tenant_id=tenant_id,
        purpose=PURPOSE_MLFLOW_MIRROR,
        destination=settings.destination,
        destination_uri_sha256=settings.tracking_uri_sha256,
        worker_principal=identity.worker_principal,
        recovery_epoch=identity.recovery_epoch,
        now=now,
    )
    registry = ServiceCredentialRegistry(session)
    match = registry.lookup(request)
    if match is None:
        return RefusingSink()

    if sink_factory is None:
        from ..adapters.mlflow_sink import MlflowSink

        def sink_factory(s: TrackingSettings):  # noqa: E306
            return MlflowSink(s.tracking_uri, experiment_prefix=s.experiment_prefix, timeout_seconds=s.timeout_seconds)

    sink = sink_factory(settings)
    try:
        from ..credentials.linux_file import LinuxFileCredentials

        reader = LinuxFileCredentials(identity.credentials_root, ServiceRegistryAdapter(registry, request))
        handle = reader.resolve(match.reference, worker_context(request), request.purpose, request.destination)
    except CredentialDenied:
        return RefusingSink()
    auth = sink.authenticate(handle)
    if not auth.authenticated:
        return RefusingSink()
    return sink


def deliver_outbox_event(
    session: Session,
    *,
    event: Any,
    tenant_id: uuid.UUID,
    identity: WorkerIdentity,
    worker_id: str,
    now: dt.datetime,
    configuration: TrackingConfiguration | None = None,
    sink_factory=None,
) -> MlflowMirrorAttempt | None:
    """Consume one ``inv.mlflow.mirror.requested`` outbox event.

    Returns the attempt row, or ``None`` when the configuration is ``absent``
    or ``invalid`` -- then nothing is sent, nothing is recorded, and the event
    stays pending (NOT_OBSERVED / INVALID_RUN by readiness, design §6). A
    :class:`MlflowRequestInvalid` from the sink propagates: it is our defect
    (``TRACK-0004``), leaves no attempt row, and the outbox policy retries or
    parks the event.
    """
    if event.event_type != MIRROR_EVENT_TYPE:
        raise ValueError(f"not a mirror event: {event.event_type!r}")
    configuration = resolve() if configuration is None else configuration
    if not configuration.readiness.configured:
        return None
    settings = configuration.settings
    intent_id = event.payload.get("intentId") if isinstance(event.payload, dict) else None
    if not intent_id or intent_id != event.aggregate_id:
        raise DeliveryIdentityError("outbox event payload does not name its own intent")

    sink = resolve_sink(
        session, tenant_id=tenant_id, settings=settings, identity=identity, now=now, sink_factory=sink_factory
    )
    return deliver_intent(
        session,
        sink,
        tenant_id=tenant_id,
        intent_id=intent_id,
        outbox_event_id=event.event_id,
        delivery_no=int(event.publish_attempts) + 1,
        settings=settings,
        worker_id=worker_id,
        now=now,
    )


def _push(
    sink: TrackingSink, intent: MlflowMirrorIntent, settings: TrackingSettings
) -> tuple[MirrorStatus, str | None, str | None, str | None]:
    """find -> (mirror) -> attest. Returns (status, error_code, reference, digest)."""
    try:
        reference_id = sink.find(intent.intent_id)
    except MirrorFailure as failure:
        return failure.result.status, failure.result.error_code, None, None
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
