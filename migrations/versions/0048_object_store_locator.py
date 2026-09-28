"""Persist immutable ObjectStore provider/locator with exact local backfill.

The revision is intentionally irreversible once an S3 locator exists. Restore
the pre-upgrade database backup or apply a reviewed forward migration; silently
collapsing provider-native locators into local keys would corrupt replay identity.
"""

from importlib import resources

from alembic import op


revision = "0048_object_store_locator"
down_revision = "0047_audit_events_isolation"
branch_labels = None
depends_on = None


def upgrade():
    script = resources.files("inv").joinpath(
        "migrations/0026_object_store_locator.sql"
    ).read_text("utf-8")
    op.execute(script)


def downgrade():
    raise RuntimeError(
        "Object provider/locator identity is irreversible; restore the pre-upgrade backup or forward-fix"
    )
