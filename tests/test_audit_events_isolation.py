"""audit_events tenant isolation (F-S02-01, migration 0047).

The baseline granted ``inv_app`` SELECT and INSERT on ``audit_events`` and left
the table outside the RLS loop, so the application role could read every
tenant's authorisation decisions. The model docstring claimed the opposite --
that NULL-tenant rows are read through a *separate* audit role -- and that role
did not exist. These tests hold the shape that closes the gap:

* the application role has no read path at all, and the policy still closes if
  someone re-grants SELECT (fail-closed twice over);
* an authentication denial with no resolvable tenant is still recorded, through
  one narrow SECURITY DEFINER primitive that can write nothing else (AC-02);
* the application role cannot forge a NULL-tenant row or another tenant's row;
* append-only holds for every role that can reach the table;
* the migration itself refuses to run when the audit read role already has
  members, directly or through a bridge role — checked by running the upgrade
  against a seeded cluster, not by reading a clean database's end state.

Read probes are compared against the owner's ground truth in the same test, so
"0 rows" is never accepted as a pass on its own -- there are rows to miss.
"""

from __future__ import annotations

import datetime as dt
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, ProgrammingError

from saintvision.db.session import TENANT_GUC, tenant_scope
from saintvision.ids import new_id

pytestmark = pytest.mark.postgres

ROOT = Path(__file__).resolve().parents[1]
UTC = dt.timezone.utc
PREVIOUS_REVISION = "0046_model_manifest_readiness"
TARGET_REVISION = "0047_audit_events_isolation"

APP_ROLE = "inv_app"
WRITER_ROLE = "inv_audit_writer"
READER_ROLE = "inv_audit_reader"

PRIMITIVE = (
    "SELECT public.record_auth_denial("
    "p_event_id => :event_id, p_actor_type => :actor_type, p_action => :action, "
    "p_reason_code => :reason_code, p_actor_id => :actor_id, p_trace_id => :trace_id, "
    "p_target_type => :target_type, p_target_id => :target_id, "
    "p_detail => CAST(:detail AS jsonb), p_source_ip => :source_ip, "
    "p_user_agent => :user_agent)"
)

INSERT_AUDIT = (
    "INSERT INTO audit_events (event_id, occurred_at, tenant_id, actor_type, "
    "action, outcome, reason_code, detail) "
    "VALUES (:i, :o, :t, :actor, :action, :outcome, :reason, '{}')"
)


def _primitive_args(**overrides) -> dict:
    args = {
        "event_id": new_id("audit_event"),
        "actor_type": "anonymous",
        "action": "GET /v1/nodes",
        "reason_code": "AUTH-MISSING-CREDENTIAL",
        "actor_id": None,
        "trace_id": None,
        "target_type": None,
        "target_id": None,
        "detail": "{}",
        "source_ip": "203.0.113.9",
        "user_agent": "pytest",
    }
    args.update(overrides)
    return args


def _seed(owner_engine, tenant_a, tenant_b) -> dict[str, str]:
    """Three rows the app role must not be able to read: A, B and NULL-tenant."""
    now = dt.datetime.now(UTC)
    ids = {
        "a": new_id("audit_event"),
        "b": new_id("audit_event"),
        "null": new_id("audit_event"),
    }
    with owner_engine.begin() as connection:
        for key, tenant, outcome, reason in (
            ("a", tenant_a, "allow", None),
            ("b", tenant_b, "allow", None),
            ("null", None, "deny", "AUTH-INVALID-CREDENTIAL"),
        ):
            connection.execute(
                text(INSERT_AUDIT),
                {
                    "i": ids[key],
                    "o": now,
                    "t": tenant,
                    "actor": "system",
                    "action": "seed",
                    "outcome": outcome,
                    "reason": reason,
                },
            )
    return ids


@pytest.fixture
def seeded_audit(owner_engine, two_tenants):
    tenant_a, tenant_b = two_tenants
    return tenant_a, tenant_b, _seed(owner_engine, tenant_a, tenant_b)


# --------------------------------------------------------------------------
# The table itself
# --------------------------------------------------------------------------


