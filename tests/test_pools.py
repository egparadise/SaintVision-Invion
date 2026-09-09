"""Discovery, pools and distributed placement against a real PostgreSQL.

Two things these tests exist to hold:

* Announcing must grant nothing. A machine on the network can make itself
  visible and can do nothing else.
* A pool total must never stand alone. The sum, the largest single node and the
  idle capacity are three different numbers, and the one that answers "can this
  job run" is the second.
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from saintvision.db.session import tenant_scope
from saintvision.errors import InvError
from saintvision.ids import new_id
from saintvision.services import discovery as discovery_service
from saintvision.services import pools as pool_service
from saintvision.services import runs as run_service

pytestmark = pytest.mark.postgres

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 9, 10, 7, 0, 0, tzinfo=UTC)

GIB = 1024**3


def _announcement(instance="agent-01", hostname="lab-01", ram=32 * GIB, gpus=1):
    return discovery_service.Announcement(
        instance_id=instance,
        hostname=hostname,
        os_type="linux",
        os_version="22.04",
        agent_version="0.1.0",
        cpu_cores=16,
        ram_bytes=ram,
        gpu_count=gpus,
    )


@pytest.fixture
def lab(owner_engine, two_tenants):
    """A project, a pool and three nodes with offers and utilisation."""
    tenant_a, tenant_b = two_tenants
    ids = {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "user_id": new_id("user"),
        "project_id": new_id("project"),
        "workspace_id": new_id("workspace"),
        "workload_id": new_id("workload"),
        "pool_id": new_id("pool"),
        "nodes": [],
    }
    digest = run_service.workload_digest({"objective": "train"})
    with owner_engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO users (user_id, tenant_id, external_subject, display_name, "
                "status, created_at, updated_at, version) "
                "VALUES (:u, :t, 'sub', 'U', 'active', now(), now(), 1)"
            ),
            {"u": ids["user_id"], "t": tenant_a},
        )
        c.execute(
            text(
                "INSERT INTO projects (project_id, tenant_id, code, display_name, status, "
                "created_at, version) VALUES (:p, :t, 'a', 'A', 'active', now(), 1)"
            ),
            {"p": ids["project_id"], "t": tenant_a},
        )
        c.execute(
            text(
                "INSERT INTO workspaces (workspace_id, tenant_id, project_id, name, status, "
                "created_by_user_id, created_at, version) "
                "VALUES (:w, :t, :p, 'ws', 'ready', :u, now(), 1)"
            ),
            {"w": ids["workspace_id"], "t": tenant_a, "p": ids["project_id"], "u": ids["user_id"]},
        )
        c.execute(
            text(
                "INSERT INTO workloads (workload_id, tenant_id, project_id, kind, objective, "
                "spec, spec_sha256, contract_version, created_by_user_id, created_at, version) "
                "VALUES (:wl, :t, :p, 'batch', 'train', '{}', :d, '1.0.0', :u, now(), 1)"
            ),
            {"wl": ids["workload_id"], "t": tenant_a, "p": ids["project_id"],
             "d": digest, "u": ids["user_id"]},
        )
        c.execute(
            text(
                "INSERT INTO resource_pools (pool_id, tenant_id, project_id, name, status, "
                "created_by_user_id, created_at, version) "
                "VALUES (:pl, :t, :p, 'lab', 'active', :u, now(), 1)"
            ),
            {"pl": ids["pool_id"], "t": tenant_a, "p": ids["project_id"], "u": ids["user_id"]},
        )

        # Three nodes: 32/64/32 GiB RAM, all offering everything they have.
        # Node B is the only one that can hold a 48 GiB shard by itself.
        for index, (ram_gib, gpus, used_ram_gib) in enumerate(
            [(32, 1, 24), (64, 2, 8), (32, 1, 0)]
        ):
            node_id = new_id("node")
            ids["nodes"].append(node_id)
            c.execute(
                text(
                    "INSERT INTO nodes (node_id, tenant_id, hostname, os_type, os_version, "
                    "agent_version, status, enrolled_at, heartbeat_sequence, version) "
                    "VALUES (:n, :t, :h, 'linux', '22.04', '0.1', 'active', now(), 0, 1)"
                ),
                {"n": node_id, "t": tenant_a, "h": f"lab-{index:02d}"},
            )
            c.execute(
                text(
                    "INSERT INTO resource_pool_members (tenant_id, pool_id, node_id, "
                    "added_by_user_id, added_at) VALUES (:t, :pl, :n, :u, now())"
                ),
                {"t": tenant_a, "pl": ids["pool_id"], "n": node_id, "u": ids["user_id"]},
            )
            for kind, total, used, unit, device in (
                ("ram", ram_gib, used_ram_gib, "GiB", None),
                ("gpu", gpus, 0, "device", 0),
                ("cpu", 16, 2, "core", None),
            ):
                capability_id = new_id("capability")
                c.execute(
                    text(
                        "INSERT INTO node_capabilities (capability_id, tenant_id, node_id, kind, "
                        "device_index, total_quantity, unit, divisible, detected_at, version) "
                        "VALUES (:c, :t, :n, :k, :d, :q, :un, true, now(), 1)"
                    ),
                    {"c": capability_id, "t": tenant_a, "n": node_id, "k": kind,
                     "d": device, "q": total, "un": unit},
                )
                c.execute(
                    text(
                        "INSERT INTO resource_offers (offer_id, tenant_id, capability_id, "
                        "offered_quantity, unit, effective_from, version) "
                        "VALUES (:o, :t, :c, :q, :un, :ef, 1)"
                    ),
                    {"o": new_id("offer"), "t": tenant_a, "c": capability_id,
                     "q": total, "un": unit, "ef": NOW - dt.timedelta(hours=1)},
                )
                c.execute(
                    text(
                        "INSERT INTO resource_snapshots (snapshot_id, observed_at, tenant_id, "
                        "node_id, capability_id, used_quantity, unit, detail) "
                        "VALUES (:s, :o, :t, :n, :c, :q, :un, '{}')"
                    ),
                    {"s": new_id("snapshot"), "o": NOW - dt.timedelta(seconds=30),
                     "t": tenant_a, "n": node_id, "c": capability_id, "q": used, "un": unit},
                )
    return ids


def _req(cpu=0.0, ram=0, gpu=0):
    return pool_service.ShardRequirement(cpu_cores=cpu, ram_bytes=ram, gpu_count=gpu)


# --------------------------------------------------------------------------
# Discovery grants nothing
# --------------------------------------------------------------------------


def test_announcing_creates_a_candidate_and_nothing_else(app_sessionmaker, lab):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, lab["tenant_a"]):
                row = discovery_service.record_announcement(
                    session, tenant_id=lab["tenant_a"], source_ip="10.0.0.9",
                    announcement=_announcement(), now=NOW,
                )
                node_count = session.execute(
                    text("SELECT count(*) FROM nodes WHERE hostname = 'lab-01'")
                ).scalar_one()
                token_count = session.execute(
                    text("SELECT count(*) FROM node_bootstrap_tokens")
                ).scalar_one()
    assert row.state == "candidate"
    assert row.admitted_node_id is None
    # No node, no credential. Visibility is all announcing buys.
    assert node_count == 0
    assert token_count == 0


def test_reannouncing_refreshes_one_row(app_sessionmaker, lab):
    """A restarting agent must not become a thousand candidates."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, lab["tenant_a"]):
                for _ in range(5):
                    row = discovery_service.record_announcement(
                        session, tenant_id=lab["tenant_a"], source_ip="10.0.0.9",
                        announcement=_announcement(), now=NOW,
                    )
                count = session.execute(
                    text("SELECT count(*) FROM node_announcements")
                ).scalar_one()
    assert count == 1
    assert row.announce_count == 5


