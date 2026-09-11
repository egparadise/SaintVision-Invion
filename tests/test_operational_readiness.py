"""Preparing a tenant for real use, and every way it is not ready.

The tool under test answers three different questions that operators routinely
hear as one: has anybody supplied this input, does this person's grant chain
allow the work, and would the kernel admit a run at all. Each case here is a
state the tool must refuse, because a readiness report that can only say "ready"
is worse than none — it sends people to change permissions that were never the
problem.
"""

from __future__ import annotations

import hashlib
import json
import random
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

pytestmark = pytest.mark.postgres

TOOL = Path(__file__).resolve().parents[1] / "tools" / "operational_readiness.py"
CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _id(prefix: str) -> str:
    return prefix + "_" + "".join(random.choice(CROCKFORD) for _ in range(26))


@pytest.fixture
def prepared(migrated, database_url):
    """A tenant with every operational input in place, and nothing more."""
    import psycopg

    dsn = database_url.replace("postgresql+psycopg://", "postgresql://")
    ids = {
        "tenant": str(uuid.uuid4()),
        "user": _id("usr"),
        "project": _id("prj"),
        "workspace": _id("wsp"),
        "node": _id("nod"),
        "capability": _id("cap"),
        "resource": _id("res"),
        "contribution": _id("stc"),
        "offer": _id("ofr"),
        "person": str(uuid.uuid4()),
        "epoch": str(uuid.uuid4()),
        "dsn": dsn,
    }
    # The subject a real token carries: sha256 over issuer and sub, not the sub
    # alone — two issuers may use the same sub for different people.
    ids["subject"] = "oidc:" + hashlib.sha256(
        b"https://login.example.internal\x00operator-1"
    ).hexdigest()
    t, u, p = ids["tenant"], ids["user"], ids["project"]

    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO inv.control_epoch(singleton,epoch) VALUES(true,%s) "
            "ON CONFLICT (singleton) DO UPDATE SET epoch=EXCLUDED.epoch",
            (ids["epoch"],),
        )
        conn.execute(
            "INSERT INTO public.tenants(tenant_id,slug,display_name) VALUES(%s,%s,'test')",
            (t, uuid.uuid4().hex[:12]),
        )
        conn.execute(
            "INSERT INTO public.users(tenant_id,user_id,external_subject,display_name,status) "
            "VALUES(%s,%s,%s,'Operator','active')",
            (t, u, ids["subject"]),
        )
        conn.execute(
            "INSERT INTO public.projects(tenant_id,project_id,code,display_name) "
            "VALUES(%s,%s,%s,'test project')",
            (t, p, uuid.uuid4().hex[:8]),
        )
        conn.execute(
            "INSERT INTO public.project_members(tenant_id,project_id,user_id,role_code) "
            "VALUES(%s,%s,%s,'owner')",
            (t, p, u),
        )
        conn.execute(
            "INSERT INTO public.workspaces"
            "(tenant_id,workspace_id,project_id,name,status,created_by_user_id) "
            "VALUES(%s,%s,%s,'ws','ready',%s)",
            (t, ids["workspace"], p, u),
        )
        conn.execute(
            "INSERT INTO public.nodes"
            "(tenant_id,node_id,hostname,os_type,os_version,agent_version,status) "
            "VALUES(%s,%s,'test-node','windows','11','1.0','active')",
            (t, ids["node"]),
        )
        conn.execute(
            "INSERT INTO public.node_capabilities"
            "(tenant_id,node_id,capability_id,kind,total_quantity,unit,divisible) "
            "VALUES(%s,%s,%s,'cpu',4000,'millicores',true)",
            (t, ids["node"], ids["capability"]),
        )
        conn.execute(
            "INSERT INTO public.resource_offers"
            "(tenant_id,offer_id,capability_id,offered_quantity,effective_from) "
            "VALUES(%s,%s,%s,2000,now())",
            (t, ids["offer"], ids["capability"]),
        )
        conn.execute(
            "INSERT INTO public.storage_contributions"
            "(tenant_id,contribution_id,node_id,declared_path,normalized_path,"
            "mode,status,registered_by_user_id) "
            "VALUES(%s,%s,%s,%s,'d:/inv-share','read_write','active',%s)",
            (t, ids["contribution"], ids["node"], r"D:\inv-share", u),
        )
        conn.execute("INSERT INTO inv.tenants(tenant_id,name) VALUES(%s,'test')", (t,))
        conn.execute("INSERT INTO inv.projects(tenant_id,project_id) VALUES(%s,%s)", (t, p))
        conn.execute(
            "INSERT INTO inv.business_projects(tenant_id,project_id,enabled) "
            "VALUES(%s,%s,true)",
            (t, p),
        )
        conn.execute(
            "INSERT INTO inv.business_subjects(tenant_id,subject_id,user_id,enabled) "
            "VALUES(%s,%s,%s,true)",
            (t, ids["subject"], u),
        )
        conn.execute(
            "INSERT INTO inv.operator_grants"
            "(tenant_id,subject_id,enabled,person_id,can_contain,can_resume,can_approve) "
            "VALUES(%s,%s,true,%s,true,true,true)",
            (t, ids["subject"], ids["person"]),
        )
        conn.execute(
            "INSERT INTO inv.business_admin_grants(tenant_id,user_id,permission,enabled) "
            "VALUES(%s,%s,'resources.manage',true)",
            (t, u),
        )
        # inv.tenants creates the controls row; this only makes the value explicit.
        conn.execute(
            "INSERT INTO inv.tenant_controls(tenant_id,kill_switch) VALUES(%s,false) "
            "ON CONFLICT (tenant_id) DO UPDATE SET kill_switch=false",
            (t,),
        )
        conn.execute(
            "INSERT INTO inv.nodes(tenant_id,node_id,status,recovery_epoch,heartbeat_at) "
            "VALUES(%s,%s,'online',%s,clock_timestamp())",
            (t, ids["node"], ids["epoch"]),
        )
        conn.execute(
            "INSERT INTO inv.resources VALUES(%s,%s,%s,'cpu',4000,2000)",
            (t, ids["resource"], ids["node"]),
        )
    return ids


