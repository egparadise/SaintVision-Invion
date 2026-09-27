"""S03-DB AC-03 acceptance evidence runner: PG-free unit tests plus one real-PG run."""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path

import pytest

from tools import collect_s03_acceptance_evidence as tool

REPO_ROOT = Path(__file__).resolve().parents[1]


def _junit(cases: dict[str, str]) -> bytes:
    body = []
    for case_id, outcome in cases.items():
        classname, name = case_id.split("::")
        inner = {"failed": '<failure message="postgresql://u:secret-pw@h/db">x</failure>',
                 "error": "<error>e</error>", "skipped": '<skipped message="s"/>'}.get(outcome, "")
        body.append(f'<testcase classname="{classname}" name="{name}" time="0.1">{inner}</testcase>')
    return (f'<?xml version="1.0"?><testsuites><testsuite name="pytest" tests="{len(cases)}">'
            f'{"".join(body)}</testsuite></testsuites>').encode()


def _all_cases() -> dict[str, str]:
    return {case: "passed" for spec in tool.AC03_CLAUSES.values() for case in spec["cases"]}


# --------------------------------------------------------------------------
# Reuse contract
# --------------------------------------------------------------------------


def test_every_mapped_case_exists_in_its_file_and_is_unique():
    mapped = [case for spec in tool.AC03_CLAUSES.values() for case in spec["cases"]]
    assert len(mapped) == len(set(mapped))
    missing = []
    for case in mapped:
        module, name = case.split("::")
        path = REPO_ROOT / (module.replace(".", "/") + ".py")
        defined = {n.name for n in ast.parse(path.read_text(encoding="utf-8-sig")).body
                   if isinstance(n, ast.FunctionDef)}
        if name not in defined:
            missing.append(case)
    assert not missing, missing
    assert len(mapped) == 27


def test_every_mapped_module_is_covered_by_a_pg_only_suite_and_containment_is_docker_lane_only():
    modules = {case.split("::")[0].replace(".", "/") + ".py"
               for spec in tool.AC03_CLAUSES.values() for case in spec["cases"]}
    covered = {path for spec in tool.SUITES for path in spec["paths"]}
    assert modules <= covered, modules - covered
    assert "tests/integration/test_containment.py" not in covered
    assert tool.DOCKER_LANE_SUITE["paths"] == ["tests/integration/test_containment.py"]
    assert tool.DOCKER_LANE_SUITE["docker"] is True
    assert not any("test_containment" in case for spec in tool.AC03_CLAUSES.values() for case in spec["cases"])


def test_docker_lane_defaults_to_not_run_and_keeps_partial_verdict():
    evidence = tool.build_evidence(provenance=_prov(), suites=[_suite()],
                                   lanes=_lanes(verdict="PASS", db=True, container=True))
    assert evidence["dockerLane"]["status"] == "not_run" and evidence["dockerLane"]["value"] is None
    assert evidence["verdict"] == "PASS_MEASURED_PARTIAL"
    measured = {**tool.DOCKER_LANE_NOT_RUN, "status": "complete", "suite_result": _suite()}
    evidence = tool.build_evidence(provenance=_prov(), suites=[_suite()],
                                   lanes=_lanes(verdict="PASS", db=True, container=True), docker_lane=measured)
    assert evidence["verdict"] == "PASS"
    assert "outcomes" not in evidence["dockerLane"]["suite_result"]


def test_unmapped_failure_in_any_suite_fails_closed():
    """Revival: 27 mapped pass + one unmapped failed case in a suite → FAIL, never PARTIAL/PASS."""
    outcomes = {**_all_cases(), "tests.test_execution::test_retry_budget_is_enforced": "failed"}
    suite = _suite(status="failed", outcomes=outcomes, exit_code=1)
    suite["counts"] = {"passed": 27, "failed": 1, "error": 0, "skipped": 0}
    evidence = tool.build_evidence(provenance=_prov(), suites=[suite],
                                   lanes=_lanes(verdict="PASS", db=True, container=True,
                                                violations={"C1": 0, "C2": 0, "C3": 0, "C4": 0}))
    assert {c["status"] for c in evidence["clauses"].values()} == {"pass"}
    assert evidence["verdict"] == "FAIL"