def test_reannouncing_does_not_revive_a_declined_candidate(app_sessionmaker, lab):
    """Re-announcing must not undo a person's decision."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, lab["tenant_a"]):
                row = discovery_service.record_announcement(
                    session, tenant_id=lab["tenant_a"], source_ip="10.0.0.9",
                    announcement=_announcement(), now=NOW,
                )
                discovery_service.decline_candidate(
                    session, tenant_id=lab["tenant_a"],
                    announcement_id=row.announcement_id, now=NOW, reason="not ours",
                )
                again = discovery_service.record_announcement(
                    session, tenant_id=lab["tenant_a"], source_ip="10.0.0.9",
                    announcement=_announcement(), now=NOW + dt.timedelta(minutes=1),
                )
    assert again.state == "declined"


def test_the_same_instance_id_from_a_different_address_is_a_different_candidate(
    app_sessionmaker, lab
):
    """instance_id is spoofable, so it is never an identity on its own."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, lab["tenant_a"]):
                discovery_service.record_announcement(
                    session, tenant_id=lab["tenant_a"], source_ip="10.0.0.9",
                    announcement=_announcement(), now=NOW,
                )
                discovery_service.record_announcement(
                    session, tenant_id=lab["tenant_a"], source_ip="10.0.0.10",
                    announcement=_announcement(), now=NOW,
                )
                count = session.execute(
                    text("SELECT count(*) FROM node_announcements")
                ).scalar_one()
    assert count == 2


