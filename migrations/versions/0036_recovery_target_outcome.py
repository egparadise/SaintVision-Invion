"""New recovery claims cannot meet objectives after a failed/aborted drill.

Do not rewrite historic evidence: NOT VALID preserves legacy rows for explicit
review, while PostgreSQL enforces the constraint on all new/updated rows.
"""

from alembic import op

revision = "0036_recovery_target_outcome"
down_revision = "0035_credential_registry"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""ALTER TABLE public.recovery_drills
        ADD CONSTRAINT ck_recovery_drills_met_targets_requires_passed
        CHECK (NOT met_targets OR outcome = 'passed') NOT VALID""")


def downgrade():
    raise RuntimeError("Recovery claim history requires a reviewed forward fix")
