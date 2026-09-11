"""Actually restore a backup, measure what it cost, and record the result.

``recovery_drills`` has existed since S12 with a careful shape — measured and
target values kept apart, a pass refused without numbers, a database pass
refused without a fencing check. Nothing ever performed one. A table for the
answer and no way to produce it is a rehearsal that has never happened, and the
first time anyone finds out is during the incident it was meant to prepare for.

This does the rehearsal end to end: dump the live database, restore it into a
disposable one, verify the restored content, measure RPO and RTO, check the
property that makes a database restore safe, and write the row.

Three decisions carry the weight.

**It never restores over the source.** That is the one mistake that turns a
rehearsal into the outage it was practising for, so the target is always a
database this tool created, its name is checked before anything is dropped, and
a target equal to the source is refused outright rather than guarded by
convention.

**Exit code zero is not verification.** ``pg_restore`` returning 0 means it
parsed the file. The drill compares row counts for every table the models
declare and a content digest for the ones that carry evidence, because a restore
that produced an empty database also exits 0.

**The fencing check is the point, not a checkbox.** ERR-DESIGN-006: restoring to
an earlier moment rewinds ``inv.fencing_token_seq`` while a Node Agent holding
token 500 does not rewind. The restored sequence then issues tokens a live
holder already has, and the ordering fencing exists to provide is gone — either
live commands look stale and are rejected, or a new lease is issued a token
below one still in use. The drill measures that gap against the source and
reports the advance required. A restore that has not been checked this way has
not been shown to be safe, and the schema already refuses to call it a pass.

Usage:
    python tools/recovery_drill.py --source DSN --admin DSN \\
        --tenant UUID --user usr_... [--docker CONTAINER] [--keep]
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

#: Tables whose contents are digested rather than merely counted. These are the
#: ones a restore exists to bring back intact; a count alone would not notice a
#: row that came back with different bytes.
DIGESTED = ("evidence_envelopes", "run_records", "artifacts", "backup_records")


class Postgres:
    """Runs the client tools, in the container when that is where they live.

    Discovered rather than assumed: a control plane host usually has them on
    PATH and a developer workstation usually does not, and a drill that cannot
    tell the difference reports a missing binary as a failed restore.
    """

    def __init__(self, container: str | None) -> None:
        self.container = container

    def _argv(self, program: str, args: list[str]) -> list[str]:
        if self.container:
            return ["docker", "exec", "-i", self.container, program, *args]
        return [program, *args]

    def available(self, program: str) -> bool:
        try:
            subprocess.run(
                self._argv(program, ["--version"]),
                capture_output=True,
                timeout=30,
                check=True,
            )
            return True
        except Exception:
            return False

    def run(self, program: str, args: list[str], *, stdin: bytes | None = None):
        return subprocess.run(
            self._argv(program, args),
            input=stdin,
            capture_output=True,
            timeout=1800,
        )


_SECRET = __import__("re").compile(r"(?i)(password=)[^\s'\"]+")


def _keep_key(match) -> str:
    """Keep the key, drop the value: the reader needs to know *what* was wrong."""
    return match.group(1) + "[redacted]"


def _redacted(text: str) -> str:
    """Client-tool output with any password in a connection string removed.

    Diagnostics are shown rather than swallowed — a tool that reports "it
    failed" teaches people to distrust the tool instead of reading the error —
    but a DSN in an error message is a credential in a log.
    """
    import re

    return re.sub(_SECRET, _keep_key, text)


def _conn(dsn: str):
    import psycopg

    return psycopg.connect(dsn, autocommit=True)


def _table_counts(dsn: str) -> dict[str, int]:
    """Every table in both schemas, discovered rather than listed.

    The first version counted only the tables the business models declare, which
    is a minority of the system: the execution kernel's ``inv`` schema holds the
    runs, leases, evidence and receipts a restore mostly exists to bring back.
    Reading the catalogue means a table added by either half is counted the day
    it appears.
    """
    counts: dict[str, int] = {}
    with _conn(dsn) as conn:
        tables = conn.execute(
            "SELECT schemaname, tablename FROM pg_catalog.pg_tables "
            "WHERE schemaname IN ('public', 'inv') ORDER BY schemaname, tablename"
        ).fetchall()
        for schema, table in tables:
            key = f"{schema}.{table}"
            try:
                counts[key] = conn.execute(
                    f'SELECT count(*) FROM "{schema}"."{table}"'
                ).fetchone()[0]
            except Exception:
                # A table the restore did not bring back is a finding, recorded
                # as absent rather than skipped.
                counts[key] = -1
    return counts


def _privileges(dsn: str) -> dict[str, str]:
    """Who may do what, per table and per column, as a comparable digest.

    A restore that brings back every row and none of the grants is a database
    the system cannot connect to — the runtime refuses to run as the owner, so
    losing the grants means losing the only role it will accept. Column
    privileges are included because the design leans on them: UPDATE on one
    CHECK-pinned sentinel column is what separates "may lock this row" from
    "may change it".
    """
    digests: dict[str, str] = {}
    with _conn(dsn) as conn:
        table_rows = conn.execute(
            "SELECT table_schema, table_name, grantee, privilege_type "
            "FROM information_schema.role_table_grants "
            "WHERE table_schema IN ('public','inv') "
            "ORDER BY 1,2,3,4"
        ).fetchall()
        column_rows = conn.execute(
            "SELECT table_schema, table_name, column_name, grantee, privilege_type "
            "FROM information_schema.column_privileges "
            "WHERE table_schema IN ('public','inv') "
            "ORDER BY 1,2,3,4,5"
        ).fetchall()
    digests["table"] = hashlib.sha256(
        "\n".join("|".join(map(str, r)) for r in table_rows).encode()
    ).hexdigest()
    digests["column"] = hashlib.sha256(
        "\n".join("|".join(map(str, r)) for r in column_rows).encode()
    ).hexdigest()
    digests["tableGrantCount"] = str(len(table_rows))
    digests["columnGrantCount"] = str(len(column_rows))
    return digests


def _content_digest(dsn: str) -> dict[str, str]:
    """A digest per evidence-bearing table, so a changed row is visible.

    Ordered by primary key text so two databases with the same rows digest the
    same regardless of physical order.
    """
    digests: dict[str, str] = {}
    with _conn(dsn) as conn:
        for table in DIGESTED:
            try:
                rows = conn.execute(
                    f'SELECT to_jsonb(t)::text FROM public."{table}" t ORDER BY 1'
                ).fetchall()
            except Exception:
                digests[table] = "absent"
                continue
            digest = hashlib.sha256()
            for (row,) in rows:
                digest.update(row.encode())
                digest.update(b"\n")
            digests[table] = digest.hexdigest()
    return digests


def _fencing_state(dsn: str) -> dict[str, int]:
    """The highest token issued, and the highest one a lease still holds.

    Both matter. The sequence says what will be issued next; the leases say what
    is out in the world and cannot be recalled.
    """
    with _conn(dsn) as conn:
        try:
            issued = conn.execute(
                "SELECT last_value FROM inv.fencing_token_seq"
            ).fetchone()[0]
        except Exception:
            issued = 0
        try:
            held = conn.execute(
                "SELECT coalesce(max(fencing_token), 0) FROM inv.resource_leases "
                "WHERE released_at IS NULL"
            ).fetchone()[0]
        except Exception:
            held = 0
    return {"sequenceLastValue": int(issued), "highestHeldToken": int(held)}


def rehearse(args) -> dict[str, Any]:
    from psycopg import sql
    from psycopg.conninfo import conninfo_to_dict, make_conninfo

    pg = Postgres(args.docker)
    for program in ("pg_dump", "psql"):
        if not pg.available(program):
            raise SystemExit(
                f"{program} is not available"
                + (f" in container {args.docker}" if args.docker else " on PATH")
                + ". A drill cannot be performed without it, and reporting a "
                "missing binary as a failed restore would be a lie about the "
                "backup."
            )

    source_info = conninfo_to_dict(args.source)
    source_db = source_info.get("dbname")
    target_db = "inv_drill_" + uuid.uuid4().hex

    if target_db == source_db:  # pragma: no cover - uuid makes this impossible
        raise SystemExit("refusing to restore over the source database")

    report: dict[str, Any] = {
        "sourceDatabase": source_db,
        "targetDatabase": target_db,
        "startedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
    }

    # Everything measured against the source is captured before the restore, so
    # a drill cannot accidentally compare the restore to itself.
    report["sourceCounts"] = _table_counts(args.source)
    report["sourceDigests"] = _content_digest(args.source)
    report["sourcePrivileges"] = _privileges(args.source)
    source_fencing = _fencing_state(args.source)
    report["sourceFencing"] = source_fencing

    dump_started = time.monotonic()
    if args.from_backup:
        # Restoring a backup taken earlier is what a real recovery does, and it
        # is the only way the fencing check can fail. A drill that dumps and
        # immediately restores always finds the sequence where it left it, so it
        # can only ever pass — which makes it a check that proves nothing.
        backup_path = Path(args.from_backup)
        backup_bytes = backup_path.read_bytes()
        backup_taken_at = dt.datetime.fromtimestamp(
            backup_path.stat().st_mtime, dt.timezone.utc
        )
        report["backupSource"] = str(backup_path)
        report["backupTakenAt"] = backup_taken_at.isoformat()
        report["dumpSeconds"] = 0.0
        report["backupBytes"] = len(backup_bytes)
        report["backupSha256"] = hashlib.sha256(backup_bytes).hexdigest()
        return _restore_and_verify(
            pg, args, report, backup_bytes, backup_taken_at, source_fencing, target_db
        )

    dump_dsn = args.container_dsn or args.source
    dumped = pg.run("pg_dump", ["--format=custom", "--dbname", dump_dsn])
    if dumped.returncode != 0:
        # The reason is shown. A drill that reports "backup failed" without
        # saying why sends someone to investigate their backups when the actual
        # problem was a host name — which is what happened the first time this
        # ran, and is the same suppression I criticised in another tool.
        raise SystemExit(
            "pg_dump failed, so there is no backup to restore:\n"
            + _redacted(dumped.stderr.decode("utf-8", "replace").strip())
        )
    backup_bytes = dumped.stdout
    report["backupBytes"] = len(backup_bytes)
    report["backupSha256"] = hashlib.sha256(backup_bytes).hexdigest()
    report["dumpSeconds"] = round(time.monotonic() - dump_started, 3)
    backup_taken_at = dt.datetime.now(dt.timezone.utc)
    if args.save_backup:
        Path(args.save_backup).write_bytes(backup_bytes)
        report["backupSource"] = args.save_backup

    return _restore_and_verify(
        pg, args, report, backup_bytes, backup_taken_at, source_fencing, target_db
    )


def _restore_and_verify(
    pg, args, report, backup_bytes, backup_taken_at, source_fencing, target_db
):
    """Restore into a database this tool created, then check what came back.

    Separated so the fresh-dump path and the restore-an-older-backup path cannot
    verify differently. The second is the one a real recovery resembles.
    """
    from psycopg import sql
    from psycopg.conninfo import make_conninfo

    with _conn(args.admin) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(target_db)))

    target_dsn = make_conninfo(args.admin, dbname=target_db)
    try:
        # RTO is measured from the moment the restore begins to the moment the
        # restored database is verified — not to the moment pg_restore returns,
        # which is before anybody knows whether it worked.
        restore_started = time.monotonic()
        restore_target = (
            make_conninfo(args.container_dsn, dbname=target_db)
            if args.container_dsn
            else target_dsn
        )
        restored = pg.run(
            "pg_restore",
            # Privileges are restored, not discarded. The first version of
            # this passed --no-privileges and then reported "integrity
            # verified" over a database with none of the carefully scoped
            # grants — inv_kernel able to touch nothing, inv_app able to
            # touch everything the owner can. A restore that loses the
            # authorisation model has not restored the system.
            ["--no-owner", "--dbname", restore_target],
            stdin=backup_bytes,
        )
        if restored.returncode != 0:
            report["restoreStderr"] = _redacted(
                restored.stderr.decode("utf-8", "replace").strip()
            )[-2000:]
        # pg_restore reports non-zero for ignorable ownership notices; the
        # verification below is what decides, not this code.
        report["restoreExitCode"] = restored.returncode

        target_counts = _table_counts(target_dsn)
        target_digests = _content_digest(target_dsn)
        target_privileges = _privileges(target_dsn)
        measured_rto = round(time.monotonic() - restore_started, 3)

        report["targetCounts"] = target_counts
        report["targetDigests"] = target_digests
        report["measuredRtoSeconds"] = measured_rto
        report["measuredRpoSeconds"] = round(
            (dt.datetime.now(dt.timezone.utc) - backup_taken_at).total_seconds(), 3
        )

        missing = sorted(
            t for t, n in target_counts.items()
            if n != report["sourceCounts"].get(t)
        )
        differing = sorted(
            t for t, d in target_digests.items()
            if d != report["sourceDigests"].get(t)
        )
        privileges_match = (
            target_privileges["table"] == report["sourcePrivileges"]["table"]
            and target_privileges["column"]
            == report["sourcePrivileges"]["column"]
        )
        report["targetPrivileges"] = target_privileges
        report["privilegesRestored"] = privileges_match
        report["tablesWithDifferentCounts"] = missing
        report["tablesWithDifferentContent"] = differing
        # Privileges count toward integrity. A database with every row and no
        # grants is one the runtime cannot connect to at all, because it refuses
        # to run as the owner — so losing them loses the only role it accepts.
        report["integrityVerified"] = (
            not missing and not differing and privileges_match
        )

        # ERR-DESIGN-006. The restored sequence must not issue a token a live
        # node already holds.
        target_fencing = _fencing_state(target_dsn)
        report["targetFencing"] = target_fencing
        safe_floor = max(
            source_fencing["sequenceLastValue"], source_fencing["highestHeldToken"]
        )
        advance = max(0, safe_floor - target_fencing["sequenceLastValue"])
        report["fencingAdvanceRequired"] = advance
        report["fencingVerified"] = advance == 0
        report["fencingNote"] = (
            "the restored sequence is at or above every token the source had "
            "issued or leased"
            if advance == 0
            else (
                f"the restored sequence would reissue tokens a live node may "
                f"hold; advance inv.fencing_token_seq by {advance} before "
                f"accepting any command"
            )
        )
        return report
    finally:
        if not args.keep:
            with _conn(args.admin) as conn:
                # Only the database this tool created is eligible.
                assert target_db.startswith("inv_drill_") and len(target_db) == 42
                conn.execute(
                    sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                        sql.Identifier(target_db)
                    )
                )
        else:
            report["keptDatabase"] = target_db


def record(report: dict[str, Any], args) -> str | None:
    """Write the drill row, through the service that computes met_targets.

    The outcome is derived from the verification rather than passed in, so a
    drill cannot be recorded as a pass because whoever ran it believed it
    worked.
    """
    import uuid as _uuid

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from saintvision.db.session import tenant_scope
    from saintvision.services import pilot as pilot_service

    passed = report["integrityVerified"] and report["fencingVerified"]
    engine = create_engine(args.record_dsn or args.source, future=True)
    factory = sessionmaker(engine, future=True, expire_on_commit=False)
    now = dt.datetime.now(dt.timezone.utc)
    tenant = _uuid.UUID(args.tenant)

    measurement = pilot_service.DrillMeasurement(
        measured_rpo_seconds=int(report["measuredRpoSeconds"]),
        measured_rto_seconds=int(report["measuredRtoSeconds"]),
    )
    with factory() as session:
        with session.begin():
            with tenant_scope(session, tenant):
                drill = pilot_service.record_recovery_drill(
                    session,
                    tenant_id=tenant,
                    scope="database",
                    outcome="passed" if passed else "failed",
                    performed_by_user_id=args.user,
                    now=now,
                    measurement=measurement if passed else None,
                    fencing_verified=report["fencingVerified"],
                    fencing_note=report["fencingNote"],
                    integrity_verified=report["integrityVerified"],
                    notes={
                        "backupSha256": report["backupSha256"],
                        "backupBytes": report["backupBytes"],
                        "tablesWithDifferentCounts": report["tablesWithDifferentCounts"],
                        "tablesWithDifferentContent": report["tablesWithDifferentContent"],
                        "fencingAdvanceRequired": report["fencingAdvanceRequired"],
                    },
                )
                return drill.drill_id
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="the live database DSN")
    parser.add_argument("--admin", required=True, help="DSN able to CREATE DATABASE")
    parser.add_argument("--tenant", help="tenant to record the drill under")
    parser.add_argument("--user", help="who performed it")
    parser.add_argument("--record-dsn", help="where to write the drill row")
    parser.add_argument("--docker", help="container holding the client tools")
    parser.add_argument(
        "--container-dsn",
        help=(
            "the same database as seen from inside the container. Needed "
            "because a host port mapping does not exist in the container's "
            "network namespace, and the first run of this tool failed for "
            "exactly that reason."
        ),
    )
    parser.add_argument(
        "--from-backup",
        help=(
            "restore a backup file taken earlier instead of dumping now. This "
            "is what a real recovery does, and the only way the fencing check "
            "can fail: a dump-then-restore always finds the sequence where it "
            "left it."
        ),
    )
    parser.add_argument("--save-backup", help="write the dump to this path")
    parser.add_argument("--keep", action="store_true", help="do not drop the restore")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = rehearse(args)

    if args.tenant and args.user:
        report["drillId"] = record(report, args)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report["integrityVerified"] and report["fencingVerified"] else 1

    print(f"backup        {report['backupBytes']} bytes, sha256 {report['backupSha256'][:16]}…")
    print(f"restore RTO   {report['measuredRtoSeconds']}s")
    print(f"integrity     {'verified' if report['integrityVerified'] else 'FAILED'}")
    print(
        f"privileges    "
        f"{'restored' if report['privilegesRestored'] else 'LOST'}"
        f"  ({report['targetPrivileges']['tableGrantCount']} table, "
        f"{report['targetPrivileges']['columnGrantCount']} column"
        f" vs {report['sourcePrivileges']['tableGrantCount']}/"
        f"{report['sourcePrivileges']['columnGrantCount']} at source)"
    )
    for table in report["tablesWithDifferentCounts"]:
        print(f"                count differs: {table}")
    for table in report["tablesWithDifferentContent"]:
        print(f"                content differs: {table}")
    print(f"fencing       {'safe' if report['fencingVerified'] else 'UNSAFE'}")
    print(f"                {report['fencingNote']}")
    if report.get("drillId"):
        print(f"recorded      {report['drillId']}")
    return 0 if report["integrityVerified"] and report["fencingVerified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
