"""Compare live privileged functions with a versioned, reviewed policy.

Continues Claude's 9995122 audit at the same entry point. SQL substrings cannot
prove isolation. Match complete schema/signature/definition and EXECUTE grants;
reject missing or unrecognized privileged routines. Never learn the policy from
the target database. A match is a bounded catalogue observation, not proof of
all RLS, caller identity or restore safety. SECURITY DEFINER uses owner rights;
RLS bypass depends on those rights and FORCE RLS, not the declaration alone.

Usage: INV_AUDIT_DSN=... python tools/check_definer_functions.py --json
Exit 0: matches policy; 1: review required; 2: observation unavailable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

POLICY_PATH = Path(__file__).with_name("definer-policy.json")
RUNTIME_ROLES = ("inv_app", "inv_kernel")
QUERY = """
SELECT p.oid, n.nspname AS schema, p.proname AS name,
       pg_catalog.oidvectortypes(p.proargtypes) AS argtypes,
       pg_catalog.pg_get_functiondef(p.oid) AS definition,
       pg_catalog.pg_get_userbyid(p.proowner) AS owner,
       p.proowner AS owner_oid,
       (SELECT coalesce(json_agg(json_build_object(
          'role', CASE WHEN a.grantee=0 THEN 'PUBLIC'
                       ELSE pg_catalog.pg_get_userbyid(a.grantee) END,
          'grantable', a.is_grantable) ORDER BY a.grantee), '[]'::json)
        FROM pg_catalog.aclexplode(coalesce(p.proacl,
             pg_catalog.acldefault('f',p.proowner))) a
        WHERE a.privilege_type='EXECUTE' AND a.grantee<>p.proowner) AS execute_grants
FROM pg_catalog.pg_proc p
JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
WHERE p.prosecdef AND left(n.nspname,3)<>'pg_'
  AND n.nspname<>'information_schema'
ORDER BY n.nspname,p.proname,p.proargtypes
"""


def _policy() -> dict:
    value = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    if value.get("version") != 1 or not value.get("functions") or not value.get("revision"):
        raise ValueError("Privileged function policy is unavailable")
    return value


def audit(dsn: str) -> list[dict]:
    """Never execute audited functions; all observations share a snapshot."""
    import psycopg
    from psycopg.rows import dict_row

    policy = _policy()
    expected = policy["functions"]
    findings = []
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        conn.execute("SET LOCAL search_path=pg_catalog")
        conn.execute("SET LOCAL statement_timeout='10s'")
        revisions = sorted(
            r["version_num"] for r in conn.execute("SELECT version_num FROM public.alembic_version")
        )
        if revisions != [policy["revision"]]:
            findings.append(
                {"function": "<migration>", "problems": ["migration_revision_mismatch"]}
            )
        roles = conn.execute(
            "SELECT oid,rolname,rolsuper,rolbypassrls FROM pg_catalog.pg_roles "
            "WHERE rolname=ANY(%s)",
            (list(RUNTIME_ROLES),),
        ).fetchall()
        if {r["rolname"] for r in roles} != set(RUNTIME_ROLES):
            findings.append({"function": "<runtime roles>", "problems": ["runtime_role_missing"]})
        for role in roles:
            problems = []
            if role["rolsuper"] or role["rolbypassrls"]:
                problems.append("runtime_role_bypasses_rls")
            schemas = conn.execute(
                "SELECT nspname FROM pg_catalog.pg_namespace WHERE "
                "nspname IN ('public','inv','pg_catalog') AND "
                "pg_catalog.has_schema_privilege(%s,oid,'CREATE')",
                (role["oid"],),
            ).fetchall()
            if schemas:
                problems.append("runtime_can_create_in_trusted_schema")
            if problems:
                findings.append(
                    {"function": "<runtime role " + role["rolname"] + ">", "problems": problems}
                )
        observed = set()
        for row in conn.execute(QUERY).fetchall():
            signature = f"{row['schema']}.{row['name']}({row['argtypes']})"
            observed.add(signature)
            spec = expected.get(signature)
            digest = hashlib.sha256(row["definition"].encode("utf-8")).hexdigest()
            problems = []
            if spec is None:
                problems.append("unrecognized_privileged_function")
            else:
                if digest != spec["definitionSHA256"]:
                    problems.append("definition_differs_from_policy")
                grants = row["execute_grants"]
                if sorted(g["role"] for g in grants) != sorted(spec["executeRoles"]) or any(
                    g["grantable"] for g in grants
                ):
                    problems.append("execute_grants_differ_from_policy")
            for role in roles:
                member = conn.execute(
                    "SELECT pg_catalog.pg_has_role(%s,%s,'MEMBER') AS member",
                    (role["oid"], row["owner_oid"]),
                ).fetchone()["member"]
                if member:
                    problems.append("runtime_can_assume_function_owner")
                    break
            findings.append(
                {
                    "function": signature,
                    "owner": row["owner"],
                    "definitionSHA256": digest,
                    "executeGrants": row["execute_grants"],
                    "policyKind": spec["kind"] if spec else None,
                    "problems": problems,
                }
            )
        for signature in sorted(set(expected) - observed):
            findings.append(
                {"function": signature, "problems": ["expected_privileged_function_missing"]}
            )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dsn",
        default=os.getenv("INV_AUDIT_DSN"),
        help="prefer INV_AUDIT_DSN to command-line secrets",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        if not args.dsn:
            raise ValueError("Missing audit connection")
        findings = audit(args.dsn)
    except Exception:
        # Driver exceptions may contain credentials/SQL/data. Never publish them
        # or turn a failed observation into an empty passing inventory.
        value = {"status": "unavailable", "error": "catalog_observation_failed", "unsafe": None}
        print(
            json.dumps(value)
            if args.json
            else "Privileged function audit unavailable; no pass recorded."
        )
        return 2
    unsafe = sum(bool(f["problems"]) for f in findings)
    status = "requires_review" if unsafe else "matches_reviewed_policy"
    if args.json:
        print(json.dumps({"status": status, "functions": findings, "unsafe": unsafe}, indent=2))
    else:
        print(status)
        for finding in findings:
            print(f"  {finding['function']}: {', '.join(finding['problems']) or 'matches policy'}")
        print("Read-only catalogue observation; runtime tenant and recovery tests remain required.")
    return 1 if unsafe else 0


if __name__ == "__main__":
    raise SystemExit(main())
