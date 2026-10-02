"""The database threat-report producer, without a database.

Every test here is about the fail-closed path, because that is the path a hosted lane takes on
a bad day: no PostgreSQL, an unreachable DSN, a tool that moved.  The measured paths need a
live catalogue and are exercised by the lane itself (card 221 records that run).  What must
hold here is that an observation nobody could make is *written as unavailable* -- never as an
empty passing inventory, which is how "no privileged function is unsafe" would come to mean
"nobody looked".
"""

from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import aggregate_ac11_evidence as aggregator  # noqa: E402
import run_ac11_security_threat_reports as producer  # noqa: E402

RUN_ID = "36953462883"
NOW = dt.datetime(2026, 10, 2, 3, 0, tzinfo=dt.timezone.utc)
APPROVED_ALLOWLIST = json.loads(
    (ROOT / aggregator.ALLOWLIST_REPO_PATH).read_text(encoding="utf-8")
)


def head() -> str:
    done = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=20
    )
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


def run(tmp_path, monkeypatch, *, dsn: str | None = None, admin: str | None = None):
    if admin is None:
        monkeypatch.delenv("INV_TEST_ADMIN_DSN", raising=False)
    else:
        monkeypatch.setenv("INV_TEST_ADMIN_DSN", admin)
    argv = [
        "--source-run-id", RUN_ID,
        "--source-head-sha", head(),
        "--output-dir", str(tmp_path),
    ]
    if dsn is not None:
        argv += ["--dsn", dsn]
    code = producer.main(argv)
    definer = json.loads((tmp_path / producer.DEFINER_MEMBER).read_text(encoding="utf-8"))
    boundary = json.loads((tmp_path / producer.RLS_MEMBER).read_text(encoding="utf-8"))
    return code, definer, boundary


def test_without_a_database_both_reports_are_unavailable_rather_than_passing(tmp_path, monkeypatch):
    code, definer, boundary = run(tmp_path, monkeypatch)
    assert code == 2
    assert definer["threatId"] == "SEC-DEF-001"
    assert definer["status"] == "unavailable"
    assert definer["exitCode"] == 2
    assert definer["unsafe"] is None
    assert definer["reportAvailable"] is False
    assert "functions" not in definer, "an unavailable observation has no inventory"
    assert boundary["threatId"] == "SEC-RLS-001"
    assert boundary["exitCode"] == 2
    assert boundary["reportAvailable"] is False
    assert "violations" not in boundary


def test_the_canonical_evaluators_read_the_unavailable_pair_as_not_observed(tmp_path, monkeypatch):
    """The aggregator's own words for this pair: ``exitCode 2`` plus ``status unavailable``.

    Any other use of exit 2 is INVALID_RUN there, so the producer has to say both -- which is
    the reason this test asks the evaluator rather than the document.
    """

    _code, definer, boundary = run(tmp_path, monkeypatch)
    assert aggregator.evaluate_definer(definer, APPROVED_ALLOWLIST) is aggregator.Verdict.NOT_OBSERVED
    assert aggregator.evaluate_rls(boundary, APPROVED_ALLOWLIST, NOW) is aggregator.Verdict.NOT_OBSERVED


def test_an_unreachable_database_is_also_unavailable(tmp_path, monkeypatch):
    """A refused connection must not become a clean inventory."""

    code, definer, boundary = run(
        tmp_path, monkeypatch, dsn="postgresql://nobody@127.0.0.1:1/none?connect_timeout=1"
    )
    assert code == 2
    assert definer["status"] == "unavailable"
    assert definer["error"] == "catalog_observation_failed"
    assert boundary["exitCode"] == 2
    assert boundary["error"] == "boundary_observation_failed"


def test_both_reports_pin_the_tools_that_ran(tmp_path, monkeypatch):
    _code, definer, boundary = run(tmp_path, monkeypatch)
    assert definer["toolFiles"] == [dict(row) for row in aggregator.DEFINER_FILES]
    assert boundary["toolFiles"] == [dict(row) for row in aggregator.RLS_FILES]


