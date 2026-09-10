"""Locality, transfer estimation and cache eviction.

The tests here mostly pin refusals. Every one of them is a place where an
optimistic default would produce a wrong schedule rather than a slow one: an
unmeasured link called instant, an empty dataset called fully local, an
unverified copy called usable, a pinned input evicted to make room.
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from saintvision.db.session import tenant_scope
from saintvision.errors import InvError
from saintvision.ids import new_id
from saintvision.services import locality as locality_service
from saintvision.services import pools as pool_service

pytestmark = pytest.mark.postgres

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 9, 10, 7, 0, 0, tzinfo=UTC)

GIB = 1024**3
GBPS = 1_000_000_000
ITEM_SHA = "a" * 64


@pytest.fixture
def store(owner_engine, two_tenants):
    """Two nodes, each with a contributed folder, and one catalogued 10 GiB item."""
    tenant_a, tenant_b = two_tenants
    ids = {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "user_id": new_id("user"),
        "project_id": new_id("project"),
        "nodes": [],
        "contributions": [],
        "location_id": new_id("data_location"),
        "item_bytes": 10 * GIB,
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
        c.execute(
            text(
                "INSERT INTO projects (project_id, tenant_id, code, display_name, status, "
                "created_at, version) VALUES (:p, :t, 'a', 'A', 'active', now(), 1)"
            ),
            {"p": ids["project_id"], "t": tenant_a},
        )
        for index in range(2):
            node_id = new_id("node")
            contribution_id = new_id("storage_contribution")
            ids["nodes"].append(node_id)
            ids["contributions"].append(contribution_id)
            c.execute(
                text(
                    "INSERT INTO nodes (node_id, tenant_id, hostname, os_type, os_version, "
                    "agent_version, status, enrolled_at, heartbeat_sequence, version) "
                    "VALUES (:n, :t, :h, 'linux', '22.04', '0.1', 'active', now(), 0, 1)"
                ),
                {"n": node_id, "t": tenant_a, "h": f"store-{index:02d}"},
            )
            c.execute(
                text(
                    "INSERT INTO storage_contributions (contribution_id, tenant_id, node_id, "
                    "declared_path, normalized_path, mode, status, capacity_bytes, "
                    "registered_by_user_id, registered_at, version) "
                    "VALUES (:c, :t, :n, :p, :p, 'read_write', 'active', :cap, :u, now(), 1)"
                ),
                {"c": contribution_id, "t": tenant_a, "n": node_id,
                 "p": f"/srv/inv/{index}", "cap": 100 * GIB, "u": ids["user_id"]},
            )
        # The item is catalogued on node 0's folder and verified.
        c.execute(
            text(
                "INSERT INTO data_locations (location_id, tenant_id, contribution_id, uri, kind, "
                "relative_path, byte_size, checksum_sha256, verified_at, ready, catalogued_at, version) "
                "VALUES (:l, :t, :c, 'inv://datasets/corpus@1/data.bin', 'dataset', "
                "'data.bin', :b, :s, now(), true, now(), 1)"
            ),
            {"l": ids["location_id"], "t": tenant_a, "c": ids["contributions"][0],
             "b": ids["item_bytes"], "s": ITEM_SHA},
        )
    return ids


def _ready_replica(session, store, node_index, *, now=NOW, bytes_=None):
    replica = locality_service.register_replica(
        session,
        tenant_id=store["tenant_a"],
        location_id=store["location_id"],
        node_id=store["nodes"][node_index],
        contribution_id=store["contributions"][node_index],
        now=now,
        local_bytes=store["item_bytes"] if bytes_ is None else bytes_,
    )
    return locality_service.mark_replica_ready(
        session, tenant_id=store["tenant_a"], replica_id=replica.replica_id,
        checksum_sha256=ITEM_SHA, now=now,
    )


# --------------------------------------------------------------------------
# A replica is not usable until it is verified
# --------------------------------------------------------------------------


def test_a_replica_starts_transferring_not_ready(app_sessionmaker, store):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, store["tenant_a"]):
                replica = locality_service.register_replica(
                    session, tenant_id=store["tenant_a"],
                    location_id=store["location_id"], node_id=store["nodes"][1],
                    contribution_id=store["contributions"][1], now=NOW,
                    local_bytes=store["item_bytes"],
                )
    assert replica.state == "transferring"


def test_a_wrong_checksum_marks_the_replica_corrupt(app_sessionmaker, store):
    """Not "retry later" — the bytes are not what the catalogue says they are."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, store["tenant_a"]):
                replica = locality_service.register_replica(
                    session, tenant_id=store["tenant_a"],
                    location_id=store["location_id"], node_id=store["nodes"][1],
                    contribution_id=store["contributions"][1], now=NOW,
                    local_bytes=store["item_bytes"],
                )
                with pytest.raises(InvError, match="corrupt"):
                    locality_service.mark_replica_ready(
                        session, tenant_id=store["tenant_a"],
                        replica_id=replica.replica_id,
                        checksum_sha256="b" * 64, now=NOW,
                    )
                state = session.execute(
                    text("SELECT state FROM data_replicas WHERE replica_id = :r"),
                    {"r": replica.replica_id},
                ).scalar_one()
    assert state == "corrupt"


