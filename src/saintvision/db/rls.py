"""Row level security DDL.

ADR-008 and PLAN-DB-001: every tenant table gets ENABLE + FORCE RLS, a policy
with both USING and WITH CHECK, and is reached only by a non-owner application
role.

FORCE matters. Without it the table owner — which is the role migrations run
as — bypasses the policy, and every test written as the owner would pass while
production leaked. The application role is separate and owns nothing.

The policy reads ``current_setting('inv.tenant_id', true)``. When it is unset
the setting is NULL, the comparison is NULL, and no rows match: unset scope
fails closed rather than returning everything.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

from .models import APPEND_ONLY_TABLES, TENANT_SCOPED_TABLES
from .session import TENANT_GUC

APP_ROLE = "inv_app"

#: NULLIF is what makes an empty string behave like an unset setting; a pooler
#: or a driver that writes '' must not become "tenant zero".
_TENANT_EXPR = f"NULLIF(current_setting('{TENANT_GUC}', true), '')::uuid"


def policy_name(table: str) -> str:
    return f"{table}_tenant_isolation"


#: What the application group role is designed to be, per property. One place,
#: because two callers need the same answer: the migration that creates the
#: role, and the operational report that checks a live deployment against it.
DESIGNED_ROLE_SHAPE: dict[str, bool] = {
    "rolcanlogin": False,
    "rolbypassrls": False,
    "rolsuper": False,
    "rolcreatedb": False,
    "rolcreaterole": False,
}

#: How each deviation reads to a person, and why it matters here.
_SHAPE_MEANING: dict[str, str] = {
    "rolcanlogin": (
        "has LOGIN, but it is designed as a NOLOGIN group role — connections "
        "come from per-deployment login roles that inherit it, so a password "
        "on this role is a credential that should not exist"
    ),
    "rolbypassrls": "has BYPASSRLS, which makes every tenant policy decorative",
    "rolsuper": "is SUPERUSER, which bypasses every permission this schema sets",
    "rolcreatedb": "may CREATE DATABASE, which the application never needs",
    "rolcreaterole": "may CREATE ROLE, which turns it into its own admin",
}


def shape_deviations(properties: dict) -> list[str]:
    """How a role's actual properties differ from the designed shape.

    Pure, so the migration path (SQLAlchemy) and the operational report
    (psycopg) judge by the same rule instead of each keeping a copy that
    drifts.
    """
    return [
        _SHAPE_MEANING[name]
        for name, designed in DESIGNED_ROLE_SHAPE.items()
        if name in properties and bool(properties[name]) is not designed
    ]


class WeakerRoleExists(RuntimeError):
    """The role is already there, and it is not the role the design describes."""


def create_app_role(connection: Connection, *, role: str = APP_ROLE) -> None:
    """Create the login-less application role, or verify the one that exists.

    NOBYPASSRLS is stated explicitly rather than relied on as the default, so
    that reading this file answers the question.

    The guard used to be ``IF NOT EXISTS`` and nothing more, which meant it
    deferred to whatever already held the name. That is exactly how a deployed
    database ended up with an ``inv_app`` that has LOGIN and a password
    committed to the repository: a bootstrap script created the weaker role
    first, and every later migration saw the name and moved on. A guard written
    for idempotency must not yield to a weaker predecessor — so an existing
    role is now checked against the designed shape, and a mismatch refuses
    loudly instead of building tenant isolation on top of it.
    """
    connection.execute(
        text(
            "DO $$ BEGIN "
            f"IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN "
            f"CREATE ROLE {role} NOLOGIN NOBYPASSRLS NOSUPERUSER NOCREATEDB NOCREATEROLE; "
            "END IF; END $$;"
        )
    )
    row = connection.execute(
        text(
            "SELECT rolcanlogin, rolbypassrls, rolsuper, rolcreatedb, rolcreaterole "
            "FROM pg_roles WHERE rolname = :role"
        ),
        {"role": role},
    ).mappings().one()
    deviations = shape_deviations(dict(row))
    if deviations:
        # Deliberately not ALTER ROLE. The weaker role may be what a running
        # deployment currently connects as, and silently flipping it to
        # NOLOGIN mid-migration would take that deployment down as a side
        # effect. The operator chooses when; this chooses loudly.
        raise WeakerRoleExists(
            f"role {role!r} already exists and is weaker than designed: "
            + "; ".join(deviations)
            + ". It was probably created by a deployment bootstrap before the "
            "migrations ran. Recreate it to the designed shape (or drop it and "
            "re-run) before continuing — tenant isolation is built on this "
            "role being exactly what the design says it is."
        )


def grant_app_privileges(
    connection: Connection, *, role: str = APP_ROLE, tables: tuple[str, ...] | None = None
) -> None:
    """Grant the application role table privileges — never ownership.

    Evidence and audit tables are append-only for this role: UPDATE and DELETE
    are withheld, which is a real constraint on the application and explicitly
    not a claim of WORM against a superuser (PLAN-DB-001).
    """
    targets = TENANT_SCOPED_TABLES if tables is None else tables
    connection.execute(text(f"GRANT USAGE ON SCHEMA public TO {role}"))
    for table in targets:
        if table in APPEND_ONLY_TABLES:
            connection.execute(text(f"GRANT SELECT, INSERT ON {table} TO {role}"))
        else:
            connection.execute(
                text(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO {role}")
            )
    for table in APPEND_ONLY_TABLES:
        if table not in targets:
            connection.execute(text(f"GRANT SELECT, INSERT ON {table} TO {role}"))
    connection.execute(text(f"GRANT SELECT ON tenants TO {role}"))


def enable_rls(
    connection: Connection, *, role: str = APP_ROLE, tables: tuple[str, ...] | None = None
) -> None:
    """Enable, force and police RLS on every tenant scoped table."""
    targets = TENANT_SCOPED_TABLES if tables is None else tables
    for table in targets:
        connection.execute(text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        connection.execute(text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
        connection.execute(text(f"DROP POLICY IF EXISTS {policy_name(table)} ON {table}"))
        connection.execute(
            text(
                f"CREATE POLICY {policy_name(table)} ON {table} "
                f"FOR ALL TO {role} "
                f"USING (tenant_id = {_TENANT_EXPR}) "
                f"WITH CHECK (tenant_id = {_TENANT_EXPR})"
            )
        )


def disable_rls(connection: Connection, *, tables: tuple[str, ...] | None = None) -> None:
    targets = TENANT_SCOPED_TABLES if tables is None else tables
    for table in targets:
        connection.execute(text(f"DROP POLICY IF EXISTS {policy_name(table)} ON {table}"))
        connection.execute(text(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY"))
        connection.execute(text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))


def rls_report(connection: Connection) -> list[dict[str, object]]:
    """Return the live RLS state, for the migration test and the ops check."""
    rows = connection.execute(
        text(
            "SELECT c.relname AS table_name, c.relrowsecurity AS enabled, "
            "c.relforcerowsecurity AS forced, "
            "(SELECT count(*) FROM pg_policy p WHERE p.polrelid = c.oid) AS policies "
            "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relkind IN ('r','p') "
            "ORDER BY c.relname"
        )
    ).mappings()
    return [dict(row) for row in rows]
