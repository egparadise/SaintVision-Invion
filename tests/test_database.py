"""Schema behaviour that only PostgreSQL can demonstrate.

Covers the three DB properties this sprint claims and that no unit test can
stand in for: RLS tenant isolation under a non-owner role (CR-12), NULLS NOT
DISTINCT uniqueness, and partition routing with no DEFAULT partition (CR-06).

Every test runs as ``inv_app`` — a non-owner, NOBYPASSRLS role. Running as the
migration owner would pass even with the policies removed.
"""

from __future__ import annotations

import datetime as dt
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError, ProgrammingError

from saintvision.db.partitions import (
    PartitionExhausted,
    assert_partitions_available,
    ensure_partitions,
    partition_status,
)
from saintvision.db.rls import rls_report
from saintvision.db.session import TENANT_GUC, tenant_scope
from saintvision.ids import new_id

pytestmark = pytest.mark.postgres

UTC = dt.timezone.utc


def _insert_node(session, tenant_id, hostname="host-a"):
    node_id = new_id("node")
    session.execute(
        text(
            "INSERT INTO nodes (node_id, tenant_id, hostname, os_type, os_version, "
            "agent_version, status, enrolled_at, heartbeat_sequence, version) "
            "VALUES (:i, :t, :h, 'linux', '1', '1', 'active', now(), 0, 1)"
        ),
        {"i": node_id, "t": tenant_id, "h": hostname},
    )
    return node_id


# --------------------------------------------------------------------------
# RLS
# --------------------------------------------------------------------------


def test_every_tenant_table_has_rls_enabled_and_forced(app_engine, migrated):
    from saintvision.db.models import TENANT_SCOPED_TABLES

    with app_engine.connect() as connection:
        report = {row["table_name"]: row for row in rls_report(connection)}
    for table in TENANT_SCOPED_TABLES:
        assert report[table]["enabled"], f"{table}: RLS not enabled"
        # FORCE is the half that is easy to omit and impossible to notice.
        assert report[table]["forced"], f"{table}: RLS not forced"
        assert report[table]["policies"] >= 1, f"{table}: no policy"


def test_rows_are_invisible_without_a_tenant_scope(app_sessionmaker, two_tenants, owner_engine):
    tenant_a, _ = two_tenants
    with owner_engine.begin() as connection:
        _insert_node(connection, tenant_a)

    with app_sessionmaker() as session:
        with session.begin():
            # No SET LOCAL: current_setting is NULL, the policy matches nothing.
            count = session.execute(text("SELECT count(*) FROM nodes")).scalar_one()
    assert count == 0


def test_scope_selects_only_the_matching_tenant(app_sessionmaker, two_tenants, owner_engine):
    tenant_a, tenant_b = two_tenants
    with owner_engine.begin() as connection:
        _insert_node(connection, tenant_a, "a-host")
        _insert_node(connection, tenant_b, "b-host")

    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, tenant_a):
                hosts = session.execute(text("SELECT hostname FROM nodes")).scalars().all()
    assert hosts == ["a-host"]


def test_scope_does_not_survive_the_transaction(app_sessionmaker, two_tenants, owner_engine):
    """CR-12's central claim.

    SET LOCAL dies with the transaction, so a pooler handing this backend to
    another tenant's request cannot inherit the scope. If this ever fails, the
    isolation story is broken regardless of what the policies say.
    """
    tenant_a, _ = two_tenants
    with owner_engine.begin() as connection:
        _insert_node(connection, tenant_a)

    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, tenant_a):
                assert session.execute(text("SELECT count(*) FROM nodes")).scalar_one() == 1

        # Next transaction on the same session and connection.
        with session.begin():
            leaked = session.execute(
                text(f"SELECT current_setting('{TENANT_GUC}', true)")
            ).scalar_one_or_none()
            assert leaked in (None, "")
            assert session.execute(text("SELECT count(*) FROM nodes")).scalar_one() == 0


def test_write_into_another_tenant_is_refused_by_with_check(
    app_sessionmaker, two_tenants
):
    tenant_a, tenant_b = two_tenants
    with app_sessionmaker() as session:
        with pytest.raises((ProgrammingError, DBAPIError, IntegrityError)):
            with session.begin():
                with tenant_scope(session, tenant_a):
                    # tenant_id says B while the scope says A: WITH CHECK rejects.
                    _insert_node(session, tenant_b, "smuggled")