def test_a_short_replica_is_not_ready(app_sessionmaker, store):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, store["tenant_a"]):
                replica = locality_service.register_replica(
                    session, tenant_id=store["tenant_a"],
                    location_id=store["location_id"], node_id=store["nodes"][1],
                    contribution_id=store["contributions"][1], now=NOW,
                    local_bytes=store["item_bytes"] // 2,
                )
                with pytest.raises(InvError, match="short of the catalogued size"):
                    locality_service.mark_replica_ready(
                        session, tenant_id=store["tenant_a"],
                        replica_id=replica.replica_id, checksum_sha256=ITEM_SHA, now=NOW,
                    )


def test_the_database_refuses_a_ready_replica_without_verification(
    app_sessionmaker, store
):
    with app_sessionmaker() as session:
        with pytest.raises((IntegrityError, DBAPIError)):
            with session.begin():
                with tenant_scope(session, store["tenant_a"]):
                    session.execute(
                        text(
                            "INSERT INTO data_replicas (replica_id, tenant_id, location_id, "
                            "node_id, contribution_id, state, local_bytes, last_used_at, created_at) "
                            "VALUES (:r, :t, :l, :n, :c, 'ready', 1, now(), now())"
                        ),
                        {"r": new_id("replica"), "t": store["tenant_a"],
                         "l": store["location_id"], "n": store["nodes"][1],
                         "c": store["contributions"][1]},
                    )


