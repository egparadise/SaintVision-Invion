"""Preserve retention pins while a departed node's replicas are stale."""
from alembic import op

revision = "0043_replica_retention"
down_revision = "0042_model_retry_lineage"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE public.data_replicas
          DROP CONSTRAINT ck_data_replicas_only_ready_replicas_pin,
          ADD CONSTRAINT ck_data_replicas_retained_replicas_pin
            CHECK (pinned_until IS NULL OR state IN ('ready', 'stale'));
    """)


def downgrade():
    raise RuntimeError("Pinned stale replicas require a reviewed forward fix")
