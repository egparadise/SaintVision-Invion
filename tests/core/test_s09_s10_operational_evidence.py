"""Fail-closed contract tests for the S09/S10 operational collector.

Every test here answers one question: can an observation nobody measured end up
looking like a pass?  The answer has to be no on each path, including the paths
a later edit is most likely to take -- a sample that is too small, a count that
does not add up, a threshold that was not recorded, and a verdict written by hand
instead of recomputed.
"""

from __future__ import annotations

from copy import deepcopy

import pytest

from tools import collect_s09_s10_operational_evidence as collector
from tools import operational_evidence as shared


SHA = "1" * 40
SEED = collector.O2_SAMPLE_SEED
DIGEST = "a" * 64


def _database(context=None, reverse=None, enforcement=None, freshness=None):
    return {
        "identity": {
            "databaseIdentitySha256": DIGEST,
            "databaseNameSha256": "b" * 64,
            "systemIdentifierObserved": True,
            "databaseOid": "16384",
            "serverVersionNum": "160004",
            "migrationHead": "0054_model_version_measurements",
            "transactionIsolation": "repeatable read",
            "transactionReadOnly": "on",
            "snapshotSha256": "c" * 64,
            "observedAt": "2026-09-29T00:00:00Z",
        },
        "sourceStartedAt": "2026-09-29T00:00:00Z",
        "sourceFinishedAt": "2026-09-29T00:00:05Z",
        "context": context,
        "reverse": reverse,
        "enforcement": enforcement,
        "freshness": freshness,
    }


def _provenance():
    return {
        "commit_sha": SHA,
        "branch": "agent/claude/card128-s09-s10-collector",
        "working_tree_clean_status": True,
        "content_clean_diff": True,
        "executor": "Claude",
    }


def _evidence(**database_kwargs):
    return collector.build_evidence(
        database=_database(**database_kwargs),
        provenance=_provenance(),
        source_env="INV_AUDIT_DSN",
    )


# --------------------------------------------------------------- the four gates


def test_nothing_measured_is_not_observed_and_claims_nothing():
    evidence = _evidence()
    assert evidence["verdict"] == "NOT_OBSERVED"
    assert evidence["acceptanceClaim"] is False
    statuses = {key: value["status"] for key, value in evidence["observations"].items()}
    assert "MEASURED_PASS" not in statuses.values()


def test_o2_below_the_registered_sample_is_not_a_pass():
    below = collector.evaluate_context_reproducibility(
        {"sampled": 19, "verified": 19, "mismatched": 0, "errored": 0, "sampleSeed": SEED}
    )
    assert below["status"] == "NOT_OBSERVED"
    assert below["minimumSample"] == 20
    at = collector.evaluate_context_reproducibility(
        {"sampled": 20, "verified": 20, "mismatched": 0, "errored": 0, "sampleSeed": SEED}
    )
    assert at["status"] == "MEASURED_PASS"


@pytest.mark.parametrize(
    "summary",
    [
        {"sampled": 40, "verified": 39, "mismatched": 1, "errored": 0, "sampleSeed": SEED},
        {"sampled": 40, "verified": 39, "mismatched": 0, "errored": 1, "sampleSeed": SEED},
    ],
)
def test_o2_one_bad_bundle_fails_however_large_the_sample(summary):
    assert collector.evaluate_context_reproducibility(summary)["status"] == "MEASURED_FAIL"


def test_o2_accounting_that_does_not_add_up_fails():
    result = collector.evaluate_context_reproducibility(
        {"sampled": 40, "verified": 10, "mismatched": 0, "errored": 0, "sampleSeed": SEED}
    )
    assert result["status"] == "MEASURED_FAIL"
    assert "add up" in result["reason"]


def test_o6_below_the_registered_sample_is_not_a_pass():
    below = collector.evaluate_reverse_lookup({"sampled": 29, "matched": 29, "mismatched": 0})
    assert below["status"] == "NOT_OBSERVED"
    assert below["minimumSample"] == 30
    at = collector.evaluate_reverse_lookup({"sampled": 30, "matched": 30, "mismatched": 0})
    assert at["status"] == "MEASURED_PASS"


def test_o6_a_single_arithmetic_mismatch_fails():
    result = collector.evaluate_reverse_lookup(
        {"sampled": 100, "matched": 99, "mismatched": 1, "excludedTruncated": 3}
    )
    assert result["status"] == "MEASURED_FAIL"
    assert result["excludedTruncated"] == 3


