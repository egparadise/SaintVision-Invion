"""Supply a fresh, disposable database. No existing schema is reused."""
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import psycopg
import pytest

from inv.e1_reservation import canonical_digest, csr_key, eligible, reconcile_pc1, reserve_pc1

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "contracts/proposed/fleet5-e1"


def locked_authority(conn, tenant):
    return conn.execute("""
        SELECT holder, generation, binding,
               evidence || jsonb_build_object('freshFence',
                   read_at <= clock_timestamp() AND expires_at > clock_timestamp())
        FROM e1.test_authority
        WHERE tenant_id=%s FOR UPDATE
    """, (tenant,)).fetchone()


def test_missing_authority():
    assert reserve_pc1(None, None, None, None, None) == "HOLD_AUTHORITY_UNAVAILABLE"


@pytest.fixture
def e1_database(request):
    explicit = os.environ.get("E1_DISPOSABLE_PG_DSN")
    if explicit:
        yield explicit
        return
    admin = request.getfixturevalue("test_admin_dsn")
    name = "e1_test_" + uuid4().hex
    with psycopg.connect(admin, autocommit=True) as setup:
        setup.execute(psycopg.sql.SQL("CREATE DATABASE {}").format(psycopg.sql.Identifier(name)))
        try:
            yield psycopg.conninfo.make_conninfo(admin, dbname=name)
        finally:
            setup.execute(psycopg.sql.SQL("DROP DATABASE {}").format(psycopg.sql.Identifier(name)))


