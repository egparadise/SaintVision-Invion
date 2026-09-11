"""Settings, and whether setting a value actually changes anything.

The acceptance criterion for this work is "화면에서 설정한 값이 실제 저장·권한
검사에 반영됨" — a value set on a screen is really stored and really shows up in
the permission check. Storing it is the easy half. These tests are mostly about
the other half.

The strongest of them is ``test_the_kernel_reads_the_same_vocabulary``: the
execution kernel selects ``public.project_members.role_code`` before it will
start anything, so the role this API writes decides the next execution request.
If the two sides ever spelled a role differently, the setting would save, the
screen would show it, and it would silently mean nothing. That is not a failure
a test of this API alone can catch, so the test reaches across and compares.
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import text

from saintvision.db.session import tenant_scope
from saintvision.errors import InvError
from saintvision.ids import new_id
from saintvision.services import settings as settings_service

pytestmark = pytest.mark.postgres

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 9, 10, 11, 0, 0, tzinfo=UTC)
GIB = 1024**3


@pytest.fixture
def base_org(owner_engine, two_tenants):
    """A project with an owner, a second owner, a viewer, a node and a workspace."""
    tenant_a, tenant_b = two_tenants
    ids = {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "owner": new_id("user"),
        "second_owner": new_id("user"),
        "viewer": new_id("user"),
        "project_id": new_id("project"),
        "workspace_id": new_id("workspace"),
        "node_id": new_id("node"),
        "ram_capability": new_id("capability"),
        "cpu_capability": new_id("capability"),
    }
    with owner_engine.begin() as c:
        for key in ("owner", "second_owner", "viewer"):
            c.execute(
                text(
                    "INSERT INTO users (user_id, tenant_id, external_subject, "
                    "display_name, status, created_at, updated_at, version) "
                    "VALUES (:u, :t, :s, :n, 'active', now(), now(), 1)"
                ),
                {"u": ids[key], "t": tenant_a, "s": ids[key], "n": key},
            )
        c.execute(
            text(
                "INSERT INTO projects (project_id, tenant_id, code, display_name, "
                "status, created_at, version) VALUES (:p, :t, 'o', 'O', 'active', now(), 1)"
            ),
            {"p": ids["project_id"], "t": tenant_a},
        )
        for key, role in (("owner", "owner"), ("viewer", "viewer")):
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
            {"w": ids["workspace_id"], "t": tenant_a, "p": ids["project_id"], "u": ids["owner"]},
        )
        c.execute(
            text(
                "INSERT INTO nodes (node_id, tenant_id, hostname, os_type, os_version, "
                "agent_version, status, enrolled_at, heartbeat_sequence, version) "
                "VALUES (:n, :t, 'set-01', 'linux', '22.04', '0.1', 'active', now(), 0, 1)"
            ),
            {"n": ids["node_id"], "t": tenant_a},
        )
        for key, kind, total, unit, device in (
            ("ram_capability", "ram", 64 * GIB, "bytes", None),
            ("cpu_capability", "cpu", 16_000, "millicores", None),
        ):
            c.execute(
                text(
                    "INSERT INTO node_capabilities (capability_id, tenant_id, node_id, "
                    "kind, device_index, total_quantity, unit, divisible, detected_at, "
                    "version) VALUES (:c, :t, :n, :k, :d, :q, :un, true, now(), 1)"
                ),
                {
                    "c": ids[key],
                    "t": tenant_a,
                    "n": ids["node_id"],
                    "k": kind,
                    "d": device,
                    "q": total,
                    "un": unit,
                },
            )
    return ids


@pytest.fixture
def org(base_org, owner_engine):
    with owner_engine.begin() as c:
        c.execute(
            text("INSERT INTO inv.business_admin_grants VALUES(:t,:u,'resources.manage',true)"),
            {"t": base_org["tenant_a"], "u": base_org["owner"]},
        )
    return base_org


def _permission(session, org, who):
    return settings_service.effective_permission(
        session,
        tenant_id=org["tenant_a"],
        project_id=org["project_id"],
        user_id=org[who],
    )


# --------------------------------------------------------------------------
# The setting is the permission check
# --------------------------------------------------------------------------


def test_the_kernel_reads_the_same_vocabulary(app_sessionmaker, org):
    """The one that makes this feature real rather than cosmetic.

    ``inv.business_auth`` selects ``public.project_members.role_code`` before it
    will start any execution. If this API wrote ``admin`` where the kernel looks
    for ``owner``, the value would save, the screen would render it, and the
    kernel would refuse every request without either side being wrong on its
    own terms.
    """
    from inv import business_auth

    assert settings_service.CAN_REQUEST == business_auth.REQUEST_ROLES, (
        "the business surface and the execution kernel disagree about which "
        "roles may request work. A role set on a screen would save and mean "
        "nothing."
    )
    assert settings_service.CAN_APPROVE == business_auth.APPROVE_ROLES
    # And every role either side recognises is one this API will accept.
    assert business_auth.REQUEST_ROLES | business_auth.APPROVE_ROLES <= set(
        settings_service.PROJECT_ROLES
    )


def test_setting_a_role_changes_what_the_user_may_do(app_sessionmaker, org):
    """Not "the row was written" — what the platform will now permit."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, org["tenant_a"]):
                before = _permission(session, org, "viewer")
                assert not before["canRequest"]

                after = settings_service.set_member_role(
                    session,
                    tenant_id=org["tenant_a"],
                    project_id=org["project_id"],
                    user_id=org["viewer"],
                    role_code="maintainer",
                    acting_user_id=org["owner"],
                    now=NOW,
                )
    assert after["canRequest"]
    assert not after["canApprove"]
    assert after["roleCode"] == "maintainer"


