"""0054 without a server: what the migration asks, issues and refuses.

The migration is loaded from its file and run against a stand-in connection
that answers the catalogue and data questions and records every operation.
What is fixed here is the shape of the decision, not PostgreSQL's behaviour:
a clean catalogue gets the kernel table, the reader, the column, the key, the
CHECK and the grants in that order; a resume adds only what is missing; a
same-named kernel table whose *security or constraint shape* differs in any
part (Codex #213 F1) stops the run before the public side is touched; a
verified version nothing can bind stops it before any DDL; the downgrade
refuses while evidence exists. The real database is
``tests/integration/test_model_version_measurements_real_pg.py``.

Design #209 v1.1 §4 also asks for properties of the code, not the database:
``verify_model_version`` cannot be called with a digest alone, no call site
anywhere does, and the reader's pinned policy hash is the hash of what this
revision creates. All are tests here.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import inspect
import json
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


M = _module()


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def scalar(self):
        return self._rows[0][0] if self._rows else None


def _rows_for(shape: dict) -> dict:
    """Catalogue rows that ``kernel_shape`` would read back as ``shape``."""
    return {
        "columns": [(n, t, nn) for n, t, nn in shape["columns"]],
        "constraints": [(t, d) for t, d in shape["constraints"]],
        "indexes": [(d,) for d in shape["indexes"]],
        "rls": list(shape["rls"]),
        "policies": [(n, c, p, r, q, w) for n, c, p, r, q, w in shape["policies"]],
        "privileges": list(shape["privileges"]),
        "triggers": list(shape["triggers"]),
        "owner": list(shape["owner"]),
    }


def kernel_rows(**overrides) -> dict:
    """The expected shape's rows, with one part replaced."""
    shape = copy.deepcopy(M.EXPECTED_KERNEL_SHAPE)
    shape.update(overrides)
    return _rows_for(shape)


class Bind:
    """Answers the catalogue and data questions, and records that it was asked."""

    def __init__(self, *, table=None, reader=None, reader_owner=None, column=None, fk=None, check=None, unbound=(), bound=(), rows=0):
        self.table = table                      # kernel_rows(...) when present, None when absent
        self.reader = reader                    # the reader's rendered definition, or None
        self.reader_owner = reader_owner if reader_owner is not None else list(M.EXPECTED_READER_OWNER)
        self.column = column
        self.fk = fk
        self.check = check
        self.unbound = list(unbound)
        self.bound = list(bound)
        self.rows = rows
        self.asked: list[str] = []

    def exec_driver_sql(self, sql):
        self.asked.append(sql)
        marker = re.search(r"/\* shape:([\w-]+) \*/", sql)
        if marker:
            part = marker.group(1)
            if part == "reader":
                return _Result([(self.reader,)] if self.reader else [])
            if part == "reader-owner":
                return _Result(self.reader_owner)
            assert self.table is not None, "the shape is asked only when the table is present"
            return _Result(self.table[part])
        if "pg_class" in sql:
            return _Result([(1,)] if self.table is not None else [])
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
    monkeypatch.setattr(alembic_op, "create_check_constraint", lambda name, table, expr: issued.append(("create_check_constraint", str(name), table, expr)))
    monkeypatch.setattr(alembic_op, "f", lambda name: f"f:{name}")
    getattr(module, direction)()
    return issued


KERNEL = ("execute", KERNEL_SQL.read_text("utf-8"))
READER = ("execute", M.READER_DDL)
ADD_COLUMN = ("add_column", "model_versions", "verified_measurement_id", "CHAR(30)", True)
ADD_FK = ("create_foreign_key", M.FK, "model_versions", "inv", "model_version_measurements", ["tenant_id", "verified_measurement_id"], ["tenant_id", "measurement_id"])
ADD_CHECK = ("create_check_constraint", f"f:{M.CHECK}", "model_versions", M.CHECK_EXPRESSION)
GRANTS = [("execute", "GRANT UPDATE (verified_measurement_id) ON model_versions TO inv_app")] + [("execute", s) for s in M.READER_GRANTS]

TABLE_OK = kernel_rows()
READER_OK = M.reader_definition()
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


