"""Rehearse a trusted PostgreSQL backup in a newly created disposable database.

Continues Claude's dee31e5 recovery tool with the canonical ADR-072 definer
policy. Compare public/inv table inventory and counts, the nine evidence table
digests, ownership/grants/RLS, restricted role probes and observed token ordering.
All required observations must succeed; process errors and unknown measurements
cannot pass. RPO is backup age when restoration starts; RTO ends after all checks.
The source must be quiescent for these comparisons. This is not a PITR or live
write consistency test and does not prove independent-cluster role restoration,
HTTP login, object storage, Node journal/epoch reconciliation or operational
resumption. The report explicitly retains those limitations.

Use only a trusted archive and an isolated rehearsal cluster with pre-provisioned
roles: restoring a dump executes SQL with the restoring administrator's rights.
Prefer INV_RECOVERY_SOURCE_DSN / INV_RECOVERY_ADMIN_DSN over command-line secrets.
The tool creates a unique inv_drill_* database and cleans up only that database.
--keep preserves it for inspection. No scheduling gate or Node state is changed.

Usage: python tools/recovery_drill.py --json [--docker CONTAINER]
Exit 0: database rehearsal passed; 1: rejected; 2: observation unavailable.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import stat
from contextlib import contextmanager
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "services/control-plane/src"))

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
        from psycopg.conninfo import conninfo_to_dict, make_conninfo

        args = list(args)
        environment = dict(os.environ)
        password = None
        if "--dbname" in args:
            index = args.index("--dbname") + 1
            info = conninfo_to_dict(args[index])
            if "sslpassword" in info:
                raise ValueError("Use a protected client key provider, not sslpassword in a DSN")
            password = info.pop("password", None)
            args[index] = make_conninfo(**info)
        if password is not None:
            environment["PGPASSWORD"] = password
        argv = self._argv(program, args)
        if self.container and password is not None:
            # Docker reads this variable from the client's environment; its
            # value is never part of process argv or public diagnostics.
            argv = ["docker", "exec", "-i", "--env", "PGPASSWORD", self.container, program, *args]
        return subprocess.run(
            argv,
            input=stdin,
            env=environment,
            capture_output=True,
            timeout=1800,
        )


def _conn(dsn: str):
    import psycopg

    return psycopg.connect(dsn, autocommit=True, connect_timeout=5)


def _table_counts(dsn: str) -> dict[str, int]:
    """Every table in both schemas, discovered rather than listed.

    The first version counted only the tables the business models declare, which
    is a minority of the system: the execution kernel's ``inv`` schema holds the
    runs, leases, evidence and receipts a restore mostly exists to bring back.
    Reading the catalogue means a table added by either half is counted the day
    it appears.
    """
    from psycopg import sql

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
                    sql.SQL("SELECT count(*) FROM {}.{}").format(
                        sql.Identifier(schema), sql.Identifier(table)
                    )
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
            "SELECT table_schema, table_name, grantor, grantee, privilege_type, is_grantable "
            "FROM information_schema.role_table_grants "
            "WHERE table_schema IN ('public','inv') "
            "ORDER BY 1,2,3,4,5,6"
        ).fetchall()
        column_rows = conn.execute(
            "SELECT table_schema, table_name, column_name, grantor, grantee, privilege_type, is_grantable "
            "FROM information_schema.column_privileges "
            "WHERE table_schema IN ('public','inv') "
            "ORDER BY 1,2,3,4,5,6,7"
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

    Grants alone do not describe who can see what. Enabled RLS applies to the
    non-owner runtime role; FORCE also subjects a table owner to it (superusers
    and BYPASSRLS still bypass it). Compare flags and owners as well as policies.
    Cluster roles are observed, not recreated by this database-only dump.

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
            "SELECT n.nspname, c.relname, c.relrowsecurity, c.relforcerowsecurity, "
            "pg_catalog.pg_get_userbyid(c.relowner) "
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
    return {
        "checked": len(findings),
        "unsafe": len(unsafe),
        "functions": unsafe,
        "status": "requires_review" if unsafe else "matches_reviewed_policy",
        "policy": "tools/definer-policy.json",
    }


def _service_resumption(dsn: str, app_role: str, kernel_role: str) -> dict[str, Any]:
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
    from psycopg import sql

    result: dict[str, Any] = {
        "appRole": app_role,
        "kernelRole": kernel_role,
        "scope": "database_role_probes",
    }
    probes = (
        ("publicRead", app_role, "SELECT count(*) FROM public.projects"),
        ("kernelRead", kernel_role, "SELECT count(*) FROM inv.runs"),
    )
    try:
        with _conn(dsn) as conn:
            for key, role, sql_text in probes:
                with conn.transaction():
                    conn.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role)))
                    conn.execute(
                        "SELECT set_config('inv.tenant_id', %s, true)",
                        (str(uuid.UUID(int=0)),),
                    )
                    conn.execute(sql_text).fetchone()
                    bypasses = conn.execute(
                        "SELECT rolsuper OR rolbypassrls FROM pg_catalog.pg_roles "
                        "WHERE rolname = current_user"
                    ).fetchone()[0]
                    # A role that bypasses RLS is not a working service, it is a
                    # tenant boundary that is not there.
                    result[key] = not bypasses
                    result[f"{key}Bypasses"] = bool(bypasses)
    except Exception as error:
        result["error"] = type(error).__name__
        result["resumed"] = False
        return result

    result.update(_rls_scopes(dsn, app_role, kernel_role))
    result["resumed"] = bool(
        result.get("publicRead") and result.get("kernelRead") and result.get("rlsScopes")
    )
    return result


def _rls_scopes(dsn: str, app_role: str, kernel_role: str) -> dict[str, Any]:
    """Seed two tenants, read under one scope, require the other to be unseen.

    Always rolled back. A restored database that returns both rows has policies
    and no isolation, which every other check in this drill would call verified.
    """
    from psycopg import sql
    from inv.ids import new_id

    mine, theirs = uuid.uuid4(), uuid.uuid4()
    projects = (new_id("prj"), new_id("prj"))
    result: dict[str, Any] = {}
    try:
        with _conn(dsn) as conn:
            with conn.transaction(force_rollback=True):
                for tenant, project in zip((mine, theirs), projects):
                    conn.execute(
                        "INSERT INTO public.tenants "
                        "(tenant_id, slug, display_name) VALUES (%s, %s, %s)",
                        (tenant, f"recovery-{tenant.hex}", "recovery drill"),
                    )
                    conn.execute(
                        "INSERT INTO public.projects "
                        "(project_id, tenant_id, code, display_name) "
                        "VALUES (%s, %s, %s, %s)",
                        (
                            project,
                            tenant,
                            f"drill-{tenant.hex}",
                            "recovery drill",
                        ),
                    )
                    conn.execute(
                        "INSERT INTO inv.tenants VALUES (%s,%s)", (tenant, "recovery drill")
                    )
                    conn.execute("INSERT INTO inv.projects VALUES (%s,%s)", (tenant, project))
                for key, role, schema in (
                    ("public", app_role, "public"),
                    ("kernel", kernel_role, "inv"),
                ):
                    with conn.transaction(force_rollback=True):
                        conn.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role)))
                        query = sql.SQL(
                            "SELECT tenant_id FROM {}.projects WHERE project_id=ANY(%s)"
                        ).format(sql.Identifier(schema))
                        scoped = []
                        for scope, expected in (
                            (str(mine), [mine]),
                            (str(theirs), [theirs]),
                            ("", []),
                        ):
                            conn.execute("SELECT set_config('inv.tenant_id', %s, true)", (scope,))
                            visible = [
                                r[0] for r in conn.execute(query, (list(projects),)).fetchall()
                            ]
                            scoped.append(visible == expected)
                        result[key + "RlsScopes"] = all(scoped)
    except Exception as error:
        return {
            "rlsScopes": False,
            "rlsError": type(error).__name__,
        }
    return {
        **result,
        "rlsScopes": all(result.get(k) is True for k in ("publicRlsScopes", "kernelRlsScopes")),
    }


def rpo_bound_from(settings: dict[str, Any]) -> tuple[bool, None, str]:
    """Configuration evidence alone never establishes a recoverable RPO bound.

    Continues Claude 4b09dfc's distinction between a drill measurement and an
    operating objective, without treating a WAL segment switch as delivery.
    Even a successful archive command may be /bin/true or lose its destination.
    """
    configured = settings.get("archive_mode") in ("on", "always") and any(
        isinstance(settings.get(key), str)
        and settings[key].strip() not in ("", "(disabled)", "not configured")
        for key in ("archive_command", "archive_library")
    )
    return (
        configured,
        None,
        (
            "archiving configuration observed; segment switching does not prove durable "
            "WAL delivery, retained base backup/WAL continuity, or successful point-in-time "
            "recovery; operational RPO is not established"
            if configured
            else "continuous archiving is not configured; backup schedule, replication and "
            "recoverable copies were not verified; operational RPO is not established"
        ),
    )


def _recovery_capability(dsn: str) -> dict[str, Any]:
    # Never retrieve archive shell/library text: it may embed credentials.
    names = [
        "wal_level",
        "archive_mode",
        "archive_command",
        "archive_library",
        "archive_timeout",
        "data_checksums",
        "full_page_writes",
    ]
    with _conn(dsn) as conn:
        rows = conn.execute(
            """SELECT name, CASE WHEN name IN ('archive_command','archive_library')
                THEN CASE WHEN btrim(setting) IN ('','(disabled)')
                     THEN 'not configured' ELSE 'configured' END
                ELSE setting END
                FROM pg_settings WHERE name=ANY(%s)""",
            (names,),
        ).fetchall()
    settings = dict(rows)
    configured, bound, basis = rpo_bound_from(settings)
    timeout = settings.get("archive_timeout", "")
    return {
        "settings": settings,
        "archivingConfigured": configured,
        "archiveSwitchTimeoutSeconds": int(timeout) if timeout.isdigit() else None,
        "operationalRpoBoundSeconds": bound,
        "operationalRpoVerified": False,
        "basis": basis,
        "dataChecksumsEnabled": settings.get("data_checksums") == "on",
        "sourceCorruptionExcluded": False,
        "requiredEvidence": [
            "recoverable base backup and continuous retained WAL",
            "durable destination and failure-domain validation",
            "measured replay target and data-loss interval",
            "ongoing archive failure and lag monitoring",
        ],
    }


def _meets_operational_rpo(report: dict[str, Any], target: int | None) -> bool:
    if target is None:
        return True
    if type(target) is not int or target <= 0:
        return False
    capability = report.get("recoveryCapability") or {}
    bound = capability.get("operationalRpoBoundSeconds")
    return (
        capability.get("operationalRpoVerified") is True
        and type(bound) in (int, float)
        and math.isfinite(bound)
        and 0 <= bound <= target
    )


def _accepted(report, args):
    return (
        (not report.get("savedBackupRequested") or report.get("savedBackupIntact") is True)
        and _passed(report)
        and _meets_operational_rpo(report, getattr(args, "require_operational_rpo", None))
    )


@contextmanager
def _backup_parent(path):
    """Linux operator-owned private directory; never follow a path symlink."""
    path = Path(path)
    if (
        sys.platform != "linux"
        or not path.is_absolute()
        or ".." in path.parts
        or path.name in ("", ".")
    ):
        raise ValueError("Private absolute Linux backup path required")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open("/", flags)
    try:
        for part in path.parts[1:-1]:
            child = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = child
        info = os.fstat(fd)
        if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise ValueError("Private operator-owned backup directory required")
        yield fd, path.name
    finally:
        os.close(fd)


def _read_backup_at(parent, name):
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != os.geteuid()
            or stat.S_IMODE(before.st_mode) != 0o600
            or before.st_nlink != 1
        ):
            raise ValueError("Private single-link backup file required")
        value = stream.read()
        after = os.fstat(stream.fileno())
        named = os.stat(name, dir_fd=parent, follow_symlinks=False)
        signature = lambda s: (
            s.st_dev,
            s.st_ino,
            s.st_size,
            s.st_mtime_ns,
            s.st_ctime_ns,
            s.st_nlink,
        )
        if signature(before) != signature(after) or signature(after) != signature(named):
            raise ValueError("Backup changed during observation")
        return value, {"device": after.st_dev, "inode": after.st_ino}


def _save_backup(path, value):
    """Publish without overwriting; sync bytes and directory before verification.

    A process crash may leave a private temp/orphan file. It is never a ledger
    success, never automatically replayed, and never deletes an existing backup.
    This is a local filesystem durability observation, not off-site evidence.
    """
    with _backup_parent(path) as (parent, name):
        temp = ".inv-backup-" + uuid.uuid4().hex
        fd = os.open(
            temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent
        )
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(value)
                stream.flush()
                os.fsync(stream.fileno())
            os.link(temp, name, src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
        finally:
            os.unlink(temp, dir_fd=parent)
        os.fsync(parent)
        written, identity = _read_backup_at(parent, name)
    digest = hashlib.sha256(written).hexdigest()
    if written != value:
        raise ValueError("Saved backup differs from dump")
    return written, dict(
        savedBackupRequested=True,
        backupSource=str(path),
        savedBackupBytes=len(written),
        savedBackupSha256=digest,
        savedBackupIdentity=identity,
        savedBackupIntact=True,
        localBackupSynced=True,
        offSiteVerified=False,
    )


def _recheck_saved_backup(report):
    if not report.get("savedBackupRequested"):
        return
    try:
        with _backup_parent(report["backupSource"]) as (parent, name):
            written, identity = _read_backup_at(parent, name)
        intact = (
            identity == report["savedBackupIdentity"]
            and len(written) == report["backupBytes"]
            and hashlib.sha256(written).hexdigest() == report["backupSha256"]
            and report.get("localBackupSynced") is True
        )
    except (OSError, ValueError, KeyError):
        intact = False
    report["savedBackupIntact"] = intact


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
            ("sequenceCalled", "SELECT is_called FROM inv.fencing_token_seq"),
            (
                "sequenceIncrement",
                "SELECT seqincrement FROM pg_catalog.pg_sequence WHERE seqrelid='inv.fencing_token_seq'::regclass",
            ),
            (
                "highestHeldToken",
                "SELECT coalesce(max(fencing_token), 0) FROM inv.resource_leases "
                "WHERE released_at IS NULL",
            ),
        ):
            try:
                raw = conn.execute(sql_text).fetchone()[0]
                state[key] = bool(raw) if key == "sequenceCalled" else int(raw)
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
    if abbrev in ("UTC", "GMT", "Z"):
        return dt.timedelta(0)
    if not abbrev:
        return None
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
    from psycopg.conninfo import conninfo_to_dict

    pg = Postgres(args.docker)
    for program in ("pg_dump", "pg_restore"):
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
        "scope": "database_rehearsal",
        "operationalRecoveryVerified": False,
        "contentDigestScope": list(DIGESTED),
        "notVerified": [
            "independent_cluster_role_restore",
            "object_store_bytes",
            "node_journal_and_epoch",
            "live_service_login_and_workload",
            "concurrent_source_writes_and_PITR",
        ],
    }

    # Everything measured against the source is captured before the restore, so
    # a drill cannot accidentally compare the restore to itself.
    report["recoveryCapability"] = _recovery_capability(args.source)
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
        report["backupTakenAt"] = backup_taken_at.isoformat() if backup_taken_at else None
        report["dumpSeconds"] = 0.0
        report["backupBytes"] = len(backup_bytes)
        report["backupSha256"] = hashlib.sha256(backup_bytes).hexdigest()
        return _restore_and_verify(
            pg, args, report, backup_bytes, backup_taken_at, source_fencing, target_db
        )

    dump_dsn = args.container_dsn or args.source
    # Conservative lower bound for this dump's snapshot, never dump completion.
    backup_taken_at = dt.datetime.now(dt.timezone.utc)
    report["backupTakenAt"] = backup_taken_at.isoformat()
    dumped = pg.run("pg_dump", ["--format=custom", "--dbname", dump_dsn])
    if dumped.returncode != 0:
        # The reason is shown. A drill that reports "backup failed" without
        # saying why sends someone to investigate their backups when the actual
        # problem was a host name — which is what happened the first time this
        # ran, and is the same suppression I criticised in another tool.
        raise RuntimeError("pg_dump failed; database diagnostics suppressed")
    backup_bytes = dumped.stdout
    report["backupBytes"] = len(backup_bytes)
    report["backupSha256"] = hashlib.sha256(backup_bytes).hexdigest()
    report["dumpSeconds"] = round(time.monotonic() - dump_started, 3)
    if args.save_backup:
        backup_bytes, saved = _save_backup(args.save_backup, backup_bytes)
        report.update(saved)

    return _restore_and_verify(
        pg, args, report, backup_bytes, backup_taken_at, source_fencing, target_db
    )


def _restore_and_verify(pg, args, report, backup_bytes, backup_taken_at, source_fencing, target_db):
    """Restore into a database this tool created, then check what came back.

    Separated so the fresh-dump path and the restore-an-older-backup path cannot
    verify differently. The second is the one a real recovery resembles.
    """
    from psycopg import sql
    from psycopg.conninfo import make_conninfo

    restore_started = time.monotonic()
    recovery_started_at = dt.datetime.now(dt.timezone.utc)
    report["recoveryStartedAt"] = recovery_started_at.isoformat()
    with _conn(args.admin) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(target_db)))

    target_dsn = make_conninfo(args.admin, dbname=target_db)
    try:
        # RTO is measured from the moment the restore begins to the moment the
        # restored database is verified — not to the moment pg_restore returns,
        # which is before anybody knows whether it worked.
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
            ["--exit-on-error", "--dbname", restore_target],
            stdin=backup_bytes,
        )
        if restored.returncode != 0:
            report["restoreError"] = "pg_restore_failed"
        # A nonzero restore is never an acceptable database, even if some
        # observable rows happened to match. Ownership is preserved as well.
        report["restoreExitCode"] = restored.returncode

        target_counts = _table_counts(target_dsn)
        target_digests = _content_digest(target_dsn)
        target_privileges = _privileges(target_dsn)
        target_authorisation = _authorisation_model(target_dsn)

        report["targetCounts"] = target_counts
        report["targetDigests"] = target_digests
        report["measuredRpoSeconds"] = _recovery_point_age(backup_taken_at, recovery_started_at)
        if report["measuredRpoSeconds"] is None:
            report["rpoUnknownReason"] = "backup time absent, lacks timezone, or is in the future"

        # A table that is unreadable on both sides compares equal and would
        # otherwise pass. Absent from both is not "verified", it is "not
        # verified" — the drill has no evidence either way and must say so.
        tables = set(target_counts) | set(report["sourceCounts"])
        unreadable = sorted(
            t
            for t in tables
            if target_counts.get(t, -1) < 0 or report["sourceCounts"].get(t, -1) < 0
        )
        missing = sorted(t for t in tables if target_counts.get(t) != report["sourceCounts"].get(t))
        report["tablesUnreadable"] = unreadable
        differing = sorted(
            t
            for t, d in target_digests.items()
            if d != report["sourceDigests"].get(t) or str(d).startswith("unreadable:")
        )
        privileges_match = (
            target_privileges["table"] == report["sourcePrivileges"]["table"]
            and target_privileges["column"] == report["sourcePrivileges"]["column"]
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
        report["definerFunctionsSafe"] = definer.get("status") == "matches_reviewed_policy"

        # Restored is not the same claim as back in service.
        resumption = (
            _service_resumption(target_dsn, args.app_role, args.kernel_role)
            if restored.returncode == 0 and report["definerFunctionsSafe"]
            else {"resumed": False, "error": "restore_or_definer_verification_failed"}
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
            restored.returncode == 0
            and bool(tables)
            and not missing
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
        source_after = _fencing_state(args.source)
        report["sourceFencingAfter"] = source_after
        report.update(_fencing_verdict(source_fencing, source_after, target_fencing))
        if restored.returncode != 0:
            report["fencingVerified"] = False
        report["measuredRtoSeconds"] = time.monotonic() - restore_started
        report["verifiedAt"] = dt.datetime.now(dt.timezone.utc).isoformat()
        return report
    finally:
        if not args.keep:
            with _conn(args.admin) as conn:
                # Only the database this tool created is eligible.
                assert target_db.startswith("inv_drill_") and len(target_db) == 42
                conn.execute(
                    sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(target_db))
                )
        else:
            report["keptDatabase"] = target_db


def _recovery_point_age(backup_time, recovery_time) -> float | None:
    if backup_time is None or backup_time.tzinfo is None or backup_time.utcoffset() is None:
        return None
    age = (recovery_time - backup_time).total_seconds()
    return age if math.isfinite(age) and age >= 0 else None


def _fencing_verdict(before, after, target) -> dict[str, Any]:
    states = (before, after, target)
    keys = ("sequenceLastValue", "highestHeldToken", "sequenceIncrement")
    known = all(type(s.get(k)) is int and s[k] >= 0 for s in states for k in keys)
    known = known and all(
        type(s.get("sequenceCalled")) is bool and s["sequenceIncrement"] == 1 for s in states
    )
    if not known:
        return {
            "fencingVerified": False,
            "fencingAdvanceRequired": None,
            "fencingNote": "fencing observation unavailable or unsupported sequence increment",
        }
    floor = max(s["highestHeldToken"] for s in states)
    floor = max(
        floor,
        *(
            s["sequenceLastValue"] if s["sequenceCalled"] else s["sequenceLastValue"] - 1
            for s in (before, after)
        ),
    )
    next_value = target["sequenceLastValue"] + int(target["sequenceCalled"])
    advance = max(0, floor + 1 - next_value)
    return {
        "fencingVerified": advance == 0,
        "fencingAdvanceRequired": advance,
        "fencingObservedFloor": floor,
        "fencingNextValue": next_value,
        "fencingNote": "observed database token ordering only; Node journals and epoch remain unverified",
    }


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

    _recheck_saved_backup(report)
    functional_passed = _passed(report)
    passed = _accepted(report, args)
    from psycopg.conninfo import conninfo_to_dict
    from sqlalchemy.engine import URL

    record_dsn = args.record_dsn or args.source
    if record_dsn.startswith("postgresql+psycopg://"):
        engine = create_engine(record_dsn, future=True)
    else:
        # Avoid interpreting libpq keyword DSNs as SQLAlchemy URLs, or silently
        # picking a different DB driver for postgresql:// URLs.
        engine = create_engine(
            URL.create("postgresql+psycopg"), connect_args=conninfo_to_dict(record_dsn), future=True
        )
    factory = sessionmaker(engine, future=True, expire_on_commit=False)
    now = dt.datetime.now(dt.timezone.utc)
    tenant = _uuid.UUID(args.tenant)

    measurement = (
        pilot_service.DrillMeasurement(
            rpo_seconds=math.ceil(report["measuredRpoSeconds"]),
            rto_seconds=math.ceil(report["measuredRtoSeconds"]),
        )
        if functional_passed
        else None
    )
    try:
        with factory() as session:
            with session.begin():
                with tenant_scope(session, tenant):
                    backup = None
                    if report.get("savedBackupRequested"):
                        backup = pilot_service.record_backup(
                            session,
                            tenant_id=tenant,
                            kind="logical",
                            location_ref=report["backupSource"],
                            now=now,
                            off_site=False,
                            byte_size=report["backupBytes"],
                        )
                        if report.get("savedBackupIntact") is True:
                            pilot_service.verify_backup(
                                session,
                                tenant_id=tenant,
                                backup_id=backup.backup_id,
                                checksum_sha256=report["backupSha256"],
                                now=now,
                            )
                    drill = pilot_service.record_recovery_drill(
                        session,
                        tenant_id=tenant,
                        scope="database",
                        backup_id=backup.backup_id if backup else None,
                        outcome="passed" if passed else "failed",
                        performed_by_user_id=args.user,
                        now=now,
                        measurement=measurement,
                        fencing_verified=report["fencingVerified"],
                        fencing_note=report["fencingNote"],
                        integrity_verified=report["integrityVerified"],
                        notes={
                            "scope": report["scope"],
                            "operationalRecoveryVerified": False,
                            "functionalDrillPassed": functional_passed,
                            "requiredOperationalRpoSeconds": getattr(
                                args, "require_operational_rpo", None
                            ),
                            "operationalRpoRequirementMet": _meets_operational_rpo(
                                report, getattr(args, "require_operational_rpo", None)
                            ),
                            "operationalRpoVerified": (report.get("recoveryCapability") or {}).get(
                                "operationalRpoVerified"
                            )
                            is True,
                            "recoveryCapability": report.get("recoveryCapability"),
                            "notVerified": report["notVerified"],
                            "backupSha256": report["backupSha256"],
                            "backupBytes": report["backupBytes"],
                            "savedBackupRequested": bool(report.get("savedBackupRequested")),
                            "savedBackupIntact": report.get("savedBackupIntact"),
                            "backupVerificationScope": "local-file-observation-not-offsite-or-PITR",
                            "tablesWithDifferentCounts": report["tablesWithDifferentCounts"],
                            "tablesWithDifferentContent": report["tablesWithDifferentContent"],
                            "fencingAdvanceRequired": report["fencingAdvanceRequired"],
                        },
                    )
        # Publish identifiers only after the transaction has committed.
        if backup is not None:
            report["backupId"] = backup.backup_id
            report["backupVerified"] = backup.verified
        return drill.drill_id
    finally:
        engine.dispose()


def _passed(report: dict[str, Any]) -> bool:
    """One definition of a passing drill, used by the exit code and the record.

    Kept in one place because the two disagreed in the first version: the
    printed result said "verified" while the recorded row would have refused the
    pass for want of measurements.
    """
    values = (report.get("measuredRpoSeconds"), report.get("measuredRtoSeconds"))
    return (
        report.get("restoreExitCode") == 0
        and type(report.get("restoreExitCode")) is int
        and report.get("integrityVerified") is True
        and report.get("fencingVerified") is True
        and all(type(v) in (int, float) and math.isfinite(v) and v >= 0 for v in values)
    )


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, "Invalid recovery arguments; see --help.\n")


def _positive_seconds(value):
    result = int(value)
    if result <= 0:
        raise argparse.ArgumentTypeError("positive seconds required")
    return result


def main() -> int:
    parser = SafeParser(description=__doc__, allow_abbrev=False)
    parser.add_argument(
        "--source",
        default=os.getenv("INV_RECOVERY_SOURCE_DSN"),
        help="source DSN; prefer INV_RECOVERY_SOURCE_DSN",
    )
    parser.add_argument(
        "--admin",
        default=os.getenv("INV_RECOVERY_ADMIN_DSN"),
        help="CREATE DATABASE DSN; prefer INV_RECOVERY_ADMIN_DSN",
    )
    parser.add_argument("--tenant", help="tenant to record the drill under")
    parser.add_argument("--user", help="who performed it")
    parser.add_argument(
        "--record-dsn",
        default=os.getenv("INV_RECOVERY_RECORD_DSN"),
        help="where to write the drill row",
    )
    parser.add_argument("--docker", help="container holding the client tools")
    parser.add_argument(
        "--container-dsn",
        default=os.getenv("INV_RECOVERY_CONTAINER_DSN"),
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
    parser.add_argument(
        "--save-backup",
        help="publish a new dump in an existing private Linux directory; never overwrite",
    )
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
    parser.add_argument(
        "--require-operational-rpo",
        type=_positive_seconds,
        metavar="SECONDS",
        help="require verified operational RPO, not just a successful logical restore; current configuration-only observations cannot satisfy this gate",
    )
    parser.add_argument("--keep", action="store_true", help="do not drop the restore")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.from_backup and args.save_backup:
        parser.error("backup input and output are mutually exclusive")
    if not args.source or not args.admin or bool(args.tenant) != bool(args.user):
        print(json.dumps({"status": "unavailable", "error": "required_configuration_missing"}))
        return 2
    try:
        report = rehearse(args)
        _recheck_saved_backup(report)
        if args.tenant and args.user:
            report["drillId"] = record(report, args)
        report["acceptance"] = {
            "functionalDrillPassed": _passed(report),
            "requiredOperationalRpoSeconds": args.require_operational_rpo,
            "operationalRpoRequirementMet": (
                _meets_operational_rpo(report, args.require_operational_rpo)
                if args.require_operational_rpo is not None
                else None
            ),
            "passed": _accepted(report, args),
        }
    except Exception as error:
        # Driver/client exceptions may echo credentials, SQL or row bytes.
        print(json.dumps({"status": "unavailable", "error": type(error).__name__}))
        return 2

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if _accepted(report, args) else 1

    print(f"backup        {report['backupBytes']} bytes, sha256 {report['backupSha256'][:16]}…")
    print(f"restore RTO   {report['measuredRtoSeconds']}s")
    rpo = report.get("measuredRpoSeconds")
    print(
        f"recovery RPO  {rpo}s for this restore only"
        if rpo is not None
        else "recovery RPO  unknown"
    )
    capability = report.get("recoveryCapability") or {}
    print("operational   RPO NOT ESTABLISHED by configuration inspection")
    print(f"                {capability.get('basis')}")
    if not _meets_operational_rpo(report, args.require_operational_rpo):
        print("operational target REFUSED; restore and operational acceptance are separate")
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
        f"{'matches reviewed policy' if report.get('definerFunctionsSafe') else 'REVIEW REQUIRED'}"
        f"  ({definer.get('checked')} checked, {definer.get('unsafe')} unsafe)"
    )
    for name in definer.get("functions") or []:
        print(f"                policy mismatch: {name}")
    resumption = report.get("serviceResumption") or {}
    print(
        f"DB role probes "
        f"{'passed' if report.get('serviceResumed') else 'FAILED'}"
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
    print("scope         database rehearsal; operational recovery remains unverified")
    if report.get("drillId"):
        print(f"recorded      {report['drillId']}")
    return 0 if _accepted(report, args) else 1


if __name__ == "__main__":
    raise SystemExit(main())
