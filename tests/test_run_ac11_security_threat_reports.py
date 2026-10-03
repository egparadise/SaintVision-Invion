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
import re
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


def document(report: dict) -> dict:
    """A measured report with the provenance ``main`` adds, which is what the evaluator reads."""

    class _Args:
        source_run_id = RUN_ID
        source_head_sha = head()

    return {
        **producer._provenance(_Args, producer._utc_now()),
        "threatId": producer.RLS_THREAT_ID,
        "toolFiles": producer.tool_files(producer.RLS_TOOL_PATHS),
        "reportAvailable": report.get("exitCode") != 2,
        **report,
    }


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


# ---------------------------------------------------------------- card 236: the audit seed

REVIEWED_ROW = {
    "rule": "E3", "role": "inv_discovery_issuer", "table": "public.tenants",
    "detail": "2 rows visible with inv.tenant_id unset",
}
AUDIT_ROWS = [
    {"rule": "E3", "role": "inv_audit_reader", "table": "public.audit_events",
     "detail": "4 rows visible with inv.tenant_id unset"},
    {"rule": "E4", "role": "inv_audit_reader", "table": "public.audit_events",
     "detail": "2 rows of other tenants visible"},
    {"rule": "E5", "role": "inv_audit_reader", "table": "public.audit_events",
     "detail": "4 rows visible for an unknown tenant"},
]


AUDIT_READER_ROWS = [
    ("inv_audit_reader", "public.audit_events", rule) for rule in ("E3", "E4", "E5")
]


def reviewed_triples(allowlist=None):
    """(role, table, rule) the **reviewed** allowlist accepts, read from it rather than assumed.

    Card 236 wrote these tests while the audit reader had no reviewed disposition, and asserted
    the verdict that implied (VIOLATIONS / MEASURED_FAIL).  `#333` then reviewed that exception in,
    so the same measurement is a PASS -- and a test that hardcodes either answer breaks whenever
    the review moves.  What is invariant is the **rule**: what the allowlist carries is accepted,
    what it does not carry is a violation.  The expectation is derived from the allowlist here, so
    both decisions are expressible and neither is baked in (카드 243 리허설에서 찾았다).
    """

    entries = (allowlist or APPROVED_ALLOWLIST)["rlsAcceptedDispositions"]
    return {
        (entry["role"], entry["table"], rule) for entry in entries for rule in entry["rules"]
    }


def judged(monkeypatch, rows, *, unverified=()):
    """``rls_report`` over a stubbed evaluation, so the subject is *which* baseline is applied."""

    import collect_rls_evidence as rls

    observation = {
        "roles": {"inv_app": {"present": True}},
        "ground_truth": {"public.audit_events": {"total": {"rows": 4}}},
        "table_census": {"schemas": ["public"], "count": 1, "sha256": "0" * 64,
                         "tables": ["public.audit_events"]},
    }
    monkeypatch.setattr(rls, "collect", lambda *_args, **_kwargs: observation)
    monkeypatch.setattr(rls, "evaluate", lambda _observation: [dict(row) for row in rows])
    monkeypatch.setattr(
        rls, "unverified_identities", lambda _observation: [dict(row) for row in unverified]
    )

    def refuse_superset():
        raise AssertionError(
            "the AC-11 report must be judged by the dispositions it names, not by the "
            "collector's S02-DB superset"
        )

    monkeypatch.setattr(rls, "load_baseline", refuse_superset)
    return producer.rls_report("postgresql://unused", None, APPROVED_ALLOWLIST)


