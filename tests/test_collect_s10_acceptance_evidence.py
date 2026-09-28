"""S10-DB/ST AC-10 acceptance evidence collector: PG-free unit tests plus one real-PG run."""

from __future__ import annotations

import ast
import json
import re
import os
from pathlib import Path

import pytest

from tools import collect_s10_acceptance_evidence as tool

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
    return {case: "passed" for spec in tool.AC10_CLAUSES.values() for case in spec["cases"]}


def _suite(status="complete", outcomes=None, exit_code=0, suite_id="all"):
    return {"id": suite_id, "paths": ["x"], "postgres": True, "exitCode": exit_code, "elapsedSeconds": 1.0,
            "junitSha256": "0" * 64, "counts": {"passed": 36, "failed": 0, "error": 0, "skipped": 0},
            "outcomes": tool.parse_junit(_junit(outcomes or _all_cases()))["outcomes"], "status": status}


def _prov(clean=True):
    return {"commit_sha": "a" * 40, "branch": "b", "integration_ref": "o", "integration_sha": "a" * 40,
            "integration_check_mode": "local", "working_tree_clean_status": clean, "content_clean_diff": clean,
            "modified_paths": [], "interpreter": "py", "runtime_python": "3.14", "timestamp_kst": "t",
            "executor": "Claude", "os_platform": "win"}


# --------------------------------------------------------------------------
# Reuse contract
# --------------------------------------------------------------------------


def test_every_mapped_case_exists_and_is_unique():
    mapped = [case for spec in tool.AC10_CLAUSES.values() for case in spec["cases"]]
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
    assert len(mapped) == 36


def test_every_mapped_module_and_the_s10_set_are_covered_one_postgres_file_per_process():
    modules = {case.split("::")[0].replace(".", "/") + ".py" for spec in tool.AC10_CLAUSES.values()
               for case in spec["cases"]}
    covered = {path for spec in tool.SUITES for path in spec["paths"]}
    assert modules <= covered, modules - covered
    assert len(covered) == 14  # the S10 real-PG set from the 2026-09-22 cross-evidence page
    for spec in tool.SUITES:
        if spec["postgres"]:
            assert len(spec["paths"]) == 1
        for path in spec["paths"]:
            assert (REPO_ROOT / path).is_file(), path


# --------------------------------------------------------------------------
# JUnit, clauses, verdicts (fail-closed)
# --------------------------------------------------------------------------


def test_parse_junit_worst_outcome_and_no_failure_text():
    raw = _junit({"tests.x::test_a[1]": "passed"}).replace(
        b"</testsuite>", b'<testcase classname="tests.x" name="test_a[2]"><failure message="postgresql://u:secret-pw@h/db">x</failure></testcase></testsuite>')
    parsed = tool.parse_junit(raw)
    assert parsed["outcomes"] == {"tests.x::test_a": "failed"}
    assert "secret-pw" not in json.dumps(parsed)
    with pytest.raises(ValueError):
        tool.parse_junit(b"<html/>")


@pytest.mark.parametrize("mutate, expected", [
    ({}, "pass"),
    ({"tests.test_lineage::test_lineage_is_tenant_isolated": "failed"}, "fail"),
    ({"tests.test_lineage::test_lineage_is_tenant_isolated": "skipped"}, "not_run"),
    ({"tests.test_lineage::test_lineage_is_tenant_isolated": None}, "not_run"),
])
def test_clause_pass_requires_every_case_passed(mutate, expected):
    cases = _all_cases()
    for case, outcome in mutate.items():
        cases.pop(case) if outcome is None else cases.__setitem__(case, outcome)
    clause = tool.evaluate_clauses(tool.parse_junit(_junit(cases))["outcomes"])["tenant-isolation"]
    assert clause["status"] == expected


@pytest.mark.parametrize("suite_kwargs, expected", [
    ({}, "PASS"),
    ({"outcomes": {**_all_cases(), "tests.test_lineage::test_a_retention_pin_only_extends": "failed"},
      "status": "failed", "exit_code": 1}, "FAIL"),
    ({"outcomes": {**_all_cases(), "tests.test_lineage::test_a_retention_pin_only_extends": "skipped"}}, "NOT_RUN"),
    ({"status": "unavailable"}, "UNAVAILABLE"),
    ({"status": "invalid-junit"}, "UNAVAILABLE"),
])
def test_overall_verdict_rules(suite_kwargs, expected):
    evidence = tool.build_evidence(provenance=_prov(), suites=[_suite(**suite_kwargs)])
    assert evidence["verdict"] == expected
    assert evidence["acceptanceClaim"] is False