def test_candidate_fields_are_marked_as_claims(app_sessionmaker, lab):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, lab["tenant_a"]):
                discovery_service.record_announcement(
                    session, tenant_id=lab["tenant_a"], source_ip="10.0.0.9",
                    announcement=_announcement(ram=999 * GIB), now=NOW,
                )
                items = discovery_service.list_candidates(
                    session, tenant_id=lab["tenant_a"], now=NOW
                )
    assert items[0]["verified"] is False
    # A wildly overstated figure is stored and surfaced as a claim, not filtered
    # out: the operator sees what the machine said.
    assert items[0]["claimedRamBytes"] == 999 * GIB
    assert all(k.startswith("claimed") for k in items[0] if k.startswith("claim"))


def test_a_stale_candidate_is_hidden_and_can_be_expired(app_sessionmaker, lab):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, lab["tenant_a"]):
                discovery_service.record_announcement(
                    session, tenant_id=lab["tenant_a"], source_ip="10.0.0.9",
                    announcement=_announcement(), now=NOW,
                )
                later = NOW + dt.timedelta(hours=1)
                assert discovery_service.list_candidates(
                    session, tenant_id=lab["tenant_a"], now=later
                ) == []
                expired = discovery_service.expire_stale_candidates(
                    session, tenant_id=lab["tenant_a"], now=later
                )
    assert expired == 1


