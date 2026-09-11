"""Merge published business and first execution histories without rewriting either."""
revision = "0026_business_start_merge"
down_revision = ("0025_workspace_start", "0025_workspace_tool_choice")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    raise RuntimeError("Forward only: restore a verified backup and apply a forward fix")
