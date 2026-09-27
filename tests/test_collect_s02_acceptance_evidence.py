"""S02-DB AC-02 acceptance evidence collector: PG-free unit tests plus one real-PG run.

PG-free tests exercise the clause table, JUnit parsing, verdict rules, redaction and
stale-output handling with synthetic inputs.  The single ``postgres`` test runs the
whole collector once against a disposable database (skips without
``INV_TEST_ADMIN_DSN``; fails under CI).
"""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path

import pytest

from tools import collect_s02_acceptance_evidence as tool

REPO_ROOT = Path(__file__).resolve().parents[1]


def _junit(cases: dict[str, str], classname: str = tool.API_CLASSNAME) -> bytes:
    body = []
    for name, outcome in cases.items():
        inner = ""
        if outcome == "failed":
            inner = '<failure message="postgresql://u:secret-pass@h/db">boom</failure>'
        elif outcome == "error":
            inner = "<error>err</error>"
        elif outcome == "skipped":
            inner = '<skipped message="no dsn"/>'
        body.append(f'<testcase classname="{classname}" name="{name}" time="0.1">{inner}</testcase>')
    return (
        '<?xml version="1.0"?><testsuites><testsuite name="pytest" tests="%d">%s</testsuite></testsuites>'
        % (len(cases), "".join(body))
    ).encode()


def _all_passed() -> dict[str, str]:
    return {name: "passed" for spec in tool.AC02_CLAUSES.values() for name in spec["cases"]}


# --------------------------------------------------------------------------
# Reuse contract: every mapped case is a real test in tests/test_api.py
# --------------------------------------------------------------------------


def test_every_mapped_case_exists_in_test_api_and_is_unique():
    source = (REPO_ROOT / tool.API_SUITE).read_text(encoding="utf-8")
    defined = {
        node.name
        for node in ast.parse(source).body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    }
    mapped = [name for spec in tool.AC02_CLAUSES.values() for name in spec["cases"]]
    assert len(mapped) == len(set(mapped)), "a case is mapped to two clauses"
    assert set(mapped) <= defined, sorted(set(mapped) - defined)
    assert len(mapped) == 16


# --------------------------------------------------------------------------
# JUnit parsing and clause rules
# --------------------------------------------------------------------------


def test_parse_junit_counts_and_strips_parameters_and_failure_text():
    raw = _junit({"test_a[postgresql://u:p@h/db]": "passed", "test_b": "failed", "test_c": "skipped"})
    parsed = tool.parse_junit(raw)
    assert parsed["counts"] == {"passed": 1, "failed": 1, "error": 0, "skipped": 1}
    assert parsed["outcomes"] == {
        f"{tool.API_CLASSNAME}::test_a": "passed",
        f"{tool.API_CLASSNAME}::test_b": "failed",
        f"{tool.API_CLASSNAME}::test_c": "skipped",
    }
    assert "secret-pass" not in json.dumps(parsed)


def test_unsafe_case_names_are_dropped_not_guessed():
    raw = _junit({"test x": "passed"}, classname="tests.test_api")
    assert tool.parse_junit(raw)["outcomes"] == {}
    with pytest.raises(ValueError):
        tool.parse_junit(b"<html/>")


@pytest.mark.parametrize(
    "mutate, expected",
    [
        ({}, "pass"),
        ({"test_bootstrap_token_cannot_be_used_twice": "failed"}, "fail"),
        ({"test_bootstrap_token_cannot_be_used_twice": "error"}, "fail"),
        ({"test_bootstrap_token_cannot_be_used_twice": "skipped"}, "not_run"),
        ({"test_bootstrap_token_cannot_be_used_twice": None}, "not_run"),
    ],
)
def test_clause_is_pass_only_when_every_case_passed(mutate, expected):
    cases = _all_passed()
    for name, outcome in mutate.items():
        if outcome is None:
            cases.pop(name)
        else:
            cases[name] = outcome
    outcomes = tool.parse_junit(_junit(cases))["outcomes"]
    clause = tool.clause_status(outcomes, tool.AC02_CLAUSES["bootstrap-token-replay-blocked"]["cases"])
    assert clause["status"] == expected
    if mutate and list(mutate.values())[0] is None:
        assert clause["cases"]["test_bootstrap_token_cannot_be_used_twice"] == "missing"


