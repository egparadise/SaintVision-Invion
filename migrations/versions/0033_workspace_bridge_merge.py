"""Join published editor/terminal/Git history with the current account kernel."""

revision = "0033_workspace_bridge_merge"
down_revision = ("0024_workspace_bridge", "0032_workspace_readiness_merge")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    raise RuntimeError("Published Workspace history requires verified restore or forward fix")
