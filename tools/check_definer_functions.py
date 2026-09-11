"""Check every SECURITY DEFINER function in a live database, not in the source.

A SECURITY DEFINER function runs as its owner and therefore **bypasses row level
security**. Every one of them is a hole in tenant isolation unless it binds its
answer to the tenant the session is actually scoped to, and a caller-supplied
tenant id is not a scope.

This repository has already made that mistake twice — ``project_kernel_link``
in 0024, corrected by 0027, and ``subject_kernel_link`` in 0026, corrected by
0028. Both corrections were ``CREATE OR REPLACE``, which is the right way to fix
one and also the reason source review cannot answer the question: **what matters
is the definition a database currently holds**, and a database that stopped
part-way through the chain holds the earlier one.

So this reads ``pg_proc``. Two properties per function:

``binds_tenant``
    The body references ``current_setting('inv.tenant_id')``. Without it the
    function answers about whatever tenant it was asked about.
``pins_search_path``
    ``search_path`` is set on the function. Resolving names through the
    caller's path is how a definer function becomes a privilege escalation —
    the caller creates ``public.users`` in a schema it controls, and the
    function reads it with the owner's rights.

A function that genuinely takes no tenant argument is not a leak, so the
allowlist names those with the reason rather than lowering the rule.

Usage:
    python tools/check_definer_functions.py --dsn DSN [--json]
"""

from __future__ import annotations

import argparse
import json
import sys

#: Definer functions that do not take a tenant and cannot leak one. Named with
#: the reason, so adding one is a decision rather than a way past the check.
NO_TENANT_ARGUMENT: dict[str, str] = {
    "node_by_certificate": (
        "authentication runs before a tenant scope exists — the credential is "
        "what decides the tenant, so there is no scope to bind to. It matches "
        "an exact 64-character fingerprint and returns three columns, so it "
        "cannot enumerate."
    ),
}

QUERY = """
SELECT n.nspname AS schema,
       p.proname AS name,
       pg_catalog.pg_get_function_identity_arguments(p.oid) AS args,
       p.prosrc AS body,
       coalesce(p.proconfig, '{}') AS config,
       pg_catalog.pg_get_userbyid(p.proowner) AS owner
FROM pg_catalog.pg_proc p
JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
WHERE p.prosecdef
  AND n.nspname IN ('public', 'inv')
ORDER BY n.nspname, p.proname
"""


def audit(dsn: str) -> list[dict]:
    import psycopg
    from psycopg.rows import dict_row

    try:
        from _definer_rules import judge
    except ImportError:
        import sys as _sys
        from pathlib import Path as _Path

        _sys.path.insert(0, str(_Path(__file__).resolve().parent))
        from _definer_rules import judge

    findings = []
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        for row in conn.execute(QUERY).fetchall():
            args = row["args"] or ""
            verdict = judge(row["body"] or "", args, row["config"] or [])
            takes_tenant = verdict["takesTenant"]
            binds_tenant = verdict["bindsTenant"]
            pins_search_path = verdict["pinsSearchPath"]

            allowed_reason = NO_TENANT_ARGUMENT.get(row["name"])
            # A function with no tenant argument cannot be asked about another
            # tenant, so the binding rule does not apply to it.
            needs_binding = takes_tenant and allowed_reason is None

            problems = []
            if needs_binding and not binds_tenant:
                problems.append(
                    "takes a tenant id and does not bind it to "
                    "current_setting('inv.tenant_id'), so it answers about "
                    "whatever tenant it is asked about"
                )
            if not pins_search_path:
                problems.append(
                    "does not pin search_path, so it resolves names through the "
                    "caller's path with the owner's rights"
                )
            if verdict["tempSchemaMisplaced"]:
                problems.append(
                    "resolves through pg_temp before its own schemas "
                    f"(search_path = {verdict['searchPath']}), so a caller can "
                    "create a temporary object that shadows a name it reads"
                )
            if takes_tenant and allowed_reason is not None and not binds_tenant:
                problems.append(
                    "is allowlisted but takes a tenant id; the allowlist is for "
                    "functions that cannot be asked about another tenant"
                )

            findings.append(
                {
                    "function": f"{row['schema']}.{row['name']}({args})",
                    "owner": row["owner"],
                    "takesTenant": takes_tenant,
                    "bindsTenant": binds_tenant,
                    "pinsSearchPath": pins_search_path,
                    "searchPath": verdict["searchPath"],
                    "allowlisted": allowed_reason is not None,
                    "allowlistReason": allowed_reason,
                    "problems": problems,
                }
            )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", required=True, help="the database to inspect")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    findings = audit(args.dsn)
    unsafe = [f for f in findings if f["problems"]]

    if args.json:
        print(json.dumps({"functions": findings, "unsafe": len(unsafe)}, indent=2))
        return 1 if unsafe else 0

    print(f"{len(findings)} SECURITY DEFINER function(s) in this database\n")
    for finding in findings:
        mark = "UNSAFE" if finding["problems"] else "ok    "
        note = ""
        if finding["allowlisted"]:
            note = "  (allowlisted)"
        elif not finding["takesTenant"]:
            note = "  (no tenant argument)"
        print(f"  {mark} {finding['function']}{note}")
        for problem in finding["problems"]:
            print(f"           {problem}")

    if unsafe:
        print(
            f"\n{len(unsafe)} function(s) run with the owner's rights and are "
            f"not held to the session's scope — by answering about a tenant the "
            f"session is not in, or by resolving a name the caller controls. A "
            f"definer function bypasses row level security, so this is the "
            f"isolation boundary, not a defence behind it."
        )
        return 1
    print("\nEvery definer function is bound to the session's tenant scope.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