def test_o6_truncated_samples_are_excluded_not_counted_as_matches():
    result = collector.evaluate_reverse_lookup(
        {"sampled": 30, "matched": 30, "mismatched": 0, "excludedTruncated": 12}
    )
    assert result["status"] == "MEASURED_PASS"
    assert result["sampled"] == 30
    assert result["excludedTruncated"] == 12


def test_o11_prime_fails_when_the_installed_shape_differs():
    result = collector.evaluate_enforcement_shape(
        {
            "checkPresent": True,
            "checkMatchesExpected": False,
            "checkValidated": True,
            "fkPresent": True,
            "fkMatchesExpected": True,
            "fkValidated": True,
            "nonOwnerUpdateGrantCount": 0,
        }
    )
    assert result["status"] == "MEASURED_FAIL"


def test_o11_prime_fails_when_the_constraint_is_gone():
    result = collector.evaluate_enforcement_shape(
        {
            "checkPresent": False,
            "checkMatchesExpected": False,
            "checkValidated": None,
            "fkPresent": True,
            "fkMatchesExpected": True,
            "fkValidated": True,
            "nonOwnerUpdateGrantCount": 0,
        }
    )
    assert result["status"] == "MEASURED_FAIL"
    assert result["checkPresent"] is False


def test_o14_without_a_recorded_bound_fails():
    result = collector.evaluate_measurement_freshness(
        {"verifiedRows": 5, "staleRows": 0, "unmatchedRows": 0, "maxAgeSeconds": None}
    )
    assert result["status"] == "MEASURED_FAIL"
    assert "bound" in result["reason"]


def test_o14_stale_or_unmatched_rows_fail():
    assert (
        collector.evaluate_measurement_freshness(
            {"verifiedRows": 5, "staleRows": 1, "unmatchedRows": 0, "maxAgeSeconds": 86_400}
        )["status"]
        == "MEASURED_FAIL"
    )
    assert (
        collector.evaluate_measurement_freshness(
            {"verifiedRows": 5, "staleRows": 0, "unmatchedRows": 1, "maxAgeSeconds": 86_400}
        )["status"]
        == "MEASURED_FAIL"
    )


def test_o14_no_verified_row_is_not_a_pass():
    result = collector.evaluate_measurement_freshness(
        {"verifiedRows": 0, "staleRows": 0, "unmatchedRows": 0, "maxAgeSeconds": 86_400}
    )
    assert result["status"] == "NOT_OBSERVED"
    assert result["maxAgeSeconds"] == 86_400


def test_o14_records_the_bound_it_judged_with():
    result = collector.evaluate_measurement_freshness(
        {"verifiedRows": 3, "staleRows": 0, "unmatchedRows": 0, "maxAgeSeconds": 600}
    )
    assert result["status"] == "MEASURED_PASS"
    assert result["maxAgeSeconds"] == 600


# ------------------------------------------------- the verdict cannot be forged


def test_one_failure_makes_the_whole_verdict_fail():
    evidence = _evidence(
        enforcement={
            "checkPresent": True,
            "checkMatchesExpected": False,
            "checkValidated": True,
            "fkPresent": True,
            "fkMatchesExpected": True,
            "fkValidated": True,
            "nonOwnerUpdateGrantCount": 0,
        }
    )
    assert evidence["observations"]["O11_PRIME"]["status"] == "MEASURED_FAIL"
    assert evidence["verdict"] == "FAIL"
    assert evidence["acceptanceClaim"] is False


def test_an_unknown_status_is_a_defect_not_a_pass():
    with pytest.raises(ValueError):
        shared.overall_verdict({"O1": {"status": "PROBABLY_FINE"}}, ("O1",))


def test_pass_requires_every_registered_observation():
    all_pass = {key: {"status": "MEASURED_PASS"} for key in collector.REQUIRED_OBSERVATIONS}
    assert shared.overall_verdict(all_pass, collector.REQUIRED_OBSERVATIONS) == "PASS"
    one_short = deepcopy(all_pass)
    one_short["O8"] = {"status": "NOT_OBSERVED"}
    assert shared.overall_verdict(one_short, collector.REQUIRED_OBSERVATIONS) == "NOT_OBSERVED"


