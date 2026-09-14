"""A real non-owner login for tests, without touching a cluster-wide role.

This helper lived in ``tests/conftest.py`` and was imported as
``from conftest import application_test_engine``. That import is ambiguous:
this repository has two conftests (``tests/conftest.py`` and
``tests/integration/conftest.py``), and under pytest's default ``prepend``
import mode the name ``conftest`` resolves to whichever was imported last — the
integration one, which does not define this helper. Collecting the whole tree
therefore failed at import for every module that used that spelling. A plain
module has no such collision, so the helper lives here and the fixture and the
tests import it from ``db_login``.

It creates an owned, throwaway login role that *inherits* the migration-owned
``inv_app`` group and drops it afterwards, so a test runs as a genuine
non-owner NOBYPASSRLS principal without ever ALTERing the shared ``inv_app``
role — the reactivation of which is the exact regression these tests guard.
"""

from __future__ import annotations

import secrets
import uuid
from contextlib import contextmanager

from sqlalchemy import create_engine

#: Migration-owned permission group; tests never change its login or password.
APP_ROLE = "inv_app"


@contextmanager
def application_test_engine(database_url, owner_engine):
    """Owned temporary login inherits inv_app; leave cluster-wide groups intact."""
    from psycopg import sql
    from sqlalchemy.engine import make_url

    role = "inv_backend_login_" + uuid.uuid4().hex
    password = secrets.token_urlsafe(32)
    with owner_engine.begin() as connection:
        conn = connection.connection.driver_connection
        conn.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {} INHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION").format(
            sql.Identifier(role), sql.Literal(password)))
        conn.execute(sql.SQL("GRANT {} TO {}").format(sql.Identifier(APP_ROLE), sql.Identifier(role)))
    engine = None
    try:
        url = make_url(database_url).set(username=role, password=password)
        engine = create_engine(url, future=True)
        yield engine
    finally:
        if engine is not None:
            engine.dispose()
        assert role.startswith("inv_backend_login_") and len(role) == 50
        with owner_engine.begin() as connection:
            connection.connection.driver_connection.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))