def _run(ids, *extra: str) -> tuple[dict, int]:
    completed = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--dsn", ids["dsn"],
            "--tenant", ids["tenant"],
            "--project", ids["project"],
            "--user", ids["user"],
            "--json",
            *extra,
        ],
        capture_output=True,
        text=True,
    )
    assert completed.stdout, completed.stderr
    return json.loads(completed.stdout), completed.returncode


def _sql(ids, statement: str, params: tuple = ()) -> None:
    import psycopg

    with psycopg.connect(ids["dsn"], autocommit=True) as conn:
        conn.execute(statement, params)


def _beat(ids) -> None:
    """Refresh the heartbeat, which a real node does and a test must too."""
    _sql(
        ids,
        "UPDATE inv.nodes SET heartbeat_at=clock_timestamp() WHERE tenant_id=%s",
        (ids["tenant"],),
    )


def test_a_prepared_tenant_reports_ready(prepared) -> None:
    _beat(prepared)
    result, code = _run(prepared)
    assert result["absent"] == []
    assert result["grants"]["refusedBy"] == []
    assert result["grants"]["mayRequestWork"] is True
    assert result["admission"]["wouldAdmit"] is True
    assert code == 0


def test_an_empty_tenant_names_who_supplies_each_missing_input(prepared) -> None:
    prepared = {**prepared, "tenant": str(uuid.uuid4())}
    result, code = _run(prepared)
    assert code == 1
    absent = {item["input"]: item["suppliedBy"] for item in result["absent"]}
    # Absent is not denied, and each one has an owner who can supply it.
    assert absent["active users"] == "operator (schema owner)"
    assert absent["ready workspaces"] == "project owner"
    assert absent["contributed folders (active)"] == "node owner"


def test_membership_without_a_role_that_may_request_is_refused(prepared) -> None:
    """A viewer is a member. The first version of this tool called that fine."""
    _beat(prepared)
    _sql(
        prepared,
        "UPDATE public.project_members SET role_code='viewer' WHERE user_id=%s",
        (prepared["user"],),
    )
    result, code = _run(prepared)
    assert result["grants"]["refusedBy"] == ["role permits requesting work"]
    assert result["grants"]["mayRequestWork"] is False
    assert code == 1


def test_a_subject_the_kernel_does_not_share_is_refused(prepared) -> None:
    """The shape a stale re-provisioning leaves behind."""
    _beat(prepared)
    _sql(
        prepared,
        "UPDATE public.users SET external_subject='oidc:stale' WHERE user_id=%s",
        (prepared["user"],),
    )
    result, code = _run(prepared)
    # The operator grant is keyed by subject, so changing the subject orphans it
    # too. Both are reported, because fixing only one leaves the person refused.
    assert result["grants"]["refusedBy"] == ["kernel subject mapping", "operator grants"]
    assert code == 1


