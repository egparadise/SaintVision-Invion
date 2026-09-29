"""Collect S09-DB, S10-DB and S10-ST operational verdicts.

This runs the judgements registered by ``S09-DB_S10-DB_S10-ST_운영_판정_기준.md``
v1.2.  That document classifies twelve observations, and only four of them can
be measured without an input we do not have; this collector measures exactly
those four and leaves the other eight explicitly unmeasured with the reason.

Measured here:

* **O2** context reproducibility -- rebuild each sampled bundle's hash from its
  snapshots and compare with the stored hash (``services.context.verify_bundle``).
  Pre-registered: sample >= 20, mismatches 0.
* **O6** reverse-lookup arithmetic -- in **one** repeatable-read session, walk
  every page of ``services.lineage.models_from_dataset_digest`` and compare the
  summed item count plus ``unresolvedModelVersions`` with an independent count in
  the *same* transaction.  Pre-registered: sample >= 30, mismatches 0.  This is a
  service-level verdict by design (criteria section 3-3): the HTTP route opens a
  new transaction per request, so a route walk cannot share one snapshot.
* **O11'** the enforcement is still installed -- read the CHECK and FK shapes
  from ``pg_constraint`` with migration 0054's own queries and compare with its
  own ``EXPECTED_CHECK``/``EXPECTED_FK``, and read the non-owner grant shape from
  ``information_schema`` rather than hardcoding it.
* **O14** stored rows are verified only by fresh measurements -- exhaustive SQL
  over the age between ``verified_at`` and the measurement's ``observed_at``,
  recording the configured maximum so a later change to that setting cannot be
  applied retroactively.

Not measured, and never silently passed: O1 and O12 need two observation points
(net change only, criteria section 5-1); O8 has no pre-registered threshold
(section 3-2); O3, O5, O9, O10 and O13 wait on an external precondition.

The output carries aggregate counts only, bound to a committed code SHA, this
file's bytes, a database identity and a transaction snapshot -- no DSN, database
name, host, row id, digest of a customer's content, or secret.

Exit codes: 0 PASS (every required observation measured and within threshold --
unreachable while eight observations lack their input), 1 FAIL, 2 UNAVAILABLE or
invalid input, 3 NOT_OBSERVED.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
for _entry in (REPO_ROOT, REPO_ROOT / "src"):
    if str(_entry) not in sys.path:
        sys.path.insert(0, str(_entry))

from tools.operational_evidence import (  # noqa: E402
    EXIT_BY_VERDICT,
    LABEL_PATTERN,
    collect_provenance_at_root,
    collector_sha256,
    database_identity,
    default_label,
    input_binding_sha256,
    iso,
    normalise_dsn,
    overall_verdict,
    sha256_text,
    validate_common,
    write_evidence as write_evidence_pair,
)


SCHEMA_VERSION = "s09-s10-operational-evidence:1"
CRITERIA_VERSION = "1.2.0"
CRITERIA_HEAD = "6db0899a45986011116e126dcd1bd2951b4a5d12"
CRITERIA_PATH = "docs/vault/30_Development/S09-DB_S10-DB_S10-ST_운영_판정_기준.md"
DEFAULT_OUT_DIR = REPO_ROOT / "docs/vault/30_Development/Evidence/s09-s10-operational"

#: Every observation the criteria document registers. PASS requires all of them,
#: which is why PASS is currently unreachable -- and saying so is the point.
REQUIRED_OBSERVATIONS = (
    "O1",
    "O2",
    "O3",
    "O5",
    "O6",
    "O8",
    "O9",
    "O10",
    "O11_PRIME",
    "O12",
    "O13",
    "O14",
)

#: Pre-registered before any result was seen (criteria sections 2 and 3).
O2_MINIMUM_SAMPLE = 20
O6_MINIMUM_SAMPLE = 30

#: The reverse-lookup response truncates the dataset-version list and says so in
#: ``truncated``; a truncated sample has no well-defined "actual count", so O6
#: excludes it (criteria section 3-1 rule 4). The bound itself is read from the
#: service rather than repeated here.


def _measured(status: str, **fields: Any) -> dict[str, Any]:
    return {"status": status, **fields}


def default_unobserved() -> dict[str, dict[str, Any]]:
    """The eight observations this collector cannot measure, and why."""
    return {
        "O1": _measured(
            "NOT_OBSERVED",
            reason="sealed-cohort net change needs two observation points; one run observes neither",
            criteriaSection="5-1",
        ),
        "O3": _measured(
            "BLOCKED_EXTERNAL",
            reason="a real provider eval run is required; G-26 is absent",
            blockedBy=["G-26"],
        ),
        "O5": _measured(
            "BLOCKED_EXTERNAL",
            reason="a provider outage window is required; G-26 is absent",
            blockedBy=["G-26"],
        ),
        "O8": _measured(
            "NOT_OBSERVED",
            reason="no pre-registered plan/latency threshold exists; seq scan count is not a stable contract",
            criteriaSection="3-2",
        ),
        "O9": _measured(
            "BLOCKED_EXTERNAL",
            reason="release manifest acceptance is required; G-23 is absent",
            blockedBy=["G-23"],
        ),
        "O10": _measured(
            "BLOCKED_EXTERNAL",
            reason="a measuring trusted worker on physical nodes is required; G-19/G-24 are absent",
            blockedBy=["G-19", "G-24"],
        ),
        "O12": _measured(
            "NOT_OBSERVED",
            reason="retention-pin net change needs two observation points",
            criteriaSection="5-1",
        ),
        "O13": _measured(
            "BLOCKED_EXTERNAL",
            reason="an object store and a GC cycle are required; G-20/G-21 are absent",
            blockedBy=["G-20", "G-21"],
        ),
    }


# --------------------------------------------------------------------------- O2


def evaluate_context_reproducibility(summary: dict[str, Any] | None) -> dict[str, Any]:
    """O2: a rebuilt bundle hash must equal the stored one.

    Fail-closed in both directions: too small a sample is not a pass, and a
    single mismatch is a failure however large the sample.
    """
    if summary is None:
        return _measured(
            "NOT_OBSERVED", reason="context bundles were not read", minimumSample=O2_MINIMUM_SAMPLE
        )
    seed = summary.get("sampleSeed")
    if not isinstance(seed, str) or not seed:
        return _measured(
            "MEASURED_FAIL",
            reason="the sample seed was not recorded, so the sample cannot be reproduced",
        )
    # Recording the seed gives reproducibility; it does not give pre-registration.
    # An operator free to choose the seed could try several and submit only the
    # run whose sample happens to miss a corrupted bundle, and the report would be
    # perfectly self-consistent. So only the registered seed can carry a verdict.
    if seed != O2_SAMPLE_SEED:
        return _measured(
            "MEASURED_FAIL",
            reason="the sample seed is not the pre-registered one; a chosen seed cannot carry a verdict",
            sampleSeed=seed,
            registeredSeed=O2_SAMPLE_SEED,
        )
    sampled = int(summary.get("sampled", 0))
    verified = int(summary.get("verified", 0))
    mismatched = int(summary.get("mismatched", 0))
    errored = int(summary.get("errored", 0))
    if sampled != verified + mismatched + errored:
        return _measured(
            "MEASURED_FAIL",
            reason="sample accounting does not add up",
            sampled=sampled,
            verified=verified,
            mismatched=mismatched,
            errored=errored,
        )
    if mismatched or errored:
        return _measured(
            "MEASURED_FAIL",
            reason="a rebuilt bundle hash differed from the stored hash, or could not be rebuilt",
            sampled=sampled,
            verified=verified,
            mismatched=mismatched,
            errored=errored,
            minimumSample=O2_MINIMUM_SAMPLE,
        )
    if sampled < O2_MINIMUM_SAMPLE:
        return _measured(
            "NOT_OBSERVED",
            reason="fewer sealed bundles exist than the pre-registered minimum sample",
            sampled=sampled,
            minimumSample=O2_MINIMUM_SAMPLE,
        )
    return _measured(
        "MEASURED_PASS",
        sampled=sampled,
        verified=verified,
        mismatched=0,
        errored=0,
        minimumSample=O2_MINIMUM_SAMPLE,
        sampleSeed=seed,
        sampleOrder=summary.get("sampleOrder"),
    )


# --------------------------------------------------------------------------- O6


def evaluate_reverse_lookup(summary: dict[str, Any] | None) -> dict[str, Any]:
    """O6: summed items + unresolved must equal the independent count."""
    if summary is None:
        return _measured(
            "NOT_OBSERVED",
            reason="dataset digests were not walked",
            minimumSample=O6_MINIMUM_SAMPLE,
        )
    sampled = int(summary.get("sampled", 0))
    matched = int(summary.get("matched", 0))
    mismatched = int(summary.get("mismatched", 0))
    excluded_truncated = int(summary.get("excludedTruncated", 0))
    if sampled != matched + mismatched:
        return _measured(
            "MEASURED_FAIL",
            reason="sample accounting does not add up",
            sampled=sampled,
            matched=matched,
            mismatched=mismatched,
        )
    if mismatched:
        return _measured(
            "MEASURED_FAIL",
            reason="page-summed item count plus unresolved did not equal the independent count",
            sampled=sampled,
            matched=matched,
            mismatched=mismatched,
            excludedTruncated=excluded_truncated,
            minimumSample=O6_MINIMUM_SAMPLE,
        )
    if sampled < O6_MINIMUM_SAMPLE:
        return _measured(
            "NOT_OBSERVED",
            reason="fewer untruncated dataset digests exist than the pre-registered minimum sample",
            sampled=sampled,
            excludedTruncated=excluded_truncated,
            minimumSample=O6_MINIMUM_SAMPLE,
        )
    return _measured(
        "MEASURED_PASS",
        sampled=sampled,
        matched=matched,
        mismatched=0,
        excludedTruncated=excluded_truncated,
        minimumSample=O6_MINIMUM_SAMPLE,
        scope="service-level: one repeatable-read session, not an HTTP walk",
    )


# ---------------------------------------------------------------------- O11'


def evaluate_enforcement_shape(summary: dict[str, Any] | None) -> dict[str, Any]:
    """O11': the CHECK and FK must still be there, validated, and unchanged."""
    if summary is None:
        return _measured("NOT_OBSERVED", reason="constraint shapes were not read")
    check_matches = summary.get("checkMatchesExpected")
    fk_matches = summary.get("fkMatchesExpected")
    grantees_match = summary.get("updateGranteesMatchExpected")
    public_grant = summary.get("publicUpdateGrant")
    shape = {
        "checkPresent": bool(summary.get("checkPresent")),
        "checkMatchesExpected": bool(check_matches),
        "checkValidated": summary.get("checkValidated"),
        "fkPresent": bool(summary.get("fkPresent")),
        "fkMatchesExpected": bool(fk_matches),
        "fkValidated": summary.get("fkValidated"),
        "nonOwnerUpdateGrantCount": summary.get("nonOwnerUpdateGrantCount"),
        "updateGranteesSha256": summary.get("updateGranteesSha256"),
        "expectedUpdateGranteesSha256": summary.get("expectedUpdateGranteesSha256"),
        "updateGranteesMatchExpected": bool(grantees_match),
        "publicUpdateGrant": bool(public_grant),
        "grantShapeSource": "information_schema.column_privileges",
    }
    if check_matches is not True or fk_matches is not True:
        return _measured(
            "MEASURED_FAIL",
            reason="the enforcement installed in the database no longer matches migration 0054",
            **shape,
        )
    # A grant nobody declared can rewrite the column the CHECK protects, so the
    # privilege shape is part of the verdict rather than a recorded curiosity.
    if public_grant is True:
        return _measured(
            "MEASURED_FAIL",
            reason="PUBLIC holds UPDATE on the enforced column",
            **shape,
        )
    if grantees_match is not True:
        return _measured(
            "MEASURED_FAIL",
            reason="the non-owner UPDATE grantees are not exactly the set migration 0054 declares",
            **shape,
        )
    return _measured("MEASURED_PASS", **shape)