def test_an_exception_the_reviewed_allowlist_does_not_carry_is_a_violation(monkeypatch):
    """Card 236: with ``audit_events`` seeded, this is the difference between FAIL and INVALID_RUN.

    ``baselineAccepted`` says the measurement was judged against the reviewed dispositions, and
    ``evaluate_rls`` refuses any ``accepted`` row outside them -- so judging with the collector's
    four-entry superset made the report claim one thing and do another: the audit reader's three
    real cross-tenant observations were "accepted" by a disposition the axis has never reviewed,
    and the evaluator answered INVALID_RUN, which is neither a PASS nor a FAIL.
    """

    report = judged(monkeypatch, [REVIEWED_ROW, *AUDIT_ROWS])
    reviewed = reviewed_triples()
    expected_violations = [row for row in AUDIT_READER_ROWS if row not in reviewed]
    observed_violations = [
        (row["role"], row["table"], row["rule"]) for row in report["violations"]
    ]
    observed_accepted = [(row["role"], row["table"], row["rule"]) for row in report["accepted"]]

    # The rule, in both directions: nothing outside the reviewed list is accepted, and everything
    # outside it is a violation.
    assert observed_violations == expected_violations
    assert all(row in reviewed for row in observed_accepted)
    assert ("inv_discovery_issuer", "public.tenants", "E3") in observed_accepted
    for row in AUDIT_READER_ROWS:
        assert (row in observed_accepted) == (row in reviewed), row
    # And the verdict follows from that, rather than being written down.
    if expected_violations:
        assert report["verdict"] == "VIOLATIONS" and report["exitCode"] == 1
    else:
        assert report["verdict"] == "PASS" and report["exitCode"] == 0


def test_a_reviewed_disposition_is_still_accepted_with_its_proof(monkeypatch):
    report = judged(monkeypatch, [REVIEWED_ROW])
    assert report["verdict"] == "PASS" and report["exitCode"] == 0
    accepted = report["accepted"][0]
    assert accepted["reason"] == APPROVED_ALLOWLIST["rlsAcceptedDispositions"][0]["proof"]
    assert accepted["since"] == APPROVED_ALLOWLIST["rlsAcceptedDispositions"][0]["disposition"]


def test_every_accepted_row_carries_a_string_reason_and_since(monkeypatch):
    """``apply_baseline`` passes ``since`` through as ``None`` when the entry has none, and the
    evaluator's schema types that field as a string -- so every reviewed disposition has to supply
    one.  The disposition kind is what it says here, because that is the reviewed reason this row
    is accepted at all."""

    report = judged(monkeypatch, [REVIEWED_ROW], unverified=[dict(REVIEWED_ROW, rule="E4")])
    assert len(report["accepted"]) == 2, "the reviewed disposition covers both rows"
    for row in report["accepted"]:
        assert isinstance(row["reason"], str) and row["reason"]
        assert isinstance(row["since"], str) and row["since"]


def test_the_reviewed_baseline_is_exactly_the_reviewed_dispositions():
    baseline = producer.reviewed_baseline(APPROVED_ALLOWLIST)
    assert [(e["role"], e["table"], tuple(e["rules"])) for e in baseline["accepted"]] == [
        (e["role"], e["table"], tuple(e["rules"]))
        for e in APPROVED_ALLOWLIST["rlsAcceptedDispositions"]
    ]
    assert all(isinstance(e["reason"], str) and e["reason"] for e in baseline["accepted"])


def test_a_seed_that_cannot_be_written_makes_the_observation_unavailable(tmp_path, monkeypatch):
    """An empty audit table measures nothing, so a failed seed must not become a pass.

    The disposable database is created and the seed refuses; both reports then say
    ``unavailable`` with exit 2 (``evaluate_rls`` answers NOT_OBSERVED for that pair) rather than
    a verdict over a table nobody wrote to.
    """

    import collect_rls_evidence as rls

    import contextlib

    @contextlib.contextmanager
    def fake_disposable(_admin):
        yield "postgresql://unused", "00000000-0000-0000-0000-000000000000"

    measured: list[str] = []
    monkeypatch.setattr(rls, "disposable_database", fake_disposable)
    monkeypatch.setattr(
        producer, "seed_audit_rows",
        lambda _dsn: (_ for _ in ()).throw(producer.ProducerError("no tenants")),
    )
    monkeypatch.setattr(rls, "collect", lambda *_a, **_k: measured.append("collected") or {})
    code, definer, boundary = run(tmp_path, monkeypatch, admin="postgresql://admin")
    assert code == 2
    assert boundary["exitCode"] == 2 and boundary["status"] == "unavailable"
    assert definer["exitCode"] == 2
    assert measured == [], "nothing is measured once the seed refused"
    assert aggregator.evaluate_rls(boundary, APPROVED_ALLOWLIST, NOW) is aggregator.Verdict.NOT_OBSERVED