def test_one_replica_per_node_per_item(app_sessionmaker, store):
    """A second row would double-count the bytes everywhere."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, store["tenant_a"]):
                first = locality_service.register_replica(
                    session, tenant_id=store["tenant_a"],
                    location_id=store["location_id"], node_id=store["nodes"][1],
                    contribution_id=store["contributions"][1], now=NOW, local_bytes=1,
                )
                second = locality_service.register_replica(
                    session, tenant_id=store["tenant_a"],
                    location_id=store["location_id"], node_id=store["nodes"][1],
                    contribution_id=store["contributions"][1], now=NOW, local_bytes=2,
                )
    assert first.replica_id == second.replica_id
    assert second.local_bytes == 2


# --------------------------------------------------------------------------
# Locality
# --------------------------------------------------------------------------


def test_a_node_holding_the_item_is_fully_local(app_sessionmaker, store):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, store["tenant_a"]):
                _ready_replica(session, store, 0)
                value = locality_service.locality(
                    session, tenant_id=store["tenant_a"],
                    location_id=store["location_id"], node_id=store["nodes"][0],
                )
    assert value == 1.0


def test_a_node_without_the_item_has_locality_zero(app_sessionmaker, store):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, store["tenant_a"]):
                value = locality_service.locality(
                    session, tenant_id=store["tenant_a"],
                    location_id=store["location_id"], node_id=store["nodes"][1],
                )
    assert value == 0.0


def test_an_empty_item_has_locality_zero_not_one(owner_engine, app_sessionmaker, store):
    """ADR-011. Zero bytes present is nothing present, not everything present.

    Returning 1.0 would rank every node as perfectly local for an item nobody
    holds, which is exactly backwards.
    """
    empty_id = new_id("data_location")
    with owner_engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO data_locations (location_id, tenant_id, contribution_id, uri, kind, "
                "relative_path, byte_size, checksum_sha256, verified_at, ready, catalogued_at, version) "
                "VALUES (:l, :t, :c, 'inv://datasets/empty@1/x', 'dataset', 'x', 0, :s, now(), "
                "true, now(), 1)"
            ),
            {"l": empty_id, "t": store["tenant_a"], "c": store["contributions"][0], "s": "c" * 64},
        )
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, store["tenant_a"]):
                value = locality_service.locality(
                    session, tenant_id=store["tenant_a"],
                    location_id=empty_id, node_id=store["nodes"][0],
                )
    assert value == 0.0


def test_an_unverified_copy_does_not_count_as_local(app_sessionmaker, store):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, store["tenant_a"]):
                locality_service.register_replica(
                    session, tenant_id=store["tenant_a"],
                    location_id=store["location_id"], node_id=store["nodes"][1],
                    contribution_id=store["contributions"][1], now=NOW,
                    local_bytes=store["item_bytes"],
                )
                value = locality_service.locality(
                    session, tenant_id=store["tenant_a"],
                    location_id=store["location_id"], node_id=store["nodes"][1],
                )
    assert value == 0.0


# --------------------------------------------------------------------------
# Transfer estimation
# --------------------------------------------------------------------------


def test_an_unmeasured_link_yields_no_estimate_not_zero(app_sessionmaker, store):
    """The refusal ADR-011 asks for, and the one that matters most.

    Zero seconds would make the scheduler prefer dragging ten gigabytes across
    an untested segment over waiting for a busier machine that already has it.
    """
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, store["tenant_a"]):
                _ready_replica(session, store, 0)
                estimate = locality_service.estimate_transfer(
                    session, tenant_id=store["tenant_a"],
                    location_id=store["location_id"],
                    target_node_id=store["nodes"][1], now=NOW,
                )
    assert estimate.seconds is None
    assert estimate.measured is False
    assert estimate.bytes_missing == store["item_bytes"]
    assert "measured link" in estimate.reason


def test_no_source_copy_yields_no_estimate(app_sessionmaker, store):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, store["tenant_a"]):
                estimate = locality_service.estimate_transfer(
                    session, tenant_id=store["tenant_a"],
                    location_id=store["location_id"],
                    target_node_id=store["nodes"][1], now=NOW,
                )
    assert estimate.seconds is None
    assert "no node holds a ready copy" in estimate.reason


def test_a_measured_link_uses_the_adr_formula(app_sessionmaker, store):
    """bytes x 8 / bits-per-second, and nothing else."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, store["tenant_a"]):
                _ready_replica(session, store, 0)
                locality_service.record_link(
                    session, tenant_id=store["tenant_a"],
                    from_node_id=store["nodes"][0], to_node_id=store["nodes"][1],
                    bits_per_second=GBPS, now=NOW,
                )
                estimate = locality_service.estimate_transfer(
                    session, tenant_id=store["tenant_a"],
                    location_id=store["location_id"],
                    target_node_id=store["nodes"][1], now=NOW,
                )
    assert estimate.measured is True
    assert estimate.seconds == pytest.approx((10 * GIB * 8) / GBPS)
    # 10 GiB over a gigabit link is about a minute and a half, not instant.
    assert estimate.seconds > 80


def test_a_stale_measurement_is_not_used(app_sessionmaker, store):
    """A number from months ago is a guess wearing a decimal point."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, store["tenant_a"]):
                _ready_replica(session, store, 0)
                locality_service.record_link(
                    session, tenant_id=store["tenant_a"],
                    from_node_id=store["nodes"][0], to_node_id=store["nodes"][1],
                    bits_per_second=GBPS, now=NOW - dt.timedelta(days=120),
                )
                estimate = locality_service.estimate_transfer(
                    session, tenant_id=store["tenant_a"],
                    location_id=store["location_id"],
                    target_node_id=store["nodes"][1], now=NOW,
                )
    assert estimate.seconds is None


def test_a_node_that_already_holds_it_transfers_nothing(app_sessionmaker, store):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, store["tenant_a"]):
                _ready_replica(session, store, 0)
                estimate = locality_service.estimate_transfer(
                    session, tenant_id=store["tenant_a"],
                    location_id=store["location_id"],
                    target_node_id=store["nodes"][0], now=NOW,
                )
    assert estimate.seconds == 0.0
    assert estimate.bytes_missing == 0


def test_a_link_must_join_two_different_nodes(app_sessionmaker, store):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, store["tenant_a"]):
                with pytest.raises(InvError):
                    locality_service.record_link(
                        session, tenant_id=store["tenant_a"],
                        from_node_id=store["nodes"][0], to_node_id=store["nodes"][0],
                        bits_per_second=GBPS, now=NOW,
                    )


# --------------------------------------------------------------------------
# Locality-aware ranking
# --------------------------------------------------------------------------


def _candidates(store):
    return [
        {"nodeId": store["nodes"][1], "hostname": "store-01", "headroom": 10.0},
        {"nodeId": store["nodes"][0], "hostname": "store-00", "headroom": 2.0},
    ]


def test_the_node_holding_the_data_outranks_the_idler_one(app_sessionmaker, store):
    """Sending work to the bytes beats sending the bytes to the work."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, store["tenant_a"]):
                _ready_replica(session, store, 0)
                locality_service.record_link(
                    session, tenant_id=store["tenant_a"],
                    from_node_id=store["nodes"][0], to_node_id=store["nodes"][1],
                    bits_per_second=GBPS, now=NOW,
                )
                ranked = locality_service.rank_by_locality(
                    session, tenant_id=store["tenant_a"],
                    candidates=_candidates(store),
                    location_ids=[store["location_id"]], now=NOW,
                )
    # Node 0 has the data (0 seconds) though node 1 is five times idler.
    assert ranked[0]["nodeId"] == store["nodes"][0]
    assert ranked[0]["transferSeconds"] == 0.0
    assert ranked[1]["transferSeconds"] > 0