# ---------------------------------------------------------------- the kernel's SQL and the reader


def test_the_kernel_sql_is_the_0037_shape_and_the_application_role_has_no_privilege_on_it():
    sql = KERNEL_SQL.read_text("utf-8")
    assert "CREATE TABLE inv.model_version_measurements" in sql
    for column, _type, _notnull in M.EXPECTED_KERNEL_SHAPE["columns"]:
        assert re.search(rf"^\s+{column} ", sql, re.M), column
    assert "PRIMARY KEY (tenant_id, measurement_id)" in sql
    assert "UNIQUE (tenant_id, request_id)" in sql
    assert "ENABLE ROW LEVEL SECURITY" in sql and "FORCE ROW LEVEL SECURITY" in sql
    assert "CREATE POLICY tenant_isolation ON inv.model_version_measurements" in sql
    assert "current_setting('inv.tenant_id', true)" in sql
    assert "REVOKE ALL ON inv.model_version_measurements FROM PUBLIC, inv_app, inv_kernel" in sql
    grants = re.findall(r"^GRANT ([A-Z, ]+) ON inv\.model_version_measurements TO (\w+)", sql, re.M)
    assert grants == [("SELECT, INSERT", "inv_kernel")]          # nothing for inv_app, nothing for PUBLIC
    assert re.search(r"CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON inv\.model_version_measurements\s+FOR EACH ROW EXECUTE FUNCTION inv\.immutable_record\(\)", sql)
    assert "REFERENCES public.model_versions" not in sql


def _checks_in(sql: str) -> set[str]:
    """Every CHECK, PRIMARY KEY and UNIQUE the kernel SQL declares, normalised
    the way PostgreSQL renders them back (LIKE is ``~~``; BETWEEN is the two
    comparisons)."""
    found: set[str] = set()
    body = sql[sql.index("CREATE TABLE inv.model_version_measurements"):sql.index("\n);")]   # the table, not the policy
    for line in body.splitlines():
        for keyword in ("CHECK (", "PRIMARY KEY (", "UNIQUE ("):
            start = line.find(keyword)
            if start < 0:
                continue
            expression = line[start:].rstrip().rstrip(",")
            expression = expression.replace(" LIKE ", " ~~ ")
            expression = re.sub(r"(\w+\([^()]*\)|\w+) BETWEEN (\d+) AND (\d+)", r"(\1 >= \2) AND (\1 <= \3)", expression)
            found.add(M.normalise(expression))
    return found


def test_every_constraint_in_the_kernel_sql_is_expected_and_nothing_else_is():
    """Codex #213 R2: the expected set is read against the SQL that creates
    the table, independently of the stand-in that echoes the expectation
    back. A CHECK in one and not the other (channel_version was) fails here."""
    declared = _checks_in(KERNEL_SQL.read_text("utf-8"))
    expected = {definition for _type, definition in M.EXPECTED_KERNEL_SHAPE["constraints"]}
    assert declared == expected, {"only in sql": declared - expected, "only expected": expected - declared}
    assert len(M.EXPECTED_KERNEL_SHAPE["constraints"]) == len(declared) == 14


def test_the_migration_wraps_that_file_as_0048_wraps_0026():
    assert M.KERNEL_SQL == "migrations/0027_model_version_measurements.sql"
    assert M._kernel_sql() == KERNEL_SQL.read_text("utf-8")


def test_the_reader_is_tenant_bound_pinned_and_executable_by_the_application_only():
    ddl = M.READER_DDL
    assert "SECURITY DEFINER" in ddl and "SET search_path = pg_catalog" in ddl
    assert "current_setting('inv.tenant_id', true)" in M.READER_BODY
    assert "p_tenant" not in ddl                                     # the tenant is never an argument
    assert "FROM inv.model_version_measurements m" in M.READER_BODY  # schema-qualified, the only table it touches
    assert M.READER_GRANTS == (
        "REVOKE ALL ON FUNCTION public.model_version_measurement(text) FROM PUBLIC",
        "GRANT EXECUTE ON FUNCTION public.model_version_measurement(text) TO inv_app",
    )
    # The DDL body and the rendered definition are the same bytes, so the
    # policy hash cannot describe something other than what is created.
    assert M.READER_BODY in ddl and M.READER_BODY in M.reader_definition()


