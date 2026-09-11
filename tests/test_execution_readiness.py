"""Why a workspace cannot run yet.

Execution results are read by ``inv.result_view.ResultView``, which is
authoritative for them; the tests that lived here for a second reader on this
side went with it. What remains is the question that is genuinely the business
surface's: not "what happened" but "why can nothing happen yet", which spans
project membership, an operator's kernel links, a workspace lifecycle and a
tool installed on a machine — no one of which the kernel owns.
"""

from __future__ import annotations

import datetime as dt
import json

import pytest
from sqlalchemy import text

from saintvision.db.session import tenant_scope
from saintvision.errors import InvError
from saintvision.ids import new_id
from saintvision.services import execution_readiness as readiness_service
from saintvision.services import projects as project_service
from saintvision.services import runs as run_service
from saintvision.services import settings as settings_service

pytestmark = pytest.mark.postgres

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 9, 11, 11, 0, 0, tzinfo=UTC)


@pytest.fixture
def lab(owner_engine, two_tenants):
    tenant_a, tenant_b = two_tenants
    ids = {
        "tenant_a": tenant_a,
        "owner": new_id("user"),
        "outsider": new_id("user"),
        "workload_id": new_id("workload"),
    }
    digest = run_service.workload_digest({"objective": "r"})
    with owner_engine.begin() as c:
        for key in ("owner", "outsider"):
            c.execute(
                text(
                    "INSERT INTO users (user_id, tenant_id, external_subject, "
                    "display_name, status, created_at, updated_at, version) "
                    "VALUES (:u, :t, :s, :n, 'active', now(), now(), 1)"
                ),
                {"u": ids[key], "t": tenant_a, "s": ids[key], "n": key},
            )
    return ids, digest


@pytest.fixture
def scene(app_sessionmaker, owner_engine, lab):
    """A project, a ready workspace and a Run, made through the real services."""
    ids, digest = lab
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, ids["tenant_a"]):
                project = project_service.create_project(
                    session, tenant_id=ids["tenant_a"], code="res-one",
                    display_name="R", created_by_user_id=ids["owner"], now=NOW,
                )
                workspace = project_service.create_workspace(
                    session, tenant_id=ids["tenant_a"],
                    project_id=project["projectId"], name="main",
                    created_by_user_id=ids["owner"], now=NOW,
                )
                settings_service.set_workspace_status(
                    session, tenant_id=ids["tenant_a"],
                    workspace_id=workspace["workspaceId"], status="ready",
                    acting_user_id=ids["owner"], now=NOW,
                )
                ids["project_id"] = project["projectId"]
                ids["workspace_id"] = workspace["workspaceId"]
    with owner_engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO workloads (workload_id, tenant_id, project_id, kind, "
                "objective, spec, spec_sha256, contract_version, created_by_user_id, "
                "created_at, version) VALUES (:w, :t, :p, 'batch', 'r', '{}', :d, "
                "'1.0.0', :u, now(), 1)"
            ),
            {"w": ids["workload_id"], "t": ids["tenant_a"], "p": ids["project_id"],
             "d": digest, "u": ids["owner"]},
        )
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, ids["tenant_a"]):
                run = run_service.create_run(
                    session, tenant_id=ids["tenant_a"],
                    workload_id=ids["workload_id"],
                    workspace_id=ids["workspace_id"],
                    requested_by_user_id=ids["owner"], now=NOW,
                )
                ids["run_id"] = run.run_id
    return ids


# --------------------------------------------------------------------------
# Why a workspace cannot run yet
# --------------------------------------------------------------------------


def test_the_checklist_reports_every_precondition_at_once(app_sessionmaker, scene):
    """Not the first one the execution path happened to check.

    Reported one at a time, a user meets whichever failed first, described as an
    authorisation error — which is the right words for exactly one of the five.
    """
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, scene["tenant_a"]):
                report = readiness_service.workspace_readiness(
                    session, tenant_id=scene["tenant_a"],
                    workspace_id=scene["workspace_id"], user_id=scene["owner"],
                )
    names = [c["check"] for c in report["checks"]]
    assert names == [
        "project_linked_to_kernel",
        "requester_registered_with_kernel",
        "role_permits_requesting",
        "workspace_ready",
        "tool_chosen_and_usable",
        "input_prepared",
    ]
    assert report["executable"] is False


