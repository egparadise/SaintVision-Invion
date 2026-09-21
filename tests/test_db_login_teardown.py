"""application_test_engine teardown boundary (VB-FIX-02).

engine.dispose() failing must not skip the DROP ROLE, or the owned login role leaks.
No real database: the owner engine and the SQLAlchemy engine are faked.
"""
import sys
from pathlib import Path

import pytest
from raises_no_skip import raises_without_skip

sys.path.insert(0, str(Path(__file__).resolve().parent))


class _Raw:
    def __init__(self, log, fail_drop): self.log = log; self.fail_drop = fail_drop
    def execute(self, statement):
        self.log.append(repr(statement))
        if self.fail_drop and "DROP ROLE" in repr(statement):
            raise RuntimeError("injected DROP ROLE failure")


class _Begin:
    def __init__(self, log, fail_drop): self._log = log; self._fail_drop = fail_drop
    def __enter__(self):
        raw = _Raw(self._log, self._fail_drop)
        return type("Outer", (), {"connection": type("DBAPI", (), {"driver_connection": raw})()})()
    def __exit__(self, *a): return False


class FakeOwnerEngine:
    def __init__(self, fail_drop=False): self.log = []; self.fail_drop = fail_drop
    def begin(self): return _Begin(self.log, self.fail_drop)


class FakeEngine:
    def __init__(self, fail_dispose): self.fail = fail_dispose; self.disposed = False
    def dispose(self):
        self.disposed = True
        if self.fail:
            raise RuntimeError("injected dispose failure")


URL = "postgresql+psycopg://u:p@h:5432/db"


def _dropped_role(log):
    return any("DROP ROLE" in s for s in log)


def test_dispose_failure_still_drops_role_and_preserves_body_error(monkeypatch):
    import db_login
    owner = FakeOwnerEngine()
    engine = FakeEngine(fail_dispose=True)
    monkeypatch.setattr(db_login, "create_engine", lambda *a, **k: engine)

    with raises_without_skip(RuntimeError, match="injected dispose failure") as exc:
        with db_login.application_test_engine(URL, owner) as produced:
            assert produced is engine
            raise AssertionError("real body failure")

    assert engine.disposed is True
    assert _dropped_role(owner.log), "DROP ROLE was skipped after dispose() failed (role leak)"
    assert isinstance(exc.value.__context__, AssertionError)  # original body error preserved


def test_normal_teardown_disposes_and_drops_role(monkeypatch):
    import db_login
    owner = FakeOwnerEngine()
    engine = FakeEngine(fail_dispose=False)
    monkeypatch.setattr(db_login, "create_engine", lambda *a, **k: engine)

    with db_login.application_test_engine(URL, owner):
        pass

    assert engine.disposed is True and _dropped_role(owner.log)


def test_drop_role_failure_alone_surfaces(monkeypatch):
    import db_login
    owner = FakeOwnerEngine(fail_drop=True)
    engine = FakeEngine(fail_dispose=False)
    monkeypatch.setattr(db_login, "create_engine", lambda *a, **k: engine)
    with raises_without_skip(RuntimeError, match="injected DROP ROLE failure"):
        with db_login.application_test_engine(URL, owner):
            pass
    assert engine.disposed is True  # dispose still ran


def test_dispose_and_drop_role_both_fail_preserve_both(monkeypatch):
    import db_login
    owner = FakeOwnerEngine(fail_drop=True)
    engine = FakeEngine(fail_dispose=True)
    monkeypatch.setattr(db_login, "create_engine", lambda *a, **k: engine)

    with raises_without_skip(ExceptionGroup, match="application_test_engine teardown failed") as exc:
        with db_login.application_test_engine(URL, owner):
            raise AssertionError("real body failure")

    messages = [str(e) for e in exc.value.exceptions]
    assert any("injected dispose failure" in m for m in messages)   # dispose error kept
    assert any("injected DROP ROLE failure" in m for m in messages)  # drop error kept, not lost
    assert engine.disposed is True and _dropped_role(owner.log)      # both were attempted
    assert isinstance(exc.value.__context__, AssertionError)         # body error preserved
