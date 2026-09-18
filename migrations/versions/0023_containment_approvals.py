"""Enforce distinct-person L2 approval for containment; do not rewrite 0022."""

from importlib.resources import files
from alembic import op, context

revision = "0023_containment_approvals"
down_revision = "0022_node_containment"
branch_labels = None
depends_on = None


def upgrade():
    script = files("inv").joinpath("migrations/0023_containment_approvals.sql").read_text("utf-8")
    if context.is_offline_mode():
        context.get_context().impl.static_output(script)
    else:
        op.get_bind().connection.driver_connection.execute(script)


def downgrade():
    raise RuntimeError(
        "Containment approval history must survive; restore a verified backup or apply a forward fix"
    )