def test_the_rls_report_states_the_reviewed_baseline_it_was_judged_against(tmp_path, monkeypatch):
    """The aggregator compares this with the reviewed allowlist exactly.

    The collector's own baseline file is a superset maintained for the S02-DB lane, so copying
    *that* would make every report INVALID_RUN; the reviewed dispositions are what the axis
    means by an accepted exception.
    """

    _code, _definer, boundary = run(tmp_path, monkeypatch)
    assert boundary["baselineAccepted"] == [
        {"role": entry["role"], "table": entry["table"], "rules": list(entry["rules"])}
        for entry in APPROVED_ALLOWLIST["rlsAcceptedDispositions"]
    ]


@pytest.mark.parametrize("member", ["DEFINER_MEMBER", "RLS_MEMBER"])
def test_no_report_carries_connection_material(tmp_path, monkeypatch, member):
    run(tmp_path, monkeypatch, dsn="postgresql://user:hunter2@127.0.0.1:1/none?connect_timeout=1")
    text = (tmp_path / getattr(producer, member)).read_text(encoding="utf-8")
    for secret in ("hunter2", "postgresql://", "password"):
        assert secret not in text


def test_the_reports_are_bound_to_the_run_and_the_source_tree(tmp_path, monkeypatch):
    _code, definer, boundary = run(tmp_path, monkeypatch)
    expected_tree = subprocess.run(
        ["git", "rev-parse", "HEAD^{tree}"], cwd=ROOT, capture_output=True, text=True, timeout=20
    ).stdout.strip()
    for document in (definer, boundary):
        assert document["sourceRunId"] == RUN_ID
        assert document["sourceHeadSha"] == head()
        assert document["checkoutTreeSha"] == expected_tree
        assert document["runPurpose"] == producer.RUN_PURPOSE


def test_a_head_that_is_not_in_this_repository_is_refused(tmp_path, monkeypatch):
    monkeypatch.delenv("INV_TEST_ADMIN_DSN", raising=False)
    with pytest.raises(producer.ProducerError, match="tree of the source head"):
        producer.main([
            "--source-run-id", RUN_ID,
            "--source-head-sha", "f" * 40,
            "--output-dir", str(tmp_path),
        ])


def test_the_boundary_is_measured_over_the_collector_s_own_role_population(monkeypatch):
    """Asking fewer roles changes the verdict, so the population is the collector's, not ours.

    Measured on this tree: with the collector's eight roles the boundary comes out UNMEASURED,
    because one row's identity cannot be verified for ``inv_cancel_bridge_owner``; with a
    two-role list that row is never asked about and the same database answers PASS.  A verdict
    obtained by asking less is not this axis's measurement, so the producer reads
    ``collect_rls_evidence.DEFAULT_ROLES`` instead of carrying a list of its own.
    """

    import collect_rls_evidence as rls

    seen: dict[str, object] = {}

    def fake_collect(dsn, roles, tenant):
        seen["roles"] = roles
        return {
            "roles": {"inv_app": {"present": True}},
            "ground_truth": {"public.projects": {"tenantScoped": True}},
            # The census travels with the report (#322 r2 F-R7), so the stub carries one too --
            # this test is about which roles were asked, and the producer copies both through.
            "table_census": {"schemas": ["inv", "public"], "count": 1,
                             "sha256": "0" * 64, "tables": ["public.projects"]},
            "definer_functions": [],
        }

    monkeypatch.setattr(rls, "collect", fake_collect)
    monkeypatch.setattr(rls, "evaluate", lambda observation: [])
    monkeypatch.setattr(rls, "unverified_identities", lambda observation: [])
    report = producer.rls_report("postgresql://unused", None, APPROVED_ALLOWLIST)
    assert seen["roles"] == rls.DEFAULT_ROLES
    assert len(rls.DEFAULT_ROLES) == 8
    assert report["measuredRoles"] == list(rls.DEFAULT_ROLES)
    assert report["table_census"]["tables"] == ["public.projects"]
    assert report["exitCode"] == 0 and report["verdict"] == "PASS"