def test_an_unlinked_project_is_refused(prepared) -> None:
    _beat(prepared)
    _sql(
        prepared,
        "UPDATE inv.business_projects SET enabled=false WHERE project_id=%s",
        (prepared["project"],),
    )
    result, code = _run(prepared)
    assert result["grants"]["refusedBy"] == ["project linked to kernel"]
    assert code == 1


def test_a_disabled_operator_grant_is_refused(prepared) -> None:
    # Identity rows are immutable by trigger; disabling is the supported path,
    # so that is what an operator would actually do.
    _beat(prepared)
    _sql(
        prepared,
        "UPDATE inv.operator_grants SET enabled=false WHERE subject_id=%s",
        (prepared["subject"],),
    )
    result, code = _run(prepared)
    assert result["grants"]["refusedBy"] == ["operator grants"]
    assert code == 1


def test_a_revoked_folder_is_reported_absent(prepared) -> None:
    _beat(prepared)
    _sql(
        prepared,
        "UPDATE public.storage_contributions SET status='revoked', revoked_at=now() "
        "WHERE tenant_id=%s",
        (prepared["tenant"],),
    )
    result, code = _run(prepared)
    assert "contributed folders (active)" in [i["input"] for i in result["absent"]]
    assert code == 1


def test_every_grant_held_and_execution_still_refused(prepared) -> None:
    """The distinction the whole tool exists for.

    Nothing about this person's permissions is wrong, and no permission change
    fixes it. Reporting grants and admission as one number is how an operator
    spends an afternoon on the wrong problem.
    """
    _beat(prepared)
    _sql(
        prepared,
        "UPDATE inv.tenant_controls SET kill_switch=true WHERE tenant_id=%s",
        (prepared["tenant"],),
    )
    result, code = _run(prepared)
    assert result["grants"]["refusedBy"] == []
    assert result["grants"]["mayRequestWork"] is True
    assert "kill switch" in result["admission"]["closed"]
    assert result["admission"]["wouldAdmit"] is False
    assert code == 0, "a closed gate is not a grant failure, and is not reported as one"


def test_a_stale_node_closes_admission_without_touching_grants(prepared) -> None:
    _sql(
        prepared,
        "UPDATE inv.nodes SET heartbeat_at=clock_timestamp()-interval '5 minutes' "
        "WHERE tenant_id=%s",
        (prepared["tenant"],),
    )
    result, _ = _run(prepared)
    assert result["admission"]["closed"] == ["a live node on the current epoch"]
    assert result["grants"]["refusedBy"] == []


def test_the_recorded_offer_and_the_kernel_offer_must_agree(prepared) -> None:
    """Two rows in two schemas describe one number, and they can disagree.

    This is the state CL-01's F1 produces: the administrator set one figure,
    the kernel will lease against another, and a refusal quotes a number nobody
    recognises.
    """
    _beat(prepared)
    _sql(
        prepared,
        "UPDATE inv.resources SET offered=1800 WHERE tenant_id=%s",
        (prepared["tenant"],),
    )
    result, code = _run(prepared)
    (entry,) = result["offerAgreement"]["disagreeing"]
    assert (entry["recordedOffer"], entry["kernelOffer"]) == (2000, 1800)
    assert code == 1


def _snapshot_count(ids) -> int:
    import psycopg

    with psycopg.connect(ids["dsn"]) as conn:
        return conn.execute(
            "SELECT count(*) FROM public.permission_snapshots WHERE tenant_id=%s",
            (ids["tenant"],),
        ).fetchone()[0]


def test_a_report_without_snapshot_writes_nothing(prepared) -> None:
    """The default is a read. A tool that files a record while you are looking
    at it is not safe to point at production."""
    _beat(prepared)
    _run(prepared)
    assert _snapshot_count(prepared) == 0


def test_a_snapshot_has_nothing_to_compare_against_the_first_time(prepared) -> None:
    """Absent is not unchanged, and the first snapshot must not claim to be."""
    _beat(prepared)
    result, _ = _run(prepared, "--snapshot")
    taken = result["permissionSnapshot"]
    assert taken["previousDigest"] is None
    assert taken["changed"] is None
    assert _snapshot_count(prepared) == 1


def test_an_unchanged_grant_chain_digests_the_same(prepared) -> None:
    _beat(prepared)
    first, _ = _run(prepared, "--snapshot")
    second, _ = _run(prepared, "--snapshot")
    assert second["permissionSnapshot"]["digest"] == first["permissionSnapshot"]["digest"]
    assert second["permissionSnapshot"]["changed"] is False


