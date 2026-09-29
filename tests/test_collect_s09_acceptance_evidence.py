"""S09-DB/ST AC-09 acceptance evidence collector: PG-free unit tests plus one real-PG run."""

from __future__ import annotations

import ast
import json
import os
import re
from pathlib import Path

import pytest

from saintvision.ids import PREFIXES as _CORE_PREFIXES
from tools import collect_s09_acceptance_evidence as tool

REPO_ROOT = Path(__file__).resolve().parents[1]
GATE = tool.LINUX_PRIVATE_STORAGE_GATE
GATED_CASES = list(tool.AC09_CLAUSES["runrecord-completion-pipeline"]["cases"])
_KERNEL_PREFIXES = ["apr", "chk", "dtl", "evd", "lse", "mdl", "mdv", "nod", "node", "plan", "pool", "prj",
                    "rep", "res", "run", "stc", "user", "usr", "wkl", "wld", "wsp"]


def _junit(cases: dict[str, str]) -> bytes:
    body = []
    for case_id, outcome in cases.items():
        classname, name = case_id.split("::")
        inner = {"failed": '<failure message="postgresql://u:secret-pw@h/db">x</failure>',
                 "error": "<error>e</error>", "skipped": '<skipped message="Linux private storage"/>'}.get(outcome, "")
        body.append(f'<testcase classname="{classname}" name="{name}" time="0.1">{inner}</testcase>')
    return (f'<?xml version="1.0"?><testsuites><testsuite name="pytest" tests="{len(cases)}">'
            f'{"".join(body)}</testsuite></testsuites>').encode()


def _all_cases(exclude_gated: bool = True) -> dict[str, str]:
    return {case: "passed" for key, spec in tool.AC09_CLAUSES.items() for case in spec["cases"]
            if not (exclude_gated and key == "runrecord-completion-pipeline")}


def _counts(outcomes: dict[str, str]) -> dict[str, int]:
    return {k: sum(1 for v in outcomes.values() if v == k) for k in ("passed", "failed", "error", "skipped")}


def _suite(status="complete", outcomes=None, exit_code=0, suite_id="all", gate=None):
    outcomes = outcomes if outcomes is not None else _all_cases()
    parsed = tool.parse_junit(_junit(outcomes))
    return {"id": suite_id, "paths": ["x"], "postgres": True, "gate": gate, "exitCode": exit_code,
            "elapsedSeconds": 1.0, "junitSha256": "0" * 64, "counts": parsed["counts"],
            "outcomes": parsed["outcomes"], "status": status}


def _gated_skipped_here():
    """What this Windows host actually produces for test_results.py: pytest exit 0, 14 ids skipped, 0 executed."""
    return _suite(status="not_run", outcomes={c: "skipped" for c in GATED_CASES},
                  suite_id="results-linux-private-storage", gate=GATE)


def _gated_measured():
    return _suite(outcomes={c: "passed" for c in GATED_CASES}, suite_id="results-linux-private-storage", gate=GATE)


def _prov(clean=True):
    return {"commit_sha": "a" * 40, "branch": "b", "integration_ref": "o", "integration_sha": "a" * 40,
            "integration_check_mode": "local", "working_tree_clean_status": clean, "content_clean_diff": clean,
            "modified_paths": [], "interpreter": "py", "runtime_python": "3.14", "timestamp_kst": "t",
            "executor": "Claude", "os_platform": "win"}


# --------------------------------------------------------------------------
# Reuse contract: every case of the five S09 files is mapped, exists, once
# --------------------------------------------------------------------------