def test_unmapped_failure_in_any_suite_fails_closed():
    """Revival (Codex #120 F-R1 class): 36 mapped pass + 1 unmapped failure → FAIL."""
    outcomes = {**_all_cases(), "tests.integration.test_model_retry::test_something_unmapped": "failed"}
    suite = _suite(status="failed", outcomes=outcomes, exit_code=1, suite_id="model-retry")
    suite["counts"] = {"passed": 36, "failed": 1, "error": 0, "skipped": 0}
    evidence = tool.build_evidence(provenance=_prov(), suites=[_suite(), suite])
    assert {c["status"] for c in evidence["clauses"].values()} == {"pass"}
    assert evidence["verdict"] == "FAIL"


@pytest.mark.parametrize("field, value", [("status", "failed"), ("exitCode", 1)])
def test_incomplete_suite_is_never_pass(field, value):
    suite = _suite()
    suite[field] = value
    assert tool.build_evidence(provenance=_prov(), suites=[suite])["verdict"] == "FAIL"


def test_external_waits_have_no_values_and_outcomes_are_not_embedded():
    evidence = tool.build_evidence(provenance=_prov(), suites=[_suite()])
    assert {w["id"] for w in evidence["externalWaits"]} == {"CX-02", "MLflow"}
    assert all(w["status"] == "UNMEASURED" and w["value"] is None for w in evidence["externalWaits"])
    assert "outcomes" not in evidence["suites"][0]
    assert evidence["provenance"]["collectorSha256"] and evidence["codeSha"] == "a" * 40
    assert "UNMEASURED" in tool.render_markdown(evidence)


# --------------------------------------------------------------------------
# Redaction (negative tests per identifier class), secrets, stale outputs, provenance
# --------------------------------------------------------------------------


from saintvision.ids import PREFIXES as _CORE_PREFIXES

_KERNEL_PREFIXES = ["apr", "chk", "dtl", "evd", "lse", "mdl", "mdv", "nod", "node", "plan", "pool", "prj",
                    "rep", "res", "run", "stc", "user", "usr", "wkl", "wld", "wsp"]


@pytest.mark.parametrize("sample", [
    "inv_backend_test_" + "a" * 32, "inv_rls_" + "b" * 32, "inv_s03_" + "c" * 32,
    "ff5d8e54-3ac6-4fbb-924e-a7f2f88bbf53", "10.0.0.7:5432",
    *[f"{prefix}_01HZZZZZZZZZZZZZZZZZZZZZZZ" for prefix in sorted(set(_CORE_PREFIXES.values()) | set(_KERNEL_PREFIXES))],
])
def test_sanitizer_replaces_each_identifier_class_and_refuses_unredacted_writes(sample, tmp_path):
    assert sample not in tool.redact_text(f"x {sample} y")
    with pytest.raises(ValueError, match="unredacted"):
        tool.assert_redacted(f"x {sample} y")
    evidence = tool.build_evidence(provenance=_prov(), suites=[_suite()], note=f"raw {sample}")
    with pytest.raises(ValueError, match="unredacted"):
        tool.write_evidence(evidence, tmp_path, "raw")
    assert not (tmp_path / "raw.json").exists()


def test_sanitizer_keeps_git_shas_and_counts():
    assert tool.redact_text("sha 1e8baf045c5a passed 228") == "sha 1e8baf045c5a passed 228"


def test_secret_guard_rejects_dsn_and_password(monkeypatch):
    monkeypatch.setenv("INV_TEST_ADMIN_DSN", "postgresql://inv:top-secret@127.0.0.1:55432/postgres")
    tool.assert_no_secrets("clean")
    with pytest.raises(ValueError, match="INV_TEST_ADMIN_DSN"):
        tool.assert_no_secrets("postgresql://inv:top-secret@127.0.0.1:55432/postgres")
    with pytest.raises(ValueError, match="password"):
        tool.assert_no_secrets("top-secret")


def test_existing_outputs_are_refused_never_deleted_and_dirty_tree_is_refused_by_default(tmp_path, monkeypatch):
    for name in ("s.json", "s.md"):
        (tmp_path / name).write_text('{"verdict":"PASS"}', encoding="utf-8")
    monkeypatch.setenv("INV_TEST_ADMIN_DSN", "postgresql://inv:pw@127.0.0.1:1/postgres")
    monkeypatch.setattr(tool, "collect_provenance", lambda executor=None: _prov())
    assert tool.main(["--out-dir", str(tmp_path), "--label", "s", "--junit-dir", str(tmp_path / "j")]) == 2
    assert (tmp_path / "s.json").read_text(encoding="utf-8") == '{"verdict":"PASS"}'
    monkeypatch.setattr(tool, "collect_provenance", lambda executor=None: _prov(clean=False))
    assert tool.main(["--out-dir", str(tmp_path), "--label", "d", "--junit-dir", str(tmp_path / "j")]) == 2
    assert not (tmp_path / "d.json").exists()
    monkeypatch.setattr(tool, "run_suite", lambda spec, junit_dir, python=None: _suite(suite_id=spec["id"]))
    assert tool.main(["--out-dir", str(tmp_path), "--label", "d", "--junit-dir", str(tmp_path / "j"),
                      "--allow-dirty-tree"]) == 0
    assert json.loads((tmp_path / "d.json").read_text(encoding="utf-8"))["provenance"]["dirtyTreeAllowed"] is True
    monkeypatch.delenv("INV_TEST_ADMIN_DSN", raising=False)
    assert tool.main(["--out-dir", str(tmp_path), "--label", "n", "--junit-dir", str(tmp_path / "j")]) == 2


