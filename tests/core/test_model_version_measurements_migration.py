"""0054 without a server: what the migration asks, issues and refuses.

The migration is loaded from its file and run against a stand-in connection
that answers the catalogue and data questions and records every operation.
What is fixed here is the shape of the decision, not PostgreSQL's behaviour:
a clean catalogue gets the kernel table, the column, the key, the CHECK and
the grant in that order; a resume adds only what is missing; a same-named
object of a different shape stops the run; a verified version nothing can
bind stops it before any DDL; the downgrade refuses while evidence exists.
The real database is ``tests/integration/test_model_version_measurements_real_pg.py``.

Design #209 v1.1 §4 also asks for two properties of the code, not the
database: ``verify_model_version`` cannot be called with a digest alone, and
no call site anywhere does. Both are tests here.
"""

from __future__ import annotations

import contextlib
import importlib.util
import inspect
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "migrations/versions/0054_model_version_measurements.py"
KERNEL_SQL = ROOT / "services/control-plane/src/inv/migrations/0027_model_version_measurements.sql"


def _module():
    spec = importlib.util.spec_from_file_location("migration_0054", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def scalar(self):
        return self._rows[0][0] if self._rows else None


class Bind:
    """Answers the catalogue and data questions, and records that it was asked."""

    def __init__(self, *, table=None, column=None, fk=None, check=None, unbound=(), bound=(), rows=0):
        self.table = table                      # a MEASUREMENTS_SHAPE row, or None when absent
        self.column = column
        self.fk = fk
        self.check = check
        self.unbound = list(unbound)
        self.bound = list(bound)
        self.rows = rows
        self.asked: list[str] = []

    def exec_driver_sql(self, sql):
        self.asked.append(sql)
        if "pg_class" in sql:
            return _Result([(1,)] if self.table else [])
        if "pg_policy" in sql:
            return _Result([self.table])
        if "information_schema.columns" in sql:
            return _Result([self.column] if self.column else [])
        if "pg_get_constraintdef" in sql:
            return _Result([self.check] if self.check else [])
        if "pg_constraint" in sql:
            return _Result([self.fk] if self.fk else [])
        if "count(*)" in sql:
            return _Result([(self.rows,)])
        if "verified_measurement_id IS NOT NULL" in sql:
            return _Result([(s,) for s in self.bound])
        if "verified_at IS NOT NULL" in sql:
            return _Result([(s,) for s in self.unbound])
        raise AssertionError(f"unexpected question: {sql[:80]}")


class Context:
    def __init__(self, *, as_sql=False):
        self.as_sql = as_sql


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
        lambda name, source, referent, local_cols, remote_cols, **kw: issued.append(
            ("create_foreign_key", name, source, kw.get("referent_schema"), referent, list(local_cols), list(remote_cols))
        ),
    )
    monkeypatch.setattr(alembic_op, "create_check_constraint", lambda name, table, expr: issued.append(("create_check_constraint", name, table, expr)))
    getattr(module, direction)()
    return issued


M = _module()
KERNEL = ("execute", KERNEL_SQL.read_text("utf-8"))
ADD_COLUMN = ("add_column", "model_versions", "verified_measurement_id", "CHAR(30)", True)
ADD_FK = ("create_foreign_key", M.FK, "model_versions", "inv", "model_version_measurements", ["tenant_id", "verified_measurement_id"], ["tenant_id", "measurement_id"])
ADD_CHECK = ("create_check_constraint", M.CHECK, "model_versions", M.CHECK_EXPRESSION)
GRANT = ("execute", "GRANT UPDATE (verified_measurement_id) ON model_versions TO inv_app")

TABLE_OK = (M.EXPECTED_MEASUREMENT_COLUMNS, 1)
COLUMN_OK = ("character", 30, "YES")
FK_OK = M.EXPECTED_FK
CHECK_OK = M.EXPECTED_CHECK
VERSION = "mdv_01J8Z3XQ2K9WMV5T7N4B6C8D0E"


