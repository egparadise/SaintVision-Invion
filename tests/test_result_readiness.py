"""Readiness cannot substitute CP tool installation or another tenant's grant."""

import pytest
from sqlalchemy import text

from saintvision.db.session import tenant_scope
from saintvision.services.execution_readiness import workspace_readiness
from test_business_results import lab, scene, NOW
from test_account_integration import account_api, org

pytestmark = pytest.mark.postgres


def test_readiness_uses_business_route_but_results_stay_on_kernel(account_api, org):
    a = account_api
    response = a.client.get(
        "/v1/workspaces/" + org["workspace_id"] + "/execution-readiness", headers=a.headers()
    )
    assert response.status_code == 200, response.text
    assert response.json()["executable"] is False
    # This fixture intentionally has no kernel DB; a routed kernel call is 503.
    response = a.client.get("/v1/runs/run_" + "0" * 26 + "/result", headers=a.headers())
    assert response.status_code == 503, response.text


def test_readiness_never_probes_control_plane_cli(
    app_sessionmaker, owner_engine, scene, monkeypatch
):
    from saintvision.adapters import agents

    monkeypatch.setattr(
        agents, "adapter_for", lambda *_: pytest.fail("local CLI is not remote readiness")
    )
    with owner_engine.begin() as c:
        c.execute(
            text("UPDATE public.workspaces SET tool_name='codex-cli' WHERE workspace_id=:w"),
            {"w": scene["workspace_id"]},
        )
    with app_sessionmaker() as s, s.begin(), tenant_scope(s, scene["tenant_a"]):
        body = workspace_readiness(
            s,
            tenant_id=scene["tenant_a"],
            workspace_id=scene["workspace_id"],
            user_id=scene["owner"],
        )
    checks = {c["check"]: c for c in body["checks"]}
    assert (
        not body["executable"] and body["nodeReadiness"] == "unknown" and body["admissionRequired"]
    )
    assert not checks["tool_chosen_and_usable"]["satisfied"]


def test_subject_and_execution_definers_reject_cross_tenant_and_revocation(
    app_sessionmaker, owner_engine, scene, two_tenants
):
    t, p, u = scene["tenant_a"], scene["project_id"], scene["owner"]
    subject = "oidc:" + "c" * 64
    with owner_engine.begin() as c:
        c.execute(
            text("INSERT INTO inv.tenants VALUES(:t,'readiness') ON CONFLICT DO NOTHING"), {"t": t}
        )
        c.execute(text("INSERT INTO inv.projects VALUES(:t,:p)"), {"t": t, "p": p})
        c.execute(
            text("INSERT INTO inv.business_projects(tenant_id,project_id) VALUES(:t,:p)"),
            {"t": t, "p": p},
        )
        c.execute(
            text("UPDATE public.users SET external_subject=:s WHERE user_id=:u"),
            {"s": subject, "u": u},
        )
        c.execute(
            text(
                "INSERT INTO inv.business_subjects(tenant_id,subject_id,user_id) VALUES(:t,:s,:u)"
            ),
            {"t": t, "s": subject, "u": u},
        )
        c.execute(
            text(
                "INSERT INTO inv.project_grants(tenant_id,project_id,subject_id,can_request,can_approve) VALUES(:t,:p,:s,true,false)"
            ),
            {"t": t, "p": p, "s": subject},
        )

    def observe(scope):
        with app_sessionmaker() as s, s.begin(), tenant_scope(s, scope):
            return s.execute(
                text(
                    "SELECT (SELECT registered FROM public.subject_kernel_link(:t,:u)), public.business_execution_permission(:t,:p,:u)"
                ),
                {"t": t, "u": u, "p": p},
            ).one()

    assert tuple(observe(t)) == (True, True)
    assert tuple(observe(two_tenants[1])) == (False, False)
    with owner_engine.begin() as c:
        c.execute(
            text(
                "UPDATE inv.project_grants SET enabled=false WHERE tenant_id=:t AND project_id=:p"
            ),
            {"t": t, "p": p},
        )
    assert tuple(observe(t)) == (True, False)
    with owner_engine.begin() as c:
        c.execute(text("UPDATE public.users SET status='suspended' WHERE user_id=:u"), {"u": u})
    assert tuple(observe(t)) == (False, False)