def test_pc1_transactions(e1_database):
    dsn = e1_database
    binding = json.loads((CONTRACT / "p14-reservation.json").read_text())
    inputs = json.loads((CONTRACT / "p14-inputs.json").read_text())
    binding["rowsReadbackSHA256"] = canonical_digest(inputs["rows"])
    evidence = dict(inputs, authenticatedAllHistory=True, freshFence=True,
                    plannedPublicKey=csr_key(inputs["csrDER"], binding["csrSHA256"]), epoch=binding["epoch"],
                    operation="fixture:E1", a7=[binding["planDigest"], inputs["manifest"], "COMMITTED"])
    request = str(uuid4())
    tenant = binding["tenantID"]

    def reserve(conn, key=request, writer="first", generation=1, body=None):
        return reserve_pc1(conn, key, writer, generation, body or binding,
                           csr_der=inputs["csrDER"], lock_authority=locked_authority)

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.transaction():
            migration = ROOT / "services/control-plane/src/inv/migrations"
            for filename in sorted(migration.glob("000[1-5]_*.sql")):
                conn.execute(filename.read_text(encoding="utf-8"))
            conn.execute("INSERT INTO inv.tenants VALUES (%s, 'fixture')", (tenant,))
            conn.execute("INSERT INTO inv.nodes(tenant_id,node_id,status) VALUES (%s,%s,'offline')",
                         (tenant, inputs["rows"][0]["nodeID"]))
            conn.execute("CREATE SCHEMA e1")
            # Model a pre-existing holder at schema creation time. The complete
            # contract has no bootstrap path until authenticated A1 exists.
            ddl = (CONTRACT / "reservations.sql").read_text()
            guard = ddl.index("CREATE TRIGGER guard_transfer")
            conn.execute(ddl[:guard])
            conn.execute("INSERT INTO fleet_writer.principals VALUES (session_user,%s)", (tenant,))
            conn.execute("INSERT INTO fleet_writer.authority VALUES (%s,session_user,'first',1)", (tenant,))
            conn.execute(ddl[guard:])
            conn.execute("""CREATE TABLE e1.test_authority (
                tenant_id uuid PRIMARY KEY, holder text, generation bigint, binding jsonb, evidence jsonb,
                read_at timestamptz DEFAULT now(), expires_at timestamptz DEFAULT now()+interval '2 minutes')""")
            for generation in (1, 7):
                with pytest.raises(psycopg.errors.RaiseException, match="authenticated genesis unavailable"), conn.transaction():
                    conn.execute("INSERT INTO fleet_writer.authority VALUES (%s,session_user,'other',%s)",
                                 (uuid4(), generation))
            assert conn.execute("SELECT count(*) FROM fleet_writer.authority").fetchone() == (1,)
        def membership():
            return [conn.execute("SELECT * FROM inv." + table).fetchall()
                    for table in ("nodes", "node_channels", "node_channel_audit", "resources")]
        before = membership()
        conn.execute("SELECT set_config('inv.tenant_id',%s,false)", (tenant,))
        assert reserve(conn) == "HOLD_AUTHORITY_UNAVAILABLE"
        conn.execute("INSERT INTO e1.test_authority(tenant_id,holder,generation,binding,evidence) VALUES (%s,'first',1,%s,%s)",
                     (tenant, psycopg.types.json.Jsonb(binding), psycopg.types.json.Jsonb(evidence)))
        with pytest.raises(RuntimeError, match="rollback"):
            with conn.transaction():
                assert reserve(conn) == "RESERVED"
                raise RuntimeError("rollback")
        assert conn.execute("SELECT count(*) FROM e1.reservations").fetchone() == (0,)
        assert conn.execute("SELECT count(*) FROM e1.reservation_audit").fetchone() == (0,)
        assert conn.execute("SELECT count(*) FROM fleet_writer.journal").fetchone() == (0,)
        reads = []
        def expires_before_commit(connection, scope):
            reads.append(scope)
            return locked_authority(connection, scope) if len(reads) == 1 else None
        assert reserve_pc1(conn, request, "first", 1, binding, csr_der=inputs["csrDER"],
                           lock_authority=expires_before_commit) == "HOLD_WRITER_FENCE"
        assert conn.execute("SELECT count(*) FROM e1.reservations").fetchone() == (0,)
        assert conn.execute("SELECT count(*) FROM e1.reservation_audit").fetchone() == (0,)
        # Seed an incomplete legacy receipt with ordinary INSERT privileges.
        digest = canonical_digest(binding)
        for surviving_table in ("audit", "journal"):
            with conn.transaction(force_rollback=True):
                conn.execute("""INSERT INTO e1.reservations VALUES
                    (%s,'PC1',%s,%s,'first',1,%s,%s,%s,%s,%s)""",
                    (tenant, binding["nodeID"], request, psycopg.types.json.Jsonb(binding),
                     digest, evidence["plannedPublicKey"], evidence["manifest"], evidence["operation"]))
                receipt = (tenant, evidence["operation"], evidence["manifest"], digest)
                if surviving_table == "audit":
                    conn.execute("INSERT INTO e1.reservation_audit VALUES (%s,%s,%s,%s)", receipt)
                else:
                    conn.execute("""INSERT INTO fleet_writer.journal VALUES
                        (%s,%s,'E1','first',1,%s,%s)""", receipt)
                assert reserve(conn) == "HOLD_RESERVATION_MISMATCH"
        barrier = Barrier(3, timeout=10)

        def compete(key):
            with psycopg.connect(dsn) as other:
                other.execute("SELECT set_config('inv.tenant_id',%s,false)", (tenant,))
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
        with conn.transaction(force_rollback=True):
            with pytest.raises(psycopg.errors.RaiseException, match="immutable"), conn.transaction():
                conn.execute("TRUNCATE fleet_writer.journal")
            with pytest.raises(psycopg.errors.RaiseException, match="immutable"), conn.transaction():
                conn.execute("TRUNCATE e1.reservation_audit")
        with conn.transaction(force_rollback=True):
            conn.execute("UPDATE e1.test_authority SET expires_at=clock_timestamp()")
            assert reserve(conn, winner) == "HOLD_WRITER_FENCE"
        with psycopg.connect(dsn, autocommit=True) as reader:
            reader.execute("SELECT set_config('inv.tenant_id',%s,false)", (tenant,))
            args = (reader, winner, "first", 1, binding, evidence["plannedPublicKey"], evidence["manifest"])
            assert reconcile_pc1(*args, evidence["operation"]) == "COMMITTED"
            assert reconcile_pc1(*args, "foreign") == "HOLD_RESERVATION_MISMATCH"
        changed = dict(binding, nodeStateEmpty={"verified": True, "evidenceRef": "fixture:changed"})
        assert reserve(conn, winner, body=changed) == "HOLD_RESERVATION_MISMATCH"
        # Even when the new body is authorized, the durable request cannot change.
        conn.execute("UPDATE e1.test_authority SET binding=%s", (psycopg.types.json.Jsonb(changed),))
        assert reserve(conn, winner, body=changed) == "HOLD_RESERVATION_MISMATCH"
        def transfer(old, generation, successor, operation):
            conn.execute("""SELECT fleet_writer.transfer(%s,%s,%s,session_user,%s,%s,%s,%s)""",
                         (tenant, old, generation, successor, operation,
                          binding["planDigest"], binding["fenceToken"]))

        operation = uuid4()
        with conn.transaction(force_rollback=True):
            transfer("first", 1, "second", operation)
        assert conn.execute("SELECT count(*) FROM fleet_writer.transfer_journal").fetchone() == (0,)
        with conn.transaction(force_rollback=True):
            outsider = "e1_other_" + uuid4().hex
            role = psycopg.sql.Identifier(outsider)
            conn.execute(psycopg.sql.SQL("CREATE ROLE {}").format(role))
            conn.execute(psycopg.sql.SQL("GRANT USAGE ON SCHEMA fleet_writer TO {}").format(role))
            conn.execute(psycopg.sql.SQL("GRANT EXECUTE ON FUNCTION fleet_writer.transfer(uuid,text,bigint,name,text,uuid,text,text) TO {}").format(role))
            foreign = str(uuid4())
            conn.execute("INSERT INTO fleet_writer.principals VALUES (%s,%s)", (outsider, foreign))
            with pytest.raises(psycopg.errors.ForeignKeyViolation), conn.transaction():
                conn.execute("SELECT fleet_writer.transfer(%s,'first',1,%s,'second',%s,%s,%s)",
                             (tenant, outsider, operation, binding["planDigest"], binding["fenceToken"]))
            conn.execute("SELECT set_config('inv.tenant_id',%s,true)", (foreign,))
            with pytest.raises(psycopg.errors.RaiseException, match="unauthorized transfer"), conn.transaction():
                transfer("first", 1, "second", operation)
            conn.execute("SELECT set_config('inv.tenant_id',%s,true)", (tenant,))
            for principal_scope in (foreign, tenant):
                conn.execute("UPDATE fleet_writer.principals SET tenant_id=%s WHERE login=%s",
                             (principal_scope, outsider))
                with conn.transaction(force_rollback=True):
                    conn.execute(psycopg.sql.SQL("SET LOCAL SESSION AUTHORIZATION {}").format(role))
                    with pytest.raises(psycopg.errors.RaiseException, match="stale or unauthorized"), conn.transaction():
                        transfer("first", 1, "second", operation)
            assert conn.execute("SELECT count(*) FROM fleet_writer.transfer_journal").fetchone() == (0,)

        start = Barrier(2)
        def compete():
            with psycopg.connect(dsn, autocommit=True) as contender:
                contender.execute("SELECT set_config('inv.tenant_id',%s,false)", (tenant,))
                start.wait(timeout=10)
                try:
                    contender.execute("SELECT fleet_writer.transfer(%s,'first',1,session_user,'second',%s,%s,%s)",
                                      (tenant, operation, binding["planDigest"], binding["fenceToken"]))
                except psycopg.errors.RaiseException as exc:
                    assert "stale or unauthorized transfer" in str(exc)
                    return False
                return True

        with ThreadPoolExecutor(2) as workers:
            results = [workers.submit(compete) for _ in range(2)]
            assert sorted(result.result(timeout=15) for result in results) == [False, True]
        assert conn.execute("SELECT count(*) FROM fleet_writer.transfer_journal").fetchone() == (1,)
        with pytest.raises(psycopg.errors.UniqueViolation), conn.transaction():
            transfer("second", 2, "third", operation)
        assert conn.execute("SELECT holder,generation FROM fleet_writer.authority").fetchone() == ("second", 2)
        assert conn.execute("""SELECT previous_holder,next_holder,actor=session_user,plan_digest,fence_token
            FROM fleet_writer.transfer_journal""").fetchone() == (
                "first", "second", True, binding["planDigest"], binding["fenceToken"])
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
            waiter.execute("SELECT set_config('inv.tenant_id',%s,false)", (tenant,))
            def stale_retry():
                entered.set()
                return reserve(waiter, winner, writer="second", generation=2, body=changed)

            with ThreadPoolExecutor(1) as workers:
                with conn.transaction():
                    transfer("second", 2, "third", uuid4())
                    pending = workers.submit(stale_retry)
                    assert entered.wait(5)
                    deadline = time.monotonic() + 5
                    while not conn.execute("""
                        SELECT pg_backend_pid() = ANY(pg_blocking_pids(%s))
                    """, (waiter.info.backend_pid,)).fetchone()[0]:
                        assert time.monotonic() < deadline, "writer never waited for authority"
                        time.sleep(0.01)
                assert pending.result(timeout=5) == "HOLD_WRITER_FENCE"

        assert membership() == before
        assert conn.execute("SELECT count(*) FROM e1.reservation_audit").fetchone() == (1,)
        role = psycopg.sql.Identifier("e1_test_" + uuid4().hex)
        with conn.transaction(force_rollback=True):
            conn.execute(psycopg.sql.SQL("CREATE ROLE {}").format(role))
            conn.execute(psycopg.sql.SQL("GRANT USAGE ON SCHEMA e1 TO {}").format(role))
            conn.execute(psycopg.sql.SQL("GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA e1 TO {}").format(role))
            conn.execute(psycopg.sql.SQL("GRANT USAGE ON SCHEMA fleet_writer TO {}").format(role))
            conn.execute(psycopg.sql.SQL("GRANT EXECUTE ON FUNCTION fleet_writer.authenticated_tenant(), fleet_writer.lock_holder(uuid) TO {}").format(role))
            conn.execute(psycopg.sql.SQL("GRANT SELECT ON fleet_writer.journal TO {}").format(role))
            conn.execute(psycopg.sql.SQL("SET LOCAL ROLE {}").format(role))
            conn.execute("SELECT set_config('inv.tenant_id',%s,true)", (str(uuid4()),))
            for table in ("reservations", "reservation_audit"):
                assert not conn.execute("SELECT 1 FROM e1." + table).fetchall()
            with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
                conn.execute("INSERT INTO e1.reservation_audit VALUES (%s,'foreign',%s,%s)",
                             (tenant, "a"*64, "b"*64))
            conn.execute("SELECT set_config('inv.tenant_id',%s,true)", (tenant,))
            for table in ("reservations", "reservation_audit"):
                assert conn.execute("SELECT count(*) FROM e1." + table).fetchone() == (1,)
            conn.execute(psycopg.sql.SQL("SET LOCAL SESSION AUTHORIZATION {}").format(role))
            assert not conn.execute("SELECT * FROM fleet_writer.lock_holder(%s)", (tenant,)).fetchall()
            for table in ("e1.reservations", "e1.reservation_audit", "fleet_writer.journal"):
                assert not conn.execute("SELECT 1 FROM " + table).fetchall()
        with pytest.raises(psycopg.errors.RaiseException, match="stale writer"), conn.transaction():
            conn.execute("""INSERT INTO fleet_writer.journal
                         VALUES (%s,'stale','E1','first',1,%s,%s)""",
                         (tenant, "a"*64, "b"*64))
        assert conn.execute("SELECT count(*) FROM fleet_writer.journal").fetchone() == (1,)



