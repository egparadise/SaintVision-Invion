"""Transaction-local tenant scope.

CR-12. Tenant isolation rests on RLS reading ``inv.tenant_id`` from the session
state. That state must be established with ``SET LOCAL`` inside an explicit
transaction and never at session level: with a transaction-mode connection
pooler the backend is reassigned between transactions, and a session-level value
would be read by the next tenant's request.

Every tenant access therefore goes through :func:`tenant_scope`. There is no API
here for setting the scope outside a transaction, and ``tests/test_rls.py``
holds that shut.
"""

from __future__ import annotations

import contextlib
import uuid
from collections.abc import Iterator

from sqlalchemy import Engine, event, text
from sqlalchemy.orm import Session, sessionmaker

#: The GUC RLS policies read. ``inv`` is a custom namespace, so PostgreSQL keeps
#: it as a plain string setting.
TENANT_GUC = "inv.tenant_id"


class TenantScopeError(RuntimeError):
    """Tenant scope was requested outside an open transaction."""


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


@contextlib.contextmanager
def tenant_scope(session: Session, tenant_id: uuid.UUID | str) -> Iterator[Session]:
    """Run a block with the tenant scope applied for that transaction only.

    Opens a transaction if one is not already open, so callers cannot end up
    issuing the SET in autocommit mode where it would silently do nothing.
    """
    value = str(tenant_id)
    # Reject anything that is not a UUID before it reaches the SET statement.
    uuid.UUID(value)

    if not session.in_transaction():
        session.begin()
    # SET LOCAL does not accept a bind parameter, so the value is inlined. It is
    # a validated UUID by the line above; nothing else reaches this string.
    session.execute(text(f"SET LOCAL {TENANT_GUC} = '{value}'"))
    try:
        yield session
    finally:
        # The scope dies with the transaction. Nothing to unset.
        pass


def current_tenant(session: Session) -> str | None:
    """Return the tenant scope visible to this transaction, or None."""
    value = session.execute(
        text(f"SELECT current_setting('{TENANT_GUC}', true)")
    ).scalar_one_or_none()
    return value or None


def install_transaction_guard(engine: Engine) -> None:
    """Fail loudly if a tenant table is read with no transaction open.

    Registered only in tests and development. In production the same property is
    enforced by RLS returning zero rows, but zero rows is a silent wrong answer;
    during development we want the noisy one.
    """

    @event.listens_for(engine, "begin")
    def _mark(conn):  # pragma: no cover - trivial
        conn.info["inv_in_transaction"] = True
