"""MLflow mirror tables (S10-BE, design #168 §2, §5.1; revision 0049).

Three append-only tables. The application role may INSERT and SELECT and
nothing else, so the mirror cannot rewrite what it recorded, and a mirror
outcome can never be read as a change to the lineage tables it mirrors.

* ``mlflow_mirror_intents`` -- written in the *same transaction* as the
  canonical change, with the outbox event that will deliver it. An intent
  without an attempt is a pending mirror, not a lost one.
* ``mlflow_mirror_attempts`` -- one row per delivery outcome. Its delivery
  identity is bound to the intent it belongs to twice over: a composite
  foreign key ``(tenant_id, intent_id, outbox_event_id)`` onto the intent
  row, and ``(tenant_id, outbox_event_id)`` onto the outbox event itself. An
  attempt cannot cite an event that is not the one its intent was enqueued
  with (Codex #172 finding 3).
* ``mlflow_mirror_defects`` -- written in the canonical transaction when the
  payload could not be canonicalised (``TRACK-0005``). The canonical change
  commits; the defect is the durable record that no intent could be made.

The ``(status, error_code)`` pair on an attempt is exactly one of the design
§5 pairs; the predicate is generated from ``tracking.codes.STATUS_CODE_PAIRS``
here and stated literally in the migration, and a test holds the two equal.
There is no ``invalid`` status: ``TRACK-0004``/``0005`` never reach a sink.

``project_id`` is nullable only for ``eval_run`` subjects: an evaluation run
belongs to a suite, not a project, so there is nothing to bind. The CHECK
states that exception rather than leaving the column loosely optional.
"""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ...tracking.codes import MirrorStatus, sql_pair_check
from ..base import Base, InvId, Sha256, TenantId, Utc

MIRROR_SUBJECT_KINDS: tuple[str, ...] = (
    "experiment",
    "training_run",
    "eval_run",
    "model_version",
    "deployment",
)
MIRROR_ATTEMPT_STATUSES: tuple[str, ...] = tuple(s.value for s in MirrorStatus)
MIRROR_DEFECT_REASONS: tuple[str, ...] = (
    "nan-or-infinity",
    "key-collision",
    "unsupported-type",
    "non-string-tag",
    "list-null",
)

#: Exactly one subject reference, matching the kind; none for an experiment.
_SUBJECT_XOR = (
    "num_nonnulls(run_id, eval_run_id, model_version_id, deployment_id) = "
    "CASE WHEN subject_kind = 'experiment' THEN 0 ELSE 1 END"
)
_SUBJECT_KIND_MATCH = (
    "(subject_kind <> 'training_run' OR run_id IS NOT NULL) AND "
    "(subject_kind <> 'eval_run' OR eval_run_id IS NOT NULL) AND "
    "(subject_kind <> 'model_version' OR model_version_id IS NOT NULL) AND "
    "(subject_kind <> 'deployment' OR deployment_id IS NOT NULL)"
)
_PROJECT_BOUND = "subject_kind = 'eval_run' OR project_id IS NOT NULL"
_KIND_ALLOWED = "subject_kind IN (" + ",".join(f"'{k}'" for k in MIRROR_SUBJECT_KINDS) + ")"


def _subject_foreign_keys(table: str) -> tuple:
    return (
        ForeignKeyConstraint(
            ["tenant_id", "project_id"],
            ["projects.tenant_id", "projects.project_id"],
            name=f"fk_{table}_tenant_id_project_id",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "run_id"],
            ["runs.tenant_id", "runs.run_id"],
            name=f"fk_{table}_tenant_id_run_id",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "eval_run_id"],
            ["eval_runs.tenant_id", "eval_runs.eval_run_id"],
            name=f"fk_{table}_tenant_id_eval_run_id",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "model_version_id"],
            ["model_versions.tenant_id", "model_versions.model_version_id"],
            name=f"fk_{table}_tenant_id_model_version_id",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "deployment_id"],
            ["deployments.tenant_id", "deployments.deployment_id"],
            name=f"fk_{table}_tenant_id_deployment_id",
        ),
    )


