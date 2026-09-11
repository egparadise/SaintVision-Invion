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
#: Evidence-bearing tables, in both schemas. The first version listed four
#: public ones, which left out everything the kernel records — the evidence,
#: the stop receipts and the committed results a restore mostly exists to bring
#: back. A count notices a lost row; only a digest notices a changed one.
DIGESTED = (
    "public.evidence_envelopes",
    "public.run_records",
    "public.artifacts",
    "public.backup_records",
    "inv.evidence",
    "inv.checkpoints",
    "inv.node_stop_receipts",
    "inv.result_commitments",
    "inv.resource_leases",
)


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
        for qualified in DIGESTED:
            schema, table = qualified.split(".", 1)
            try:
                rows = conn.execute(
                    f'SELECT to_jsonb(t)::text FROM "{schema}"."{table}" t ORDER BY 1'
                ).fetchall()
            except Exception as error:
                # Distinguished from an empty table: "could not read" and
                # "read and found nothing" are different facts, and treating
                # them alike is how a lost table passes verification.
                digests[qualified] = f"unreadable:{type(error).__name__}"
                continue
            digest = hashlib.sha256()
            for (row,) in rows:
                digest.update(row.encode())
                digest.update(b"\n")
            digests[qualified] = digest.hexdigest()
    return digests


def _authorisation_model(dsn: str) -> dict[str, Any]:
    """Roles, memberships, RLS flags and policies — the rest of the boundary.

    Grants alone do not describe who can see what. ``inv_app`` is a non-owner
    precisely so row level security applies to it, and RLS only applies when the
    table has it **enabled and forced**: a restore that brings back the policies
    but loses ``FORCE`` leaves every policy in place and silently inapplicable to
    the owner. Losing a role membership does the same from the other direction.

    Each part is digested separately so a failure names which part moved rather
    than reporting one opaque mismatch.
    """
    parts: dict[str, Any] = {}
    queries = {
        "roles": (
            "SELECT rolname, rolsuper, rolbypassrls, rolcanlogin, rolinherit "
            "FROM pg_catalog.pg_roles WHERE rolname LIKE 'inv%' ORDER BY 1"
        ),
        "memberships": (
            "SELECT r.rolname, m.rolname, a.admin_option "
            "FROM pg_catalog.pg_auth_members a "
            "JOIN pg_catalog.pg_roles r ON r.oid = a.roleid "
            "JOIN pg_catalog.pg_roles m ON m.oid = a.member "
            "WHERE r.rolname LIKE 'inv%' OR m.rolname LIKE 'inv%' ORDER BY 1,2"
        ),
        # relrowsecurity without relforcerowsecurity is RLS that the owner walks
        # straight through, which is the shape this schema deliberately avoids.
        "rowSecurity": (
            "SELECT n.nspname, c.relname, c.relrowsecurity, c.relforcerowsecurity "
            "FROM pg_catalog.pg_class c "
            "JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname IN ('public','inv') AND c.relkind = 'r' ORDER BY 1,2"
        ),
        "policies": (
            "SELECT schemaname, tablename, policyname, permissive, roles::text, "
            "cmd, coalesce(qual,''), coalesce(with_check,'') "
            "FROM pg_catalog.pg_policies "
            "WHERE schemaname IN ('public','inv') ORDER BY 1,2,3"
        ),
    }
    with _conn(dsn) as conn:
        for key, sql_text in queries.items():
            try:
                rows = conn.execute(sql_text).fetchall()
            except Exception as error:
                # Same rule as everywhere else here: unknown is not a match.
                parts[key] = f"unreadable:{type(error).__name__}"
                parts.setdefault("counts", {})[key] = None
                continue
            parts[key] = hashlib.sha256(
                "\n".join("|".join(map(str, r)) for r in rows).encode()
            ).hexdigest()
            parts.setdefault("counts", {})[key] = len(rows)
    return parts


