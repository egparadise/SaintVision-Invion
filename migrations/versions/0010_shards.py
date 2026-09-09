from importlib.resources import files
from alembic import op

revision = "0010_shards"
down_revision = "0009_node_snapshots"
branch_labels = None
depends_on = None


def upgrade():
    op.get_bind().connection.driver_connection.execute(
        files("inv").joinpath("migrations/0010_shards.sql").read_text("utf-8")
    )


def downgrade():
    raise RuntimeError("Use a reviewed forward recovery migration")
