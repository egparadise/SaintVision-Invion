"""Durable one-shot ToolGateway admission ledger."""

from importlib.resources import files
from alembic import op

revision = "0003_tool_claims"
down_revision = "0002_approvals"
branch_labels = None
depends_on = None


def upgrade():
    script = files("inv").joinpath("migrations/0003_tool_claims.sql").read_text("utf-8")
    bind = op.get_bind()
    conn = getattr(bind, "connection", None)
    driver_conn = getattr(conn, "driver_connection", None)
    if driver_conn is not None:
        driver_conn.execute(script)
    elif hasattr(bind, "exec_driver_sql"):
        try:
            bind.exec_driver_sql(script)
        except AttributeError:
            op.execute(script)
    else:
        op.execute(script)


def downgrade():
    raise RuntimeError("Tool claims are immutable; use reviewed forward recovery")
