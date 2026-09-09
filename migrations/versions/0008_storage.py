"""Bounded object publication and checkpoint pins."""

from importlib.resources import files
from alembic import op

revision = "0008_storage"
down_revision = "0007_delivery_queue"
branch_labels = None
depends_on = None


def upgrade():
    op.get_bind().exec_driver_sql(
        files("inv").joinpath("migrations/0008_storage.sql").read_text("utf-8")
    )


def downgrade():
    raise RuntimeError("Restore a verified backup or apply a forward migration")