@pytest.mark.parametrize("key", ["O1", "O12"])
def test_validation_refuses_a_net_change_observation_that_claims_a_pass(key):
    evidence = _evidence()
    evidence["observations"][key] = {"status": "MEASURED_PASS"}
    evidence["verdict"] = shared.overall_verdict(
        evidence["observations"], collector.REQUIRED_OBSERVATIONS
    )
    evidence["acceptanceClaim"] = evidence["verdict"] == "PASS"
    with pytest.raises(ValueError, match="net-change"):
        collector.validate_evidence(evidence)


def test_validation_refuses_o8_passing_without_a_threshold():
    evidence = _evidence()
    evidence["observations"]["O8"] = {"status": "MEASURED_PASS"}
    evidence["verdict"] = shared.overall_verdict(
        evidence["observations"], collector.REQUIRED_OBSERVATIONS
    )
    evidence["acceptanceClaim"] = evidence["verdict"] == "PASS"
    with pytest.raises(ValueError, match="threshold"):
        collector.validate_evidence(evidence)


@pytest.mark.parametrize("key", ["O3", "O5", "O9", "O10", "O13"])
def test_validation_refuses_an_external_observation_that_stops_saying_so(key):
    evidence = _evidence()
    evidence["observations"][key] = {"status": "NOT_OBSERVED", "reason": "quietly reclassified"}
    with pytest.raises(ValueError, match="external precondition"):
        collector.validate_evidence(evidence)


def test_validation_refuses_a_hand_written_verdict():
    evidence = _evidence()
    evidence["verdict"] = "PASS"
    evidence["acceptanceClaim"] = True
    with pytest.raises(ValueError, match="recomputed"):
        collector.validate_evidence(evidence)


def test_validation_refuses_an_acceptance_claim_without_a_pass():
    evidence = _evidence()
    evidence["acceptanceClaim"] = True
    with pytest.raises(ValueError, match="acceptanceClaim"):
        collector.validate_evidence(evidence)


def test_validation_refuses_a_shortened_observation_set():
    evidence = _evidence()
    del evidence["observations"]["O13"]
    with pytest.raises(ValueError):
        collector.validate_evidence(evidence)


def test_validation_refuses_a_rewritten_measured_here_list():
    evidence = _evidence()
    evidence["measuredHere"] = ["O2", "O6", "O11_PRIME", "O14", "O8"]
    with pytest.raises(ValueError, match="measuredHere"):
        collector.validate_evidence(evidence)


def test_validation_refuses_a_dirty_source_tree():
    provenance = _provenance()
    provenance["content_clean_diff"] = False
    with pytest.raises(ValueError, match="clean"):
        collector.build_evidence(
            database=_database(), provenance=provenance, source_env="INV_AUDIT_DSN"
        )


def test_validation_refuses_reversed_source_timestamps():
    database = _database()
    database["sourceFinishedAt"] = "2026-09-28T23:59:00Z"
    with pytest.raises(ValueError, match="reversed"):
        collector.build_evidence(
            database=database, provenance=_provenance(), source_env="INV_AUDIT_DSN"
        )


def test_the_excluded_boundaries_stay_excluded():
    evidence = _evidence()
    evidence["excludedBoundaries"]["O6-http"]["status"] = "MEASURED_PASS"
    with pytest.raises(ValueError, match="O6-http"):
        collector.validate_evidence(evidence)


# ----------------------------------------------------------------- entry points


def test_main_without_a_dsn_is_unavailable_not_a_pass(monkeypatch):
    monkeypatch.delenv("INV_AUDIT_DSN", raising=False)
    assert collector.main(["--dsn-env", "INV_AUDIT_DSN"]) == 2


def test_main_rejects_an_unsafe_label(monkeypatch):
    monkeypatch.setenv("INV_AUDIT_DSN", "postgresql://example/invalid")
    assert collector.main(["--label", "../escape"]) == 2


def test_main_rejects_an_out_of_range_sample_limit(monkeypatch):
    monkeypatch.setenv("INV_AUDIT_DSN", "postgresql://example/invalid")
    assert collector.main(["--o6-limit", "0"]) == 2


def test_exit_codes_never_map_an_unmeasured_verdict_to_zero():
    assert shared.EXIT_BY_VERDICT["NOT_OBSERVED"] == 3
    assert shared.EXIT_BY_VERDICT["FAIL"] == 1
    assert shared.EXIT_BY_VERDICT["PASS"] == 0


