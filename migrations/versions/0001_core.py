"""Core lease, run, tenant and event persistence.

Revision ID: 0001_core
Revises: none
"""

from importlib.resources import files
from alembic import op

revision = "0001_core"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # psycopg simple protocol executes this complete, trusted migration script.
    script = files("inv").joinpath("migrations/0001_core.sql").read_text("utf-8")
    op.get_bind().connection.driver_connection.execute(script)


def downgrade():
    # Intentional refusal: immutable Evidence must be exported before destruction.
    raise RuntimeError(
        "Destructive downgrade requires an explicit data retention migration"
    )
