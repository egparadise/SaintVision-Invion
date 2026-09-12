"""Snapshot-consistent pilot dump/restore/upgrade in an owned disposable database.

The dump is kept only in process memory, never published. Existing cluster roles
are reused. This is not an independent-cluster restore or a retained backup.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from sqlalchemy.engine import URL

from lan_pilot import load, runtime
from migration_graph import chain
from plan_lan_migration import gap_plan
from recovery_drill import Postgres, _definer_verdict

ROOT = Path(__file__).resolve().parents[1]


def inventory(conn, columns=None):
    """Digest every stored row, retaining the old projection across added columns."""
    if columns is None:
        columns = {}
        for schema, table in conn.execute("""SELECT schemaname,tablename FROM pg_tables
                WHERE schemaname IN ('public','inv') ORDER BY 1,2"""):
            names = [r[0] for r in conn.execute("""SELECT a.attname FROM pg_attribute a
                JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname=%s AND c.relname=%s AND a.attnum>0 AND NOT a.attisdropped
                ORDER BY a.attnum""", (schema, table))]
            columns[schema + "." + table] = names
    result = {}
    for name, names in columns.items():
        schema, table = name.split(".", 1)
        query = sql.SQL("SELECT row_to_json(t)::jsonb::text FROM (SELECT {} FROM {}.{}) t ORDER BY 1").format(
            sql.SQL(",").join(map(sql.Identifier, names)), sql.Identifier(schema), sql.Identifier(table))
        digest, count = hashlib.sha256(), 0
        # Stream rows so the comparison does not materialize all source data.
        with conn.cursor(name="inventory_" + uuid4().hex) as cursor:
            cursor.execute(query)
            for row in cursor:
                raw = row[0].encode("utf-8")
                digest.update(len(raw).to_bytes(8, "big"))
                digest.update(raw)
                count += 1
        result[name] = dict(rows=count, sha256=digest.hexdigest())
    return columns, result


def assert_preserved(before, after, *, upgraded=False):
    expected = {k: v for k, v in before.items() if not (upgraded and k == "public.alembic_version")}
    if any(after.get(k) != value for k, value in expected.items()):
        raise ValueError("Restored or upgraded rows differ from the source snapshot")


def digest_db(dsn, columns=None):
    with psycopg.connect(dsn) as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        conn.execute("SET LOCAL statement_timeout='30s'")
        return inventory(conn, columns)


def rehearse(state_path):
    state = load(state_path)
    source = state["adminDSN"]
    name = "inv_lan_rehearsal_" + uuid4().hex
    target = make_conninfo(source, dbname=name)
    client = Postgres(state["container"])
    # Docker's client connects inside the existing PostgreSQL container.
    inside_source = make_conninfo(source, host="127.0.0.1", port=5432)
    inside_target = make_conninfo(inside_source, dbname=name)
    created = False
    report = dict(startedAt=datetime.now(timezone.utc).isoformat(),
                  scope="same-cluster-snapshot-database-upgrade-rehearsal",
                  operationalAcceptanceAssessed=False, sourceDatabaseMutated=False,
                  retainedBackup=False, independentClusterRestore=False)
    try:
        with psycopg.connect(source) as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            conn.execute("SET LOCAL statement_timeout='30s'")
            snapshot = conn.execute("SELECT pg_export_snapshot()").fetchone()[0]
            heads = [r[0] for r in conn.execute("SELECT version_num FROM public.alembic_version")]
            report["plan"] = gap_plan(heads)
            columns, before = inventory(conn)
            dump = client.run("pg_dump", ["--dbname", inside_source, "--format=custom", "--snapshot", snapshot])
            if dump.returncode:
                raise ValueError("Snapshot dump failed")
            archive = dump.stdout
            report["archiveSha256"] = hashlib.sha256(archive).hexdigest()
            report["archiveBytes"] = len(archive)
        with psycopg.connect(source, autocommit=True) as conn:
            conn.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(name)))
            created = True
        restored = client.run("pg_restore", ["--dbname", inside_target, "--exit-on-error"], stdin=archive)
        if restored.returncode:
            raise ValueError("Snapshot restore failed")
        restored_columns, restored_rows = digest_db(target)
        if restored_columns != columns or restored_rows != before:
            raise ValueError("Restore inventory differs")
        report["restoreExactRows"] = True
        info = conninfo_to_dict(target)
        url = URL.create("postgresql+psycopg", username=info.get("user"), password=info.get("password"),
                         host=info.get("host"), port=int(info.get("port", 5432)), database=name)
        env = {**os.environ, "INV_MIGRATION_DSN": url.render_as_string(hide_password=False)}
        first_upgrade = None
        for _ in range(2):
            applied = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"],
                                     cwd=ROOT, env=env, capture_output=True, timeout=180)
            if applied.returncode:
                raise ValueError("Restored database upgrade failed")
            current_inventory = digest_db(target)
            if first_upgrade is None:
                first_upgrade = current_inventory
            elif current_inventory != first_upgrade:
                raise ValueError("Upgrade replay changed rows or column inventory")
        report["replayExactRows"] = True
        _, after = digest_db(target, columns)
        assert_preserved(before, after, upgraded=True)
        report["oldColumnRowsPreserved"] = True
        report["sourceTables"] = len(before)
        report["sourceRows"] = sum(r["rows"] for r in before.values())
        report["sourceInventory"] = before
        with psycopg.connect(target) as conn:
            final_heads = [r[0] for r in conn.execute("SELECT version_num FROM public.alembic_version")]
        if final_heads != [chain()[-1].revision]:
            raise ValueError("Upgraded revision differs")
        report["finalHeads"] = final_heads
        report["definer"] = _definer_verdict(target)
        if not report["definer"].get("checked") or report["definer"].get("unsafe") != 0:
            raise ValueError("Upgraded privileged functions require review")
        copied = {**state, "runtimeDSN": make_conninfo(state["runtimeDSN"], dbname=name)}
        with runtime(copied).transaction(state["tenantId"]) as conn:
            row = conn.execute("SELECT node_id FROM inv.nodes WHERE node_id=%s", (state["nodeId"],)).fetchone()
            if not row:
                raise ValueError("Restored runtime cannot see its Node")
        report["runtimeTransactionPassed"] = True
        report["completedAt"] = datetime.now(timezone.utc).isoformat()
        return report
    finally:
        if created:
            assert name.startswith("inv_lan_rehearsal_") and len(name) == 50
            assert conninfo_to_dict(source)["dbname"] != name
            with psycopg.connect(source, autocommit=True) as conn:
                conn.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
            report["disposableDatabaseRemoved"] = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = rehearse(args.state)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    except Exception:
        print("Snapshot upgrade rehearsal failed; source deployment not authorized.", file=sys.stderr)
        return 2
    print("PASS: snapshot restore, old-column row preservation, upgrade/replay and runtime DB transaction")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
