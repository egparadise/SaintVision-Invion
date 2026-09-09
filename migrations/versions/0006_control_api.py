from importlib.resources import files
from alembic import op

revision = "0006_control_api"
down_revision = "0005_node_channels"
branch_labels = None
depends_on = None


def upgrade():
    op.get_bind().exec_driver_sql(
        files("inv").joinpath("migrations/0006_control_api.sql").read_text("utf-8")
    )


def downgrade():
    raise RuntimeError("Event ordering requires reviewed forward recovery")