class MlflowMirrorIntent(Base):
    __tablename__ = "mlflow_mirror_intents"
    __table_args__ = (
        PrimaryKeyConstraint("tenant_id", "intent_id", name="pk_mlflow_mirror_intents"),
        *_subject_foreign_keys("mlflow_mirror_intents"),
        ForeignKeyConstraint(
            ["tenant_id", "outbox_event_id"],
            ["outbox_events.tenant_id", "outbox_events.event_id"],
            name="fk_mlflow_mirror_intents_tenant_id_outbox_event_id",
        ),
        # The target of the attempts' delivery-identity foreign key.
        UniqueConstraint(
            "tenant_id", "intent_id", "outbox_event_id",
            name="uq_mlflow_mirror_intents_intent_event",
        ),
        CheckConstraint(_KIND_ALLOWED, name="subject_kind_allowed"),
        CheckConstraint(_SUBJECT_XOR, name="exactly_one_subject"),
        CheckConstraint(_SUBJECT_KIND_MATCH, name="subject_matches_kind"),
        CheckConstraint(_PROJECT_BOUND, name="project_bound_unless_eval_run"),
        CheckConstraint("payload_sha256 ~ '^[0-9a-f]{64}$'", name="payload_sha256_hex"),
        CheckConstraint("recovery_epoch >= 0", name="recovery_epoch_non_negative"),
        # Same subject + same canonical payload = the same intent (idempotent
        # enqueue). Declared as an expression index in the migration because
        # COALESCE is not a constraint column; kept here as a plain index so the
        # model and the migration agree on what exists.
        Index(
            "uq_mlflow_mirror_intents_subject_payload",
            "tenant_id",
            "subject_kind",
            text("COALESCE(run_id, eval_run_id, model_version_id, deployment_id, project_id)"),
            "payload_sha256",
            unique=True,
        ),
        Index("ix_mlflow_mirror_intents_tenant_id_created_at", "tenant_id", "created_at"),
    )

    tenant_id: Mapped[TenantId] = mapped_column()
    intent_id: Mapped[InvId] = mapped_column()
    project_id: Mapped[InvId | None] = mapped_column(nullable=True)
    subject_kind: Mapped[str] = mapped_column(String(16))
    run_id: Mapped[InvId | None] = mapped_column(nullable=True)
    eval_run_id: Mapped[InvId | None] = mapped_column(nullable=True)
    model_version_id: Mapped[InvId | None] = mapped_column(nullable=True)
    deployment_id: Mapped[InvId | None] = mapped_column(nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB)
    payload_sha256: Mapped[Sha256] = mapped_column()
    outbox_event_id: Mapped[InvId] = mapped_column()
    recovery_epoch: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[Utc] = mapped_column(server_default=text("now()"))


