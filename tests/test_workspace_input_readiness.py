"""Read actual pending input, not historical or another project's submission."""

import datetime as dt
import json
from uuid import uuid4

import pytest
from sqlalchemy import text

from saintvision.db.session import tenant_scope
from saintvision.ids import new_id
from saintvision.services.execution_readiness import workspace_readiness
from test_execution_readiness import lab, scene, NOW

pytestmark = pytest.mark.postgres


def pending(owner_engine, scene, *, project=None, run_id=None, created=None):
    t, p, w = scene["tenant_a"], project or scene["project_id"], scene["workspace_id"]
    run_id, start_id = run_id or new_id("run"), uuid4()
    with owner_engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO inv.control_epoch(singleton,epoch) VALUES(true,:e) ON CONFLICT DO NOTHING"
            ),
            {"e": uuid4()},
        )
        c.execute(
            text("INSERT INTO inv.tenants VALUES(:t,'input test') ON CONFLICT DO NOTHING"), {"t": t}
        )
        c.execute(
            text("INSERT INTO inv.projects VALUES(:t,:p) ON CONFLICT DO NOTHING"), {"t": t, "p": p}
        )
        c.execute(
            text("INSERT INTO inv.runs(tenant_id,project_id,run_id) VALUES(:t,:p,:r)"),
            {"t": t, "p": p, "r": run_id},
        )
        c.execute(
            text(
                """INSERT INTO inv.workspace_starts(tenant_id,project_id,run_id,start_id,workspace_id,
            step_id,requester_id,recovery_epoch,workload,snapshot,created_at)
            VALUES(:t,:p,:r,:s,:w,'python',:u,(SELECT epoch FROM inv.control_epoch WHERE singleton),
            CAST(:wl AS jsonb),:data,:created)"""
            ),
            {
                "t": t,
                "p": p,
                "r": run_id,
                "s": start_id,
                "w": w,
                "u": scene["owner"],
                "wl": json.dumps({"workspaceId": w, "workspaceStart": {"startId": str(start_id)}}),
                "data": b"bounded synthetic input",
                "created": created or NOW,
            },
        )
    return run_id


def read(app_sessionmaker, scene):
    with app_sessionmaker() as s, s.begin(), tenant_scope(s, scene["tenant_a"]):
        value = workspace_readiness(
            s,
            tenant_id=scene["tenant_a"],
            workspace_id=scene["workspace_id"],
            user_id=scene["owner"],
        )
    assert value["executable"] is False and value["admissionRequired"] is True
    return next(c for c in value["checks"] if c["check"] == "input_prepared")


def test_latest_pending_submission_is_selected_by_time(app_sessionmaker, owner_engine, scene):
    pending(owner_engine, scene, run_id="run_" + "Z" * 26, created=NOW)
    later = pending(
        owner_engine, scene, run_id="run_" + "0" * 26, created=NOW + dt.timedelta(seconds=1)
    )
    assert read(app_sessionmaker, scene)["runId"] == later


@pytest.mark.parametrize("reason", ["cancelled", "old-epoch", "different-project"])
def test_historical_or_unrelated_input_is_not_ready(app_sessionmaker, owner_engine, scene, reason):
    run_id = pending(
        owner_engine, scene, project=new_id("project") if reason == "different-project" else None
    )
    with owner_engine.begin() as c:
        if reason == "cancelled":
            c.execute(
                text("UPDATE inv.runs SET state='cancelled',version=version+1 WHERE run_id=:r"),
                {"r": run_id},
            )
        elif reason == "old-epoch":
            c.execute(text("UPDATE inv.control_epoch SET epoch=:e WHERE singleton"), {"e": uuid4()})
    value = read(app_sessionmaker, scene)
    assert not value["satisfied"] and value["runId"] is None and value["snapshotBytes"] is None
    assert value["maxSnapshotBytes"] == 65536 and value["maxContentBytes"] == 32768


@pytest.mark.parametrize("scope", ["different", "unset", "empty"])
def test_populated_input_cannot_be_read_from_another_session_scope(
    app_sessionmaker, owner_engine, scene, two_tenants, scope
):
    pending(owner_engine, scene)
    with app_sessionmaker() as s, s.begin():
        if scope != "unset":
            s.execute(
                text("SELECT set_config('inv.tenant_id',:t,true)"),
                {"t": str(two_tenants[1]) if scope == "different" else ""},
            )
        assert (
            s.execute(
                text("SELECT * FROM public.workspace_input_state(:t,:w)"),
                {"t": scene["tenant_a"], "w": scene["workspace_id"]},
            ).all()
            == []
        )


def test_revoked_membership_cannot_read_prepared_input(app_sessionmaker, owner_engine, scene):
    from saintvision.errors import InvError

    pending(owner_engine, scene)
    with owner_engine.begin() as c:
        c.execute(
            text("DELETE FROM public.project_members WHERE user_id=:u AND project_id=:p"),
            {"u": scene["owner"], "p": scene["project_id"]},
        )
    with pytest.raises(InvError, match="not accessible"):
        read(app_sessionmaker, scene)