# --------------------------------------------------------------------------
# Verdict and honesty rules
# --------------------------------------------------------------------------


def _api(status="complete", outcomes=None, exit_code=0):
    return {"suite": tool.API_SUITE, "command": "pytest", "exitCode": exit_code, "elapsedSeconds": 1.0,
            "junitSha256": "0" * 64, "counts": {"passed": 16, "failed": 0, "error": 0, "skipped": 0},
            "outcomes": tool.parse_junit(_junit(outcomes or _all_passed()))["outcomes"], "status": status}


def _rls(verdict="PASS", status="complete"):
    return {"status": status, "verdict": verdict, "exitCode": {"PASS": 0, "VIOLATIONS": 1,
            "UNAVAILABLE": 2, "UNMEASURED": 3}[verdict], "roles": ["inv_app"], "violations": 0,
            "accepted": 0, "unmeasured": 0, "evidenceJson": "x.json"}


def _provenance():
    return {"commit_sha": "a" * 40, "branch": "b", "integration_ref": "origin/x", "integration_sha": "a" * 40,
            "integration_check_mode": "local", "working_tree_clean_status": True, "content_clean_diff": True,
            "modified_paths": [], "interpreter": "py", "runtime_python": "3.14", "timestamp_kst": "t",
            "executor": "Claude", "os_platform": "win"}


@pytest.mark.parametrize(
    "api_kwargs, rls_kwargs, expected",
    [
        ({}, {}, "PASS"),
        ({"outcomes": {**_all_passed(), "test_denials_are_recorded": "failed"}}, {}, "FAIL"),
        ({}, {"verdict": "VIOLATIONS"}, "FAIL"),
        ({"outcomes": {**_all_passed(), "test_denials_are_recorded": "skipped"}}, {}, "NOT_RUN"),
        ({}, {"verdict": "UNMEASURED", "status": "complete"}, "NOT_RUN"),
        ({"status": "unavailable"}, {}, "UNAVAILABLE"),
        ({}, {"verdict": "UNAVAILABLE", "status": "unavailable"}, "UNAVAILABLE"),
    ],
)
def test_overall_verdict_never_passes_on_skips_or_unmeasured(api_kwargs, rls_kwargs, expected):
    evidence = tool.build_evidence(provenance=_provenance(), api=_api(**api_kwargs), rls=_rls(**rls_kwargs))
    assert evidence["verdict"] == expected
    assert evidence["acceptanceClaim"] is False


def test_external_waits_are_unmeasured_without_values_and_outcomes_are_not_embedded():
    evidence = tool.build_evidence(provenance=_provenance(), api=_api(), rls=_rls())
    assert {item["id"] for item in evidence["externalWaits"]} == {"U2", "U3", "U4", "U5"}
    assert all(item["status"] == "UNMEASURED" and item["value"] is None for item in evidence["externalWaits"])
    assert evidence["browserAcceptance"]["status"] == "not_in_scope"
    assert "outcomes" not in evidence["apiSuite"]
    assert evidence["codeSha"] == "a" * 40
    assert evidence["provenance"]["working_tree_clean_status"] is True
    text = tool.render_markdown(evidence)
    assert "UNMEASURED" in text and "**PASS**" in text


# --------------------------------------------------------------------------
# Redaction and stale outputs
# --------------------------------------------------------------------------


def test_secret_guard_rejects_dsn_and_password_from_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("INV_TEST_ADMIN_DSN", "postgresql://inv:top-secret-pw@127.0.0.1:55432/postgres")
    tool.assert_no_secrets("clean text")
    with pytest.raises(ValueError, match="INV_TEST_ADMIN_DSN"):
        tool.assert_no_secrets("dsn postgresql://inv:top-secret-pw@127.0.0.1:55432/postgres here")
    with pytest.raises(ValueError, match="password"):
        tool.assert_no_secrets("pw top-secret-pw leaked")
    evidence = tool.build_evidence(provenance=_provenance(), api=_api(), rls=_rls(), note="top-secret-pw")
    with pytest.raises(ValueError):
        tool.write_evidence(evidence, tmp_path, "x")
    assert not (tmp_path / "x.json").exists()