# --------------------------------------------------------------------------- O14


def evaluate_measurement_freshness(summary: dict[str, Any] | None) -> dict[str, Any]:
    """O14: no stored row may be verified by a measurement older than the bound.

    The bound is recorded with the result so that raising the setting later
    cannot turn a past failure into a pass.
    """
    if summary is None:
        return _measured("NOT_OBSERVED", reason="verified rows were not read")
    verified_rows = int(summary.get("verifiedRows", 0))
    stale_rows = int(summary.get("staleRows", 0))
    unmatched_rows = int(summary.get("unmatchedRows", 0))
    max_age = summary.get("maxAgeSeconds")
    if not isinstance(max_age, int) or max_age <= 0:
        return _measured("MEASURED_FAIL", reason="the configured freshness bound was not recorded")
    if stale_rows or unmatched_rows:
        return _measured(
            "MEASURED_FAIL",
            reason="a stored row is verified by a measurement older than the bound, or by none",
            verifiedRows=verified_rows,
            staleRows=stale_rows,
            unmatchedRows=unmatched_rows,
            maxAgeSeconds=max_age,
        )
    if verified_rows == 0:
        return _measured(
            "NOT_OBSERVED",
            reason="no verified model version exists yet, so freshness has nothing to judge",
            verifiedRows=0,
            maxAgeSeconds=max_age,
        )
    return _measured(
        "MEASURED_PASS",
        verifiedRows=verified_rows,
        staleRows=0,
        unmatchedRows=0,
        maxAgeSeconds=max_age,
    )


