from importlib.resources import files
from alembic import op

revision = "0013_placement_limits"
down_revision = "0012_workspace_restore"
branch_labels = None
depends_on = None


def upgrade():
    op.get_bind().connection.driver_connection.execute(
        files("inv").joinpath("migrations/0013_placement_limits.sql").read_text("utf-8")
    )


def downgrade():
    raise RuntimeError("Use a reviewed forward recovery migration")
