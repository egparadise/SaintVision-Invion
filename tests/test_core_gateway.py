"""Reserving capacity through the execution core, from the business surface.

This is the seam actually being crossed rather than described. Every test here
runs one SQLAlchemy transaction that writes ``public`` rows and, through
``inv.db.BoundDatabase``, ``inv`` rows — which is only possible because both
schemas are now reachable by one role (revision 0022) and both scope by the
same ``SET LOCAL inv.tenant_id``.

What is worth holding:

* identity flows one way, with the same identifiers on both sides;
* resource observation is **not** projected — a reservation against a node the
  core has never measured is refused, not invented;
* the recorded epoch is load-bearing: a binding prepared under an older epoch
  cannot reserve under the current one;
* the reservation and the record of why it was made commit together.
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import text

from saintvision.db.session import tenant_scope
from saintvision.errors import InvError
from saintvision.ids import new_id
from saintvision.services import core_gateway as gateway
from saintvision.services import handoff as handoff_service
from saintvision.services import runs as run_service

pytestmark = pytest.mark.postgres

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 9, 10, 9, 0, 0, tzinfo=UTC)
DIGEST = "c" * 64
GIB = 1024**3


@pytest.fixture
def seam(owner_engine, two_tenants):
    """A project, a node, a workspace and a run — on the public side only."""
    tenant_a, tenant_b = two_tenants
    ids = {
        "tenant_a": tenant_a,
        "requester": new_id("user"),
        "approver": new_id("user"),
        "project_id": new_id("project"),
        "workspace_id": new_id("workspace"),
        "workload_id": new_id("workload"),
        "node_id": new_id("node"),
    }
    digest = run_service.workload_digest({"objective": "seam"})
    with owner_engine.begin() as c:
        for key, role in (("requester", "maintainer"), ("approver", "approver")):
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
                "status, created_at, version) VALUES (:p, :t, 's', 'S', 'active', now(), 1)"
            ),
            {"p": ids["project_id"], "t": tenant_a},
        )
        for key, role in (("requester", "maintainer"), ("approver", "approver")):
            c.execute(
                text(
                    "INSERT INTO project_members (tenant_id, project_id, user_id, "
                    "role_code, granted_at) VALUES (:t, :p, :u, :r, now())"
                ),
                {"t": tenant_a, "p": ids["project_id"], "u": ids[key], "r": role},
            )
        c.execute(
            text(
                "INSERT INTO nodes (node_id, tenant_id, hostname, os_type, os_version, "
                "agent_version, status, enrolled_at, heartbeat_sequence, version) "
                "VALUES (:n, :t, 'seam-01', 'linux', '22.04', '0.1', 'active', now(), 0, 1)"
            ),
            {"n": ids["node_id"], "t": tenant_a},
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
                "objective, spec, spec_sha256, contract_version, created_by_user_id, "
                "created_at, version) "
                "VALUES (:w, :t, :p, 'batch', 'seam', '{}', :d, '1.0.0', :u, now(), 1)"
            ),
            {"w": ids["workload_id"], "t": tenant_a, "p": ids["project_id"],
             "d": digest, "u": ids["requester"]},
        )
    return ids


def _observe_resource(owner_engine, seam, *, kind="memory", offered=64 * GIB):
    """What the core's own probes would have recorded. Never written by the gateway."""
    resource_id = new_id("run").replace("run_", "res_")
    with owner_engine.begin() as c:
        # inv.resources references inv.nodes, so the node identity has to exist
        # first. Written as the owner here because this stands in for the core's
        # own observation path, which the gateway deliberately does not perform.
        c.execute(
            text(
                "INSERT INTO inv.tenants (tenant_id, name) VALUES (:t, 'seam') "
                "ON CONFLICT DO NOTHING"
            ),
            {"t": seam["tenant_a"]},
        )
        c.execute(
            text(
                "INSERT INTO inv.nodes (tenant_id, node_id, status, heartbeat_at, "
                "recovery_epoch, clock_skew_seconds) VALUES (:t, :n, 'online', "
                "clock_timestamp(), (SELECT epoch FROM inv.control_epoch WHERE singleton), 0) "
                "ON CONFLICT (tenant_id, node_id) DO UPDATE SET status = 'online', "
                "heartbeat_at = clock_timestamp(), "
                "recovery_epoch = excluded.recovery_epoch, clock_skew_seconds = 0"
            ),
            {"t": seam["tenant_a"], "n": seam["node_id"]},
        )
        c.execute(
            text(
                "INSERT INTO inv.resources (tenant_id, resource_id, node_id, kind, "
                "capacity, offered) VALUES (:t, :r, :n, :k, :cap, :off)"
            ),
            {"t": seam["tenant_a"], "r": resource_id, "n": seam["node_id"],
             "k": kind, "cap": offered, "off": offered},
        )
    return resource_id


