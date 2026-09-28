"""Real-PG proof that owner corruption is visible during a test and gone after it.

Reproduces the PR #126 class of failure in one session: an ``inv.result_commitments``
row without its ``inv.execution_attempts`` parent (exactly what the invalid-EvidenceEnvelope
case builds) is inserted with triggers suspended inside ``preserved_rows``; the audit must
report the orphan while it exists and report nothing once the block has exited.
"""

from uuid import uuid4

import psycopg
from psycopg.types.json import Jsonb
import pytest

from db_integrity import database_integrity_violations, preserved_rows, suspended_triggers
from inv.ids import new_id


def _orphan_commitment(e, run_id):
    return (
        "INSERT INTO inv.result_commitments(tenant_id,project_id,run_id,attempt,command_id,object_id,evidence_id,envelope,content_hash) "
        "VALUES(%s,%s,%s,1,%s,%s,%s,%s,%s)",
        (e.tenant, e.project, run_id, str(uuid4()), str(uuid4()), new_id("evd"), Jsonb({}), "4" * 64),
    )


def test_audit_is_clean_on_the_migrated_schema_before_any_corruption(env):
    assert database_integrity_violations(env.owner) == []


def test_orphan_is_reported_while_live_and_gone_after_preserved_rows_exits(env):
    e = env
    run_id = new_id("run")
    with preserved_rows(e.owner, ("inv.result_commitments", "tenant_id=%s AND run_id=%s", (e.tenant, run_id))):
        with psycopg.connect(e.owner) as conn, suspended_triggers(conn, "inv.result_commitments", "ALL"):
            conn.execute(*_orphan_commitment(e, run_id))
        live = database_integrity_violations(e.owner)
        assert any(f["kind"] == "fk-orphan" and f["table"] == "inv.result_commitments" for f in live), live
    assert database_integrity_violations(e.owner) == []
    with psycopg.connect(e.owner) as conn:
        assert conn.execute("SELECT count(*) FROM inv.result_commitments WHERE run_id=%s", (run_id,)).fetchone()[0] == 0


def test_preserved_rows_restores_a_corrupted_row_verbatim_even_when_the_block_raises(env):
    e = env
    with psycopg.connect(e.owner) as conn:
        before = conn.execute("SELECT to_jsonb(n) FROM inv.nodes n WHERE node_id=%s", (e.node,)).fetchone()[0]
    with pytest.raises(RuntimeError):
        with preserved_rows(e.owner, ("inv.nodes", "tenant_id=%s AND node_id=%s", (e.tenant, e.node))):
            with psycopg.connect(e.owner) as conn:
                conn.execute("UPDATE inv.nodes SET status='quarantined', clock_skew_seconds=42 WHERE node_id=%s", (e.node,))
            raise RuntimeError("assertion failed mid-test")
    with psycopg.connect(e.owner) as conn:
        after = conn.execute("SELECT to_jsonb(n) FROM inv.nodes n WHERE node_id=%s", (e.node,)).fetchone()[0]
    assert after == before


def test_disabled_trigger_is_reported_and_suspended_triggers_never_leaves_one(env):
    e = env
    with psycopg.connect(e.owner) as conn:
        with suspended_triggers(conn, "inv.evidence", "USER"):
            conn.commit()  # make the disabled state visible to the auditor's own connection
            live = database_integrity_violations(e.owner)
            assert any(f["kind"] == "disabled-trigger" and f["table"] == "inv.evidence" for f in live), live
    assert not any(f["kind"] == "disabled-trigger" for f in database_integrity_violations(e.owner))


def test_audit_refuses_a_role_that_rls_could_silence(env):
    with pytest.raises(RuntimeError, match="bypasses row-level security"):
        database_integrity_violations(env.runtime)
