"""The business chain that reaches the execution core.

Six steps: check the permission, stop editing, freeze the inputs, obtain a
fresh approval, reserve and queue, execute and settle. What these tests hold is
not that each step works — it is that **each step refuses when a fact the
previous step established has since changed.** That is the only property the
chain adds over calling the six things in a row, and it is the property that
makes an approval mean something.

Every one of these tests corresponds to a real window: between two steps there
is a network round trip and usually a human, which is more than enough time for
a workspace to be edited, a membership to be revoked, or a control plane to
restart and roll its recovery epoch.
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from saintvision.db.session import tenant_scope
from saintvision.errors import InvError
from saintvision.ids import new_id
from saintvision.services import handoff as handoff_service
from saintvision.services import runs as run_service

pytestmark = pytest.mark.postgres

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 9, 10, 9, 0, 0, tzinfo=UTC)
DIGEST_A = "a" * 64
DIGEST_B = "b" * 64


@pytest.fixture
def chain(owner_engine, two_tenants):
    """A project with an owner, a requester, an approver, a workspace and a run."""
    tenant_a, tenant_b = two_tenants
    ids = {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "requester": new_id("user"),
        "approver": new_id("user"),
        "outsider": new_id("user"),
        "project_id": new_id("project"),
        "workspace_id": new_id("workspace"),
        "workload_id": new_id("workload"),
    }
    digest = run_service.workload_digest({"objective": "resume"})
    with owner_engine.begin() as c:
        for key, role in (
            ("requester", "maintainer"),
            ("approver", "approver"),
            ("outsider", "viewer"),
        ):
            c.execute(
                text(
                    "INSERT INTO users (user_id, tenant_id, external_subject, "
                    "display_name, status, created_at, updated_at, version) "
                    "VALUES (:u, :t, :s, 'U', 'active', now(), now(), 1)"
                ),
                {"u": ids[key], "t": tenant_a, "s": ids[key]},
            )
        c.execute(
            text(
                "INSERT INTO projects (project_id, tenant_id, code, display_name, "
                "status, created_at, version) VALUES (:p, :t, 'c', 'C', 'active', now(), 1)"
            ),
            {"p": ids["project_id"], "t": tenant_a},
        )
        for key, role in (
            ("requester", "maintainer"),
            ("approver", "approver"),
            ("outsider", "viewer"),
        ):
            c.execute(
                text(
                    "INSERT INTO project_members (tenant_id, project_id, user_id, "
                    "role_code, granted_at) VALUES (:t, :p, :u, :r, now())"
                ),
                {"t": tenant_a, "p": ids["project_id"], "u": ids[key], "r": role},
            )
        c.execute(
            text(
                "INSERT INTO workspaces (workspace_id, tenant_id, project_id, name, "
                "status, created_by_user_id, created_at, version) "
                "VALUES (:w, :t, :p, 'ws', 'ready', :u, now(), 1)"
            ),
            {"w": ids["workspace_id"], "t": tenant_a, "p": ids["project_id"],
             "u": ids["requester"]},
        )
        c.execute(
            text(
                "INSERT INTO workloads (workload_id, tenant_id, project_id, kind, "
                "objective, spec, spec_sha256, contract_version, "
                "created_by_user_id, created_at, version) "
                "VALUES (:w, :t, :p, 'batch', 'resume', '{}', :d, '1.0.0', :u, now(), 1)"
            ),
            {"w": ids["workload_id"], "t": tenant_a, "p": ids["project_id"],
             "d": digest, "u": ids["requester"]},
        )
    with owner_engine.begin() as c:
        c.execute(
            text("SELECT set_config('inv.tenant_id', :t, false)"), {"t": str(tenant_a)}
        )
    return ids


def _run(session, chain):
    return run_service.create_run(
        session,
        tenant_id=chain["tenant_a"],
        workload_id=chain["workload_id"],
        workspace_id=chain["workspace_id"],
        requested_by_user_id=chain["requester"],
        now=NOW,
    )


def _permission(session, chain, who="requester"):
    return handoff_service.check_project_permission(
        session,
        tenant_id=chain["tenant_a"],
        project_id=chain["project_id"],
        user_id=chain[who],
    )


def _frozen(session, chain, *, digest=DIGEST_A):
    """Walk steps 1 to 3 and return (run_id, lock, binding)."""
    run = _run(session, chain)
    permission = _permission(session, chain)
    lock = handoff_service.stop_editing(
        session,
        tenant_id=chain["tenant_a"],
        workspace_id=chain["workspace_id"],
        run_id=run.run_id,
        user_id=chain["requester"],
        content_sha256=digest,
        now=NOW,
    )
    binding = handoff_service.freeze_inputs(
        session,
        tenant_id=chain["tenant_a"],
        project_id=chain["project_id"],
        run_id=run.run_id,
        workspace_id=chain["workspace_id"],
        lock=lock,
        permission=permission,
        step_id="build",
        source_attempt=1,
        bound_run_version=1,
        input_sha256=digest,
        input_size_bytes=1024,
        now=NOW,
    )
    return run.run_id, lock, binding


# --------------------------------------------------------------------------
# Step 1 — project permission
# --------------------------------------------------------------------------


def test_tenant_isolation_does_not_give_project_isolation(app_sessionmaker, chain):
    """The reason this check exists at all.

    Row level security keeps one tenant out of another's rows and says nothing
    about projects. A user is a member of some projects in their tenant and not
    others, and no policy expresses that — so this is not defence in depth, it
    is the only thing there.
    """
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, chain["tenant_a"]):
                stranger = new_id("user")
                with pytest.raises(InvError, match="no project membership"):
                    handoff_service.check_project_permission(
                        session,
                        tenant_id=chain["tenant_a"],
                        project_id=chain["project_id"],
                        user_id=stranger,
                    )


def test_a_viewer_may_not_request_execution(app_sessionmaker, chain):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, chain["tenant_a"]):
                permission = _permission(session, chain, "outsider")
                assert not permission.can_request
                with pytest.raises(InvError, match="may not request execution"):
                    handoff_service.require_can_request(permission)


def test_an_archived_project_accepts_nothing(app_sessionmaker, owner_engine, chain):
    """Archiving a project that still runs work archives nothing."""
    with owner_engine.begin() as c:
        c.execute(
            text("UPDATE projects SET status = 'archived' WHERE project_id = :p"),
            {"p": chain["project_id"]},
        )
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, chain["tenant_a"]):
                with pytest.raises(InvError, match="not active"):
                    _permission(session, chain)


# --------------------------------------------------------------------------
# Step 2 — stop editing
# --------------------------------------------------------------------------


def test_two_runs_cannot_quiesce_one_workspace(app_sessionmaker, chain):
    """The race the lock exists to prevent, resolved by PostgreSQL and not by us."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, chain["tenant_a"]):
                first = _run(session, chain)
                second = _run(session, chain)
                handoff_service.stop_editing(
                    session, tenant_id=chain["tenant_a"],
                    workspace_id=chain["workspace_id"], run_id=first.run_id,
                    user_id=chain["requester"], content_sha256=DIGEST_A, now=NOW,
                )
                with pytest.raises(InvError, match="already stopped for another run"):
                    handoff_service.stop_editing(
                        session, tenant_id=chain["tenant_a"],
                        workspace_id=chain["workspace_id"], run_id=second.run_id,
                        user_id=chain["requester"], content_sha256=DIGEST_A, now=NOW,
                    )


