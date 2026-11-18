"""Supply a fresh, disposable database. No existing schema is reused."""
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import psycopg
import pytest

from inv.e1_reservation import reserve_pc1

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "contracts/proposed/fleet5-e1"


def locked_authority(conn, tenant):
    return conn.execute("""
        SELECT holder, generation, binding FROM e1.test_authority
        WHERE tenant_id=%s FOR UPDATE
    """, (tenant,)).fetchone()


def test_missing_authority():
    assert reserve_pc1(None, None, None, None, None) == "HOLD_AUTHORITY_UNAVAILABLE"


def test_pc1_transactions():
    dsn = os.environ.get("E1_DISPOSABLE_PG_DSN")
    if not dsn:
        pytest.skip("requires a fresh disposable PostgreSQL database")
    binding = json.loads((CONTRACT / "p14-reservation.json").read_text())
    request = str(uuid4())
    tenant = binding["tenantID"]

    def reserve(conn, key=request, writer="first", generation=1, body=None):
        return reserve_pc1(conn, key, writer, generation, body or binding,
                           lock_authority=locked_authority)

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.transaction():
            conn.execute("CREATE SCHEMA e1")
            conn.execute((CONTRACT / "reservations.sql").read_text())
            conn.execute("""CREATE TABLE e1.test_authority (
                tenant_id uuid PRIMARY KEY, holder text, generation bigint, binding jsonb)""")
        assert reserve(conn) == "HOLD_AUTHORITY_UNAVAILABLE"
        conn.execute("INSERT INTO e1.test_authority VALUES (%s,'first',1,%s)",
                     (tenant, psycopg.types.json.Jsonb(binding)))
        with pytest.raises(RuntimeError, match="rollback"):
            with conn.transaction():
                assert reserve(conn) == "RESERVED"
                raise RuntimeError("rollback")
        assert conn.execute("SELECT count(*) FROM e1.reservations").fetchone() == (0,)
        barrier = Barrier(3, timeout=10)

        def compete(key):
            with psycopg.connect(dsn) as other:
                barrier.wait()
                return reserve(other, key)

        keys = [request, request, str(uuid4())]
        with ThreadPoolExecutor(3) as workers:
            results = list(workers.map(compete, keys))
        assert results.count("RESERVED") == 1
        winner = keys[results.index("RESERVED")]
        for key, result in zip(keys, results):
            assert result in ({"RESERVED", "EXACT_RETRY"} if key == winner
                              else {"HOLD_RESERVATION_MISMATCH"})
        assert reserve(conn, winner) == "EXACT_RETRY"
        changed = dict(binding, csrSHA256="a" * 64)
        assert reserve(conn, winner, body=changed) == "HOLD_RESERVATION_MISMATCH"
        # Even when the new body is authorized, the durable request cannot change.
        conn.execute("UPDATE e1.test_authority SET binding=%s", (psycopg.types.json.Jsonb(changed),))
        assert reserve(conn, winner, body=changed) == "HOLD_RESERVATION_MISMATCH"
        conn.execute("UPDATE e1.test_authority SET holder='second',generation=2")
        assert reserve(conn, winner) == "HOLD_WRITER_FENCE"
        assert reserve(conn, winner, writer="second") == "HOLD_WRITER_FENCE"
        assert conn.execute("SELECT request_id::text,binding FROM e1.reservations").fetchall() == [
            (winner, binding)]
        # Rotate while the original holder is already waiting on the row lock.
        import time
        from threading import Event
        entered = Event()
        with psycopg.connect(dsn, autocommit=True, application_name="e1_stale") as waiter:
            def stale_retry():
                entered.set()
                return reserve(waiter, winner, writer="second", generation=2, body=changed)

            with ThreadPoolExecutor(1) as workers:
                with conn.transaction():
                    conn.execute("UPDATE e1.test_authority SET generation=3")
                    pending = workers.submit(stale_retry)
                    assert entered.wait(5)
                    deadline = time.monotonic() + 5
                    while not conn.execute("""
                        SELECT pg_backend_pid() = ANY(pg_blocking_pids(%s))
                    """, (waiter.info.backend_pid,)).fetchone()[0]:
                        assert time.monotonic() < deadline, "writer never waited for authority"
                        time.sleep(0.01)
                assert pending.result(timeout=5) == "HOLD_WRITER_FENCE"
