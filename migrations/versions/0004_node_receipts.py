from importlib.resources import files
from alembic import op

revision = "0004_node_receipts"
down_revision = "0003_tool_claims"
branch_labels = None
depends_on = None


def upgrade():
    op.get_bind().exec_driver_sql(
        files("inv").joinpath("migrations/0004_node_receipts.sql").read_text("utf-8")
    )


def downgrade():
    raise RuntimeError("Node receipts are immutable; use reviewed forward recovery")