# ------------------------------------------------------------------ SQL inputs

O14_SQL = """
SELECT count(*) AS verified_rows,
       count(*) FILTER (
           WHERE m.measurement_id IS NULL
       ) AS unmatched_rows,
       count(*) FILTER (
           WHERE m.observed_at IS NOT NULL
             AND v.verified_at - m.observed_at > make_interval(secs => %(max_age)s)
       ) AS stale_rows
  FROM public.model_versions v
  LEFT JOIN inv.model_version_measurements m
         ON m.tenant_id = v.tenant_id
        AND m.measurement_id = v.verified_measurement_id
 WHERE v.verified_at IS NOT NULL
"""

#: Non-owner UPDATE grantees on the enforced column. Read, never assumed -- the
#: expected grantee comes from migration 0054's own GRANT statement.
O11_GRANT_SQL = """
SELECT grantee
  FROM information_schema.column_privileges
 WHERE table_schema = 'public'
   AND table_name = 'model_versions'
   AND column_name = 'verified_measurement_id'
   AND privilege_type = 'UPDATE'
   AND grantee <> current_user
 ORDER BY grantee
"""

#: Candidate digests for O6: dataset versions whose digest is set, with the
#: project the service resolves through ``datasets``. Ordered so a rerun on an
#: unchanged database samples the same digests.
O6_DIGEST_SQL = """
SELECT DISTINCT v.tenant_id, d.project_id, v.content_sha256
  FROM public.dataset_versions v
  JOIN public.datasets d
    ON d.tenant_id = v.tenant_id AND d.dataset_id = v.dataset_id
 WHERE v.content_sha256 IS NOT NULL
 ORDER BY v.content_sha256, d.project_id
 LIMIT %(limit)s
"""