def test_update_cannot_move_a_row_to_another_tenant(
    app_sessionmaker, two_tenants, owner_engine
):
    tenant_a, tenant_b = two_tenants
    with owner_engine.begin() as connection:
        node_id = _insert_node(connection, tenant_a)

    with app_sessionmaker() as session:
        with pytest.raises((ProgrammingError, DBAPIError, IntegrityError)):
            with session.begin():
                with tenant_scope(session, tenant_a):
                    session.execute(
                        text("UPDATE nodes SET tenant_id = :b WHERE node_id = :i"),
                        {"b": tenant_b, "i": node_id},
                    )


def test_empty_tenant_setting_is_treated_as_unset(app_sessionmaker, two_tenants, owner_engine):
    """A pooler or driver writing '' must not become "tenant zero"."""
    tenant_a, _ = two_tenants
    with owner_engine.begin() as connection:
        _insert_node(connection, tenant_a)

    with app_sessionmaker() as session:
        with session.begin():
            session.execute(text(f"SET LOCAL {TENANT_GUC} = ''"))
            assert session.execute(text("SELECT count(*) FROM nodes")).scalar_one() == 0


def test_tenant_scope_rejects_a_non_uuid_value(app_sessionmaker, two_tenants):
    with app_sessionmaker() as session:
        with session.begin():
            with pytest.raises(ValueError):
                with tenant_scope(session, "'; DROP TABLE nodes; --"):
                    pass


def test_app_role_cannot_delete_audit_events(app_sessionmaker, two_tenants):
    """Append-only for the application role (PLAN-DB-001).

    Not a WORM claim: the owner and any superuser can still delete.
    """
    tenant_a, _ = two_tenants
    with app_sessionmaker() as session:
        with session.begin():
            session.execute(
                text(
                    "INSERT INTO audit_events (event_id, occurred_at, tenant_id, actor_type, "
                    "action, outcome, detail) VALUES (:i, now(), :t, 'system', 'x', 'allow', '{}')"
                ),
                {"i": new_id("audit_event"), "t": tenant_a},
            )
    with app_sessionmaker() as session:
        with pytest.raises((ProgrammingError, DBAPIError)):
            with session.begin():
                session.execute(text("DELETE FROM audit_events"))


# --------------------------------------------------------------------------
# Constraints
# --------------------------------------------------------------------------


def test_two_unenrolled_nodes_cannot_both_hold_a_null_fingerprint(
    app_sessionmaker, two_tenants
):
    """NULLS NOT DISTINCT on the node's authenticated identity.

    A plain UNIQUE permits unlimited NULLs, which is exactly the unenrolled
    state; the constraint is what stops that becoming a shared identity.
    """
    tenant_a, _ = two_tenants
    with app_sessionmaker() as session:
        with pytest.raises(IntegrityError):
            with session.begin():
                with tenant_scope(session, tenant_a):
                    _insert_node(session, tenant_a, "h1")
                    _insert_node(session, tenant_a, "h2")


def test_whole_host_capability_cannot_be_registered_twice(app_sessionmaker, two_tenants):
    """device_index is NULL for RAM; NULLS NOT DISTINCT makes the second insert fail."""
    tenant_a, _ = two_tenants
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, tenant_a):
                node_id = _insert_node(session, tenant_a, "cap-host")
                session.execute(
                    text("UPDATE nodes SET certificate_fingerprint = :f WHERE node_id = :i"),
                    {"f": "a" * 64, "i": node_id},
                )
                for _ in range(1):
                    session.execute(
                        text(
                            "INSERT INTO node_capabilities (capability_id, tenant_id, node_id, "
                            "kind, device_index, total_quantity, unit, divisible, detected_at, version) "
                            "VALUES (:c, :t, :n, 'ram', NULL, 64, 'GiB', true, now(), 1)"
                        ),
                        {"c": new_id("capability"), "t": tenant_a, "n": node_id},
                    )
        with pytest.raises(IntegrityError):
            with session.begin():
                with tenant_scope(session, tenant_a):
                    session.execute(
                        text(
                            "INSERT INTO node_capabilities (capability_id, tenant_id, node_id, "
                            "kind, device_index, total_quantity, unit, divisible, detected_at, version) "
                            "VALUES (:c, :t, :n, 'ram', NULL, 64, 'GiB', true, now(), 1)"
                        ),
                        {"c": new_id("capability"), "t": tenant_a, "n": node_id},
                    )