def test_admission_mints_a_token_but_does_not_create_a_node(app_sessionmaker, lab):
    """Admission authorises joining; the machine still has to prove what it is."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, lab["tenant_a"]):
                row = discovery_service.record_announcement(
                    session, tenant_id=lab["tenant_a"], source_ip="10.0.0.9",
                    announcement=_announcement(), now=NOW,
                )
                issued = discovery_service.admit_candidate(
                    session, tenant_id=lab["tenant_a"],
                    announcement_id=row.announcement_id,
                    admitted_by_user_id=lab["user_id"], now=NOW,
                )
                nodes_named = session.execute(
                    text("SELECT count(*) FROM nodes WHERE hostname = 'lab-01'")
                ).scalar_one()
                state = session.execute(
                    text("SELECT state FROM node_announcements WHERE announcement_id = :a"),
                    {"a": row.announcement_id},
                ).scalar_one()
    assert issued.secret
    assert nodes_named == 0
    # Still a candidate: enrolment has not happened, so nothing may claim it has.
    assert state == "candidate"


def test_admitting_twice_is_refused(app_sessionmaker, lab):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, lab["tenant_a"]):
                row = discovery_service.record_announcement(
                    session, tenant_id=lab["tenant_a"], source_ip="10.0.0.9",
                    announcement=_announcement(), now=NOW,
                )
                discovery_service.decline_candidate(
                    session, tenant_id=lab["tenant_a"],
                    announcement_id=row.announcement_id, now=NOW,
                )
                with pytest.raises(InvError):
                    discovery_service.admit_candidate(
                        session, tenant_id=lab["tenant_a"],
                        announcement_id=row.announcement_id,
                        admitted_by_user_id=lab["user_id"], now=NOW,
                    )


def test_the_database_refuses_an_admitted_state_without_a_node(app_sessionmaker, lab):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, lab["tenant_a"]):
                row = discovery_service.record_announcement(
                    session, tenant_id=lab["tenant_a"], source_ip="10.0.0.9",
                    announcement=_announcement(), now=NOW,
                )
                announcement_id = row.announcement_id
        with pytest.raises((IntegrityError, DBAPIError)):
            with session.begin():
                with tenant_scope(session, lab["tenant_a"]):
                    session.execute(
                        text(
                            "UPDATE node_announcements SET state = 'admitted' "
                            "WHERE announcement_id = :a"
                        ),
                        {"a": announcement_id},
                    )


def test_discovery_is_tenant_isolated(app_sessionmaker, lab):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, lab["tenant_a"]):
                discovery_service.record_announcement(
                    session, tenant_id=lab["tenant_a"], source_ip="10.0.0.9",
                    announcement=_announcement(), now=NOW,
                )
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, lab["tenant_b"]):
                assert discovery_service.list_candidates(
                    session, tenant_id=lab["tenant_b"], now=NOW
                ) == []


# --------------------------------------------------------------------------
# Capacity: three numbers, never one
# --------------------------------------------------------------------------


def test_capacity_reports_the_sum_and_the_single_node_ceiling(app_sessionmaker, lab):
    """The number that answers "can this job run" is not the sum."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, lab["tenant_a"]):
                capacity = pool_service.pool_capacity(
                    session, tenant_id=lab["tenant_a"], pool_id=lab["pool_id"], now=NOW
                )
    # 32 + 64 + 32 across the pool, but the biggest single machine is 64.
    assert capacity["totalOffered"]["ram"] == 128
    assert capacity["largestSingleNode"]["ram"] == 64
    assert capacity["totalOffered"]["gpu"] == 4
    assert capacity["largestSingleNode"]["gpu"] == 2
    # Both are present, so a caller cannot show only the sum by accident.
    assert "largestSingleNode" in capacity
    assert "not shared across machines" in capacity["note"]


def test_spare_reflects_current_utilisation(app_sessionmaker, lab):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, lab["tenant_a"]):
                capacity = pool_service.pool_capacity(
                    session, tenant_id=lab["tenant_a"], pool_id=lab["pool_id"], now=NOW
                )
    # Used RAM is 24 + 8 + 0 of 128 offered.
    assert capacity["spareNow"]["ram"] == 96
    assert capacity["spareNow"]["ram"] < capacity["totalOffered"]["ram"]


def test_a_node_with_no_fresh_snapshot_counts_as_zero_spare(app_sessionmaker, lab):
    """Treating an unmeasured machine as idle is how work lands on a busy one."""
    much_later = NOW + dt.timedelta(hours=2)
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, lab["tenant_a"]):
                capacity = pool_service.pool_capacity(
                    session, tenant_id=lab["tenant_a"], pool_id=lab["pool_id"], now=much_later
                )
    assert capacity["spareNow"]["ram"] == 0
    assert len(capacity["unmeasuredNodes"]) == 3
    # Offered capacity is still reported: the machines exist, we just do not
    # know what they are doing.
    assert capacity["totalOffered"]["ram"] == 128


def test_a_lost_node_does_not_contribute_capacity(owner_engine, app_sessionmaker, lab):
    with owner_engine.begin() as c:
        c.execute(
            text("UPDATE nodes SET status = 'lost' WHERE node_id = :n"),
            {"n": lab["nodes"][1]},
        )
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, lab["tenant_a"]):
                capacity = pool_service.pool_capacity(
                    session, tenant_id=lab["tenant_a"], pool_id=lab["pool_id"], now=NOW
                )
    assert capacity["activeMemberCount"] == 2
    assert capacity["totalOffered"]["ram"] == 64
    assert capacity["largestSingleNode"]["ram"] == 32


# --------------------------------------------------------------------------
# Idle-first placement
# --------------------------------------------------------------------------