#: Independent count for one digest, in the same transaction as the page walk.
#: This is deliberately a second implementation in SQL: calling the service
#: again would put the same defect on both sides of the comparison, and then
#: agreement would prove nothing (criteria T3). It reproduces the service's
#: ``wanted`` set -- distinct lineage subjects for the bounded dataset-version
#: list -- because summed items plus ``unresolvedModelVersions`` equals exactly
#: that set's size.
O6_COUNT_SQL = """
WITH bounded AS (
    SELECT v.dataset_version_id
      FROM public.dataset_versions v
      JOIN public.datasets d
        ON d.tenant_id = v.tenant_id AND d.dataset_id = v.dataset_id
     WHERE v.tenant_id = %(tenant_id)s
       AND v.content_sha256 = %(content_sha256)s
       AND d.project_id = %(project_id)s
     ORDER BY v.dataset_version_id
     LIMIT %(array_limit)s
)
SELECT count(DISTINCT l.model_version_id) AS wanted_count
  FROM public.model_lineage l
 WHERE l.tenant_id = %(tenant_id)s
   AND l.kind = 'dataset_version'
   AND l.subject_id IN (SELECT dataset_version_id FROM bounded)
"""

#: The O2 sample. The criteria call for a *random* sample, and ordering by id
#: would only ever examine the oldest bundles -- twenty good ones at the front
#: would hide every later corruption. Ordering by a digest of a pre-registered
#: seed and the bundle id spreads the sample across the whole space while staying
#: reproducible: the same seed on an unchanged database picks the same bundles.
#: The seed is recorded with the result.
O2_BUNDLE_SQL = """
SELECT b.tenant_id, b.bundle_id
  FROM public.context_bundles b
 ORDER BY md5(%(seed)s || b.bundle_id), b.bundle_id
 LIMIT %(limit)s
"""

#: Pre-registered before any result was seen. Changing it re-draws the sample, so
#: it belongs in the evidence rather than in a caller's head.
O2_SAMPLE_SEED = "s09-o2-context-reproducibility-v1"


