from importlib.resources import files
from alembic import op

revision = "0009_node_snapshots"
down_revision = "0008_storage"
branch_labels = None
depends_on = None


def upgrade():
    script = files("inv").joinpath("migrations/0009_node_snapshots.sql").read_text("utf-8")
    from alembic import context
    if context.is_offline_mode():
        # A literal DDL script; preserve PostgreSQL casts and PL/pgSQL bodies.
        context.get_context().impl.static_output(script)
    else:
        op.get_bind().connection.driver_connection.execute(script)


def downgrade():
    raise RuntimeError("Use a reviewed forward recovery migration")
