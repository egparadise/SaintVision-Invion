"""Creating a project with a real account, and being refused without one.

The completion criterion is "a project made with a real account reaches the
execution kernel, and an unauthorised request is refused". These hold both
halves, and the first half is not only "it was created": a project that exists
but cannot execute has to say so, or the person who made it meets an
authorisation error about an operator step nobody told them about.
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import text

from saintvision.db.session import tenant_scope
from saintvision.errors import InvError
from saintvision.ids import new_id
from saintvision.services import projects as project_service
from saintvision.services import settings as settings_service

pytestmark = pytest.mark.postgres

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 9, 11, 9, 0, 0, tzinfo=UTC)


@pytest.fixture
def people(owner_engine, two_tenants):
    """Two users in one tenant, and one in another."""
    tenant_a, tenant_b = two_tenants
    ids = {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "alice": new_id("user"),
        "bob": new_id("user"),
        "stranger": new_id("user"),
    }
    with owner_engine.begin() as c:
        for key, tenant in (
            ("alice", tenant_a),
            ("bob", tenant_a),
            ("stranger", tenant_b),
        ):
            c.execute(
                text(
                    "INSERT INTO users (user_id, tenant_id, external_subject, "
                    "display_name, status, created_at, updated_at, version) "
                    "VALUES (:u, :t, :s, :n, 'active', now(), now(), 1)"
                ),
                {"u": ids[key], "t": tenant, "s": ids[key], "n": key},
            )
    return ids


def _create(session, people, who="alice", code="team-one"):
    return project_service.create_project(
        session,
        tenant_id=people["tenant_a"],
        code=code,
        display_name="Team One",
        created_by_user_id=people[who],
        now=NOW,
    )


# --------------------------------------------------------------------------
# Creating
# --------------------------------------------------------------------------


def test_the_creator_owns_the_project_they_just_made(app_sessionmaker, people):
    """Otherwise the failure appears one request later, as an authorisation bug."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, people["tenant_a"]):
                created = _create(session, people)
                permission = settings_service.effective_permission(
                    session,
                    tenant_id=people["tenant_a"],
                    project_id=created["projectId"],
                    user_id=people["alice"],
                )
    assert created["memberCount"] == 1
    assert permission["roleCode"] == "owner"
    assert permission["canAdminister"]


def test_a_project_created_now_is_visible_now(app_sessionmaker, people):
    """The stale-snapshot bug, stated as a test.

    ``Principal.project_ids`` is fixed when a credential is verified, so a
    project created after sign-in is not in it and its own creator could not
    open it. Access is read from project_members instead.
    """
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, people["tenant_a"]):
                created = _create(session, people)
                listed = project_service.list_projects(
                    session, tenant_id=people["tenant_a"], user_id=people["alice"]
                )
    assert [p["projectId"] for p in listed] == [created["projectId"]]
    assert listed[0]["roleCode"] == "owner"


def test_a_created_project_cannot_execute_yet_and_says_so(
    app_sessionmaker, people
):
    """Creating a project does not grant the right to run code on a machine.

    That separation is correct and it is invisible without this: a screen would
    show a project, a workspace and a run button, and the run would fail with an
    authorisation error about an operator step the user cannot perform.
    """
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, people["tenant_a"]):
                created = _create(session, people)
    assert created["kernelLinked"] is False
    assert created["kernelEnabled"] is False
    assert "not connected to the execution kernel" in created["kernelNote"]


def test_a_linked_project_reports_that_it_can_run(
    app_sessionmaker, owner_engine, people
):
    """And once an operator links it, the same field says so."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, people["tenant_a"]):
                created = _create(session, people)
                project_id = created["projectId"]

    # What an operator does, as the owner role: link the project to the kernel.
    with owner_engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO inv.tenants (tenant_id, name) VALUES (:t, 'a') "
                "ON CONFLICT DO NOTHING"
            ),
            {"t": people["tenant_a"]},
        )
        c.execute(
            text(
                "INSERT INTO inv.projects (tenant_id, project_id) VALUES (:t, :p) "
                "ON CONFLICT DO NOTHING"
            ),
            {"t": people["tenant_a"], "p": project_id},
        )
        c.execute(
            text(
                "INSERT INTO inv.business_projects (tenant_id, project_id, enabled) "
                "VALUES (:t, :p, true)"
            ),
            {"t": people["tenant_a"], "p": project_id},
        )

    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, people["tenant_a"]):
                link = project_service.kernel_link(
                    session, tenant_id=people["tenant_a"], project_id=project_id
                )
    assert link == {"kernelLinked": True, "kernelEnabled": True}


def test_the_application_cannot_read_the_link_table_directly(
    app_sessionmaker, people
):
    """The definer function is narrow on purpose.

    The web process must not be able to enumerate or alter which projects may
    execute; it may ask one yes/no question about one project it already names.
    """
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, people["tenant_a"]):
                with pytest.raises(Exception) as excinfo:
                    session.execute(
                        text("SELECT * FROM inv.business_projects")
                    ).all()
    assert "permission denied" in str(excinfo.value).lower()


def test_a_duplicate_code_is_refused(app_sessionmaker, people):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, people["tenant_a"]):
                _create(session, people)
                with pytest.raises(InvError, match="already exists"):
                    _create(session, people, who="bob")


def test_a_suspended_user_cannot_create_a_project(
    app_sessionmaker, people
):
    """Otherwise a suspended account outlives its suspension in what it owns."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, people["tenant_a"]):
                settings_service.set_user_status(
                    session, tenant_id=people["tenant_a"], user_id=people["alice"],
                    status="suspended", now=NOW,
                )
                with pytest.raises(InvError, match="suspended user cannot create"):
                    _create(session, people)