def load_enforcement_expectation() -> dict[str, Any]:
    """Read migration 0054's own queries and expectations, never a copy of them.

    Copying the shapes here would let the two drift apart silently, and then this
    observation would confirm the copy rather than the installed constraint.
    """
    import importlib.util

    path = REPO_ROOT / "migrations/versions/0054_model_version_measurements.py"
    spec = importlib.util.spec_from_file_location("_inv_migration_0054", path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ValueError("migration 0054 could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    grantee = re.search(r"\bTO\s+([A-Za-z0-9_]+)\s*$", module.GRANT)
    if grantee is None:  # pragma: no cover - defensive
        raise ValueError("migration 0054 GRANT does not name a grantee")
    return {
        "check_sql": module.CHECK_SHAPE,
        "fk_sql": module.FK_SHAPE,
        "expected_check": module.EXPECTED_CHECK,
        "expected_fk": module.EXPECTED_FK,
        "expected_update_grantees": (grantee.group(1),),
    }


def _positional_rows(conn, statement: str) -> list[tuple]:
    """Read a shape query as tuples.

    Migration 0054's FK_SHAPE selects two unnamed ``array_agg`` subqueries, so
    PostgreSQL names both columns ``array_agg``. Reading that through a mapping
    row factory silently drops one of them -- the observed shape then has nine
    elements and can never equal the migration's ten-element expectation, which is
    how this observation reported a healthy FK as changed. The migration reads the
    same query positionally (``r[0]``..``r[9]``); so does this.
    """
    if hasattr(conn, "execute_positional"):
        return list(conn.execute_positional(statement).fetchall())
    from psycopg.rows import tuple_row

    with conn.cursor(row_factory=tuple_row) as cursor:
        cursor.execute(statement)
        return list(cursor.fetchall())


def read_enforcement_shape(conn) -> dict[str, Any]:
    """Compare the installed constraints with migration 0054's own expectation."""
    shapes = load_enforcement_expectation()
    check_rows = _positional_rows(conn, shapes["check_sql"])
    fk_rows = _positional_rows(conn, shapes["fk_sql"])
    # The same coercion the migration applies before comparing (0054 upgrade()).
    check_observed = (
        (check_rows[0][0], check_rows[0][1], bool(check_rows[0][2])) if check_rows else None
    )
    fk_observed = None
    if fk_rows:
        r = fk_rows[0]
        fk_observed = (
            r[0], r[1], list(r[2] or []), list(r[3] or []), r[4], r[5], r[6],
            bool(r[7]), bool(r[8]), bool(r[9]),
        )
    observed_grantees = tuple(
        str(row["grantee"]) for row in conn.execute(O11_GRANT_SQL).fetchall()
    )
    expected_grantees = tuple(shapes["expected_update_grantees"])
    return {
        "checkPresent": check_observed is not None,
        "checkMatchesExpected": check_observed == shapes["expected_check"],
        "checkValidated": check_observed[2] if check_observed else None,
        "fkPresent": fk_observed is not None,
        "fkMatchesExpected": fk_observed == shapes["expected_fk"],
        "fkValidated": fk_observed[-1] if fk_observed else None,
        "fkShapeElementCount": len(fk_observed) if fk_observed else 0,
        "nonOwnerUpdateGrantCount": len(observed_grantees),
        # The names are hashed: the judgement is "exactly the declared role, and
        # never PUBLIC", which does not require publishing the role name.
        "updateGranteesSha256": sha256_text("\0".join(sorted(observed_grantees))),
        "expectedUpdateGranteesSha256": sha256_text("\0".join(sorted(expected_grantees))),
        "updateGranteesMatchExpected": sorted(observed_grantees) == sorted(expected_grantees),
        "publicUpdateGrant": any(name.upper() == "PUBLIC" for name in observed_grantees),
    }


def read_measurement_freshness(conn, *, max_age_seconds: int) -> dict[str, Any]:
    row = conn.execute(O14_SQL, {"max_age": max_age_seconds}).fetchone()
    return {
        "verifiedRows": int(row["verified_rows"]),
        "staleRows": int(row["stale_rows"]),
        "unmatchedRows": int(row["unmatched_rows"]),
        "maxAgeSeconds": int(max_age_seconds),
    }


def read_context_reproducibility(session, conn, *, limit: int, seed: str) -> dict[str, Any]:
    """O2 over the same database, through the product's own verifier."""
    from saintvision.services.context import verify_bundle

    rows = conn.execute(O2_BUNDLE_SQL, {"limit": limit, "seed": seed}).fetchall()
    verified = mismatched = errored = 0
    for row in rows:
        try:
            ok = verify_bundle(session, tenant_id=row["tenant_id"], bundle_id=row["bundle_id"])
        except Exception:
            # An unreadable bundle is not a pass. The identifier is not recorded.
            errored += 1
            continue
        if ok:
            verified += 1
        else:
            mismatched += 1
    return {
        "sampled": len(rows),
        "verified": verified,
        "mismatched": mismatched,
        "errored": errored,
        "sampleSeed": seed,
        "sampleOrder": "md5(seed || bundle_id)",
    }


def read_reverse_lookup(session, conn, *, limit: int, page_limit: int) -> dict[str, Any]:
    """O6 in one transaction: walk every page, then count independently."""
    from saintvision.services.lineage import ARRAY_LIMIT, models_from_dataset_digest

    digests = conn.execute(O6_DIGEST_SQL, {"limit": limit}).fetchall()
    matched = mismatched = excluded = 0
    for row in digests:
        items = 0
        unresolved: int | None = None
        cursor: str | None = None
        truncated = False
        while True:
            page = models_from_dataset_digest(
                session,
                tenant_id=row["tenant_id"],
                project_id=row["project_id"],
                content_sha256=row["content_sha256"],
                limit=page_limit,
                cursor=cursor,
            )
            page_items = page.get("items") or []
            items += len(page_items)
            if unresolved is None:
                unresolved = int(page.get("unresolvedModelVersions") or 0)
            if page.get("truncated"):
                truncated = True
            cursor = page.get("nextCursor")
            if not cursor:
                break
        if truncated:
            excluded += 1
            continue
        expected = int(
            conn.execute(
                O6_COUNT_SQL,
                {
                    "tenant_id": row["tenant_id"],
                    "project_id": row["project_id"],
                    "content_sha256": row["content_sha256"],
                    "array_limit": ARRAY_LIMIT,
                },
            ).fetchone()["wanted_count"]
        )
        if items + int(unresolved or 0) == expected:
            matched += 1
        else:
            mismatched += 1
    return {
        "sampled": matched + mismatched,
        "matched": matched,
        "mismatched": mismatched,
        "excludedTruncated": excluded,
    }


class SnapshotHandle:
    """Raw SQL access over the *same* connection an ORM session is using.

    O6 compares a service page walk with an independent SQL count, and that
    comparison only means something if both see one snapshot. Handing the SQL a
    second connection -- which is what an independent engine or ``psycopg.connect``
    would do -- silently turns the check into a comparison of two moments in time.
    So the collector takes the session's own DBAPI connection and runs the raw
    statements through it. ``pg_backend_pid`` and ``txid_current_snapshot`` are
    therefore identical for both paths, which the integration test asserts.
    """

    def __init__(self, session) -> None:
        from psycopg.rows import dict_row

        self._session = session
        self._driver = session.connection().connection.driver_connection
        self._row_factory = dict_row

    def execute(self, statement: str, params: dict[str, Any] | None = None):
        cursor = self._driver.cursor(row_factory=self._row_factory)
        cursor.execute(statement, params)
        return cursor

    def execute_positional(self, statement: str, params: dict[str, Any] | None = None):
        """Rows as tuples, for a SELECT whose columns are not uniquely named."""
        from psycopg.rows import tuple_row

        cursor = self._driver.cursor(row_factory=tuple_row)
        cursor.execute(statement, params)
        return cursor

    @property
    def session(self):
        return self._session


def collect_database(
    dsn: str,
    *,
    max_age_seconds: int,
    o2_limit: int,
    o6_limit: int,
    o6_page_limit: int,
    o2_seed: str,
) -> dict[str, Any]:
    """Read one target database in a single repeatable-read, read-only snapshot.

    Everything -- identity, constraint shapes, freshness, the O2 sample and the
    O6 page walk with its independent count -- runs on one connection inside one
    transaction, and nothing is written.
    """
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session

    normalised = normalise_dsn(dsn)
    engine = create_engine(
        normalised
        if normalised.startswith("postgresql+")
        else normalised.replace("postgresql://", "postgresql+psycopg://", 1),
        isolation_level="REPEATABLE READ",
        future=True,
    )
    try:
        with Session(engine) as session:
            # First statements of the transaction, so the snapshot every later
            # read sees is the read-only repeatable-read one.
            session.execute(text("SET TRANSACTION READ ONLY"))
            session.execute(text("SET LOCAL statement_timeout = '120s'"))
            conn = SnapshotHandle(session)
            identity = database_identity(conn)
            started_at = conn.execute("SELECT clock_timestamp() AS value").fetchone()["value"]
            enforcement = read_enforcement_shape(conn)
            freshness = read_measurement_freshness(conn, max_age_seconds=max_age_seconds)
            context = read_context_reproducibility(session, conn, limit=o2_limit, seed=o2_seed)
            reverse = read_reverse_lookup(session, conn, limit=o6_limit, page_limit=o6_page_limit)
            finished_at = conn.execute("SELECT clock_timestamp() AS value").fetchone()["value"]
            session.rollback()
    finally:
        engine.dispose()
    return {
        "identity": identity,
        "sourceStartedAt": iso(started_at),
        "sourceFinishedAt": iso(finished_at),
        "context": context,
        "reverse": reverse,
        "enforcement": enforcement,
        "freshness": freshness,
    }


def build_evidence(
    *, database: dict[str, Any], provenance: dict[str, Any], source_env: str
) -> dict[str, Any]:
    observations = default_unobserved()
    observations["O2"] = evaluate_context_reproducibility(database.get("context"))
    observations["O6"] = evaluate_reverse_lookup(database.get("reverse"))
    observations["O11_PRIME"] = evaluate_enforcement_shape(database.get("enforcement"))
    observations["O14"] = evaluate_measurement_freshness(database.get("freshness"))
    verdict = overall_verdict(observations, REQUIRED_OBSERVATIONS)
    collector_sha = collector_sha256(__file__)
    binding = {
        "codeSha": provenance.get("commit_sha"),
        "collectorSha256": collector_sha,
        "databaseIdentitySha256": database["identity"]["databaseIdentitySha256"],
        "snapshotSha256": database["identity"]["snapshotSha256"],
        "sourceStartedAt": database["sourceStartedAt"],
        "sourceFinishedAt": database["sourceFinishedAt"],
        "maxAgeSeconds": (database.get("freshness") or {}).get("maxAgeSeconds"),
        "o2SampleSeed": (database.get("context") or {}).get("sampleSeed"),
    }
    evidence = {
        "schemaVersion": SCHEMA_VERSION,
        "taskIds": ["S09-DB", "S10-DB", "S10-ST"],
        "criteria": {
            "version": CRITERIA_VERSION,
            "sourceHead": CRITERIA_HEAD,
            "path": CRITERIA_PATH,
        },
        "acceptanceClaim": verdict == "PASS",
        "verdict": verdict,
        "codeSha": provenance.get("commit_sha"),
        "provenance": {
            "branch": provenance.get("branch"),
            "workingTreeClean": provenance.get("working_tree_clean_status"),
            "contentClean": provenance.get("content_clean_diff"),
            "executor": provenance.get("executor"),
            "collectorSha256": collector_sha,
        },
        "source": {
            "kind": "core-postgresql",
            "dsnEnvironment": source_env,
            "sourceStartedAt": database["sourceStartedAt"],
            "sourceFinishedAt": database["sourceFinishedAt"],
            "database": database["identity"],
            "inputBindingSha256": input_binding_sha256(binding),
        },
        "observations": observations,
        "measuredHere": ["O2", "O6", "O11_PRIME", "O14"],
        "excludedBoundaries": {
            "O6-http": {
                "status": "NOT_OBSERVED",
                "reason": "an HTTP-level walk cannot share one snapshot; criteria section 3-3 keeps that out of scope",
            },
            "O11-prime-fail-closed-reader": {
                "status": "NOT_OBSERVED",
                "reason": "the broken-constraint fixture half of O11' is a test, not a production read",
            },
        },
    }
    validate_evidence(evidence)
    return evidence


def validate_evidence(evidence: dict[str, Any]) -> None:
    validate_common(
        evidence,
        schema_version=SCHEMA_VERSION,
        criteria={
            "version": CRITERIA_VERSION,
            "sourceHead": CRITERIA_HEAD,
            "path": CRITERIA_PATH,
        },
        required=REQUIRED_OBSERVATIONS,
    )
    if evidence.get("taskIds") != ["S09-DB", "S10-DB", "S10-ST"]:
        raise ValueError("taskIds must name the three judged tasks")
    observations = evidence.get("observations") or {}
    if set(observations) != set(REQUIRED_OBSERVATIONS):
        raise ValueError("every registered observation must be present")
    if evidence.get("measuredHere") != ["O2", "O6", "O11_PRIME", "O14"]:
        raise ValueError("measuredHere must name exactly the four measurable observations")
    for key in ("O1", "O12"):
        if observations[key]["status"] == "MEASURED_PASS":
            raise ValueError(f"{key} is a net-change observation and cannot pass from one reading")
    if observations["O8"]["status"] == "MEASURED_PASS":
        raise ValueError("O8 has no pre-registered threshold and cannot pass")
    for key in ("O3", "O5", "O9", "O10", "O13"):
        if observations[key]["status"] != "BLOCKED_EXTERNAL":
            raise ValueError(f"{key} waits on an external precondition and must say so")
    excluded = evidence.get("excludedBoundaries") or {}
    for key in ("O6-http", "O11-prime-fail-closed-reader"):
        if excluded.get(key, {}).get("status") != "NOT_OBSERVED":
            raise ValueError(f"{key} must remain explicitly excluded")


def render_markdown(evidence: dict[str, Any]) -> str:
    source = evidence["source"]
    lines = [
        "# S09-DB · S10-DB · S10-ST 운영 판정 수집 결과",
        "",
        f"- verdict: **{evidence['verdict']}** · acceptanceClaim: `{str(evidence['acceptanceClaim']).lower()}`",
        f"- criteria: `{evidence['criteria']['version']}` @ `{evidence['criteria']['sourceHead'][:12]}`",
        f"- codeSha: `{evidence['codeSha'][:12]}` · collector: `{evidence['provenance']['collectorSha256'][:12]}`",
        f"- database: `{source['database']['databaseIdentitySha256'][:12]}` ·"
        f" migration head `{source['database']['migrationHead']}` ·"
        f" isolation `{source['database']['transactionIsolation']}`",
        f"- window: `{source['sourceStartedAt']}` → `{source['sourceFinishedAt']}`",
        "",
        "| 관측 | 상태 | 요약 |",
        "|---|---|---|",
    ]
    for key in REQUIRED_OBSERVATIONS:
        item = evidence["observations"][key]
        detail = item.get("reason") or ""
        if not detail:
            counts = {
                name: value
                for name, value in item.items()
                if name != "status" and isinstance(value, (int, bool))
            }
            detail = ", ".join(f"{name}={value}" for name, value in sorted(counts.items()))
        lines.append(f"| {key} | `{item['status']}` | {detail} |")
    lines += [
        "",
        "측정한 것은 **O2 · O6 · O11′ · O14** 넷뿐이고, 나머지 여덟은 입력이 없어"
        " `NOT_OBSERVED`/`BLOCKED_EXTERNAL`로 남습니다 — 관측하지 않은 것은 통과가 되지 않습니다.",
        "",
    ]
    return "\n".join(lines)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n", 1)[0])
    result.add_argument(
        "--dsn-env", choices=("INV_AUDIT_DSN", "INV_TEST_DATABASE_URL"), default="INV_AUDIT_DSN"
    )
    result.add_argument(
        "--max-age-seconds",
        type=int,
        default=None,
        help="O14 freshness bound; defaults to INV_MODEL_MEASUREMENT_MAX_AGE_SECONDS or 86400",
    )
    result.add_argument("--o2-limit", type=int, default=200)
    # There is deliberately no --o2-seed. The seed is pre-registered in this file,
    # and a flag would turn it into something the executor picks.
    result.add_argument("--o6-limit", type=int, default=200)
    result.add_argument("--o6-page-limit", type=int, default=50)
    result.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    result.add_argument("--label")
    result.add_argument("--executor", default="Claude")
    return result


def resolve_max_age(explicit: int | None) -> int:
    if explicit is not None:
        return explicit
    from saintvision.config import Settings

    return int(Settings.from_env().model_measurement_max_age_seconds)


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    dsn = os.environ.get(args.dsn_env)
    if not dsn:
        print(f"{args.dsn_env} is required; no database was observed", file=sys.stderr)
        return 2
    if args.label is not None and not LABEL_PATTERN.fullmatch(args.label):
        print("label must be 1-128 safe filename characters", file=sys.stderr)
        return 2
    for name, value in (
        ("--o2-limit", args.o2_limit),
        ("--o6-limit", args.o6_limit),
        ("--o6-page-limit", args.o6_page_limit),
    ):
        if value < 1 or value > 10_000:
            print(f"{name} must be in [1, 10000]", file=sys.stderr)
            return 2
    provenance = collect_provenance_at_root(args.executor)
    if not provenance.get("working_tree_clean_status") or not provenance.get("content_clean_diff"):
        print("a clean committed working tree is required", file=sys.stderr)
        return 2
    try:
        max_age = resolve_max_age(args.max_age_seconds)
        if max_age <= 0:
            raise ValueError("freshness bound must be positive")
        database = collect_database(
            dsn,
            max_age_seconds=max_age,
            o2_limit=args.o2_limit,
            o6_limit=args.o6_limit,
            o6_page_limit=args.o6_page_limit,
            o2_seed=O2_SAMPLE_SEED,
        )
        evidence = build_evidence(
            database=database, provenance=provenance, source_env=args.dsn_env
        )
        label = args.label or default_label("s09-s10-operational", evidence["codeSha"])
        json_path, markdown_path = write_evidence_pair(
            evidence, args.out_dir, label, render_markdown=render_markdown
        )
    except Exception as error:
        # A database error can echo connection details; only the class is shown.
        print(f"collector unavailable: {type(error).__name__}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "verdict": evidence["verdict"],
                "observations": {
                    key: value["status"] for key, value in evidence["observations"].items()
                },
                "json": str(json_path),
                "markdown": str(markdown_path),
            },
            ensure_ascii=False,
        )
    )
    return EXIT_BY_VERDICT[evidence["verdict"]]


if __name__ == "__main__":
    raise SystemExit(main())
