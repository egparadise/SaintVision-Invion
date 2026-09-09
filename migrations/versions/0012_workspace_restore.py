from importlib.resources import files
from alembic import op

revision = "0012_workspace_restore"
down_revision = "0011_results"
branch_labels = None
depends_on = None


def upgrade():
    op.get_bind().connection.driver_connection.execute(
        files("inv").joinpath("migrations/0012_workspace_restore.sql").read_text("utf-8")
    )


def downgrade():
    raise RuntimeError("Use a reviewed forward recovery migration")
