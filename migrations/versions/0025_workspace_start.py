"""First Workspace execution; independent of historical recovery checkouts."""

from importlib.resources import files
from alembic import op, context

revision = "0025_workspace_start"
down_revision = "0023_containment_approvals"
branch_labels = None
depends_on = None


def upgrade():
    script = files("inv").joinpath("migrations/0025_workspace_start.sql").read_text("utf-8")
    if context.is_offline_mode():
        context.get_context().impl.static_output(script)
    else:
        op.get_bind().connection.driver_connection.execute(script)


def downgrade():
    raise RuntimeError("First execution input and evidence must survive; use a forward fix")
