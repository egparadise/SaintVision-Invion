"""PG-free checks for the owner-corruption hygiene helpers (tests/db_integrity.py).

* ratchet: no raw ``DISABLE TRIGGER`` / ``ENABLE TRIGGER`` outside the helper, so every
  suspension is guaranteed to be re-enabled in ``finally``;
* the restore protocol (capture -> delete -> re-insert, triggers suspended, reverse order,
  even when the guarded block raises) is verified against a recording fake connection;
* the SQL the audit builds for foreign keys and CHECK constraints renders as expected.
"""

from __future__ import annotations

from pathlib import Path
import re

import pytest
from psycopg import sql

import db_integrity as hygiene

TESTS = Path(__file__).resolve().parent
HELPER = TESTS / "db_integrity.py"
RAW_TRIGGER = re.compile(r"(DISABLE|ENABLE)\s+TRIGGER", re.IGNORECASE)


def test_no_raw_trigger_statement_outside_the_helper():
    offenders = []
    for path in TESTS.rglob("*.py"):
        if path == HELPER or path == Path(__file__):
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
            if RAW_TRIGGER.search(line) and not line.lstrip().startswith("#"):
                offenders.append(f"{path.relative_to(TESTS)}:{number}")
    assert offenders == [], offenders


def test_every_owner_corruption_site_uses_preserved_rows_or_suspended_triggers():
    """The sites found by the 2026-09-28 sweep must keep using the helpers (not a raw ALTER)."""
    sites = {
        "integration/test_postgres.py": ("preserved_rows", "suspended_triggers"),
        "integration/test_approval_review.py": ("preserved_rows", "suspended_triggers"),
        "integration/test_model_view.py": ("preserved_rows", "suspended_triggers"),
        "integration/test_shard_recovery.py": ("suspended_triggers",),
        "integration/test_storage_view.py": ("preserved_rows", "suspended_triggers"),
    }
    for relative, helpers in sites.items():
        text = (TESTS / relative).read_text(encoding="utf-8-sig")
        for helper in helpers:
            assert f"from db_integrity import" in text and helper in text, (relative, helper)


def test_session_fixtures_audit_before_dropping_the_database():
    integration = (TESTS / "integration" / "conftest.py").read_text(encoding="utf-8-sig")
    root = (TESTS / "conftest.py").read_text(encoding="utf-8-sig")
    for text in (integration, root):
        assert "database_integrity_violations(" in text
        audit = text.index("database_integrity_violations(")
        drop = text.index("DROP DATABASE", audit)
        assert audit < drop, "audit must run before the drop"
        assert "assert not findings" in text[drop:]


class _Cursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _Conn:
    """Records rendered SQL; SELECT to_jsonb returns the rows configured per table."""

    def __init__(self, rows_by_table):
        self.rows_by_table = rows_by_table
        self.log: list[str] = []

    def execute(self, query, params=None):
        rendered = query.as_string(None) if isinstance(query, sql.Composable) else query
        self.log.append(rendered)
        if rendered.startswith("SELECT to_jsonb"):
            table = rendered.split(" FROM ")[1].split(" ")[0].replace('"', "")
            return _Cursor([(row,) for row in self.rows_by_table.get(table, [])])
        return _Cursor([])


def test_suspended_triggers_re_enables_even_when_the_block_raises():
    conn = _Conn({})
    with pytest.raises(RuntimeError):
        with hygiene.suspended_triggers(conn, "inv.evidence", "USER"):
            raise RuntimeError("corruption failed half-way")
    assert conn.log == ['ALTER TABLE "inv"."evidence" DISABLE TRIGGER USER',
                        'ALTER TABLE "inv"."evidence" ENABLE TRIGGER USER']
    conn = _Conn({})
    with hygiene.suspended_triggers(conn, "inv.approval_review_snapshots", "immutable"):
        pass
    assert conn.log[-1] == 'ALTER TABLE "inv"."approval_review_snapshots" ENABLE TRIGGER "immutable"'


@pytest.mark.parametrize("bad", ["evidence", "inv.evidence; DROP", "Inv.Evidence", "inv.evidence.x"])
def test_table_names_are_validated(bad):
    with pytest.raises(ValueError):
        with hygiene.suspended_triggers(_Conn({}), bad, "USER"):
            pass


@pytest.mark.parametrize("bad", ["ALL; DROP", "USER x", "Immutable"])
def test_trigger_specs_are_validated(bad):
    with pytest.raises(ValueError):
        with hygiene.suspended_triggers(_Conn({}), "inv.evidence", bad):
            pass


def test_restore_rows_deletes_then_reinserts_captured_rows_in_reverse_order_with_triggers_suspended():
    captured = [
        (("inv.runs", "run_id=ANY(%s)", (["r1", "r2"],)), [{"run_id": "r1"}, {"run_id": "r2"}]),
        (("inv.result_commitments", "run_id=%s", ("r2",)), []),  # synthetic orphan: nothing to put back
    ]
    conn = _Conn({})
    hygiene.restore_rows(conn, captured)
    assert conn.log == [
        'ALTER TABLE "inv"."result_commitments" DISABLE TRIGGER ALL',
        'DELETE FROM "inv"."result_commitments" WHERE run_id=%s',
        'ALTER TABLE "inv"."result_commitments" ENABLE TRIGGER ALL',
        'ALTER TABLE "inv"."runs" DISABLE TRIGGER ALL',
        'DELETE FROM "inv"."runs" WHERE run_id=ANY(%s)',
        'INSERT INTO "inv"."runs" SELECT * FROM jsonb_populate_record(NULL::"inv"."runs", %s)',
        'INSERT INTO "inv"."runs" SELECT * FROM jsonb_populate_record(NULL::"inv"."runs", %s)',
        'ALTER TABLE "inv"."runs" ENABLE TRIGGER ALL',
    ]


def test_snapshot_rows_captures_exactly_the_targets():
    conn = _Conn({"inv.evidence": [{"evidence_id": "evd_1", "envelope": {"a": 1}}]})
    captured = hygiene.snapshot_rows(conn, [("inv.evidence", "evidence_id=%s", ("evd_1",)),
                                           ("inv.runs", "run_id=%s", ("r",))])
    assert captured == [(("inv.evidence", "evidence_id=%s", ("evd_1",)), [{"evidence_id": "evd_1", "envelope": {"a": 1}}]),
                        (("inv.runs", "run_id=%s", ("r",)), [])]
    assert conn.log[0] == 'SELECT to_jsonb(t) FROM "inv"."evidence" t WHERE evidence_id=%s'


def test_orphan_and_check_queries_render():
    query = hygiene.orphan_query("inv.result_completions", "inv.result_commitments",
                                 ["tenant_id", "run_id"], ["tenant_id", "run_id"]).as_string(None)
    assert query == ('SELECT count(*) FROM inv.result_completions c WHERE c."tenant_id" IS NOT NULL AND c."run_id" IS NOT NULL '
                     'AND NOT EXISTS (SELECT 1 FROM inv.result_commitments p WHERE p."tenant_id" = c."tenant_id" AND p."run_id" = c."run_id")')
    check = hygiene.check_query("inv.nodes", "CHECK ((clock_skew_seconds >= '-86400'::integer::numeric))").as_string(None)
    assert check == "SELECT count(*) FROM inv.nodes t WHERE NOT ((clock_skew_seconds >= '-86400'::integer::numeric))"
    with pytest.raises(ValueError):
        hygiene.check_query("inv.nodes", "FOREIGN KEY (a) REFERENCES b(a)")
