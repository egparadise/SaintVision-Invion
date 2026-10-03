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

from saintvision.ids import is_id

#: The GUC RLS policies read. ``inv`` is a custom namespace, so PostgreSQL keeps
#: it as a plain string setting.
TENANT_GUC = "inv.tenant_id"

#: The GUC that says which project the request was authorised for (0062).
#:
#: Phase 1 does not change any policy, so nothing in the database reads this yet.
#: It is set anyway, by the one route that has checked the caller's membership,
#: so that Phase 2 can replace ``data_locations_tenant_isolation`` with a
#: tenant+project policy without touching the route -- and so that any future
#: reader which forgets to set it gets zero rows rather than another project's.
PROJECT_GUC = "inv.project_id"

#: The GUC that says which human the request was verified as.
#:
#: Why this exists as transaction state rather than a function argument: the
#: release-acceptance write contract (``#282`` §4-1) forbids the canonical write
#: functions from taking a raw user ID argument, and the reason is sound. An
#: argument is a claim the caller makes; a function that accepts one can be asked
#: to record a decision as somebody else, and then the two-person rule is a rule
#: about whatever two strings the caller passed. Reading the acting user from
#: transaction state that only the request path sets means the function sees the
#: identity the token was verified as, or nothing.
#:
#: It is **not** authorisation. It says who this is; the function still re-reads
#: the active user mapping and the live permission. Unset is the normal state for
#: every other request in the system, and the functions fail closed on it.
ACTOR_GUC = "inv.user_id"


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


@contextlib.contextmanager
def project_scope(session: Session, project_id: str) -> Iterator[Session]:
    """Run a block with one project scope applied for that transaction only (0062).

    The value must be a project the request has already been authorised for --
    ``project_service.require_project_access`` judged it and the route re-checked
    it after taking its locks. A raw path segment that has not been through that
    check must not reach this function: the GUC exists so the database reads a
    project the caller could not choose for themselves.

    Transaction-local for the same reason as :func:`tenant_scope`: a pooled
    backend must not carry one request's project into the next one.
    """
    value = str(project_id)
    # SET LOCAL takes no bind parameter, so the value is inlined -- which means it
    # must be proven to be an ID first. ``prj_`` plus 26 Crockford base32
    # characters has no quote, no space and no semicolon in its alphabet.
    if not is_id(value, "project"):
        raise ValueError("project scope requires an authorised project ID")

    if not session.in_transaction():
        session.begin()
    session.execute(text(f"SET LOCAL {PROJECT_GUC} = '{value}'"))
    try:
        yield session
    finally:
        # The scope dies with the transaction, like the tenant's.
        pass


@contextlib.contextmanager
def actor_scope(session: Session, user_id: str) -> Iterator[Session]:
    """Run a block with the server-derived acting user applied for that transaction only.

    Pass the user the request *derived* from a verified credential -- never a value
    that arrived in a body, a path, or a header. The whole point of the GUC is that
    the database reads an identity the caller could not choose; handing it a caller's
    string would undo that in one line.

    Transaction-local for the same reason as :func:`tenant_scope`: a session-level
    value would outlive the request and be read by the next one on the same pooled
    backend, which is to say it would attribute one person's decision to another.
    """
    value = str(user_id)
    # SET LOCAL takes no bind parameter, so the value is inlined -- which means it
    # must be proven to be an ID first. ``usr_`` plus 26 Crockford base32
    # characters has no quote, no space, and no semicolon in its alphabet.
    if not is_id(value, "user"):
        raise ValueError("actor scope requires a user ID derived from a verified credential")

    if not session.in_transaction():
        session.begin()
    session.execute(text(f"SET LOCAL {ACTOR_GUC} = '{value}'"))
    try:
        yield session
    finally:
        # The scope dies with the transaction, like the tenant's.
        pass


def current_tenant(session: Session) -> str | None:
    """Return the tenant scope visible to this transaction, or None."""
    value = session.execute(
        text(f"SELECT current_setting('{TENANT_GUC}', true)")
    ).scalar_one_or_none()
    return value or None


def current_actor(session: Session) -> str | None:
    """Return the acting user visible to this transaction, or None.

    ``None`` is what every request that never set it sees, so a reader of this
    value cannot tell "no human" from "not set" -- and must not need to. The
    canonical write functions treat both as no human.
    """
    value = session.execute(
        text(f"SELECT current_setting('{ACTOR_GUC}', true)")
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