@pytest.mark.parametrize("sample", [
    "inv_s03_" + "a" * 32, "inv_rls_" + "b" * 32, "inv_backend_test_" + "c" * 32,
    "ff5d8e54-3ac6-4fbb-924e-a7f2f88bbf53", "run_01HZZZZZZZZZZZZZZZZZZZZZZZ", "lse_01J00000000000000000000000",
    "evd_01HZZZZZZZZZZZZZZZZZZZZZZZ", "192.168.45.74:18443",
])
def test_sanitizer_replaces_each_identifier_class_and_negative_guard_refuses(sample, tmp_path):
    assert sample not in tool.redact_text(f"x {sample} y")
    with pytest.raises(ValueError, match="unredacted"):
        tool.assert_redacted(f"x {sample} y")
    evidence = tool.build_evidence(provenance=_prov(), suites=[_suite()], lanes=_lanes(), note=f"raw {sample}")
    with pytest.raises(ValueError, match="unredacted"):
        tool.write_evidence(evidence, tmp_path, "raw")


def test_lane_artifacts_are_rewritten_in_place_with_placeholders(tmp_path):
    raw = {"db": {"name": "inv_s03_" + "d" * 32, "runs": [{"run_id": "run_01HZZZZZZZZZZZZZZZZZZZZZZZ",
           "tenant_id": "ff5d8e54-3ac6-4fbb-924e-a7f2f88bbf53"}]},
           "container": {"probes": [{"stdout_head": "probe-stdout\n", "sqlState": "55P03"}]}, "git_sha": "1e8baf04"}
    (tmp_path / "l.json").write_text(json.dumps(raw), encoding="utf-8")
    (tmp_path / "l.md").write_text("db inv_s03_" + "d" * 32 + " run run_01HZZZZZZZZZZZZZZZZZZZZZZZ at 10.0.0.1:5432\n",
                                   encoding="utf-8")
    summary = tool.redact_lane_artifacts(tmp_path, "l")
    assert summary["redacted"] is True and summary["rawJsonSha256"] != summary["jsonSha256"]
    redacted = json.loads((tmp_path / "l.json").read_text(encoding="utf-8"))
    assert redacted["db"]["name"] == "inv_disposable_<redacted>"
    assert redacted["db"]["runs"][0] == {"run_id": "<id:redacted>", "tenant_id": "<uuid:redacted>"}
    assert redacted["container"]["probes"][0] == {"stdout_head": "probe-stdout\n", "sqlState": "55P03"}
    assert redacted["git_sha"] == "1e8baf04"
    for name in ("l.json", "l.md"):
        tool.assert_redacted((tmp_path / name).read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# JUnit and clause rules
# --------------------------------------------------------------------------


def test_parse_junit_keeps_worst_outcome_per_parametrized_case_and_no_failure_text():
    raw = _junit({"tests.x::test_a[1]": "passed"}).replace(b"</testsuite>",
        b'<testcase classname="tests.x" name="test_a[2]"><failure message="postgresql://u:secret-pw@h/db">x</failure></testcase></testsuite>')
    parsed = tool.parse_junit(raw)
    assert parsed["outcomes"] == {"tests.x::test_a": "failed"}
    assert parsed["counts"] == {"passed": 1, "failed": 1, "error": 0, "skipped": 0}
    assert "secret-pw" not in json.dumps(parsed)


@pytest.mark.parametrize("mutate, expected", [
    ({}, "pass"),
    ({"tests.test_execution::test_the_database_refuses_a_success_without_evidence": "failed"}, "fail"),
    ({"tests.test_execution::test_the_database_refuses_a_success_without_evidence": "skipped"}, "not_run"),
    ({"tests.test_execution::test_the_database_refuses_a_success_without_evidence": None}, "not_run"),
])
def test_clause_pass_requires_every_case_passed(mutate, expected):
    cases = _all_cases()
    for case, outcome in mutate.items():
        cases.pop(case) if outcome is None else cases.__setitem__(case, outcome)
    outcomes = tool.parse_junit(_junit(cases))["outcomes"]
    zeros = {"C1": 0, "C2": 0, "C3": 0, "C4": 0}  # a measured lane states every rule explicitly
    clause = tool.evaluate_clauses(outcomes, zeros, db_measured=True)["evidence-id-and-output-hash-enforced"]
    assert clause["status"] == expected


def test_db_lane_violation_fails_the_owning_clause_only():
    outcomes = tool.parse_junit(_junit(_all_cases()))["outcomes"]
    clauses = tool.evaluate_clauses(outcomes, {"C1": 0, "C2": 1, "C3": 0, "C4": 0}, db_measured=True)
    assert clauses["evidence-id-and-output-hash-enforced"]["status"] == "fail"
    assert clauses["evidence-id-and-output-hash-enforced"]["dbLaneRules"] == {"C2": 1, "C3": 0}
    assert clauses["resources-reclaimed-after-exit"]["status"] == "pass"
    assert clauses["allowed-execution-succeeds"]["status"] == "pass"


# --------------------------------------------------------------------------
# Verdicts
# --------------------------------------------------------------------------


def _suite(status="complete", outcomes=None, exit_code=0):
    return {"id": "all", "paths": ["x"], "select": None, "postgres": True, "exitCode": exit_code,
            "elapsedSeconds": 1.0, "junitSha256": "0" * 64,
            "counts": {"passed": 28, "failed": 0, "error": 0, "skipped": 0},
            "outcomes": tool.parse_junit(_junit(outcomes or _all_cases()))["outcomes"], "status": status}


def _lanes(verdict="UNMEASURED", db=False, container=False, violations=None, status="complete"):
    if violations is None:  # a measured lane states every judged rule explicitly; {} stays {} when passed
        violations = {"C1": 0, "C2": 0, "C3": 0, "C4": 0} if db else {}
    return {"status": status, "verdict": verdict, "exitCode": {"PASS": 0, "VIOLATIONS": 1, "UNAVAILABLE": 2,
            "UNMEASURED": 3}[verdict], "ledgerSource": "empty-disposable-database", "evidenceJson": "l.json",
            "db": {"measured": db, "runs": 0, "leases": 0}, "container": {"measured": container, "probes": 0,
            "reason": None if container else "docker unavailable"}, "violationsByRule": violations}


def _prov():
    return {"commit_sha": "a" * 40, "branch": "b", "integration_ref": "o", "integration_sha": "a" * 40,
            "integration_check_mode": "local", "working_tree_clean_status": True, "content_clean_diff": True,
            "modified_paths": [], "interpreter": "py", "runtime_python": "3.14", "timestamp_kst": "t",
            "executor": "Claude", "os_platform": "win"}


@pytest.mark.parametrize("suite_kwargs, lanes_kwargs, expected", [
    ({}, {}, "PASS_MEASURED_PARTIAL"),
    ({}, {"verdict": "PASS", "db": True, "container": True}, "PASS_MEASURED_PARTIAL"),  # docker lane not run
    ({}, {"verdict": "PASS", "db": True, "container": False}, "PASS_MEASURED_PARTIAL"),
    ({"outcomes": {**_all_cases(), "tests.test_run_state::test_the_happy_path_is_walkable": "failed"}}, {}, "FAIL"),
    ({}, {"verdict": "VIOLATIONS", "db": True, "violations": {"C1": 2}}, "FAIL"),
    ({"outcomes": {**_all_cases(), "tests.test_run_state::test_the_happy_path_is_walkable": "skipped"}}, {}, "NOT_RUN"),
    ({"status": "unavailable"}, {}, "UNAVAILABLE"),
    ({}, {"verdict": "UNAVAILABLE", "status": "unavailable"}, "UNAVAILABLE"),
])
def test_overall_verdict_never_promotes_unmeasured_lanes(suite_kwargs, lanes_kwargs, expected):
    evidence = tool.build_evidence(provenance=_prov(), suites=[_suite(**suite_kwargs)], lanes=_lanes(**lanes_kwargs))
    assert evidence["verdict"] == expected
    assert evidence["acceptanceClaim"] is False
    assert tool.EXIT_BY_VERDICT[expected] in (0, 1, 2, 3)


def test_bundle_lists_waits_without_values_and_hides_outcomes():
    evidence = tool.build_evidence(provenance=_prov(), suites=[_suite()], lanes=_lanes())
    assert all(item["value"] is None for item in evidence["physicalWaits"])
    assert evidence["linuxDockerOnly"]["status"] == "not_run_here"
    assert "outcomes" not in evidence["suites"][0]
    assert evidence["provenance"]["runnerSha256"]
    text = tool.render_markdown(evidence)
    assert "PASS_MEASURED_PARTIAL" in text and "not_run_here" in text


# --------------------------------------------------------------------------
# Redaction, stale outputs, stubbed end-to-end
# --------------------------------------------------------------------------


def test_secret_guard_and_write_refusal(monkeypatch, tmp_path):
    monkeypatch.setenv("INV_TEST_ADMIN_DSN", "postgresql://inv:top-secret@127.0.0.1:55432/postgres")
    with pytest.raises(ValueError):
        tool.assert_no_secrets("x top-secret y")
    evidence = tool.build_evidence(provenance=_prov(), suites=[_suite()], lanes=_lanes(), note="top-secret")
    with pytest.raises(ValueError):
        tool.write_evidence(evidence, tmp_path, "x")
    assert not (tmp_path / "x.json").exists()


def test_stale_outputs_removed_and_missing_dsn_is_unavailable(tmp_path, monkeypatch):
    for name in ("s.json", "s.md", "s-lanes.json", "s-lanes.md"):
        (tmp_path / name).write_text("{}", encoding="utf-8")
    monkeypatch.delenv("INV_TEST_ADMIN_DSN", raising=False)
    assert tool.main(["--out-dir", str(tmp_path), "--label", "s", "--junit-dir", str(tmp_path / "j")]) == 2
    assert not any((tmp_path / n).exists() for n in ("s.json", "s.md", "s-lanes.json", "s-lanes.md"))


def test_main_bundles_stubbed_suites_and_lanes(tmp_path, monkeypatch):
    monkeypatch.setenv("INV_TEST_ADMIN_DSN", "postgresql://inv:stub-pw@127.0.0.1:1/postgres")
    monkeypatch.setattr(tool, "collect_provenance", lambda executor=None: _prov())
    monkeypatch.setattr(tool, "run_suite", lambda spec, junit_dir, python=None: {**_suite(), "id": spec["id"]})
    monkeypatch.setattr(tool, "run_lanes", lambda out_dir, label, dsn, container_image, note: _lanes())
    code = tool.main(["--out-dir", str(tmp_path), "--label", "b", "--junit-dir", str(tmp_path / "j")])
    assert code == 0
    payload = json.loads((tmp_path / "b.json").read_text(encoding="utf-8"))
    assert payload["verdict"] == "PASS_MEASURED_PARTIAL"
    assert {k: v["status"] for k, v in payload["clauses"].items()} == {
        "allowed-execution-succeeds": "pass", "forbidden-path-or-command-blocked": "pass",
        "resources-reclaimed-after-exit": "not_run", "evidence-id-and-output-hash-enforced": "not_run"}
    assert payload["passScope"]["passed"] == ["allowed-execution-succeeds", "forbidden-path-or-command-blocked"]
    assert payload["passScope"]["notRunUnmeasuredLane"] == ["resources-reclaimed-after-exit", "evidence-id-and-output-hash-enforced"]
    assert payload["clauses"]["resources-reclaimed-after-exit"]["dbLaneRules"] == {"C1": None, "C4": None}
    assert "pass scope" in (tmp_path / "b.md").read_text(encoding="utf-8")
    assert [s["id"] for s in payload["suites"]] == [s["id"] for s in tool.SUITES]
    text = (tmp_path / "b.json").read_text(encoding="utf-8") + (tmp_path / "b.md").read_text(encoding="utf-8")
    assert "stub-pw" not in text


# --------------------------------------------------------------------------
# Real PostgreSQL: one full runner invocation
# --------------------------------------------------------------------------


@pytest.mark.postgres
def test_real_pg_runner_bundle(tmp_path):
    admin = os.environ.get("INV_TEST_ADMIN_DSN")
    if not admin:
        if os.environ.get("CI"):
            pytest.fail("CI requires INV_TEST_ADMIN_DSN; DB tests must not be skipped")
        pytest.skip("Set INV_TEST_ADMIN_DSN to a disposable PostgreSQL 16+ test server")
    code = tool.main(["--out-dir", str(tmp_path), "--label", "real", "--junit-dir", str(tmp_path / "j")])
    payload = json.loads((tmp_path / "real.json").read_text(encoding="utf-8"))
    assert code == tool.EXIT_BY_VERDICT[payload["verdict"]]
    assert payload["acceptanceClaim"] is False
    assert payload["lanes"]["status"] == "complete"
    assert admin not in (tmp_path / "real.json").read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# Codex #121 residual: unobserved violations are unknown, never 0
# --------------------------------------------------------------------------


def test_unmeasured_db_lane_never_passes_lane_dependent_clauses():
    """Revival: db.measured=false + violationsByRule={} must not yield pass or numeric zeros."""
    outcomes = tool.parse_junit(_junit(_all_cases()))["outcomes"]
    clauses = tool.evaluate_clauses(outcomes, {}, db_measured=False)
    for key in ("resources-reclaimed-after-exit", "evidence-id-and-output-hash-enforced"):
        assert clauses[key]["status"] == "not_run"
        assert clauses[key]["notRunReason"] == "db-lane-unmeasured"
        assert all(v is None for v in clauses[key]["dbLaneRules"].values())
        assert 0 not in clauses[key]["dbLaneRules"].values()
    assert clauses["allowed-execution-succeeds"]["status"] == "pass"
    evidence = tool.build_evidence(provenance=_prov(), suites=[_suite()], lanes=_lanes(db=False))
    assert evidence["verdict"] == "PASS_MEASURED_PARTIAL"
    assert evidence["passScope"]["notRunUnmeasuredLane"] == [
        "resources-reclaimed-after-exit", "evidence-id-and-output-hash-enforced"]
    assert "not_run" in tool.render_markdown(evidence)


def test_measured_db_lane_with_explicit_zero_violations_passes_lane_clauses():
    """Only a measured DB lane with explicit C1..C4 = 0 may pass the lane-dependent clauses."""
    outcomes = tool.parse_junit(_junit(_all_cases()))["outcomes"]
    clauses = tool.evaluate_clauses(outcomes, {"C1": 0, "C2": 0, "C3": 0, "C4": 0}, db_measured=True)
    assert {c["status"] for c in clauses.values()} == {"pass"}
    assert clauses["evidence-id-and-output-hash-enforced"]["dbLaneRules"] == {"C2": 0, "C3": 0}
    evidence = tool.build_evidence(provenance=_prov(), suites=[_suite()],
                                   lanes=_lanes(verdict="PASS", db=True, container=True,
                                                violations={"C1": 0, "C2": 0, "C3": 0, "C4": 0}))
    assert evidence["passScope"]["passed"] == list(tool.AC03_CLAUSES)
    assert evidence["verdict"] == "PASS_MEASURED_PARTIAL"  # docker lane still not_run


def test_measured_lane_with_empty_rule_map_is_invalid_evidence_not_pass():
    """Codex #121: db_measured=True + {} (or a missing key) must never be treated as zero."""
    outcomes = tool.parse_junit(_junit(_all_cases()))["outcomes"]
    for violations in ({}, {"C1": 0, "C2": 0, "C3": 0}, {"C1": 0, "C2": 0, "C3": 0, "C4": None},
                       {"C1": 0, "C2": 0, "C3": 0, "C4": True}):
        clauses = tool.evaluate_clauses(outcomes, violations, db_measured=True)
        for key in ("resources-reclaimed-after-exit", "evidence-id-and-output-hash-enforced"):
            if any(rule not in violations or not isinstance(violations.get(rule), int)
                   or isinstance(violations.get(rule), bool) for rule in tool.AC03_CLAUSES[key]["lane_rules"]):
                assert clauses[key]["status"] == "not_run", (violations, key)
                assert clauses[key]["notRunReason"] == "lane-rule-missing-invalid-evidence"
                assert 0 not in [v for r, v in clauses[key]["dbLaneRules"].items() if r in clauses[key]["laneRulesMissing"]]
    evidence = tool.build_evidence(provenance=_prov(), suites=[_suite()],
                                   lanes=_lanes(verdict="PASS", db=True, container=True, violations={}))
    assert evidence["verdict"] == "NOT_RUN"
    assert evidence["passScope"]["notRunOther"] == ["resources-reclaimed-after-exit", "evidence-id-and-output-hash-enforced"]


def test_reported_violation_dominates_a_missing_sibling_rule():
    outcomes = tool.parse_junit(_junit(_all_cases()))["outcomes"]
    clauses = tool.evaluate_clauses(outcomes, {"C2": 1}, db_measured=True)
    assert clauses["evidence-id-and-output-hash-enforced"]["status"] == "fail"
    assert clauses["resources-reclaimed-after-exit"]["status"] == "not_run"


def test_run_lanes_serializes_every_judged_rule_explicitly(tmp_path, monkeypatch):
    from tools import collect_container_evidence as cce
    payload = {"db": {"measured": True, "counts": {"runs": 2, "leases": 3}}, "container": {"measured": False,
               "probes": [], "reason": "no docker"}, "violations": [{"rule": "C4", "run": "run_01HZZZZZZZZZZZZZZZZZZZZZZZ"}],
               "provenance": {"collector_sha256": "x"}}
    def fake_main(argv):
        out = Path(argv[argv.index("--out-dir") + 1]); label = argv[argv.index("--label") + 1]
        (out / f"{label}.json").write_text(json.dumps(payload), encoding="utf-8")
        (out / f"{label}.md").write_text("md", encoding="utf-8")
        return 1
    monkeypatch.setattr(cce, "main", fake_main)
    monkeypatch.setenv("INV_TEST_ADMIN_DSN", "postgresql://inv:pw@127.0.0.1:1/postgres")
    summary = tool.run_lanes(tmp_path, "lanes", dsn=None, container_image=None, note=None)
    assert summary["violationsByRule"] == {"C1": 0, "C2": 0, "C3": 0, "C4": 1}
    assert summary["verdict"] == "VIOLATIONS" and summary["db"]["measured"] is True


def test_lane_evidence_outside_repo_is_recorded_as_placeholder_not_relative_to(tmp_path, monkeypatch):
    """Hosted CI writes to /tmp: relative_to(REPO_ROOT) must never raise or leak the absolute path."""
    from tools import collect_container_evidence as cce
    payload = {"db": {"measured": False, "counts": {"runs": 0, "leases": 0}}, "container": {"measured": False,
               "probes": [], "reason": "no docker"}, "violations": [], "provenance": {"collector_sha256": "x"}}
    def fake_main(argv):
        out = Path(argv[argv.index("--out-dir") + 1]); label = argv[argv.index("--label") + 1]
        (out / f"{label}.json").write_text(json.dumps(payload), encoding="utf-8")
        (out / f"{label}.md").write_text("md", encoding="utf-8")
        return 3
    monkeypatch.setattr(cce, "main", fake_main)
    monkeypatch.setenv("INV_TEST_ADMIN_DSN", "postgresql://inv:pw@127.0.0.1:1/postgres")
    outside = tmp_path / "outside"  # pytest tmp_path is outside the repository
    summary = tool.run_lanes(outside, "lanes", dsn=None, container_image=None, note=None)
    assert summary["evidenceJson"] == "<outside-repo>/lanes.json"
    assert str(outside) not in json.dumps(summary)
    assert tool.evidence_ref(REPO_ROOT / "docs" / "x.json") == "docs/x.json"
