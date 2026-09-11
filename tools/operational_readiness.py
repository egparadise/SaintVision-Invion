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
    Whether the execution kernel would admit a run at all. **This is not a
    grant.** A user holding every grant is still refused while the kill switch
    is on or no node is online, and reading the two as one number is how an
    operator spends an afternoon re-granting permissions that were never the
    problem.

It also compares the recorded offer with the offer the kernel actually holds.
Those are two rows in two schemas and they can disagree, so "the administrator
set 4 cores" and "the kernel will lease 4 cores" are different claims.

Reading is the default and is safe against production; it makes no decision it
does not show the evidence for. ``--snapshot`` is the one action that writes, and
it is opt-in for that reason: it files the grant intersection as a
``PermissionSnapshot`` so that "who could do what" is an artefact rather than a
memory, and reports whether the digest has moved since the last one. That is what
re-verifying permissions means in practice — comparing today against the state
that was accepted.

Usage:
    python tools/operational_readiness.py --dsn DSN --tenant UUID
        [--project prj_...] [--user usr_...] [--json]
        [--snapshot --performed-by usr_...]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

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
        "disagreeing": [
            c for c in compared if not c["agrees"] and c["kind"] != "gpu"
        ],
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
        # The intersection, which is the only thing that answers "can they work".
        "mayRequestWork": not refusing and role in CAN_REQUEST,
        # Two different authorities, reported separately because they are.
        # Business approval comes from the project role. Privileged operator
        # voting comes from inv.operator_grants.can_approve, which is what
        # workspace_git's _actor checks before it will count a vote. The first
        # version returned one "mayApprove" from the role alone, and reported
        # True for somebody whose operator grant said can_approve is false.
        # Collapsing them overstated what a person could do.
        "mayApproveInProject": not [
            layer["layer"] for layer in layers
            if not layer["holds"] and layer["layer"] != "role permits requesting work"
        ] and role in CAN_APPROVE,
        "mayApproveAsOperator": bool(capabilities.get("can_approve")),
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
                else "execution is stopped for this tenant"
                if kill
                else "execution is permitted"
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

    # A node the kernel will place work on: online, on the current epoch, and
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
    return {"gates": gates, "closed": closed, "wouldAdmit": not closed}


def snapshot_permissions(args, grants: dict[str, Any]) -> dict[str, Any]:
    """File the grant intersection, and say whether it moved.

    Written from the **same** computation the report printed, not a second pass
    over the database. A snapshot assembled independently would drift from the
    report beside it, and the first anyone would learn of the drift is while
    comparing two snapshots during an incident.

    The recorder is ``pilot.take_permission_snapshot``, which has existed since
    S12 and had no caller — the service knew how to file a snapshot and nothing
    knew how to collect one. This supplies the collector rather than adding a
    second recorder.
    """
    import datetime as dt
    import uuid as _uuid

    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker

    from saintvision.db.models import PermissionSnapshot
    from saintvision.db.session import tenant_scope
    from saintvision.services import pilot as pilot_service

    tenant = _uuid.UUID(args.tenant)
    # The project belongs in the payload: one person holds different grants in
    # different projects, and the model records a subject, not a subject here.
    payload = [
        {"projectId": grants["projectId"], "layer": layer["layer"], "holds": layer["holds"],
         "value": layer["value"]}
        for layer in grants["layers"]
    ]
    # SQLAlchemy picks psycopg2 for a bare "postgresql://"; this project uses
    # psycopg 3 and the driver has to be named for it.
    url = args.dsn
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    engine = create_engine(url, future=True)
    factory = sessionmaker(engine, future=True, expire_on_commit=False)
    try:
        with factory() as session:
            with session.begin():
                with tenant_scope(session, tenant):
                    previous = session.scalars(
                        select(PermissionSnapshot)
                        .where(
                            PermissionSnapshot.tenant_id == tenant,
                            PermissionSnapshot.subject_type == "user",
                            PermissionSnapshot.subject_id == grants["userId"],
                        )
                        .order_by(PermissionSnapshot.taken_at.desc())
                        .limit(1)
                    ).first()
                    before = previous.digest_sha256 if previous else None
                    taken = pilot_service.take_permission_snapshot(
                        session,
                        tenant_id=tenant,
                        subject_type="user",
                        subject_id=grants["userId"],
                        grants=payload,
                        now=dt.datetime.now(dt.timezone.utc),
                    )
                    return {
                        "snapshotId": taken.snapshot_id,
                        "digest": taken.digest_sha256,
                        "previousDigest": before,
                        # None means there is nothing to compare against yet,
                        # which is not the same as "unchanged".
                        "changed": None if before is None else before != taken.digest_sha256,
                    }
    finally:
        engine.dispose()


def acceptance_evidence(args) -> dict[str, Any]:
    """The evidence AC-12 asks for, and which of it does not exist yet.

    Calls ``pilot.pilot_readiness``, which has had no caller since S12 — the
    aggregation existed and nothing ever asked it the question. Reported before
    a release manifest exists, because the gaps it names (no passing drill, no
    verified backup, no off-site copy, folders nobody has checked) are the ones
    worth closing *before* a release is cut, not after.
    """
    import datetime as dt
    import uuid as _uuid

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from saintvision.db.session import tenant_scope
    from saintvision.services import pilot as pilot_service

    url = args.dsn
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    engine = create_engine(url, future=True)
    factory = sessionmaker(engine, future=True, expire_on_commit=False)
    tenant = _uuid.UUID(args.tenant)
    try:
        with factory() as session:
            with session.begin():
                with tenant_scope(session, tenant):
                    return pilot_service.pilot_readiness(
                        session,
                        tenant_id=tenant,
                        now=dt.datetime.now(dt.timezone.utc),
                        release_id=args.release or None,
                    )
    finally:
        engine.dispose()


