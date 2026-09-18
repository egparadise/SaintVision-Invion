"""Failure-boundary controls for the disposable test-database provisioning (VB-FIX-01).

Five controls: normal, first-create (database) failure, database-success-then-role
failure, migration (prepare) failure, and teardown (drop) failure. Each asserts that
ONLY the resources actually created are dropped, that a drop failure of one resource
does not skip the other, and that the original error is preserved. No real database.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db_provision import provision_disposable_database  # noqa: E402


def _steps(fail_at=None):
    calls = []

    def step(name, ret=None):
        def run():
            calls.append(name)
            if fail_at == name:
                raise RuntimeError("injected %s failure" % name)
            return ret
        return run

    kw = dict(
        create_database=step("create_database"),
        create_role=step("create_role"),
        prepare=step("prepare", ret="SESSION-VALUE"),
        drop_database=step("drop_database"),
        drop_role=step("drop_role"),
    )
    return calls, kw


def _drive(kw, *, body_error=None):
    """Run the generator to its yield, then to teardown; return (yielded, raised)."""
    gen = provision_disposable_database(**kw)
    raised = None
    yielded = None
    try:
        yielded = next(gen)                 # setup up to and including yield
    except BaseException as exc:            # setup failed before yield
        return None, exc
    try:
        if body_error is not None:
            gen.throw(body_error)           # inject a body/test error -> finally
        else:
            next(gen)                       # resume past yield -> finally -> StopIteration
    except StopIteration:
        pass
    except BaseException as exc:            # teardown or re-raised error
        raised = exc
    return yielded, raised


def test_normal_creates_then_drops_both():
    calls, kw = _steps()
    yielded, raised = _drive(kw)
    assert yielded == "SESSION-VALUE" and raised is None
    assert calls == ["create_database", "create_role", "prepare", "drop_database", "drop_role"]


def test_first_create_failure_drops_nothing():
    calls, kw = _steps(fail_at="create_database")
    _, raised = _drive(kw)
    assert isinstance(raised, RuntimeError) and "create_database" in str(raised)
    assert calls == ["create_database"]     # nothing created -> nothing dropped


def test_database_success_then_role_failure_drops_only_database():
    calls, kw = _steps(fail_at="create_role")
    _, raised = _drive(kw)
    assert isinstance(raised, RuntimeError) and "create_role" in str(raised)
    # the created database IS dropped; the never-created role is NOT dropped
    assert calls == ["create_database", "create_role", "drop_database"]


def test_migration_failure_drops_both():
    calls, kw = _steps(fail_at="prepare")
    _, raised = _drive(kw)
    assert isinstance(raised, RuntimeError) and "prepare" in str(raised)
    assert calls == ["create_database", "create_role", "prepare", "drop_database", "drop_role"]


def test_teardown_drop_database_failure_still_drops_role_and_surfaces():
    calls, kw = _steps(fail_at="drop_database")
    _, raised = _drive(kw)
    # a DROP DATABASE failure must NOT skip the DROP ROLE, and must be surfaced
    assert calls == ["create_database", "create_role", "prepare", "drop_database", "drop_role"]
    assert isinstance(raised, RuntimeError) and "drop_database" in str(raised)


def test_body_error_is_preserved_through_teardown():
    calls, kw = _steps()
    body = AssertionError("real test failure")
    _, raised = _drive(kw, body_error=body)
    # teardown still drops both; the original body error is preserved (re-raised as-is
    # here because teardown itself did not fail)
    assert calls == ["create_database", "create_role", "prepare", "drop_database", "drop_role"]
    assert raised is body


def test_body_error_and_teardown_failure_both_preserved():
    calls, kw = _steps(fail_at="drop_database")
    body = AssertionError("real test failure")
    _, raised = _drive(kw, body_error=body)
    assert calls == ["create_database", "create_role", "prepare", "drop_database", "drop_role"]
    # cleanup failure surfaces, with the original body error kept on __context__
    assert isinstance(raised, RuntimeError) and "drop_database" in str(raised)
    assert raised.__context__ is body