def _definer_verdict(dsn: str) -> dict[str, Any]:
    """Run the live definer-function audit against the restored database.

    A SECURITY DEFINER function bypasses row level security, so its *restored*
    definition is part of the isolation boundary, not a detail behind it. This
    repository has twice shipped one that read across tenants, and both fixes
    were ``CREATE OR REPLACE`` — which is exactly why the question can only be
    answered about a database, and why a restore is the right place to ask it.
    """
    try:
        from check_definer_functions import audit
    except ImportError:
        import sys as _sys

        _sys.path.insert(0, str(Path(__file__).resolve().parent))
        from check_definer_functions import audit
    try:
        findings = audit(dsn)
    except Exception as error:
        return {"checked": None, "unsafe": None, "error": type(error).__name__}
    unsafe = [f["function"] for f in findings if f["problems"]]
    return {"checked": len(findings), "unsafe": len(unsafe), "functions": unsafe}


def _service_resumption(
    dsn: str, app_role: str, kernel_role: str
) -> dict[str, Any]:
    """Can the restored database actually serve a request, and does RLS scope?

    "Restored" and "back in service" are different claims, and the drill has so
    far only supported the first. The runtime connects as a non-owner without
    BYPASSRLS, sets a transaction-local tenant scope and reads. Two roles,
    because the authorisation model has two halves and a restore can lose either
    one: ``inv_app`` holds USAGE on ``public`` and serves the request path,
    while the execution record in ``inv`` is reached through ``inv_kernel``
    membership. Checking only one would have declared the database in service
    with half its access gone.

    Then the part a grants digest cannot show: that RLS *scopes*. Two tenants
    are seeded and read back under one scope; the other tenant's row must be
    invisible, not merely covered by a policy that exists. Policies survive a
    restore that drops ``FORCE``, and such a database passes every comparison
    here while isolating nothing.

    The seed runs inside a transaction that is always rolled back, so the drill
    leaves no rows behind even under ``--keep``.
    """
    result: dict[str, Any] = {"appRole": app_role, "kernelRole": kernel_role}
    probes = (
        ("publicRead", app_role, "SELECT count(*) FROM public.projects"),
        ("kernelRead", kernel_role, "SELECT count(*) FROM inv.runs"),
    )
    try:
        with _conn(dsn) as conn:
            for key, role, sql_text in probes:
                with conn.transaction():
                    conn.execute(f'SET LOCAL ROLE "{role}"')
                    conn.execute(
                        "SELECT set_config('inv.tenant_id', %s, true)",
                        (str(uuid.UUID(int=0)),),
                    )
                    conn.execute(sql_text).fetchone()
                    bypasses = conn.execute(
                        "SELECT rolbypassrls FROM pg_roles "
                        "WHERE rolname = current_user"
                    ).fetchone()[0]
                    # A role that bypasses RLS is not a working service, it is a
                    # tenant boundary that is not there.
                    result[key] = not bypasses
                    result[f"{key}Bypasses"] = bool(bypasses)
    except Exception as error:
        result["error"] = f"{type(error).__name__}: {str(error).strip()[:200]}"
        result["resumed"] = False
        return result

    result.update(_rls_scopes(dsn, app_role))
    result["resumed"] = bool(
        result.get("publicRead")
        and result.get("kernelRead")
        and result.get("rlsScopes")
    )
    return result


def _rls_scopes(dsn: str, app_role: str) -> dict[str, Any]:
    """Seed two tenants, read under one scope, require the other to be unseen.

    Always rolled back. A restored database that returns both rows has policies
    and no isolation, which every other check in this drill would call verified.
    """
    mine = uuid.UUID("00000000-0000-0000-0000-00000000d21e")
    theirs = uuid.UUID("00000000-0000-0000-0000-00000000d21f")
    try:
        with _conn(dsn) as conn:
            transaction = conn.transaction()
            transaction.__enter__()
            try:
                for tenant, slug in ((mine, "drill-a"), (theirs, "drill-b")):
                    conn.execute(
                        "INSERT INTO public.tenants "
                        "(tenant_id, slug, display_name) VALUES (%s, %s, %s)",
                        (tenant, f"recovery-{slug}", f"recovery drill {slug}"),
                    )
                    conn.execute(
                        "INSERT INTO public.projects "
                        "(project_id, tenant_id, code, display_name) "
                        "VALUES (%s, %s, %s, %s)",
                        (
                            f"prj_drill_{slug}",
                            tenant,
                            f"drill-{slug}",
                            "recovery drill",
                        ),
                    )
                conn.execute(f'SET LOCAL ROLE "{app_role}"')
                conn.execute(
                    "SELECT set_config('inv.tenant_id', %s, true)", (str(mine),)
                )
                visible = [
                    row[0]
                    for row in conn.execute(
                        "SELECT tenant_id FROM public.projects "
                        "WHERE project_id LIKE 'prj_drill_%'"
                    ).fetchall()
                ]
            finally:
                # Never commit. The drill is a measurement, not a writer.
                transaction.__exit__(Exception, Exception("rollback"), None)
    except Exception as error:
        return {
            "rlsScopes": False,
            "rlsError": f"{type(error).__name__}: {str(error).strip()[:200]}",
        }
    return {
        "rlsScopes": visible == [mine],
        "rlsVisibleTenants": [str(t) for t in visible],
    }