def test_the_definer_policy_pins_exactly_this_revisions_reader():
    policy = json.loads((ROOT / "tools/definer-policy.json").read_text(encoding="utf-8"))
    entry = policy["functions"]["public.model_version_measurement(text)"]
    assert entry["definitionSHA256"] == M.reader_definition_sha256() == hashlib.sha256(M.reader_definition().encode()).hexdigest()
    assert entry["executeRoles"] == ["inv_app"] and entry["kind"] == "tenant-bound"
    assert policy["revision"] == "0054_model_version_measurements"


def test_the_rendered_definition_follows_the_shape_postgresql_uses_for_0044():
    """The renderer is the one that reproduces 0044's pinned hash from its DDL
    (verified against the policy entry): the same header lines, the body
    verbatim between ``$function$`` quotes, one trailing newline."""
    rendered = M.reader_definition()
    assert rendered.startswith("CREATE OR REPLACE FUNCTION public.model_version_measurement(p_measurement_id text)\n RETURNS TABLE(")
    assert "\n LANGUAGE plpgsql\n SECURITY DEFINER\n SET search_path TO 'pg_catalog'\nAS $function$" in rendered
    assert rendered.endswith("$function$\n")


# ---------------------------------------------------------------- upgrade paths


def test_a_clean_catalogue_gets_everything_in_order(monkeypatch):
    bind = Bind()
    issued = _run(monkeypatch, bind=bind)
    assert issued == [KERNEL, READER, ADD_COLUMN, ADD_FK, ADD_CHECK, *GRANTS]
    # The data question came first, in its no-column form.
    assert "verified_at IS NOT NULL" in bind.asked[1] and "pg_class" in bind.asked[2]


def test_offline_rendering_issues_everything_and_asks_nothing(monkeypatch):
    assert _run(monkeypatch, as_sql=True) == [KERNEL, READER, ADD_COLUMN, ADD_FK, ADD_CHECK, *GRANTS]


def test_the_check_name_is_final_so_the_naming_convention_is_not_applied_twice(monkeypatch):
    """Hosted CI on 348e2403: ``ck_model_versions_ck_model_versions_...`` --
    Alembic applied the metadata convention to the explicit name, and the
    resume then could not find its own constraint."""
    issued = _run(monkeypatch, bind=Bind())
    assert ("create_check_constraint", f"f:{M.CHECK}", "model_versions", M.CHECK_EXPRESSION) in issued
    assert "op.f(CHECK)" in MIGRATION.read_text(encoding="utf-8")


def test_a_resume_adds_only_what_is_missing_and_always_reissues_the_grants(monkeypatch):
    assert _run(monkeypatch, bind=Bind(table=TABLE_OK)) == [READER, ADD_COLUMN, ADD_FK, ADD_CHECK, *GRANTS]
    assert _run(monkeypatch, bind=Bind(table=TABLE_OK, reader=READER_OK)) == [ADD_COLUMN, ADD_FK, ADD_CHECK, *GRANTS]
    assert _run(monkeypatch, bind=Bind(table=TABLE_OK, reader=READER_OK, column=COLUMN_OK)) == [ADD_FK, ADD_CHECK, *GRANTS]
    assert _run(monkeypatch, bind=Bind(table=TABLE_OK, reader=READER_OK, column=COLUMN_OK, fk=FK_OK)) == [ADD_CHECK, *GRANTS]
    assert _run(monkeypatch, bind=Bind(table=TABLE_OK, reader=READER_OK, column=COLUMN_OK, fk=FK_OK, check=CHECK_OK)) == GRANTS


def test_a_resume_does_not_rerun_the_kernel_sql_when_the_table_is_whole(monkeypatch):
    issued = _run(monkeypatch, bind=Bind(table=TABLE_OK, reader=READER_OK, column=COLUMN_OK, fk=FK_OK, check=CHECK_OK))
    assert KERNEL not in issued                  # CREATE TABLE is not idempotent