def test_the_criteria_binding_names_the_reviewed_document():
    evidence = _evidence()
    assert evidence["criteria"]["version"] == "1.2.0"
    assert evidence["criteria"]["path"].endswith("S09-DB_S10-DB_S10-ST_운영_판정_기준.md")
    assert len(evidence["criteria"]["sourceHead"]) == 40


def test_the_expectation_comes_from_the_migration_not_a_copy():
    shapes = collector.load_enforcement_expectation()
    assert shapes["expected_check"][0] == "c"
    assert "verified_at IS NULL" in shapes["expected_check"][1]
    assert shapes["expected_check"][2] is True
    assert shapes["expected_fk"][0] == "f"
    assert "pg_constraint" in shapes["check_sql"]


# ------------------------------------------------- F1-F3 regressions (card 128 r2)


def test_o2_without_a_recorded_seed_cannot_pass():
    """A sample nobody can redraw is not a measurement."""
    result = collector.evaluate_context_reproducibility(
        {"sampled": 40, "verified": 40, "mismatched": 0, "errored": 0}
    )
    assert result["status"] == "MEASURED_FAIL"
    assert "seed" in result["reason"]


def test_o2_sample_is_ordered_by_a_seeded_digest_not_by_id():
    """Ordering by id would only ever look at the oldest bundles."""
    assert "md5(%(seed)s || b.bundle_id)" in collector.O2_BUNDLE_SQL
    assert "ORDER BY b.bundle_id" not in collector.O2_BUNDLE_SQL
    assert collector.O2_SAMPLE_SEED


def test_o2_pass_carries_the_seed_it_sampled_with():
    result = collector.evaluate_context_reproducibility(
        {
            "sampled": 25,
            "verified": 25,
            "mismatched": 0,
            "errored": 0,
            "sampleSeed": SEED,
            "sampleOrder": "md5(seed || bundle_id)",
        }
    )
    assert result["status"] == "MEASURED_PASS"
    assert result["sampleSeed"] == SEED


def test_o11_prime_fails_when_public_holds_the_update_grant():
    result = collector.evaluate_enforcement_shape(
        {
            "checkPresent": True,
            "checkMatchesExpected": True,
            "checkValidated": True,
            "fkPresent": True,
            "fkMatchesExpected": True,
            "fkValidated": True,
            "nonOwnerUpdateGrantCount": 2,
            "updateGranteesMatchExpected": False,
            "publicUpdateGrant": True,
        }
    )
    assert result["status"] == "MEASURED_FAIL"
    assert "PUBLIC" in result["reason"]


def test_o11_prime_fails_on_an_extra_grantee_even_without_public():
    result = collector.evaluate_enforcement_shape(
        {
            "checkPresent": True,
            "checkMatchesExpected": True,
            "checkValidated": True,
            "fkPresent": True,
            "fkMatchesExpected": True,
            "fkValidated": True,
            "nonOwnerUpdateGrantCount": 2,
            "updateGranteesMatchExpected": False,
            "publicUpdateGrant": False,
        }
    )
    assert result["status"] == "MEASURED_FAIL"
    assert "grantees" in result["reason"]


def test_o11_prime_passes_only_when_the_grantees_match_the_migration():
    result = collector.evaluate_enforcement_shape(
        {
            "checkPresent": True,
            "checkMatchesExpected": True,
            "checkValidated": True,
            "fkPresent": True,
            "fkMatchesExpected": True,
            "fkValidated": True,
            "nonOwnerUpdateGrantCount": 1,
            "updateGranteesMatchExpected": True,
            "publicUpdateGrant": False,
        }
    )
    assert result["status"] == "MEASURED_PASS"
    assert result["grantShapeSource"] == "information_schema.column_privileges"


def test_the_expected_grantee_comes_from_the_migration_grant_statement():
    shapes = collector.load_enforcement_expectation()
    assert shapes["expected_update_grantees"] == ("inv_app",)


def test_o6_and_its_independent_count_share_one_connection_by_construction():
    """The snapshot handle exists so the SQL cannot get a second connection.

    If someone reintroduces a separate engine or psycopg.connect for the count,
    this assertion is the thing that notices.
    """
    import inspect

    source = inspect.getsource(collector.collect_database)
    assert "SnapshotHandle(session)" in source
    assert "psycopg.connect" not in source
    handle_source = inspect.getsource(collector.SnapshotHandle)
    assert "session.connection().connection.driver_connection" in handle_source