def test_default_label_carries_sha_and_utc_timestamp(monkeypatch, tmp_path):
    monkeypatch.setattr(tool, "collect_provenance", lambda executor=None: _prov())
    monkeypatch.setattr(tool, "run_suite", lambda spec, junit_dir, python=None: _suite(suite_id=spec["id"]))
    monkeypatch.setenv("INV_TEST_ADMIN_DSN", "postgresql://inv:pw@127.0.0.1:1/postgres")
    assert tool.main(["--out-dir", str(tmp_path), "--junit-dir", str(tmp_path / "j")]) == 0
    names = sorted(p.name for p in tmp_path.glob("s10-acceptance-*.json"))
    assert len(names) == 1 and re.fullmatch(r"s10-acceptance-a{12}-\d{8}T\d{6}Z\.json", names[0]), names


def test_failed_outranks_unavailable():
    failed = _suite(status="failed", outcomes={**_all_cases(), "tests.test_lineage::test_x": "failed"}, exit_code=1)
    failed["counts"] = {"passed": 36, "failed": 1, "error": 0, "skipped": 0}
    unavailable = _suite(status="unavailable", suite_id="u")
    unavailable["counts"] = None
    assert tool.build_evidence(provenance=_prov(), suites=[unavailable, failed])["verdict"] == "FAIL"


def test_provenance_is_computed_from_the_repo_root(monkeypatch, tmp_path):
    seen = {}

    def fake_collect(executor=None):
        seen["cwd"] = Path(os.getcwd()).resolve()
        return _prov()
    monkeypatch.setattr(tool, "collect_provenance", fake_collect)
    monkeypatch.chdir(tmp_path)
    tool.collect_provenance_at_repo_root("Claude")
    assert seen["cwd"] == tool.REPO_ROOT.resolve()
    assert Path(os.getcwd()).resolve() == tmp_path.resolve()


def test_main_bundles_stubbed_suites(tmp_path, monkeypatch):
    monkeypatch.setenv("INV_TEST_ADMIN_DSN", "postgresql://inv:stub-pw@127.0.0.1:1/postgres")
    monkeypatch.setattr(tool, "collect_provenance", lambda executor=None: _prov())
    monkeypatch.setattr(tool, "run_suite", lambda spec, junit_dir, python=None: _suite(suite_id=spec["id"]))
    code = tool.main(["--out-dir", str(tmp_path), "--label", "b", "--junit-dir", str(tmp_path / "j"),
                      "--note", "dev PG at 127.0.0.1:55432 model mdl_01HZZZZZZZZZZZZZZZZZZZZZZZ"])
    assert code == 0
    payload = json.loads((tmp_path / "b.json").read_text(encoding="utf-8"))
    assert payload["verdict"] == "PASS" and payload["schemaVersion"] == tool.SCHEMA_VERSION
    assert {k: v["status"] for k, v in payload["clauses"].items()} == {k: "pass" for k in tool.AC10_CLAUSES}
    assert [s["id"] for s in payload["suites"]] == [s["id"] for s in tool.SUITES]
    assert payload["note"] == "dev PG at <host:port:redacted> model <id:redacted>"
    text = (tmp_path / "b.json").read_text(encoding="utf-8") + (tmp_path / "b.md").read_text(encoding="utf-8")
    assert "stub-pw" not in text


# --------------------------------------------------------------------------
# Real PostgreSQL: one full collector invocation (files run one per process inside)
# --------------------------------------------------------------------------


@pytest.mark.postgres
def test_real_pg_collector_bundle(tmp_path):
    admin = os.environ.get("INV_TEST_ADMIN_DSN")
    if not admin:
        if os.environ.get("CI"):
            pytest.fail("CI requires INV_TEST_ADMIN_DSN; DB tests must not be skipped")
        pytest.skip("Set INV_TEST_ADMIN_DSN to a disposable PostgreSQL 16+ test server")
    code = tool.main(["--out-dir", str(tmp_path), "--label", "real", "--junit-dir", str(tmp_path / "j")])
    payload = json.loads((tmp_path / "real.json").read_text(encoding="utf-8"))
    assert code == tool.EXIT_BY_VERDICT[payload["verdict"]]
    assert payload["acceptanceClaim"] is False
    assert admin not in (tmp_path / "real.json").read_text(encoding="utf-8")