def _approved_binding(session, seam, owner_engine):
    """Walk the whole business chain and return an approved binding."""
    run = run_service.create_run(
        session,
        tenant_id=seam["tenant_a"],
        workload_id=seam["workload_id"],
        workspace_id=seam["workspace_id"],
        requested_by_user_id=seam["requester"],
        now=NOW,
    )
    permission = handoff_service.check_project_permission(
        session, tenant_id=seam["tenant_a"], project_id=seam["project_id"],
        user_id=seam["requester"],
    )
    lock = handoff_service.stop_editing(
        session, tenant_id=seam["tenant_a"], workspace_id=seam["workspace_id"],
        run_id=run.run_id, user_id=seam["requester"], content_sha256=DIGEST, now=NOW,
    )
    version = gateway.project_identity(
        session, tenant_id=seam["tenant_a"], tenant_name="seam",
        project_id=seam["project_id"], run_id=run.run_id,
    )
    gateway.project_node(
        session, tenant_id=seam["tenant_a"], node_id=seam["node_id"]
    )
    binding = handoff_service.freeze_inputs(
        session, tenant_id=seam["tenant_a"], project_id=seam["project_id"],
        run_id=run.run_id, workspace_id=seam["workspace_id"], lock=lock,
        permission=permission, step_id="build", source_attempt=1,
        bound_run_version=version, input_sha256=DIGEST, input_size_bytes=64, now=NOW,
    )
    approver = handoff_service.check_project_permission(
        session, tenant_id=seam["tenant_a"], project_id=seam["project_id"],
        user_id=seam["approver"],
    )
    gateway.project_grant(
        session, tenant_id=seam["tenant_a"], project_id=seam["project_id"],
        user_id=seam["approver"],
    )
    handoff_service.attach_approval(
        session, tenant_id=seam["tenant_a"], binding_id=binding.binding_id,
        approval_id=new_id("approval"), permission=approver,
        permission_snapshot_id=None, now=NOW,
    )
    return binding


# --------------------------------------------------------------------------
# Identity: one way, same identifiers
# --------------------------------------------------------------------------


def test_the_run_has_the_same_identifier_on_both_sides(
    app_sessionmaker, owner_engine, seam
):
    """The mapping is identity, and this is where that stops being a claim."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, seam["tenant_a"]):
                run = run_service.create_run(
                    session, tenant_id=seam["tenant_a"],
                    workload_id=seam["workload_id"],
                    workspace_id=seam["workspace_id"],
                    requested_by_user_id=seam["requester"], now=NOW,
                )
                run_id = run.run_id
                gateway.project_identity(
                    session, tenant_id=seam["tenant_a"], tenant_name="seam",
                    project_id=seam["project_id"], run_id=run_id,
                )
    with owner_engine.connect() as c:
        core = c.execute(
            text("SELECT run_id, project_id, state FROM inv.runs WHERE run_id = :r"),
            {"r": run_id},
        ).one()
    assert core[0] == run_id
    assert core[1] == seam["project_id"]
    # Walked to a state that may hold a reservation, one legal edge at a time.
    assert core[2] == "planned"


def test_projecting_twice_does_not_disturb_a_run_the_core_has_moved(
    app_sessionmaker, owner_engine, seam
):
    """A retry must not walk a Run backwards or bump its version again."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, seam["tenant_a"]):
                run = run_service.create_run(
                    session, tenant_id=seam["tenant_a"],
                    workload_id=seam["workload_id"],
                    workspace_id=seam["workspace_id"],
                    requested_by_user_id=seam["requester"], now=NOW,
                )
                first = gateway.project_identity(
                    session, tenant_id=seam["tenant_a"], tenant_name="seam",
                    project_id=seam["project_id"], run_id=run.run_id,
                )
                again = gateway.project_identity(
                    session, tenant_id=seam["tenant_a"], tenant_name="seam",
                    project_id=seam["project_id"], run_id=run.run_id,
                )
    assert first == again