def test_suspending_a_user_denies_them_immediately(app_sessionmaker, org):
    """Effective everywhere at once, because the kernel reads this row.

    A suspension that only took effect at the next login would leave an open
    session approving work for as long as its token lasted.
    """
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, org["tenant_a"]):
                assert _permission(session, org, "owner")["canApprove"]
                settings_service.set_user_status(
                    session,
                    tenant_id=org["tenant_a"],
                    user_id=org["owner"],
                    status="suspended",
                    now=NOW,
                )
                after = _permission(session, org, "owner")
    # The role is unchanged and the permission is gone. A screen that rendered
    # the role alone would show an owner who may do nothing.
    assert after["roleCode"] == "owner"
    assert not after["canApprove"]
    assert not after["canRequest"]
    assert not after["canAdminister"]


def test_archiving_a_project_stops_everything_in_it(app_sessionmaker, org):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, org["tenant_a"]):
                settings_service.set_project_status(
                    session,
                    tenant_id=org["tenant_a"],
                    project_id=org["project_id"],
                    status="archived",
                    acting_user_id=org["owner"],
                )
                after = _permission(session, org, "owner")
    assert after["projectStatus"] == "archived"
    assert not after["canRequest"] and not after["canApprove"]


def test_a_retired_user_cannot_be_brought_back(app_sessionmaker, org):
    """Retirement is how a person leaves. Undoing it would restore an account
    without anyone re-granting anything."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, org["tenant_a"]):
                settings_service.set_user_status(
                    session,
                    tenant_id=org["tenant_a"],
                    user_id=org["viewer"],
                    status="retired",
                    now=NOW,
                )
                with pytest.raises(InvError, match="cannot be reactivated"):
                    settings_service.set_user_status(
                        session,
                        tenant_id=org["tenant_a"],
                        user_id=org["viewer"],
                        status="active",
                        now=NOW,
                    )


# --------------------------------------------------------------------------
# Who may change settings
# --------------------------------------------------------------------------


def test_only_an_owner_may_change_settings(app_sessionmaker, org):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, org["tenant_a"]):
                with pytest.raises(InvError, match="only a project owner"):
                    settings_service.set_member_role(
                        session,
                        tenant_id=org["tenant_a"],
                        project_id=org["project_id"],
                        user_id=org["viewer"],
                        role_code="owner",
                        acting_user_id=org["viewer"],
                        now=NOW,
                    )


def test_a_project_cannot_lose_its_last_owner(app_sessionmaker, org):
    """A project with no owner works until someone needs to change something.

    Then nobody can, and the change that caused it was made long enough ago
    that nobody connects the two.
    """
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, org["tenant_a"]):
                with pytest.raises(InvError, match="only owner"):
                    settings_service.set_member_role(
                        session,
                        tenant_id=org["tenant_a"],
                        project_id=org["project_id"],
                        user_id=org["owner"],
                        role_code="viewer",
                        acting_user_id=org["owner"],
                        now=NOW,
                    )
                with pytest.raises(InvError, match="only owner"):
                    settings_service.remove_member(
                        session,
                        tenant_id=org["tenant_a"],
                        project_id=org["project_id"],
                        user_id=org["owner"],
                        acting_user_id=org["owner"],
                    )


def test_a_second_owner_makes_the_first_removable(app_sessionmaker, org):
    """The rule is "a project keeps an owner", not "an owner is permanent"."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, org["tenant_a"]):
                settings_service.set_member_role(
                    session,
                    tenant_id=org["tenant_a"],
                    project_id=org["project_id"],
                    user_id=org["second_owner"],
                    role_code="owner",
                    acting_user_id=org["owner"],
                    now=NOW,
                )
                settings_service.set_member_role(
                    session,
                    tenant_id=org["tenant_a"],
                    project_id=org["project_id"],
                    user_id=org["owner"],
                    role_code="viewer",
                    acting_user_id=org["owner"],
                    now=NOW,
                )
                remaining = _permission(session, org, "second_owner")
    assert remaining["canAdminister"]


