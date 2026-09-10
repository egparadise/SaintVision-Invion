"""The execution core's authorisation model, checked against the schema.

Until revision 0022 the entire ``inv`` grant policy lived in
``tests/integration/conftest.py``: a role created per test and given fifteen
scoped privileges. That is not a hardening detail left for later — the runtime
in ``inv.db.Database.transaction`` refuses to connect as a superuser, as a
BYPASSRLS role, or as the schema owner, so with no grant to anybody else the
execution core cannot open a connection at all.

These tests hold the policy now that it is in a migration:

* every ``inv`` table has a decision recorded about it, so a new one cannot
  arrive either unreachable or quietly writable;
* the three shapes that are easy to get subtly wrong — append-only, lockable
  but not writable, write-once — are what the schema actually grants;
* the role the application connects as is one the runtime will accept.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.postgres

APP_ROLE = "inv_app"

#: Mirrors migration 0022. Written out so a change to the migration has to be
#: made here too, deliberately, rather than the test following whatever the
#: schema happens to say.
INSERT_ONLY = {"evidence", "checkpoints"}
LOCK_SENTINEL_ONLY = {"project_grants", "project_nodes", "node_channels"}
APPEND_THEN_FROZEN = {
    "approval_votes",
    "approval_dispatches",
    "approval_audit",
    "tool_claims",
    "node_stop_receipts",
}
READ_ONLY = {"node_channel_audit"}


def _privileges(connection, table: str) -> set[str]:
    return set(
        connection.execute(
            text(
                "SELECT privilege_type FROM information_schema.role_table_grants "
                "WHERE table_schema = 'inv' AND table_name = :t AND grantee = :r"
            ),
            {"t": table, "r": APP_ROLE},
        ).scalars()
    )


def _column_privileges(connection, table: str) -> set[tuple[str, str]]:
    return {
        (row[0], row[1])
        for row in connection.execute(
            text(
                "SELECT column_name, privilege_type "
                "FROM information_schema.column_privileges "
                "WHERE table_schema = 'inv' AND table_name = :t AND grantee = :r"
            ),
            {"t": table, "r": APP_ROLE},
        ).all()
    }


def _inv_tables(connection) -> set[str]:
    return set(
        connection.execute(
            text(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'inv' "
                "ORDER BY tablename"
            )
        ).scalars()
    )


def test_the_application_role_can_reach_the_schema(owner_engine, migrated):
    """Without USAGE nothing inside the schema is addressable at all."""
    with owner_engine.connect() as connection:
        granted = connection.execute(
            text(
                "SELECT has_schema_privilege(:r, 'inv', 'USAGE') AS usable"
            ),
            {"r": APP_ROLE},
        ).scalar_one()
    assert granted, (
        "inv_app cannot use the inv schema. The runtime refuses to connect as "
        "the owner, so with no grant here the execution core cannot start."
    )


def test_the_runtime_would_accept_this_role(owner_engine, migrated):
    """The three conditions ``Database.transaction`` checks before every query."""
    with owner_engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT r.rolsuper, r.rolbypassrls, r.oid = n.nspowner AS owns_schema "
                "FROM pg_roles r JOIN pg_namespace n ON n.nspname = 'inv' "
                "WHERE r.rolname = :r"
            ),
            {"r": APP_ROLE},
        ).one()
    assert not any(row), (
        "the application role is a superuser, can bypass RLS, or owns the "
        "schema; the runtime rejects all three with AUTH-0020"
    )


def test_every_inv_table_has_a_recorded_decision(owner_engine, migrated):
    """A new table must not arrive unreachable, or writable by accident.

    ``GRANT ... ON ALL TABLES`` is a snapshot, not a rule: it covers what exists
    when it runs. ``ALTER DEFAULT PRIVILEGES`` would cover later tables
    automatically and would be wrong — it would hand DELETE to the next
    append-only ledger someone adds. So the grant is explicit, and this is what
    makes the next table a decision instead of an oversight.
    """
    with owner_engine.connect() as connection:
        tables = _inv_tables(connection)
        ungranted = {t for t in tables if not _privileges(connection, t)}
        # A table with no table-level grant is acceptable only when it has a
        # column-level one — that is the lockable-not-writable shape.
        ungranted = {
            t for t in ungranted if not _column_privileges(connection, t)
        }
    assert not ungranted, (
        f"inv tables the application cannot touch at all: {sorted(ungranted)}. "
        "Either grant them in a revision after 0022, or state that they are "
        "operator-only — but not by leaving the grant out."
    )


@pytest.mark.parametrize("table", sorted(INSERT_ONLY))
def test_an_append_only_ledger_grants_insert_and_nothing_else(
    owner_engine, migrated, table
):
    """The trigger refuses UPDATE and DELETE; the grant means it never gets there."""
    with owner_engine.connect() as connection:
        assert _privileges(connection, table) == {"SELECT", "INSERT"}, (
            f"inv.{table} is append-only. Holding UPDATE or DELETE on it means "
            "the trigger is the only thing standing between a bug and a "
            "rewritten record."
        )


@pytest.mark.parametrize("table", sorted(LOCK_SENTINEL_ONLY))
def test_a_lockable_table_is_not_a_writable_one(owner_engine, migrated, table):
    """UPDATE on one CHECK-pinned column: enough to lock, not enough to change.

    PostgreSQL requires an UPDATE privilege for ``SELECT ... FOR SHARE``. The
    application has to prove a project's membership did not change under it,
    which is a read that takes a lock — and it must not be able to change that
    membership. Naming the sentinel column is what separates the two.
    """
    with owner_engine.connect() as connection:
        table_level = _privileges(connection, table)
        columns = _column_privileges(connection, table)
    assert "INSERT" not in table_level and "DELETE" not in table_level
    assert ("lock_sentinel", "UPDATE") in columns
    updatable = {c for c, p in columns if p == "UPDATE"}
    assert updatable == {"lock_sentinel"}, (
        f"inv.{table} grants UPDATE on {sorted(updatable)}. Only the sentinel "
        "may be named, or the lock becomes an edit."
    )


@pytest.mark.parametrize("table", sorted(APPEND_THEN_FROZEN))
def test_a_write_once_record_cannot_be_revised(owner_engine, migrated, table):
    """Votes, dispatches and receipts are the evidence of a decision."""
    with owner_engine.connect() as connection:
        privileges = _privileges(connection, table)
    assert "UPDATE" not in privileges and "DELETE" not in privileges, (
        f"inv.{table} records what was decided or delivered. Being able to "
        "revise it afterwards makes it a note rather than evidence."
    )


def test_the_recovery_epoch_is_lockable_but_never_writable(owner_engine, migrated):
    """Every transaction takes FOR SHARE on it; none may move it."""
    with owner_engine.connect() as connection:
        columns = _column_privileges(connection, "control_epoch")
    updatable = {c for c, p in columns if p == "UPDATE"}
    assert updatable == {"singleton"}, (
        f"control_epoch grants UPDATE on {sorted(updatable)}. The epoch is what "
        "makes a stale reservation refuse to run; an application that can move "
        "it can make its own stale work look current."
    )
