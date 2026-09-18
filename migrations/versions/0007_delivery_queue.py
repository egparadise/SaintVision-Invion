from importlib.resources import files
from alembic import op

revision = "0007_delivery_queue"
down_revision = "0006_control_api"
branch_labels = None
depends_on = None


def upgrade():
    script = files("inv").joinpath("migrations/0007_delivery_queue.sql").read_text("utf-8")
    from alembic import context
    if context.is_offline_mode():
        # A literal DDL script; preserve PostgreSQL casts and PL/pgSQL bodies.
        context.get_context().impl.static_output(script)
    else:
        op.get_bind().connection.driver_connection.execute(script)


def downgrade():
    raise RuntimeError("Uncertain deliveries require reviewed forward recovery")
