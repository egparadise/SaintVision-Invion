"""Workspace editor, terminal attachments and Git intent history; forward only."""

from importlib.resources import files
from alembic import op, context

revision = "0024_workspace_bridge"
down_revision = "0023_containment_approvals"
branch_labels = None
depends_on = None


def upgrade():
    script = files("inv").joinpath("migrations/0024_workspace_bridge.sql").read_text("utf-8")
    if context.is_offline_mode():
        context.get_context().impl.static_output(script)
    else:
        op.get_bind().connection.driver_connection.execute(script)


def downgrade():
    raise RuntimeError(
        "Editor, terminal and Git history must survive; use verified restore or forward fix"
    )
