"""Join the independently delivered service and execution migration histories.

Do not rewrite already published revision parents. Recovery is by verified
restore and forward fix; crossing the execution branch backwards is unsafe.
"""

from importlib.resources import files
from alembic import op, context

revision = "0019_workspace_api_integration"
down_revision = ("0018_workspace_resume", "0010_canonical_resource_units")
branch_labels = None
depends_on = None


def upgrade():
    script = files("inv").joinpath("migrations/0019_runtime_role.sql").read_text("utf-8")
    if context.is_offline_mode():
        context.get_context().impl.static_output(script)
    else:
        op.get_bind().connection.driver_connection.execute(script)


def downgrade():
    raise RuntimeError("Use verified restore and forward fix for the integrated execution history")