def test_ranking_puts_the_idlest_node_first(app_sessionmaker, lab):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, lab["tenant_a"]):
                ranked = pool_service.rank_idle_first(
                    session, tenant_id=lab["tenant_a"], pool_id=lab["pool_id"],
                    requirement=_req(ram=8), now=NOW,
                )
    # Spare RAM: node0 = 8, node1 = 56, node2 = 32. Node 1 is idlest.
    assert ranked[0]["nodeId"] == lab["nodes"][1]
    assert ranked[1]["nodeId"] == lab["nodes"][2]


def test_a_shard_larger_than_any_node_has_no_candidate(app_sessionmaker, lab):
    """The pool sums to 128 GiB; no single machine holds 100."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, lab["tenant_a"]):
                ranked = pool_service.rank_idle_first(
                    session, tenant_id=lab["tenant_a"], pool_id=lab["pool_id"],
                    requirement=_req(ram=100), now=NOW,
                )
    assert ranked == []


def test_ranking_uses_spare_not_offered(app_sessionmaker, lab):
    """Node 0 offers 32 GiB but only 8 are free, so a 16 GiB shard skips it."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, lab["tenant_a"]):
                ranked = pool_service.rank_idle_first(
                    session, tenant_id=lab["tenant_a"], pool_id=lab["pool_id"],
                    requirement=_req(ram=16), now=NOW,
                )
    assert lab["nodes"][0] not in [c["nodeId"] for c in ranked]


def test_a_gpu_shard_is_not_sent_to_the_node_with_the_most_free_ram(
    owner_engine, app_sessionmaker, lab
):
    """Scoring on the dimension the shard needs, not on whatever is largest."""
    # Saturate node 1's GPUs while leaving its RAM free.
    with owner_engine.begin() as c:
        capability_id = c.execute(
            text(
                "SELECT capability_id FROM node_capabilities "
                "WHERE node_id = :n AND kind = 'gpu'"
            ),
            {"n": lab["nodes"][1]},
        ).scalar_one()
        c.execute(
            text(
                "INSERT INTO resource_snapshots (snapshot_id, observed_at, tenant_id, node_id, "
                "capability_id, used_quantity, unit, detail) "
                "VALUES (:s, :o, :t, :n, :c, 2, 'device', '{}')"
            ),
            {"s": new_id("snapshot"), "o": NOW - dt.timedelta(seconds=10),
             "t": lab["tenant_a"], "n": lab["nodes"][1], "c": capability_id},
        )
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, lab["tenant_a"]):
                ranked = pool_service.rank_idle_first(
                    session, tenant_id=lab["tenant_a"], pool_id=lab["pool_id"],
                    requirement=_req(gpu=1), now=NOW,
                )
    assert lab["nodes"][1] not in [c["nodeId"] for c in ranked]


# --------------------------------------------------------------------------
# Distributed plans
# --------------------------------------------------------------------------


def _run(session, lab):
    return run_service.create_run(
        session, tenant_id=lab["tenant_a"], workload_id=lab["workload_id"],
        workspace_id=lab["workspace_id"], requested_by_user_id=lab["user_id"], now=NOW,
    )


def test_splitting_requires_the_workload_to_declare_it(app_sessionmaker, lab):
    """A program that is not shard-aware gives a wrong answer when split."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, lab["tenant_a"]):
                run = _run(session, lab)
                with pytest.raises(InvError, match="declare it can be split"):
                    pool_service.plan_distributed_run(
                        session, tenant_id=lab["tenant_a"], run_id=run.run_id,
                        pool_id=lab["pool_id"], strategy="data_parallel",
                        shard_count=3, requirement=_req(ram=8), now=NOW,
                        splittable_declared=False,
                    )


def test_a_declared_split_places_shards_idlest_first(app_sessionmaker, lab):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, lab["tenant_a"]):
                run = _run(session, lab)
                plan, placements = pool_service.plan_distributed_run(
                    session, tenant_id=lab["tenant_a"], run_id=run.run_id,
                    pool_id=lab["pool_id"], strategy="data_parallel",
                    shard_count=3, requirement=_req(ram=8), now=NOW,
                    splittable_declared=True,
                )
    assert plan.shard_count == 3
    assert len(placements) == 3
    assert placements[0].node_id == lab["nodes"][1]
    # The ranking is kept so the decision can be explained later.
    assert plan.ranking_snapshot["ranked"]


def test_one_node_can_hold_several_shards_when_it_has_room(app_sessionmaker, lab):
    """Node 1 has 56 GiB spare, so it takes more than one 16 GiB shard."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, lab["tenant_a"]):
                run = _run(session, lab)
                _, placements = pool_service.plan_distributed_run(
                    session, tenant_id=lab["tenant_a"], run_id=run.run_id,
                    pool_id=lab["pool_id"], strategy="data_parallel",
                    shard_count=4, requirement=_req(ram=16), now=NOW,
                    splittable_declared=True,
                )
    per_node = {}
    for p in placements:
        per_node[p.node_id] = per_node.get(p.node_id, 0) + 1
    assert per_node[lab["nodes"][1]] >= 2