def test_an_unknown_cost_sorts_last_not_first(app_sessionmaker, store):
    """The whole point of returning None instead of zero."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, store["tenant_a"]):
                _ready_replica(session, store, 0)
                # No link recorded, so node 1's cost is unknown.
                ranked = locality_service.rank_by_locality(
                    session, tenant_id=store["tenant_a"],
                    candidates=_candidates(store),
                    location_ids=[store["location_id"]], now=NOW,
                )
    assert ranked[0]["nodeId"] == store["nodes"][0]
    assert ranked[-1]["transferSeconds"] is None
    assert ranked[-1]["unknownTransfers"] == 1


def test_ranking_without_inputs_is_left_alone(app_sessionmaker, store):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, store["tenant_a"]):
                candidates = _candidates(store)
                ranked = locality_service.rank_by_locality(
                    session, tenant_id=store["tenant_a"], candidates=candidates,
                    location_ids=[], now=NOW,
                )
    assert ranked == candidates


# --------------------------------------------------------------------------
# Cache accounting and eviction
# --------------------------------------------------------------------------


def test_the_cache_may_fill_sixty_percent_of_a_contributed_folder(
    app_sessionmaker, store
):
    """The rest is the owner's headroom. The machine is theirs."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, store["tenant_a"]):
                _ready_replica(session, store, 0)
                usage = locality_service.cache_usage(
                    session, tenant_id=store["tenant_a"],
                    contribution_id=store["contributions"][0],
                )
    assert usage["capacityBytes"] == 100 * GIB
    assert usage["cacheLimitBytes"] == int(100 * GIB * 0.60)
    assert usage["cacheUsedBytes"] == 10 * GIB
    assert usage["overLimit"] is False


def test_nothing_is_evicted_while_under_the_limit(app_sessionmaker, store):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, store["tenant_a"]):
                _ready_replica(session, store, 0)
                candidates = locality_service.eviction_candidates(
                    session, tenant_id=store["tenant_a"],
                    contribution_id=store["contributions"][0], now=NOW,
                )
    assert candidates == []


def test_eviction_takes_the_least_recently_used_first(
    owner_engine, app_sessionmaker, store
):
    older, newer = new_id("data_location"), new_id("data_location")
    with owner_engine.begin() as c:
        for location_id, name in ((older, "old.bin"), (newer, "new.bin")):
            c.execute(
                text(
                    "INSERT INTO data_locations (location_id, tenant_id, contribution_id, uri, "
                    "kind, relative_path, byte_size, checksum_sha256, verified_at, ready, "
                    "catalogued_at, version) VALUES (:l, :t, :c, :u, 'dataset', :r, :b, :s, "
                    "now(), true, now(), 1)"
                ),
                {"l": location_id, "t": store["tenant_a"], "c": store["contributions"][0],
                 "u": f"inv://datasets/x@1/{name}", "r": name, "b": 40 * GIB,
                 "s": ITEM_SHA},
            )
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, store["tenant_a"]):
                for location_id, used_at in (
                    (older, NOW - dt.timedelta(days=7)),
                    (newer, NOW),
                ):
                    replica = locality_service.register_replica(
                        session, tenant_id=store["tenant_a"], location_id=location_id,
                        node_id=store["nodes"][0],
                        contribution_id=store["contributions"][0],
                        now=used_at, local_bytes=40 * GIB,
                    )
                    locality_service.mark_replica_ready(
                        session, tenant_id=store["tenant_a"],
                        replica_id=replica.replica_id, checksum_sha256=ITEM_SHA,
                        now=used_at,
                    )
                # 80 GiB held against a 60 GiB limit.
                candidates = locality_service.eviction_candidates(
                    session, tenant_id=store["tenant_a"],
                    contribution_id=store["contributions"][0], now=NOW,
                )
    assert [c["locationId"] for c in candidates] == [older]


