"""0053: the evaluation suite's project column, driven against a stand-in catalogue.

Same method as ``test_model_version_digest_scope_migration.py`` (0052): the
migration's ``upgrade()``/``downgrade()`` run with ``alembic.op`` replaced, so
what is asserted is the statements they issue for each catalogue state, not
substrings of the source.

Catalogue states, because which one the database is in decides what converges:

* nothing there -- add the column, the foreign key and the index;
* the column there with the right shape (a resume) -- keep it, check the data,
  add only what is missing;
* the column or the foreign key there with a different shape -- refuse;
* on a resume, rows referencing a project that is not theirs -- refuse before
  any DDL;
* a downgrade while any suite holds a project -- refuse; otherwise drop all
  three, each ``IF EXISTS``.

What the column and the foreign key *do* on a real database is
``tests/integration/test_eval_suite_project_scope_real_pg.py``.
"""

from __future__ import annotations

import contextlib
import importlib.util
from pathlib import Path

import pytest

MIGRATION = Path(__file__).resolve().parents[2] / "migrations/versions/0053_eval_suite_project_scope.py"
COLUMN_OK = ("character", 30, "YES")
FK_OK = ("f", "projects", ["tenant_id", "project_id"], ["tenant_id", "project_id"])


def _module():
    spec = importlib.util.spec_from_file_location("migration_0053", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class Bind:
    """Answers the catalogue and data questions, and records that it was asked."""

    def __init__(self, *, column=None, fk=None, index=False, violations=(), scoped=()):
        self.column = column
        self.fk = fk
        self.index = index
        self.violations = list(violations)
        self.scoped = list(scoped)
        self.asked: list[str] = []

    def exec_driver_sql(self, sql):
        self.asked.append(sql)
        if "information_schema.columns" in sql:
            return _Result([self.column] if self.column else [])
        if "pg_constraint" in sql:
            return _Result([self.fk] if self.fk else [])
        if "pg_indexes" in sql:
            return _Result([(1,)] if self.index else [])
        if "LEFT JOIN" in sql:
            return _Result([(s,) for s in self.violations])
        if "IS NOT NULL ORDER BY" in sql:
            return _Result([(s,) for s in self.scoped])
        raise AssertionError(f"unexpected question: {sql[:80]}")


class Context:
    def __init__(self, *, as_sql=False):
        self.as_sql = as_sql

    def autocommit_block(self):
        return contextlib.nullcontext()


def _run(monkeypatch, *, bind=None, as_sql=False, direction="upgrade"):
    """Run the migration against a stand-in and return the operations it issued."""
    import alembic.op as alembic_op

    module = _module()
    issued: list[tuple] = []
    monkeypatch.setattr(alembic_op, "get_context", lambda: Context(as_sql=as_sql))
    if bind is None:
        monkeypatch.setattr(alembic_op, "get_bind", lambda: pytest.fail("this path must not ask for a connection"))
    else:
        monkeypatch.setattr(alembic_op, "get_bind", lambda: bind)
    monkeypatch.setattr(alembic_op, "execute", lambda sql: issued.append(("execute", sql)))
    monkeypatch.setattr(alembic_op, "add_column", lambda table, column: issued.append(("add_column", table, column.name, str(column.type), column.nullable)))
    monkeypatch.setattr(
        alembic_op, "create_foreign_key",
        lambda name, source, referent, local_cols, remote_cols, **kw: issued.append(("create_foreign_key", name, source, referent, list(local_cols), list(remote_cols))),
    )
    monkeypatch.setattr(alembic_op, "create_index", lambda name, table, columns, **kw: issued.append(("create_index", name, table, list(columns))))
    getattr(module, direction)()
    return issued


ADD_COLUMN = ("add_column", "eval_suites", "project_id", "CHAR(30)", True)
ADD_FK = ("create_foreign_key", "fk_eval_suites_tenant_id_project_id", "eval_suites", "projects", ["tenant_id", "project_id"], ["tenant_id", "project_id"])
ADD_INDEX = ("create_index", "ix_eval_suites_tenant_id_project_id", "eval_suites", ["tenant_id", "project_id"])


def test_it_sits_on_the_fixed_order_at_the_number_the_coordinator_assigned():
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'revision = "0053_eval_suite_project_scope"' in source
    # 0053 by the coordinator's decision of 2026-09-28 on #191: 0052 went to the
    # digest-scope fix (#197). Pinned so a renumber cannot fork the graph.
    assert 'down_revision = "0052_model_version_digest_scope"' in source


def test_the_graph_has_one_head_and_it_is_this_revision():
    import subprocess
    import sys

    root = Path(__file__).resolve().parents[2]
    head = subprocess.run(
        [sys.executable, str(root / "tools/migration_graph.py"), "--head"],
        capture_output=True, text=True, cwd=root,
    )
    assert head.returncode == 0, head.stderr
    assert head.stdout.strip() == "0053_eval_suite_project_scope"


# ---------------------------------------------------------------- upgrade paths


def test_a_clean_catalogue_adds_the_column_the_foreign_key_and_the_index(monkeypatch):
    bind = Bind()
    issued = _run(monkeypatch, bind=bind)
    assert issued == [ADD_COLUMN, ADD_FK, ADD_INDEX]
    # No data question on a fresh run: there is no column to read.
    assert not any("LEFT JOIN" in q for q in bind.asked)


def test_offline_rendering_issues_everything_and_asks_nothing(monkeypatch):
    issued = _run(monkeypatch, as_sql=True)
    assert issued == [ADD_COLUMN, ADD_FK, ADD_INDEX]


def test_a_resume_with_the_column_right_adds_only_what_is_missing(monkeypatch):
    bind = Bind(column=COLUMN_OK)
    assert _run(monkeypatch, bind=bind) == [ADD_FK, ADD_INDEX]
    bind = Bind(column=COLUMN_OK, fk=FK_OK)
    assert _run(monkeypatch, bind=bind) == [ADD_INDEX]
    bind = Bind(column=COLUMN_OK, fk=FK_OK, index=True)
    assert _run(monkeypatch, bind=bind) == []                       # fully applied: nothing touched


def test_a_resume_checks_the_data_before_the_foreign_key_and_refuses_orphans(monkeypatch):
    bind = Bind(column=COLUMN_OK, violations=["evs_01J8Z3XQ2K9WMV5T7N4B6C8D0E"])
    with pytest.raises(RuntimeError) as raised:
        _run(monkeypatch, bind=bind)
    assert "evs_01J8Z3XQ2K9WMV5T7N4B6C8D0E" in str(raised.value) and "reviewed data fix" in str(raised.value)
    assert not any(q for q in bind.asked if "pg_constraint" in q)  # refused before any DDL question


@pytest.mark.parametrize(
    "column",
    [("character varying", 30, "YES"), ("character", 64, "YES"), ("character", 30, "NO")],
    ids=["type", "width", "not-null"],
)
def test_a_column_of_that_name_with_a_different_shape_is_refused(monkeypatch, column):
    with pytest.raises(RuntimeError) as raised:
        _run(monkeypatch, bind=Bind(column=column))
    assert "different definition" in str(raised.value)


@pytest.mark.parametrize(
    "fk",
    [
        ("f", "workloads", ["tenant_id", "project_id"], ["tenant_id", "project_id"]),
        ("f", "projects", ["project_id"], ["project_id"]),
        ("u", "projects", ["tenant_id", "project_id"], ["tenant_id", "project_id"]),
    ],
    ids=["other-table", "not-composite", "not-a-fk"],
)
def test_a_constraint_of_that_name_with_a_different_shape_is_refused(monkeypatch, fk):
    with pytest.raises(RuntimeError) as raised:
        _run(monkeypatch, bind=Bind(column=COLUMN_OK, fk=fk))
    assert "different definition" in str(raised.value)


# ---------------------------------------------------------------- downgrade


def test_a_downgrade_with_no_scoped_suite_drops_all_three_if_exists(monkeypatch):
    issued = _run(monkeypatch, bind=Bind(), direction="downgrade")
    sql = [s for kind, s in issued if kind == "execute"]
    assert sql == [
        "DROP INDEX IF EXISTS ix_eval_suites_tenant_id_project_id",
        "ALTER TABLE eval_suites DROP CONSTRAINT IF EXISTS fk_eval_suites_tenant_id_project_id",
        "ALTER TABLE eval_suites DROP COLUMN IF EXISTS project_id",
    ]


def test_a_downgrade_refuses_while_any_suite_holds_a_project(monkeypatch):
    bind = Bind(scoped=["evs_01J8Z3XQ2K9WMV5T7N4B6C8D0E"])
    with pytest.raises(RuntimeError) as raised:
        _run(monkeypatch, bind=bind, direction="downgrade")
    assert "discard" in str(raised.value) and "evs_01J8Z3XQ2K9WMV5T7N4B6C8D0E" in str(raised.value)


def test_the_model_declares_the_same_column_constraint_and_index():
    from saintvision.db.models import EvalSuite

    column = EvalSuite.__table__.columns["project_id"]
    assert column.nullable is True and str(column.type) == "CHAR(30)"          # InvId, like every id column
    names = {c.name for c in EvalSuite.__table__.constraints}
    assert "fk_eval_suites_tenant_id_project_id" in names
    assert {i.name for i in EvalSuite.__table__.indexes} >= {"ix_eval_suites_tenant_id_project_id"}