def test_the_seed_runs_before_anything_is_measured(tmp_path, monkeypatch):
    import collect_rls_evidence as rls

    import contextlib

    order: list[str] = []

    @contextlib.contextmanager
    def fake_disposable(_admin):
        yield "postgresql://unused", "00000000-0000-0000-0000-000000000000"

    monkeypatch.setattr(rls, "disposable_database", fake_disposable)
    monkeypatch.setattr(producer, "seed_audit_rows", lambda _dsn: order.append("seed") or {
        "table": "public.audit_events", "path": "p", "role": "inv_app",
        "tenants": ["a", "b"], "rowsPerTenant": 2, "crossTenantWriteRefusedWith": "refused",
    })
    monkeypatch.setattr(producer, "definer_report", lambda _dsn: order.append("definer") or
                        {"exitCode": 2, "status": "unavailable"})
    monkeypatch.setattr(producer, "rls_report", lambda *_a, **_k: order.append("rls") or
                        {"exitCode": 2, "status": "unavailable", "baselineAccepted": []})
    run(tmp_path, monkeypatch, admin="postgresql://admin")
    assert order == ["seed", "definer", "rls"]


# ---------------------------------------------------------------- card 236: against a real server


@pytest.fixture(scope="module")
def audit_db():
    """A disposable migrated database with an **empty** ``public.audit_events``."""

    import os

    sys.path.insert(0, str(ROOT / "tools"))
    import collect_rls_evidence as rls

    admin = os.getenv("INV_TEST_ADMIN_DSN")
    if not admin:
        if os.getenv("CI"):
            pytest.fail("CI requires INV_TEST_ADMIN_DSN; DB tests must not be skipped")
        pytest.skip("Set INV_TEST_ADMIN_DSN to a disposable PostgreSQL 16+ test server")

    class Redacted(str):  # pytest prints fixture values on failure: never show the DSN
        def __repr__(self):
            return "<audit_db dsn=redacted>"

    with rls.disposable_database(admin) as (dsn, tenant_a):
        yield Redacted(dsn), tenant_a


@pytest.fixture(scope="module")
def before_and_after(audit_db):
    """The same database measured with the audit table empty and then seeded.

    One fixture, so the two measurements cannot drift apart into two databases -- and so the
    before state cannot be "whatever an earlier test left behind".
    """

    dsn, tenant_a = audit_db
    before = producer.rls_report(str(dsn), tenant_a, APPROVED_ALLOWLIST)
    summary = producer.seed_audit_rows(str(dsn))
    after = producer.rls_report(str(dsn), tenant_a, APPROVED_ALLOWLIST)
    return before, summary, after


def audit_cells(report):
    table = report["roles"]["inv_audit_reader"]["tables"]["public.audit_events"]
    return table["visible"]


def test_an_empty_audit_table_observes_nothing_and_the_axis_says_so(before_and_after):
    """Why this card exists: "the role sees none of the other tenant's rows" over no rows.

    Every visibility cell is 0 because the table is empty, the identity fingerprints are both the
    digest of nothing, and the canonical evaluator answers NOT_OBSERVED -- the axis is not claiming
    a measured boundary, which is correct and is also why nothing here is evidence of isolation.
    """

    before, _summary, _after = before_and_after
    cells = audit_cells(before)
    assert before["ground_truth"]["public.audit_events"] == {
        "total": {"rows": 0}, "tenant_a": {"rows": 0}, "other_tenants": {"rows": 0}
    }
    assert {name: cell.get("rows") for name, cell in cells.items() if name != "identity"} == {
        "guc_unset": 0, "guc_tenant_a": 0, "guc_tenant_a_foreign_rows": 0,
        "guc_unknown_tenant": 0, "guc_not_uuid": 0,
    }
    assert cells["identity"]["owner_a"]["rows"] == 0 and cells["identity"]["role_a"]["rows"] == 0