def test_audit_events_rls_is_enabled_forced_and_policed(app_engine, migrated):
    """FORCE is the half that is easy to omit and impossible to notice."""
    with app_engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT c.relrowsecurity AS enabled, c.relforcerowsecurity AS forced "
                "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'public' AND c.relname = 'audit_events'"
            )
        ).mappings().one()
        policies = connection.execute(
            text(
                "SELECT policyname, cmd, roles::text AS roles FROM pg_policies "
                "WHERE schemaname = 'public' AND tablename = 'audit_events' "
                "ORDER BY policyname"
            )
        ).mappings().all()
    assert row["enabled"] and row["forced"]
    assert [(p["policyname"], p["cmd"]) for p in policies] == [
        ("audit_events_audit_read", "SELECT"),
        ("audit_events_denial_append", "INSERT"),
        ("audit_events_tenant_isolation", "ALL"),
    ]
    by_name = {p["policyname"]: p["roles"] for p in policies}
    assert READER_ROLE in by_name["audit_events_audit_read"]
    assert WRITER_ROLE in by_name["audit_events_denial_append"]
    assert APP_ROLE in by_name["audit_events_tenant_isolation"]
    # A policy for PUBLIC would apply to every role, including the two new ones.
    assert not any("public" in p["roles"].lower().strip("{}").split(",") for p in policies)


def test_the_application_role_has_no_read_privilege_and_keeps_insert(app_engine, migrated):
    with app_engine.connect() as connection:
        privileges = connection.execute(
            text(
                "SELECT has_table_privilege(:r, 'public.audit_events', 'SELECT') AS sel, "
                "has_any_column_privilege(:r, 'public.audit_events', 'SELECT') AS col_sel, "
                "has_table_privilege(:r, 'public.audit_events', 'INSERT') AS ins, "
                "has_table_privilege(:r, 'public.audit_events', 'UPDATE') AS upd, "
                "has_table_privilege(:r, 'public.audit_events', 'DELETE') AS del"
            ),
            {"r": APP_ROLE},
        ).mappings().one()
    assert privileges["ins"] is True
    assert privileges["sel"] is False and privileges["col_sel"] is False
    assert privileges["upd"] is False and privileges["del"] is False


# --------------------------------------------------------------------------
# Reads: 0 for the application role, and 0 for the right reason
# --------------------------------------------------------------------------


def test_the_application_role_cannot_read_audit_events_at_all(
    app_sessionmaker, owner_engine, seeded_audit
):
    tenant_a, _, _ = seeded_audit
    with owner_engine.connect() as connection:
        total = connection.execute(text("SELECT count(*) FROM audit_events")).scalar_one()
    assert total == 3, "the owner must see rows, or a 0 below would mean nothing"

    for guc in (None, str(tenant_a), "not-a-uuid"):
        with app_sessionmaker() as session:
            with pytest.raises((ProgrammingError, DBAPIError)), session.begin():
                if guc is not None:
                    session.execute(text(f"SET LOCAL {TENANT_GUC} = '{guc}'"))
                session.execute(text("SELECT count(*) FROM audit_events"))


def test_the_policy_still_closes_when_select_is_re_granted(
    app_sessionmaker, owner_engine, seeded_audit
):
    """Defence in depth: the missing GRANT is not the only thing holding the line.

    If an operator re-grants SELECT -- the exact mistake the baseline made -- the
    policy must still show the role nothing outside its own tenant, and nothing
    at all with the scope unset or unparseable.
    """
    tenant_a, tenant_b, ids = seeded_audit
    with owner_engine.begin() as connection:
        connection.execute(text(f"GRANT SELECT ON audit_events TO {APP_ROLE}"))
    try:
        with app_sessionmaker() as session:
            with session.begin():
                assert session.execute(
                    text("SELECT count(*) FROM audit_events")
                ).scalar_one() == 0
        with app_sessionmaker() as session:
            with session.begin():
                with tenant_scope(session, tenant_a):
                    rows = session.execute(
                        text("SELECT event_id, tenant_id FROM audit_events")
                    ).mappings().all()
        assert [r["event_id"].strip() for r in rows] == [ids["a"]]
        assert {str(r["tenant_id"]) for r in rows} == {str(tenant_a)}
        with app_sessionmaker() as session:
            with session.begin():
                with tenant_scope(session, tenant_b):
                    foreign = session.execute(
                        text("SELECT count(*) FROM audit_events WHERE tenant_id <> :t"),
                        {"t": tenant_b},
                    ).scalar_one()
        assert foreign == 0
        # NULL-tenant rows are outside every tenant scope, by construction.
        with app_sessionmaker() as session:
            with session.begin():
                with tenant_scope(session, tenant_a):
                    assert session.execute(
                        text("SELECT count(*) FROM audit_events WHERE tenant_id IS NULL")
                    ).scalar_one() == 0
        # An unparseable scope fails closed with an error, never with every row.
        with app_sessionmaker() as session:
            with pytest.raises((ProgrammingError, DBAPIError)), session.begin():
                session.execute(text(f"SET LOCAL {TENANT_GUC} = 'not-a-uuid'"))
                session.execute(text("SELECT count(*) FROM audit_events"))
    finally:
        with owner_engine.begin() as connection:
            connection.execute(text(f"REVOKE SELECT ON audit_events FROM {APP_ROLE}"))


