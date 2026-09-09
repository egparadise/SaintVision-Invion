"""Durable one-shot ToolGateway admission ledger."""

from importlib.resources import files
from alembic import op

revision = "0003_tool_claims"
down_revision = "0002_approvals"
branch_labels = None
depends_on = None


def upgrade():
    op.get_bind().exec_driver_sql(
        files("inv").joinpath("migrations/0003_tool_claims.sql").read_text("utf-8")
    )


def downgrade():
    raise RuntimeError("Tool claims are immutable; use reviewed forward recovery")
