"""Real PostgreSQL evidence for the S09/S10 operational collector.

Every SQL statement and every service call the collector makes runs here against
a migrated database, because a statement that only ever ran against a fake proves
nothing about the schema it claims to read.

Two things need a real database and cannot be shown any other way:

* that O6's page walk and its independent count really do share one snapshot --
  proved by reading ``pg_backend_pid`` and ``txid_current_snapshot`` through both
  paths and requiring them to be identical, and by showing a second connection
  has a different backend; and
* that O11' notices when the enforcement it checks is taken away or widened --
  the constraint has to exist before it can be dropped, and a grant has to be
  grantable before an extra one can be added.

This file does not seed operational data. The MEASURED_FAIL directions for O2,
O6 and O14 are fixed PG-free in ``tests/core/test_s09_s10_operational_evidence.py``.
"""

from __future__ import annotations

import uuid

import psycopg
from psycopg.rows import dict_row
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from tools import collect_s09_s10_operational_evidence as collector


pytestmark = pytest.mark.postgres


def _conn(database_url: str):
    return psycopg.connect(collector.normalise_dsn(database_url), row_factory=dict_row)


def _engine(database_url: str):
    normalised = collector.normalise_dsn(database_url)
    return create_engine(
        normalised
        if normalised.startswith("postgresql+")
        else normalised.replace("postgresql://", "postgresql+psycopg://", 1),
        isolation_level="REPEATABLE READ",
        future=True,
    )


# --------------------------------------------------------------- O6, one snapshot


def test_the_service_walk_and_the_independent_count_share_one_transaction(
    owner_engine, database_url
):
    """The contract O6 rests on: one snapshot, not two moments in time.

    If the raw SQL is ever given its own connection again -- an independent
    engine, or ``psycopg.connect`` -- the backend pid and the snapshot diverge and
    this test fails. The third connection is here to show the assertion can tell
    two transactions apart, so an equality that held by accident would not pass.
    """
    engine = _engine(database_url)
    try:
        with Session(engine) as session:
            session.execute(text("SET TRANSACTION READ ONLY"))
            handle = collector.SnapshotHandle(session)

            orm_pid = session.execute(text("SELECT pg_backend_pid() AS pid")).one()[0]
            orm_snapshot = session.execute(
                text("SELECT txid_current_snapshot()::text AS snap")
            ).one()[0]
            raw_pid = handle.execute("SELECT pg_backend_pid() AS pid").fetchone()["pid"]
            raw_snapshot = handle.execute(
                "SELECT txid_current_snapshot()::text AS snap"
            ).fetchone()["snap"]
            read_only = handle.execute(
                "SELECT current_setting('transaction_read_only') AS value"
            ).fetchone()["value"]
            isolation = handle.execute(
                "SELECT current_setting('transaction_isolation') AS value"
            ).fetchone()["value"]
            session.rollback()
    finally:
        engine.dispose()

    assert raw_pid == orm_pid, "the raw SQL ran on a different backend than the service"
    assert raw_snapshot == orm_snapshot, "the raw SQL saw a different snapshot"
    assert read_only == "on"
    assert isolation == "repeatable read"

    with _conn(database_url) as other:
        other_pid = other.execute("SELECT pg_backend_pid() AS pid").fetchone()["pid"]
    assert other_pid != orm_pid, "the control connection must be a different backend"


def test_a_row_committed_elsewhere_is_invisible_inside_the_collector_snapshot(
    owner_engine, database_url
):
    """A second connection's commit must not appear mid-collection.

    This is what "one snapshot" buys: the page walk and the count cannot straddle
    someone else's write.
    """
    marker_tenant = str(uuid.uuid4())
    marker_digest = "f" * 64
    engine = _engine(database_url)
    try:
        with Session(engine) as session:
            session.execute(text("SET TRANSACTION READ ONLY"))
            handle = collector.SnapshotHandle(session)
            before = handle.execute(
                "SELECT count(*) AS value FROM public.context_snapshots"
            ).fetchone()["value"]

            # A real row, committed by a different connection while the
            # collection is open. A temp table would not be observable and would
            # make this test's name a claim it does not check.
            with owner_engine.begin() as outside:
                outside.execute(
                    text(
                        "INSERT INTO public.context_snapshots"
                        " (tenant_id, content_hash, content, byte_size)"
                        " VALUES (:tenant, :digest, :content, :size)"
                    ),
                    {
                        "tenant": marker_tenant,
                        "digest": marker_digest,
                        "content": "snapshot-visibility-probe",
                        "size": len("snapshot-visibility-probe"),
                    },
                )

            # A connection opened after the commit does see it, so the
            # invisibility below is the snapshot doing its job rather than an
            # insert that quietly failed.
            with _conn(database_url) as witness:
                seen = witness.execute(
                    "SELECT count(*) AS value FROM public.context_snapshots"
                    " WHERE tenant_id = %(tenant)s AND content_hash = %(digest)s",
                    {"tenant": marker_tenant, "digest": marker_digest},
                ).fetchone()["value"]
                witness.rollback()

            after = handle.execute(
                "SELECT count(*) AS value FROM public.context_snapshots"
            ).fetchone()["value"]
            same_snapshot = handle.execute(
                "SELECT txid_current_snapshot()::text AS snap"
            ).fetchone()["snap"]
            again = handle.execute(
                "SELECT txid_current_snapshot()::text AS snap"
            ).fetchone()["snap"]
            session.rollback()
    finally:
        engine.dispose()
        with owner_engine.begin() as cleanup:
            cleanup.execute(
                text(
                    "DELETE FROM public.context_snapshots"
                    " WHERE tenant_id = :tenant AND content_hash = :digest"
                ),
                {"tenant": marker_tenant, "digest": marker_digest},
            )
    assert seen == 1, "the marker row was never committed, so the test proves nothing"
    assert after == before, "a row committed elsewhere became visible mid-collection"
    assert same_snapshot == again, "the snapshot moved inside one collection"


