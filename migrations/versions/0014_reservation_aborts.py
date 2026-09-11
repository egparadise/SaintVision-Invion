from importlib.resources import files
from alembic import op

revision = "0014_reservation_aborts"
down_revision = "0013_placement_limits"
branch_labels = None
depends_on = None


def upgrade():
    script = files("inv").joinpath("migrations/0014_reservation_aborts.sql").read_text("utf-8")
    from alembic import context

    if context.is_offline_mode():
        # A literal DDL script; preserve PostgreSQL casts and PL/pgSQL bodies.
        from sqlalchemy import DDL

        op.execute(DDL(script))
    else:
        op.get_bind().connection.driver_connection.execute(script)


def downgrade():
    raise RuntimeError("Use a reviewed forward recovery migration")