def test_the_database_allows_only_one_held_lock_per_workspace(
    app_sessionmaker, chain
):
    """Not only the service. Two callers race, and one must lose in the database."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, chain["tenant_a"]):
                run = _run(session, chain)
                run_id = run.run_id
                handoff_service.stop_editing(
                    session, tenant_id=chain["tenant_a"],
                    workspace_id=chain["workspace_id"], run_id=run_id,
                    user_id=chain["requester"], content_sha256=DIGEST_A, now=NOW,
                )
        with pytest.raises(IntegrityError):
            with session.begin():
                with tenant_scope(session, chain["tenant_a"]):
                    session.execute(
                        text(
                            "INSERT INTO workspace_edit_locks (lock_id, tenant_id, "
                            "workspace_id, run_id, held_by_user_id, content_sha256, "
                            "reason, acquired_at, version) "
                            "VALUES (:l, :t, :w, :r, :u, :d, 'execution', now(), 1)"
                        ),
                        {"l": new_id("edit_lock"), "t": chain["tenant_a"],
                         "w": chain["workspace_id"], "r": run_id,
                         "u": chain["requester"], "d": DIGEST_B},
                    )


def test_the_same_run_quiescing_twice_is_a_retry(app_sessionmaker, chain):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, chain["tenant_a"]):
                run = _run(session, chain)
                args = dict(
                    tenant_id=chain["tenant_a"], workspace_id=chain["workspace_id"],
                    run_id=run.run_id, user_id=chain["requester"],
                    content_sha256=DIGEST_A, now=NOW,
                )
                first = handoff_service.stop_editing(session, **args)
                again = handoff_service.stop_editing(session, **args)
    assert first.lock_id == again.lock_id


# --------------------------------------------------------------------------
# Step 3 — freeze the inputs
# --------------------------------------------------------------------------


def test_an_edit_between_stopping_and_freezing_is_caught(app_sessionmaker, chain):
    """The window this whole chain exists to close.

    Editing stopped with the workspace holding one thing; the freeze captured
    another. Approving the second is approving bytes nobody looked at.
    """
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, chain["tenant_a"]):
                run = _run(session, chain)
                permission = _permission(session, chain)
                lock = handoff_service.stop_editing(
                    session, tenant_id=chain["tenant_a"],
                    workspace_id=chain["workspace_id"], run_id=run.run_id,
                    user_id=chain["requester"], content_sha256=DIGEST_A, now=NOW,
                )
                with pytest.raises(InvError, match="changed after editing was stopped"):
                    handoff_service.freeze_inputs(
                        session, tenant_id=chain["tenant_a"],
                        project_id=chain["project_id"], run_id=run.run_id,
                        workspace_id=chain["workspace_id"], lock=lock,
                        permission=permission, step_id="build", source_attempt=1,
                        bound_run_version=1,
                        input_sha256=DIGEST_B,  # not what the lock recorded
                        input_size_bytes=10, now=NOW,
                    )


def test_freezing_records_the_epoch_the_core_is_actually_in(
    app_sessionmaker, owner_engine, chain
):
    """Read from inv.control_epoch, not from this side's configuration.

    A copy in configuration would be a second answer, and the whole point of the
    field is that there is only one.
    """
    with owner_engine.connect() as c:
        expected = str(
            c.execute(text("SELECT epoch FROM inv.control_epoch WHERE singleton"))
            .scalar_one()
        )
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, chain["tenant_a"]):
                _, _, binding = _frozen(session, chain)
                recorded = str(binding.recovery_epoch)
    assert recorded == expected


def test_freezing_after_editing_resumed_is_refused(app_sessionmaker, chain):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, chain["tenant_a"]):
                run = _run(session, chain)
                permission = _permission(session, chain)
                lock = handoff_service.stop_editing(
                    session, tenant_id=chain["tenant_a"],
                    workspace_id=chain["workspace_id"], run_id=run.run_id,
                    user_id=chain["requester"], content_sha256=DIGEST_A, now=NOW,
                )
                handoff_service.resume_editing(
                    session, tenant_id=chain["tenant_a"], lock_id=lock.lock_id, now=NOW
                )
                with pytest.raises(InvError, match="resumed before the inputs were frozen"):
                    handoff_service.freeze_inputs(
                        session, tenant_id=chain["tenant_a"],
                        project_id=chain["project_id"], run_id=run.run_id,
                        workspace_id=chain["workspace_id"], lock=lock,
                        permission=permission, step_id="build", source_attempt=1,
                        bound_run_version=1, input_sha256=DIGEST_A,
                        input_size_bytes=10, now=NOW,
                    )


def test_a_binding_cannot_exist_without_its_lock(app_sessionmaker, chain):
    """The foreign key that makes "the inputs were still" a schema fact."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, chain["tenant_a"]):
                run = _run(session, chain)
                run_id = run.run_id
        with pytest.raises(IntegrityError):
            with session.begin():
                with tenant_scope(session, chain["tenant_a"]):
                    session.execute(
                        text(
                            "INSERT INTO execution_bindings (binding_id, tenant_id, "
                            "project_id, run_id, workspace_id, lock_id, recovery_epoch, "
                            "bound_run_version, source_attempt, input_sha256, "
                            "input_size_bytes, step_id, state, created_by_user_id, "
                            "created_at, version) VALUES (:b, :t, :p, :r, :w, :l, "
                            "gen_random_uuid(), 1, 1, :d, 0, 'build', 'frozen', :u, "
                            "now(), 1)"
                        ),
                        {"b": new_id("binding"), "t": chain["tenant_a"],
                         "p": chain["project_id"], "r": run_id,
                         "w": chain["workspace_id"], "l": new_id("edit_lock"),
                         "d": DIGEST_A, "u": chain["requester"]},
                    )


