"""MLflow mirror: intents, attempts, defects (S10-BE, design PR #168 v1.3).

Revision ID: 0049_mlflow_mirror
Revises: 0048_object_store_locator
Create Date: 2026-09-28

Three append-only tables for decision B (mirror). The canonical lineage tables
are not touched: an intent (or a defect) is written in the same transaction as
the canonical change, a worker records each delivery outcome as a new attempt
row, and nothing here grants the application role UPDATE or DELETE.

Numbering (coordinator decision 2026-09-28 12:23 KST): 0047 (PR #128) ->
0048 (PR #159) -> 0049 (this) -> 0050 (card be). This branch carries the #159
head merged in, so 0048 exists here and the graph has one head;
``tools/migration_graph.py`` and ``tests/test_migrations.py`` refuse two.
This PR merges after #159.

Delivery identity (Codex #172 finding 3): an attempt row is bound to the
intent it belongs to *and* to the outbox event that intent was enqueued
with, through two composite foreign keys. ``outbox_events`` gains a unique
index on ``(tenant_id, event_id)`` to be that target; ``event_id`` was already
globally unique, so no existing row can violate it.

The ``(status, error_code)`` pair on an attempt is exactly one of the design
§5 pairs (finding 2). The predicate is written out here, pinned to this
revision's moment; ``tests/test_tracking_canonical.py`` holds it equal to the
live ``tracking.codes.sql_pair_check()`` so the two cannot drift silently.

Partitioned tables: none added by this revision.

The downgrade is a refusal: attempt rows are the record of what was sent to an
external system and cannot be restored from anywhere else.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0049_mlflow_mirror"
down_revision = "0048_object_store_locator"
branch_labels = None
depends_on = None

INV_ID = sa.CHAR(30)
SHA256 = sa.CHAR(64)
UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB
TS = sa.DateTime(timezone=True)

APP_ROLE = "inv_app"
TENANT_EXPR = "NULLIF(current_setting('inv.tenant_id', true), '')::uuid"

SUBJECT_KINDS = ("experiment", "training_run", "eval_run", "model_version", "deployment")
ATTEMPT_STATUSES = ("mirrored", "unavailable", "refused", "mismatch")
DEFECT_REASONS = ("nan-or-infinity", "key-collision", "unsupported-type", "non-string-tag", "list-null")

KIND_ALLOWED = "subject_kind IN (" + ",".join(f"'{k}'" for k in SUBJECT_KINDS) + ")"
SUBJECT_XOR = (
    "num_nonnulls(run_id, eval_run_id, model_version_id, deployment_id) = "
    "CASE WHEN subject_kind = 'experiment' THEN 0 ELSE 1 END"
)
SUBJECT_KIND_MATCH = (
    "(subject_kind <> 'training_run' OR run_id IS NOT NULL) AND "
    "(subject_kind <> 'eval_run' OR eval_run_id IS NOT NULL) AND "
    "(subject_kind <> 'model_version' OR model_version_id IS NOT NULL) AND "
    "(subject_kind <> 'deployment' OR deployment_id IS NOT NULL)"
)
PROJECT_BOUND = "subject_kind = 'eval_run' OR project_id IS NOT NULL"
#: Design §5, stated at this revision's moment (see module docstring).
#: NULL-safe: ``=`` against a NULL error_code is NULL and a CHECK passes on
#: NULL, so a failure status with no code would slip through; IS NOT DISTINCT
#: FROM is false there (hosted run 36375872884 caught exactly that row).
STATUS_CODE_PAIR = (
    "(status = 'mirrored' AND error_code IS NULL) OR "
    "(status = 'unavailable' AND error_code IS NOT DISTINCT FROM 'TRACK-0001') OR "
    "(status = 'refused' AND error_code IS NOT DISTINCT FROM 'TRACK-0002') OR "
    "(status = 'mismatch' AND error_code IS NOT DISTINCT FROM 'TRACK-0003')"
)

#: Every table in this revision is append-only for the application role.
NEW_APPEND_ONLY = ("mlflow_mirror_intents", "mlflow_mirror_attempts", "mlflow_mirror_defects")


def _now():
    return sa.text("now()")


def _subject_columns():
    return (
        sa.Column("project_id", INV_ID),
        sa.Column("subject_kind", sa.String(16), nullable=False),
        sa.Column("run_id", INV_ID),
        sa.Column("eval_run_id", INV_ID),
        sa.Column("model_version_id", INV_ID),
        sa.Column("deployment_id", INV_ID),
    )


def _subject_constraints(table: str):
    return (
        sa.ForeignKeyConstraint(
            ["tenant_id", "project_id"], ["projects.tenant_id", "projects.project_id"],
            name=f"fk_{table}_tenant_id_project_id",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "run_id"], ["runs.tenant_id", "runs.run_id"],
            name=f"fk_{table}_tenant_id_run_id",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "eval_run_id"], ["eval_runs.tenant_id", "eval_runs.eval_run_id"],
            name=f"fk_{table}_tenant_id_eval_run_id",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "model_version_id"],
            ["model_versions.tenant_id", "model_versions.model_version_id"],
            name=f"fk_{table}_tenant_id_model_version_id",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "deployment_id"],
            ["deployments.tenant_id", "deployments.deployment_id"],
            name=f"fk_{table}_tenant_id_deployment_id",
        ),
        sa.CheckConstraint(KIND_ALLOWED, name="subject_kind_allowed"),
        sa.CheckConstraint(SUBJECT_XOR, name="exactly_one_subject"),
        sa.CheckConstraint(SUBJECT_KIND_MATCH, name="subject_matches_kind"),
        sa.CheckConstraint(PROJECT_BOUND, name="project_bound_unless_eval_run"),
    )


def upgrade() -> None:
    # Target for the tenant-scoped delivery-identity foreign keys below.
    op.execute(
        "CREATE UNIQUE INDEX uq_outbox_events_tenant_id_event_id "
        "ON outbox_events (tenant_id, event_id)"
    )

    op.create_table(
        "mlflow_mirror_intents",
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("intent_id", INV_ID, nullable=False),
        *_subject_columns(),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("payload_sha256", SHA256, nullable=False),
        sa.Column("outbox_event_id", INV_ID, nullable=False),
        sa.Column("recovery_epoch", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", TS, nullable=False, server_default=_now()),
        sa.PrimaryKeyConstraint("tenant_id", "intent_id", name="pk_mlflow_mirror_intents"),
        *_subject_constraints("mlflow_mirror_intents"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "outbox_event_id"],
            ["outbox_events.tenant_id", "outbox_events.event_id"],
            name="fk_mlflow_mirror_intents_tenant_id_outbox_event_id",
        ),
        sa.UniqueConstraint(
            "tenant_id", "intent_id", "outbox_event_id",
            name="uq_mlflow_mirror_intents_intent_event",
        ),
        sa.CheckConstraint("payload_sha256 ~ '^[0-9a-f]{64}$'", name="payload_sha256_hex"),
        sa.CheckConstraint("recovery_epoch >= 0", name="recovery_epoch_non_negative"),
    )
    # Idempotent enqueue: the same subject with the same canonical payload is
    # one intent. COALESCE picks the single non-null subject reference, or the
    # project for an experiment.
    op.execute(
        "CREATE UNIQUE INDEX uq_mlflow_mirror_intents_subject_payload "
        "ON mlflow_mirror_intents (tenant_id, subject_kind, "
        "COALESCE(run_id, eval_run_id, model_version_id, deployment_id, project_id), "
        "payload_sha256)"
    )
    op.create_index(
        "ix_mlflow_mirror_intents_tenant_id_created_at",
        "mlflow_mirror_intents",
        ["tenant_id", "created_at"],
    )

    op.create_table(
        "mlflow_mirror_attempts",
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("attempt_id", INV_ID, nullable=False),
        sa.Column("intent_id", INV_ID, nullable=False),
        sa.Column("attempt_no", sa.Integer, nullable=False),
        sa.Column("outbox_event_id", INV_ID, nullable=False),
        sa.Column("delivery_no", sa.Integer, nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("error_code", sa.String(16)),
        sa.Column("tracking_uri_sha256", SHA256, nullable=False),
        sa.Column("reference_id", sa.String(128)),
        sa.Column("response_payload_sha256", SHA256),
        sa.Column("worker_id", sa.String(64), nullable=False),
        sa.Column("started_at", TS, nullable=False),
        sa.Column("finished_at", TS, nullable=False),
        sa.PrimaryKeyConstraint("tenant_id", "attempt_id", name="pk_mlflow_mirror_attempts"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "intent_id", "outbox_event_id"],
            [
                "mlflow_mirror_intents.tenant_id",
                "mlflow_mirror_intents.intent_id",
                "mlflow_mirror_intents.outbox_event_id",
            ],
            name="fk_mlflow_mirror_attempts_intent_event",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "outbox_event_id"],
            ["outbox_events.tenant_id", "outbox_events.event_id"],
            name="fk_mlflow_mirror_attempts_tenant_id_outbox_event_id",
        ),
        sa.UniqueConstraint(
            "tenant_id", "intent_id", "attempt_no",
            name="uq_mlflow_mirror_attempts_intent_attempt_no",
        ),
        sa.UniqueConstraint(
            "tenant_id", "outbox_event_id", "delivery_no",
            name="uq_mlflow_mirror_attempts_delivery",
        ),
        sa.CheckConstraint("attempt_no >= 1", name="attempt_no_positive"),
        sa.CheckConstraint("delivery_no >= 1", name="delivery_no_positive"),
        sa.CheckConstraint(
            "status IN (" + ",".join(f"'{s}'" for s in ATTEMPT_STATUSES) + ")",
            name="status_allowed",
        ),
        sa.CheckConstraint(
            "error_code IS NULL OR error_code ~ '^TRACK-[0-9]{4}$'", name="error_code_track"
        ),
        sa.CheckConstraint(STATUS_CODE_PAIR, name="status_code_pair"),
        sa.CheckConstraint(
            "tracking_uri_sha256 ~ '^[0-9a-f]{64}$'", name="tracking_uri_sha256_hex"
        ),
        sa.CheckConstraint(
            "status <> 'mirrored' OR reference_id IS NOT NULL", name="mirrored_has_reference"
        ),
    )
    op.create_index(
        "ix_mlflow_mirror_attempts_tenant_id_intent_id",
        "mlflow_mirror_attempts",
        ["tenant_id", "intent_id"],
    )

    op.create_table(
        "mlflow_mirror_defects",
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("defect_id", INV_ID, nullable=False),
        *_subject_columns(),
        sa.Column("error_code", sa.String(16), nullable=False),
        sa.Column("reason_class", sa.String(32), nullable=False),
        sa.Column("created_at", TS, nullable=False, server_default=_now()),
        sa.PrimaryKeyConstraint("tenant_id", "defect_id", name="pk_mlflow_mirror_defects"),
        *_subject_constraints("mlflow_mirror_defects"),
        sa.CheckConstraint("error_code ~ '^TRACK-[0-9]{4}$'", name="error_code_track"),
        sa.CheckConstraint(
            "reason_class IN (" + ",".join(f"'{r}'" for r in DEFECT_REASONS) + ")",
            name="reason_class_allowed",
        ),
    )
    op.create_index(
        "ix_mlflow_mirror_defects_tenant_id_created_at",
        "mlflow_mirror_defects",
        ["tenant_id", "created_at"],
    )

    for table in NEW_APPEND_ONLY:
        op.execute(f"GRANT SELECT, INSERT ON {table} TO {APP_ROLE}")
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_tenant_isolation ON {table} FOR ALL TO {APP_ROLE} "
            f"USING (tenant_id = {TENANT_EXPR}) WITH CHECK (tenant_id = {TENANT_EXPR})"
        )


def downgrade() -> None:
    raise RuntimeError(
        "0049_mlflow_mirror is irreversible: attempt rows record what was sent to an "
        "external tracking server and cannot be restored; apply a reviewed forward fix"
    )
