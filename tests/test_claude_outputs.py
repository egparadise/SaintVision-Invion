"""Results, and never inventing one.

The governing test here is ``test_nothing_that_is_missing_is_rendered_as_a_value``.
The studio screen that calls these endpoints was found showing a fixed hash,
1,024 bytes and an invented Evidence id whenever the server did not answer. The
screen is Gemini's to fix; what this side owes is an API where a missing fact
never arrives looking like a present one, because an API that returns
plausibly-shaped emptiness is half of how that defect happens.
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
from saintvision.services import results as results_service
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
# Never invent a result
# --------------------------------------------------------------------------


def test_nothing_that_is_missing_is_rendered_as_a_value(app_sessionmaker, scene):
    """The rule this module exists for.

    A Run that has produced nothing must not come back looking like a Run that
    produced empty things. No zero hash, no zero-length digest, no fabricated
    identifier, and every absence carrying the reason for it.
    """
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, scene["tenant_a"]):
                body = results_service.run_result(
                    session, tenant_id=scene["tenant_a"],
                    run_id=scene["run_id"], user_id=scene["owner"],
                )
    assert body["sealed"] is False
    assert body["record"] is None
    assert body["evidence"] is None
    # Each absence explains itself rather than leaving a null to be guessed at.
    assert body["recordAbsent"]["reason"]
    assert body["evidenceAbsent"]["reason"]

    # And nothing in the response looks like a digest, a placeholder size, or a
    # fabricated identifier.
    rendered = json.dumps(body)
    assert "0" * 64 not in rendered
    assert '"1024"' not in rendered and ": 1024" not in rendered
    assert "e3b0c44298fc1c149afbf4c8996fb924" not in rendered  # sha256 of nothing


def test_an_unmeasured_artifact_reports_no_size_rather_than_zero(
    app_sessionmaker, owner_engine, scene
):
    """A size of zero is a real size; a size nobody measured is not.

    Reporting them the same way is how a screen ends up showing a confident
    number for a file that was never written.
    """
    artifact_id = new_id("artifact")
    with owner_engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO artifacts (artifact_id, tenant_id, run_id, name, "
                "media_type, status, byte_size, created_at, version) "
                "VALUES (:a, :t, :r, 'out.txt', 'text/plain', 'staging', 0, now(), 1)"
            ),
            {"a": artifact_id, "t": scene["tenant_a"], "r": scene["run_id"]},
        )
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, scene["tenant_a"]):
                items = results_service.list_artifacts(
                    session, tenant_id=scene["tenant_a"],
                    run_id=scene["run_id"], user_id=scene["owner"],
                )
    assert len(items) == 1
    assert items[0]["byteSize"] is None
    assert items[0]["byteSizeAbsent"]["reason"]
    assert items[0]["checksumSha256"] is None
    assert items[0]["checksumAbsent"]["reason"]


def test_a_digest_without_a_verification_is_not_verified(
    app_sessionmaker, owner_engine, scene
):
    """The artifact most likely to be shown as confirmed, because it looks complete.

    It is necessarily `staging`: the schema refuses an `active` artifact that
    has no verification (``active_requires_verification``), so "has a digest,
    was never verified" can only exist before promotion — which is exactly when
    a screen is most tempted to treat the digest as proof.
    """
    with owner_engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO artifacts (artifact_id, tenant_id, run_id, name, "
                "media_type, status, byte_size, checksum_sha256, created_at, version) "
                "VALUES (:a, :t, :r, 'out.bin', 'application/octet-stream', "
                "'staging', 42, :c, now(), 1)"
            ),
            {"a": new_id("artifact"), "t": scene["tenant_a"], "r": scene["run_id"],
             "c": "a" * 64},
        )
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, scene["tenant_a"]):
                items = results_service.list_artifacts(
                    session, tenant_id=scene["tenant_a"],
                    run_id=scene["run_id"], user_id=scene["owner"],
                )
    assert items[0]["checksumSha256"] == "a" * 64
    assert items[0]["verified"] is False
    assert items[0]["verifiedAt"] is None
    # A real size stays a real size.
    assert items[0]["byteSize"] == 42


def test_a_run_with_no_binding_reports_none_not_an_empty_binding(
    app_sessionmaker, scene
):
    """The binding is the kernel's record of which approval and epoch applied."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, scene["tenant_a"]):
                body = results_service.run_result(
                    session, tenant_id=scene["tenant_a"],
                    run_id=scene["run_id"], user_id=scene["owner"],
                )
    assert body["binding"] is None


# --------------------------------------------------------------------------
# Reading a result requires access to its project
# --------------------------------------------------------------------------


def test_a_non_member_cannot_read_a_result(app_sessionmaker, scene):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, scene["tenant_a"]):
                with pytest.raises(InvError, match="not accessible"):
                    results_service.run_result(
                        session, tenant_id=scene["tenant_a"],
                        run_id=scene["run_id"], user_id=scene["outsider"],
                    )


def test_a_non_member_cannot_list_artifacts_or_attempts(app_sessionmaker, scene):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, scene["tenant_a"]):
                for call in (
                    results_service.list_artifacts,
                    results_service.attempt_log,
                ):
                    with pytest.raises(InvError, match="not accessible"):
                        call(
                            session, tenant_id=scene["tenant_a"],
                            run_id=scene["run_id"], user_id=scene["outsider"],
                        )


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
    # Only the tool choice is left, and it belongs to the requester.
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


# --------------------------------------------------------------------------
# Downloads
# --------------------------------------------------------------------------


def test_outputs_come_from_the_execution_record_not_the_artifact_table(
    app_sessionmaker, scene
):
    """public.artifacts describes files nobody wrote.

    Nothing writes that table and a row in it cannot be resolved to bytes, so
    listing it would offer downloads that cannot happen. The outputs that exist
    are the kernel's committed results.
    """
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, scene["tenant_a"]):
                outputs = results_service.committed_outputs(
                    session, tenant_id=scene["tenant_a"],
                    run_id=scene["run_id"], user_id=scene["owner"],
                )
    assert outputs == []


def test_the_output_resolver_is_bound_to_the_session_tenant(
    app_sessionmaker, owner_engine, scene, two_tenants
):
    """A definer function bypasses RLS, so a caller-supplied tenant is not a scope.

    Revision 0027 had to correct exactly this in 0024. Asking about another
    tenant returns nothing rather than that tenant's outputs.
    """
    _, tenant_b = two_tenants
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, scene["tenant_a"]):
                rows = session.execute(
                    text(
                        "SELECT count(*) FROM public.run_committed_outputs(:t, :r)"
                    ),
                    {"t": str(tenant_b), "r": scene["run_id"]},
                ).scalar_one()
    assert rows == 0


def test_a_non_member_cannot_list_outputs(app_sessionmaker, scene):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, scene["tenant_a"]):
                with pytest.raises(InvError, match="not accessible"):
                    results_service.committed_outputs(
                        session, tenant_id=scene["tenant_a"],
                        run_id=scene["run_id"], user_id=scene["outsider"],
                    )


def test_downloading_an_output_that_does_not_exist_says_the_same_as_another_runs(
    app_sessionmaker, scene, tmp_path
):
    """Distinguishing them would confirm an object id belongs to somebody."""
    import uuid as _uuid

    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, scene["tenant_a"]):
                with pytest.raises(InvError, match="output not found for this run"):
                    results_service.read_output(
                        session, tenant_id=scene["tenant_a"],
                        run_id=scene["run_id"], object_id=str(_uuid.uuid4()),
                        user_id=scene["owner"], object_root=str(tmp_path),
                    )
