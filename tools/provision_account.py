"""Operator provisioning: link an account, a project and a workspace for execution.

``GET /v1/workspaces/{id}/execution-readiness`` reports five preconditions and
says which of them an operator owns. This is the other half — the thing an
operator actually runs to satisfy them.

**It is deliberately not an API.** Two of the five links decide which projects
may execute and who may approve, and the whole reason they live in
``inv.business_projects`` and ``inv.business_subjects`` is that the web process
must not be able to grant itself either. A endpoint that did this, however well
guarded, would be that grant. So it is a command an operator runs with the
schema owner's credentials, on purpose, and it prints what it did.

**It refuses to guess the subject.** ``inv.business_subjects.subject_id`` is
``oidc:sha256([issuer, sub])`` and the mapping is one-to-one and immutable — a
two-person rule one person can satisfy with two identities is not a two-person
rule. So the issuer and the subject are named explicitly and the hash is derived
here with the same function the kernel uses, rather than accepting a
pre-computed digest that nobody could check.

**Every step is idempotent and none is destructive.** Running it twice is what a
retry looks like. It never disables a link, never changes a role that already
exists, and never moves the recovery epoch — rolling the epoch voids every
reservation in flight and is a separate, deliberate act.

Usage:
    python tools/provision_account.py --dsn ... --check   PROJECT USER ISSUER SUB
    python tools/provision_account.py --dsn ... --apply   PROJECT USER ISSUER SUB
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from typing import Any


def public_subject(issuer: str, subject: str) -> str:
    """The kernel's derivation, not a second one.

    Imported if the package is importable, recomputed identically otherwise, so
    this tool can run on a machine that has the database but not the service.
    """
    try:
        from inv.identity import public_subject as kernel_subject

        return kernel_subject(issuer, subject)
    except Exception:
        return (
            "oidc:"
            + hashlib.sha256(
                json.dumps([issuer, subject], separators=(",", ":")).encode()
            ).hexdigest()
        )


def _rows(conn, sql: str, params: tuple) -> list[tuple]:
    with conn.cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchall()


def inspect(conn, *, tenant: str, project: str, user: str, subject: str) -> dict[str, Any]:
    """What is already in place. Read-only, and safe to run against production."""
    state: dict[str, Any] = {}
    state["epoch"] = bool(
        _rows(conn, "SELECT 1 FROM inv.control_epoch WHERE singleton", ())
    )
    state["publicProject"] = bool(
        _rows(
            conn,
            "SELECT 1 FROM public.projects WHERE tenant_id=%s AND project_id=%s",
            (tenant, project),
        )
    )
    state["publicUser"] = bool(
        _rows(
            conn,
            "SELECT 1 FROM public.users WHERE tenant_id=%s AND user_id=%s AND status='active'",
            (tenant, user),
        )
    )
    state["kernelTenant"] = bool(
        _rows(conn, "SELECT 1 FROM inv.tenants WHERE tenant_id=%s", (tenant,))
    )
    state["kernelProject"] = bool(
        _rows(
            conn,
            "SELECT 1 FROM inv.projects WHERE tenant_id=%s AND project_id=%s",
            (tenant, project),
        )
    )
    state["businessProject"] = bool(
        _rows(
            conn,
            "SELECT 1 FROM inv.business_projects WHERE tenant_id=%s AND project_id=%s AND enabled",
            (tenant, project),
        )
    )
    existing = _rows(
        conn,
        "SELECT subject_id FROM inv.business_subjects WHERE tenant_id=%s AND user_id=%s",
        (tenant, user),
    )
    state["businessSubject"] = bool(existing)
    # The one case that must never be papered over: this user is already mapped
    # to a *different* subject. The mapping is one-to-one on purpose, and
    # silently replacing it would let one person hold two voting identities.
    state["conflictingSubject"] = (
        existing[0][0] if existing and existing[0][0] != subject else None
    )
    state["externalSubjectMatches"] = bool(
        _rows(
            conn,
            "SELECT 1 FROM public.users WHERE tenant_id=%s AND user_id=%s "
            "AND external_subject=%s",
            (tenant, user, subject),
        )
    )
    return state


def apply(conn, *, tenant: str, project: str, user: str, subject: str) -> list[str]:
    """Do the missing steps. Idempotent, and never destructive."""
    done: list[str] = []
    with conn.cursor() as cursor:
        cursor.execute(
            "INSERT INTO inv.control_epoch (singleton, epoch) "
            "VALUES (true, gen_random_uuid()) ON CONFLICT (singleton) DO NOTHING"
        )
        if cursor.rowcount:
            done.append("seeded the first recovery epoch")

        cursor.execute(
            "INSERT INTO inv.tenants (tenant_id, name) "
            "SELECT tenant_id, display_name FROM public.tenants WHERE tenant_id=%s "
            "ON CONFLICT (tenant_id) DO NOTHING",
            (tenant,),
        )
        if cursor.rowcount:
            done.append("projected the tenant into the kernel")

        cursor.execute(
            "INSERT INTO inv.projects (tenant_id, project_id) VALUES (%s, %s) "
            "ON CONFLICT DO NOTHING",
            (tenant, project),
        )
        if cursor.rowcount:
            done.append("projected the project into the kernel")

        cursor.execute(
            "INSERT INTO inv.business_projects (tenant_id, project_id, enabled) "
            "VALUES (%s, %s, true) "
            "ON CONFLICT (tenant_id, project_id) DO UPDATE SET enabled = true",
            (tenant, project),
        )
        done.append("linked the project for execution")

        cursor.execute(
            "UPDATE public.users SET external_subject=%s "
            "WHERE tenant_id=%s AND user_id=%s AND external_subject IS DISTINCT FROM %s",
            (subject, tenant, user, subject),
        )
        if cursor.rowcount:
            done.append("set the account's login subject")

        cursor.execute(
            "INSERT INTO inv.business_subjects (tenant_id, subject_id, user_id, enabled) "
            "VALUES (%s, %s, %s, true) ON CONFLICT DO NOTHING",
            (tenant, subject, user),
        )
        if cursor.rowcount:
            done.append("registered the approval subject")
    return done


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", required=True, help="schema owner DSN")
    parser.add_argument("--tenant", required=True)
    parser.add_argument("project")
    parser.add_argument("user", help="public.users.user_id, e.g. usr_01...")
    parser.add_argument("issuer", help="OIDC issuer, exactly as the token carries it")
    parser.add_argument("sub", help="OIDC subject claim")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="report only")
    group.add_argument("--apply", action="store_true", help="make the missing links")
    args = parser.parse_args()

    import psycopg

    subject = public_subject(args.issuer, args.sub)
    with psycopg.connect(args.dsn, autocommit=False) as conn:
        state = inspect(
            conn,
            tenant=args.tenant,
            project=args.project,
            user=args.user,
            subject=subject,
        )
        print(f"subject: {subject}")
        for key, value in state.items():
            if key == "conflictingSubject":
                continue
            print(f"  {key:24} {'ok' if value else 'MISSING'}")

        if state["conflictingSubject"]:
            # Refused rather than replaced. The mapping is one-to-one so that a
            # two-person approval cannot be satisfied by one person holding two
            # identities; quietly repointing it would undo that.
            print(
                f"\nREFUSED: {args.user} is already mapped to "
                f"{state['conflictingSubject']}. The mapping is one-to-one on "
                f"purpose. An operator must decide which identity is correct and "
                f"remove the other deliberately.",
                file=sys.stderr,
            )
            return 2

        if not state["publicProject"] or not state["publicUser"]:
            print(
                "\nREFUSED: the project or the active user does not exist on the "
                "business side. Create them through the API first; this tool "
                "links what exists and does not invent accounts.",
                file=sys.stderr,
            )
            return 2

        if args.check:
            missing = [k for k, v in state.items() if k != "conflictingSubject" and not v]
            print(f"\n{len(missing)} link(s) missing" if missing else "\nfully linked")
            return 1 if missing else 0

        done = apply(
            conn,
            tenant=args.tenant,
            project=args.project,
            user=args.user,
            subject=subject,
        )
        conn.commit()
        print("\napplied:")
        for line in done:
            print(f"  - {line}")
        print(
            "\nThe workspace tool choice and the node's installed tools are not "
            "set here: one belongs to whoever runs the work, the other to the "
            "machine. Check /v1/workspaces/{id}/execution-readiness."
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