def test_a_verified_version_nothing_can_bind_stops_the_run_before_any_ddl(monkeypatch):
    for bind in (Bind(unbound=[VERSION]), Bind(column=COLUMN_OK, table=TABLE_OK, unbound=[VERSION])):
        with pytest.raises(RuntimeError) as raised:
            _run(monkeypatch, bind=bind)
        assert VERSION in str(raised.value) and "reviewed data fix" in str(raised.value)
        assert not any("pg_class" in q for q in bind.asked)     # refused before the catalogue was even read


# ---------------------------------------------------------------- the kernel table's whole shape (Codex #213 F1)


def _without(part_rows, predicate):
    return [row for row in part_rows if not predicate(row)]


TAMPERED = {
    # (a) row security switched off, or no longer forced on the owner
    "rls-disabled": kernel_rows(rls=[(False, True)]),
    "rls-not-forced": kernel_rows(rls=[(True, False)]),
    # (b) the same policy name, letting everything through
    "policy-using-true": kernel_rows(policies=[("tenant_isolation", "*", True, ["public"], "true", "true")]),
    "policy-check-true": kernel_rows(policies=[("tenant_isolation", "*", True, ["public"], M.normalise(M.TENANT_PREDICATE), "true")]),
    "policy-select-only": kernel_rows(policies=[("tenant_isolation", "r", True, ["public"], M.normalise(M.TENANT_PREDICATE), M.normalise(M.TENANT_PREDICATE))]),
    "policy-restrictive": kernel_rows(policies=[("tenant_isolation", "*", False, ["public"], M.normalise(M.TENANT_PREDICATE), M.normalise(M.TENANT_PREDICATE))]),
    "policy-role-narrowed": kernel_rows(policies=[("tenant_isolation", "*", True, ["inv_kernel"], M.normalise(M.TENANT_PREDICATE), M.normalise(M.TENANT_PREDICATE))]),
    "policy-missing": kernel_rows(policies=[]),
    "second-policy": kernel_rows(policies=M.EXPECTED_KERNEL_SHAPE["policies"] + [("open", "*", True, ["public"], "true", "true")]),
    # (c) the immutable trigger gone, disabled, or pointing elsewhere
    "trigger-missing": kernel_rows(triggers=[]),
    "trigger-disabled": kernel_rows(triggers=[("immutable", "D", "inv", "immutable_record", 27)]),
    "trigger-other-function": kernel_rows(triggers=[("immutable", "O", "public", "immutable_record", 27)]),
    "trigger-update-only": kernel_rows(triggers=[("immutable", "O", "inv", "immutable_record", 19)]),
    # (d) a write grant for the application, or anything for PUBLIC
    "app-insert": kernel_rows(privileges=sorted(M.EXPECTED_KERNEL_SHAPE["privileges"] + [("inv_app", "INSERT")])),
    "app-select": kernel_rows(privileges=sorted(M.EXPECTED_KERNEL_SHAPE["privileges"] + [("inv_app", "SELECT")])),
    "public-select": kernel_rows(privileges=sorted(M.EXPECTED_KERNEL_SHAPE["privileges"] + [("public", "SELECT")])),
    "kernel-update": kernel_rows(privileges=sorted(M.EXPECTED_KERNEL_SHAPE["privileges"] + [("inv_kernel", "UPDATE")])),
    "kernel-delete": kernel_rows(privileges=sorted(M.EXPECTED_KERNEL_SHAPE["privileges"] + [("inv_kernel", "DELETE")])),
    "no-acl": kernel_rows(privileges=[]),
    # (e) keys, indexes, columns and checks
    "no-request-unique": kernel_rows(constraints=_without(M.EXPECTED_KERNEL_SHAPE["constraints"], lambda r: r[0] == "u")),
    "no-primary-key": kernel_rows(constraints=_without(M.EXPECTED_KERNEL_SHAPE["constraints"], lambda r: r[0] == "p")),
    "digest-check-gone": kernel_rows(constraints=_without(M.EXPECTED_KERNEL_SHAPE["constraints"], lambda r: "sha256~" in r[1] and r[1].startswith("checksha256"))),
    "digest-check-loosened": kernel_rows(constraints=sorted(
        [r for r in M.EXPECTED_KERNEL_SHAPE["constraints"] if not r[1].startswith("checksha256")] + [("c", M.normalise("CHECK (sha256 ~ '^[0-9a-f]+$')"))]
    )),
    "byte-size-integer": kernel_rows(columns=[(n, "integer" if n == "byte_size" else t, nn) for n, t, nn in M.EXPECTED_KERNEL_SHAPE["columns"]]),
    "digest-nullable": kernel_rows(columns=[(n, t, False if n == "sha256" else nn) for n, t, nn in M.EXPECTED_KERNEL_SHAPE["columns"]]),
    "column-missing": kernel_rows(columns=[c for c in M.EXPECTED_KERNEL_SHAPE["columns"] if c[0] != "certificate_sha256"]),
    "column-extra": kernel_rows(columns=M.EXPECTED_KERNEL_SHAPE["columns"] + [("note", "text", False)]),
    "columns-reordered": kernel_rows(columns=list(reversed(M.EXPECTED_KERNEL_SHAPE["columns"]))),
    "index-missing": kernel_rows(indexes=[i for i in M.EXPECTED_KERNEL_SHAPE["indexes"] if "by_version" not in i]),
    "unique-index-demoted": kernel_rows(indexes=sorted(
        i.replace("createuniqueindexmodel_version_measurements_tenant_id_request_id_key", "createindexmodel_version_measurements_tenant_id_request_id_key")
        for i in M.EXPECTED_KERNEL_SHAPE["indexes"]
    )),
    # (f) the owner (Codex #213 R2): a runtime role owning the table, or able to assume its owner
    "owner-app": kernel_rows(owner=[(False, True, False)]),
    "owner-kernel": kernel_rows(owner=[(False, False, True)]),
    "app-member-of-owner": kernel_rows(owner=[(True, True, False)]),
    "kernel-member-of-owner": kernel_rows(owner=[(True, False, True)]),
}


