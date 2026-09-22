"""Collect API<->PostgreSQL authentication and RLS boundary evidence (S02-DB).

For every measured database role (``inv_app``, ``inv_kernel``, ... via ``SET ROLE``
from an owner/superuser connection) this tool records, against the live catalogue
and live rows:

* role attributes (superuser / bypassrls / login / memberships);
* per table (schemas ``public`` and ``inv``): table and column privileges, RLS
  enabled/forced flags, the policies that apply to the role, and the number of
  rows the role can actually see (a) with ``inv.tenant_id`` unset, (b) set to a
  real tenant, (c) set to a random tenant, (d) set to a non-UUID value -- each
  compared with the superuser ground truth (total rows, rows of that tenant,
  rows of other tenants);
* per SECURITY DEFINER function: owner, search_path configuration and EXECUTE
  grants per role.

Nothing is written to the measured database: every probe runs inside a
transaction that is rolled back.  Outputs are one JSON and one Markdown file
under ``--out-dir`` and never contain the DSN, passwords or credential values.

Expectations (violations -> exit 1; reviewed exceptions live in tools/rls-boundary-baseline.json
and are reported under 'accepted'):
  E1 a measured role is neither SUPERUSER nor BYPASSRLS;
  E2 a tenant-scoped table (has ``tenant_id``) the role can read is RLS enabled
     AND forced;
  E3 with the GUC unset the role sees 0 rows of every tenant-scoped table (or is
     denied);
  E4 with the GUC set to tenant A the role sees exactly the owner's tenant-A row
     SET -- judged by ROW IDENTITY, never by count or by a value projection:
     inside one REPEATABLE READ transaction the owner fingerprints tenant A's rows
     and the role fingerprints what it sees.  Identity is ``ctid`` when the role
     can read it, otherwise ``tenant_id`` + the complete primary key when the role
     can read all of them.  A different set (count inflation OR a same-count row
     swap) is an E4 violation.  When neither identity is readable the table is
     "identity unverifiable": it is reported under ``unmeasured`` and the verdict
     becomes UNMEASURED (exit 3) -- never PASS -- unless the baseline accepts that
     (role, table) with a reason;
  E5 with the GUC set to an unknown tenant the role sees 0 rows;
  E6 no SECURITY DEFINER function grants EXECUTE to PUBLIC.

Rerun (values not recorded here):
  INV_AUDIT_DSN=<owner dsn> python tools/collect_rls_evidence.py --out-dir <dir>
  python tools/collect_rls_evidence.py --disposable --out-dir <dir>   # needs INV_TEST_ADMIN_DSN
Exit 0: PASS; 1: violations; 2: observation unavailable; 3: UNMEASURED (no violation but
at least one row identity could not be verified).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = Path(__file__).with_name("rls-boundary-baseline.json")
DEFAULT_ROLES = ("inv_app", "inv_kernel", "inv_runtime_dev", "inv_discovery_issuer", "inv_discovery_issuer_guard")
SCHEMAS = ("public", "inv")
TENANT_GUC = "inv.tenant_id"
PRIVILEGES = ("SELECT", "INSERT", "UPDATE", "DELETE")

ROLE_QUERY = """
SELECT r.rolname, r.rolsuper, r.rolbypassrls, r.rolcanlogin, r.rolinherit,
       (SELECT coalesce(array_agg(g.rolname ORDER BY g.rolname), '{}')
          FROM pg_auth_members m JOIN pg_roles g ON g.oid=m.roleid WHERE m.member=r.oid) AS member_of
FROM pg_roles r WHERE r.rolname = %s
"""

TABLE_QUERY = """
SELECT n.nspname AS schema, c.relname AS name, c.relrowsecurity, c.relforcerowsecurity,
       EXISTS (SELECT 1 FROM pg_attribute a WHERE a.attrelid=c.oid AND a.attname='tenant_id'
               AND NOT a.attisdropped) AS has_tenant_id
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE c.relkind IN ('r','p') AND n.nspname = ANY(%s)
  AND NOT EXISTS (SELECT 1 FROM pg_inherits i WHERE i.inhrelid=c.oid)
ORDER BY n.nspname, c.relname
"""

POLICY_QUERY = """
SELECT schemaname, tablename, policyname, permissive, roles, cmd,
       qual IS NOT NULL AS has_using, with_check IS NOT NULL AS has_with_check