# --------------------------------------------------------------------------
# Step 4 — a fresh approval
# --------------------------------------------------------------------------


def test_the_requester_may_not_approve_their_own_execution(app_sessionmaker, chain):
    """A quorum of one is not a quorum."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, chain["tenant_a"]):
                _, _, binding = _frozen(session, chain)
                permission = _permission(session, chain, "requester")
                with pytest.raises(InvError, match="may not approve their own"):
                    handoff_service.attach_approval(
                        session, tenant_id=chain["tenant_a"],
                        binding_id=binding.binding_id,
                        approval_id=new_id("approval"), permission=permission,
                        permission_snapshot_id=None, now=NOW,
                    )


def test_a_viewer_may_not_approve(app_sessionmaker, chain):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, chain["tenant_a"]):
                _, _, binding = _frozen(session, chain)
                permission = _permission(session, chain, "outsider")
                with pytest.raises(InvError, match="may not approve execution"):
                    handoff_service.attach_approval(
                        session, tenant_id=chain["tenant_a"],
                        binding_id=binding.binding_id,
                        approval_id=new_id("approval"), permission=permission,
                        permission_snapshot_id=None, now=NOW,
                    )


def test_an_approval_id_must_be_one_the_core_can_hold(app_sessionmaker, chain):
    """The identity mapping, at the point where it would otherwise fail late.

    public used to mint `apv_` while inv.approval_requests enforces `apr_`. One
    value has to be writable on both sides of the seam it crosses.
    """
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, chain["tenant_a"]):
                _, _, binding = _frozen(session, chain)
                permission = _permission(session, chain, "approver")
                with pytest.raises(InvError, match="execution-core approval id"):
                    handoff_service.attach_approval(
                        session, tenant_id=chain["tenant_a"],
                        binding_id=binding.binding_id,
                        approval_id="apv_01M24Q3CSP3N3TDMS9TPXZC1JV",
                        permission=permission, permission_snapshot_id=None, now=NOW,
                    )


def test_stale_frozen_inputs_cannot_be_approved(app_sessionmaker, chain):
    """A freeze nobody acted on stops being a description of the present."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, chain["tenant_a"]):
                _, _, binding = _frozen(session, chain)
                permission = _permission(session, chain, "approver")
                much_later = NOW + dt.timedelta(
                    seconds=handoff_service.FREEZE_TTL_SECONDS + 1
                )
                with pytest.raises(InvError, match="too old to approve"):
                    handoff_service.attach_approval(
                        session, tenant_id=chain["tenant_a"],
                        binding_id=binding.binding_id,
                        approval_id=new_id("approval"), permission=permission,
                        permission_snapshot_id=None, now=much_later,
                    )