@pytest.mark.parametrize("case", sorted(TAMPERED), ids=sorted(TAMPERED))
def test_a_table_of_that_name_whose_security_or_constraint_shape_differs_is_refused_before_the_public_side(monkeypatch, case):
    bind = Bind(table=TAMPERED[case], reader=READER_OK, column=None)
    with pytest.raises(RuntimeError) as raised:
        _run(monkeypatch, bind=bind)
    assert "different definition" in str(raised.value) and "inv.model_version_measurements" in str(raised.value)
    # Refused before the reader, the key or the CHECK were even asked about
    # (the column question before it is the data check, which comes first).
    assert not any("shape:reader" in q or M.FK in q or M.CHECK in q for q in bind.asked)


def test_every_part_of_the_shape_is_compared_and_the_stand_in_rows_reproduce_the_expected_shape():
    assert set(M.KERNEL_SHAPE_QUERIES) == set(M.EXPECTED_KERNEL_SHAPE) == {
        "columns", "constraints", "indexes", "rls", "policies", "privileges", "triggers", "owner",
    }
    assert M._shape_from(kernel_rows()) == M.EXPECTED_KERNEL_SHAPE
    for part, sql in M.KERNEL_SHAPE_QUERIES.items():
        assert f"/* shape:{part} */" in sql


def test_the_normaliser_ignores_rendering_and_keeps_meaning():
    n = M.normalise
    assert n("CHECK (((sha256)::text ~ '^[0-9a-f]{64}$'::text))") == n("CHECK (sha256 ~ '^[0-9a-f]{64}$')")
    assert n("CHECK ((duration_seconds >= (0)::double precision))") == n("CHECK (duration_seconds >= 0)")
    assert n("(tenant_id = (NULLIF(current_setting('inv.tenant_id'::text, true), ''::text))::uuid)") == n(M.TENANT_PREDICATE)
    assert n("CHECK (sha256 ~ '^[0-9a-f]{64}$')") != n("CHECK (sha256 ~ '^[0-9a-f]+$')")
    assert n("true") != n(M.TENANT_PREDICATE)
    assert n("CHECK (byte_size >= 0)") != n("CHECK (byte_size >= 1)")


