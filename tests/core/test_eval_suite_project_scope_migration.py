"""0053: the evaluation suite's project column, driven against a stand-in catalogue.

Same method as ``test_model_version_digest_scope_migration.py`` (0052): the
migration's ``upgrade()``/``downgrade()`` run with ``alembic.op`` replaced, so
what is asserted is the statements they issue for each catalogue state, not
substrings of the source.

Catalogue states, because which one the database is in decides what converges:

* nothing there -- add the column, the foreign key and the index;
* the column there with the right shape (a resume) -- keep it, check the data,
  add only what is missing;
* the column, the foreign key or the index there with a different shape --
  refuse, where "shape" includes the foreign key's referential actions,
  deferrability and validity (Codex #202 F1) and the index's column order,
  uniqueness, predicate, expression and validity (Codex #202 F2);
* the index there with the right shape but invalid or not ready -- drop and
  rebuild it, the one residue this migration repairs;
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
FK_OK = ("f", "projects", ["tenant_id", "project_id"], ["tenant_id", "project_id"], "a", "a", "s", False, False, True)
INDEX_OK = (["tenant_id", "project_id"], False, False, False, "btree", True, True)


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

    def __init__(self, *, column=None, fk=None, index=None, violations=(), scoped=()):
        self.column = column
        self.fk = fk
        self.index = index                      # a full INDEX_SHAPE row, or None
        self.violations = list(violations)
        self.scoped = list(scoped)
        self.asked: list[str] = []

    def exec_driver_sql(self, sql):
        self.asked.append(sql)
        if "information_schema.columns" in sql:
            return _Result([self.column] if self.column else [])
        if "pg_constraint" in sql:
            return _Result([self.fk] if self.fk else [])
        if "pg_index" in sql:
            return _Result([self.index] if self.index else [])
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
    # Later revisions sit above this migration; the repository graph must still
    # converge on the current release-acceptance resolver head.
    assert head.stdout.strip() == "0063_build_policy_resource_budgets"


# ---------------------------------------------------------------- upgrade paths


def test_a_clean_catalogue_adds_the_column_the_foreign_key_and_the_index(monkeypatch):
    bind = Bind()
    issued = _run(monkeypatch, bind=bind)
    assert issued == [ADD_COLUMN, ADD_FK, ADD_INDEX]
    # No data question on a fresh run: there is no column to read.
    assert not any("LEFT JOIN projects" in q for q in bind.asked)   # the data question, not the index shape query


def test_offline_rendering_issues_everything_and_asks_nothing(monkeypatch):
    issued = _run(monkeypatch, as_sql=True)
    assert issued == [ADD_COLUMN, ADD_FK, ADD_INDEX]


def test_a_resume_with_the_column_right_adds_only_what_is_missing(monkeypatch):
    bind = Bind(column=COLUMN_OK)
    assert _run(monkeypatch, bind=bind) == [ADD_FK, ADD_INDEX]
    bind = Bind(column=COLUMN_OK, fk=FK_OK)
    assert _run(monkeypatch, bind=bind) == [ADD_INDEX]
    bind = Bind(column=COLUMN_OK, fk=FK_OK, index=INDEX_OK)
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


def _fk(**overrides):
    fields = ["contype", "referenced", "columns", "referenced_columns", "on_update", "on_delete", "match_type", "deferrable", "initially_deferred", "validated"]
    values = dict(zip(fields, FK_OK))
    values.update(overrides)
    return tuple(values[f] for f in fields)


@pytest.mark.parametrize(
    "fk",
    [
        _fk(referenced="workloads"),
        _fk(columns=["project_id"], referenced_columns=["project_id"]),
        _fk(contype="u"),
        _fk(on_delete="c"),                      # ON DELETE CASCADE: a project deletion would delete suites
        _fk(on_update="c"),                      # ON UPDATE CASCADE
        _fk(on_delete="n"),                      # ON DELETE SET NULL
        _fk(match_type="f"),                     # MATCH FULL: would refuse (tenant_id, NULL), the unscoped suite (Codex #202 R1)
        _fk(match_type="p"),                     # MATCH PARTIAL
        _fk(deferrable=True),                    # DEFERRABLE
        _fk(deferrable=True, initially_deferred=True),
        _fk(validated=False),                    # NOT VALID
    ],
    ids=["other-table", "not-composite", "not-a-fk", "delete-cascade", "update-cascade", "delete-set-null", "match-full", "match-partial", "deferrable", "initially-deferred", "not-valid"],
)
def test_a_constraint_of_that_name_with_a_different_shape_is_refused(monkeypatch, fk):
    """Codex #202 F1: the name and the columns are not the contract; the
    referential actions, deferrability and validity are part of it."""
    bind = Bind(column=COLUMN_OK, fk=fk)
    with pytest.raises(RuntimeError) as raised:
        _run(monkeypatch, bind=bind)
    assert "different definition" in str(raised.value)
    assert not any("pg_index" in q for q in bind.asked)              # refused before the index is even looked at


def _index(**overrides):
    fields = ["columns", "is_unique", "is_partial", "is_expression", "access_method", "is_valid", "is_ready"]
    values = dict(zip(fields, INDEX_OK))
    values.update(overrides)
    return tuple(values[f] for f in fields)


@pytest.mark.parametrize(
    "index",
    [
        _index(columns=["project_id", "tenant_id"]),   # wrong order
        _index(columns=["project_id"]),                # other columns
        _index(is_unique=True),                        # unique
        _index(is_partial=True),                       # partial
        _index(is_expression=True),                    # expression
        _index(access_method="hash"),                  # another access method under the name
    ],
    ids=["column-order", "other-columns", "unique", "partial", "expression", "access-method"],
)
def test_an_index_of_that_name_with_a_different_shape_is_refused(monkeypatch, index):
    """Codex #202 F2: an index is judged by its columns in order, uniqueness,
    predicate and expression -- not by its name being present."""
    with pytest.raises(RuntimeError) as raised:
        _run(monkeypatch, bind=Bind(column=COLUMN_OK, fk=FK_OK, index=index))
    assert "different definition" in str(raised.value)


@pytest.mark.parametrize("index", [_index(is_valid=False), _index(is_ready=False)], ids=["invalid", "not-ready"])
def test_an_index_of_the_right_shape_that_is_invalid_is_dropped_and_rebuilt(monkeypatch, index):
    """The residue of an interrupted build is the one state repaired: the
    shape says it is ours, and an invalid index serves nobody."""
    issued = _run(monkeypatch, bind=Bind(column=COLUMN_OK, fk=FK_OK, index=index))
    assert issued == [("execute", "DROP INDEX IF EXISTS ix_eval_suites_tenant_id_project_id"), ADD_INDEX]


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