def test_a_revoked_capability_moves_the_digest(prepared) -> None:
    """Re-verifying permissions means comparing today against what was filed."""
    _beat(prepared)
    _run(prepared, "--snapshot")
    _sql(
        prepared,
        "UPDATE inv.operator_grants SET can_approve=false WHERE subject_id=%s",
        (prepared["subject"],),
    )
    after, _ = _run(prepared, "--snapshot")
    assert after["permissionSnapshot"]["changed"] is True
    assert after["grants"]["mayApproveAsOperator"] is False


def test_project_approval_and_operator_approval_are_reported_apart(prepared) -> None:
    """They are different authorities and the first version collapsed them.

    A project owner whose operator grant says can_approve is false could still
    be reported as able to approve, which overstates what workspace_git would
    actually let them do.
    """
    _beat(prepared)
    _sql(
        prepared,
        "UPDATE inv.operator_grants SET can_approve=false WHERE subject_id=%s",
        (prepared["subject"],),
    )
    result, _ = _run(prepared)
    assert result["grants"]["mayApproveInProject"] is True
    assert result["grants"]["mayApproveAsOperator"] is False


def test_acceptance_evidence_names_what_is_missing(prepared) -> None:
    """A fresh deployment has none of AC-12's evidence, and says which.

    pilot_readiness has existed since S12 with no caller: the aggregation was
    written and nothing ever asked it the question.
    """
    _beat(prepared)
    result, code = _run(prepared, "--acceptance-evidence")
    evidence = result["acceptanceEvidence"]
    assert "no passing database recovery drill" in evidence["blockers"]
    assert "no verified backup" in evidence["blockers"]
    # ADR-018: local durability is not recovery from losing the domain.
    assert "no verified off-site backup" in evidence["blockers"]
    assert code == 1


def test_unassessed_acceptance_never_reads_as_accepted(prepared) -> None:
    """The distinction that keeps this honest before a release is cut."""
    _beat(prepared)
    result, _ = _run(prepared, "--acceptance-evidence")
    evidence = result["acceptanceEvidence"]
    assert evidence["acceptanceAssessed"] is False
    # Even with every other blocker cleared, the evidence cannot be complete
    # while acceptance has not been assessed at all.
    assert evidence["evidenceComplete"] is False


def test_recorded_evidence_clears_the_blockers_it_covers(prepared) -> None:
    """Evidence is what was recorded, so recording it is what closes a gap."""
    import datetime as dt
    import uuid

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from saintvision.db.session import tenant_scope
    from saintvision.services import pilot as pilot_service

    _beat(prepared)
    url = "postgresql+psycopg://" + prepared["dsn"][len("postgresql://") :]
    engine = create_engine(url, future=True)
    factory = sessionmaker(engine, future=True, expire_on_commit=False)
    tenant = uuid.UUID(prepared["tenant"])
    now = dt.datetime.now(dt.timezone.utc)
    try:
        with factory() as session:
            with session.begin():
                with tenant_scope(session, tenant):
                    backup = pilot_service.record_backup(
                        session,
                        tenant_id=tenant,
                        kind="logical",
                        location_ref="//nas/offsite/db.dump",
                        now=now,
                        off_site=True,
                        byte_size=1024,
                    )
                    pilot_service.verify_backup(
                        session,
                        tenant_id=tenant,
                        backup_id=backup.backup_id,
                        checksum_sha256="e" * 64,
                        now=now,
                    )
                    pilot_service.record_recovery_drill(
                        session,
                        tenant_id=tenant,
                        scope="database",
                        outcome="passed",
                        performed_by_user_id=prepared["user"],
                        now=now,
                        measurement=pilot_service.DrillMeasurement(
                            rpo_seconds=6, rto_seconds=6
                        ),
                        backup_id=backup.backup_id,
                        fencing_verified=True,
                        integrity_verified=True,
                    )
    finally:
        engine.dispose()

    result, _ = _run(prepared, "--acceptance-evidence")
    blockers = result["acceptanceEvidence"]["blockers"]
    assert "no passing database recovery drill" not in blockers
    assert "no verified backup" not in blockers
    assert "no verified off-site backup" not in blockers
    # The contributed folder is active and has never been health checked, which
    # is reported as needing attention rather than assumed fine.
    assert any("contributed folder" in b for b in blockers)
