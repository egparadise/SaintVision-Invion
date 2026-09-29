"""Owner-only corruption helpers and a database integrity audit for real-PG tests.

Negative tests must sometimes build a physically impossible state as the disposable
database owner (suspend a trigger, insert an orphan, corrupt a stored row) to prove
that the *serving* code refuses it.  Those tests were leaving the corruption behind:
PR #126 showed that ``tests/integration/test_postgres.py``'s invalid-EvidenceEnvelope
case left ``inv.result_commitments`` rows without their ``inv.execution_attempts``
parent, so any later ``pg_restore`` of the shared session database failed on the
foreign key and 14 recovery-drill cases failed for reasons unrelated to recovery.

Two rules restore order independence without weakening a single negative assertion:

* ``suspended_triggers`` re-enables what it disabled in ``finally``;
* ``preserved_rows`` snapshots the rows a test is about to corrupt (or the absence of
  rows it is about to insert) and puts exactly that state back when the test ends,
  with triggers suspended for the restore only, so the corruption is visible to the
  serving code *during* the test and gone *after* it.

``database_integrity_violations`` is the fail-closed audit that the session fixtures
run before dropping a disposable database: every validated foreign key must have no
orphan, every validated CHECK constraint must hold for every row, and no trigger may
be left disabled.  It refuses to run under a role that RLS could silence, because a
row the auditor cannot see is not a row that is known to be clean.
"""

from __future__ import annotations

from contextlib import contextmanager
import re
from typing import Any, Iterator, Sequence

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

_QUALIFIED_TABLE = re.compile(r"^[a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*$")
_TRIGGER_SPEC = re.compile(r"^(?:ALL|USER|[a-z_][a-z0-9_]*)$")
AUDITED_SCHEMAS = ("inv", "public")


def _table(name: str) -> sql.Composed:
    if not _QUALIFIED_TABLE.fullmatch(name):
        raise ValueError(f"table must be schema.table in lowercase: {name!r}")
    schema, table = name.split(".")
    return sql.SQL(".").join((sql.Identifier(schema), sql.Identifier(table)))


@contextmanager
def suspended_triggers(conn: psycopg.Connection, table: str, which: str = "USER") -> Iterator[None]:
    """``ALTER TABLE .. DISABLE TRIGGER <which>`` with the matching ENABLE guaranteed in ``finally``."""
    if not _TRIGGER_SPEC.fullmatch(which):
        raise ValueError(f"trigger spec must be ALL, USER or a trigger name: {which!r}")
    spec = sql.SQL(which) if which in ("ALL", "USER") else sql.Identifier(which)
    conn.execute(sql.SQL("ALTER TABLE {} DISABLE TRIGGER {}").format(_table(table), spec))
    try:
        yield
    finally:
        conn.execute(sql.SQL("ALTER TABLE {} ENABLE TRIGGER {}").format(_table(table), spec))


RowTarget = tuple[str, str, Sequence[Any]]  # (schema.table, WHERE predicate with %s, params)


def snapshot_rows(conn: psycopg.Connection, targets: Sequence[RowTarget]) -> list[tuple[RowTarget, list[dict]]]:
    captured = []
    for table, where, params in targets:
        rows = conn.execute(
            sql.SQL("SELECT to_jsonb(t) FROM {} t WHERE ").format(_table(table)) + sql.SQL(where), params
        ).fetchall()
        captured.append(((table, where, tuple(params)), [row[0] for row in rows]))
    return captured


def restore_rows(conn: psycopg.Connection, captured: Sequence[tuple[RowTarget, list[dict]]]) -> None:
    """Delete whatever now matches each target and re-insert the captured rows verbatim.

    Runs with ALL triggers suspended on the target table (foreign-key and immutability
    triggers included) so the original state comes back regardless of what the test did
    in between, and in reverse capture order so parents are restored after children are
    removed and before children are re-inserted.
    """
    for (table, where, params), rows in reversed(list(captured)):
        with suspended_triggers(conn, table, "ALL"):
            conn.execute(sql.SQL("DELETE FROM {} WHERE ").format(_table(table)) + sql.SQL(where), params)
            for row in rows:
                conn.execute(
                    sql.SQL("INSERT INTO {0} SELECT * FROM jsonb_populate_record(NULL::{0}, %s)").format(_table(table)),
                    (Jsonb(row),),
                )


@contextmanager
def preserved_rows(owner_dsn: str, *targets: RowTarget) -> Iterator[None]:
    """Guarantee that the rows matching ``targets`` are identical before and after the block.

    Use it around a whole negative test: corrupt as the owner inside the block, exercise the
    serving code, assert the refusal, and let the exit restore the database.  Targets that
    match nothing before the block (synthetic orphans) are simply deleted afterwards.
    """
    with psycopg.connect(owner_dsn) as conn:
        captured = snapshot_rows(conn, targets)
        conn.rollback()
    try:
        yield
    finally:
        with psycopg.connect(owner_dsn) as conn:
            restore_rows(conn, captured)