def test_each_unmet_precondition_names_who_can_lift_it(app_sessionmaker, scene):
    """"You are not allowed" and "nobody has set this up" need different people.

    They feel identical to whoever is blocked, and acting on the wrong one means
    a project owner changing a role that was never the problem.
    """
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, scene["tenant_a"]):
                report = readiness_service.workspace_readiness(
                    session, tenant_id=scene["tenant_a"],
                    workspace_id=scene["workspace_id"], user_id=scene["owner"],
                )
    unmet = {c["check"]: c for c in report["checks"] if not c["satisfied"]}
    assert unmet["project_linked_to_kernel"]["resolvedBy"] == "operator"
    assert unmet["requester_registered_with_kernel"]["resolvedBy"] == "operator"
    assert unmet["tool_chosen_and_usable"]["resolvedBy"] == "requester"
    # Each carries something to actually do.
    assert all(c.get("remedy") for c in unmet.values())
    assert "operator" in report["blockedBy"]


def test_the_role_check_passes_for_an_owner_and_fails_for_a_viewer(
    app_sessionmaker, scene
):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, scene["tenant_a"]):
                report = readiness_service.workspace_readiness(
                    session, tenant_id=scene["tenant_a"],
                    workspace_id=scene["workspace_id"], user_id=scene["owner"],
                )
                by_name = {c["check"]: c for c in report["checks"]}
                assert by_name["role_permits_requesting"]["satisfied"]
                assert by_name["workspace_ready"]["satisfied"]

                settings_service.set_member_role(
                    session, tenant_id=scene["tenant_a"],
                    project_id=scene["project_id"], user_id=scene["outsider"],
                    role_code="viewer", acting_user_id=scene["owner"], now=NOW,
                )
                viewer_report = readiness_service.workspace_readiness(
                    session, tenant_id=scene["tenant_a"],
                    workspace_id=scene["workspace_id"], user_id=scene["outsider"],
                )
    viewer = {c["check"]: c for c in viewer_report["checks"]}
    assert not viewer["role_permits_requesting"]["satisfied"]
    assert viewer["role_permits_requesting"]["resolvedBy"] == "project owner"


def test_an_operator_link_satisfies_the_kernel_checks(
    app_sessionmaker, owner_engine, scene
):
    """And the checklist stops reporting them, which is how it is verifiable.

    The linking is done as the schema owner here because that is who owns it —
    the application cannot do this, and a function that let it would be a way
    for the web process to grant itself execution rights.
    """
    with owner_engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO inv.tenants (tenant_id, name) VALUES (:t, 'a') "
                "ON CONFLICT DO NOTHING"
            ),
            {"t": scene["tenant_a"]},
        )
        c.execute(
            text(
                "INSERT INTO inv.projects (tenant_id, project_id) VALUES (:t, :p) "
                "ON CONFLICT DO NOTHING"
            ),
            {"t": scene["tenant_a"], "p": scene["project_id"]},
        )
        c.execute(
            text(
                "INSERT INTO inv.business_projects (tenant_id, project_id, enabled) "
                "VALUES (:t, :p, true)"
            ),
            {"t": scene["tenant_a"], "p": scene["project_id"]},
        )
        c.execute(
            text(
                "INSERT INTO inv.business_subjects "
                "(tenant_id, subject_id, user_id, enabled) "
                "VALUES (:t, :s, :u, true)"
            ),
            {"t": scene["tenant_a"], "s": "oidc:" + "b" * 64, "u": scene["owner"]},
        )
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, scene["tenant_a"]):
                report = readiness_service.workspace_readiness(
                    session, tenant_id=scene["tenant_a"],
                    workspace_id=scene["workspace_id"], user_id=scene["owner"],
                )
    by_name = {c["check"]: c for c in report["checks"]}
    assert by_name["project_linked_to_kernel"]["satisfied"]
    assert by_name["requester_registered_with_kernel"]["satisfied"]
    # Only the requester's own steps are left: choose a tool, submit input.
    assert report["blockedBy"] == ["requester"]


def test_the_checklist_cannot_be_used_to_probe_another_project(
    app_sessionmaker, scene
):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, scene["tenant_a"]):
                with pytest.raises(InvError, match="not accessible"):
                    readiness_service.workspace_readiness(
                        session, tenant_id=scene["tenant_a"],
                        workspace_id=scene["workspace_id"],
                        user_id=scene["outsider"],
                    )




