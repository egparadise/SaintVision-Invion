"""Record which development tool a workspace is set up to use.

Revision ID: 0025_workspace_tool_choice
Revises: 0024_project_kernel_link
Create Date: 2026-09-11

Four agent CLIs are installed on a node and a person picks one per workspace.
Without somewhere to put that choice it has to travel on every execution
request, which means the screen decides the tool at the moment of running and
two people working in one workspace can be running different tools without
either knowing.

Two things the column is deliberately **not**:

It is not a foreign key to a tools table. The set of tools is code
(``saintvision.adapters.agents.TOOLS``), not data — adding one is a change to
the adapter definitions, and a table would let a row name a tool no adapter
exists for. The check constraint names them, so an unknown value is refused at
the point of writing rather than discovered at the point of running.

It is not a guarantee the tool is usable. Whether it is installed and signed in
is a property of the node at the moment of execution, and a workspace
configured last week cannot promise anything about a machine today. The choice
is recorded here; readiness is asked of the node.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0025_workspace_tool_choice"
down_revision = "0024_project_kernel_link"
branch_labels = None
depends_on = None

#: Mirrors saintvision.adapters.agents.TOOLS. Written out rather than imported:
#: a migration that reads today's application constants describes today's code
#: instead of the change it made.
TOOL_NAMES = ("claude-code", "codex-cli", "gemini-cli", "antigravity")


def upgrade() -> None:
    op.add_column("workspaces", sa.Column("tool_name", sa.String(32)))
    op.create_check_constraint(
        "tool_name_allowed",
        "workspaces",
        "tool_name IS NULL OR tool_name IN "
        + str(TOOL_NAMES).replace('"', "'"),
    )


def downgrade() -> None:
    op.drop_constraint("tool_name_allowed", "workspaces", type_="check")
    op.drop_column("workspaces", "tool_name")
