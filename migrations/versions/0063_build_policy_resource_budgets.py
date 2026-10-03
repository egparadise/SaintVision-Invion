"""Per-build resource budgets for the immutable S08 build profile (0063).

Existing profile versions remain readable for audit but cannot activate product
dispatch: their three budget columns are NULL and the runtime fails closed.  An
operator must append a new profile version with all three positive values.  The
existing profile guard makes those values immutable after insertion.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0063_build_policy_budgets"
down_revision = "0062_data_location_project_scope"
branch_labels = None
depends_on = None

TABLE = "build_policy_profiles"
COLUMNS = ("budget_cpu_millis", "budget_memory_bytes", "budget_storage_bytes")


def upgrade() -> None:
    for name in COLUMNS:
        op.add_column(TABLE, sa.Column(name, sa.BigInteger(), nullable=True), schema="inv")
    op.add_column(
        TABLE,
        sa.Column("base_image_digests", postgresql.ARRAY(sa.Text()), nullable=True),
        schema="inv",
    )
    op.create_check_constraint(
        "build_policy_budget_complete_and_positive",
        TABLE,
        "(budget_cpu_millis IS NULL AND budget_memory_bytes IS NULL "
        "AND budget_storage_bytes IS NULL AND base_image_digests IS NULL) OR "
        "(budget_cpu_millis BETWEEN 1 AND 9007199254740991 "
        "AND budget_memory_bytes BETWEEN 1 AND 9007199254740991 "
        "AND budget_storage_bytes BETWEEN 1 AND 9007199254740991 "
        "AND base_image_digests IS NOT NULL "
        "AND cardinality(base_image_digests) BETWEEN 1 AND 64)",
        schema="inv",
    )


def downgrade() -> None:
    context = op.get_context()
    if not context.as_sql:
        populated = op.get_bind().exec_driver_sql(
            "SELECT profile_id,version FROM inv.build_policy_profiles "
            "WHERE budget_cpu_millis IS NOT NULL OR budget_memory_bytes IS NOT NULL "
            "OR budget_storage_bytes IS NOT NULL OR base_image_digests IS NOT NULL "
            "ORDER BY profile_id,version LIMIT 10"
        ).fetchall()
        if populated:
            identities = ", ".join(f"{row[0]}@{row[1]}" for row in populated)
            raise RuntimeError(
                "0063_build_policy_budgets cannot discard active profile budgets "
                f"({identities}); restore a reviewed pre-0063 database instead"
            )
    op.drop_constraint(
        "build_policy_budget_complete_and_positive",
        TABLE,
        schema="inv",
        type_="check",
    )
    op.drop_column(TABLE, "base_image_digests", schema="inv")
    for name in reversed(COLUMNS):
        op.drop_column(TABLE, name, schema="inv")