# ------------------------------------------------------------------------- O11'


def test_o11_prime_passes_against_the_installed_enforcement(owner_engine, database_url):
    """The CHECK, the FK and the grant shape from 0054 are all as declared."""
    with _conn(database_url) as conn:
        summary = collector.read_enforcement_shape(conn)
    assert summary["checkPresent"] is True
    assert summary["checkMatchesExpected"] is True
    assert summary["checkValidated"] is True
    assert summary["fkPresent"] is True
    assert summary["fkMatchesExpected"] is True
    assert summary["fkValidated"] is True
    assert summary["updateGranteesMatchExpected"] is True
    assert summary["publicUpdateGrant"] is False
    verdict = collector.evaluate_enforcement_shape(summary)
    assert verdict["status"] == "MEASURED_PASS"
    assert verdict["grantShapeSource"] == "information_schema.column_privileges"


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


def test_o11_prime_notices_an_extra_update_grant(owner_engine, database_url):
    """A grantee nobody declared can rewrite the column the CHECK protects.

    Granting UPDATE to PUBLIC inside a rolled-back transaction must turn the
    observation into a failure; recording the count without judging it would let
    this through, which is what this test exists to prevent.
    """
    with _conn(database_url) as conn:
        baseline = collector.read_enforcement_shape(conn)
        assert collector.evaluate_enforcement_shape(baseline)["status"] == "MEASURED_PASS"
        conn.execute(
            "GRANT UPDATE (verified_measurement_id) ON public.model_versions TO PUBLIC"
        )
        widened = collector.read_enforcement_shape(conn)
        conn.rollback()
    assert widened["publicUpdateGrant"] is True
    assert widened["updateGranteesMatchExpected"] is False
    assert widened["nonOwnerUpdateGrantCount"] > baseline["nonOwnerUpdateGrantCount"]
    verdict = collector.evaluate_enforcement_shape(widened)
    assert verdict["status"] == "MEASURED_FAIL"
    assert "PUBLIC" in verdict["reason"]

    with _conn(database_url) as conn:
        restored = collector.read_enforcement_shape(conn)
    assert restored["publicUpdateGrant"] is False, "the rollback must remove the extra grant"
    assert restored["updateGranteesMatchExpected"] is True


def test_the_expected_grantee_is_read_from_the_migration(owner_engine, database_url):
    shapes = collector.load_enforcement_expectation()
    assert shapes["expected_update_grantees"] == ("inv_app",)
    with _conn(database_url) as conn:
        observed = collector.read_enforcement_shape(conn)
    assert observed["updateGranteesSha256"] == observed["expectedUpdateGranteesSha256"]


# -------------------------------------------------------------------------- O14


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


# ---------------------------------------------------------------------- O2 / O6


def test_o2_and_o6_statements_resolve_and_report_nothing_measured(owner_engine, database_url):
    """The O2 and O6 reads run on one connection; empty is NOT_OBSERVED."""
    engine = _engine(database_url)
    try:
        with Session(engine) as session:
            session.execute(text("SET TRANSACTION READ ONLY"))
            handle = collector.SnapshotHandle(session)
            context = collector.read_context_reproducibility(
                session, handle, limit=50, seed=collector.O2_SAMPLE_SEED
            )
            reverse = collector.read_reverse_lookup(session, handle, limit=50, page_limit=25)
            session.rollback()
    finally:
        engine.dispose()
    assert context["sampled"] == 0
    assert context["sampleSeed"] == collector.O2_SAMPLE_SEED
    assert reverse == {"sampled": 0, "matched": 0, "mismatched": 0, "excludedTruncated": 0}
    assert collector.evaluate_context_reproducibility(context)["status"] == "NOT_OBSERVED"
    assert collector.evaluate_reverse_lookup(reverse)["status"] == "NOT_OBSERVED"


def test_the_o2_sample_order_is_the_seeded_digest(owner_engine, database_url):
    """The ordering expression must be accepted by PostgreSQL, not only by a fake."""
    with _conn(database_url) as conn:
        rows = conn.execute(
            collector.O2_BUNDLE_SQL, {"limit": 5, "seed": collector.O2_SAMPLE_SEED}
        ).fetchall()
    assert rows == []


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
    assert database_url not in repr(identity)