_FOREIGN_KEYS = """
SELECT c.conname, c.conrelid::regclass::text, c.confrelid::regclass::text,
       ARRAY(SELECT a.attname FROM unnest(c.conkey) WITH ORDINALITY k(attnum, ord)
             JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum ORDER BY k.ord),
       ARRAY(SELECT a.attname FROM unnest(c.confkey) WITH ORDINALITY k(attnum, ord)
             JOIN pg_attribute a ON a.attrelid = c.confrelid AND a.attnum = k.attnum ORDER BY k.ord)
FROM pg_constraint c JOIN pg_namespace n ON n.oid = c.connamespace
WHERE c.contype = 'f' AND c.convalidated AND n.nspname = ANY(%s)
ORDER BY 2, 1
"""
_CHECKS = """
SELECT c.conname, c.conrelid::regclass::text, pg_get_constraintdef(c.oid)
FROM pg_constraint c JOIN pg_namespace n ON n.oid = c.connamespace
WHERE c.contype = 'c' AND c.convalidated AND c.conrelid <> 0 AND n.nspname = ANY(%s)
ORDER BY 2, 1
"""
_DISABLED_TRIGGERS = """
SELECT t.tgrelid::regclass::text, t.tgname
FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE t.tgenabled = 'D' AND n.nspname = ANY(%s)
ORDER BY 1, 2
"""


def orphan_query(child: str, parent: str, child_cols: Sequence[str], parent_cols: Sequence[str]) -> sql.Composed:
    """MATCH SIMPLE semantics: a child row is judged only when every key column is non-null."""
    not_null = sql.SQL(" AND ").join(sql.SQL("c.{} IS NOT NULL").format(sql.Identifier(col)) for col in child_cols)
    join = sql.SQL(" AND ").join(
        sql.SQL("p.{} = c.{}").format(sql.Identifier(pc), sql.Identifier(cc)) for cc, pc in zip(child_cols, parent_cols)
    )
    return sql.SQL("SELECT count(*) FROM {child} c WHERE {not_null} AND NOT EXISTS (SELECT 1 FROM {parent} p WHERE {join})").format(
        child=sql.SQL(child), parent=sql.SQL(parent), not_null=not_null, join=join
    )


def check_query(table: str, definition: str) -> sql.Composed:
    """``pg_get_constraintdef`` renders ``CHECK (<expr>)``; rows where the expression is NULL pass."""
    if not definition.startswith("CHECK "):
        raise ValueError(f"not a CHECK constraint definition: {definition!r}")
    return sql.SQL("SELECT count(*) FROM {} t WHERE NOT {}").format(sql.SQL(table), sql.SQL(definition[len("CHECK "):]))


def database_integrity_violations(owner_dsn: str, schemas: Sequence[str] = AUDITED_SCHEMAS) -> list[dict[str, Any]]:
    """Fail-closed audit: FK orphans, CHECK violations and disabled triggers, as a list of findings."""
    findings: list[dict[str, Any]] = []
    with psycopg.connect(owner_dsn) as conn:
        conn.execute("BEGIN READ ONLY")
        bypasses_rls = conn.execute(
            "SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user"
        ).fetchone()[0]
        if not bypasses_rls:
            raise RuntimeError("integrity audit needs a role that bypasses row-level security; "
                               "rows the auditor cannot see are not known to be clean")
        for name, child, parent, child_cols, parent_cols in conn.execute(_FOREIGN_KEYS, (list(schemas),)).fetchall():
            orphans = conn.execute(orphan_query(child, parent, child_cols, parent_cols)).fetchone()[0]
            if orphans:
                findings.append({"kind": "fk-orphan", "constraint": name, "table": child, "parent": parent, "rows": orphans})
        for name, table, definition in conn.execute(_CHECKS, (list(schemas),)).fetchall():
            violating = conn.execute(check_query(table, definition)).fetchone()[0]
            if violating:
                findings.append({"kind": "check-violation", "constraint": name, "table": table, "rows": violating})
        for table, trigger in conn.execute(_DISABLED_TRIGGERS, (list(schemas),)).fetchall():
            findings.append({"kind": "disabled-trigger", "table": table, "trigger": trigger})
        conn.rollback()
    return findings


def assert_database_integrity(owner_dsn: str, schemas: Sequence[str] = AUDITED_SCHEMAS) -> None:
    findings = database_integrity_violations(owner_dsn, schemas)
    assert not findings, f"disposable database left physically inconsistent by a test: {findings}"
