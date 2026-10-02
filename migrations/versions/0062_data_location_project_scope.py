"""Project binding for catalogued data locations (0062, card 253 Phase 1).

The design this implements ([[S02-ST 제공 폴더·DataLocation 카탈로그 설계 (카드 250)]] §3-2)
splits the work in two, and this is only the first half:

* the column and a composite foreign key land here, and nothing else does;
* **no policy, GRANT, ENABLE or FORCE changes.** ``data_locations`` keeps the
  ``data_locations_tenant_isolation`` policy 0001 created, so every reader that
  cannot set a project scope keeps working exactly as before. Replacing that
  policy with a tenant+project one is Phase 2 and a separate card, because a
  policy that requires ``inv.project_id`` would silently return zero rows for
  the existing owner-scoped routes that have no project selector at all.

``project_id`` is nullable on purpose. A location catalogued before this
revision has no project, and "no project" must mean **invisible to every
project-scoped read** rather than "visible to all of them" -- the fail-closed
direction. The route added with this revision never writes NULL: it takes the
project from its own path.

``storage_contributions`` is deliberately left alone. The product states that a
contribution is tenant-wide ("a folder belongs to a node, not a project",
``src/saintvision/api/v1/storage.py``), so the project binds to the catalogued
item inside the folder, not to the folder.

Reversible: the downgrade drops what the upgrade added and touches no policy,
so a round trip returns the exact pre-0062 state. Dropping the column loses the
bindings, and a later re-upgrade leaves every row NULL -- invisible to project
reads -- so reversing never widens exposure.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0062_data_location_project_scope"
down_revision = "0060_build_execution_admissions"
branch_labels = None
depends_on = None

INV_ID = sa.CHAR(30)

#: Named here so the downgrade drops exactly what the upgrade created.
PROJECT_FK = "fk_data_locations_tenant_id_project_id"


def upgrade() -> None:
    op.add_column("data_locations", sa.Column("project_id", INV_ID, nullable=True))
    # The composite key is what makes a cross-tenant project binding impossible
    # at the database level: projects carries uq_projects_tenant_id_project_id.
    op.create_foreign_key(
        PROJECT_FK,
        "data_locations",
        "projects",
        ["tenant_id", "project_id"],
        ["tenant_id", "project_id"],
    )
    # Project-scoped reads filter on (tenant_id, project_id) and then order by
    # the catalogue clock, so the index carries the ordering column too.
    op.create_index(
        "ix_data_locations_tenant_id_project_id",
        "data_locations",
        ["tenant_id", "project_id", "catalogued_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_data_locations_tenant_id_project_id", table_name="data_locations")
    op.drop_constraint(PROJECT_FK, "data_locations", type_="foreignkey")
    op.drop_column("data_locations", "project_id")
