from importlib.resources import files
from alembic import op, context

revision = "0016_shard_parents"
down_revision = "0015_output_ingestions"
branch_labels = None
depends_on = None


def upgrade():
    script = files("inv").joinpath("migrations/0016_shard_parents.sql").read_text("utf-8")
    if context.is_offline_mode():
        context.get_context().impl.static_output(script)
    else:
        op.get_bind().connection.driver_connection.execute(script)


def downgrade():
    raise RuntimeError("Use a reviewed forward recovery migration")