FROM pg_policies WHERE schemaname = ANY(%s) ORDER BY schemaname, tablename, policyname
"""

FUNCTION_QUERY = """
SELECT n.nspname AS schema, p.proname AS name, pg_catalog.oidvectortypes(p.proargtypes) AS argtypes,
       pg_catalog.pg_get_userbyid(p.proowner) AS owner, p.proconfig,
       (SELECT coalesce(array_agg(CASE WHEN a.grantee=0 THEN 'PUBLIC'
                                       ELSE pg_catalog.pg_get_userbyid(a.grantee) END ORDER BY a.grantee), '{}')
          FROM pg_catalog.aclexplode(coalesce(p.proacl, pg_catalog.acldefault('f',p.proowner))) a
         WHERE a.privilege_type='EXECUTE' AND a.grantee<>p.proowner) AS execute_grants
FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
WHERE p.prosecdef AND n.nspname = ANY(%s)
ORDER BY n.nspname, p.proname, p.proargtypes
"""


def _ident(schema: str, name: str) -> str:
    from psycopg import sql
    return sql.SQL("{}.{}").format(sql.Identifier(schema), sql.Identifier(name))


def _count(conn, schema: str, name: str, where: str = "", params=()) -> dict:
    """Return {"rows": n} or {"denied": sqlstate} -- inside a savepoint so denial
    does not poison the surrounding transaction."""
    from psycopg import sql
    import psycopg
    try:
        with conn.transaction():
            row = conn.execute(
                sql.SQL("SELECT count(*) FROM {}" + (" WHERE " + where if where else "")).format(
                    _ident(schema, name)), params).fetchone()
            return {"rows": int(row[0])}
    except psycopg.Error as error:
        return {"denied": error.sqlstate or "unknown"}


def _fingerprint(conn, schema: str, name: str, columns: list[str] | None, where: str = "", params=()) -> dict:
    """{"rows": n, "fp": md5-of-ordered-row-identities} or {"denied": sqlstate}.

    ``columns`` None -> identity by ctid (true row identity); a list -> projection of
    those columns (weaker: identical projections of different rows collide)."""
    from psycopg import sql
    import psycopg
    if columns is None:
        expr = sql.SQL("md5(coalesce(string_agg(ctid::text, ',' ORDER BY ctid), ''))")
    else:
        rowexpr = sql.SQL("concat_ws('\x1f', {})").format(sql.SQL(", ").join(sql.Identifier(c) for c in columns))
        expr = sql.SQL("md5(coalesce(string_agg({r}, ',' ORDER BY {r}), ''))").format(r=rowexpr)
    try:
        with conn.transaction():
            row = conn.execute(
                sql.SQL("SELECT count(*), {} FROM {}.{}" + (" WHERE " + where if where else "")).format(
                    expr, sql.Identifier(schema), sql.Identifier(name)), params).fetchone()
            return {"rows": int(row[0]), "fp": row[1]}
    except psycopg.Error as error:
        return {"denied": error.sqlstate or "unknown"}


def _readable_columns(conn, role: str, table: dict) -> list[str]:
    rows = conn.execute(
        "SELECT a.attname FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace"
        " WHERE n.nspname=%s AND c.relname=%s AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum",
        (table["schema"], table["name"])).fetchall()
    from psycopg import sql
    ident = sql.SQL("{}.{}").format(sql.Identifier(table["schema"]), sql.Identifier(table["name"])).as_string(conn)
    return [r[0] for r in rows if conn.execute("SELECT has_column_privilege(%s, %s, %s, 'SELECT')", (role, ident, r[0])).fetchone()[0]]


def _primary_key(conn, table: dict) -> list[str]:
    rows = conn.execute(
        "SELECT a.attname FROM pg_index i JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum = ANY(i.indkey)"
        " JOIN pg_class c ON c.oid=i.indrelid JOIN pg_namespace n ON n.oid=c.relnamespace"
        " WHERE i.indisprimary AND n.nspname=%s AND c.relname=%s ORDER BY array_position(i.indkey, a.attnum)",
        (table["schema"], table["name"])).fetchall()
    return [r[0] for r in rows]


def _identity(conn, role: str, table: dict, tenant_a: str) -> dict:
    """Owner-side tenant-A row set vs the set the role sees under GUC = A (same snapshot).

    Identity is ctid, else tenant_id + the full primary key; a value projection is
    never accepted (two different rows may project to the same values).
    Must be called inside the probe transaction BEFORE ``SET LOCAL ROLE``."""
    schema, name = table["schema"], table["name"]
    from psycopg import sql
    pk = _primary_key(conn, table)
    readable = set(_readable_columns(conn, role, table))
    key_cols = ["tenant_id"] + [c for c in pk if c != "tenant_id"] if pk else []
    key_readable = bool(key_cols) and set(key_cols) <= readable
    owner_ctid = _fingerprint(conn, schema, name, None, "tenant_id = %s", (tenant_a,))
    owner_key = _fingerprint(conn, schema, name, key_cols, "tenant_id = %s", (tenant_a,)) if key_readable else None
    conn.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role)))
    conn.execute("SELECT set_config(%s, %s, true)", (TENANT_GUC, tenant_a))
    role_ctid = _fingerprint(conn, schema, name, None)
    result: dict
    if "fp" in role_ctid and "fp" in owner_ctid:
        result = {"method": "ctid", "owner_a": owner_ctid, "role_a": role_ctid, "match": role_ctid["fp"] == owner_ctid["fp"]}
    elif key_readable and owner_key and "fp" in owner_key:
        role_key = _fingerprint(conn, schema, name, key_cols)
        if "fp" in role_key:
            result = {"method": "pk", "columns": key_cols, "owner_a": owner_key, "role_a": role_key,
                      "match": role_key["fp"] == owner_key["fp"]}
        else:
            result = {"method": "unverifiable", "reason": f"pk projection denied {role_key.get('denied')}"}
    else:
        missing = sorted(set(key_cols) - readable) if key_cols else ["<no primary key>"]
        result = {"method": "unverifiable",
                  "reason": f"ctid denied {role_ctid.get('denied')}; identity columns not readable: {missing}"}
    conn.execute("RESET ROLE")
    conn.execute(f"RESET {TENANT_GUC}")
    return result


def _visibility(conn, role: str, table: dict, tenant_a: str | None, random_tenant: str) -> dict:
    """Row counts the role sees under each GUC state (transaction rolled back by caller)."""
    from psycopg import sql
    schema, name, scoped = table["schema"], table["name"], table["has_tenant_id"]
    out: dict = {}
    if scoped and tenant_a is not None:
        out["identity"] = _identity(conn, role, table, tenant_a)
    conn.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role)))
    conn.execute(f"RESET {TENANT_GUC}")
    out["guc_unset"] = _count(conn, schema, name)
    if tenant_a is not None:
        conn.execute("SELECT set_config(%s, %s, true)", (TENANT_GUC, tenant_a))
        out["guc_tenant_a"] = _count(conn, schema, name)
        if scoped:
            out["guc_tenant_a_foreign_rows"] = _count(conn, schema, name, "tenant_id <> %s", (tenant_a,))
    conn.execute("SELECT set_config(%s, %s, true)", (TENANT_GUC, random_tenant))
    out["guc_unknown_tenant"] = _count(conn, schema, name)
    conn.execute("SELECT set_config(%s, %s, true)", (TENANT_GUC, "not-a-uuid"))
    out["guc_not_uuid"] = _count(conn, schema, name)
    conn.execute("RESET ROLE")
    conn.execute(f"RESET {TENANT_GUC}")
    return out


def _ground_truth(conn, table: dict, tenant_a: str | None) -> dict:
    schema, name = table["schema"], table["name"]
    out = {"total": _count(conn, schema, name)}
    if table["has_tenant_id"] and tenant_a is not None:
        out["tenant_a"] = _count(conn, schema, name, "tenant_id = %s", (tenant_a,))
        out["other_tenants"] = _count(conn, schema, name, "tenant_id <> %s", (tenant_a,))
    return out


def _privileges(conn, role: str, table: dict) -> dict:
    from psycopg import sql
    ident = sql.SQL("{}.{}").format(sql.Identifier(table["schema"]), sql.Identifier(table["name"])).as_string(conn)
    out = {}
    for priv in PRIVILEGES:
        table_level = conn.execute("SELECT has_table_privilege(%s, %s, %s)", (role, ident, priv)).fetchone()[0]
        column_level = False
        if priv != "DELETE":  # PostgreSQL has no column-level DELETE privilege
            column_level = conn.execute("SELECT has_any_column_privilege(%s, %s, %s)", (role, ident, priv)).fetchone()[0]
        out[priv.lower()] = "table" if table_level else ("column" if column_level else None)
    return out


def _policies_for(policies: list[dict], role: str, table: dict) -> list[dict]:
    return [
        {"name": p["policyname"], "cmd": p["cmd"], "permissive": p["permissive"],
         "roles": list(p["roles"]), "using": p["has_using"], "with_check": p["has_with_check"]}
        for p in policies
        if p["schemaname"] == table["schema"] and p["tablename"] == table["name"]
        and ("public" in p["roles"] or role in p["roles"])
    ]


def _pick_tenants(conn) -> list[str]:
    try:
        rows = conn.execute("SELECT tenant_id::text FROM inv.tenants ORDER BY tenant_id LIMIT 2").fetchall()
    except Exception:
        conn.rollback()
        return []
    return [r[0] for r in rows]


def collect(dsn: str, roles: tuple[str, ...], tenant_a: str | None = None) -> dict:
    """Observe the database at ``dsn``.  Raises on connection failure."""
    import psycopg
    from psycopg.rows import dict_row

    random_tenant = str(uuid.uuid4())
    with psycopg.connect(dsn) as conn:  # tuple rows for probes; dict rows for catalogue reads
        catalogue = conn.cursor(row_factory=dict_row)
        conn.execute("SET statement_timeout = '30s'")
        version = conn.execute("SHOW server_version").fetchone()[0]
        dbname = conn.execute("SELECT current_database()").fetchone()[0]
        try:
            head = conn.execute("SELECT version_num FROM alembic_version").fetchone()
            migration = head[0] if head else None
        except psycopg.Error:
            conn.rollback()
            migration = None
        me = catalogue.execute("SELECT current_user AS u, (SELECT rolsuper FROM pg_roles WHERE rolname=current_user) AS s,"
                               " (SELECT rolbypassrls FROM pg_roles WHERE rolname=current_user) AS b").fetchone()
        guc_unset = conn.execute("SELECT current_setting(%s, true)", (TENANT_GUC,)).fetchone()[0]
        tenants = _pick_tenants(conn)
        if tenant_a is None and tenants:
            tenant_a = tenants[0]
        tables = catalogue.execute(TABLE_QUERY, (list(SCHEMAS),)).fetchall()
        policies = catalogue.execute(POLICY_QUERY, (list(SCHEMAS),)).fetchall()
        functions = catalogue.execute(FUNCTION_QUERY, (list(SCHEMAS),)).fetchall()
        truth = {f"{t['schema']}.{t['name']}": _ground_truth(conn, t, tenant_a) for t in tables}
        conn.rollback()

        role_reports = {}
        for role in roles:
            attrs = catalogue.execute(ROLE_QUERY, (role,)).fetchone()
            if attrs is None:
                role_reports[role] = {"present": False}
                continue
            report = {
                "present": True,
                "superuser": attrs["rolsuper"], "bypassrls": attrs["rolbypassrls"],
                "login": attrs["rolcanlogin"], "inherit": attrs["rolinherit"],
                "member_of": list(attrs["member_of"]),
                "tables": {}, "functions": {},
            }
            for table in tables:
                key = f"{table['schema']}.{table['name']}"
                entry = {
                    "tenant_scoped": table["has_tenant_id"],
                    "rls_enabled": table["relrowsecurity"], "rls_forced": table["relforcerowsecurity"],
                    "privileges": _privileges(conn, role, table),
                    "policies": _policies_for(policies, role, table),
                }
                readable = entry["privileges"]["select"] is not None
                if readable:
                    conn.rollback()  # end the implicit read transaction so the next BEGIN is top-level
                    with conn.transaction():
                        # one snapshot for the owner fingerprint and the role's view
                        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
                        entry["visible"] = _visibility(conn, role, table, tenant_a, random_tenant)
                        raise psycopg.Rollback  # never persist anything, even SET LOCAL side effects
                report["tables"][key] = entry
            for fn in functions:
                key = f"{fn['schema']}.{fn['name']}({fn['argtypes']})"
                sig = f"{fn['schema']}.{fn['name']}({fn['argtypes']})"
                execute = conn.execute("SELECT has_function_privilege(%s, %s, 'EXECUTE')", (role, sig)).fetchone()[0]
                report["functions"][key] = {"execute": bool(execute)}
            role_reports[role] = report

        function_catalogue = {
            f"{fn['schema']}.{fn['name']}({fn['argtypes']})": {
                "owner": fn["owner"], "config": list(fn["proconfig"] or []),
                "execute_grants": list(fn["execute_grants"]),
            }
            for fn in functions
        }

    prov = provenance()
    return {
        "collector": "tools/collect_rls_evidence.py",
        "collected_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "git_sha": prov["git_sha"],
        "provenance": prov,
        "database": {"name": dbname, "server_version": version, "migration_head": migration,
                     "observer": {"role": me["u"], "superuser": me["s"], "bypassrls": me["b"]}},
        "tenant_guc": {"name": TENANT_GUC, "unset_value": guc_unset, "tenant_a": tenant_a,
                       "known_tenants": len(tenants), "random_tenant": random_tenant},
        "schemas": list(SCHEMAS),
        "ground_truth": truth,
        "roles": role_reports,
        "definer_functions": function_catalogue,
    }


def load_baseline(path: Path | None = None) -> dict:
    path = path or BASELINE_PATH
    if not path.exists():
        return {"accepted": []}
    return json.loads(path.read_text(encoding="utf-8"))


def apply_baseline(violations: list[dict], baseline: dict) -> tuple[list[dict], list[dict]]:
    """Split violations into (remaining, accepted) using reviewed (role, table, rules) entries."""
    remaining, accepted = [], []
    for v in violations:
        match = next((e for e in baseline.get("accepted", []) if e["role"] == v.get("role")
                      and e["table"] == v.get("table") and v["rule"] in e["rules"]), None)
        if match is None:
            remaining.append(v)
        else:
            accepted.append({**v, "reason": match["reason"], "since": match.get("since")})
    return remaining, accepted


def evaluate(observation: dict) -> list[dict]:
    """Apply E1..E6 to an observation; return the list of violations (empty = pass)."""
    violations: list[dict] = []
    for role, report in observation["roles"].items():
        if not report.get("present"):
            continue
        if report["superuser"] or report["bypassrls"]:
            violations.append({"rule": "E1", "role": role, "detail": "role is SUPERUSER or BYPASSRLS"})
        for table, entry in report["tables"].items():
            readable = entry["privileges"]["select"] is not None
            if not entry["tenant_scoped"] or not readable:
                continue
            if not (entry["rls_enabled"] and entry["rls_forced"]):
                violations.append({"rule": "E2", "role": role, "table": table,
                                   "detail": "tenant-scoped readable table without enabled+forced RLS"})
            vis = entry.get("visible", {})
            truth = observation.get("ground_truth", {}).get(table, {})
            if vis.get("guc_unset", {}).get("rows", 0) > 0:
                violations.append({"rule": "E3", "role": role, "table": table,
                                   "detail": f"{vis['guc_unset']['rows']} rows visible with {TENANT_GUC} unset"})
            foreign = vis.get("guc_tenant_a_foreign_rows", {})
            visible_a = vis.get("guc_tenant_a", {}).get("rows")
            truth_a = truth.get("tenant_a", {}).get("rows")
            identity = vis.get("identity")
            if foreign.get("rows", 0) > 0:
                violations.append({"rule": "E4", "role": role, "table": table,
                                   "detail": f"{foreign['rows']} rows of other tenants visible"})
            elif identity is not None and identity.get("match") is False:
                violations.append({"rule": "E4", "role": role, "table": table,
                                   "detail": f"row set under tenant A differs from the owner's tenant-A set "
                                             f"({identity['method']}: role {identity['role_a']['rows']} rows / owner {identity['owner_a']['rows']} rows; "
                                             f"foreign probe: {foreign.get('denied', foreign.get('rows', 'n/a'))})"})
            elif identity is None and visible_a is not None and truth_a is not None and visible_a > truth_a:
                violations.append({"rule": "E4", "role": role, "table": table,
                                   "detail": f"{visible_a} rows visible under tenant A but the owner counts {truth_a}"
                                             f" (foreign probe: {foreign.get('denied', foreign.get('rows', 'n/a'))})"})
            if vis.get("guc_unknown_tenant", {}).get("rows", 0) > 0:
                violations.append({"rule": "E5", "role": role, "table": table,
                                   "detail": f"{vis['guc_unknown_tenant']['rows']} rows visible for an unknown tenant"})
    for fn, entry in observation["definer_functions"].items():
        if "PUBLIC" in entry["execute_grants"]:
            violations.append({"rule": "E6", "function": fn, "detail": "EXECUTE granted to PUBLIC"})
    return violations


def unverified_identities(observation: dict) -> list[dict]:
    """(role, table) pairs whose E4 row identity could not be checked: these make the
    verdict UNMEASURED (never PASS) unless the baseline accepts them for rule E4."""
    out = []
    for role, report in observation["roles"].items():
        if not report.get("present"):
            continue
        for table, entry in report["tables"].items():
            identity = entry.get("visible", {}).get("identity")
            if identity is not None and identity.get("method") == "unverifiable":
                out.append({"rule": "E4", "role": role, "table": table,
                            "detail": f"row identity unverifiable: {identity.get('reason')}"})
    return out


def verdict(violations: list[dict], unmeasured: list[dict]) -> str:
    if violations:
        return "VIOLATIONS"
    return "UNMEASURED" if unmeasured else "PASS"


def _fmt(cell: dict | None) -> str:
    if cell is None:
        return "-"
    if "denied" in cell:
        return f"denied {cell['denied']}"
    return str(cell["rows"])


def _fmt_identity(identity: dict | None) -> str:
    if identity is None:
        return "-"
    if identity.get("method") == "unverifiable":
        return "unverifiable"
    return f"{'same' if identity['match'] else 'DIFFERENT'} ({identity['method']})"


def render_markdown(observation: dict, violations: list[dict], accepted: list[dict] | None = None,
                    unmeasured: list[dict] | None = None) -> str:
    db = observation["database"]
    guc = observation["tenant_guc"]
    accepted = accepted or []
    unmeasured = unmeasured or []
    lines = [
        "# RLS / authentication boundary evidence",
        "",
        f"- collected_at: {observation['collected_at']} · git HEAD: `{observation['git_sha']}` · collector: `{observation['collector']}`",
        f"- provenance: collector sha256 `{(observation.get('provenance') or {}).get('collector_sha256')}` · baseline sha256 "
        f"`{(observation.get('provenance') or {}).get('baseline_sha256')}` · uncommitted sources: "
        f"{(observation.get('provenance') or {}).get('uncommitted_sources') or 'none'}",
        f"- database: `{db['name']}` · PostgreSQL {db['server_version']} · migration head `{db['migration_head']}`"
        f" · observer role `{db['observer']['role']}` (superuser={db['observer']['superuser']}, bypassrls={db['observer']['bypassrls']})",
        f"- GUC `{guc['name']}`: unset value `{guc['unset_value']!r}` · tenant A `{guc['tenant_a']}` · known tenants {guc['known_tenants']}",
        f"- verdict: **{verdict(violations, unmeasured) if not violations else f'{len(violations)} violation(s)'}** (E1..E6; an unverifiable row identity makes the verdict UNMEASURED, never PASS)",
        "- rerun: `INV_AUDIT_DSN=<owner dsn> python tools/collect_rls_evidence.py --out-dir <dir>` (DSN value is never recorded)",
    ]
    if observation.get("note"):
        lines.append(f"- condition: {observation['note']}")
    lines.append("")
    if unmeasured:
        lines += ["## Unverifiable row identities (verdict cannot be PASS)", "", "| rule | role | table | detail |", "|---|---|---|---|"]
        for u in unmeasured:
            lines.append(f"| {u['rule']} | {u['role']} | {u['table']} | {u['detail']} |")
        lines.append("")
    if accepted:
        lines += ["## Accepted exceptions (tools/rls-boundary-baseline.json)", "", "| rule | role | table | reason |", "|---|---|---|---|"]
        for a in accepted:
            lines.append(f"| {a['rule']} | {a['role']} | {a['table']} | {a['reason']} |")
        lines.append("")
    if violations:
        lines += ["## Violations", "", "| rule | role | object | detail |", "|---|---|---|---|"]
        for v in violations:
            lines.append(f"| {v['rule']} | {v.get('role', '-')} | {v.get('table', v.get('function', '-'))} | {v['detail']} |")
        lines.append("")
    for role, report in observation["roles"].items():
        lines += [f"## role `{role}`", ""]
        if not report.get("present"):
            lines += ["absent in pg_roles (not measured)", ""]
            continue
        lines += [
            f"superuser={report['superuser']} bypassrls={report['bypassrls']} login={report['login']}"
            f" member_of={report['member_of'] or '[]'}",
            "",
            "| table | scoped | RLS | privileges | policies | truth total / A / other | unset | A | A-foreign | A-identity | unknown | not-uuid |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        for table, entry in report["tables"].items():
            privs = ",".join(f"{k[0].upper()}{'' if v == 'table' else '(col)'}" for k, v in entry["privileges"].items() if v) or "-"
            if privs == "-" and not entry["policies"]:
                continue  # nothing granted: keep the table out of the boundary table
            rls = ("on" if entry["rls_enabled"] else "off") + ("+forced" if entry["rls_forced"] else "")
            pol = ",".join(f"{p['name']}[{p['cmd']}]" for p in entry["policies"]) or "-"
            truth = observation["ground_truth"].get(table, {})
            vis = entry.get("visible", {})
            lines.append(
                f"| `{table}` | {'yes' if entry['tenant_scoped'] else 'no'} | {rls} | {privs} | {pol} | "
                f"{_fmt(truth.get('total'))} / {_fmt(truth.get('tenant_a'))} / {_fmt(truth.get('other_tenants'))} | "
                f"{_fmt(vis.get('guc_unset'))} | {_fmt(vis.get('guc_tenant_a'))} | {_fmt(vis.get('guc_tenant_a_foreign_rows'))} | "
                f"{_fmt_identity(vis.get('identity'))} | {_fmt(vis.get('guc_unknown_tenant'))} | {_fmt(vis.get('guc_not_uuid'))} |"
            )
        lines += ["", "| SECURITY DEFINER function | execute |", "|---|---|"]
        for fn, entry in report["functions"].items():
            lines.append(f"| `{fn}` | {'yes' if entry['execute'] else 'no'} |")
        lines.append("")
    lines += ["## SECURITY DEFINER catalogue", "", "| function | owner | config | execute grants |", "|---|---|---|---|"]
    for fn, entry in observation["definer_functions"].items():
        lines.append(f"| `{fn}` | {entry['owner']} | {' '.join(entry['config']) or '-'} | {', '.join(entry['execute_grants']) or '-'} |")
    lines.append("")
    return "\n".join(lines)


def _git_sha() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT,
                              capture_output=True, text=True, timeout=10).stdout.strip() or None
    except Exception:
        return None


def _sha256_of(path: Path) -> str | None:
    import hashlib
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def provenance() -> dict:
    """What produced this evidence: HEAD, whether the collector/baseline are committed
    at that HEAD, and their content hashes (the hashes are the durable identity when
    the evidence is generated before the commit that carries the collector)."""
    collector = Path(__file__).resolve()
    tracked_dirty: list[str] = []
    try:
        status = subprocess.run(["git", "status", "--porcelain", "--", str(collector), str(BASELINE_PATH)],
                                cwd=REPO_ROOT, capture_output=True, text=True, timeout=10).stdout
        tracked_dirty = [line[3:].strip() for line in status.splitlines() if line.strip()]
    except Exception:
        pass
    return {
        "git_sha": _git_sha(),
        "collector_sha256": _sha256_of(collector),
        "baseline_sha256": _sha256_of(BASELINE_PATH),
        "uncommitted_sources": tracked_dirty,
        "note": "git_sha is HEAD of the working tree at collection time; if uncommitted_sources is non-empty "
                "the collector/baseline content hashes, not git_sha, identify the code that ran.",
    }


def assert_no_secrets(text: str, dsn: str) -> None:
    """Refuse to write evidence that embeds the DSN or its password."""
    from psycopg.conninfo import conninfo_to_dict
    if dsn in text:
        raise ValueError("evidence would embed the DSN")
    try:
        password = conninfo_to_dict(dsn).get("password")
    except Exception:
        password = None
    if password and password in text:
        raise ValueError("evidence would embed a password")


def _compact(observation: dict) -> dict:
    """Drop per-role table entries with no privilege, policy or probe (keeps the JSON reviewable)."""
    out = json.loads(json.dumps(observation))
    for report in out["roles"].values():
        if not report.get("present"):
            continue
        report["tables"] = {k: v for k, v in report["tables"].items()
                            if any(v["privileges"].values()) or v["policies"] or "visible" in v}
    return out


def write_evidence(observation: dict, violations: list[dict], out_dir: Path, label: str, dsn: str,
                   accepted: list[dict] | None = None, unmeasured: list[dict] | None = None) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {**_compact(observation), "violations": violations, "accepted": accepted or [],
               "unmeasured": unmeasured or [], "verdict": verdict(violations, unmeasured or [])}
    json_text = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True)
    md_text = render_markdown(observation, violations, accepted, unmeasured)
    assert_no_secrets(json_text, dsn)
    assert_no_secrets(md_text, dsn)
    json_path, md_path = out_dir / f"{label}.json", out_dir / f"{label}.md"
    json_path.write_text(json_text + "\n", encoding="utf-8")
    md_path.write_text(md_text, encoding="utf-8")
    return json_path, md_path


def disposable_database(admin_dsn: str):
    """Context manager: CREATE DATABASE, alembic upgrade head, seed two tenants; DROP on exit."""
    import contextlib
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import conninfo_to_dict, make_conninfo
    from sqlalchemy.engine import URL

    @contextlib.contextmanager
    def _cm():
        name = "inv_rls_" + uuid.uuid4().hex
        owner = make_conninfo(admin_dsn, dbname=name)
        with psycopg.connect(admin_dsn, autocommit=True) as conn:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            info = conninfo_to_dict(owner)
            url = URL.create("postgresql+psycopg", username=info.get("user"), password=info.get("password"),
                             host=info.get("host"), port=int(info.get("port", 5432)), database=name
                             ).render_as_string(hide_password=False)
            result = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=REPO_ROOT,
                                    env={**os.environ, "INV_MIGRATION_DSN": url, "INV_DATABASE_URL": url},
                                    capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError("alembic upgrade failed (credential-bearing output suppressed)")
            tenant_a, tenant_b = str(uuid.uuid4()), str(uuid.uuid4())
            with psycopg.connect(owner) as conn:
                conn.execute("INSERT INTO inv.tenants VALUES (%s,'rls-evidence-a'),(%s,'rls-evidence-b')", (tenant_a, tenant_b))
                conn.execute("INSERT INTO public.tenants(tenant_id,slug,display_name) VALUES (%s,'rls-a','A'),(%s,'rls-b','B')",
                             (tenant_a, tenant_b))
                conn.execute(
                    "INSERT INTO public.projects(project_id,tenant_id,code,display_name) VALUES (%s,%s,'rls-a','A'),(%s,%s,'rls-b','B')",
                    ("prj_" + uuid.uuid4().hex[:26].upper(), tenant_a, "prj_" + uuid.uuid4().hex[:26].upper(), tenant_b))
            yield owner, tenant_a
        finally:
            assert name.startswith("inv_rls_") and len(name) == 40
            with psycopg.connect(admin_dsn, autocommit=True) as conn:
                conn.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
    return _cm()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dsn", default=os.environ.get("INV_AUDIT_DSN"),
                        help="owner/superuser DSN able to SET ROLE (default: $INV_AUDIT_DSN); never recorded")
    parser.add_argument("--disposable", action="store_true",
                        help="create a disposable migrated database from $INV_TEST_ADMIN_DSN, measure it, drop it")
    parser.add_argument("--roles", default=",".join(DEFAULT_ROLES), help="comma-separated roles to measure")
    parser.add_argument("--tenant", default=None, help="tenant A uuid (default: first row of inv.tenants)")
    parser.add_argument("--out-dir", default=str(REPO_ROOT / "docs/vault/30_Development/Evidence/rls-boundary"))
    parser.add_argument("--label", default=None, help="file stem (default: rls-<db>-<git>-<utc date>)")
    parser.add_argument("--json", action="store_true", help="also print the JSON payload to stdout")
    parser.add_argument("--note", default=None, help="free-text run condition recorded in the evidence")
    parser.add_argument("--baseline", default=str(BASELINE_PATH), help="reviewed exceptions file (default: tools/rls-boundary-baseline.json)")
    args = parser.parse_args(argv)
    roles = tuple(r.strip() for r in args.roles.split(",") if r.strip())
    try:
        if args.disposable:
            admin = os.environ.get("INV_TEST_ADMIN_DSN")
            if not admin:
                print("INV_TEST_ADMIN_DSN is required for --disposable", file=sys.stderr)
                return 2
            with disposable_database(admin) as (dsn, tenant_a):
                observation = collect(dsn, roles, args.tenant or tenant_a)
        else:
            if not args.dsn:
                print("--dsn or INV_AUDIT_DSN is required", file=sys.stderr)
                return 2
            dsn = args.dsn
            observation = collect(dsn, roles, args.tenant)
    except Exception as error:  # connection / catalogue failure: credentials may be in the message
        print(f"observation unavailable: {type(error).__name__}", file=sys.stderr)
        return 2
    observation["note"] = args.note
    baseline = load_baseline(Path(args.baseline))
    violations, accepted = apply_baseline(evaluate(observation), baseline)
    unmeasured, accepted_unmeasured = apply_baseline(unverified_identities(observation), baseline)
    accepted += accepted_unmeasured
    result = verdict(violations, unmeasured)
    label = args.label or "rls-{}-{}-{}".format(
        observation["database"]["name"], observation["git_sha"] or "nogit",
        dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d"))
    json_path, md_path = write_evidence(observation, violations, Path(args.out_dir), label, dsn, accepted, unmeasured)
    if args.json:
        print(json.dumps({**observation, "violations": violations}, indent=2, ensure_ascii=False, sort_keys=True))
    print(f"{result if not violations else 'VIOLATIONS ' + str(len(violations))}: roles={len(observation['roles'])}"
          f" tables={len(observation['ground_truth'])} definer_functions={len(observation['definer_functions'])}"
          f" accepted={len(accepted)} unmeasured={len(unmeasured)}"
          f" -> {md_path.relative_to(REPO_ROOT) if md_path.is_relative_to(REPO_ROOT) else md_path}")
    for v in violations:
        print(f"  {v['rule']} {v.get('role', '')} {v.get('table', v.get('function', ''))}: {v['detail']}")
    for u in unmeasured:
        print(f"  unmeasured {u['role']} {u['table']}: {u['detail']}")
    return {"PASS": 0, "VIOLATIONS": 1, "UNMEASURED": 3}[result]


if __name__ == "__main__":
    sys.exit(main())