def test_a_partial_placement_is_refused(app_sessionmaker, lab):
    """Three of five shards running would report success for a job that did not."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, lab["tenant_a"]):
                run = _run(session, lab)
                with pytest.raises(InvError) as caught:
                    pool_service.plan_distributed_run(
                        session, tenant_id=lab["tenant_a"], run_id=run.run_id,
                        pool_id=lab["pool_id"], strategy="data_parallel",
                        shard_count=20, requirement=_req(ram=32), now=NOW,
                        splittable_declared=True,
                    )
    assert "would report success for a job that did not run" in caught.value.message


def test_a_single_node_plan_cannot_have_several_shards(app_sessionmaker, lab):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, lab["tenant_a"]):
                run = _run(session, lab)
                with pytest.raises(InvError):
                    pool_service.plan_distributed_run(
                        session, tenant_id=lab["tenant_a"], run_id=run.run_id,
                        pool_id=lab["pool_id"], strategy="single_node",
                        shard_count=2, requirement=_req(ram=8), now=NOW,
                        splittable_declared=True,
                    )


def test_the_database_refuses_a_split_without_the_declaration(app_sessionmaker, lab):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, lab["tenant_a"]):
                run = _run(session, lab)
                run_id = run.run_id
        with pytest.raises((IntegrityError, DBAPIError)):
            with session.begin():
                with tenant_scope(session, lab["tenant_a"]):
                    session.execute(
                        text(
                            "INSERT INTO distributed_plans (plan_id, tenant_id, run_id, pool_id, "
                            "strategy, state, shard_count, splittable_declared, shard_cpu_cores, "
                            "shard_ram_bytes, shard_gpu_count, ranking_snapshot, created_at, version) "
                            "VALUES (:p, :t, :r, :pl, 'data_parallel', 'planned', 4, false, "
                            "0, 0, 0, '{}', now(), 1)"
                        ),
                        {"p": new_id("plan"), "t": lab["tenant_a"], "r": run_id,
                         "pl": lab["pool_id"]},
                    )


def test_one_run_has_at_most_one_plan(app_sessionmaker, lab):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, lab["tenant_a"]):
                run = _run(session, lab)
                pool_service.plan_distributed_run(
                    session, tenant_id=lab["tenant_a"], run_id=run.run_id,
                    pool_id=lab["pool_id"], strategy="single_node",
                    shard_count=1, requirement=_req(ram=8), now=NOW,
                )
                run_id = run.run_id
        with pytest.raises(IntegrityError):
            with session.begin():
                with tenant_scope(session, lab["tenant_a"]):
                    pool_service.plan_distributed_run(
                        session, tenant_id=lab["tenant_a"], run_id=run_id,
                        pool_id=lab["pool_id"], strategy="single_node",
                        shard_count=1, requirement=_req(ram=8), now=NOW,
                    )


def test_pool_membership_is_idempotent(app_sessionmaker, lab):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, lab["tenant_a"]):
                for _ in range(3):
                    pool_service.add_member(
                        session, tenant_id=lab["tenant_a"], pool_id=lab["pool_id"],
                        node_id=lab["nodes"][0], added_by_user_id=lab["user_id"], now=NOW,
                    )
                count = session.execute(
                    text("SELECT count(*) FROM resource_pool_members WHERE node_id = :n"),
                    {"n": lab["nodes"][0]},
                ).scalar_one()
    assert count == 1