# --------------------------------------------------------------------------
# What a machine offers
# --------------------------------------------------------------------------


def test_an_offer_is_superseded_not_edited(app_sessionmaker, org):
    """effective_from/effective_to exist so a past placement stays explainable.

    Editing the row in place would rewrite the reason for a decision that has
    already happened.
    """
    later = NOW + dt.timedelta(hours=1)
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, org["tenant_a"]):
                settings_service.set_resource_offer(
                    session,
                    acting_user_id=org["owner"],
                    tenant_id=org["tenant_a"],
                    capability_id=org["ram_capability"],
                    offered_quantity=48,
                    unit="GiB",
                    now=NOW,
                )
                settings_service.set_resource_offer(
                    session,
                    acting_user_id=org["owner"],
                    tenant_id=org["tenant_a"],
                    capability_id=org["ram_capability"],
                    offered_quantity=32,
                    unit="GiB",
                    now=later,
                )
                rows = session.execute(
                    text(
                        "SELECT offered_quantity, effective_from, effective_to "
                        "FROM resource_offers WHERE capability_id = :c "
                        "ORDER BY effective_from"
                    ),
                    {"c": org["ram_capability"]},
                ).all()
    assert len(rows) == 2
    # The old offer is closed at the moment the new one opens, so a placement
    # made in between resolves to exactly one offer.
    assert rows[0][0] == 48 * GIB and rows[0][2] == later
    assert rows[1][0] == 32 * GIB and rows[1][2] is None


