"""Forward-only business/kernel seam; preserve every published canonical revision."""

from importlib.resources import files
from alembic import op, context

revision = "0021_business_kernel"
down_revision = "0020_shard_recovery"
branch_labels = None
depends_on = None


def upgrade():
    script = files("inv").joinpath("migrations/0021_business_kernel.sql").read_text("utf-8")
    if context.is_offline_mode():
        context.get_context().impl.static_output(script)
    else:
        op.get_bind().connection.driver_connection.execute(script)


def downgrade():
    raise RuntimeError(
        "Business execution identities and evidence cannot be discarded; restore a verified backup or apply a forward fix"
    )