def test_it_sits_on_the_fixed_order_at_the_number_the_coordinator_assigned():
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'revision = "0054_model_version_measurements"' in source
    # 0054 by the coordinator's decision on #209 (card 83): 0053 went to the
    # eval-suite project scope (#202). Pinned so a renumber cannot fork the graph.
    assert 'down_revision = "0053_eval_suite_project_scope"' in source


def test_the_graph_has_one_head_and_it_is_this_revision():
    import subprocess
    import sys

    head = subprocess.run(
        [sys.executable, str(ROOT / "tools/migration_graph.py"), "--head"],
        capture_output=True, text=True, cwd=ROOT,
    )
    assert head.returncode == 0, head.stderr
    assert head.stdout.strip() == "0054_model_version_measurements"


# ---------------------------------------------------------------- the kernel's SQL


def test_the_kernel_sql_is_the_0037_shape_and_the_application_role_may_only_read():
    sql = KERNEL_SQL.read_text("utf-8")
    assert "CREATE TABLE inv.model_version_measurements" in sql
    for column in M.EXPECTED_MEASUREMENT_COLUMNS:
        assert re.search(rf"^\s+{column} ", sql, re.M), column
    assert "PRIMARY KEY (tenant_id, measurement_id)" in sql
    assert "UNIQUE (tenant_id, request_id)" in sql
    assert "ENABLE ROW LEVEL SECURITY" in sql and "FORCE ROW LEVEL SECURITY" in sql
    assert "CREATE POLICY tenant_isolation ON inv.model_version_measurements" in sql
    assert "current_setting('inv.tenant_id', true)" in sql
    assert "REVOKE ALL ON inv.model_version_measurements FROM PUBLIC, inv_app, inv_kernel" in sql
    grants = re.findall(r"^GRANT ([A-Z, ]+) ON inv\.model_version_measurements TO (\w+)", sql, re.M)
    assert sorted(grants) == [("SELECT", "inv_app"), ("SELECT, INSERT", "inv_kernel")]
    assert "UPDATE" not in {g for g, _ in grants} and "DELETE" not in {g for g, _ in grants}
    assert re.search(r"CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON inv\.model_version_measurements\s+FOR EACH ROW EXECUTE FUNCTION inv\.immutable_record\(\)", sql)
    # No key back to public.model_versions (see the file): the binding is the public side's.
    assert "REFERENCES public.model_versions" not in sql


def test_the_migration_wraps_that_file_as_0048_wraps_0026():
    assert M.KERNEL_SQL == "migrations/0027_model_version_measurements.sql"
    assert M._kernel_sql() == KERNEL_SQL.read_text("utf-8")


# ---------------------------------------------------------------- upgrade paths


def test_a_clean_catalogue_gets_the_table_the_column_the_key_the_check_and_the_grant(monkeypatch):
    bind = Bind()
    issued = _run(monkeypatch, bind=bind)
    assert issued == [KERNEL, ADD_COLUMN, ADD_FK, ADD_CHECK, GRANT]
    # The data question came first, in its no-column form.
    assert "verified_at IS NOT NULL" in bind.asked[1] and "pg_class" in bind.asked[2]


def test_offline_rendering_issues_everything_and_asks_nothing(monkeypatch):
    assert _run(monkeypatch, as_sql=True) == [KERNEL, ADD_COLUMN, ADD_FK, ADD_CHECK, GRANT]


def test_a_resume_adds_only_what_is_missing_and_always_reissues_the_grant(monkeypatch):
    assert _run(monkeypatch, bind=Bind(table=TABLE_OK)) == [ADD_COLUMN, ADD_FK, ADD_CHECK, GRANT]
    assert _run(monkeypatch, bind=Bind(table=TABLE_OK, column=COLUMN_OK)) == [ADD_FK, ADD_CHECK, GRANT]
    assert _run(monkeypatch, bind=Bind(table=TABLE_OK, column=COLUMN_OK, fk=FK_OK)) == [ADD_CHECK, GRANT]
    assert _run(monkeypatch, bind=Bind(table=TABLE_OK, column=COLUMN_OK, fk=FK_OK, check=CHECK_OK)) == [GRANT]