@pytest.mark.parametrize("case", ["retired-key", "disabled-node", "rotation-key", "stale-digest",
                                   "missing-history", "foreign-A7", "missing-A7", "wrong-epoch",
                                   "duplicate-node", "duplicate-key", "unknown-status", "foreign-rotation"])
def test_ineligible_history_or_checkpoint(case):
    binding = json.loads((CONTRACT / "p14-reservation.json").read_text())
    inputs = json.loads((CONTRACT / "p14-inputs.json").read_text())
    key = csr_key(inputs["csrDER"], binding["csrSHA256"])
    assert key
    evidence = dict(inputs, authenticatedAllHistory=True, freshFence=True,
                    plannedPublicKey=csr_key(inputs["csrDER"], binding["csrSHA256"]), epoch=binding["epoch"], operation="E1",
                    a7=[binding["planDigest"], inputs["manifest"], "COMMITTED"])
    if case == "duplicate-node":
        inputs["rows"][-1]["nodeID"] = inputs["rows"][0]["nodeID"]
    elif case == "duplicate-key":
        inputs["rows"][-1]["publicKeySHA256"] = inputs["rows"][0]["publicKeySHA256"]
    elif case == "unknown-status":
        inputs["rows"][-1]["status"] = "unknown"
    elif case == "foreign-rotation":
        evidence["rotationKeys"][0] = inputs["rows"][-1]["publicKeySHA256"]
    elif case == "retired-key":
        inputs["rows"][0].update(status="RETIRED", publicKeySHA256=key)
    elif case == "disabled-node":
        inputs["rows"][0].update(status="DISABLED", nodeID=binding["nodeID"])
    elif case == "rotation-key":
        evidence["rotationKeys"][0] = key
    elif case == "missing-history":
        evidence["authenticatedAllHistory"] = False
    elif case == "foreign-A7":
        evidence["a7"][1] = "0" * 64
    elif case == "missing-A7":
        del evidence["a7"]
    elif case == "wrong-epoch":
        evidence["epoch"] = str(uuid4())
    if case != "stale-digest":
        binding["rowsReadbackSHA256"] = canonical_digest(evidence["rows"])
    assert not eligible(binding, evidence, key)