def test_a_revoked_membership_becomes_a_revoked_grant(
    app_sessionmaker, owner_engine, seam
):
    """A projection that only ever adds is a permission system that only grows.

    The grant is disabled rather than deleted: approval rows point at
    project_grants, so removing one would either fail on the foreign key or
    orphan the history of a decision that really was authorised when it was
    made.
    """
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, seam["tenant_a"]):
                gateway.project_identity(
                    session, tenant_id=seam["tenant_a"], tenant_name="seam",
                    project_id=seam["project_id"], run_id=new_id("run"),
                )
                gateway.project_grant(
                    session, tenant_id=seam["tenant_a"],
                    project_id=seam["project_id"], user_id=seam["approver"],
                )
    with owner_engine.connect() as c:
        granted = c.execute(
            text(
                "SELECT can_request, can_approve, enabled FROM inv.project_grants "
                "WHERE subject_id = :u"
            ),
            {"u": seam["approver"]},
        ).one()
    # The permissions came from public.project_members, not from the caller:
    # an approver may approve and may not request.
    assert granted == (False, True, True)

    with owner_engine.begin() as c:
        c.execute(
            text("DELETE FROM project_members WHERE user_id = :u"),
            {"u": seam["approver"]},
        )
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, seam["tenant_a"]):
                gateway.project_grant(
                    session, tenant_id=seam["tenant_a"],
                    project_id=seam["project_id"], user_id=seam["approver"],
                )
    with owner_engine.connect() as c:
        revoked = c.execute(
            text(
                "SELECT can_request, can_approve, enabled FROM inv.project_grants "
                "WHERE subject_id = :u"
            ),
            {"u": seam["approver"]},
        ).one()
    assert revoked == (False, False, False)


def test_the_business_surface_cannot_declare_a_node_alive(
    app_sessionmaker, owner_engine, seam
):
    """Node liveness is measured, not asserted.

    The projection gives the core a node identity so a resource row can point
    at it, and leaves the node offline. A control plane able to declare a node
    online is one able to place work on a machine that is gone — and the core
    refuses the reservation, which is how the first version of this projection
    was caught.
    """
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, seam["tenant_a"]):
                gateway.project_identity(
                    session, tenant_id=seam["tenant_a"], tenant_name="seam",
                    project_id=seam["project_id"], run_id=new_id("run"),
                )
                gateway.project_node(
                    session, tenant_id=seam["tenant_a"], node_id=seam["node_id"]
                )
    with owner_engine.connect() as c:
        status = c.execute(
            text("SELECT status FROM inv.nodes WHERE node_id = :n"),
            {"n": seam["node_id"]},
        ).scalar_one()
    assert status == "offline"


# --------------------------------------------------------------------------
# Resources: resolved, never invented
# --------------------------------------------------------------------------


def test_the_kind_vocabularies_are_translated_in_one_place(
    app_sessionmaker, owner_engine, seam
):
    """public says ram; inv says memory. Neither half is asked to change here."""
    resource_id = _observe_resource(owner_engine, seam, kind="memory")
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, seam["tenant_a"]):
                gateway.project_node(
                    session, tenant_id=seam["tenant_a"], node_id=seam["node_id"]
                )
                resolved = gateway.resolve_resource(
                    session, tenant_id=seam["tenant_a"],
                    node_id=seam["node_id"], kind="ram",
                )
    assert resolved == resource_id