def test_input_is_the_precondition_a_user_meets_after_the_others(
    app_sessionmaker, scene
):
    """Everything permitted, everything linked, and still nothing to run.

    Submitting workspace files is the execution kernel's endpoint; this side
    only asks whether it happened. Without the check, a person satisfies five
    preconditions and then presses a button that fails for a sixth reason
    nothing mentioned.
    """
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, scene["tenant_a"]):
                report = readiness_service.workspace_readiness(
                    session, tenant_id=scene["tenant_a"],
                    workspace_id=scene["workspace_id"], user_id=scene["owner"],
                )
    check = {c["check"]: c for c in report["checks"]}["input_prepared"]
    assert check["satisfied"] is False
    assert check["resolvedBy"] == "requester"
    # The bound is stated before a submission is refused for exceeding it.
    assert "65536 bytes" in check["remedy"]


def test_prepared_input_satisfies_the_check_and_reports_its_size(
    app_sessionmaker, owner_engine, scene
):
    """Read from what the kernel wrote, never reconstructed here."""
    import uuid as _uuid

    with owner_engine.begin() as c:
        # The operator's step. inv.control_epoch is created empty on purpose —
        # rolling the epoch voids every reservation in flight, so no migration
        # does it — and the kernel's guard requires the current one, so without
        # this the insert fails exactly as it should.
        c.execute(
            text(
                "INSERT INTO inv.control_epoch (singleton, epoch) "
                "VALUES (true, gen_random_uuid()) ON CONFLICT DO NOTHING"
            )
        )
        c.execute(
            text(
                "INSERT INTO inv.tenants (tenant_id, name) VALUES (:t, 'r') "
                "ON CONFLICT DO NOTHING"
            ),
            {"t": scene["tenant_a"]},
        )
        c.execute(
            text(
                "INSERT INTO inv.projects (tenant_id, project_id) VALUES (:t, :p) "
                "ON CONFLICT DO NOTHING"
            ),
            {"t": scene["tenant_a"], "p": scene["project_id"]},
        )
        c.execute(
            text(
                "INSERT INTO inv.runs (tenant_id, project_id, run_id) "
                "VALUES (:t, :p, :r) ON CONFLICT DO NOTHING"
            ),
            {"t": scene["tenant_a"], "p": scene["project_id"], "r": scene["run_id"]},
        )
        start_id = _uuid.uuid4()
        c.execute(
            text(
                "INSERT INTO inv.workspace_starts (tenant_id, project_id, run_id, "
                "start_id, workspace_id, step_id, requester_id, recovery_epoch, "
                "workload, snapshot) VALUES (:t, :p, :r, :s, :w, 'build', :u, "
                "(SELECT epoch FROM inv.control_epoch WHERE singleton), "
                "CAST(:wl AS jsonb), :snap)"
            ),
            {"t": scene["tenant_a"], "p": scene["project_id"], "r": scene["run_id"],
             "s": start_id, "w": scene["workspace_id"], "u": scene["owner"],
             "wl": '{"workspaceId": "%s", "workspaceStart": {"startId": "%s"}}'
                   % (scene["workspace_id"], start_id),
             "snap": b"x" * 1234},
        )

    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, scene["tenant_a"]):
                report = readiness_service.workspace_readiness(
                    session, tenant_id=scene["tenant_a"],
                    workspace_id=scene["workspace_id"], user_id=scene["owner"],
                )
    check = {c["check"]: c for c in report["checks"]}["input_prepared"]
    assert check["satisfied"] is True
    assert check["snapshotBytes"] == 1234
    assert check["maxSnapshotBytes"] == 65536
    assert check["runId"] == scene["run_id"]


def test_the_input_reader_is_bound_to_the_session_tenant(
    app_sessionmaker, scene, two_tenants
):
    """Every definer function added after 0027 is bound from the start."""
    _, tenant_b = two_tenants
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, scene["tenant_a"]):
                rows = session.execute(
                    text(
                        "SELECT count(*) FROM public.workspace_input_state(:t, :w)"
                    ),
                    {"t": str(tenant_b), "w": scene["workspace_id"]},
                ).scalar_one()
    assert rows == 0