def test_only_the_audit_reader_role_sees_null_tenant_and_cross_tenant_rows(
    owner_engine, seeded_audit
):
    _, _, ids = seeded_audit
    with owner_engine.connect() as connection:
        with connection.begin():
            connection.execute(text(f"SET LOCAL ROLE {READER_ROLE}"))
            rows = connection.execute(
                text("SELECT event_id FROM audit_events ORDER BY event_id")
            ).scalars().all()
        assert sorted(r.strip() for r in rows) == sorted(ids.values())
    # The reader reads; it never writes.
    with owner_engine.connect() as connection:
        with pytest.raises((ProgrammingError, DBAPIError)), connection.begin():
            connection.execute(text(f"SET LOCAL ROLE {READER_ROLE}"))
            connection.execute(
                text(INSERT_AUDIT),
                {
                    "i": new_id("audit_event"),
                    "o": dt.datetime.now(UTC),
                    "t": None,
                    "actor": "system",
                    "action": "reader-should-not-write",
                    "outcome": "deny",
                    "reason": "X",
                },
            )


def test_neither_new_role_is_reachable_from_the_runtime_roles(app_engine, migrated):
    with app_engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT r.rolname AS runtime, g.rolname AS granted, "
                "pg_has_role(r.oid, g.oid, 'MEMBER') AS member, "
                "g.rolcanlogin AS login, g.rolsuper AS super, g.rolbypassrls AS bypass "
                "FROM pg_roles r CROSS JOIN pg_roles g "
                "WHERE r.rolname IN ('inv_app', 'inv_kernel') "
                "AND g.rolname IN (:w, :r2)"
            ),
            {"w": WRITER_ROLE, "r2": READER_ROLE},
        ).mappings().all()
    assert rows, "the audit roles must exist"
    for row in rows:
        assert row["member"] is False, f"{row['runtime']} can assume {row['granted']}"
        assert not row["login"] and not row["super"] and not row["bypass"]


# --------------------------------------------------------------------------
# AC-02: the denial with no tenant is still recorded
# --------------------------------------------------------------------------


def test_a_null_tenant_denial_is_recorded_through_the_primitive(
    app_sessionmaker, owner_engine, two_tenants
):
    args = _primitive_args()
    before = dt.datetime.now(UTC)
    with app_sessionmaker() as session:
        with session.begin():
            session.execute(text(PRIMITIVE), args)
    with owner_engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT tenant_id, outcome, reason_code, actor_type, action, "
                "source_ip, occurred_at FROM audit_events WHERE event_id = :i"
            ),
            {"i": args["event_id"]},
        ).mappings().one()
    assert row["tenant_id"] is None
    assert row["outcome"] == "deny"
    assert row["reason_code"] == "AUTH-MISSING-CREDENTIAL"
    assert row["actor_type"] == "anonymous"
    assert row["source_ip"] == "203.0.113.9"
    # Written by the server clock, not by the caller.
    assert row["occurred_at"] >= before - dt.timedelta(seconds=5)


def test_the_primitive_refuses_a_denial_that_says_nothing(app_sessionmaker, two_tenants):
    """A denial with no reason code is not an audit record.

    The sqlstate is asserted, not just "it raised": a missing function raises too
    (42883), and that would make this test pass while proving nothing.
    """
    for field in ("reason_code", "action", "actor_type", "event_id"):
        with app_sessionmaker() as session:
            with pytest.raises(DBAPIError) as caught, session.begin():
                session.execute(text(PRIMITIVE), _primitive_args(**{field: None}))
        assert caught.value.orig.sqlstate == "22023", field


