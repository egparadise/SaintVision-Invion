"""Append-only selected Workspace intent and atomic first Run bridge."""
from importlib.resources import files
from alembic import context, op

revision = "0068_first_workspace_intent"
down_revision = "0067_audit_reader_revoke"
branch_labels = None
depends_on = None


def upgrade():
    script = files("inv").joinpath("migrations/0068_first_workspace_intent.sql").read_text("utf-8")
    if context.is_offline_mode():
        context.get_context().impl.static_output(script)
    else:
        op.get_bind().connection.driver_connection.execute(script)


def downgrade():
    raise RuntimeError("First Workspace intent and Run identities are append-only; apply a forward fix")
