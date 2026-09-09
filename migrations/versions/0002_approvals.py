"""Durable approval grants, challenges, votes, dispatches and audit."""

from importlib.resources import files
from alembic import op

revision = "0002_approvals"
down_revision = "0001_core"
branch_labels = None
depends_on = None


def upgrade():
    script = files("inv").joinpath("migrations/0002_approvals.sql").read_text("utf-8")
    op.get_bind().connection.driver_connection.execute(script)


def downgrade():
    raise RuntimeError("Approval audit retention requires a reviewed forward migration")