def test_the_seed_writes_two_tenants_through_the_product_writers(before_and_after, audit_db):
    """Two tenants, two rows each, by ``record_denial_out_of_band`` and ``record_event``."""

    import psycopg

    dsn, _tenant_a = audit_db
    _before, summary, _after = before_and_after
    assert summary["role"] == producer.APP_ROLE
    assert len(summary["tenants"]) == 2 and summary["rowsPerTenant"] == 2
    with psycopg.connect(str(dsn)) as conn:
        rows = conn.execute(
            "SELECT tenant_id::text, outcome, action, actor_type FROM public.audit_events "
            "ORDER BY tenant_id, outcome"
        ).fetchall()
    assert len(rows) == 4
    assert sorted({row[0] for row in rows}) == sorted(summary["tenants"])
    assert sorted({row[1] for row in rows}) == ["allow", "deny"]
    assert all(row[3] == "user" for row in rows), "the product writes a principal's audit row"
    assert all(row[2].startswith(("GET /v1/", "POST /v1/")) for row in rows)


def test_the_seed_is_not_a_bypass(before_and_after, audit_db):
    """The policy -- not the seed -- is what admitted those rows.

    Three refusals, all from the database: another tenant's row under this tenant's scope, a row
    with **no** scope set at all, and the application reading what it wrote (0047 revoked SELECT).
    If any of them succeeded, the rows measured afterwards would be rows no policy ever checked.
    """

    import datetime as _dt
    import uuid as _uuid

    import psycopg
    from sqlalchemy import text as _text
    from sqlalchemy.exc import DBAPIError
    from sqlalchemy.orm import sessionmaker

    sys.path.insert(0, str(ROOT / "src"))
    from saintvision.services.audit import record_event

    dsn, _tenant_a = audit_db
    _before, summary, _after = before_and_after
    assert "row-level security" in summary["crossTenantWriteRefusedWith"]

    engine = producer._app_engine(str(dsn))
    try:
        factory = sessionmaker(bind=engine, expire_on_commit=False)
        # No scope at all: the WITH CHECK compares tenant_id with an unset GUC.
        with pytest.raises(DBAPIError, match="row-level security"):
            with factory() as session:
                with session.begin():
                    record_event(
                        session, now=_dt.datetime.now(_dt.timezone.utc), actor_type="system",
                        action="ac11.audit_seed.unscoped_probe", outcome="deny",
                        tenant_id=_uuid.UUID(summary["tenants"][0]), reason_code="AC11-SEED-PROBE",
                    )
        # And the application cannot read the table it appends to.
        with pytest.raises(DBAPIError, match="permission denied"):
            with engine.begin() as connection:
                connection.execute(_text("SELECT count(*) FROM public.audit_events"))
    finally:
        engine.dispose()

    with psycopg.connect(str(dsn)) as conn:
        assert conn.execute(
            "SELECT count(*) FROM public.audit_events WHERE tenant_id IS NULL"
        ).fetchone()[0] == 0, "the seed adds no tenant-less row"
        assert conn.execute("SELECT count(*) FROM public.audit_events").fetchone()[0] == 4, (
            "the refused probes left nothing behind"
        )


def test_the_seeded_table_makes_the_cross_tenant_comparison_real(before_and_after):
    """What the card asked for: the comparison now has rows on both sides.

    The owner sees tenant A's two rows; ``inv_audit_reader`` sees all four, of which two belong to
    the other tenant -- so E3/E4/E5 are statements about rows that exist, and the identity
    fingerprints differ instead of both being the digest of nothing.
    """

    _before, _summary, after = before_and_after
    cells = audit_cells(after)
    assert after["ground_truth"]["public.audit_events"] == {
        "total": {"rows": 4}, "tenant_a": {"rows": 2}, "other_tenants": {"rows": 2}
    }
    assert cells["guc_unset"]["rows"] == 4
    assert cells["guc_tenant_a_foreign_rows"]["rows"] == 2
    identity = cells["identity"]
    assert identity["owner_a"]["rows"] == 2 and identity["role_a"]["rows"] == 4
    assert identity["match"] is False
    assert identity["owner_a"]["fp"] != identity["role_a"]["fp"]