class MlflowMirrorAttempt(Base):
    __tablename__ = "mlflow_mirror_attempts"
    __table_args__ = (
        PrimaryKeyConstraint("tenant_id", "attempt_id", name="pk_mlflow_mirror_attempts"),
        # Delivery identity: this attempt belongs to this intent *and* to the
        # event that intent was enqueued with. Both edges, so neither a foreign
        # event id nor another tenant's event can be recorded.
        ForeignKeyConstraint(
            ["tenant_id", "intent_id", "outbox_event_id"],
            [
                "mlflow_mirror_intents.tenant_id",
                "mlflow_mirror_intents.intent_id",
                "mlflow_mirror_intents.outbox_event_id",
            ],
            name="fk_mlflow_mirror_attempts_intent_event",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "outbox_event_id"],
            ["outbox_events.tenant_id", "outbox_events.event_id"],
            name="fk_mlflow_mirror_attempts_tenant_id_outbox_event_id",
        ),
        UniqueConstraint(
            "tenant_id", "intent_id", "attempt_no",
            name="uq_mlflow_mirror_attempts_intent_attempt_no",
        ),
        UniqueConstraint(
            "tenant_id", "outbox_event_id", "delivery_no",
            name="uq_mlflow_mirror_attempts_delivery",
        ),
        CheckConstraint("attempt_no >= 1", name="attempt_no_positive"),
        CheckConstraint("delivery_no >= 1", name="delivery_no_positive"),
        CheckConstraint(
            "status IN (" + ",".join(f"'{s}'" for s in MIRROR_ATTEMPT_STATUSES) + ")",
            name="status_allowed",
        ),
        CheckConstraint(
            "error_code IS NULL OR error_code ~ '^TRACK-[0-9]{4}$'", name="error_code_track"
        ),
        # The exact (status, error_code) pairs of design §5, from one source.
        CheckConstraint(sql_pair_check(), name="status_code_pair"),
        CheckConstraint("tracking_uri_sha256 ~ '^[0-9a-f]{64}$'", name="tracking_uri_sha256_hex"),
        CheckConstraint(
            "status <> 'mirrored' OR reference_id IS NOT NULL", name="mirrored_has_reference"
        ),
        Index("ix_mlflow_mirror_attempts_tenant_id_intent_id", "tenant_id", "intent_id"),
    )

    tenant_id: Mapped[TenantId] = mapped_column()
    attempt_id: Mapped[InvId] = mapped_column()
    intent_id: Mapped[InvId] = mapped_column()
    attempt_no: Mapped[int] = mapped_column(Integer)
    outbox_event_id: Mapped[InvId] = mapped_column()
    delivery_no: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16))
    error_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    tracking_uri_sha256: Mapped[Sha256] = mapped_column()
    #: The sink's reference: experiment id, run id or model version number.
    reference_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    response_payload_sha256: Mapped[Sha256 | None] = mapped_column(nullable=True)
    worker_id: Mapped[str] = mapped_column(String(64))
    started_at: Mapped[Utc] = mapped_column()
    finished_at: Mapped[Utc] = mapped_column()


class MlflowMirrorDefect(Base):
    __tablename__ = "mlflow_mirror_defects"
    __table_args__ = (
        PrimaryKeyConstraint("tenant_id", "defect_id", name="pk_mlflow_mirror_defects"),
        *_subject_foreign_keys("mlflow_mirror_defects"),
        CheckConstraint(_KIND_ALLOWED, name="subject_kind_allowed"),
        CheckConstraint(_SUBJECT_XOR, name="exactly_one_subject"),
        CheckConstraint(_SUBJECT_KIND_MATCH, name="subject_matches_kind"),
        CheckConstraint(_PROJECT_BOUND, name="project_bound_unless_eval_run"),
        CheckConstraint("error_code ~ '^TRACK-[0-9]{4}$'", name="error_code_track"),
        CheckConstraint(
            "reason_class IN (" + ",".join(f"'{r}'" for r in MIRROR_DEFECT_REASONS) + ")",
            name="reason_class_allowed",
        ),
        Index("ix_mlflow_mirror_defects_tenant_id_created_at", "tenant_id", "created_at"),
    )

    tenant_id: Mapped[TenantId] = mapped_column()
    defect_id: Mapped[InvId] = mapped_column()
    project_id: Mapped[InvId | None] = mapped_column(nullable=True)
    subject_kind: Mapped[str] = mapped_column(String(16))
    run_id: Mapped[InvId | None] = mapped_column(nullable=True)
    eval_run_id: Mapped[InvId | None] = mapped_column(nullable=True)
    model_version_id: Mapped[InvId | None] = mapped_column(nullable=True)
    deployment_id: Mapped[InvId | None] = mapped_column(nullable=True)
    error_code: Mapped[str] = mapped_column(String(16))
    reason_class: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[Utc] = mapped_column(server_default=text("now()"))
