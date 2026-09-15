"""Upgrade an existing pinned replica from the 0042 constraint in PostgreSQL."""
import importlib.util
from pathlib import Path
import datetime as dt

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
import pytest

from test_replica_repair import location, _add_replica, NOW


@pytest.mark.postgres
def test_forward_upgrade_preserves_existing_pin_and_bytes(owner_engine, location):
    _add_replica(owner_engine, location, 0, "ready")
    pin = NOW + dt.timedelta(hours=1)
    migration = Path(__file__).parents[1] / "migrations/versions/0043_replica_retention.py"
    spec = importlib.util.spec_from_file_location("retention_migration", migration)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with owner_engine.begin() as conn:
        conn.execute(text("""
            ALTER TABLE public.data_replicas
              DROP CONSTRAINT ck_data_replicas_retained_replicas_pin,
              ADD CONSTRAINT ck_data_replicas_only_ready_replicas_pin
                CHECK (pinned_until IS NULL OR state = 'ready')
        """))
        conn.execute(text("UPDATE public.data_replicas SET pinned_until=:pin WHERE location_id=:id"),
                     {"pin": pin, "id": location["location_id"]})
        before = conn.execute(text("SELECT * FROM public.data_replicas WHERE location_id=:id"),
                              {"id": location["location_id"]}).one()
        with Operations.context(MigrationContext.configure(conn)):
            module.upgrade()
        after = conn.execute(text("SELECT * FROM public.data_replicas WHERE location_id=:id"),
                             {"id": location["location_id"]}).one()
        assert after == before
        conn.execute(text("UPDATE public.data_replicas SET state='stale' WHERE location_id=:id"),
                     {"id": location["location_id"]})
        assert conn.execute(text("SELECT pinned_until FROM public.data_replicas WHERE location_id=:id"),
                            {"id": location["location_id"]}).scalar_one() == pin