def test_a_location_cannot_be_ready_without_a_checksum(app_sessionmaker, two_tenants):
    """ADR-011 expressed as a constraint, so no service path can shortcut it."""
    tenant_a, _ = two_tenants
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, tenant_a):
                node_id = _insert_node(session, tenant_a, "loc-host")
                contribution_id = new_id("storage_contribution")
                session.execute(
                    text(
                        "INSERT INTO storage_contributions (contribution_id, tenant_id, node_id, "
                        "declared_path, normalized_path, mode, status, registered_by_user_id, "
                        "registered_at, version) VALUES (:c, :t, :n, '/srv/x', '/srv/x', "
                        "'read_only', 'active', :u, now(), 1)"
                    ),
                    {"c": contribution_id, "t": tenant_a, "n": node_id, "u": new_id("user")},
                )
        with pytest.raises(IntegrityError):
            with session.begin():
                with tenant_scope(session, tenant_a):
                    session.execute(
                        text(
                            "INSERT INTO data_locations (location_id, tenant_id, contribution_id, "
                            "uri, kind, relative_path, byte_size, ready, catalogued_at, version) "
                            "VALUES (:l, :t, :c, 'inv://datasets/a@1/x', 'dataset', 'x', 1, true, now(), 1)"
                        ),
                        {"l": new_id("data_location"), "t": tenant_a, "c": contribution_id},
                    )


def test_gpu_requires_a_device_index_and_others_forbid_it(app_sessionmaker, two_tenants):
    tenant_a, _ = two_tenants
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, tenant_a):
                node_id = _insert_node(session, tenant_a, "gpu-host")
        with pytest.raises(IntegrityError):
            with session.begin():
                with tenant_scope(session, tenant_a):
                    session.execute(
                        text(
                            "INSERT INTO node_capabilities (capability_id, tenant_id, node_id, "
                            "kind, device_index, total_quantity, unit, divisible, detected_at, version) "
                            "VALUES (:c, :t, :n, 'gpu', NULL, 1, 'device', false, now(), 1)"
                        ),
                        {"c": new_id("capability"), "t": tenant_a, "n": node_id},
                    )


# --------------------------------------------------------------------------
# Partitions
# --------------------------------------------------------------------------


def test_migration_created_a_three_month_lead(app_engine, migrated):
    with app_engine.connect() as connection:
        statuses = {
            s.table: s.months_ahead
            for s in partition_status(connection, now=dt.datetime.now(UTC))
        }
    assert statuses["resource_snapshots"] >= 4
    assert statuses["audit_events"] >= 4


def test_there_is_no_default_partition(app_engine, migrated):
    """CR-06: a DEFAULT partition would absorb stray rows and then block
    attaching the real partition for that range."""
    with app_engine.connect() as connection:
        defaults = connection.execute(
            text(
                "SELECT c.relname FROM pg_class c "
                "JOIN pg_inherits i ON i.inhrelid = c.oid "
                "JOIN pg_class p ON p.oid = i.inhparent "
                "WHERE p.relname IN ('resource_snapshots','audit_events') "
                "AND pg_get_expr(c.relpartbound, c.oid) = 'DEFAULT'"
            )
        ).scalars().all()
    assert defaults == []


def test_insert_outside_every_partition_fails_loudly(app_sessionmaker, two_tenants):
    """The behaviour CR-06 chose over silent absorption."""
    tenant_a, _ = two_tenants
    far_future = dt.datetime.now(UTC) + dt.timedelta(days=365 * 5)
    with app_sessionmaker() as session:
        with pytest.raises((ProgrammingError, DBAPIError, IntegrityError)):
            with session.begin():
                with tenant_scope(session, tenant_a):
                    session.execute(
                        text(
                            "INSERT INTO audit_events (event_id, occurred_at, tenant_id, "
                            "actor_type, action, outcome, detail) "
                            "VALUES (:i, :o, :t, 'system', 'x', 'allow', '{}')"
                        ),
                        {"i": new_id("audit_event"), "o": far_future, "t": tenant_a},
                    )


def test_ensure_partitions_is_idempotent(owner_engine, migrated):
    with owner_engine.begin() as connection:
        again = ensure_partitions(connection, now=dt.datetime.now(UTC), lead_months=3)
    assert again == []


def test_startup_gate_raises_when_the_lead_is_short(app_engine, migrated):
    """The startup check refuses rather than waiting for the first failed insert."""
    with app_engine.connect() as connection:
        # Five years out, nothing is covered.
        with pytest.raises(PartitionExhausted):
            assert_partitions_available(
                connection,
                now=dt.datetime.now(UTC) + dt.timedelta(days=365 * 5),
                minimum_months=1,
            )
        # Today, the migration's lead satisfies it.
        assert assert_partitions_available(
            connection, now=dt.datetime.now(UTC), minimum_months=1
        )