def test_a_resume_does_not_rerun_the_kernel_sql_when_the_table_is_right(monkeypatch):
    issued = _run(monkeypatch, bind=Bind(table=TABLE_OK, column=COLUMN_OK, fk=FK_OK, check=CHECK_OK))
    assert KERNEL not in issued                  # CREATE TABLE is not idempotent


def test_a_verified_version_nothing_can_bind_stops_the_run_before_any_ddl(monkeypatch):
    for bind in (Bind(unbound=[VERSION]), Bind(column=COLUMN_OK, table=TABLE_OK, unbound=[VERSION])):
        with pytest.raises(RuntimeError) as raised:
            _run(monkeypatch, bind=bind)
        assert VERSION in str(raised.value) and "reviewed data fix" in str(raised.value)
        assert not any("pg_class" in q for q in bind.asked)     # refused before the catalogue was even read


@pytest.mark.parametrize(
    "table",
    [
        (sorted(set(M.EXPECTED_MEASUREMENT_COLUMNS) - {"certificate_sha256"}), 1),   # a column short
        (sorted(M.EXPECTED_MEASUREMENT_COLUMNS + ["extra"]), 1),                    # a column over
        (M.EXPECTED_MEASUREMENT_COLUMNS, 0),                                        # no tenant policy
    ],
    ids=["missing-column", "extra-column", "no-policy"],
)
def test_a_table_of_that_name_with_a_different_shape_is_refused(monkeypatch, table):
    with pytest.raises(RuntimeError) as raised:
        _run(monkeypatch, bind=Bind(table=table))
    assert "different definition" in str(raised.value)


@pytest.mark.parametrize(
    "column",
    [("character varying", 30, "YES"), ("character", 64, "YES"), ("character", 30, "NO")],
    ids=["type", "width", "not-null"],
)
def test_a_column_of_that_name_with_a_different_shape_is_refused(monkeypatch, column):
    with pytest.raises(RuntimeError) as raised:
        _run(monkeypatch, bind=Bind(table=TABLE_OK, column=column))
    assert "different definition" in str(raised.value)


def _fk(**overrides):
    fields = ["contype", "referenced", "columns", "referenced_columns", "on_update", "on_delete", "match_type", "deferrable", "initially_deferred", "validated"]
    values = dict(zip(fields, FK_OK))
    values.update(overrides)
    return tuple(values[f] for f in fields)


@pytest.mark.parametrize(
    "fk",
    [
        _fk(referenced="inv.storage_sample_requests"),
        _fk(columns=["verified_measurement_id"], referenced_columns=["measurement_id"]),   # not tenant-composite
        _fk(contype="u"),
        _fk(on_delete="c"),                      # ON DELETE CASCADE would let a measurement drop take the version
        _fk(on_delete="n"),                      # ON DELETE SET NULL would silently un-verify
        _fk(match_type="f"),                     # MATCH FULL refuses (tenant_id, NULL), the unverified row
        _fk(deferrable=True),
        _fk(validated=False),
    ],
    ids=["table", "columns", "type", "cascade", "set-null", "match-full", "deferrable", "not-validated"],
)
def test_a_key_of_that_name_with_a_different_shape_is_refused(monkeypatch, fk):
    with pytest.raises(RuntimeError) as raised:
        _run(monkeypatch, bind=Bind(table=TABLE_OK, column=COLUMN_OK, fk=fk))
    assert "different definition" in str(raised.value)


@pytest.mark.parametrize(
    "check",
    [
        ("c", "CHECK ((verified_at IS NULL))", True),
        ("c", "CHECK (((verified_at IS NULL) OR (verified_measurement_id IS NULL)))", True),
        ("c", CHECK_OK[1], False),
    ],
    ids=["one-sided", "or-not-iff", "not-validated"],
)
def test_a_check_of_that_name_with_a_different_expression_is_refused(monkeypatch, check):
    with pytest.raises(RuntimeError) as raised:
        _run(monkeypatch, bind=Bind(table=TABLE_OK, column=COLUMN_OK, fk=FK_OK, check=check))
    assert "different definition" in str(raised.value)


