"""Core lease, run, tenant and event persistence.

Revision ID: 0001_core
Revises: none
"""

from importlib.resources import files
from alembic import op

revision = "0001_core"
down_revision = "0007_locality_replicas"
branch_labels = None
depends_on = None


def upgrade():
    # psycopg simple protocol executes this complete, trusted migration script.
    script = files("inv").joinpath("migrations/0001_core.sql").read_text("utf-8")
    bind = op.get_bind()
    conn = getattr(bind, "connection", None)
    driver_conn = getattr(conn, "driver_connection", None)
    if driver_conn is not None:
        driver_conn.execute(script)
    elif hasattr(bind, "exec_driver_sql"):
        try:
            bind.exec_driver_sql(script)
        except AttributeError:
            op.execute(script)
    else:
        op.execute(script)


def downgrade():
    # Intentional refusal: immutable Evidence must be exported before destruction.
    raise RuntimeError(
        "Destructive downgrade requires an explicit data retention migration"
    )
