"""Durable containment controls and operator authority, preserving canonical history."""

from importlib.resources import files
from alembic import op, context

revision = "0022_node_containment"
down_revision = "0021_business_kernel"
branch_labels = None
depends_on = None


def upgrade():
    script = files("inv").joinpath("migrations/0022_node_containment.sql").read_text("utf-8")
    if context.is_offline_mode():
        context.get_context().impl.static_output(script)
    else:
        op.get_bind().connection.driver_connection.execute(script)


def downgrade():
    raise RuntimeError(
        "Containment latches and audit must survive; restore a verified backup or apply a forward fix"
    )