# ---------------------------------------------------------------- downgrade


def test_a_downgrade_with_nothing_bound_and_no_measurement_drops_everything(monkeypatch):
    issued = _run(monkeypatch, bind=Bind(table=TABLE_OK, column=COLUMN_OK), direction="downgrade")
    assert [s for kind, s in issued if kind == "execute"] == [
        f"ALTER TABLE public.model_versions DROP CONSTRAINT IF EXISTS {M.CHECK}",
        f"ALTER TABLE public.model_versions DROP CONSTRAINT IF EXISTS {M.FK}",
        "ALTER TABLE public.model_versions DROP COLUMN IF EXISTS verified_measurement_id",
        "DROP TABLE IF EXISTS inv.model_version_measurements",
    ]


def test_a_downgrade_refuses_while_a_version_is_bound_to_a_measurement(monkeypatch):
    with pytest.raises(RuntimeError) as raised:
        _run(monkeypatch, bind=Bind(table=TABLE_OK, column=COLUMN_OK, bound=[VERSION]), direction="downgrade")
    assert "discard" in str(raised.value) and VERSION in str(raised.value)


def test_a_downgrade_refuses_while_any_measurement_row_exists(monkeypatch):
    with pytest.raises(RuntimeError) as raised:
        _run(monkeypatch, bind=Bind(table=TABLE_OK, column=COLUMN_OK, rows=3), direction="downgrade")
    assert "3 measurement row(s)" in str(raised.value) and "discard" in str(raised.value)


# ---------------------------------------------------------------- the model and the service


def test_the_model_declares_the_column_the_check_and_the_lifecycle_grant():
    from saintvision.db.models import LIFECYCLE_UPDATE_COLUMNS, ModelVersion

    column = ModelVersion.__table__.columns["verified_measurement_id"]
    assert column.nullable is True and str(column.type) == "CHAR(30)"
    from sqlalchemy import CheckConstraint

    checks = {c.name: str(c.sqltext) for c in ModelVersion.__table__.constraints if isinstance(c, CheckConstraint)}
    assert checks[M.CHECK] == M.CHECK_EXPRESSION
    assert "verified_measurement_id" in LIFECYCLE_UPDATE_COLUMNS["model_versions"]


def test_the_measurement_id_kind_is_registered():
    from saintvision.ids import is_id, new_id

    assert is_id(new_id("model_measurement"), "model_measurement")


def test_verify_model_version_requires_a_measurement_and_a_digest_alone_cannot_call_it():
    from saintvision.services.lineage import verify_model_version

    parameters = inspect.signature(verify_model_version).parameters
    measurement = parameters["measurement_id"]
    assert measurement.kind is inspect.Parameter.KEYWORD_ONLY
    assert measurement.default is inspect.Parameter.empty      # no default: the digest-only form is a TypeError


def _calls(source: str):
    """Every ``verify_model_version(`` call in ``source`` with its argument text."""
    for match in re.finditer(r"verify_model_version\(", source):
        if source[max(0, match.start() - 4):match.start()].endswith("def "):
            continue
        depth, index = 1, match.end()
        while depth:
            depth += {"(": 1, ")": -1}.get(source[index], 0)
            index += 1
        yield source[match.end():index - 1]


def test_no_call_site_anywhere_passes_a_digest_without_a_measurement():
    """Design #209 v1.1 §4: the digest-only call path count is zero, by grep."""
    seen = 0
    for path in list((ROOT / "src").rglob("*.py")) + list((ROOT / "tests").rglob("*.py")):
        if path == Path(__file__).resolve():
            continue
        for arguments in _calls(path.read_text(encoding="utf-8")):
            seen += 1
            assert "measurement_id=" in arguments, f"{path.relative_to(ROOT)}: {arguments[:120]}"
    assert seen >= 3                                             # the service's own test helpers at least