def test_the_unit_is_converted_once_at_the_boundary(app_sessionmaker, org):
    """Two screens describing the same machine must store the same number."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, org["tenant_a"]):
                in_gib = settings_service.set_resource_offer(
                    session,
                    acting_user_id=org["owner"],
                    tenant_id=org["tenant_a"],
                    capability_id=org["ram_capability"],
                    offered_quantity=32,
                    unit="GiB",
                    now=NOW,
                )
                in_bytes = settings_service.set_resource_offer(
                    session,
                    acting_user_id=org["owner"],
                    tenant_id=org["tenant_a"],
                    capability_id=org["ram_capability"],
                    offered_quantity=32 * GIB,
                    unit="bytes",
                    now=NOW + dt.timedelta(minutes=1),
                )
    assert in_gib["offeredQuantity"] == in_bytes["offeredQuantity"] == 32 * GIB
    assert in_gib["unit"] == "bytes"
    # Identical value, so no second row was written for a change that was not one.
    assert in_bytes["previousOfferedQuantity"] == 32 * GIB


def test_a_node_cannot_offer_more_than_it_has(app_sessionmaker, org):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, org["tenant_a"]):
                with pytest.raises(InvError, match="cannot offer more than it has"):
                    settings_service.set_resource_offer(
                        session,
                        acting_user_id=org["owner"],
                        tenant_id=org["tenant_a"],
                        capability_id=org["ram_capability"],
                        offered_quantity=128,
                        unit="GiB",
                        now=NOW,
                    )


def test_a_unit_from_the_wrong_kind_is_refused(app_sessionmaker, org):
    """ "cores" is a real unit and is not a real unit of memory."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, org["tenant_a"]):
                with pytest.raises(InvError, match="not a recognised unit"):
                    settings_service.set_resource_offer(
                        session,
                        acting_user_id=org["owner"],
                        tenant_id=org["tenant_a"],
                        capability_id=org["ram_capability"],
                        offered_quantity=8,
                        unit="cores",
                        now=NOW,
                    )


def test_lowering_an_offer_says_what_it_does_not_do(app_sessionmaker, org):
    """An offer is a ceiling for new work, not a recall of running work.

    The operator who lowers it is the person most likely to assume otherwise.
    """
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, org["tenant_a"]):
                settings_service.set_resource_offer(
                    session,
                    acting_user_id=org["owner"],
                    tenant_id=org["tenant_a"],
                    capability_id=org["ram_capability"],
                    offered_quantity=48,
                    unit="GiB",
                    now=NOW,
                )
                lowered = settings_service.set_resource_offer(
                    session,
                    acting_user_id=org["owner"],
                    tenant_id=org["tenant_a"],
                    capability_id=org["ram_capability"],
                    offered_quantity=8,
                    unit="GiB",
                    now=NOW + dt.timedelta(minutes=1),
                )
    assert "already leased" in lowered["note"]


def test_the_pool_reports_what_was_just_offered(app_sessionmaker, org):
    """End to end: a value set here is the value placement reads.

    The setting is only real if the thing that spends capacity sees it.
    """
    from saintvision.services import pools as pool_service

    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, org["tenant_a"]):
                settings_service.set_resource_offer(
                    session,
                    acting_user_id=org["owner"],
                    tenant_id=org["tenant_a"],
                    capability_id=org["ram_capability"],
                    offered_quantity=24,
                    unit="GiB",
                    now=NOW,
                )
                pool = pool_service.create_pool(
                    session,
                    tenant_id=org["tenant_a"],
                    project_id=org["project_id"],
                    name="p",
                    created_by_user_id=org["owner"],
                    now=NOW,
                )
                pool_service.add_member(
                    session,
                    tenant_id=org["tenant_a"],
                    pool_id=pool.pool_id,
                    node_id=org["node_id"],
                    added_by_user_id=org["owner"],
                    now=NOW,
                )
                capacity = pool_service.pool_capacity(
                    session, tenant_id=org["tenant_a"], pool_id=pool.pool_id, now=NOW
                )
    assert capacity["totalOffered"]["ram"] == 24 * GIB
    assert capacity["units"]["ram"] == "bytes"


