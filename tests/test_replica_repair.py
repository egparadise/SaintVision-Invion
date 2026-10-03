"""Replica health and repair planning (VF-CL-04, contract-independent part).

Every assertion is a place where miscounting would either hide a real loss or
invent a false one:

* only ``ready`` copies satisfy the replica factor -- a ``transferring`` or
  ``corrupt`` copy present must not make a location look safe;
* a location with copies that are all unusable is *at_risk*, distinct from one
  with no copies at all (*unreplicated*) and from a healthy one;
* a departed node's copies become ``stale`` while the location and its manifest
  survive -- node loss touches copies, not the catalogue.
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import text

from saintvision.db.session import tenant_scope
from saintvision.errors import InvError
from saintvision.ids import new_id
from saintvision.services import replica_repair
from saintvision.services import nodes as node_service

pytestmark = pytest.mark.postgres

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 9, 15, 7, 0, 0, tzinfo=UTC)
SHA = "d" * 64


@pytest.fixture
def location(owner_engine, two_tenants):
    """A verified dataset location under tenant A, plus three nodes to place on."""
    tenant_a, tenant_b = two_tenants
    ids = {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "user_id": new_id("user"),
        "nodes": [new_id("node") for _ in range(3)],
        "contribution_id": new_id("storage_contribution"),
        "location_id": new_id("data_location"),
        # Card 266: the scope the three functions now take as authority, plus the
        # two rows that must stay out of this project's answer.
        "project_id": new_id("project"),
        "other_project_id": new_id("project"),
        "other_project_location_id": new_id("data_location"),
        "legacy_location_id": new_id("data_location"),
        "bytes": 4096,
    }
    with owner_engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO users (user_id, tenant_id, external_subject, display_name, "
                "status, created_at, updated_at, version) "
                "VALUES (:u, :t, 'sub', 'U', 'active', now(), now(), 1)"
            ),
            {"u": ids["user_id"], "t": tenant_a},
        )
        for index, node_id in enumerate(ids["nodes"]):
            c.execute(
                text(
                    "INSERT INTO nodes (node_id, tenant_id, hostname, os_type, os_version, "
                    "agent_version, status, enrolled_at, heartbeat_sequence, version) "
                    "VALUES (:n, :t, :h, 'linux', '22.04', '0.1', 'active', now(), 0, 1)"
                ),
                {"n": node_id, "t": tenant_a, "h": f"rep-{index:02d}"},
            )
        c.execute(
            text(
                "INSERT INTO storage_contributions (contribution_id, tenant_id, node_id, "
                "declared_path, normalized_path, mode, status, registered_by_user_id, "
                "registered_at, version) VALUES (:c, :t, :n, '/srv/inv/0', '/srv/inv/0', "
                "'read_write', 'active', :u, now(), 1)"
            ),
            {"c": ids["contribution_id"], "t": tenant_a, "n": ids["nodes"][0], "u": ids["user_id"]},
        )
        for key, code in (("project_id", "rep-a"), ("other_project_id", "rep-b")):
            c.execute(
                text(
                    "INSERT INTO projects (project_id, tenant_id, code, display_name, status, "
                    "created_at, version) VALUES (:p, :t, :c, :c, 'active', now(), 1)"
                ),
                {"p": ids[key], "t": tenant_a, "c": code},
            )
        # Three locations in one contribution: this project's, another project's,
        # and one with a NULL project_id -- the shape every row had before 0062.
        for key, project in (
            ("location_id", ids["project_id"]),
            ("other_project_location_id", ids["other_project_id"]),
            ("legacy_location_id", None),
        ):
            c.execute(
                text(
                    "INSERT INTO data_locations (location_id, tenant_id, project_id, "
                    "contribution_id, uri, kind, relative_path, byte_size, checksum_sha256, "
                    "verified_at, ready, catalogued_at, version) "
                    "VALUES (:l, :t, :p, :c, :uri, 'dataset', :rel, :b, :s, now(), true, now(), 1)"
                ),
                {
                    "l": ids[key], "t": tenant_a, "p": project, "c": ids["contribution_id"],
                    # The first location keeps the URI this fixture has always used:
                    # other suites import it and assert on that exact address, so the
                    # two rows card 266 added take names of their own instead.
                    "uri": (
                        "inv://datasets/corpus@1/data.bin" if key == "location_id"
                        else f"inv://datasets/corpus@1/{key}.bin"
                    ),
                    "rel": "data.bin" if key == "location_id" else f"{key}.bin",
                    "b": ids["bytes"], "s": SHA,
                },
            )
    return ids


def _add_replica(owner_engine, location, node_index, state):
    """Insert a replica in an explicit state, as the owner (outside RLS)."""
    ready_cols = ""
    ready_vals = ""
    params = {
        "r": new_id("replica"),
        "t": location["tenant_a"],
        "l": location["location_id"],
        "n": location["nodes"][node_index],
        "c": location["contribution_id"],
        "st": state,
        "b": location["bytes"] if state == "ready" else location["bytes"] // 2,
    }
    if state == "ready":
        # The check constraint requires a verified checksum for ready.
        ready_cols = ", checksum_sha256, verified_at"
        ready_vals = ", :s, now()"
        params["s"] = SHA
    with owner_engine.begin() as c:
        c.execute(
            text(
                f"INSERT INTO data_replicas (replica_id, tenant_id, location_id, node_id, "
                f"contribution_id, state, local_bytes, last_used_at, created_at{ready_cols}) "
                f"VALUES (:r, :t, :l, :n, :c, :st, :b, now(), now(){ready_vals})"
            ),
            params,
        )


def test_two_ready_replicas_meets_a_factor_of_two(owner_engine, app_sessionmaker, location):
    _add_replica(owner_engine, location, 0, "ready")
    _add_replica(owner_engine, location, 1, "ready")
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, location["tenant_a"]):
                health = replica_repair.replica_health(
                    session, tenant_id=location["tenant_a"],
                    location_id=location["location_id"],
                    project_id=location["project_id"], desired=2,
                )
                assert health.classification == "healthy"
                assert health.ready == 2
                assert health.needs_repair is False
                assert health.deficit == 0


def test_one_ready_replica_is_under_replicated_with_a_source(owner_engine, app_sessionmaker, location):
    _add_replica(owner_engine, location, 0, "ready")
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, location["tenant_a"]):
                health = replica_repair.replica_health(
                    session, tenant_id=location["tenant_a"],
                    location_id=location["location_id"],
                    project_id=location["project_id"], desired=2,
                )
                assert health.classification == "under_replicated"
                assert health.deficit == 1
                assert health.source_nodes == [location["nodes"][0]]


def test_only_unusable_copies_is_at_risk_not_healthy(owner_engine, app_sessionmaker, location):
    """A corrupt copy present must not make the location look safe."""
    _add_replica(owner_engine, location, 0, "corrupt")
    _add_replica(owner_engine, location, 1, "transferring")
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, location["tenant_a"]):
                health = replica_repair.replica_health(
                    session, tenant_id=location["tenant_a"],
                    location_id=location["location_id"],
                    project_id=location["project_id"], desired=2,
                )
                assert health.classification == "at_risk"
                assert health.ready == 0
                assert health.unusable == {"transferring": 1, "corrupt": 1}
                assert health.source_nodes == []


def test_no_replica_at_all_is_unreplicated(app_sessionmaker, location):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, location["tenant_a"]):
                health = replica_repair.replica_health(
                    session, tenant_id=location["tenant_a"],
                    location_id=location["location_id"],
                    project_id=location["project_id"], desired=2,
                )
                assert health.classification == "unreplicated"
                assert health.ready == 0
                assert health.needs_repair is True


def test_locations_needing_repair_excludes_healthy_ones(owner_engine, app_sessionmaker, location):
    _add_replica(owner_engine, location, 0, "ready")  # only one -> under-replicated
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, location["tenant_a"]):
                needing = replica_repair.locations_needing_repair(
                    session, tenant_id=location["tenant_a"],
                    project_id=location["project_id"], desired=2,
                )
                assert [h.location_id for h in needing] == [location["location_id"]]
                # Raise the copies to the factor and it drops off the list.
                _add_replica(owner_engine, location, 1, "ready")
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, location["tenant_a"]):
                needing = replica_repair.locations_needing_repair(
                    session, tenant_id=location["tenant_a"],
                    project_id=location["project_id"], desired=2,
                )
                assert needing == []


def test_a_departed_node_marks_its_copies_stale_and_keeps_the_location(
    owner_engine, app_sessionmaker, location
):
    _add_replica(owner_engine, location, 0, "ready")
    _add_replica(owner_engine, location, 1, "ready")
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, location["tenant_a"]):
                marked = replica_repair.mark_node_replicas_unavailable(
                    session, tenant_id=location["tenant_a"],
                    node_id=location["nodes"][0], now=NOW,
                )
                assert marked == 1
                # The location survives; only node 0's copy is gone.
                health = replica_repair.replica_health(
                    session, tenant_id=location["tenant_a"],
                    location_id=location["location_id"],
                    project_id=location["project_id"], desired=2,
                )
                assert health.ready == 1
                assert health.unusable.get("stale") == 1
                assert health.source_nodes == [location["nodes"][1]]
                # The catalogue row is untouched.
                still = session.execute(
                    text("SELECT count(*) FROM data_locations WHERE location_id = :l"),
                    {"l": location["location_id"]},
                ).scalar_one()
                assert still == 1


def test_liveness_sweep_marks_departed_node_replicas_stale(
    owner_engine, app_sessionmaker, location
):
    """The product loss path must invoke replica repair, not only the helper."""
    _add_replica(owner_engine, location, 0, "ready")
    with owner_engine.begin() as c:
        c.execute(
            text(
                "UPDATE nodes SET enrolled_at=:old, last_heartbeat_at=:old "
                "WHERE node_id=:n"
            ),
            {
                "old": NOW - dt.timedelta(minutes=2),
                "n": location["nodes"][0],
            },
        )

    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, location["tenant_a"]):
                assert node_service.mark_lost_nodes(
                    session,
                    tenant_id=location["tenant_a"],
                    now=NOW,
                    timeout_seconds=60,
                ) == 1

    with owner_engine.connect() as c:
        row = c.execute(
            text(
                "SELECT n.status, r.state "
                "FROM nodes n JOIN data_replicas r ON r.node_id=n.node_id "
                "WHERE n.node_id=:n AND r.replica_id IN "
                "(SELECT replica_id FROM data_replicas WHERE node_id=:n)"
            ),
            {"n": location["nodes"][0]},
        ).one()
    assert row[0] == "lost"
    assert row[1] == "stale"


def test_liveness_sweep_rolls_back_node_and_replica_on_repair_failure(
    owner_engine, app_sessionmaker, location, monkeypatch
):
    """A failed replica transition cannot leave the Node lost by itself."""
    _add_replica(owner_engine, location, 0, "ready")
    with owner_engine.begin() as c:
        c.execute(
            text(
                "UPDATE nodes SET enrolled_at=:old, last_heartbeat_at=:old "
                "WHERE node_id=:n"
            ),
            {
                "old": NOW - dt.timedelta(minutes=2),
                "n": location["nodes"][0],
            },
        )

    def fail_repair(*_args, **_kwargs):
        raise RuntimeError("synthetic replica repair failure")

    monkeypatch.setattr(replica_repair, "mark_node_replicas_unavailable", fail_repair)
    with pytest.raises(RuntimeError, match="synthetic replica repair failure"):
        with app_sessionmaker() as session:
            with session.begin():
                with tenant_scope(session, location["tenant_a"]):
                    node_service.mark_lost_nodes(
                        session,
                        tenant_id=location["tenant_a"],
                        now=NOW,
                        timeout_seconds=60,
                    )

    with owner_engine.connect() as c:
        row = c.execute(
            text(
                "SELECT n.status, r.state "
                "FROM nodes n JOIN data_replicas r ON r.node_id=n.node_id "
                "WHERE n.node_id=:n"
            ),
            {"n": location["nodes"][0]},
        ).one()
    assert row[0] == "active"
    assert row[1] == "ready"


def test_node_loss_on_a_pinned_replica_keeps_the_pin(owner_engine, app_sessionmaker, location):
    """Node loss invalidates availability, not retention (migration 0043).

    A ready replica held by an active lease (pinned) must survive node loss as a
    stale-but-pinned row -- otherwise recovery could discard something Evidence
    depends on. This is the case the original replica_repair missed: marking a
    pinned ready replica stale used to violate only_ready_replicas_pin; the
    retained_replicas_pin constraint admits a pinned stale row, so the pin is
    preserved through the transition.
    """
    pinned_until = dt.datetime(2027, 6, 1, tzinfo=UTC)
    replica_id = new_id("replica")
    with owner_engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO data_replicas (replica_id, tenant_id, location_id, node_id, "
                "contribution_id, state, local_bytes, checksum_sha256, verified_at, "
                "pinned_until, last_used_at, created_at) "
                "VALUES (:r, :t, :l, :n, :c, 'ready', :b, :s, now(), :p, now(), now())"
            ),
            {"r": replica_id, "t": location["tenant_a"], "l": location["location_id"],
             "n": location["nodes"][0], "c": location["contribution_id"],
             "b": location["bytes"], "s": SHA, "p": pinned_until},
        )
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, location["tenant_a"]):
                marked = replica_repair.mark_node_replicas_unavailable(
                    session, tenant_id=location["tenant_a"],
                    node_id=location["nodes"][0], now=NOW,
                )
                assert marked == 1
    with owner_engine.connect() as c:
        row = c.execute(
            text("SELECT state, pinned_until FROM data_replicas WHERE replica_id = :r"),
            {"r": replica_id},
        ).one()
    assert row[0] == "stale"
    assert row[1] is not None


def test_fleet_summary_aggregates_classification_across_the_catalogue(
    owner_engine, app_sessionmaker, location
):
    # With no replica, the one catalogued location is unreplicated.
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, location["tenant_a"]):
                summary = replica_repair.fleet_replica_summary(
                    session, tenant_id=location["tenant_a"],
                    project_id=location["project_id"], desired=2,
                )
                assert summary.to_dict() == {
                    "locations": 1, "healthy": 0, "underReplicated": 0,
                    "atRisk": 0, "unreplicated": 1, "needingRepair": 1,
                }
    # Bring it to the factor and it moves to healthy.
    _add_replica(owner_engine, location, 0, "ready")
    _add_replica(owner_engine, location, 1, "ready")
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, location["tenant_a"]):
                summary = replica_repair.fleet_replica_summary(
                    session, tenant_id=location["tenant_a"],
                    project_id=location["project_id"], desired=2,
                )
                assert summary.healthy == 1
                assert summary.needing_repair == 0


def test_a_replica_factor_below_one_is_rejected(app_sessionmaker, location):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, location["tenant_a"]):
                with pytest.raises(InvError, match="at least 1"):
                    replica_repair.replica_health(
                        session, tenant_id=location["tenant_a"],
                        location_id=location["location_id"],
                        project_id=location["project_id"], desired=0,
                    )


# ===========================================================================
# Card 266: project is an authority input, not a convenience filter.
#
# Before this card the three functions narrowed by tenant alone, so a
# project-scoped reader would have been handed the whole tenant's catalogue.
# Each test below dies if one scope condition is removed.
# ===========================================================================


def test_another_projects_location_is_the_same_answer_as_absence(app_sessionmaker, location):
    """Not "forbidden" and not an empty result -- the same refusal as a row that
    is not there, because telling them apart names somebody else's location."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, location["tenant_a"]):
                with pytest.raises(InvError, match="data location not found"):
                    replica_repair.replica_health(
                        session,
                        tenant_id=location["tenant_a"],
                        location_id=location["other_project_location_id"],
                        project_id=location["project_id"],
                        desired=2,
                    )


