"""Explicit operator-owned account links and project grants, in one transaction.

Set INV_PROVISION_DSN outside shell history; use --check before --apply.
Existing login subjects, disabled links/grants, roles and epochs are never changed.
This prepares account permissions; it does not admit a workload or prepare a Node.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/control-plane/src"))
from inv.identity import public_subject

SCOPES = {"request": (True, False), "approve": (False, True), "request-and-approve": (True, True)}


class ProvisioningRefused(ValueError):
    """A public, credential-free refusal reason."""


def identity(tenant, project, user, issuer, sub, grant):
    try:
        tenant = str(UUID(tenant))
        parsed = urlsplit(issuer)
        valid = (
            parsed.scheme == "https"
            and parsed.hostname
            and not parsed.username
            and not parsed.password
            and not parsed.query
            and not parsed.fragment
            and 1 <= len(issuer) <= 2048
            and 1 <= len(sub) <= 200
            and not any(ord(c) < 32 for c in issuer + sub)
            and re.fullmatch(r"prj_[0-9A-HJKMNP-TV-Z]{26}", project)
            and re.fullmatch(r"usr_[0-9A-HJKMNP-TV-Z]{26}", user)
            and grant in SCOPES
        )
        if not valid:
            raise ValueError()
    except (ValueError, TypeError):
        raise ProvisioningRefused(
            "Invalid explicit tenant/project/user/OIDC identity or grant scope"
        ) from None
    return dict(
        tenant=tenant, project=project, user=user, subject=public_subject(issuer, sub), grant=grant
    )


def _state(conn, *, tenant, project, user, subject, grant, lock=False):
    conn.execute("SELECT set_config('inv.tenant_id', %s, true)", (tenant,))
    suffix = " FOR SHARE" if lock else ""

    def one(query, values=()):
        return conn.execute(query + suffix, values).fetchone()

    epoch = one("SELECT epoch FROM inv.control_epoch WHERE singleton")
    permission = one(
        "SELECT enabled,can_request,can_approve FROM inv.project_grants WHERE tenant_id=%s AND project_id=%s AND subject_id=%s",
        (tenant, project, subject),
    )
    link = one(
        "SELECT enabled FROM inv.business_projects WHERE tenant_id=%s AND project_id=%s",
        (tenant, project),
    )
    public_project = one(
        "SELECT status FROM public.projects WHERE tenant_id=%s AND project_id=%s", (tenant, project)
    )
    mappings = conn.execute(
        "SELECT subject_id,user_id,enabled FROM inv.business_subjects WHERE tenant_id=%s AND (user_id=%s OR subject_id=%s) ORDER BY subject_id"
        + suffix,
        (tenant, user, subject),
    ).fetchall()
    account = one(
        "SELECT status,external_subject FROM public.users WHERE tenant_id=%s AND user_id=%s",
        (tenant, user),
    )
    member = one(
        "SELECT role_code FROM public.project_members WHERE tenant_id=%s AND project_id=%s AND user_id=%s",
        (tenant, project, user),
    )
    public_tenant = one("SELECT display_name FROM public.tenants WHERE tenant_id=%s", (tenant,))
    kernel_tenant = one("SELECT 1 FROM inv.tenants WHERE tenant_id=%s", (tenant,))
    kernel_project = one(
        "SELECT 1 FROM inv.projects WHERE tenant_id=%s AND project_id=%s", (tenant, project)
    )
    blockers = []
    if not epoch:
        blockers.append("Recovery epoch must already be provisioned separately")
    if not public_tenant:
        blockers.append("Business tenant does not exist")
    if not public_project or public_project[0] != "active":
        blockers.append("Active business project required")
    if not account or account != ("active", subject):
        blockers.append("Active account with the exact existing OIDC subject required")
    if mappings and (len(mappings) != 1 or mappings[0] != (subject, user, True)):
        blockers.append("Existing subject mapping conflicts or is disabled")
    if link and not link[0]:
        blockers.append("Existing project link is disabled")
    requested = SCOPES[grant]
    if permission and permission != (True, *requested):
        blockers.append("Existing grant is disabled or has a different scope")
    role = member[0] if member else None
    if requested[0] and role not in {"owner", "maintainer", "operator"}:
        blockers.append("Current project membership does not permit requesting")
    if requested[1] and role not in {"owner", "approver"}:
        blockers.append("Current project membership does not permit approving")
    missing = [
        name
        for name, present in (
            ("kernelTenant", kernel_tenant),
            ("kernelProject", kernel_project),
            ("businessProject", link),
            ("businessSubject", mappings),
            ("projectGrant", permission),
        )
        if not present
    ]
    return dict(
        scope="account-kernel-provisioning",
        tenantId=tenant,
        projectId=project,
        userId=user,
        subject=subject,
        grant=grant,
        role=role,
        epoch=str(epoch[0]) if epoch else None,
        blockers=blockers,
        missing=missing,
        linked=not blockers and not missing,
        executionReady=False,
    )


def inspect(conn, **target):
    """A read-only diagnostic. It is never authorization for a later apply."""
    with conn.transaction():
        conn.execute("SET TRANSACTION READ ONLY")
        return _state(conn, **target)


def apply(conn, *, reason, **target):
    """Recheck under locks, insert only missing rows, audit and commit atomically."""
    if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 300:
        raise ProvisioningRefused("An explicit operator reason (1-300 characters) is required")
    with conn.transaction():
        conn.execute("SET LOCAL lock_timeout = '5s'")
        # Serializes invocations, including two projects for one account.
        # Current service membership/status writers meet the row locks below.
        conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            ("account-provisioning:" + target["tenant"],),
        )
        state = _state(conn, **target, lock=True)
        if state["blockers"]:
            raise ProvisioningRefused("; ".join(state["blockers"]))
        tenant, project, user, subject = (
            target[k] for k in ("tenant", "project", "user", "subject")
        )
        missing = state["missing"]
        if "kernelTenant" in missing:
            conn.execute(
                "INSERT INTO inv.tenants(tenant_id,name) SELECT tenant_id,display_name FROM public.tenants WHERE tenant_id=%s",
                (tenant,),
            )
        if "kernelProject" in missing:
            conn.execute(
                "INSERT INTO inv.projects(tenant_id,project_id) VALUES(%s,%s)", (tenant, project)
            )
        if "businessProject" in missing:
            conn.execute(
                "INSERT INTO inv.business_projects(tenant_id,project_id) VALUES(%s,%s)",
                (tenant, project),
            )
        if "businessSubject" in missing:
            conn.execute(
                "INSERT INTO inv.business_subjects(tenant_id,subject_id,user_id) VALUES(%s,%s,%s)",
                (tenant, subject, user),
            )
        if "projectGrant" in missing:
            conn.execute(
                "INSERT INTO inv.project_grants(tenant_id,project_id,subject_id,can_request,can_approve) VALUES(%s,%s,%s,%s,%s)",
                (tenant, project, subject, *SCOPES[target["grant"]]),
            )
        audit = str(uuid4()) if missing else None
        if audit:
            conn.execute(
                "INSERT INTO inv.account_provisioning_events(tenant_id,event_id,project_id,user_id,subject_id,grant_scope,recovery_epoch,operator_name,reason,created_links) VALUES(%s,%s,%s,%s,%s,%s,%s,session_user,%s,%s::jsonb)",
                (
                    tenant,
                    audit,
                    project,
                    user,
                    subject,
                    target["grant"],
                    state["epoch"],
                    reason.strip(),
                    json.dumps(missing),
                ),
            )
        after = _state(conn, **target, lock=True)
        if not after["linked"]:
            raise ProvisioningRefused("Provisioning postcondition failed; transaction rolled back")
        return {**after, "changed": missing, "auditId": audit}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dsn-env",
        default="INV_PROVISION_DSN",
        help="environment variable holding the schema-owner DSN",
    )
    for name in ("tenant", "project", "user", "issuer", "sub"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--grant", choices=SCOPES, required=True)
    parser.add_argument("--reason")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    import psycopg

    try:
        target = identity(args.tenant, args.project, args.user, args.issuer, args.sub, args.grant)
        dsn = os.environ.get(args.dsn_env)
        if not dsn:
            raise ProvisioningRefused("Provisioning DSN environment variable is not configured")
        with psycopg.connect(dsn, autocommit=True) as conn:
            result = (
                apply(conn, reason=args.reason, **target) if args.apply else inspect(conn, **target)
            )
        print(json.dumps(result, ensure_ascii=True))
        return 0 if result["linked"] else 1
    except ProvisioningRefused as exc:
        print(json.dumps({"refused": str(exc)}), file=sys.stderr)
        return 2
    except psycopg.Error as exc:
        print(
            json.dumps(
                {
                    "refused": "Database operation failed; no partial provisioning committed",
                    "sqlstate": exc.sqlstate,
                }
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
