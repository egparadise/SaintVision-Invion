"""0052: scoping the model version digest uniqueness to the model.

Three things are worth a test here and none of them is the DDL string.

* The **order**. The new constraint is created before the old one is dropped, so
  the table is never briefly unprotected, and the concurrent index is dropped by
  name first so a retry after a failed build can succeed.
* The **pre-check**. The argument that no existing row can violate the narrower
  constraint is an argument; the migration reads the database before acting on it
  and refuses with a sentence rather than an opaque DDL error.
* The **refusal to reverse**. Narrowing cannot be undone, and the reason is not
  "it is hard" -- restoring the wide constraint would reopen the cross-project
  existence oracle the narrowing closed.

What the constraint *does* is the database's behaviour and lives in
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


def test_it_sits_on_the_fixed_order_at_the_number_the_coordinator_assigned():
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'revision = "0052_model_version_digest_scope"' in source
    # 0052 by the coordinator's decision of 2026-09-28, which moved the W5
    # eval-suite migration to 0053. Pinned so a renumber cannot fork the graph.
    assert 'down_revision = "0051_service_credentials"' in source


def _executed_statements():
    """The SQL the upgrade actually executes, in order.

    Extracted from the ``op.execute`` calls rather than by searching the function
    body: the body also *explains* these statements in comments, and a test that
    matched the prose would pass on a reordered migration whose comments still
    said the right thing. That is the failure this helper exists to avoid -- the
    first version of this file found "ADD CONSTRAINT" in a comment.
    """
    import ast

    source = MIGRATION.read_text(encoding="utf-8")
    tree = ast.parse(source)
    upgrade = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "upgrade"
    )
    found = []
    for node in ast.walk(upgrade):
        if not isinstance(node, ast.Call):
            continue
        callee = node.func
        if getattr(callee, "attr", None) != "execute" or not node.args:
            continue
        argument = node.args[0]
        if isinstance(argument, ast.JoinedStr):
            # An f-string: keep the literal parts and the interpolated names, so
            # the statement reads the way it was written.
            parts = []
            for value in argument.values:
                if isinstance(value, ast.Constant):
                    parts.append(str(value.value))
                elif isinstance(value, ast.FormattedValue):
                    parts.append("{" + ast.unparse(value.value) + "}")
            text = "".join(parts)
        elif isinstance(argument, ast.Constant):
            text = str(argument.value)
        else:
            continue
        # ``ast.walk`` is breadth first, so position is what puts these in the
        # order the migration runs them.
        found.append((node.lineno, node.col_offset, text))
    return [text for _line, _col, text in sorted(found)]


def test_the_new_constraint_is_created_before_the_old_one_is_dropped():
    statements = _executed_statements()
    create = next(i for i, s in enumerate(statements) if "CREATE UNIQUE INDEX" in s)
    add = next(i for i, s in enumerate(statements) if "ADD CONSTRAINT" in s)
    drop = next(i for i, s in enumerate(statements) if "DROP CONSTRAINT" in s)
    assert create < add < drop
    # A crash between the add and the drop leaves both constraints, which both
    # hold, so a retry converges. The other order leaves the table unprotected.
    assert "{NEW_CONSTRAINT}" in statements[add]
    assert "{OLD_CONSTRAINT}" in statements[drop]


def test_the_concurrent_build_clears_its_own_failed_attempt_first():
    source = MIGRATION.read_text(encoding="utf-8")
    assert "autocommit_block()" in source, "CONCURRENTLY cannot run in a transaction"
    statements = _executed_statements()
    drop_index = next(
        i for i, s in enumerate(statements) if "DROP INDEX CONCURRENTLY IF EXISTS" in s
    )
    create = next(
        i
        for i, s in enumerate(statements)
        if "CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS" in s
    )
    assert drop_index < create, (
        "ADD CONSTRAINT USING INDEX refuses an INVALID index holding the name"
    )


def test_the_check_groups_by_the_columns_the_new_constraint_covers():
    module = _module()
    query = " ".join(module.VIOLATIONS.split())
    assert "GROUP BY model_id, content_sha256" in query
    assert "HAVING count(*) > 1" in query
    assert "FROM model_versions" in query


def test_a_row_that_would_violate_the_narrower_rule_stops_the_migration(monkeypatch):
    """Fail closed, and before any DDL.

    The argument for "no data migration" is that the dropped constraint is
    strictly stronger than the added one. If that is ever wrong, this is what the
    operator sees instead of a half-applied migration.
    """
    import alembic.op as alembic_op

    module = _module()
    touched = []

    class Bind:
        def exec_driver_sql(self, _sql):
            class Result:
                def fetchall(self_inner):
                    return [("mdl_one", "a" * 64, 2)]

            return Result()

    class Context:
        """Online mode, so the guard reads the database."""

        as_sql = False

        def autocommit_block(self):
            pytest.fail("the check must refuse before any DDL")

    monkeypatch.setattr(alembic_op, "get_bind", lambda: Bind())
    monkeypatch.setattr(alembic_op, "execute", lambda sql: touched.append(sql))
    monkeypatch.setattr(alembic_op, "get_context", lambda: Context())

    with pytest.raises(RuntimeError) as raised:
        module.upgrade()

    message = str(raised.value)
    assert NEW in message
    assert "mdl_one" in message, "the operator needs to know which rows"
    assert "reviewed data fix" in message
    assert touched == [], "nothing was executed"


def test_a_clean_database_lets_the_migration_proceed(monkeypatch):
    """The same path with no offending rows reaches the DDL, in order."""
    import alembic.op as alembic_op

    module = _module()
    statements = []

    class Bind:
        def exec_driver_sql(self, _sql):
            class Result:
                def fetchall(self_inner):
                    return []

            return Result()

    class Context:
        as_sql = False

        def autocommit_block(self):
            import contextlib

            statements.append("<autocommit>")
            return contextlib.nullcontext()

    monkeypatch.setattr(alembic_op, "get_bind", lambda: Bind())
    monkeypatch.setattr(alembic_op, "get_context", lambda: Context())
    monkeypatch.setattr(alembic_op, "execute", lambda sql: statements.append(sql))

    module.upgrade()

    assert statements[0] == "<autocommit>"
    kinds = [
        "DROP INDEX CONCURRENTLY" in s
        or "CREATE UNIQUE INDEX CONCURRENTLY" in s
        or "ADD CONSTRAINT" in s
        or "DROP CONSTRAINT" in s
        for s in statements[1:]
    ]
    assert all(kinds), statements
    assert "DROP INDEX CONCURRENTLY IF EXISTS" in statements[1]
    assert "CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS" in statements[2]
    assert f"ADD CONSTRAINT {NEW} UNIQUE USING INDEX {NEW}" in statements[3]
    assert f"DROP CONSTRAINT {OLD}" in statements[4]
    assert len(statements) == 5


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

    constraint = next(
        c for c in ModelVersion.__table__.constraints if c.name == NEW
    )
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
    model = module._project_with_model(
        recorder, tenant_id=tenant, now=now, label="guard"
    )
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


def test_offline_rendering_does_not_try_to_query_a_database(monkeypatch):
    """``alembic upgrade --sql`` renders against a mock connection.

    The Backend lane has a "Migration renders offline" step, and the first version
    of this migration broke it: the mock connection has no ``exec_driver_sql``.
    In that mode there is nothing to check and the output is SQL for review, so
    the guard is skipped -- and asking the bind at all is the regression.
    """
    import alembic.op as alembic_op

    module = _module()
    statements = []

    class Context:
        as_sql = True

        def autocommit_block(self):
            import contextlib

            return contextlib.nullcontext()

    def no_bind():
        pytest.fail("offline rendering must not ask for a connection")

    monkeypatch.setattr(alembic_op, "get_context", lambda: Context())
    monkeypatch.setattr(alembic_op, "get_bind", no_bind)
    monkeypatch.setattr(alembic_op, "execute", lambda sql: statements.append(sql))

    module.upgrade()

    # Every statement is still rendered, in order, for the reviewer.
    assert len(statements) == 4
    assert f"DROP CONSTRAINT {OLD}" in statements[-1]
