"""What an operational database actually holds, and what it still needs.

Preparing this platform for real use is not one switch. A person who can log in
still cannot request work; a project that exists is deliberately not linked to
the execution kernel; a node that is registered offers nothing until an
administrator says how much. Each of those is a separate operational input from
a different person, and the failure mode is always the same — somebody is told
"you do not have permission" when the truth is "nobody has supplied that input
yet".

So this reports three things, kept apart on purpose:

``inputs``
    What operational input exists and what is absent, each absent one named with
    **who supplies it**. Absent is not the same as denied.
``grants``
    The grant intersection for a user in a project. Four separate records must
    agree before that person may request work, and this says which one refuses.
``admission``
    Observed gates only; open gates do not establish execution admission. This is not a
    grant.** A user holding every grant is still refused while the kill switch
    is on or no node is online, and reading the two as one number is how an
    operator spends an afternoon re-granting permissions that were never the
    problem.

It also compares the recorded offer with the offer the kernel actually holds.
Those are two rows in two schemas and they can disagree, so "the administrator
set 4 cores" and "the kernel will lease 4 cores" are different claims.

Default reads use a read-only, repeatable-read transaction. --snapshot is an
explicit operator write of a historical observation, serialized per tenant/user/project.
--acceptance-evidence reads the existing AC-12 catalog in the same snapshot,
without certifying physical recovery or off-site evidence. Exit zero reports no missing
observed inputs or grants; it does not authorize a run or certify readiness.

Usage:
    python tools/operational_readiness.py --dsn-env INV_READINESS_DSN --tenant UUID
        [--project prj_...] [--user usr_...] [--json]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
SNAPSHOT_CONTRACT = "permission-observation-v1"

#: Who supplies each operational input. The point of naming them is that an
#: absent input has an owner, and telling somebody "permission denied" when the
#: real answer is "your operator has not linked this project" wastes their time
#: and teaches them the system is arbitrary.
OPERATOR = "operator (schema owner)"
PROJECT_OWNER = "project owner"
NODE_OWNER = "node owner"

#: Which project roles may request work and which may approve it. Held here so
#: that "is a member" and "may do the thing" stay separate questions — the first
#: version conflated them and reported a viewer as having nothing wrong.
CAN_REQUEST = ("owner", "maintainer", "operator")
CAN_APPROVE = ("owner", "approver")


def _scalar(conn, sql: str, params: tuple = ()) -> Any:
    row = conn.execute(sql, params).fetchone()
    return None if row is None else row[0]


def _rows(conn, sql: str, params: tuple = ()) -> list[tuple]:
    return conn.execute(sql, params).fetchall()


def _capability_columns(conn) -> list[str]:
    """Which ``can_*`` columns ``inv.operator_grants`` actually has.

    Read from the catalogue rather than hardcoded: the set differs between
    branches (``can_git`` arrives with the remote Git work), and a tool that
    assumes a column silently reports nothing about the ones it does not know.
    """
    return [
        name
        for (name,) in _rows(
            conn,
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='inv' AND table_name='operator_grants' "
            "AND column_name LIKE 'can\\_%%' ORDER BY column_name",
        )
    ]


def inputs(conn, tenant: str) -> dict[str, Any]:
    """Every operational input this tenant needs, present or absent."""
    found: list[dict[str, Any]] = []

    def record(name: str, count: int, owner: str, needed: str) -> None:
        found.append(
            {
                "input": name,
                "count": count,
                "present": count > 0,
                "suppliedBy": owner,
                "whatItIs": needed,
            }
        )

    record(
        "recovery epoch",
        1 if _scalar(conn, "SELECT count(*) FROM inv.control_epoch WHERE singleton") else 0,
        OPERATOR,
        "the kernel refuses every command until a recovery epoch exists",
    )
    record(
        "active users",
        _scalar(
            conn,
            "SELECT count(*) FROM public.users WHERE tenant_id=%s AND status='active'",
            (tenant,),
        ),
        OPERATOR,
        "a person who can sign in",
    )
    record(
        "OIDC subjects on those users",
        _scalar(
            conn,
            "SELECT count(*) FROM public.users WHERE tenant_id=%s AND status='active' "
            "AND external_subject IS NOT NULL",
            (tenant,),
        ),
        OPERATOR,
        "the subject a token carries, derived from issuer and sub",
    )
    record(
        "kernel subject mappings",
        _scalar(
            conn,
            "SELECT count(*) FROM inv.business_subjects WHERE tenant_id=%s AND enabled",
            (tenant,),
        ),
        OPERATOR,
        "one subject to one user, so one person cannot hold two voting identities",
    )
    record(
        "projects",
        _scalar(conn, "SELECT count(*) FROM public.projects WHERE tenant_id=%s", (tenant,)),
        PROJECT_OWNER,
        "somewhere for work to belong",
    )
    record(
        "projects linked to the kernel",
        _scalar(
            conn,
            "SELECT count(*) FROM inv.business_projects WHERE tenant_id=%s AND enabled",
            (tenant,),
        ),
        OPERATOR,
        "creating a project deliberately does not let the kernel act on it",
    )
    record(
        "ready workspaces",
        _scalar(
            conn,
            "SELECT count(*) FROM public.workspaces WHERE tenant_id=%s "
            "AND status='ready' AND deleted_at IS NULL",
            (tenant,),
        ),
        PROJECT_OWNER,
        "a workspace whose storage is provisioned",
    )
    record(
        "registered nodes",
        _scalar(
            conn,
            "SELECT count(*) FROM public.nodes WHERE tenant_id=%s AND status='active'",
            (tenant,),
        ),
        NODE_OWNER,
        "a machine that has enrolled",
    )
    record(
        "nodes the kernel knows",
        _scalar(conn, "SELECT count(*) FROM inv.nodes WHERE tenant_id=%s", (tenant,)),
        OPERATOR,
        "the kernel's own record of that machine",
    )
    record(
        "contributed folders (active)",
        _scalar(
            conn,
            "SELECT count(*) FROM public.storage_contributions "
            "WHERE tenant_id=%s AND status='active'",
            (tenant,),
        ),
        NODE_OWNER,
        "a folder its owner has explicitly offered; nothing is taken by default",
    )
    record(
        "declared capabilities",
        _scalar(
            conn,
            "SELECT count(*) FROM public.node_capabilities WHERE tenant_id=%s",
            (tenant,),
        ),
        NODE_OWNER,
        "what the machine reports it has",
    )
    record(
        "current resource offers",
        _scalar(
            conn,
            "SELECT count(*) FROM public.resource_offers "
            "WHERE tenant_id=%s AND effective_to IS NULL",
            (tenant,),
        ),
        OPERATOR,
        "how much of that capability may actually be used",
    )
    return {"inputs": found, "absent": [i for i in found if not i["present"]]}


def offers(conn, tenant: str) -> dict[str, Any]:
    """The recorded offer against the offer the kernel holds.

    Two rows in two schemas describe one number. ``public.resource_offers`` is
    what an administrator set and what the UI shows; ``inv.resources.offered``
    is what a reservation is actually measured against. They are written by one
    function and can still end up different, and when they do the symptom is a
    refusal quoting a number nobody recognises — so it is worth naming as its
    own check rather than discovering it from a failed run.
    """
    rows = _rows(
        conn,
        """
        SELECT c.capability_id, c.node_id, c.kind, c.unit, o.offered_quantity,
               coalesce((
                   SELECT sum(r.offered) FROM inv.resources r
                   WHERE r.tenant_id = c.tenant_id AND r.node_id = c.node_id
                     AND r.kind = CASE c.kind WHEN 'cpu' THEN 'cpu'
                                              WHEN 'ram' THEN 'memory'
                                              WHEN 'disk' THEN 'storage'
                                              ELSE c.kind END
               ), 0) AS kernel_offered
        FROM public.node_capabilities c
        JOIN public.resource_offers o
          ON o.tenant_id = c.tenant_id AND o.capability_id = c.capability_id
         AND o.effective_to IS NULL
        WHERE c.tenant_id = %s
        ORDER BY c.capability_id
        """,
        (tenant,),
    )
    compared = []
    for capability, node, kind, unit, recorded, kernel_offered in rows:
        compared.append(
            {
                "capabilityId": capability,
                "nodeId": node,
                "kind": kind,
                "unit": unit,
                "recordedOffer": int(recorded),
                "kernelOffer": int(kernel_offered),
                "agrees": int(recorded) == int(kernel_offered),
            }
        )
    # A GPU offer is recorded and deliberately not applied to the kernel, so it
    # is reported rather than counted as a disagreement to chase.
    return {
        "offers": compared,
        "disagreeing": [c for c in compared if not c["agrees"] and c["kind"] != "gpu"],
        "recordedNotApplied": [c for c in compared if c["kind"] == "gpu"],
    }


def grants(conn, tenant: str, project: str, user: str, columns: list[str]) -> dict[str, Any]:
    """Which record refuses this person, layer by layer.

    Four separate records have to agree, written by different people at
    different times, and any one of them says no on its own. Reporting only the
    final answer sends somebody to change the wrong one.
    """
    layers: list[dict[str, Any]] = []

    role = _scalar(
        conn,
        "SELECT role_code FROM public.project_members "
        "WHERE tenant_id=%s AND project_id=%s AND user_id=%s",
        (tenant, project, user),
    )
    layers.append(
        {
            "layer": "project membership",
            # Membership and capability are different failures with different
            # remedies: "add them to the project" versus "change their role".
            # Reporting only membership called a viewer fine.
            "holds": role is not None,
            "value": role,
            "grantedBy": PROJECT_OWNER,
            "means": "the role decides whether this person may request or approve",
        }
    )
    layers.append(
        {
            "layer": "role permits requesting work",
            "holds": role in CAN_REQUEST,
            "value": {"role": role, "rolesThatMayRequest": list(CAN_REQUEST)},
            "grantedBy": PROJECT_OWNER,
            "means": "being in a project is not the same as being able to run work in it",
        }
    )

    subject = _scalar(
        conn,
        "SELECT external_subject FROM public.users "
        "WHERE tenant_id=%s AND user_id=%s AND status='active'",
        (tenant, user),
    )
    mapped = _scalar(
        conn,
        "SELECT subject_id FROM inv.business_subjects "
        "WHERE tenant_id=%s AND user_id=%s AND enabled",
        (tenant, user),
    )
    layers.append(
        {
            "layer": "kernel subject mapping",
            # Both must exist *and* agree. A mapping that points at a different
            # subject than the token carries authenticates nobody, and it is the
            # shape a stale re-provisioning leaves behind.
            "holds": subject is not None and mapped is not None and subject == mapped,
            "value": {"onUser": subject, "inKernel": mapped},
            "grantedBy": OPERATOR,
            "means": "approval identity, one subject to one user",
        }
    )

    linked = _scalar(
        conn,
        "SELECT enabled FROM inv.business_projects WHERE tenant_id=%s AND project_id=%s",
        (tenant, project),
    )
    layers.append(
        {
            "layer": "project linked to kernel",
            "holds": bool(linked),
            "value": linked,
            "grantedBy": OPERATOR,
            "means": "the kernel acts only on projects an operator has linked",
        }
    )

    operator_row = None
    if subject is not None and columns:
        operator_row = conn.execute(
            "SELECT enabled, person_id, "
            + ", ".join(columns)
            + " FROM inv.operator_grants WHERE tenant_id=%s AND subject_id=%s",
            (tenant, subject),
        ).fetchone()
    capabilities = (
        {name: bool(operator_row[index + 2]) for index, name in enumerate(columns)}
        if operator_row
        else {}
    )
    layers.append(
        {
            "layer": "operator grants",
            # person_id is part of the record, not decoration: an operator grant
            # with no person behind it cannot satisfy a two-person rule.
            "holds": bool(operator_row and operator_row[0] and operator_row[1] is not None),
            "value": capabilities,
            "operatorEnabled": bool(operator_row and operator_row[0]),
            "operatorPersonId": str(operator_row[1]) if operator_row and operator_row[1] else None,
            "grantedBy": OPERATOR,
            "means": "privileged operations, each named separately",
        }
    )

    admin = {
        permission: bool(enabled)
        for permission, enabled in _rows(
            conn,
            "SELECT permission, enabled FROM inv.business_admin_grants "
            "WHERE tenant_id=%s AND user_id=%s",
            (tenant, user),
        )
    }
    layers.append(
        {
            "layer": "business administration",
            "holds": any(admin.values()),
            "value": admin,
            "grantedBy": OPERATOR,
            "means": "administering resources and accounts, separate from using them",
        }
    )

    refusing = [layer["layer"] for layer in layers if not layer["holds"]]
    return {
        "projectId": project,
        "userId": user,
        "layers": layers,
        "refusedBy": refusing,
        # Diagnostic intersection only; the kernel must authorize each operation.
        "observedRequestGrantsHold": not refusing and role in CAN_REQUEST,
        "mayRequestWork": None,
        "mayApprove": None,
        "mayApproveAsOperator": None,
        "observedOperatorApprovalCapability": bool(
            operator_row
            and operator_row[0]
            and operator_row[1] is not None
            and capabilities.get("can_approve")
            and subject is not None
            and mapped == subject
        ),
        "scope": "diagnostic-not-authorization",
        "unverified": [
            "current project grant",
            "operation-specific capability",
            "two-person approval",
        ],
        "observedApprovalGrantsHold": not [
            layer["layer"]
            for layer in layers
            if not layer["holds"] and layer["layer"] != "role permits requesting work"
        ]
        and role in CAN_APPROVE,
    }


def admission(conn, tenant: str) -> dict[str, Any]:
    """Whether the kernel would admit a run — which is not a permission.

    Every gate here can refuse a person who holds every grant in the section
    above, and none of them is fixed by granting anything. They are separated so
    that "you cannot run this" comes with the true reason.
    """
    gates: list[dict[str, Any]] = []

    kill = _scalar(
        conn, "SELECT kill_switch FROM inv.tenant_controls WHERE tenant_id=%s", (tenant,)
    )
    gates.append(
        {
            "gate": "kill switch",
            "open": kill is False,
            "value": kill,
            "means": (
                "no tenant_controls row yet"
                if kill is None
                else (
                    "execution is stopped for this tenant"
                    if kill
                    else "kill switch is off; other admission checks remain"
                )
            ),
        }
    )

    epoch = _scalar(conn, "SELECT epoch FROM inv.control_epoch WHERE singleton")
    gates.append(
        {
            "gate": "recovery epoch",
            "open": epoch is not None,
            "value": str(epoch) if epoch else None,
            "means": "commands carry the epoch they were issued under",
        }
    )

    # An observed node, not proof of a schedulable execution profile: online, and
    # with a heartbeat recent enough that it is still the same machine.
    live = _scalar(
        conn,
        "SELECT count(*) FROM inv.nodes WHERE tenant_id=%s AND status='online' "
        "AND recovery_epoch = (SELECT epoch FROM inv.control_epoch WHERE singleton) "
        "AND heartbeat_at >= clock_timestamp() - interval '15 seconds'",
        (tenant,),
    )
    gates.append(
        {
            "gate": "a live node on the current epoch",
            "open": bool(live),
            "value": live,
            "means": "a stale or old-epoch node is not a place to run work",
        }
    )

    offered = _scalar(
        conn,
        "SELECT coalesce(sum(offered),0) FROM inv.resources WHERE tenant_id=%s",
        (tenant,),
    )
    gates.append(
        {
            "gate": "capacity offered to the kernel",
            "open": bool(offered),
            "value": int(offered or 0),
            "means": "registered capacity is not offered capacity",
        }
    )

    closed = [gate["gate"] for gate in gates if not gate["open"]]
    return {
        "gates": gates,
        "closed": closed,
        "observedGatesOpen": not closed,
        "wouldAdmit": False if closed else None,
        "scope": "diagnostic-not-execution-admission",
        "unverified": [
            "execution profile",
            "project placement",
            "workload reservations",
            "approval and current dispatch authorization",
        ],
    }


def _collect(conn, args):
    observed = conn.execute("SELECT transaction_timestamp()").fetchone()[0]
    result: dict[str, Any] = {"tenant": args.tenant, "observedAt": observed.isoformat()}
    result.update(inputs(conn, args.tenant))
    result["offerAgreement"] = offers(conn, args.tenant)
    result["admission"] = admission(conn, args.tenant)
    if args.project and args.user:
        result["grants"] = grants(
            conn, args.tenant, args.project, args.user, _capability_columns(conn)
        )
    return result


def _snapshot_lock_key(args):
    scope = json.dumps(
        [SNAPSHOT_CONTRACT, args.tenant, args.project, args.user], separators=(",", ":")
    )
    return int.from_bytes(hashlib.sha256(scope.encode()).digest()[:8], "big", signed=True)


def _acceptance_evidence(session, args, result):
    if not getattr(args, "acceptance_evidence", False):
        return
    import datetime as dt
    import uuid
    from saintvision.services import pilot

    result["acceptanceEvidence"] = pilot.pilot_readiness(
        session,
        tenant_id=uuid.UUID(args.tenant),
        now=dt.datetime.fromisoformat(result["observedAt"]),
        release_id=getattr(args, "release", None),
    )


def _catalog_report(args):
    import uuid
    from psycopg.conninfo import conninfo_to_dict
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import URL
    from sqlalchemy.orm import Session
    from saintvision.db.session import tenant_scope

    engine = create_engine(
        URL.create("postgresql+psycopg"),
        connect_args=conninfo_to_dict(args.dsn),
        isolation_level="REPEATABLE READ",
        future=True,
    )
    try:
        with Session(engine) as session:
            with session.begin():
                session.execute(text("SET TRANSACTION READ ONLY"))
                with tenant_scope(session, uuid.UUID(args.tenant)):
                    result = _collect(session.connection().connection.driver_connection, args)
                    _acceptance_evidence(session, args, result)
            return result
    finally:
        engine.dispose()


def _snapshot_report(args):
    """Lock before opening the observation snapshot; one transaction records it.

    The dedicated lock transaction ends on every path, including commit
    errors. Hash collisions only serialize unrelated observers. This collector
    coordinates with itself; older unversioned writers are excluded from its
    comparisons. It never claims to freeze production authorization changes.
    """
    import datetime as dt
    import uuid
    import psycopg
    from psycopg.conninfo import conninfo_to_dict
    from sqlalchemy import create_engine, select
    from sqlalchemy.engine import URL
    from sqlalchemy.orm import Session
    from saintvision.db.models import PermissionSnapshot
    from saintvision.db.session import tenant_scope
    from saintvision.services import pilot

    tenant = uuid.UUID(args.tenant)
    args.tenant = str(tenant)
    if not args.project or not args.user:
        raise ValueError("Snapshot requires project and user")
    # No application runtime credential can promote itself to a snapshot writer.
    with psycopg.connect(args.dsn, connect_timeout=5) as lock:
        allowed = lock.execute("""SELECT r.rolsuper OR pg_has_role(current_user,d.datdba,'USAGE')
            FROM pg_roles r CROSS JOIN pg_database d
            WHERE r.rolname=current_user AND d.datname=current_database()""").fetchone()
        if not allowed or not allowed[0]:
            raise PermissionError("Operator database role required")
        lock.execute("SET LOCAL lock_timeout='5s'")
        lock.execute("SELECT pg_advisory_xact_lock(%s)", (_snapshot_lock_key(args),))
        engine = create_engine(
            URL.create("postgresql+psycopg"),
            connect_args=conninfo_to_dict(args.dsn),
            isolation_level="REPEATABLE READ",
            future=True,
        )
        try:
            with Session(engine, expire_on_commit=False) as session:
                with session.begin():
                    with tenant_scope(session, tenant):
                        raw = session.connection().connection.driver_connection
                        exists = raw.execute(
                            """SELECT
                            EXISTS(SELECT 1 FROM public.users WHERE tenant_id=%s AND user_id=%s),
                            EXISTS(SELECT 1 FROM public.projects WHERE tenant_id=%s AND project_id=%s)""",
                            (tenant, args.user, tenant, args.project),
                        ).fetchone()
                        if not exists or not all(exists):
                            raise ValueError("Snapshot subject or project absent in tenant")
                        result = _collect(raw, args)
                        _acceptance_evidence(session, args, result)
                        marker = {"contract": SNAPSHOT_CONTRACT, "projectId": args.project}
                        previous = session.scalars(
                            select(PermissionSnapshot)
                            .where(
                                PermissionSnapshot.tenant_id == tenant,
                                PermissionSnapshot.subject_type == "user",
                                PermissionSnapshot.subject_id == args.user,
                                PermissionSnapshot.grants.contains([marker]),
                            )
                            .order_by(
                                PermissionSnapshot.taken_at.desc(),
                                PermissionSnapshot.snapshot_id.desc(),
                            )
                            .limit(1)
                        ).first()
                        observed = dt.datetime.fromisoformat(result["observedAt"])
                        # Reject clock rollback instead of silently reordering history.
                        if previous is not None and observed <= previous.taken_at:
                            raise ValueError("Observation clock did not advance")
                        payload = [marker] + [dict(layer) for layer in result["grants"]["layers"]]
                        taken = pilot.take_permission_snapshot(
                            session,
                            tenant_id=tenant,
                            subject_type="user",
                            subject_id=args.user,
                            grants=payload,
                            now=observed,
                        )
                        receipt = dict(
                            snapshotId=taken.snapshot_id,
                            digest=taken.digest_sha256,
                            previousSnapshotId=previous.snapshot_id if previous else None,
                            previousDigest=previous.digest_sha256 if previous else None,
                            changed=(
                                None
                                if previous is None
                                else previous.digest_sha256 != taken.digest_sha256
                            ),
                            contract=SNAPSHOT_CONTRACT,
                            projectId=args.project,
                            observedAt=result["observedAt"],
                            scope="historical-observation-not-authorization",
                        )
                # Do not expose a receipt for a rolled-back transaction.
                result["permissionSnapshot"] = receipt
                return result
        finally:
            engine.dispose()


def report(args) -> dict[str, Any]:
    import psycopg

    if getattr(args, "snapshot", False):
        return _snapshot_report(args)
    if getattr(args, "acceptance_evidence", False):
        return _catalog_report(args)
    with psycopg.connect(args.dsn, connect_timeout=5) as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        conn.execute("SELECT set_config('inv.tenant_id', %s, true)", (args.tenant,))
        result = _collect(conn, args)
    return result


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse's default includes rejected values, which may be credentials.
        self.exit(2, "Invalid readiness arguments; see --help.\n")


def _exit_code(result):
    evidence = result.get("acceptanceEvidence")
    return (
        1
        if (
            result["absent"]
            or result["offerAgreement"]["disagreeing"]
            or result.get("grants", {}).get("refusedBy", [])
            or (evidence is not None and evidence.get("evidenceComplete") is not True)
        )
        else 0
    )


def main() -> int:
    parser = SafeParser(description=__doc__, allow_abbrev=False)
    parser.add_argument(
        "--dsn-env",
        default="INV_READINESS_DSN",
        help="environment variable containing the operator DSN",
    )
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--project", help="report the grant intersection in this project")
    parser.add_argument("--user", help="the user to report it for")
    parser.add_argument(
        "--snapshot",
        action="store_true",
        help="operator-only: record a historical project permission observation",
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--acceptance-evidence",
        action="store_true",
        help="read the AC-12 record catalog; operating acceptance remains unassessed",
    )
    parser.add_argument("--release", help="release whose AC-12 acceptance record is compared")
    args = parser.parse_args()
    if args.release and not args.acceptance_evidence:
        parser.error("release requires acceptance evidence")
    if bool(args.project) != bool(args.user):
        parser.error("--project and --user are given together or not at all")
    if args.snapshot and not args.project:
        parser.error("snapshot requires project and user")

    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", args.dsn_env):
        parser.error("invalid environment variable name")
    args.dsn = os.environ.get(args.dsn_env)
    if not args.dsn:
        parser.error("missing DSN environment variable")
    try:
        result = report(args)
    except Exception:
        print(json.dumps({"error": "operational_readiness_unavailable"}))
        return 2
    absent = result["absent"]
    disagreeing = result["offerAgreement"]["disagreeing"]
    refused = result.get("grants", {}).get("refusedBy", [])

    if args.json:
        print(json.dumps(result, indent=2, default=str))
        return _exit_code(result)

    print(f"tenant {args.tenant}\n")
    print("operational inputs")
    for item in result["inputs"]:
        mark = "ok     " if item["present"] else "ABSENT "
        print(f"  {mark} {item['input']}: {item['count']}")
        if not item["present"]:
            print(f"            supplied by {item['suppliedBy']} — {item['whatItIs']}")

    print("\nrecorded offer vs the offer the kernel holds")
    if not result["offerAgreement"]["offers"]:
        print("  (no capability has a current offer)")
    for entry in result["offerAgreement"]["offers"]:
        mark = "ok     " if entry["agrees"] else "DIFFERS"
        if entry["kind"] == "gpu" and not entry["agrees"]:
            mark = "held   "
        print(
            f"  {mark} {entry['capabilityId']} {entry['kind']}: "
            f"recorded {entry['recordedOffer']} {entry['unit']}, "
            f"kernel {entry['kernelOffer']}"
        )
    for entry in result["offerAgreement"]["recordedNotApplied"]:
        if not entry["agrees"]:
            print("            a GPU offer is recorded and not applied without a device mapping")
    for entry in disagreeing:
        print(
            "            the kernel will lease against its own number, so a refusal "
            "here quotes a figure the administrator never set"
        )

    if "grants" in result:
        g = result["grants"]
        print(f"\ngrant intersection for {g['userId']} in {g['projectId']}")
        for layer in g["layers"]:
            mark = "ok     " if layer["holds"] else "REFUSES"
            print(f"  {mark} {layer['layer']}: {layer['value']}")
            if not layer["holds"]:
                print(f"            granted by {layer['grantedBy']} — {layer['means']}")
        print(f"  may request work: {g['mayRequestWork']}")
        print(f"  may approve:      {g['mayApprove']}")

    if "permissionSnapshot" in result:
        taken = result["permissionSnapshot"]
        print(f"\npermission observation {taken['snapshotId']}")
        print(f"  observed at: {taken['observedAt']}")
        print(f"  changed within project: {taken['changed']}")
        print("  historical observation; current authorization remains unverified")

    print("\nobserved execution gates (admission remains unverified)")
    for gate in result["admission"]["gates"]:
        mark = "open   " if gate["open"] else "CLOSED "
        print(f"  {mark} {gate['gate']}: {gate['value']} — {gate['means']}")
    if result["admission"]["closed"]:
        print(
            "  a person holding every grant above is still refused while these "
            "are closed, and granting more permissions does not open them"
        )

    if "acceptanceEvidence" in result:
        evidence = result["acceptanceEvidence"]
        print(f"\nAC-12 record catalog complete: {evidence['catalogComplete']}")
        print("  operating acceptance: not assessed")
        for reason in evidence["blockers"] + evidence["unverified"]:
            print(f"  {reason}")
    return _exit_code(result)


if __name__ == "__main__":
    raise SystemExit(main())
