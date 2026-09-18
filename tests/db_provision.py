"""Disposable test-database provisioning with ownership-tracked, independent teardown.

Split out of tests/integration/conftest.py so the failure boundary can be
regression-tested without a real PostgreSQL (VB-FIX-01). The postgres fixture created
the database and role BEFORE its try/finally, so a role-create failure after a
successful database-create left the try/finally unentered and the disposable database
undropped -- an accumulation on failure (the same class as a leaked container), even
though the run itself ended honestly as an ERROR.

This enters the cleanup structure BEFORE the first allocation, tracks ownership of each
resource that was actually created, drops ONLY those (never a name that failed to
create, never another run's resource), keeps a drop failure of one resource from
skipping the other, and preserves the original setup/body error together with any
cleanup error(s).
"""
from __future__ import annotations


def provision_disposable_database(*, create_database, create_role, prepare,
                                  drop_database, drop_role):
    """Generator: create the database, then the role, run ``prepare`` (migration +
    grants) and yield its value; on teardown drop only what was created, each drop
    independent, all errors preserved. Wrap it from a fixture with ``yield from``.

    ``prepare`` returns the value the fixture yields. Each argument is a zero-argument
    callable that raises on failure.
    """
    created_db = False
    created_role = False
    try:
        create_database()
        created_db = True          # only after the create actually succeeded
        create_role()
        created_role = True
        yield prepare()
    finally:
        cleanup_errors = []
        if created_db:
            try:
                drop_database()
            except Exception as exc:  # noqa: BLE001 -- record; do NOT skip the role drop
                cleanup_errors.append(exc)
        if created_role:
            try:
                drop_role()
            except Exception as exc:  # noqa: BLE001
                cleanup_errors.append(exc)
        if cleanup_errors:
            # Surface the cleanup failure. If the finally is unwinding a setup/body
            # error, Python keeps it on __context__, so both are preserved.
            if len(cleanup_errors) == 1:
                raise cleanup_errors[0]
            raise ExceptionGroup("disposable database teardown failed", cleanup_errors)