@pytest.mark.parametrize("code", ["Team One", "a", "-leading", "trailing-", "x" * 70])
def test_an_unusable_project_code_is_refused(app_sessionmaker, people, code):
    """A code appears in URLs and in operator conversation."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, people["tenant_a"]):
                with pytest.raises(InvError, match="project code"):
                    project_service.create_project(
                        session, tenant_id=people["tenant_a"], code=code,
                        display_name="X", created_by_user_id=people["alice"], now=NOW,
                    )


# --------------------------------------------------------------------------
# Refusing
# --------------------------------------------------------------------------


def test_a_non_member_is_refused_and_told_nothing(app_sessionmaker, people):
    """The denial does not confirm the project exists.

    Distinguishing "no such project" from "not yours" hands an identifier to
    someone who has no access to it.
    """
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, people["tenant_a"]):
                created = _create(session, people)
                with pytest.raises(InvError) as real:
                    project_service.require_project_access(
                        session, tenant_id=people["tenant_a"],
                        project_id=created["projectId"], user_id=people["bob"],
                    )
                with pytest.raises(InvError) as imaginary:
                    project_service.require_project_access(
                        session, tenant_id=people["tenant_a"],
                        project_id=new_id("project"), user_id=people["bob"],
                    )
    assert real.value.message == imaginary.value.message
    assert real.value.code == imaginary.value.code


def test_a_revoked_membership_stops_working_immediately(app_sessionmaker, people):
    """The other direction of the snapshot problem.

    A membership revoked after a token was issued would stay effective until
    that token expired, which is the whole span during which revocation is
    supposed to matter.
    """
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, people["tenant_a"]):
                created = _create(session, people)
                settings_service.set_member_role(
                    session, tenant_id=people["tenant_a"],
                    project_id=created["projectId"], user_id=people["bob"],
                    role_code="maintainer", acting_user_id=people["alice"], now=NOW,
                )
                project_service.require_project_access(
                    session, tenant_id=people["tenant_a"],
                    project_id=created["projectId"], user_id=people["bob"],
                )
                settings_service.remove_member(
                    session, tenant_id=people["tenant_a"],
                    project_id=created["projectId"], user_id=people["bob"],
                    acting_user_id=people["alice"],
                )
                with pytest.raises(InvError, match="not accessible"):
                    project_service.require_project_access(
                        session, tenant_id=people["tenant_a"],
                        project_id=created["projectId"], user_id=people["bob"],
                    )


def test_another_tenants_user_cannot_reach_this_project(
    app_sessionmaker, people
):
    """Row level security already stops this; the service refuses it as well.

    Not defence in depth for its own sake — the RLS scope is set from the
    credential, and this is the check that holds if a caller ever reaches the
    service with a scope it should not have.
    """
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, people["tenant_a"]):
                created = _create(session, people)
                with pytest.raises(InvError, match="not accessible"):
                    project_service.require_project_access(
                        session, tenant_id=people["tenant_a"],
                        project_id=created["projectId"], user_id=people["stranger"],
                    )


# --------------------------------------------------------------------------
# Workspaces
# --------------------------------------------------------------------------


def test_a_workspace_starts_provisioning_not_ready(app_sessionmaker, people):
    """Nothing has prepared storage for it yet.

    A workspace that claims to be ready before anything provisioned it fails at
    the moment someone puts files in it.
    """
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, people["tenant_a"]):
                created = _create(session, people)
                workspace = project_service.create_workspace(
                    session, tenant_id=people["tenant_a"],
                    project_id=created["projectId"], name="build",
                    created_by_user_id=people["alice"], now=NOW,
                )
    assert workspace["status"] == "provisioning"
    assert "ready" in workspace["allowedNext"]


def test_a_viewer_may_not_create_a_workspace(app_sessionmaker, people):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, people["tenant_a"]):
                created = _create(session, people)
                settings_service.set_member_role(
                    session, tenant_id=people["tenant_a"],
                    project_id=created["projectId"], user_id=people["bob"],
                    role_code="viewer", acting_user_id=people["alice"], now=NOW,
                )
                with pytest.raises(InvError, match="may not create workspaces"):
                    project_service.create_workspace(
                        session, tenant_id=people["tenant_a"],
                        project_id=created["projectId"], name="build",
                        created_by_user_id=people["bob"], now=NOW,
                    )


def test_a_deleted_workspace_is_not_listed(app_sessionmaker, people):
    """A deleted workspace in a list is one somebody will try to open."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, people["tenant_a"]):
                created = _create(session, people)
                workspace = project_service.create_workspace(
                    session, tenant_id=people["tenant_a"],
                    project_id=created["projectId"], name="build",
                    created_by_user_id=people["alice"], now=NOW,
                )
                for status in ("ready", "deleting", "deleted"):
                    settings_service.set_workspace_status(
                        session, tenant_id=people["tenant_a"],
                        workspace_id=workspace["workspaceId"], status=status,
                        acting_user_id=people["alice"], now=NOW,
                    )
                listed = project_service.list_workspaces(
                    session, tenant_id=people["tenant_a"],
                    project_id=created["projectId"], user_id=people["alice"],
                )
    assert listed == []


def test_listing_workspaces_requires_membership(app_sessionmaker, people):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, people["tenant_a"]):
                created = _create(session, people)
                with pytest.raises(InvError, match="not accessible"):
                    project_service.list_workspaces(
                        session, tenant_id=people["tenant_a"],
                        project_id=created["projectId"], user_id=people["bob"],
                    )
