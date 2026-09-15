"""Upgrade an existing pinned replica from the 0042 constraint in PostgreSQL."""
import importlib.util
from pathlib import Path
import datetime as dt
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
import pytest

from test_replica_repair import location, _add_replica, NOW
from saintvision.db.session import tenant_scope
from saintvision.services.replica_repair import mark_node_replicas_unavailable


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


@pytest.mark.postgres
def test_departure_does_not_overwrite_concurrent_corruption(
    owner_engine, app_sessionmaker, location
):
    _add_replica(owner_engine, location, 0, "ready")
    application = "replica_review_" + uuid4().hex

    def depart():
        with app_sessionmaker() as session, session.begin():
            session.execute(text("SELECT set_config('application_name', :name, true)"),
                            {"name": application})
            session.execute(text("SET LOCAL lock_timeout='10s'"))
            with tenant_scope(session, location["tenant_a"]):
                return mark_node_replicas_unavailable(
                    session, tenant_id=location["tenant_a"],
                    node_id=location["nodes"][0], now=NOW
                )

    with ThreadPoolExecutor(max_workers=1) as pool:
        # Keep the corruption uncommitted until the departure transaction is
        # observed waiting on its row lock. No timing-only race assumption.
        with owner_engine.begin() as writer:
            writer.execute(text("UPDATE public.data_replicas SET state='corrupt' WHERE location_id=:id"),
                           {"id": location["location_id"]})
            future = pool.submit(depart)
            deadline = time.monotonic() + 8
            blocked = False
            while time.monotonic() < deadline:
                with owner_engine.connect() as observer:
                    blocked = observer.execute(text("""
                        SELECT EXISTS(SELECT 1 FROM pg_stat_activity
                         WHERE application_name=:name AND wait_event_type='Lock')
                    """), {"name": application}).scalar_one()
                if blocked:
                    break
                time.sleep(0.02)
            assert blocked, "departure transaction never reached the row lock"
        assert future.result(timeout=10) == 0
    with owner_engine.connect() as conn:
        assert conn.execute(text("SELECT state FROM public.data_replicas WHERE location_id=:id"),
                            {"id": location["location_id"]}).scalar_one() == "corrupt"