def test_the_primitive_is_owned_by_the_writer_and_executable_only_by_the_app(
    app_engine, migrated
):
    with app_engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT pg_get_userbyid(p.proowner) AS owner, p.prosecdef, "
                "p.proconfig::text AS config, "
                "(SELECT coalesce(array_agg(CASE WHEN a.grantee = 0 THEN 'PUBLIC' "
                "  ELSE pg_get_userbyid(a.grantee) END ORDER BY a.grantee), '{}') "
                " FROM aclexplode(coalesce(p.proacl, acldefault('f', p.proowner))) a "
                " WHERE a.privilege_type = 'EXECUTE' AND a.grantee <> p.proowner) AS grants "
                "FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
                "WHERE n.nspname = 'public' AND p.proname = 'record_auth_denial'"
            )
        ).mappings().one()
    assert row["owner"] == WRITER_ROLE
    assert row["prosecdef"] is True
    assert "search_path=pg_catalog" in row["config"]
    assert list(row["grants"]) == [APP_ROLE]


# --------------------------------------------------------------------------
# What the application role must not be able to write
# --------------------------------------------------------------------------


def test_the_application_role_can_still_write_its_own_tenants_row(
    app_sessionmaker, owner_engine, two_tenants
):
    """Positive control: record_event's path must keep working."""
    tenant_a, _ = two_tenants
    event_id = new_id("audit_event")
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, tenant_a):
                session.execute(
                    text(INSERT_AUDIT),
                    {
                        "i": event_id,
                        "o": dt.datetime.now(UTC),
                        "t": tenant_a,
                        "actor": "user",
                        "action": "node.enroll",
                        "outcome": "allow",
                        "reason": None,
                    },
                )
    with owner_engine.connect() as connection:
        assert connection.execute(
            text("SELECT count(*) FROM audit_events WHERE event_id = :i"), {"i": event_id}
        ).scalar_one() == 1


@pytest.mark.parametrize("scope", ["unset", "tenant_a"])
def test_the_application_role_cannot_forge_a_null_tenant_row(
    app_sessionmaker, two_tenants, scope
):
    tenant_a, _ = two_tenants
    with app_sessionmaker() as session:
        with pytest.raises((ProgrammingError, DBAPIError)), session.begin():
            if scope == "tenant_a":
                session.execute(text(f"SET LOCAL {TENANT_GUC} = '{tenant_a}'"))
            session.execute(
                text(INSERT_AUDIT),
                {
                    "i": new_id("audit_event"),
                    "o": dt.datetime.now(UTC),
                    "t": None,
                    "actor": "anonymous",
                    "action": "forged",
                    "outcome": "deny",
                    "reason": "AUTH-MISSING-CREDENTIAL",
                },
            )


def test_the_application_role_cannot_write_another_tenants_row(app_sessionmaker, two_tenants):
    tenant_a, tenant_b = two_tenants
    with app_sessionmaker() as session:
        with pytest.raises((ProgrammingError, DBAPIError)), session.begin():
            with tenant_scope(session, tenant_a):
                session.execute(
                    text(INSERT_AUDIT),
                    {
                        "i": new_id("audit_event"),
                        "o": dt.datetime.now(UTC),
                        "t": tenant_b,
                        "actor": "user",
                        "action": "cross-tenant",
                        "outcome": "allow",
                        "reason": None,
                    },
                )


# --------------------------------------------------------------------------
# Append-only, for every role that can reach the table
# --------------------------------------------------------------------------


def test_append_only_holds_for_the_application_role(app_sessionmaker, owner_engine, seeded_audit):
    tenant_a, _, ids = seeded_audit
    for statement in (
        "UPDATE audit_events SET action = 'rewritten' WHERE event_id = :i",
        "DELETE FROM audit_events WHERE event_id = :i",
    ):
        with app_sessionmaker() as session:
            with pytest.raises((ProgrammingError, DBAPIError)), session.begin():
                with tenant_scope(session, tenant_a):
                    session.execute(text(statement), {"i": ids["a"]})
    with owner_engine.connect() as connection:
        assert connection.execute(
            text("SELECT action FROM audit_events WHERE event_id = :i"), {"i": ids["a"]}
        ).scalar_one() == "seed"