@pytest.mark.parametrize("owner", [[(False, True, False)], [(True, True, False)], [(True, False, True)], []], ids=["owned-by-app", "app-member", "kernel-member", "absent"])
def test_a_reader_whose_owner_is_or_admits_a_runtime_role_is_refused(monkeypatch, owner):
    with pytest.raises(RuntimeError) as raised:
        _run(monkeypatch, bind=Bind(table=TABLE_OK, reader=READER_OK, reader_owner=owner))
    assert "model_version_measurement(text) (owner)" in str(raised.value)


def test_a_reader_of_that_name_with_a_different_definition_is_refused(monkeypatch):
    other = M.reader_definition().replace("m.measurement_id = p_measurement_id", "true")
    with pytest.raises(RuntimeError) as raised:
        _run(monkeypatch, bind=Bind(table=TABLE_OK, reader=other))
    assert "public.model_version_measurement(text)" in str(raised.value)


@pytest.mark.parametrize(
    "column",
    [("character varying", 30, "YES"), ("character", 64, "YES"), ("character", 30, "NO")],
    ids=["type", "width", "not-null"],
)
def test_a_column_of_that_name_with_a_different_shape_is_refused(monkeypatch, column):
    with pytest.raises(RuntimeError) as raised:
        _run(monkeypatch, bind=Bind(table=TABLE_OK, reader=READER_OK, column=column))
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
        _fk(on_delete="c"),
        _fk(on_delete="n"),
        _fk(match_type="f"),
        _fk(deferrable=True),
        _fk(validated=False),
    ],
    ids=["table", "columns", "type", "cascade", "set-null", "match-full", "deferrable", "not-validated"],
)
def test_a_key_of_that_name_with_a_different_shape_is_refused(monkeypatch, fk):
    with pytest.raises(RuntimeError) as raised:
        _run(monkeypatch, bind=Bind(table=TABLE_OK, reader=READER_OK, column=COLUMN_OK, fk=fk))
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
        _run(monkeypatch, bind=Bind(table=TABLE_OK, reader=READER_OK, column=COLUMN_OK, fk=FK_OK, check=check))
    assert "different definition" in str(raised.value)


# ---------------------------------------------------------------- downgrade


def test_a_downgrade_with_nothing_bound_and_no_measurement_drops_everything(monkeypatch):
    issued = _run(monkeypatch, bind=Bind(table=TABLE_OK, column=COLUMN_OK), direction="downgrade")
    assert [s for kind, s in issued if kind == "execute"] == [
        f"ALTER TABLE public.model_versions DROP CONSTRAINT IF EXISTS {M.CHECK}",
        f"ALTER TABLE public.model_versions DROP CONSTRAINT IF EXISTS {M.FK}",
        "ALTER TABLE public.model_versions DROP COLUMN IF EXISTS verified_measurement_id",
        "DROP FUNCTION IF EXISTS public.model_version_measurement(text)",
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
    from sqlalchemy import CheckConstraint

    from saintvision.db.models import LIFECYCLE_UPDATE_COLUMNS, ModelVersion

    column = ModelVersion.__table__.columns["verified_measurement_id"]
    assert column.nullable is True and str(column.type) == "CHAR(30)"
    checks = {c.name: str(c.sqltext) for c in ModelVersion.__table__.constraints if isinstance(c, CheckConstraint)}
    assert checks[M.CHECK] == M.CHECK_EXPRESSION
    assert "verified_measurement_id" in LIFECYCLE_UPDATE_COLUMNS["model_versions"]


def test_the_measurement_id_kind_is_registered():
    from saintvision.ids import is_id, new_id

    assert is_id(new_id("model_measurement"), "model_measurement")


def test_the_service_reads_through_the_reader_and_compares_the_size_with_no_sentinel():
    from saintvision.services import lineage

    assert "FROM public.model_version_measurement(:measurement_id)" in str(lineage._MEASUREMENT)
    assert "inv.model_version_measurements" not in str(lineage._MEASUREMENT)
    source = inspect.getsource(lineage.verify_model_version)
    assert "int(measurement.byte_size) != int(row.byte_size)" in source
    assert "row.byte_size and" not in source                          # Codex #213 F2: 0 is a size, not "unknown"


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