def test_a_legacy_null_project_location_is_in_no_projects_answer(app_sessionmaker, location):
    """0062 added project_id as nullable, so rows catalogued before it are NULL.
    NULL is not "every project": it is no project."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, location["tenant_a"]):
                with pytest.raises(InvError, match="data location not found"):
                    replica_repair.replica_health(
                        session,
                        tenant_id=location["tenant_a"],
                        location_id=location["legacy_location_id"],
                        project_id=location["project_id"],
                        desired=2,
                    )


def test_the_repair_plan_lists_only_this_projects_locations(app_sessionmaker, location):
    """Three unreplicated locations exist in the tenant; one belongs to this
    project. A tenant-only query would return all three."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, location["tenant_a"]):
                needing = replica_repair.locations_needing_repair(
                    session,
                    tenant_id=location["tenant_a"],
                    project_id=location["project_id"], desired=2,
                )
                assert [health.location_id for health in needing] == [location["location_id"]]
                # And the other project sees exactly its own one.
                other = replica_repair.locations_needing_repair(
                    session,
                    tenant_id=location["tenant_a"],
                    project_id=location["other_project_id"], desired=2,
                )
                assert [health.location_id for health in other] == [
                    location["other_project_location_id"]
                ]


def test_the_fleet_summary_counts_only_this_projects_locations(app_sessionmaker, location):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, location["tenant_a"]):
                summary = replica_repair.fleet_replica_summary(
                    session,
                    tenant_id=location["tenant_a"],
                    project_id=location["project_id"], desired=2,
                )
                # One location, not the tenant's three.
                assert summary.locations == 1
                assert summary.unreplicated == 1


def test_a_project_with_no_locations_and_an_unknown_project_answer_alike(
    app_sessionmaker, location
):
    """No existence oracle for projects either: an id that names nothing and a
    project that holds nothing give the same empty answer."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, location["tenant_a"]):
                for project_id in (new_id("project"), location["other_project_id"]):
                    summary = replica_repair.fleet_replica_summary(
                        session,
                        tenant_id=location["tenant_a"],
                        project_id=project_id, desired=2,
                    )
                    if project_id == location["other_project_id"]:
                        assert summary.locations == 1
                    else:
                        assert summary.locations == 0
                        assert summary.needing_repair == 0