def test_an_unobserved_resource_is_refused_not_created(app_sessionmaker, seam):
    """A row written to make a reservation succeed is capacity nobody measured."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, seam["tenant_a"]):
                with pytest.raises(InvError, match="has not observed this resource"):
                    gateway.resolve_resource(
                        session, tenant_id=seam["tenant_a"],
                        node_id=seam["node_id"], kind="ram",
                    )


# --------------------------------------------------------------------------
# Reserving through the core, in one transaction
# --------------------------------------------------------------------------


def test_an_approved_binding_reserves_and_becomes_queued(
    app_sessionmaker, owner_engine, seam
):
    """The whole chain, ending in capacity actually held by the execution core."""
    _observe_resource(owner_engine, seam, kind="memory", offered=64 * GIB)
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, seam["tenant_a"]):
                binding = _approved_binding(session, seam, owner_engine)
                leases = gateway.reserve_for_binding(
                    session, tenant_id=seam["tenant_a"], binding=binding,
                    allocations=[(seam["node_id"], "ram", 8 * GIB)], now=NOW,
                )
                binding_id = binding.binding_id
                run_id = binding.run_id

    assert len(leases) == 1
    assert leases[0]["amount"] == 8 * GIB
    # A fencing token, from the core's own sequence.
    assert leases[0]["fencingToken"]

    with owner_engine.connect() as c:
        held = c.execute(
            text(
                "SELECT sum(amount) FROM inv.resource_leases "
                "WHERE run_id = :r AND released_at IS NULL"
            ),
            {"r": run_id},
        ).scalar_one()
        state = c.execute(
            text("SELECT state FROM execution_bindings WHERE binding_id = :b"),
            {"b": binding_id},
        ).scalar_one()
    assert held == 8 * GIB
    assert state == "queued"


def test_the_reservation_and_its_reason_commit_together(
    app_sessionmaker, owner_engine, seam
):
    """One transaction across two schemas.

    If the binding update failed after the lease was written, capacity would be
    held for a decision nobody can find. Rolling back must take both.
    """
    _observe_resource(owner_engine, seam, kind="memory", offered=64 * GIB)
    with app_sessionmaker() as session:
        try:
            with session.begin():
                with tenant_scope(session, seam["tenant_a"]):
                    binding = _approved_binding(session, seam, owner_engine)
                    run_id = binding.run_id
                    gateway.reserve_for_binding(
                        session, tenant_id=seam["tenant_a"], binding=binding,
                        allocations=[(seam["node_id"], "ram", 8 * GIB)], now=NOW,
                    )
                    raise RuntimeError("something after the reservation failed")
        except RuntimeError:
            pass

    with owner_engine.connect() as c:
        leases = c.execute(
            text("SELECT count(*) FROM inv.resource_leases WHERE run_id = :r"),
            {"r": run_id},
        ).scalar_one()
        bindings = c.execute(
            text("SELECT count(*) FROM execution_bindings WHERE run_id = :r"),
            {"r": run_id},
        ).scalar_one()
    assert leases == 0
    assert bindings == 0


def test_a_binding_from_an_older_epoch_cannot_reserve(
    app_sessionmaker, owner_engine, seam
):
    """The recorded epoch, one layer deeper than the handoff check.

    The core stamps leases with the epoch it is handed and matches nodes against
    it. A binding prepared before an operator reconciled finds no ready node,
    so even a caller that skipped the business-surface check cannot reserve
    against a world that no longer exists.
    """
    _observe_resource(owner_engine, seam, kind="memory", offered=64 * GIB)
    stale = "00000000-0000-4000-8000-000000000000"
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, seam["tenant_a"]):
                run = run_service.create_run(
                    session, tenant_id=seam["tenant_a"],
                    workload_id=seam["workload_id"],
                    workspace_id=seam["workspace_id"],
                    requested_by_user_id=seam["requester"], now=NOW,
                )
                gateway.project_identity(
                    session, tenant_id=seam["tenant_a"], tenant_name="seam",
                    project_id=seam["project_id"], run_id=run.run_id,
                )
                gateway.project_node(
                    session, tenant_id=seam["tenant_a"], node_id=seam["node_id"]
                )
                with pytest.raises(InvError, match="refused the reservation"):
                    gateway.reserve(
                        session, tenant_id=seam["tenant_a"],
                        project_id=seam["project_id"], run_id=run.run_id,
                        recovery_epoch=stale,
                        allocations=[(seam["node_id"], "ram", 8 * GIB)],
                        idempotency_key="stale-epoch",
                    )


def test_only_an_approved_binding_may_reserve(app_sessionmaker, owner_engine, seam):
    """Frozen is not approved. Reserving on a freeze spends capacity on a proposal."""
    _observe_resource(owner_engine, seam, kind="memory", offered=64 * GIB)
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, seam["tenant_a"]):
                run = run_service.create_run(
                    session, tenant_id=seam["tenant_a"],
                    workload_id=seam["workload_id"],
                    workspace_id=seam["workspace_id"],
                    requested_by_user_id=seam["requester"], now=NOW,
                )
                permission = handoff_service.check_project_permission(
                    session, tenant_id=seam["tenant_a"],
                    project_id=seam["project_id"], user_id=seam["requester"],
                )
                lock = handoff_service.stop_editing(
                    session, tenant_id=seam["tenant_a"],
                    workspace_id=seam["workspace_id"], run_id=run.run_id,
                    user_id=seam["requester"], content_sha256=DIGEST, now=NOW,
                )
                version = gateway.project_identity(
                    session, tenant_id=seam["tenant_a"], tenant_name="seam",
                    project_id=seam["project_id"], run_id=run.run_id,
                )
                binding = handoff_service.freeze_inputs(
                    session, tenant_id=seam["tenant_a"],
                    project_id=seam["project_id"], run_id=run.run_id,
                    workspace_id=seam["workspace_id"], lock=lock,
                    permission=permission, step_id="build", source_attempt=1,
                    bound_run_version=version, input_sha256=DIGEST,
                    input_size_bytes=64, now=NOW,
                )
                with pytest.raises(InvError, match="only an approved binding"):
                    gateway.reserve_for_binding(
                        session, tenant_id=seam["tenant_a"], binding=binding,
                        allocations=[(seam["node_id"], "ram", 8 * GIB)], now=NOW,
                    )


def test_reserving_more_than_the_node_offers_is_refused(
    app_sessionmaker, owner_engine, seam
):
    """The core's ceiling arithmetic, reached through the gateway unchanged."""
    _observe_resource(owner_engine, seam, kind="memory", offered=4 * GIB)
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, seam["tenant_a"]):
                binding = _approved_binding(session, seam, owner_engine)
                with pytest.raises(InvError, match="refused the reservation"):
                    gateway.reserve_for_binding(
                        session, tenant_id=seam["tenant_a"], binding=binding,
                        allocations=[(seam["node_id"], "ram", 8 * GIB)], now=NOW,
                    )