def test_the_writer_role_can_append_only_null_tenant_denials(owner_engine, seeded_audit):
    """The policy, not just the function body, is what bounds the writer."""
    tenant_a, _, ids = seeded_audit
    now = dt.datetime.now(UTC)
    allowed = new_id("audit_event")
    with owner_engine.begin() as connection:
        connection.execute(text(f"SET LOCAL ROLE {WRITER_ROLE}"))
        connection.execute(
            text(INSERT_AUDIT),
            {
                "i": allowed,
                "o": now,
                "t": None,
                "actor": "anonymous",
                "action": "direct-writer-denial",
                "outcome": "deny",
                "reason": "AUTH-INVALID-CREDENTIAL",
            },
        )
    for label, params in (
        ("tenant row", {"t": tenant_a, "outcome": "deny", "reason": "AUTH-TENANT-SCOPE"}),
        ("allow outcome", {"t": None, "outcome": "allow", "reason": None}),
    ):
        with owner_engine.connect() as connection:
            with pytest.raises((ProgrammingError, DBAPIError)), connection.begin():
                connection.execute(text(f"SET LOCAL ROLE {WRITER_ROLE}"))
                connection.execute(
                    text(INSERT_AUDIT),
                    {
                        "i": new_id("audit_event"),
                        "o": now,
                        "actor": "anonymous",
                        "action": f"writer-{label}",
                        **params,
                    },
                )
    for statement in (
        "UPDATE audit_events SET action = 'rewritten' WHERE event_id = :i",
        "DELETE FROM audit_events WHERE event_id = :i",
    ):
        with owner_engine.connect() as connection:
            with pytest.raises((ProgrammingError, DBAPIError)), connection.begin():
                connection.execute(text(f"SET LOCAL ROLE {WRITER_ROLE}"))
                connection.execute(text(statement), {"i": allowed})
    with owner_engine.connect() as connection:
        assert connection.execute(
            text("SELECT count(*) FROM audit_events")
        ).scalar_one() == len(ids) + 1


# --------------------------------------------------------------------------
# The membership guard, exercised by running the migration
# --------------------------------------------------------------------------


def _alembic(url: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=ROOT,
        env={**os.environ, "INV_MIGRATION_DSN": url, "INV_DATABASE_URL": url, "PYTHONUTF8": "1"},
        capture_output=True,
        text=True,
        timeout=300,
    )


#: What the isolation looks like in the catalogue, in one row. Read as the owner.
ISOLATION_STATE = """
SELECT
  (SELECT c.relrowsecurity FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relname = 'audit_events') AS rls_enabled,
  (SELECT c.relforcerowsecurity FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relname = 'audit_events') AS rls_forced,
  (SELECT count(*) FROM pg_policies
    WHERE schemaname = 'public' AND tablename = 'audit_events') AS policies,
  (SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'public' AND p.proname = 'record_auth_denial') AS primitive,
  has_table_privilege('inv_app', 'public.audit_events', 'SELECT') AS app_select,
  has_table_privilege('inv_app', 'public.audit_events', 'INSERT') AS app_insert,
  (SELECT version_num FROM public.alembic_version) AS head
"""


def _isolation_state(url: str) -> dict:
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(url.replace("postgresql+psycopg", "postgresql"), row_factory=dict_row) as conn:
        return conn.execute(ISOLATION_STATE).fetchone()


