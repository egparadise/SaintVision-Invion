"""Real PostgreSQL evidence for the S09/S10 operational collector.

Every SQL statement and every service call the collector makes runs here against
a migrated database, because a statement that only ever ran against a fake proves
nothing about the schema it claims to read.

What this file does *not* do is seed operational data. The MEASURED_FAIL
directions for O2, O6 and O14 are fixed PG-free in
``tests/core/test_s09_s10_operational_evidence.py``; what needs a real database
is that the statements parse and resolve against the real schema, that an empty
database is never a pass, and that O11' notices when the enforcement it checks is
taken away -- which is the one thing no fake can show, since the constraint has
to actually exist to be removed.
"""

from __future__ import annotations

import psycopg
from psycopg.rows import dict_row
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from tools import collect_s09_s10_operational_evidence as collector


pytestmark = pytest.mark.postgres


def _conn(database_url: str):
    return psycopg.connect(collector.normalise_dsn(database_url), row_factory=dict_row)


def test_o11_prime_passes_against_the_installed_enforcement(owner_engine, database_url):
    """The CHECK and FK from 0054 are present, validated and unchanged."""
    with _conn(database_url) as conn:
        summary = collector.read_enforcement_shape(conn)
    assert summary["checkPresent"] is True
    assert summary["checkMatchesExpected"] is True
    assert summary["checkValidated"] is True
    assert summary["fkPresent"] is True
    assert summary["fkMatchesExpected"] is True
    assert summary["fkValidated"] is True
    verdict = collector.evaluate_enforcement_shape(summary)
    assert verdict["status"] == "MEASURED_PASS"
    assert verdict["grantShapeSource"] == "information_schema.role_table_grants"


def test_o11_prime_notices_when_the_check_is_removed(owner_engine, database_url):
    """Take the enforcement away and the observation must fail, not pass.

    The drop happens inside a transaction that is rolled back, so the database
    leaves this test exactly as it arrived.
    """
    with _conn(database_url) as conn:
        before = collector.read_enforcement_shape(conn)
        assert collector.evaluate_enforcement_shape(before)["status"] == "MEASURED_PASS"
        conn.execute(
            "ALTER TABLE public.model_versions "
            "DROP CONSTRAINT ck_model_versions_verified_iff_measurement"
        )
        after = collector.read_enforcement_shape(conn)
        conn.rollback()
    assert after["checkPresent"] is False
    assert after["checkMatchesExpected"] is False
    verdict = collector.evaluate_enforcement_shape(after)
    assert verdict["status"] == "MEASURED_FAIL"
    assert "no longer matches" in verdict["reason"]

    with _conn(database_url) as conn:
        restored = collector.read_enforcement_shape(conn)
    assert restored["checkMatchesExpected"] is True, "the rollback must leave the CHECK installed"


def test_o14_statement_resolves_and_an_empty_database_is_not_a_pass(owner_engine, database_url):
    with _conn(database_url) as conn:
        summary = collector.read_measurement_freshness(conn, max_age_seconds=86_400)
    assert summary == {
        "verifiedRows": 0,
        "staleRows": 0,
        "unmatchedRows": 0,
        "maxAgeSeconds": 86_400,
    }
    verdict = collector.evaluate_measurement_freshness(summary)
    assert verdict["status"] == "NOT_OBSERVED"
    assert verdict["maxAgeSeconds"] == 86_400


def test_o14_records_the_bound_it_was_given(owner_engine, database_url):
    """A different bound produces a different recorded bound, not a silent default."""
    with _conn(database_url) as conn:
        summary = collector.read_measurement_freshness(conn, max_age_seconds=60)
    assert summary["maxAgeSeconds"] == 60


def test_o2_and_o6_statements_resolve_and_report_nothing_measured(owner_engine, database_url):
    """The O2 and O6 reads run against the real schema; empty is NOT_OBSERVED."""
    engine = create_engine(
        collector.normalise_dsn(database_url).replace(
            "postgresql://", "postgresql+psycopg://", 1
        ),
        isolation_level="REPEATABLE READ",
        future=True,
    )
    try:
        with _conn(database_url) as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            with Session(engine) as session:
                context = collector.read_context_reproducibility(session, conn, limit=50)
                reverse = collector.read_reverse_lookup(
                    session, conn, limit=50, page_limit=25
                )
                session.rollback()
            conn.rollback()
    finally:
        engine.dispose()
    assert context == {"sampled": 0, "verified": 0, "mismatched": 0, "errored": 0}
    assert reverse == {"sampled": 0, "matched": 0, "mismatched": 0, "excludedTruncated": 0}
    assert collector.evaluate_context_reproducibility(context)["status"] == "NOT_OBSERVED"
    assert collector.evaluate_reverse_lookup(reverse)["status"] == "NOT_OBSERVED"


def test_the_independent_o6_count_is_not_the_service_query(owner_engine, database_url):
    """O6's count must be a second implementation, or agreement proves nothing.

    This runs the collector's own SQL directly: if someone replaces it with a
    call back into ``models_from_dataset_digest``, this statement stops existing
    and the test stops compiling.
    """
    from saintvision.services.lineage import ARRAY_LIMIT

    with _conn(database_url) as conn:
        row = conn.execute(
            collector.O6_COUNT_SQL,
            {
                "tenant_id": "00000000-0000-0000-0000-000000000000",
                "project_id": "prj_absent",
                "content_sha256": "a" * 64,
                "array_limit": ARRAY_LIMIT,
            },
        ).fetchone()
    assert row["wanted_count"] == 0
    assert "model_lineage" in collector.O6_COUNT_SQL
    assert "models_from_dataset_digest" not in collector.O6_COUNT_SQL


def test_database_identity_binds_without_naming_the_database(owner_engine, database_url):
    with _conn(database_url) as conn:
        identity = collector.database_identity(conn)
    assert identity["systemIdentifierObserved"] is True
    assert len(identity["databaseIdentitySha256"]) == 64
    assert len(identity["databaseNameSha256"]) == 64
    assert identity["migrationHead"]
    serialised = repr(identity)
    assert "postgres" not in serialised.lower() or "postgresql://" not in serialised
    assert database_url not in serialised
