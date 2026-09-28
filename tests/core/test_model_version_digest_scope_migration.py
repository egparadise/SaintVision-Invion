"""0052: scoping the model version digest uniqueness to the model.

These drive ``upgrade()`` itself with a stand-in catalogue and record the SQL it
issues. The first version of this file read the migration's source and asserted
the order of substrings in it, which passed while matching ``ADD CONSTRAINT``
inside an explanatory *comment* -- so the statements are now observed rather than
read.

Four catalogue states, because which one the database is in decides what
converges:

* nothing there yet -- build the index concurrently and promote it;
* **the new constraint already there, exactly right** -- a run interrupted between
  the promotion and the drop. It must be left completely alone. Codex found that
  the first version dropped the index that constraint owns, which PostgreSQL
  refuses, wedging the migration at the crash point the docstring called safe;
* the name taken by something with a different shape -- refuse;
* rows that would violate the narrower rule -- refuse, before any DDL.

What the constraint *does*, and the same resume against a real database, are in
``tests/integration/test_model_version_digest_scope_real_pg.py``.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

OLD = "uq_model_versions_tenant_id_content_sha256"
NEW = "uq_model_versions_model_id_content_sha256"
MIGRATION = Path(__file__).resolve().parents[2] / (
    "migrations/versions/0052_model_version_digest_scope.py"
)


def _module():
    spec = importlib.util.spec_from_file_location("migration_0052", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Bind:
    """Answers the two questions the migration asks, and records that it was asked."""

    def __init__(self, *, constraint=None, violations=()):
        self.constraint = constraint
        self.violations = list(violations)
        self.asked = []

    def exec_driver_sql(self, sql):
        self.asked.append(sql)
        rows = (
            [self.constraint] if "pg_constraint" in sql and self.constraint else []
        )
        if "GROUP BY" in sql:
            rows = self.violations
        return _Result(rows)


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class Context:
    def __init__(self, *, as_sql=False, record=None):
        self.as_sql = as_sql
        self._record = record

    def autocommit_block(self):
        import contextlib

        if self._record is not None:
            self._record.append("<autocommit>")
        return contextlib.nullcontext()


def _run(monkeypatch, *, bind=None, as_sql=False):
    """Run ``upgrade()`` against a stand-in and return the SQL it issued."""
    import alembic.op as alembic_op

    module = _module()
    statements: list[str] = []
    monkeypatch.setattr(
        alembic_op, "get_context", lambda: Context(as_sql=as_sql, record=statements)
    )
    if bind is None:

        def no_bind():
            pytest.fail("this path must not ask for a connection")

        monkeypatch.setattr(alembic_op, "get_bind", no_bind)
    else:
        monkeypatch.setattr(alembic_op, "get_bind", lambda: bind)
    monkeypatch.setattr(alembic_op, "execute", lambda sql: statements.append(sql))
    module.upgrade()
    return statements


def test_it_sits_on_the_fixed_order_at_the_number_the_coordinator_assigned():
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'revision = "0052_model_version_digest_scope"' in source
    # 0052 by the coordinator's decision of 2026-09-28, which moved the W5
    # eval-suite migration to 0053. Pinned so a renumber cannot fork the graph.
    assert 'down_revision = "0051_service_credentials"' in source


# --------------------------------------------------------------------------
# Nothing there yet: build, promote, then drop the wide one
# --------------------------------------------------------------------------


def test_a_clean_catalogue_builds_promotes_and_then_drops_the_old_constraint(monkeypatch):
    statements = _run(monkeypatch, bind=Bind())
    assert statements[0] == "<autocommit>"
    assert "DROP INDEX CONCURRENTLY IF EXISTS" in statements[1]
    assert "CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS" in statements[2]
    assert f"ADD CONSTRAINT {NEW} UNIQUE USING INDEX {NEW}" in statements[3]
    assert f"DROP CONSTRAINT IF EXISTS {OLD}" in statements[4]
    assert len(statements) == 5


def test_the_index_name_is_cleared_before_the_concurrent_build(monkeypatch):
    """A failed ``CREATE UNIQUE INDEX CONCURRENTLY`` leaves an INVALID index
    holding the name, which ``ADD CONSTRAINT ... USING INDEX`` refuses."""
    statements = _run(monkeypatch, bind=Bind())
    drop = next(i for i, s in enumerate(statements) if "DROP INDEX CONCURRENTLY" in s)
    create = next(
        i for i, s in enumerate(statements) if "CREATE UNIQUE INDEX CONCURRENTLY" in s
    )
    assert drop < create


def test_the_new_constraint_exists_before_the_old_one_is_dropped(monkeypatch):
    statements = _run(monkeypatch, bind=Bind())
    add = next(i for i, s in enumerate(statements) if "ADD CONSTRAINT" in s)
    drop = next(i for i, s in enumerate(statements) if "DROP CONSTRAINT" in s)
    assert add < drop, "the table must never be left with no uniqueness at all"


# --------------------------------------------------------------------------
# Interrupted after the promotion: leave the constraint completely alone
# --------------------------------------------------------------------------


def test_a_resume_after_the_promotion_only_drops_the_old_constraint(monkeypatch):
    """The crash point the first version of this migration wedged on.

    Revision still 0051, the new constraint already promoted. A re-run that begins
    with ``DROP INDEX CONCURRENTLY IF EXISTS`` meets an index the constraint owns,
    and PostgreSQL answers ``cannot drop index ... because constraint ... requires
    it``. So the only statement this path may issue is the drop of the old one.
    """
    bind = Bind(constraint=("u", ["model_id", "content_sha256"]))
    statements = _run(monkeypatch, bind=bind)
    assert len(statements) == 1
    assert f"DROP CONSTRAINT IF EXISTS {OLD}" in statements[0]
    # Nothing touched the index or the constraint that owns it.
    joined = " ".join(statements)
    assert "DROP INDEX" not in joined
    assert "CREATE UNIQUE INDEX" not in joined
    assert "ADD CONSTRAINT" not in joined
    assert "<autocommit>" not in statements
    # And the violations query is not run either: the constraint already enforces
    # what it would have been checking.
    assert not any("GROUP BY" in sql for sql in bind.asked)


def test_the_resume_reads_the_catalogue_before_anything_else(monkeypatch):
    bind = Bind(constraint=("u", ["model_id", "content_sha256"]))
    _run(monkeypatch, bind=bind)
    assert bind.asked, "the catalogue decides which path converges"
    assert "pg_constraint" in bind.asked[0]
    assert NEW in bind.asked[0]
    assert "model_versions" in bind.asked[0]


@pytest.mark.parametrize(
    "constraint",
    [
        ("u", ["tenant_id", "content_sha256"]),
        ("u", ["content_sha256", "model_id"]),
        ("u", ["model_id"]),
        ("p", ["model_id", "content_sha256"]),
        ("u", None),
    ],
    ids=["other-columns", "wrong-order", "too-few", "not-unique", "no-columns"],
)
def test_the_same_name_with_a_different_shape_is_refused(monkeypatch, constraint):
    """Something other than this migration owns the name. Guessing is worse."""
    import alembic.op as alembic_op

    module = _module()
    statements: list[str] = []
    bind = Bind(constraint=constraint)
    monkeypatch.setattr(alembic_op, "get_context", lambda: Context(record=statements))
    monkeypatch.setattr(alembic_op, "get_bind", lambda: bind)
    monkeypatch.setattr(alembic_op, "execute", lambda sql: statements.append(sql))

    with pytest.raises(RuntimeError) as raised:
        module.upgrade()

    message = str(raised.value)
    assert NEW in message
    assert "reviewed fix" in message
    assert statements == [], "nothing was executed"


# --------------------------------------------------------------------------
# Data that would violate the narrower rule
# --------------------------------------------------------------------------


def test_a_row_that_would_violate_the_narrower_rule_stops_the_migration(monkeypatch):
    """Fail closed, and before any DDL.

    The argument for "no data migration" is that the dropped constraint is
    strictly stronger than the added one. If that is ever wrong, this is what the
    operator sees instead of a half-applied migration.
    """
    import alembic.op as alembic_op

    module = _module()
    statements: list[str] = []
    bind = Bind(violations=[("mdl_one", "a" * 64, 2)])
    monkeypatch.setattr(alembic_op, "get_context", lambda: Context(record=statements))
    monkeypatch.setattr(alembic_op, "get_bind", lambda: bind)
    monkeypatch.setattr(alembic_op, "execute", lambda sql: statements.append(sql))

    with pytest.raises(RuntimeError) as raised:
        module.upgrade()

    message = str(raised.value)
    assert NEW in message
    assert "mdl_one" in message, "the operator needs to know which rows"
    assert "reviewed data fix" in message
    assert statements == [], "nothing was executed"


def test_the_check_groups_by_the_columns_the_new_constraint_covers():
    module = _module()
    query = " ".join(module.VIOLATIONS.split())
    assert "GROUP BY model_id, content_sha256" in query
    assert "HAVING count(*) > 1" in query
    assert "FROM model_versions" in query


def test_the_catalogue_query_asks_about_this_table_and_this_name():
    module = _module()
    query = " ".join(module.CONSTRAINT_SHAPE.split())
    assert "FROM pg_constraint" in query
    assert f"c.conname = '{NEW}'" in query
    # Scoped to the table, so a same-named constraint elsewhere is not mistaken
    # for this one.
    assert "c.conrelid = 'model_versions'::regclass" in query
    assert "contype" in query


# --------------------------------------------------------------------------
# Offline rendering
# --------------------------------------------------------------------------


def test_offline_rendering_does_not_try_to_query_a_database(monkeypatch):
    """``alembic upgrade --sql`` renders against a mock connection.

    The Backend lane has a "Migration renders offline" step, and the first version
    of this migration broke it: the mock connection has no ``exec_driver_sql``. In
    that mode there is nothing to check and the output is SQL for review, so every
    read is skipped -- and asking the bind at all is the regression. ``_run`` fails
    the test if the bind is requested.
    """
    statements = _run(monkeypatch, bind=None, as_sql=True)
    # Every statement is still rendered, in order, for the reviewer.
    assert statements[0] == "<autocommit>"
    assert len(statements) == 5
    assert f"DROP CONSTRAINT IF EXISTS {OLD}" in statements[-1]


# --------------------------------------------------------------------------
# The refusal to reverse, and the metadata
# --------------------------------------------------------------------------


def test_the_downgrade_refuses_and_says_why_it_cannot_be_undone():
    module = _module()
    with pytest.raises(RuntimeError) as raised:
        module.downgrade()
    message = str(raised.value).lower()
    # Two reasons, not one: the data may no longer satisfy the wide constraint,
    # and restoring it would reopen the leak.
    assert "same bytes" in message
    assert "oracle" in message
    assert "forward fix" in message


def test_the_model_declares_the_constraint_the_migration_leaves_behind():
    """Otherwise the model and the database disagree about the schema."""
    from saintvision.db.models.lineage import ModelVersion

    names = {
        constraint.name
        for constraint in ModelVersion.__table__.constraints
        if constraint.name
    }
    assert NEW in names
    assert OLD not in names, "the tenant-wide rule is gone from the metadata too"
    constraint = next(c for c in ModelVersion.__table__.constraints if c.name == NEW)
    assert [column.name for column in constraint.columns] == ["model_id", "content_sha256"]


def test_the_original_invariant_is_still_expressible():
    """The point of narrowing is scope, not abandoning the rule.

    ``(model_id, content_sha256)`` still refuses the same bytes under two version
    names in one model, which is what ``0004_s10_lineage`` was protecting. The
    thing that disappears is the answer about another project.
    """
    from saintvision.db.models.lineage import ModelVersion

    constraint = next(c for c in ModelVersion.__table__.constraints if c.name == NEW)
    columns = [column.name for column in constraint.columns]
    assert "content_sha256" in columns
    assert "tenant_id" not in columns
    # model_id is narrower than tenant_id, not a different axis: a model has one
    # tenant, so nothing that was refused inside a model is allowed now.
    assert "model_id" in columns


# --------------------------------------------------------------------------
# The real-PostgreSQL fixture, exercised without PostgreSQL
# --------------------------------------------------------------------------


def test_the_real_pg_fixture_builds_its_rows_without_a_database():
    """A wrong column or a wrong id kind should not cost an hour of hosted CI.

    #167 spent one learning that ``new_id("code_commit")`` is not an entity kind,
    with every assertion behind it unrun. Importing the fixture and handing it a
    connection that only records statements catches that class here.
    """
    import datetime as dt
    import uuid as uuid_module

    path = (
        Path(__file__).resolve().parents[1]
        / "integration/test_model_version_digest_scope_real_pg.py"
    )
    spec = importlib.util.spec_from_file_location("real_pg_0052_fixture", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class Recorder:
        def __init__(self):
            self.statements: list[str] = []

        def execute(self, statement, params=None):
            self.statements.append(str(statement))
            return None

    recorder = Recorder()
    now = dt.datetime(2026, 9, 28, tzinfo=dt.timezone.utc)
    tenant = uuid_module.UUID("11111111-1111-1111-1111-111111111111")
    model = module._project_with_model(recorder, tenant_id=tenant, now=now, label="guard")
    assert set(model) == {"project_id", "model_id", "name"}
    module._version(
        recorder,
        tenant_id=tenant,
        model=model,
        version="1.0.0",
        digest=module._digest(),
        now=now,
    )
    written = [
        statement.split("INSERT INTO ", 1)[1].split(" ", 1)[0]
        for statement in recorder.statements
    ]
    assert written == ["projects", "models", "model_versions"], written

    from saintvision.ids import is_id

    assert is_id(model["project_id"], "project")
    assert is_id(model["model_id"], "model")
    # 64 lowercase hex, which is what the checksum column's CHECK requires.
    digest = module._digest()
    assert len(digest) == 64 and digest == digest.lower()