def _defined_tests(path: Path) -> set[str]:
    return {n.name for n in ast.parse(path.read_text(encoding="utf-8-sig")).body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test_")}


def test_every_mapped_case_exists_once_and_every_test_of_the_s09_files_is_mapped():
    mapped = [case for spec in tool.AC09_CLAUSES.values() for case in spec["cases"]]
    assert len(mapped) == len(set(mapped))
    by_module: dict[str, set[str]] = {}
    for case in mapped:
        module, name = case.split("::")
        by_module.setdefault(module, set()).add(name)
    for module, names in by_module.items():
        defined = _defined_tests(REPO_ROOT / (module.replace(".", "/") + ".py"))
        assert names == defined, (module, names ^ defined)
    assert len(mapped) == 73
    covered = {path for spec in tool.SUITES for path in spec["paths"]}
    assert {m.replace(".", "/") + ".py" for m in by_module} == covered
    for spec in tool.SUITES:
        assert len(spec["paths"]) == 1 and spec["postgres"]
        assert (REPO_ROOT / spec["paths"][0]).is_file()


def test_the_gated_file_declares_its_gate_in_source_and_the_collector_names_it():
    source = (REPO_ROOT / "tests/integration/test_results.py").read_text(encoding="utf-8-sig")
    assert "Linux private storage" in source and "sys.platform != 'linux'" in source.replace('"', "'")
    gated = [s for s in tool.SUITES if s.get("gate")]
    assert [s["id"] for s in gated] == ["results-linux-private-storage"]
    assert tool.AC09_CLAUSES["runrecord-completion-pipeline"]["gate"] == gated[0]["gate"] == GATE
    assert all(c.startswith("tests.integration.test_results::") for c in GATED_CASES)


# --------------------------------------------------------------------------
# JUnit, clauses, gates, verdicts (fail-closed; unobserved is never zero)
# --------------------------------------------------------------------------


def test_parse_junit_worst_outcome_and_no_failure_text():
    raw = _junit({"tests.x::test_a[1]": "passed"}).replace(
        b"</testsuite>", b'<testcase classname="tests.x" name="test_a[2]"><failure message="postgresql://u:secret-pw@h/db">x</failure></testcase></testsuite>')
    parsed = tool.parse_junit(raw)
    assert parsed["outcomes"] == {"tests.x::test_a": "failed"}
    assert "secret-pw" not in json.dumps(parsed)
    with pytest.raises(ValueError):
        tool.parse_junit(b"<html/>")


@pytest.mark.parametrize("mutate, expected, reason", [
    ({}, "pass", None),
    ({"tests.test_context_eval::test_evaluation_is_tenant_isolated": "failed"}, "fail", "case-failed-or-errored"),
    ({"tests.test_context_eval::test_evaluation_is_tenant_isolated": "error"}, "fail", "case-failed-or-errored"),
    ({"tests.test_context_eval::test_evaluation_is_tenant_isolated": "skipped"}, "not_run", "case-skipped-or-missing"),
    ({"tests.test_context_eval::test_evaluation_is_tenant_isolated": None}, "not_run", "case-skipped-or-missing"),
])
def test_clause_pass_requires_every_case_passed_and_states_a_reason(mutate, expected, reason):
    cases = _all_cases()
    for case, outcome in mutate.items():
        cases.pop(case) if outcome is None else cases.__setitem__(case, outcome)
    clause = tool.evaluate_clauses(tool.parse_junit(_junit(cases))["outcomes"])["tenant-isolation"]
    assert clause["status"] == expected and clause["reason"] == reason


def test_gated_clause_is_not_run_with_the_gate_as_reason_only_when_its_suite_skipped_everything():
    skipped = tool.gates_skipped_here([_suite(), _gated_skipped_here()])
    assert skipped == {GATE}
    outcomes = {**_all_cases(), **{c: "skipped" for c in GATED_CASES}}
    clause = tool.evaluate_clauses(outcomes, skipped)["runrecord-completion-pipeline"]
    assert clause["status"] == "not_run" and clause["reason"] == f"environment-gated:{GATE}"
    # Same skips but the gate not attributed (e.g. suite unavailable): ordinary not_run, not gated.
    clause = tool.evaluate_clauses(outcomes, set())["runrecord-completion-pipeline"]
    assert clause["status"] == "not_run" and clause["reason"] == "case-skipped-or-missing"
    # A gated suite that executed even one case is not "skipped here" (nothing is zeroed by the gate).
    partial = _suite(status="failed", outcomes={**{c: "skipped" for c in GATED_CASES[1:]}, GATED_CASES[0]: "failed"},
                     exit_code=1, suite_id="results-linux-private-storage", gate=GATE)
    assert tool.gates_skipped_here([partial]) == set()


def test_gated_suite_with_a_missing_case_is_not_gated_not_run():
    """13 skipped + 1 missing id must not hide behind the gate reason."""
    outcomes = {**_all_cases(), **{c: "skipped" for c in GATED_CASES[1:]}}
    clause = tool.evaluate_clauses(outcomes, {GATE})["runrecord-completion-pipeline"]
    assert clause["status"] == "not_run" and clause["reason"] == "case-skipped-or-missing"


@pytest.mark.parametrize("suites_factory, expected", [
    (lambda: [_suite(), _gated_measured()], "PASS"),
    (lambda: [_suite(), _gated_skipped_here()], "PASS_MEASURED_PARTIAL"),
    (lambda: [_suite(outcomes={**_all_cases(), "tests.test_context_eval::test_only_one_record_per_run": "failed"},
                     status="failed", exit_code=1), _gated_skipped_here()], "FAIL"),
    (lambda: [_suite(outcomes={**_all_cases(), "tests.test_context_eval::test_only_one_record_per_run": "skipped"}),
              _gated_skipped_here()], "NOT_RUN"),
    (lambda: [_suite(status="unavailable"), _gated_skipped_here()], "UNAVAILABLE"),
    (lambda: [_suite(status="invalid-junit"), _gated_skipped_here()], "UNAVAILABLE"),
    (lambda: [_suite(), _suite(status="unavailable", suite_id="results-linux-private-storage", gate=GATE)], "UNAVAILABLE"),
    (lambda: [_suite(status="not_run", outcomes={c: "skipped" for c in _all_cases()}), _gated_skipped_here()], "NOT_RUN"),
    (lambda: [_gated_skipped_here()], "NOT_RUN"),
])
def test_overall_verdict_rules(suites_factory, expected):
    suites = suites_factory()
    for s in suites:
        if s["status"] in ("unavailable", "invalid-junit"):
            s["counts"] = None
    evidence = tool.build_evidence(provenance=_prov(), suites=suites)
    assert evidence["verdict"] == expected
    assert evidence["acceptanceClaim"] is False
    assert tool.EXIT_BY_VERDICT[expected] in (0, 1, 2, 3)


def test_pass_measured_partial_states_its_scope_and_never_counts_the_gate_as_pass_or_zero():
    evidence = tool.build_evidence(provenance=_prov(), suites=[_suite(), _gated_skipped_here()])
    assert evidence["verdict"] == "PASS_MEASURED_PARTIAL"
    assert evidence["passScope"]["notRunEnvironmentGated"] == ["runrecord-completion-pipeline"]
    assert evidence["passScope"]["notRunOther"] == [] and evidence["passScope"]["failed"] == []
    assert len(evidence["passScope"]["passed"]) == 7
    assert evidence["environment"]["gatesSkippedHere"] == [GATE]
    assert evidence["passScopeNote"]
    gated_suite = next(s for s in evidence["suites"] if s["id"] == "results-linux-private-storage")
    assert gated_suite["counts"] == {"passed": 0, "failed": 0, "error": 0, "skipped": 14}
    assert evidence["totals"]["skipped"] == 14
    md = tool.render_markdown(evidence)
    assert f"environment-gated:{GATE}" in md and "PASS_MEASURED_PARTIAL" in md


def test_unmapped_failure_in_any_suite_fails_closed():
    """Revival (Codex #120 F-R1 class): all mapped pass + 1 unmapped failure → FAIL."""
    outcomes = {**_all_cases(), "tests.integration.test_approvals::test_something_unmapped": "failed"}
    suite = _suite(status="failed", outcomes=outcomes, exit_code=1, suite_id="approvals")
    evidence = tool.build_evidence(provenance=_prov(), suites=[suite, _gated_measured()])
    assert {c["status"] for c in evidence["clauses"].values()} == {"pass"}
    assert evidence["verdict"] == "FAIL"


@pytest.mark.parametrize("field, value", [("status", "failed"), ("exitCode", 1)])
def test_incomplete_suite_is_never_pass(field, value):
    suite = _suite()
    suite[field] = value
    assert tool.build_evidence(provenance=_prov(), suites=[suite, _gated_measured()])["verdict"] == "FAIL"


def test_failed_outranks_unavailable_in_either_order():
    failed = _suite(status="failed", outcomes={**_all_cases(), "tests.test_context_eval::test_x": "failed"}, exit_code=1)
    unavailable = _suite(status="unavailable", suite_id="u")
    unavailable["counts"] = None
    for suites in ([unavailable, failed], [failed, unavailable]):
        assert tool.build_evidence(provenance=_prov(), suites=suites)["verdict"] == "FAIL"
    # A failure recorded inside a suite whose status is unavailable/not_run still fails.
    odd = _suite(status="not_run", outcomes={**_all_cases(), "tests.test_context_eval::test_x": "error"})
    assert tool.build_evidence(provenance=_prov(), suites=[odd])["verdict"] == "FAIL"


def test_unavailable_suite_is_unknown_not_zero():
    unavailable = _suite(status="unavailable", suite_id="approvals")
    unavailable["counts"] = None
    unavailable["junitSha256"] = None
    evidence = tool.build_evidence(provenance=_prov(), suites=[unavailable])
    assert evidence["totals"] is None and evidence["unavailableSuites"] == ["approvals"]
    assert evidence["verdict"] == "UNAVAILABLE"
    assert "None" in tool.render_markdown(evidence)


def test_external_waits_have_no_values_and_outcomes_are_not_embedded():
    evidence = tool.build_evidence(provenance=_prov(), suites=[_suite(), _gated_measured()])
    assert {w["id"] for w in evidence["externalWaits"]} == {
        "AC-09-prompt-validity", "AC-09-coding-success", "AC-09-leak-zero", "CX-02"}
    assert all(w["status"] == "UNMEASURED" and w["value"] is None for w in evidence["externalWaits"])
    assert all("outcomes" not in s for s in evidence["suites"])
    assert evidence["provenance"]["collectorSha256"] and evidence["codeSha"] == "a" * 40
    assert "UNMEASURED" in tool.render_markdown(evidence)


# --------------------------------------------------------------------------
# Redaction (negative test per identifier class), secrets, outputs, provenance
# --------------------------------------------------------------------------


@pytest.mark.parametrize("sample", [
    "inv_backend_test_" + "a" * 32, "inv_rls_" + "b" * 32, "inv_s03_" + "c" * 32,
    "ff5d8e54-3ac6-4fbb-924e-a7f2f88bbf53", "10.0.0.7:5432", "192.168.45.74:18443",
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


def test_s09_id_prefixes_are_in_the_core_set():
    assert {"evs", "evc", "evr", "art", "apv", "run", "evd", "wsp", "usr"} <= set(_CORE_PREFIXES.values())


def test_sanitizer_keeps_git_shas_counts_and_case_names():
    text = "sha 1e8baf045c5a passed 76 skipped 21 test_a_sealed_record_cannot_be_rewritten"
    assert tool.redact_text(text) == text


def test_secret_guard_rejects_dsn_and_password(monkeypatch):
    monkeypatch.setenv("INV_TEST_ADMIN_DSN", "postgresql://inv:top-secret@127.0.0.1:55432/postgres")
    tool.assert_no_secrets("clean")
    with pytest.raises(ValueError, match="INV_TEST_ADMIN_DSN"):
        tool.assert_no_secrets("postgresql://inv:top-secret@127.0.0.1:55432/postgres")
    with pytest.raises(ValueError, match="password"):
        tool.assert_no_secrets("top-secret")


def test_evidence_ref_outside_repo_is_a_placeholder(tmp_path):
    assert tool.evidence_ref(tmp_path / "x.json") == "<outside-repo>/x.json"
    assert tool.evidence_ref(REPO_ROOT / "tools" / "collect_s09_acceptance_evidence.py") == \
        "tools/collect_s09_acceptance_evidence.py"


def _stub_run(monkeypatch):
    monkeypatch.setattr(tool, "run_suite", lambda spec, junit_dir, python=None:
                        _gated_skipped_here() if spec.get("gate") else _suite(suite_id=spec["id"]))


def test_existing_outputs_are_refused_never_deleted(tmp_path, monkeypatch):
    (tmp_path / "s.md").write_text("prior", encoding="utf-8")  # a lone sibling blocks the label
    monkeypatch.setenv("INV_TEST_ADMIN_DSN", "postgresql://inv:pw@127.0.0.1:1/postgres")
    monkeypatch.setattr(tool, "collect_provenance", lambda executor=None: _prov())
    _stub_run(monkeypatch)
    assert tool.main(["--out-dir", str(tmp_path), "--label", "s", "--junit-dir", str(tmp_path / "j")]) == 2
    assert (tmp_path / "s.md").read_text(encoding="utf-8") == "prior" and not (tmp_path / "s.json").exists()


def test_dirty_tree_is_refused_by_default_and_recorded_when_allowed(tmp_path, monkeypatch):
    monkeypatch.setenv("INV_TEST_ADMIN_DSN", "postgresql://inv:pw@127.0.0.1:1/postgres")
    monkeypatch.setattr(tool, "collect_provenance", lambda executor=None: _prov(clean=False))
    _stub_run(monkeypatch)
    assert tool.main(["--out-dir", str(tmp_path), "--label", "d", "--junit-dir", str(tmp_path / "j")]) == 2
    assert not (tmp_path / "d.json").exists()
    assert tool.main(["--out-dir", str(tmp_path), "--label", "d", "--junit-dir", str(tmp_path / "j"),
                      "--allow-dirty-tree"]) == 0
    payload = json.loads((tmp_path / "d.json").read_text(encoding="utf-8"))
    assert payload["provenance"]["dirtyTreeAllowed"] is True
    assert payload["provenance"]["working_tree_clean_status"] is False


def test_missing_dsn_is_unavailable_and_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.delenv("INV_TEST_ADMIN_DSN", raising=False)
    monkeypatch.setattr(tool, "collect_provenance", lambda executor=None: _prov())
    assert tool.main(["--out-dir", str(tmp_path), "--label", "n", "--junit-dir", str(tmp_path / "j")]) == 2
    assert not list(tmp_path.glob("*"))


def test_default_label_carries_sha_and_utc_timestamp(monkeypatch, tmp_path):
    monkeypatch.setattr(tool, "collect_provenance", lambda executor=None: _prov())
    monkeypatch.setenv("INV_TEST_ADMIN_DSN", "postgresql://inv:pw@127.0.0.1:1/postgres")
    _stub_run(monkeypatch)
    assert tool.main(["--out-dir", str(tmp_path), "--junit-dir", str(tmp_path / "j")]) == 0
    names = sorted(p.name for p in tmp_path.glob("s09-acceptance-*.json"))
    assert len(names) == 1 and re.fullmatch(r"s09-acceptance-a{12}-\d{8}T\d{6}Z\.json", names[0]), names


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


def test_main_bundles_stubbed_suites_on_a_gated_host(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("INV_TEST_ADMIN_DSN", "postgresql://inv:stub-pw@127.0.0.1:1/postgres")
    monkeypatch.setattr(tool, "collect_provenance", lambda executor=None: _prov())
    _stub_run(monkeypatch)
    code = tool.main(["--out-dir", str(tmp_path), "--label", "b", "--junit-dir", str(tmp_path / "j"),
                      "--note", "dev PG at 127.0.0.1:55432 suite evs_01HZZZZZZZZZZZZZZZZZZZZZZZ"])
    assert code == 0
    payload = json.loads((tmp_path / "b.json").read_text(encoding="utf-8"))
    assert payload["verdict"] == "PASS_MEASURED_PARTIAL" and payload["schemaVersion"] == tool.SCHEMA_VERSION
    assert {k: v["status"] for k, v in payload["clauses"].items()} == {
        **{k: "pass" for k in tool.AC09_CLAUSES}, "runrecord-completion-pipeline": "not_run"}
    assert [s["id"] for s in payload["suites"]] == [s["id"] for s in tool.SUITES]
    assert payload["note"] == "dev PG at <host:port:redacted> suite <id:redacted>"
    text = (tmp_path / "b.json").read_text(encoding="utf-8") + (tmp_path / "b.md").read_text(encoding="utf-8")
    assert "stub-pw" not in text and "127.0.0.1:55432" not in text
    printed = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert printed["json"] == "<outside-repo>/b.json"


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