def test_offers_are_listed_beside_what_the_machine_actually_has(app_sessionmaker, org):
    """A screen showing only the offer cannot tell if there is room to raise it."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, org["tenant_a"]):
                settings_service.set_resource_offer(
                    session,
                    acting_user_id=org["owner"],
                    tenant_id=org["tenant_a"],
                    capability_id=org["cpu_capability"],
                    offered_quantity=8,
                    unit="cores",
                    now=NOW,
                )
                listed = settings_service.node_offers(
                    session, tenant_id=org["tenant_a"], node_id=org["node_id"], now=NOW
                )
    by_kind = {row["kind"]: row for row in listed}
    assert by_kind["cpu"]["offeredQuantity"] == 8_000
    assert by_kind["cpu"]["totalQuantity"] == 16_000
    assert by_kind["cpu"]["unit"] == "millicores"
    # A capability with no offer yet reports zero rather than being absent.
    assert by_kind["ram"]["offeredQuantity"] == 0


# --------------------------------------------------------------------------
# Workspaces
# --------------------------------------------------------------------------


def test_a_workspace_reaches_deleted_only_through_deleting(app_sessionmaker, org):
    """A workspace that jumps to deleted is one whose files nothing removed."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, org["tenant_a"]):
                with pytest.raises(InvError, match="cannot go from"):
                    settings_service.set_workspace_status(
                        session,
                        tenant_id=org["tenant_a"],
                        workspace_id=org["workspace_id"],
                        status="deleted",
                        acting_user_id=org["owner"],
                        now=NOW,
                    )
                settings_service.set_workspace_status(
                    session,
                    tenant_id=org["tenant_a"],
                    workspace_id=org["workspace_id"],
                    status="deleting",
                    acting_user_id=org["owner"],
                    now=NOW,
                )
                deleted = settings_service.set_workspace_status(
                    session,
                    tenant_id=org["tenant_a"],
                    workspace_id=org["workspace_id"],
                    status="deleted",
                    acting_user_id=org["owner"],
                    now=NOW,
                )
    assert deleted.deleted_at is not None


# --------------------------------------------------------------------------
# An offer only means something if the thing that grants leases reads it
# --------------------------------------------------------------------------


def _observe(owner_engine, org, *, kind="memory", capacity=64 * GIB):
    """What the kernel's own probes would have recorded on this node."""
    resource_id = new_id("run").replace("run_", "res_")
    with owner_engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO inv.tenants (tenant_id, name) VALUES (:t, 'o') "
                "ON CONFLICT DO NOTHING"
            ),
            {"t": org["tenant_a"]},
        )
        c.execute(
            text(
                "INSERT INTO inv.nodes (tenant_id, node_id, status, heartbeat_at, "
                "recovery_epoch, clock_skew_seconds) VALUES (:t, :n, 'online', "
                "clock_timestamp(), gen_random_uuid(), 0) ON CONFLICT DO NOTHING"
            ),
            {"t": org["tenant_a"], "n": org["node_id"]},
        )
        c.execute(
            text(
                "INSERT INTO inv.resources (tenant_id, resource_id, node_id, kind, "
                "capacity, offered) VALUES (:t, :r, :n, :k, :cap, 0)"
            ),
            {
                "t": org["tenant_a"],
                "r": resource_id,
                "n": org["node_id"],
                "k": kind,
                "cap": capacity,
            },
        )
    return resource_id


def test_an_offer_reaches_what_the_kernel_grants_leases_against(
    app_sessionmaker, owner_engine, org
):
    """Until this, a lowered offer changed a number no scheduler read.

    The machine kept accepting the work its owner had just said it should stop
    taking, and nothing anywhere reported a disagreement.
    """
    resource_id = _observe(owner_engine, org)
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, org["tenant_a"]):
                body = settings_service.set_resource_offer(
                    session,
                    acting_user_id=org["owner"],
                    tenant_id=org["tenant_a"],
                    capability_id=org["ram_capability"],
                    offered_quantity=24,
                    unit="GiB",
                    now=NOW,
                )
    assert body["appliedToKernel"] is True
    assert body["kernelResourceId"] == resource_id
    with owner_engine.connect() as c:
        offered = c.execute(
            text("SELECT offered FROM inv.resources WHERE resource_id = :r"),
            {"r": resource_id},
        ).scalar_one()
    assert offered == 24 * GIB