def test_o2_refuses_a_seed_the_executor_chose():
    """Recording a seed gives reproducibility, not pre-registration.

    An executor free to pick the seed could try several and submit only the run
    whose sample misses a corrupted bundle; the report would look self-consistent.
    Only the registered seed carries a verdict.
    """
    result = collector.evaluate_context_reproducibility(
        {
            "sampled": 40,
            "verified": 40,
            "mismatched": 0,
            "errored": 0,
            "sampleSeed": "attacker-chosen",
            "sampleOrder": "md5(seed || bundle_id)",
        }
    )
    assert result["status"] == "MEASURED_FAIL"
    assert "pre-registered" in result["reason"]
    assert result["registeredSeed"] == collector.O2_SAMPLE_SEED


def test_the_seed_is_not_an_operator_flag():
    """A flag would make the seed the executor's choice; there must not be one."""
    import argparse

    options = {
        action.option_strings[0]
        for action in collector.parser()._actions
        if isinstance(action, argparse.Action) and action.option_strings
    }
    assert "--o2-seed" not in options
    assert "--o2-limit" in options


# ------------------------- FK shape must be read positionally (train-2 failure)


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeShapeConn:
    """Answers the two shape queries positionally, like the migration does.

    Migration 0054's FK_SHAPE selects two unnamed array_agg columns, so a mapping
    row factory keeps only one of them. This fake returns the ten-element tuple a
    positional read gives, which is what the collector must ask for.
    """

    def __init__(self, fk_row, check_row, grantees=("inv_app",)):
        self.fk_row = fk_row
        self.check_row = check_row
        self.grantees = grantees
        self.positional_calls = 0

    def execute_positional(self, statement, params=None):
        self.positional_calls += 1
        if "pg_get_constraintdef" in statement:
            return _FakeCursor([self.check_row])
        return _FakeCursor([self.fk_row])

    def execute(self, statement, params=None):
        assert "column_privileges" in statement, (
            "shape queries must not be read through the mapping cursor"
        )
        return _FakeCursor([{"grantee": name} for name in self.grantees])


def _expected_rows():
    shapes = collector.load_enforcement_expectation()
    check = shapes["expected_check"]
    fk = shapes["expected_fk"]
    return (
        tuple(fk[:2]) + (list(fk[2]), list(fk[3])) + tuple(fk[4:7]) + (fk[7], fk[8], fk[9]),
        (check[0], check[1], check[2]),
    )


def test_the_fk_shape_is_read_positionally_and_keeps_all_ten_elements():
    fk_row, check_row = _expected_rows()
    conn = _FakeShapeConn(fk_row, check_row)
    summary = collector.read_enforcement_shape(conn)
    assert conn.positional_calls == 2, "both shape queries must use the positional cursor"
    assert summary["fkShapeElementCount"] == 10, (
        "a mapping read collapses the two array_agg columns to nine elements"
    )
    assert summary["fkMatchesExpected"] is True
    assert summary["checkMatchesExpected"] is True
    assert collector.evaluate_enforcement_shape(summary)["status"] == "MEASURED_PASS"


def test_a_genuinely_changed_fk_still_fails():
    """The positional read must not turn the check into a rubber stamp."""
    fk_row, check_row = _expected_rows()
    tampered = list(fk_row)
    tampered[6] = "f"  # confmatchtype: FULL instead of the expected SIMPLE
    summary = collector.read_enforcement_shape(_FakeShapeConn(tuple(tampered), check_row))
    assert summary["fkMatchesExpected"] is False
    assert collector.evaluate_enforcement_shape(summary)["status"] == "MEASURED_FAIL"


def test_a_missing_fk_row_is_reported_as_absent():
    fk_row, check_row = _expected_rows()
    conn = _FakeShapeConn(fk_row, check_row)
    conn.execute_positional = lambda statement, params=None: _FakeCursor([])
    summary = collector.read_enforcement_shape(conn)
    assert summary["fkPresent"] is False
    assert summary["checkPresent"] is False
    assert summary["fkShapeElementCount"] == 0
    assert collector.evaluate_enforcement_shape(summary)["status"] == "MEASURED_FAIL"
