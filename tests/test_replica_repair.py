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
        c.execute(
            text(
                "INSERT INTO data_locations (location_id, tenant_id, contribution_id, uri, kind, "
                "relative_path, byte_size, checksum_sha256, verified_at, ready, catalogued_at, version) "
                "VALUES (:l, :t, :c, 'inv://datasets/corpus@1/data.bin', 'dataset', 'data.bin', "
                ":b, :s, now(), true, now(), 1)"
            ),
            {"l": ids["location_id"], "t": tenant_a, "c": ids["contribution_id"],
             "b": ids["bytes"], "s": SHA},
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
                    location_id=location["location_id"], desired=2,
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
                    location_id=location["location_id"], desired=2,
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
                    location_id=location["location_id"], desired=2,
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
                    location_id=location["location_id"], desired=2,
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
                    session, tenant_id=location["tenant_a"], desired=2,
                )
                assert [h.location_id for h in needing] == [location["location_id"]]
                # Raise the copies to the factor and it drops off the list.
                _add_replica(owner_engine, location, 1, "ready")
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, location["tenant_a"]):
                needing = replica_repair.locations_needing_repair(
                    session, tenant_id=location["tenant_a"], desired=2,
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
                    location_id=location["location_id"], desired=2,
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


def test_a_replica_factor_below_one_is_rejected(app_sessionmaker, location):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, location["tenant_a"]):
                with pytest.raises(InvError, match="at least 1"):
                    replica_repair.replica_health(
                        session, tenant_id=location["tenant_a"],
                        location_id=location["location_id"], desired=0,
                    )
