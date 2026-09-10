"""Join the independently delivered service and execution migration histories.

Do not rewrite already published revision parents. Recovery is by verified
restore and forward fix; crossing the execution branch backwards is unsafe.
"""

revision = "0019_workspace_api_integration"
down_revision = ("0018_workspace_resume", "0010_canonical_resource_units")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    raise RuntimeError("Use verified restore and forward fix for the integrated execution history")
