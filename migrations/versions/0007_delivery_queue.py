from importlib.resources import files
from alembic import op

revision = "0007_delivery_queue"
down_revision = "0006_control_api"
branch_labels = None
depends_on = None


def upgrade():
    op.get_bind().exec_driver_sql(
        files("inv").joinpath("migrations/0007_delivery_queue.sql").read_text("utf-8")
    )


def downgrade():
    raise RuntimeError("Uncertain deliveries require reviewed forward recovery")