def test_the_axis_now_measures_a_verdict_instead_of_observing_nothing(before_and_after):
    """NOT_OBSERVED before, MEASURED_FAIL after -- and the three rows name why.

    The failure is the audit reader's cross-tenant SELECT, which 0047 grants on purpose and the
    S02-DB baseline excepts with its reason -- but the **reviewed** AC-11 dispositions do not carry
    that exception.  Adding it is a review decision on the axis's source document, so this card
    measures and reports rather than deciding (card 236 Codex decision request #1).
    """

    before, _summary, after = before_and_after
    before_document = document(before)
    after_document = document(after)
    assert aggregator.rls_report_shape(before_document) is None
    assert aggregator.rls_report_shape(after_document) is None
    assert aggregator.evaluate_rls(before_document, APPROVED_ALLOWLIST, NOW) is (
        aggregator.Verdict.NOT_OBSERVED
    )
    reviewed = reviewed_triples()
    expected_violations = [row for row in AUDIT_READER_ROWS if row not in reviewed]
    # Whether this is a FAIL or a PASS is the reviewed allowlist's decision, not this test's.
    # What the seed changed is that the comparison is **measured** at all: before it, the axis
    # said NOT_OBSERVED over an empty table.
    expected = (
        aggregator.Verdict.MEASURED_FAIL if expected_violations else aggregator.Verdict.MEASURED_PASS
    )
    assert aggregator.evaluate_rls(after_document, APPROVED_ALLOWLIST, NOW) is expected
    assert [(row["role"], row["table"], row["rule"]) for row in after["violations"]] == (
        expected_violations
    )


@pytest.fixture
def fresh_audit_db():
    """A disposable migrated database of this test's own, because it ends up with extra rows."""

    import os

    sys.path.insert(0, str(ROOT / "tools"))
    import collect_rls_evidence as rls

    admin = os.getenv("INV_TEST_ADMIN_DSN")
    if not admin:
        if os.getenv("CI"):
            pytest.fail("CI requires INV_TEST_ADMIN_DSN; DB tests must not be skipped")
        pytest.skip("Set INV_TEST_ADMIN_DSN to a disposable PostgreSQL 16+ test server")
    with rls.disposable_database(admin) as (dsn, _tenant_a):
        yield dsn


def test_a_seed_the_policy_did_not_check_is_refused(fresh_audit_db):
    """If the write is not policy-enforced, no visibility measurement is recorded.

    ``_prove_policy_enforced`` writes the *other* tenant's row under this tenant's scope and
    requires the database to refuse it.  Here it is handed an engine that is **not** the
    application role -- the DSN that created the database -- so on a server where that role
    bypasses RLS the write succeeds, and the producer must refuse the whole observation rather
    than measure rows no policy ever checked.
    """

    import datetime as _dt

    import psycopg
    from psycopg.conninfo import conninfo_to_dict
    from sqlalchemy import create_engine
    from sqlalchemy.engine import URL
    from sqlalchemy.pool import NullPool

    with psycopg.connect(fresh_audit_db) as conn:
        bypasses = conn.execute(
            "SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user"
        ).fetchone()[0]
        tenants = [
            str(row[0]) for row in conn.execute(
                "SELECT tenant_id::text FROM public.tenants ORDER BY tenant_id"
            ).fetchall()
        ]
    if not bypasses:
        pytest.skip("this server's owner is subject to RLS, so it cannot demonstrate a bypass")

    info = conninfo_to_dict(fresh_audit_db)
    owner_engine = create_engine(
        URL.create(
            "postgresql+psycopg", username=info.get("user"), password=info.get("password"),
            host=info.get("host"), port=int(info.get("port", 5432)), database=info.get("dbname"),
        ),
        future=True, poolclass=NullPool,
    )
    try:
        with pytest.raises(producer.ProducerError, match="not policy-enforced"):
            producer._prove_policy_enforced(
                owner_engine, tenants[0], tenants[1], _dt.datetime.now(_dt.timezone.utc)
            )
    finally:
        owner_engine.dispose()


def test_a_seed_that_wrote_something_other_than_what_it_says_is_refused(
    fresh_audit_db, monkeypatch
):
    """The owner counts the rows, and the count has to be the one the seed claims.

    Patched to claim three rows per tenant while the two product writers still write two, the
    verification refuses -- so a seed that half-wrote cannot be measured as though it had written
    what it meant to.
    """

    monkeypatch.setattr(producer, "AUDIT_SEED_ROWS_PER_TENANT", 3)
    with pytest.raises(producer.ProducerError, match="not what was written"):
        producer.seed_audit_rows(fresh_audit_db)