def test_stale_outputs_are_removed_before_a_rerun(tmp_path, monkeypatch):
    for name in ("s.json", "s.md", "s-rls.json", "s-rls.md"):
        (tmp_path / name).write_text('{"verdict":"PASS"}', encoding="utf-8")
    monkeypatch.delenv("INV_TEST_ADMIN_DSN", raising=False)
    code = tool.main(["--out-dir", str(tmp_path), "--label", "s", "--junit-dir", str(tmp_path / "junit")])
    assert code == 2
    assert not any((tmp_path / name).exists() for name in ("s.json", "s.md", "s-rls.json", "s-rls.md"))


def test_main_writes_bundle_from_stubbed_runners(tmp_path, monkeypatch):
    monkeypatch.setenv("INV_TEST_ADMIN_DSN", "postgresql://inv:stub-pw@127.0.0.1:1/postgres")
    monkeypatch.setattr(tool, "collect_provenance", lambda executor=None: _provenance())
    monkeypatch.setattr(tool, "run_api_suite", lambda junit_path, python=None: _api())
    monkeypatch.setattr(tool, "run_rls_collector", lambda out_dir, label: _rls())
    code = tool.main(["--out-dir", str(tmp_path), "--label", "bundle", "--junit-dir", str(tmp_path / "junit")])
    assert code == 0
    payload = json.loads((tmp_path / "bundle.json").read_text(encoding="utf-8"))
    assert payload["verdict"] == "PASS" and payload["schemaVersion"] == tool.SCHEMA_VERSION
    assert {k: v["status"] for k, v in payload["clauses"].items()} == {
        "allowed-node-registration-and-read": "pass",
        "bootstrap-token-replay-blocked": "pass",
        "cross-tenant-project-isolation": "pass",
        "denial-recorded": "pass",
    }
    text = (tmp_path / "bundle.json").read_text(encoding="utf-8") + (tmp_path / "bundle.md").read_text(encoding="utf-8")
    assert "stub-pw" not in text and "127.0.0.1:1" not in text


# --------------------------------------------------------------------------
# Real PostgreSQL: one full collector run against a disposable database
# --------------------------------------------------------------------------


@pytest.mark.postgres
def test_real_pg_collector_bundle_is_measured_and_redacted(tmp_path):
    admin = os.environ.get("INV_TEST_ADMIN_DSN")
    if not admin:
        if os.environ.get("CI"):
            pytest.fail("CI requires INV_TEST_ADMIN_DSN; DB tests must not be skipped")
        pytest.skip("Set INV_TEST_ADMIN_DSN to a disposable PostgreSQL 16+ test server")
    code = tool.main(["--out-dir", str(tmp_path), "--label", "real", "--junit-dir", str(tmp_path / "junit"),
                      "--note", "collector self-test"])
    payload = json.loads((tmp_path / "real.json").read_text(encoding="utf-8"))
    assert payload["apiSuite"]["status"] in ("complete", "failed"), payload["apiSuite"]
    assert payload["apiSuite"]["counts"]["passed"] + payload["apiSuite"]["counts"]["failed"] >= 16
    assert payload["rlsBoundary"]["status"] == "complete"
    assert payload["verdict"] in ("PASS", "FAIL", "NOT_RUN")
    assert code == tool.EXIT_BY_VERDICT[payload["verdict"]]
    assert payload["acceptanceClaim"] is False
    text = (tmp_path / "real.json").read_text(encoding="utf-8") + (tmp_path / "real.md").read_text(encoding="utf-8")
    assert admin not in text
    assert not any(k for k in os.environ if k.endswith("_PASSWORD") and os.environ[k] and os.environ[k] in text)
    assert (tmp_path / "real-rls.json").is_file()