def report(args) -> dict[str, Any]:
    import psycopg

    with psycopg.connect(args.dsn) as conn:
        conn.execute("SELECT set_config('inv.tenant_id', %s, false)", (args.tenant,))
        result: dict[str, Any] = {"tenant": args.tenant}
        result.update(inputs(conn, args.tenant))
        result["offerAgreement"] = offers(conn, args.tenant)
        result["admission"] = admission(conn, args.tenant)
        if args.project and args.user:
            result["grants"] = grants(
                conn, args.tenant, args.project, args.user, _capability_columns(conn)
            )
    if args.snapshot and "grants" in result:
        result["permissionSnapshot"] = snapshot_permissions(args, result["grants"])
    if args.acceptance_evidence:
        result["acceptanceEvidence"] = acceptance_evidence(args)
    return result


def _exit_code(result: dict[str, Any]) -> int:
    """One rule for both output modes.

    The JSON branch and the printed branch each had their own expression, and
    they disagreed the moment acceptance evidence was added: a run that listed
    every AC-12 blocker still exited 0 under --json. Two copies of a pass rule
    drift, and the drift is invisible because each copy looks right where it
    sits.
    """
    evidence = result.get("acceptanceEvidence")
    return (
        1
        if result["absent"]
        or result["offerAgreement"]["disagreeing"]
        or result.get("grants", {}).get("refusedBy", [])
        or (evidence is not None and not evidence["evidenceComplete"])
        else 0
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", required=True, help="schema owner DSN")
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--project", help="report the grant intersection in this project")
    parser.add_argument("--user", help="the user to report it for")
    parser.add_argument(
        "--snapshot",
        action="store_true",
        help=(
            "file the grant intersection as a PermissionSnapshot and report "
            "whether its digest moved since the last one. This writes"
        ),
    )
    parser.add_argument(
        "--acceptance-evidence",
        action="store_true",
        help="report the evidence AC-12 requires, and what is missing",
    )
    parser.add_argument(
        "--release",
        help=(
            "assess acceptance against this release manifest. Without it the "
            "acceptance side is reported as not assessed, which is not the same "
            "as satisfied"
        ),
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.release and not args.acceptance_evidence:
        parser.error("--release is only meaningful with --acceptance-evidence")
    if bool(args.project) != bool(args.user):
        parser.error("--project and --user are given together or not at all")
    if args.snapshot and not args.project:
        parser.error("--snapshot needs --project and --user: a snapshot is of a subject")

    result = report(args)
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
        print(f"  may request work:        {g['mayRequestWork']}")
        print(f"  may approve in project:  {g['mayApproveInProject']}")
        print(f"  may approve as operator: {g['mayApproveAsOperator']}")

    taken = result.get("permissionSnapshot")
    if taken:
        print(f"\npermission snapshot {taken['snapshotId']}")
        print(f"  digest   {taken['digest'][:16]}…")
        if taken["previousDigest"] is None:
            print("  no earlier snapshot for this subject; nothing to compare against")
        elif taken["changed"]:
            print(
                f"  CHANGED  from {taken['previousDigest'][:16]}… — what this "
                f"person can do is not what was last filed"
            )
        else:
            print("  unchanged from the previous snapshot")

    print("\nexecution admission (not a permission)")
    for gate in result["admission"]["gates"]:
        mark = "open   " if gate["open"] else "CLOSED "
        print(f"  {mark} {gate['gate']}: {gate['value']} — {gate['means']}")
    if result["admission"]["closed"]:
        print(
            "  a person holding every grant above is still refused while these "
            "are closed, and granting more permissions does not open them"
        )

    evidence = result.get("acceptanceEvidence")
    if evidence:
        print("\nacceptance evidence (AC-12)")
        if not evidence["acceptanceAssessed"]:
            print(
                "  acceptance NOT ASSESSED — no release named. This is not the "
                "same as accepted, and the evidence below cannot be complete "
                "without it."
            )
        for blocker in evidence["blockers"]:
            print(f"  MISSING  {blocker}")
        for drill in evidence["drillsMissingTargets"]:
            print(
                f"  MISSED   drill {drill['drillId']} passed but measured "
                f"RPO {drill['measuredRpoSeconds']}s / RTO "
                f"{drill['measuredRtoSeconds']}s against targets "
                f"{drill['targetRpoSeconds']}s / {drill['targetRtoSeconds']}s"
            )
        for folder in evidence["contributionsNeedingAttention"]:
            print(f"  FOLDER   {folder.get('normalizedPath')}: {folder.get('reason')}")
        for limitation in evidence["knownLimitations"]:
            print(f"  NOTED    known limitation: {limitation}")
        if not evidence["blockers"]:
            print("  every piece of evidence AC-12 names has been recorded")

    return _exit_code(result)


if __name__ == "__main__":
    raise SystemExit(main())