@pytest.fixture
def disposable_migration_database(test_admin_dsn, migrated):
    """An empty throwaway database this test may migrate on its own.

    ``migrated`` is requested so the cluster already holds ``inv_audit_reader``
    and ``inv_audit_writer``: roles are cluster-wide, and the membership guard is
    about membership that *pre-dates* the migration, which can only happen when
    the role arrived from another database in the cluster.
    """
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import conninfo_to_dict
    from sqlalchemy.engine import URL

    name = "inv_audit_guard_" + uuid.uuid4().hex
    with psycopg.connect(test_admin_dsn, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    info = conninfo_to_dict(test_admin_dsn)
    url = URL.create(
        "postgresql+psycopg",
        username=info.get("user"),
        password=info.get("password"),
        host=info.get("host"),
        port=int(info.get("port", 5432)),
        database=name,
    ).render_as_string(hide_password=False)
    try:
        yield url
    finally:
        with psycopg.connect(test_admin_dsn, autocommit=True) as conn:
            assert name.startswith("inv_audit_guard_")
            conn.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


@pytest.fixture
def guard_database(disposable_migration_database):
    """The same database, stopped one revision below 0047."""
    result = _alembic(disposable_migration_database, "upgrade", PREVIOUS_REVISION)
    assert result.returncode == 0, result.stderr[-2000:]
    return disposable_migration_database


@pytest.mark.parametrize("shape", ["direct", "chain"])
def test_the_upgrade_stops_when_the_audit_reader_already_has_members(
    guard_database, test_admin_dsn, shape
):
    """Pre-existing membership must fail the migration closed, chains included.

    ``GRANT inv_audit_reader TO bridge; GRANT bridge TO leaf`` gives ``leaf`` the
    reader through ``pg_has_role`` while no runtime role is a direct member, which
    is why the guard refuses *any* member rather than naming inv_app and
    inv_kernel. A clean database's final ``pg_has_role = false`` cannot show this;
    only running the upgrade against a seeded cluster can.

    The leaf is a throwaway role, not ``inv_app``: roles are cluster-wide, and
    granting the real application role a transitive path to every tenant's audit
    rows is the hole itself, not a way to test for it. The guard's property does
    not depend on who the leaf is — it is "any member at all" — and the test
    asserts the seeded chain really does confer the reader on the leaf, so the
    shape being refused is the bypass and not a no-op.

    Cluster-wide side effect, deliberately short-lived: the memberships below
    exist for the seconds this test runs and are revoked in ``finally``. While
    they exist, any *other* session running this upgrade would also (correctly)
    abort.
    """
    import psycopg
    from psycopg import sql

    suffix = uuid.uuid4().hex[:12]
    leaf = f"inv_audit_leaf_{suffix}"
    bridge = f"inv_audit_bridge_{suffix}" if shape == "chain" else None
    created = [r for r in (leaf, bridge) if r]

    with psycopg.connect(test_admin_dsn, autocommit=True) as conn:
        for role in created:
            conn.execute(
                sql.SQL("CREATE ROLE {} NOLOGIN NOSUPERUSER NOBYPASSRLS").format(
                    sql.Identifier(role)
                )
            )
        if bridge:
            conn.execute(sql.SQL("GRANT inv_audit_reader TO {}").format(sql.Identifier(bridge)))
            conn.execute(
                sql.SQL("GRANT {} TO {}").format(sql.Identifier(bridge), sql.Identifier(leaf))
            )
        else:
            conn.execute(sql.SQL("GRANT inv_audit_reader TO {}").format(sql.Identifier(leaf)))
        # The seed is the real bypass shape: the leaf holds the reader either way.
        assert conn.execute(
            "SELECT pg_has_role(%s, 'inv_audit_reader', 'MEMBER')", (leaf,)
        ).fetchone()[0] is True
    try:
        result = _alembic(guard_database, "upgrade", "head")
        assert result.returncode != 0, "the upgrade must refuse, not proceed"
        output = result.stdout + result.stderr
        assert "inv_audit_reader already has members" in output, output[-2000:]
        # Aborted, not half-applied.
        state = _isolation_state(guard_database)
        assert state["head"] == PREVIOUS_REVISION
        assert state["rls_enabled"] is False and state["policies"] == 0
        assert state["primitive"] == 0
    finally:
        with psycopg.connect(test_admin_dsn, autocommit=True) as conn:
            if bridge:
                conn.execute(
                    sql.SQL("REVOKE {} FROM {}").format(
                        sql.Identifier(bridge), sql.Identifier(leaf)
                    )
                )
            conn.execute(
                sql.SQL("REVOKE inv_audit_reader FROM {}").format(
                    sql.Identifier(bridge or leaf)
                )
            )
            for role in created:
                conn.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))


def test_the_downgrade_removes_the_machinery_without_restoring_the_read(
    disposable_migration_database,
):
    """The reversible tail reverses, and rolling back does not reopen the hole.

    Revision 0047 is the reversible audit-isolation change. Exercise it
    directly so a later irreversible migration is not crossed by this focused
    regression. The property that matters is not just "both commands succeed": a
    downgrade that restored ``GRANT SELECT ON audit_events TO inv_app`` would make
    a rollback a way to reintroduce the exposure 0047 fixes. So the app role's
    SELECT is asserted to stay revoked at 0046.
    """
    url = disposable_migration_database
    assert _alembic(url, "upgrade", TARGET_REVISION).returncode == 0
    at_head = _isolation_state(url)
    assert _alembic(url, "downgrade", PREVIOUS_REVISION).returncode == 0
    at_previous = _isolation_state(url)
    assert _alembic(url, "upgrade", TARGET_REVISION).returncode == 0
    back_at_head = _isolation_state(url)

    assert at_head == {
        "rls_enabled": True, "rls_forced": True, "policies": 3, "primitive": 1,
        "app_select": False, "app_insert": True, "head": "0047_audit_events_isolation",
    }
    assert at_previous == {
        "rls_enabled": False, "rls_forced": False, "policies": 0, "primitive": 0,
        # The machinery is gone; the revoked read is NOT given back.
        "app_select": False, "app_insert": True, "head": PREVIOUS_REVISION,
    }
    assert back_at_head == at_head
