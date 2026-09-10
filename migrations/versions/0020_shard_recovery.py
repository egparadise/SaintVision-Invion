"""Bounded, freshly approved shard replacement generations."""

from importlib.resources import files
from alembic import op, context

revision = "0020_shard_recovery"
down_revision = "0019_workspace_api_integration"
branch_labels = None
depends_on = None


def upgrade():
    script = files("inv").joinpath("migrations/0020_shard_recovery.sql").read_text("utf-8")
    if context.is_offline_mode():
        context.get_context().impl.static_output(script)
    else:
        op.get_bind().connection.driver_connection.execute(script)


def downgrade():
    raise RuntimeError("Use verified restore and forward fix for shard recovery history")
