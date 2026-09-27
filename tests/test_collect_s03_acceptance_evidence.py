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
    assert len(mapped) == 28


def test_every_mapped_module_is_covered_by_a_suite_entry():
    modules = {case.split("::")[0].replace(".", "/") + ".py"
               for spec in tool.AC03_CLAUSES.values() for case in spec["cases"]}
    covered = {path for spec in tool.SUITES for path in spec["paths"]}
    assert modules <= covered, modules - covered


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
    clause = tool.evaluate_clauses(outcomes)["evidence-id-and-output-hash-enforced"]
    assert clause["status"] == expected


def test_db_lane_violation_fails_the_owning_clause_only():
    outcomes = tool.parse_junit(_junit(_all_cases()))["outcomes"]
    clauses = tool.evaluate_clauses(outcomes, {"C2": 1})
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
    return {"status": status, "verdict": verdict, "exitCode": {"PASS": 0, "VIOLATIONS": 1, "UNAVAILABLE": 2,
            "UNMEASURED": 3}[verdict], "ledgerSource": "empty-disposable-database", "evidenceJson": "l.json",
            "db": {"measured": db, "runs": 0, "leases": 0}, "container": {"measured": container, "probes": 0,
            "reason": None if container else "docker unavailable"}, "violationsByRule": violations or {}}


def _prov():
    return {"commit_sha": "a" * 40, "branch": "b", "integration_ref": "o", "integration_sha": "a" * 40,
            "integration_check_mode": "local", "working_tree_clean_status": True, "content_clean_diff": True,
            "modified_paths": [], "interpreter": "py", "runtime_python": "3.14", "timestamp_kst": "t",
            "executor": "Claude", "os_platform": "win"}


@pytest.mark.parametrize("suite_kwargs, lanes_kwargs, expected", [
    ({}, {}, "PASS_MEASURED_PARTIAL"),
    ({}, {"verdict": "PASS", "db": True, "container": True}, "PASS"),
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
    assert {k: v["status"] for k, v in payload["clauses"].items()} == {k: "pass" for k in tool.AC03_CLAUSES}
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