def test_an_offer_below_what_is_already_leased_is_refused(app_sessionmaker, owner_engine, org):
    """The kernel's rule, and it is stricter than "a ceiling for future work".

    Accepting it would leave the kernel holding more than the owner now permits.
    """
    resource_id = _observe(owner_engine, org)
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, org["tenant_a"]):
                settings_service.set_resource_offer(
                    session,
                    acting_user_id=org["owner"],
                    tenant_id=org["tenant_a"],
                    capability_id=org["ram_capability"],
                    offered_quantity=48,
                    unit="GiB",
                    now=NOW,
                )
    # Something is running against it.
    with owner_engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO inv.projects (tenant_id, project_id) VALUES (:t, :p) "
                "ON CONFLICT DO NOTHING"
            ),
            {"t": org["tenant_a"], "p": org["project_id"]},
        )
        run_id = new_id("run")
        c.execute(
            text("INSERT INTO inv.runs (tenant_id, project_id, run_id) " "VALUES (:t, :p, :r)"),
            {"t": org["tenant_a"], "p": org["project_id"], "r": run_id},
        )
        c.execute(
            text(
                "INSERT INTO inv.resource_leases (tenant_id, project_id, run_id, "
                "resource_id, lease_id, amount, recovery_epoch, expires_at) "
                "VALUES (:t, :p, :r, :res, :l, :a, gen_random_uuid(), "
                "clock_timestamp() + interval '1 hour')"
            ),
            {
                "t": org["tenant_a"],
                "p": org["project_id"],
                "r": run_id,
                "res": resource_id,
                "l": new_id("run").replace("run_", "lse_"),
                "a": 32 * GIB,
            },
        )

    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, org["tenant_a"]):
                with pytest.raises(InvError, match="already leased exceeds"):
                    settings_service.set_resource_offer(
                        session,
                        acting_user_id=org["owner"],
                        tenant_id=org["tenant_a"],
                        capability_id=org["ram_capability"],
                        offered_quantity=8,
                        unit="GiB",
                        now=NOW + dt.timedelta(minutes=1),
                    )


def test_an_unobserved_node_is_reported_not_refused(app_sessionmaker, org):
    """A machine the kernel has never measured is a normal state.

    An owner recording what they intend to offer on a node that is not enrolled
    for execution yet should not be blocked by that.
    """
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, org["tenant_a"]):
                body = settings_service.set_resource_offer(
                    session,
                    acting_user_id=org["owner"],
                    tenant_id=org["tenant_a"],
                    capability_id=org["ram_capability"],
                    offered_quantity=16,
                    unit="GiB",
                    now=NOW,
                )
    assert body["appliedToKernel"] is False
    assert body["kernelReasonCode"] == "resource_not_registered"
    assert body["offeredQuantity"] == 16 * GIB


def test_applying_an_offer_is_bound_to_the_session_tenant(
    app_sessionmaker, owner_engine, org, two_tenants
):
    """A definer function bypasses RLS, and this one writes.

    Revision 0027 had to correct exactly this shape on a read path; repeating it
    where the function changes what can be spent would be worse.
    """
    _, tenant_b = two_tenants
    _observe(owner_engine, org)
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, org["tenant_a"]):
                applied, reason, _, _ = session.execute(
                    text(
                        "SELECT applied, reason, resource_ids, "
                        "capacity FROM "
                        "public.apply_capability_offer(:t, CAST(:n AS char(30)), "
                        "CAST(:u AS char(30)), 1)"
                    ),
                    {"t": str(tenant_b), "n": org["ram_capability"], "u": org["owner"]},
                ).one()
    assert applied is False
    assert reason == "tenant_scope_mismatch"