def test_one_binding_carries_one_decision(app_sessionmaker, chain):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, chain["tenant_a"]):
                _, _, binding = _frozen(session, chain)
                permission = _permission(session, chain, "approver")
                handoff_service.attach_approval(
                    session, tenant_id=chain["tenant_a"],
                    binding_id=binding.binding_id, approval_id=new_id("approval"),
                    permission=permission, permission_snapshot_id=None, now=NOW,
                )
                with pytest.raises(InvError, match="already carries a decision"):
                    handoff_service.attach_approval(
                        session, tenant_id=chain["tenant_a"],
                        binding_id=binding.binding_id,
                        approval_id=new_id("approval"), permission=permission,
                        permission_snapshot_id=None, now=NOW,
                    )


def test_approving_records_who_could_do_what_at_that_moment(app_sessionmaker, chain):
    """A membership revoked tomorrow must not make today's approval look wrong."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, chain["tenant_a"]):
                _, _, binding = _frozen(session, chain)
                permission = _permission(session, chain, "approver")
                snapshot_id = handoff_service.record_permission_snapshot(
                    session, tenant_id=chain["tenant_a"], permission=permission, now=NOW
                )
                handoff_service.attach_approval(
                    session, tenant_id=chain["tenant_a"],
                    binding_id=binding.binding_id, approval_id=new_id("approval"),
                    permission=permission, permission_snapshot_id=snapshot_id, now=NOW,
                )
                stored = session.execute(
                    text(
                        "SELECT subject_id, digest_sha256 FROM permission_snapshots "
                        "WHERE snapshot_id = :s"
                    ),
                    {"s": snapshot_id},
                ).one()
    assert stored[0] == chain["approver"]
    assert stored[1] == permission.digest()


# --------------------------------------------------------------------------
# Steps 5 and 6 — reserve, queue, execute, settle
# --------------------------------------------------------------------------


def test_an_epoch_roll_stops_a_frozen_binding_from_being_queued(
    app_sessionmaker, owner_engine, chain
):
    """The mapping earning its place.

    The execution core rolls its recovery epoch when an operator reconciles
    after a restart. A binding prepared before that roll describes reservations
    that no longer exist — and without the recorded epoch it looks exactly like
    one prepared after.
    """
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, chain["tenant_a"]):
                _, _, binding = _frozen(session, chain)
                permission = _permission(session, chain, "approver")
                handoff_service.attach_approval(
                    session, tenant_id=chain["tenant_a"],
                    binding_id=binding.binding_id, approval_id=new_id("approval"),
                    permission=permission, permission_snapshot_id=None, now=NOW,
                )
                binding_id = binding.binding_id

    with owner_engine.begin() as c:
        c.execute(text("UPDATE inv.control_epoch SET epoch = gen_random_uuid()"))

    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, chain["tenant_a"]):
                with pytest.raises(InvError, match="recovery epoch moved"):
                    handoff_service.advance(
                        session, tenant_id=chain["tenant_a"],
                        binding_id=binding_id, to="queued", now=NOW,
                    )


def test_a_binding_only_moves_forward(app_sessionmaker, chain):
    """A late report must not walk a binding back into a state it left."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, chain["tenant_a"]):
                _, _, binding = _frozen(session, chain)
                permission = _permission(session, chain, "approver")
                handoff_service.attach_approval(
                    session, tenant_id=chain["tenant_a"],
                    binding_id=binding.binding_id, approval_id=new_id("approval"),
                    permission=permission, permission_snapshot_id=None, now=NOW,
                )
                handoff_service.advance(
                    session, tenant_id=chain["tenant_a"],
                    binding_id=binding.binding_id, to="queued", now=NOW,
                )
                with pytest.raises(InvError, match="only moves forward"):
                    handoff_service.advance(
                        session, tenant_id=chain["tenant_a"],
                        binding_id=binding.binding_id, to="approved", now=NOW,
                    )