def _fencing_state(dsn: str) -> dict[str, Any]:
    """The highest token issued, and the highest one a lease still holds.

    A failed query is ``None``, never ``0``. The first version swallowed the
    exception and returned zero, which is the worst possible answer here: a
    permission error or a missing table made both sides read 0, the required
    advance computed to 0, and the drill reported "fencing safe" — a false pass
    on the single check that decides whether a restore can be accepted at all.

    Not knowing is a result. It is reported as one, and it blocks the pass.
    """
    state: dict[str, Any] = {}
    with _conn(dsn) as conn:
        for key, sql_text in (
            ("sequenceLastValue", "SELECT last_value FROM inv.fencing_token_seq"),
            (
                "highestHeldToken",
                "SELECT coalesce(max(fencing_token), 0) FROM inv.resource_leases "
                "WHERE released_at IS NULL",
            ),
        ):
            try:
                state[key] = int(conn.execute(sql_text).fetchone()[0])
            except Exception as error:
                state[key] = None
                state.setdefault("errors", {})[key] = type(error).__name__
    return state


def _archive_taken_at(pg, backup_path: Path, args):
    """When the dump was actually taken, from the archive's own header.

    ``pg_restore --list`` prints the archive's creation time. That is the moment
    the backup represents; a file's mtime is the moment it was last written,
    which a copy resets. An RPO computed from mtime measures the filesystem, not
    the recovery point.

    An explicit ``--backup-taken-at`` wins, because an operator restoring from a
    media catalogue knows better than either.
    """
    if getattr(args, "backup_taken_at", None):
        return dt.datetime.fromisoformat(args.backup_taken_at)
    listed = pg.run("pg_restore", ["--list"], stdin=backup_path.read_bytes())
    if listed.returncode != 0:
        return None
    for line in listed.stdout.decode("utf-8", "replace").splitlines():
        if "Archive created at" not in line:
            continue
        stamp = line.split("Archive created at", 1)[1].strip()
        # pg_restore ends the line with the *server's local* zone abbreviation
        # ("... 08:53:45 UTC", "... 17:53:45 KST"). Assuming UTC would put the
        # recovery point hours off in either direction, so the abbreviation is
        # resolved against the database rather than guessed.
        head, _, zone = stamp.rpartition(" ")
        if not zone.isalpha():
            head, zone = stamp, ""
        for fmt in ("%a %b %d %H:%M:%S %Y", "%Y-%m-%d %H:%M:%S"):
            try:
                naive = dt.datetime.strptime(head.strip(), fmt)
            except ValueError:
                continue
            offset = _zone_offset(zone, args)
            if offset is None:
                return None
            return (naive - offset).replace(tzinfo=dt.timezone.utc)
    return None


