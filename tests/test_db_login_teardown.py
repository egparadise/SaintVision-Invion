"""application_test_engine teardown boundary (VB-FIX-02).

engine.dispose() failing must not skip the DROP ROLE, or the owned login role leaks.
No real database: the owner engine and the SQLAlchemy engine are faked.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))


class _Raw:
    def __init__(self, log): self.log = log
    def execute(self, statement): self.log.append(repr(statement))


class _Begin:
    def __init__(self, log): self._log = log
    def __enter__(self):
        raw = _Raw(self._log)
        return type("Outer", (), {"connection": type("DBAPI", (), {"driver_connection": raw})()})()
    def __exit__(self, *a): return False


class FakeOwnerEngine:
    def __init__(self): self.log = []
    def begin(self): return _Begin(self.log)


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

    with pytest.raises(RuntimeError, match="injected dispose failure") as exc:
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