def test_settling_lets_editing_continue(app_sessionmaker, chain):
    """A workspace left quiesced after its run finished is one nobody can edit."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, chain["tenant_a"]):
                _, lock, binding = _frozen(session, chain)
                permission = _permission(session, chain, "approver")
                handoff_service.attach_approval(
                    session, tenant_id=chain["tenant_a"],
                    binding_id=binding.binding_id, approval_id=new_id("approval"),
                    permission=permission, permission_snapshot_id=None, now=NOW,
                )
                for state in ("queued", "executing", "settled"):
                    handoff_service.advance(
                        session, tenant_id=chain["tenant_a"],
                        binding_id=binding.binding_id, to=state, now=NOW,
                    )
                released = handoff_service.get_edit_lock(
                    session, tenant_id=chain["tenant_a"], lock_id=lock.lock_id
                )
                assert released.released_at is not None
                # And the workspace can be quiesced again for the next run.
                nxt = _run(session, chain)
                handoff_service.stop_editing(
                    session, tenant_id=chain["tenant_a"],
                    workspace_id=chain["workspace_id"], run_id=nxt.run_id,
                    user_id=chain["requester"], content_sha256=DIGEST_B, now=NOW,
                )


def test_one_run_cannot_be_bound_twice_for_the_same_moment(
    app_sessionmaker, owner_engine, chain
):
    """(run, epoch, version) is unique: two approvals for one decision is not a retry."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, chain["tenant_a"]):
                run_id, lock, binding = _frozen(session, chain)
                epoch = str(binding.recovery_epoch)
        with pytest.raises(IntegrityError):
            with session.begin():
                with tenant_scope(session, chain["tenant_a"]):
                    session.execute(
                        text(
                            "INSERT INTO execution_bindings (binding_id, tenant_id, "
                            "project_id, run_id, workspace_id, lock_id, recovery_epoch, "
                            "bound_run_version, source_attempt, input_sha256, "
                            "input_size_bytes, step_id, state, created_by_user_id, "
                            "created_at, version) VALUES (:b, :t, :p, :r, :w, :l, "
                            "CAST(:e AS uuid), 1, 1, :d, 0, 'build', 'frozen', :u, "
                            "now(), 1)"
                        ),
                        {"b": new_id("binding"), "t": chain["tenant_a"],
                         "p": chain["project_id"], "r": run_id,
                         "w": chain["workspace_id"], "l": lock.lock_id, "e": epoch,
                         "d": DIGEST_A, "u": chain["requester"]},
                    )


def test_the_binding_body_carries_every_identifier_the_core_needs(
    app_sessionmaker, chain
):
    """The mapping, as a caller receives it.

    A caller that passes these through verbatim cannot prepare work under one
    epoch and submit it under another, because the values it holds are the ones
    this side recorded.
    """
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, chain["tenant_a"]):
                run_id, _, binding = _frozen(session, chain)
                body = handoff_service.binding_body(binding)
    assert body["runId"] == run_id
    assert body["runId"].startswith("run_")
    assert body["projectId"].startswith("prj_")
    assert body["workspaceId"].startswith("wsp_")
    for field in ("recoveryEpoch", "boundRunVersion", "sourceAttempt", "inputSha256"):
        assert body[field] is not None, field