def _zone_offset(abbrev: str, args) -> dt.timedelta | None:
    """The UTC offset of a zone abbreviation, from Postgres' own table.

    Returns ``None`` for an abbreviation Postgres does not know rather than
    falling back to UTC: a silently wrong offset is a recovery point reported
    hours from the truth, which is worse than reporting none.
    """
    if abbrev in ("", "UTC", "GMT", "Z"):
        return dt.timedelta(0)
    try:
        import psycopg

        with psycopg.connect(args.admin) as conn:
            row = conn.execute(
                "SELECT utc_offset FROM pg_timezone_abbrevs WHERE abbrev = %s",
                (abbrev,),
            ).fetchone()
    except Exception:
        return None
    return row[0] if row else None


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
    report["sourceAuthorisation"] = _authorisation_model(args.source)
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
        # mtime is when the file was last written — copying or moving it resets
        # that, and an RPO computed from it is a measurement of the filesystem.
        # A custom-format dump records when it was actually taken; that is read
        # from the archive, and when it cannot be, RPO is unknown rather than
        # invented.
        backup_taken_at = _archive_taken_at(pg, backup_path, args)
        if backup_taken_at is None:
            report["rpoUnknownReason"] = (
                "the archive does not state when it was taken and file mtime is "
                "not that time; pass --backup-taken-at to measure RPO"
            )
        report["backupSource"] = str(backup_path)
        report["backupTakenAt"] = (
            backup_taken_at.isoformat() if backup_taken_at else None
        )
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
        target_authorisation = _authorisation_model(target_dsn)
        measured_rto = round(time.monotonic() - restore_started, 3)

        report["targetCounts"] = target_counts
        report["targetDigests"] = target_digests
        report["measuredRtoSeconds"] = measured_rto
        report["measuredRpoSeconds"] = (
            round(
                (dt.datetime.now(dt.timezone.utc) - backup_taken_at).total_seconds(),
                3,
            )
            if backup_taken_at is not None
            else None
        )

        # A table that is unreadable on both sides compares equal and would
        # otherwise pass. Absent from both is not "verified", it is "not
        # verified" — the drill has no evidence either way and must say so.
        unreadable = sorted(
            t for t, n in target_counts.items()
            if n == -1 or report["sourceCounts"].get(t) == -1
        )
        missing = sorted(
            t for t, n in target_counts.items()
            if n != report["sourceCounts"].get(t)
        )
        report["tablesUnreadable"] = unreadable
        differing = sorted(
            t for t, d in target_digests.items()
            if d != report["sourceDigests"].get(t)
            or str(d).startswith("unreadable:")
        )
        privileges_match = (
            target_privileges["table"] == report["sourcePrivileges"]["table"]
            and target_privileges["column"]
            == report["sourcePrivileges"]["column"]
        )
        report["targetPrivileges"] = target_privileges

        # Roles, memberships, RLS enable/force and policies. Compared part by
        # part so a failure says which part moved.
        source_auth = report["sourceAuthorisation"]
        authorisation_moved = sorted(
            part
            for part in ("roles", "memberships", "rowSecurity", "policies")
            if target_authorisation.get(part) != source_auth.get(part)
            or str(target_authorisation.get(part)).startswith("unreadable:")
        )
        report["targetAuthorisation"] = target_authorisation
        report["authorisationChanged"] = authorisation_moved
        report["authorisationRestored"] = not authorisation_moved

        # The restored definitions of every SECURITY DEFINER function, which
        # bypass RLS and are therefore part of the boundary being restored.
        definer = _definer_verdict(target_dsn)
        report["definerFunctions"] = definer
        report["definerFunctionsSafe"] = definer.get("unsafe") == 0

        # Restored is not the same claim as back in service.
        resumption = _service_resumption(
            target_dsn, args.app_role, args.kernel_role
        )
        report["serviceResumption"] = resumption
        report["serviceResumed"] = bool(resumption.get("resumed"))

        report["privilegesRestored"] = privileges_match
        report["tablesWithDifferentCounts"] = missing
        report["tablesWithDifferentContent"] = differing
        # Privileges count toward integrity. A database with every row and no
        # grants is one the runtime cannot connect to at all, because it refuses
        # to run as the owner — so losing them loses the only role it accepts.
        report["integrityVerified"] = (
            not missing
            and not differing
            and not unreadable
            and privileges_match
            and not authorisation_moved
            and report["definerFunctionsSafe"]
            and report["serviceResumed"]
        )

        # ERR-DESIGN-006. The restored sequence must not issue a token a live
        # node already holds.
        target_fencing = _fencing_state(target_dsn)
        report["targetFencing"] = target_fencing
        values = (
            source_fencing.get("sequenceLastValue"),
            source_fencing.get("highestHeldToken"),
            target_fencing.get("sequenceLastValue"),
        )
        if any(v is None for v in values):
            # Unknown is not safe. A drill that could not read the sequence has
            # not shown the restore is acceptable, and saying "safe" because the
            # query failed is the failure mode this check exists to prevent.
            report["fencingAdvanceRequired"] = None
            report["fencingVerified"] = False
            report["fencingNote"] = (
                "the fencing state could not be read on one or both sides "
                f"({source_fencing.get('errors') or target_fencing.get('errors')}); "
                "a restore whose token ordering is unknown has not been shown "
                "to be safe"
            )
        else:
            safe_floor = max(
                source_fencing["sequenceLastValue"],
                source_fencing["highestHeldToken"],
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

    passed = _passed(report)
    engine = create_engine(args.record_dsn or args.source, future=True)
    factory = sessionmaker(engine, future=True, expire_on_commit=False)
    now = dt.datetime.now(dt.timezone.utc)
    tenant = _uuid.UUID(args.tenant)

    measurement = (
        pilot_service.DrillMeasurement(
            measured_rpo_seconds=int(report["measuredRpoSeconds"]),
            measured_rto_seconds=int(report["measuredRtoSeconds"]),
        )
        if passed
        else None
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
                    measurement=measurement,
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


def _passed(report: dict[str, Any]) -> bool:
    """One definition of a passing drill, used by the exit code and the record.

    Kept in one place because the two disagreed in the first version: the
    printed result said "verified" while the recorded row would have refused the
    pass for want of measurements.
    """
    return bool(
        report.get("integrityVerified")
        and report.get("fencingVerified")
        and report.get("measuredRpoSeconds") is not None
        and report.get("measuredRtoSeconds") is not None
    )


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
    parser.add_argument(
        "--backup-taken-at",
        help=(
            "ISO timestamp the backup represents. Overrides the archive header; "
            "an operator restoring from a media catalogue knows this better "
            "than the file does."
        ),
    )
    parser.add_argument(
        "--app-role",
        default="inv_app",
        help=(
            "the non-owner role the runtime connects as; the drill sets it and "
            "performs the read a request performs, because a database that "
            "cannot serve one has not been recovered"
        ),
    )
    parser.add_argument(
        "--kernel-role",
        default="inv_kernel",
        help=(
            "the role with access to the execution record in inv; the runtime "
            "reaches it through membership, so a restore can lose this half of "
            "the model while the request path still works"
        ),
    )
    parser.add_argument("--keep", action="store_true", help="do not drop the restore")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = rehearse(args)

    if args.tenant and args.user:
        report["drillId"] = record(report, args)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if _passed(report) else 1

    print(f"backup        {report['backupBytes']} bytes, sha256 {report['backupSha256'][:16]}…")
    print(f"restore RTO   {report['measuredRtoSeconds']}s")
    rpo = report.get("measuredRpoSeconds")
    print(f"recovery RPO  {rpo}s" if rpo is not None else "recovery RPO  unknown")
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
    for table in report.get("tablesUnreadable", []):
        print(f"                unreadable (not verified either way): {table}")
    auth = report.get("sourceAuthorisation", {}).get("counts") or {}
    print(
        f"authorisation "
        f"{'restored' if report.get('authorisationRestored') else 'CHANGED'}"
        f"  ({auth.get('roles')} roles, {auth.get('memberships')} memberships, "
        f"{auth.get('policies')} policies, {auth.get('rowSecurity')} tables' RLS flags)"
    )
    for part in report.get("authorisationChanged", []):
        print(f"                differs: {part}")
    definer = report.get("definerFunctions") or {}
    print(
        f"definer fns   "
        f"{'bound to tenant scope' if report.get('definerFunctionsSafe') else 'UNSAFE'}"
        f"  ({definer.get('checked')} checked, {definer.get('unsafe')} unsafe)"
    )
    for name in definer.get("functions") or []:
        print(f"                bypasses RLS without binding the scope: {name}")
    resumption = report.get("serviceResumption") or {}
    print(
        f"service       "
        f"{'resumed' if report.get('serviceResumed') else 'NOT RESUMED'}"
        f"  (public as {resumption.get('appRole')}, "
        f"inv as {resumption.get('kernelRole')}, "
        f"RLS scopes={resumption.get('rlsScopes')})"
    )
    for note in (resumption.get("error"), resumption.get("rlsError")):
        if note:
            print(f"                {note}")
    if resumption.get("rlsScopes") is False and resumption.get("rlsVisibleTenants"):
        print(
            "                another tenant's row was visible under this scope: "
            f"{resumption['rlsVisibleTenants']}"
        )
    print(f"fencing       {'safe' if report['fencingVerified'] else 'UNSAFE'}")
    print(f"                {report['fencingNote']}")
    if report.get("drillId"):
        print(f"recorded      {report['drillId']}")
    return 0 if _passed(report) else 1


if __name__ == "__main__":
    raise SystemExit(main())