def test_a_pinned_replica_is_never_evicted(owner_engine, app_sessionmaker, store):
    """An active lease pinned its inputs. Evicting them would fail a running job
    to make room for a queued one."""
    other = new_id("data_location")
    with owner_engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO data_locations (location_id, tenant_id, contribution_id, uri, kind, "
                "relative_path, byte_size, checksum_sha256, verified_at, ready, catalogued_at, version) "
                "VALUES (:l, :t, :c, 'inv://datasets/x@1/other.bin', 'dataset', 'other.bin', :b, "
                ":s, now(), true, now(), 1)"
            ),
            {"l": other, "t": store["tenant_a"], "c": store["contributions"][0],
             "b": 70 * GIB, "s": ITEM_SHA},
        )
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, store["tenant_a"]):
                pinned = locality_service.register_replica(
                    session, tenant_id=store["tenant_a"], location_id=other,
                    node_id=store["nodes"][0], contribution_id=store["contributions"][0],
                    now=NOW - dt.timedelta(days=30), local_bytes=70 * GIB,
                )
                locality_service.mark_replica_ready(
                    session, tenant_id=store["tenant_a"], replica_id=pinned.replica_id,
                    checksum_sha256=ITEM_SHA, now=NOW - dt.timedelta(days=30),
                )
                session.execute(
                    text("UPDATE data_replicas SET pinned_until = :p WHERE replica_id = :r"),
                    {"p": NOW + dt.timedelta(hours=1), "r": pinned.replica_id},
                )
                candidates = locality_service.eviction_candidates(
                    session, tenant_id=store["tenant_a"],
                    contribution_id=store["contributions"][0], now=NOW,
                )
    # It is the oldest and the largest, and it is over the limit — and it stays.
    assert candidates == []


def test_the_database_refuses_a_pin_on_an_unready_replica(app_sessionmaker, store):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, store["tenant_a"]):
                replica = locality_service.register_replica(
                    session, tenant_id=store["tenant_a"],
                    location_id=store["location_id"], node_id=store["nodes"][1],
                    contribution_id=store["contributions"][1], now=NOW, local_bytes=1,
                )
                replica_id = replica.replica_id
        with pytest.raises((IntegrityError, DBAPIError)):
            with session.begin():
                with tenant_scope(session, store["tenant_a"]):
                    session.execute(
                        text("UPDATE data_replicas SET pinned_until = :p WHERE replica_id = :r"),
                        {"p": NOW + dt.timedelta(hours=1), "r": replica_id},
                    )


def test_a_node_runs_at_most_two_transfers(app_sessionmaker, store):
    """More would saturate the owner's link and make their machine unpleasant."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, store["tenant_a"]):
                assert locality_service.may_start_transfer(
                    session, tenant_id=store["tenant_a"], node_id=store["nodes"][0]
                )
                for index in range(2):
                    location_id = new_id("data_location")
                    session.execute(
                        text(
                            "INSERT INTO data_locations (location_id, tenant_id, contribution_id, "
                            "uri, kind, relative_path, byte_size, catalogued_at, version) "
                            "VALUES (:l, :t, :c, :u, 'dataset', :r, 1, now(), 1)"
                        ),
                        {"l": location_id, "t": store["tenant_a"],
                         "c": store["contributions"][0],
                         "u": f"inv://datasets/t@1/f{index}", "r": f"f{index}"},
                    )
                    locality_service.register_replica(
                        session, tenant_id=store["tenant_a"], location_id=location_id,
                        node_id=store["nodes"][0],
                        contribution_id=store["contributions"][0], now=NOW, local_bytes=0,
                    )
                assert locality_service.active_transfers(
                    session, tenant_id=store["tenant_a"], node_id=store["nodes"][0]
                ) == 2
                assert not locality_service.may_start_transfer(
                    session, tenant_id=store["tenant_a"], node_id=store["nodes"][0]
                )


def test_replicas_are_tenant_isolated(app_sessionmaker, store):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, store["tenant_a"]):
                _ready_replica(session, store, 0)
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, store["tenant_b"]):
                for table in ("data_replicas", "node_links"):
                    assert (
                        session.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() == 0
                    ), table