# ------------------------------------------------- #334 r1: which refusal counts as the proof

MEASURED_REFUSAL = 'new row violates row-level security policy for table "audit_events"'


def pg_error(sqlstate: str, message: str):
    """A psycopg error of that SQLSTATE, the way the driver raises it."""

    import psycopg

    return psycopg.errors.lookup(sqlstate)(message)


def test_the_measured_postgres_refusal_is_the_proof():
    """The exact words and SQLSTATE measured against PostgreSQL 16 with 0047's policy."""

    assert producer.rls_refusal(
        pg_error(producer.RLS_REFUSAL_SQLSTATE, MEASURED_REFUSAL),
        producer.AUDIT_SEED_TABLE, producer.AUDIT_SEED_POLICY,
    ) == MEASURED_REFUSAL


def test_a_refusal_that_names_the_policy_is_also_the_proof():
    """PostgreSQL names the policy in some versions; then it has to be the reviewed one."""

    named = (
        'new row violates row-level security policy "audit_events_tenant_isolation" '
        'for table "audit_events"'
    )
    assert producer.rls_refusal(
        pg_error(producer.RLS_REFUSAL_SQLSTATE, named),
        producer.AUDIT_SEED_TABLE, producer.AUDIT_SEED_POLICY,
    ) == named


@pytest.mark.parametrize(
    ("label", "sqlstate", "message", "reason"),
    [
        ("another sqlstate", "42P01", 'relation "audit_events" does not exist',
         "not a row-level security refusal"),
        ("a different 42501", "42501", "permission denied for table audit_events",
         "not with PostgreSQL's row-level security wording"),
        ("another table", "42501",
         'new row violates row-level security policy for table "projects"',
         "names table 'projects'"),
        ("another policy", "42501",
         'new row violates row-level security policy "something_else" for table "audit_events"',
         "names policy 'something_else'"),
    ],
    ids=["other-sqlstate", "other-42501", "other-table", "other-policy"],
)
def test_an_error_that_is_not_that_refusal_is_not_a_proof(label, sqlstate, message, reason):
    """#334 r1: any ``DBAPIError`` counted as "the policy refused", so an unenforced seed passed."""

    with pytest.raises(producer.ProducerError, match=re.escape(reason)):
        producer.rls_refusal(
            pg_error(sqlstate, message), producer.AUDIT_SEED_TABLE, producer.AUDIT_SEED_POLICY
        )


def test_a_connection_failure_is_not_a_proof_and_is_not_quoted():
    """A dropped connection is not a policy decision, and its message can carry host and user."""

    import psycopg

    error = psycopg.OperationalError("connection failed: host=db.internal user=invowner")
    with pytest.raises(producer.ProducerError) as refused:
        producer.rls_refusal(error, producer.AUDIT_SEED_TABLE, producer.AUDIT_SEED_POLICY)
    assert "OperationalError" in str(refused.value) and "sqlstate=None" in str(refused.value)
    for secret in ("db.internal", "invowner", "connection failed"):
        assert secret not in str(refused.value)


def test_a_sqlite_engine_cannot_prove_that_a_policy_checked_anything(tmp_path):
    """The probe end to end against an engine that has no row-level security at all.

    This is the case Codex found: ``_prove_policy_enforced`` caught ``DBAPIError`` and called it a
    refusal, so a sqlite engine -- which fails for an entirely different reason and has no policies
    -- certified the seed as policy-enforced.
    """

    import datetime as _dt

    from sqlalchemy import create_engine

    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'probe.sqlite'}", future=True)
    try:
        with pytest.raises(producer.ProducerError, match="not a row-level security refusal|"
                                                        "row-level security wording"):
            producer._prove_policy_enforced(
                engine,
                "00000000-0000-0000-0000-000000000001",
                "00000000-0000-0000-0000-000000000002",
                _dt.datetime.now(_dt.timezone.utc),
            )
    finally:
        engine.dispose()
