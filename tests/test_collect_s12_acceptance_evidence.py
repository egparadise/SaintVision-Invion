"""S12-DB AC-12 acceptance evidence collector: PG-free unit tests plus one real-PG run.

The collector re-implements no judgement: every PG-free test feeds it the JSON shapes the
existing tools publish (operational_readiness --acceptance-evidence, pitr_readiness,
pitr_opt_in_dry_run, the desktop-browser proof) and checks the sorting into
PASS / FAIL / NOT_OBSERVED / BLOCKED_EXTERNAL.  Nothing unobserved may become PASS or 0.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from saintvision.ids import PREFIXES as _CORE_PREFIXES
from tools import collect_s12_acceptance_evidence as tool

REPO_ROOT = Path(__file__).resolve().parents[1]
TENANT = "b0d2c1f0-1111-4222-8333-444455556666"
RELEASE = "rel_01HZZZZZZZZZZZZZZZZZZZZZZZ"
ALL_ITEM_IDS = [s["id"] for s in tool.AC12_ITEMS] + [s["id"] for s in tool.EXTERNAL_ITEMS]


def _catalog(*, assessed=True, blockers=(), limitations=("no GPU pinning yet",), version="1.0.0", sha="a" * 64):
    return {
        "releaseId": RELEASE if assessed else None, "version": version if assessed else None,
        "manifestSha256": sha if assessed else None, "acceptanceAssessed": assessed,
        "acceptances": [{"criterion": "AC-12", "outcome": "accepted"}] if assessed else [],
        "knownLimitations": list(limitations) if assessed else [], "drillsMissingTargets": [],
        "contributionsNeedingAttention": [], "blockers": list(blockers),
        "catalogComplete": not blockers and assessed, "scope": "record-catalog-not-operational-acceptance",
        "operationalAcceptanceAssessed": False,
        "unverified": ["operational RPO and full-service recovery"], "evidenceComplete": False,
    }


def _readiness(*, absent=(), disagreeing=(), closed=(), catalog=None, status="complete"):
    if status != "complete":
        return {"status": status, "reason": "operational_readiness_unavailable", "payload": None, "exitCode": 2}
    payload = {
        "tenant": TENANT, "observedAt": "2026-09-28T01:00:00+00:00",
        "inputs": [{"input": "declared capabilities", "present": True, "count": 1}],
        "absent": [{"input": name, "present": False, "count": 0} for name in absent],
        "offerAgreement": {"offers": [], "disagreeing": list(disagreeing), "recordedNotApplied": []},
        "admission": {"gates": [], "closed": list(closed), "observedGatesOpen": not closed, "wouldAdmit": None,
                      "scope": "diagnostic-not-execution-admission", "unverified": []},
        "acceptanceEvidence": catalog if catalog is not None else _catalog(),
    }
    return {"status": "complete", "reason": None, "payload": payload, "exitCode": 1, "elapsedSeconds": 0.1}


def _pitr(verdict="possible", status="complete"):
    if status != "complete":
        return {"status": status, "reason": "INV_PITR_DSN is not set", "payload": None, "exitCode": None}
    return {"status": "complete", "reason": None, "exitCode": 0, "elapsedSeconds": 0.1,
            "payload": {"verdict": verdict, "reasons": ["Configuration observed"], "scope": "configuration-only", "pitrVerified": False}}


def _dry_run(hv="observed", status="complete", mutated=False):
    if status != "complete":
        return {"status": status, "reason": "harness refused (argparse error, stderr not recorded)" if status == "refused" else "--pitr-archive/--pitr-backups not given",
                "payload": None, "exitCode": 2 if status == "refused" else None}
    return {"status": "complete", "reason": None, "exitCode": 0, "elapsedSeconds": 0.2, "payload": {
        "harnessVerdict": hv, "mode": "dry-run", "decision": "tier-a-deferred",
        "mutations": {"postgresRestarted": mutated, "postgresSettingsChanged": False, "composeApplied": False, "retentionApplied": False},
        "retention": {"deleteArchive": ["000000010000000000000001"], "deleteBackups": []},
        "acceptance": {"pitrVerified": False, "ac12Satisfied": False}}}


def _web(passed=5, failure=0, error=0, skipped=0, status="complete", exit_code=0, ev="complete"):
    if status != "complete":
        return {"status": status, "reason": "no --web-smoke-proof given (desktop-browser lane, Gemini)", "payload": None}
    return {"status": "complete", "reason": None, "proofSha256": "c" * 64,
            "payload": {"browserOptIn": True, "exitCode": exit_code, "evidenceStatus": ev,
                        "tests": {"passed": passed, "failure": failure, "error": error, "skipped": skipped}}}


def _prov(clean=True):
    return {"commit_sha": "a" * 40, "branch": "b", "integration_ref": "o", "integration_sha": "a" * 40,
            "integration_check_mode": "local", "working_tree_clean_status": clean, "content_clean_diff": clean,
            "modified_paths": [], "interpreter": "py", "runtime_python": "3.14", "timestamp_kst": "t",
            "executor": "Claude", "os_platform": "win"}


def _build(**kw):
    defaults = dict(provenance=_prov(), readiness=_readiness(), pitr=_pitr(), dry_run=_dry_run(), web=_web(), release_given=True)
    defaults.update(kw)
    return tool.build_evidence(**defaults)


# --------------------------------------------------------------------------
# item table and reuse contract
# --------------------------------------------------------------------------


def test_item_table_is_unique_and_every_item_is_evaluated():
    assert len(ALL_ITEM_IDS) == len(set(ALL_ITEM_IDS)) == 17
    evidence = _build()
    assert list(evidence["items"]) == ALL_ITEM_IDS
    assert all(item["status"] in (tool.PASS, tool.FAIL, tool.NOT_OBSERVED, tool.BLOCKED_EXTERNAL) for item in evidence["items"].values())
    assert set(evidence["scope"]) == {tool.PASS, tool.FAIL, tool.NOT_OBSERVED, tool.BLOCKED_EXTERNAL}


def test_collector_reuses_existing_tools_and_defines_no_judgement_of_its_own():
    source = (REPO_ROOT / "tools" / "collect_s12_acceptance_evidence.py").read_text(encoding="utf-8")
    for name in ("operational_readiness.py", "pitr_readiness.py", "pitr_opt_in_dry_run.py"):
        assert name in source and (REPO_ROOT / "tools" / name).is_file()
    # no SQL, no settings assessment, no drill/backups logic re-implemented here
    assert "SELECT " not in source and "archive_mode" not in source and "met_targets" not in source


# --------------------------------------------------------------------------
# sorting rules
# --------------------------------------------------------------------------


def test_fully_observed_catalog_passes_measured_items_and_externals_stay_blocked():
    evidence = _build()
    s = evidence["scope"]
    assert set(s[tool.PASS]) == {i["id"] for i in tool.AC12_ITEMS}
    assert s[tool.FAIL] == [] and s[tool.NOT_OBSERVED] == []
    assert s[tool.BLOCKED_EXTERNAL] == [i["id"] for i in tool.EXTERNAL_ITEMS]
    assert evidence["verdict"] == "PASS_MEASURED_PARTIAL" and evidence["acceptanceClaim"] is False
    assert all(item["value"] is None for k, item in evidence["items"].items() if item["group"] == "external")


def test_without_a_release_the_release_group_is_blocked_external_not_fail_not_pass():
    evidence = _build(readiness=_readiness(catalog=_catalog(assessed=False)), release_given=False)
    for key in ("release-manifest-recorded", "user-acceptance-record-ac12", "known-limitations-recorded"):
        assert evidence["items"][key]["status"] == tool.BLOCKED_EXTERNAL
        assert "user input" in evidence["items"][key]["reason"]
    assert evidence["inputs"]["acceptanceCatalog"]["acceptanceAssessed"] is False
    assert evidence["verdict"] == "PASS_MEASURED_PARTIAL"


@pytest.mark.parametrize("blocker, item", [
    ("no acceptance record for AC-12 in this release", "user-acceptance-record-ac12"),
    ("a rejected acceptance stands against this release", "user-acceptance-record-ac12"),
    ("an acceptance refers to a different manifest than the current one", "user-acceptance-record-ac12"),
    ("no passing database recovery drill", "database-recovery-drill-passed-with-targets"),
    ("no database recovery drill meeting targets and integrity/fencing checks", "database-recovery-drill-passed-with-targets"),
    ("no verified backup", "verified-backup-in-retention"),
    ("no verified off-site backup", "verified-off-site-backup"),
    ("2 contributed folder(s) need attention", "contributed-folders-checked"),
])
def test_each_catalog_blocker_fails_exactly_its_item(blocker, item):
    evidence = _build(readiness=_readiness(catalog=_catalog(blockers=(blocker,))))
    assert evidence["items"][item]["status"] == tool.FAIL and blocker in evidence["items"][item]["reason"]
    others = [k for k, v in evidence["items"].items() if v["status"] == tool.FAIL]
    assert others == [item]
    assert evidence["verdict"] == "FAIL"


def test_empty_known_limitations_is_not_observed_not_pass():
    evidence = _build(readiness=_readiness(catalog=_catalog(limitations=())))
    item = evidence["items"]["known-limitations-recorded"]
    assert item["status"] == tool.NOT_OBSERVED and item["count"] == 0


@pytest.mark.parametrize("kwargs, item, expected", [
    ({"absent": ("current resource offers",)}, "operational-inputs-present", tool.FAIL),
    ({"disagreeing": ("cap-1",)}, "offer-agreement", tool.FAIL),
    ({"closed": ("capacity offered to the kernel",)}, "admission-gates-observed-open", tool.FAIL),
])
def test_permission_items_fail_on_the_readiness_fields(kwargs, item, expected):
    evidence = _build(readiness=_readiness(**kwargs))
    assert evidence["items"][item]["status"] == expected and evidence["verdict"] == "FAIL"


def test_readiness_unavailable_makes_every_readiness_item_not_observed_with_reason():
    evidence = _build(readiness=_readiness(status="unavailable"))
    for key in [i["id"] for i in tool.AC12_ITEMS if i["source"].startswith("operational_readiness")]:
        assert evidence["items"][key]["status"] == tool.NOT_OBSERVED, key
        assert evidence["items"][key]["reason"]
    assert evidence["inputs"]["acceptanceCatalog"] is None
    assert evidence["verdict"] == "PASS_MEASURED_PARTIAL"  # pitr/dry-run/web still passed


@pytest.mark.parametrize("verdict, expected", [("possible", tool.PASS), ("absent", tool.FAIL), ("inconclusive", tool.NOT_OBSERVED)])
def test_pitr_configuration_verdict_maps_without_reinterpretation(verdict, expected):
    evidence = _build(pitr=_pitr(verdict))
    item = evidence["items"]["pitr-configuration-possible"]
    assert item["status"] == expected and item["verdict"] == verdict
    if expected == tool.PASS:
        assert item["pitrVerified"] is False


@pytest.mark.parametrize("dry, expected", [
    (_dry_run(), tool.PASS),
    (_dry_run(hv="inconclusive"), tool.NOT_OBSERVED),
    (_dry_run(mutated=True), tool.FAIL),
    (_dry_run(status="refused"), tool.FAIL),
    (_dry_run(status="not_run"), tool.NOT_OBSERVED),
    (_dry_run(status="unavailable"), tool.NOT_OBSERVED),
])
def test_pitr_rehearsal_item(dry, expected):
    evidence = _build(dry_run=dry)
    assert evidence["items"]["pitr-rehearsal-dry-run-observed"]["status"] == expected


@pytest.mark.parametrize("web, expected", [
    (_web(), tool.PASS),
    (_web(failure=1), tool.FAIL),
    (_web(skipped=1), tool.FAIL),
    (_web(passed=0), tool.FAIL),
    (_web(exit_code=1), tool.FAIL),
    (_web(ev="partial"), tool.FAIL),
    (_web(status="not_run"), tool.NOT_OBSERVED),
    (_web(status="unavailable"), tool.NOT_OBSERVED),
])
def test_web_smoke_item_requires_every_journey_passed(web, expected):
    assert _build(web=web)["items"]["web-smoke-journeys"]["status"] == expected


def test_nothing_observed_is_not_observed_not_zero():
    evidence = _build(readiness=_readiness(status="unavailable"), pitr=_pitr(status="unavailable"),
                      dry_run=_dry_run(status="not_run"), web=_web(status="not_run"), release_given=False)
    assert evidence["scope"][tool.PASS] == [] and evidence["scope"][tool.FAIL] == []
    assert evidence["verdict"] == "NOT_OBSERVED" and tool.EXIT_BY_VERDICT["NOT_OBSERVED"] == 3
    assert "0" not in json.dumps({k: v.get("value") for k, v in evidence["items"].items()})


def test_fail_outranks_everything_else():
    evidence = _build(readiness=_readiness(status="unavailable"), pitr=_pitr("absent"), web=_web(status="not_run"))
    assert evidence["verdict"] == "FAIL" and tool.EXIT_BY_VERDICT["FAIL"] == 1


def test_external_items_can_never_pass_even_with_a_perfect_catalog():
    evidence = _build()
    assert all(evidence["items"][s["id"]]["status"] == tool.BLOCKED_EXTERNAL for s in tool.EXTERNAL_ITEMS)
    assert evidence["verdict"] != "PASS"


# --------------------------------------------------------------------------
# tool runners: unavailable / refused paths, no re-judgement
# --------------------------------------------------------------------------


def test_runners_report_unavailable_when_the_dsn_env_is_unset(monkeypatch, tmp_path):
    monkeypatch.delenv("X_READINESS", raising=False)
    monkeypatch.delenv("X_PITR", raising=False)
    assert tool.run_operational_readiness("X_READINESS", TENANT, None)["status"] == "unavailable"
    assert tool.run_pitr_readiness("X_PITR")["status"] == "unavailable"
    assert tool.run_pitr_dry_run("X_PITR", None, None, __import__("datetime").datetime.now(__import__("datetime").timezone.utc))["status"] == "not_run"
    assert tool.read_web_smoke_proof(None)["status"] == "not_run"
    assert tool.read_web_smoke_proof(tmp_path / "missing.json")["status"] == "unavailable"
    (tmp_path / "bad.json").write_text("{", encoding="utf-8")
    assert tool.read_web_smoke_proof(tmp_path / "bad.json")["status"] == "unavailable"


def test_operational_readiness_error_payload_is_unavailable_not_fail(monkeypatch):
    monkeypatch.setenv("X_READINESS", "postgresql://u:p@127.0.0.1:1/x")
    monkeypatch.setattr(tool, "_run_json", lambda command, env, cwd=None: {"exitCode": 2, "elapsedSeconds": 0.0, "payload": {"error": "operational_readiness_unavailable"}, "parseError": None, "stderrLines": 0})
    result = tool.run_operational_readiness("X_READINESS", TENANT, None)
    assert result["status"] == "unavailable" and result["reason"] == "operational_readiness_unavailable"
    evidence = _build(readiness=result)
    assert evidence["items"]["operational-inputs-present"]["status"] == tool.NOT_OBSERVED


def test_dry_run_argparse_refusal_is_fail_closed(monkeypatch, tmp_path):
    monkeypatch.setenv("X_PITR", "postgresql://u:p@127.0.0.1:1/x")
    monkeypatch.setattr(tool, "_run_json", lambda command, env, cwd=None: {"exitCode": 2, "elapsedSeconds": 0.0, "payload": None, "parseError": None, "stderrLines": 2})
    result = tool.run_pitr_dry_run("X_PITR", tmp_path, tmp_path, __import__("datetime").datetime.now(__import__("datetime").timezone.utc))
    assert result["status"] == "refused"
    assert _build(dry_run=result)["items"]["pitr-rehearsal-dry-run-observed"]["status"] == tool.FAIL


# --------------------------------------------------------------------------
# redaction (prefix-agnostic), secrets, outputs, provenance
# --------------------------------------------------------------------------


_KERNEL_PREFIXES = ["apr", "chk", "dtl", "evd", "lse", "mdl", "mdv", "nod", "node", "plan", "pool", "prj",
                    "rep", "res", "run", "stc", "user", "usr", "wkl", "wld", "wsp"]


@pytest.mark.parametrize("sample", [
    "inv_backend_test_" + "a" * 32, "inv_test_" + "b" * 32, TENANT, "10.0.0.7:5432",
    "backup_01HZZZZZZZZZZZZZZZZZZZZZZZ", "release_01HZZZZZZZZZZZZZZZZZZZZZZZ", "acceptancerec_01HZZZZZZZZZZZZZZZZZZZZZZZ",
    *[f"{prefix}_01HZZZZZZZZZZZZZZZZZZZZZZZ" for prefix in sorted(set(_CORE_PREFIXES.values()) | set(_KERNEL_PREFIXES))],
])
def test_sanitizer_is_prefix_agnostic_and_written_files_never_carry_the_value(sample, tmp_path):
    assert sample not in tool.redact_text(f"x {sample} y")
    with pytest.raises(ValueError, match="unredacted"):
        tool.assert_redacted(f"x {sample} y")
    # write_evidence redacts every produced text first and then re-checks it (fail-closed guard):
    # the sample must be gone from both files, and a guard bypass would be caught by assert_redacted.
    evidence = _build(note=f"raw {sample}")
    json_path, md_path = tool.write_evidence(evidence, tmp_path, "raw")
    text = json_path.read_text(encoding="utf-8") + md_path.read_text(encoding="utf-8")
    assert sample not in text and "redacted>" in text


def test_explicit_command_line_values_are_redacted_whatever_their_shape(tmp_path):
    odd_release = "my-release-2026-Q3"  # no prefix, no ULID: only the explicit-value rule catches it
    evidence = _build(note=f"release {odd_release} tenant {TENANT}")
    with pytest.raises(ValueError, match="value:redacted"):
        tool.assert_redacted(json.dumps(evidence), explicit=(odd_release,))
    json_path, _ = tool.write_evidence(evidence, tmp_path, "e", explicit=(odd_release, TENANT))
    text = json_path.read_text(encoding="utf-8")
    assert odd_release not in text and TENANT not in text and "<value:redacted>" in text


def test_sanitizer_keeps_git_shas_counts_and_item_ids():
    text = "sha 1e8baf045c5a passed 5 database-recovery-drill-passed-with-targets no verified backup"
    assert tool.redact_text(text) == text


def test_secret_guard_covers_the_dsn_envs_this_run_used(monkeypatch):
    monkeypatch.setenv("X_READINESS", "postgresql://inv:top-secret@127.0.0.1:55432/postgres")
    tool.assert_no_secrets("clean", extra_env=("X_READINESS",))
    with pytest.raises(ValueError, match="X_READINESS"):
        tool.assert_no_secrets("postgresql://inv:top-secret@127.0.0.1:55432/postgres", extra_env=("X_READINESS",))
    with pytest.raises(ValueError, match="password"):
        tool.assert_no_secrets("top-secret", extra_env=("X_READINESS",))


def test_evidence_ref_outside_repo_is_a_placeholder(tmp_path):
    assert tool.evidence_ref(tmp_path / "x.json") == "<outside-repo>/x.json"


def _stub_runners(monkeypatch, **overrides):
    monkeypatch.setattr(tool, "run_operational_readiness", lambda dsn_env, tenant, release, python=None: overrides.get("readiness", _readiness()))
    monkeypatch.setattr(tool, "run_pitr_readiness", lambda dsn_env, python=None: overrides.get("pitr", _pitr()))
    monkeypatch.setattr(tool, "run_pitr_dry_run", lambda dsn_env, a, b, now, python=None: overrides.get("dry", _dry_run()))
    monkeypatch.setattr(tool, "read_web_smoke_proof", lambda path: overrides.get("web", _web()))


def test_existing_outputs_refused_dirty_tree_refused_and_no_dsn_is_unavailable(tmp_path, monkeypatch):
    monkeypatch.setenv("INV_READINESS_DSN", "postgresql://inv:pw@127.0.0.1:1/postgres")
    monkeypatch.setattr(tool, "collect_provenance", lambda executor=None: _prov())
    _stub_runners(monkeypatch)
    (tmp_path / "s.md").write_text("prior", encoding="utf-8")
    assert tool.main(["--out-dir", str(tmp_path), "--label", "s", "--tenant", TENANT]) == 2
    assert (tmp_path / "s.md").read_text(encoding="utf-8") == "prior" and not (tmp_path / "s.json").exists()
    monkeypatch.setattr(tool, "collect_provenance", lambda executor=None: _prov(clean=False))
    assert tool.main(["--out-dir", str(tmp_path), "--label", "d", "--tenant", TENANT]) == 2
    assert tool.main(["--out-dir", str(tmp_path), "--label", "d", "--tenant", TENANT, "--allow-dirty-tree"]) == 0
    assert json.loads((tmp_path / "d.json").read_text(encoding="utf-8"))["provenance"]["dirtyTreeAllowed"] is True
    monkeypatch.delenv("INV_READINESS_DSN", raising=False)
    monkeypatch.delenv("INV_PITR_DSN", raising=False)
    assert tool.main(["--out-dir", str(tmp_path), "--label", "n", "--tenant", TENANT]) == 2
    assert not (tmp_path / "n.json").exists()


def test_default_label_carries_sha_and_utc_timestamp(tmp_path, monkeypatch):
    monkeypatch.setenv("INV_READINESS_DSN", "postgresql://inv:pw@127.0.0.1:1/postgres")
    monkeypatch.setattr(tool, "collect_provenance", lambda executor=None: _prov())
    _stub_runners(monkeypatch)
    assert tool.main(["--out-dir", str(tmp_path), "--tenant", TENANT]) == 0
    names = [p.name for p in tmp_path.glob("s12-acceptance-*.json")]
    assert len(names) == 1 and re.fullmatch(r"s12-acceptance-a{12}-\d{8}T\d{6}Z\.json", names[0]), names


def test_provenance_is_computed_from_the_repo_root(tmp_path, monkeypatch):
    seen = {}

    def fake_collect(executor=None):
        seen["cwd"] = Path(os.getcwd()).resolve()
        return _prov()
    monkeypatch.setattr(tool, "collect_provenance", fake_collect)
    monkeypatch.chdir(tmp_path)
    tool.collect_provenance_at_repo_root("Claude")
    assert seen["cwd"] == tool.REPO_ROOT.resolve() and Path(os.getcwd()).resolve() == tmp_path.resolve()


def test_main_end_to_end_with_stubbed_tools_redacts_tenant_release_and_ids(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("INV_READINESS_DSN", "postgresql://inv:stub-pw@127.0.0.1:1/postgres")
    monkeypatch.setattr(tool, "collect_provenance", lambda executor=None: _prov())
    _stub_runners(monkeypatch)
    code = tool.main(["--out-dir", str(tmp_path), "--label", "b", "--tenant", TENANT, "--release", RELEASE,
                      "--note", f"tenant {TENANT} release {RELEASE} drill drl_01HZZZZZZZZZZZZZZZZZZZZZZZ at 10.0.0.7:5432"])
    assert code == 0
    text = (tmp_path / "b.json").read_text(encoding="utf-8") + (tmp_path / "b.md").read_text(encoding="utf-8")
    payload = json.loads((tmp_path / "b.json").read_text(encoding="utf-8"))
    assert payload["verdict"] == "PASS_MEASURED_PARTIAL" and payload["schemaVersion"] == tool.SCHEMA_VERSION
    assert payload["inputs"]["releaseGiven"] is True
    for secret in (TENANT, RELEASE, "stub-pw", "10.0.0.7:5432", "drl_01HZZZZZZZZZZZZZZZZZZZZZZZ"):
        assert secret not in text
    assert "<value:redacted>" in payload["note"] and "<id:redacted>" in payload["note"] and "<host:port:redacted>" in payload["note"]
    printed = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert printed["json"] == "<outside-repo>/b.json" and printed["verdict"] == "PASS_MEASURED_PARTIAL"


# --------------------------------------------------------------------------
# Real PostgreSQL: the collector against a migrated disposable database (hosted Backend)
# --------------------------------------------------------------------------


@pytest.mark.postgres
def test_real_pg_collector_bundle_against_migrated_schema(tmp_path, monkeypatch, migrated, database_url):
    """No records exist for a fresh tenant: the catalog must come back with blockers (FAIL items),
    permissions items observed, release group BLOCKED_EXTERNAL, and nothing invented."""
    import uuid
    from psycopg.conninfo import make_conninfo
    from sqlalchemy.engine import make_url

    admin = os.environ.get("INV_TEST_ADMIN_DSN")
    if not admin:
        if os.environ.get("CI"):
            pytest.fail("CI requires INV_TEST_ADMIN_DSN; DB tests must not be skipped")
        pytest.skip("Set INV_TEST_ADMIN_DSN to a disposable PostgreSQL 16+ test server")
    dsn = make_conninfo(admin, dbname=make_url(database_url).database)
    monkeypatch.setenv("INV_S12_READINESS_DSN", dsn)
    monkeypatch.setenv("INV_S12_PITR_DSN", dsn)
    tenant = str(uuid.uuid4())
    code = tool.main(["--out-dir", str(tmp_path), "--label", "real", "--tenant", tenant,
                      "--readiness-dsn-env", "INV_S12_READINESS_DSN", "--pitr-dsn-env", "INV_S12_PITR_DSN"])
    payload = json.loads((tmp_path / "real.json").read_text(encoding="utf-8"))
    assert code == tool.EXIT_BY_VERDICT[payload["verdict"]]
    assert payload["acceptanceClaim"] is False
    text = (tmp_path / "real.json").read_text(encoding="utf-8")
    assert dsn not in text and tenant not in text
    items = payload["items"]
    assert payload["inputs"]["operationalReadiness"]["status"] == "complete", payload["inputs"]["operationalReadiness"]
    assert items["verified-backup-in-retention"]["status"] == tool.FAIL
    assert items["database-recovery-drill-passed-with-targets"]["status"] == tool.FAIL
    assert items["release-manifest-recorded"]["status"] == tool.BLOCKED_EXTERNAL
    assert items["operational-inputs-present"]["status"] in (tool.PASS, tool.FAIL)
    assert items["pitr-configuration-possible"]["status"] in (tool.PASS, tool.FAIL, tool.NOT_OBSERVED)
    assert items["pitr-rehearsal-dry-run-observed"]["status"] == tool.NOT_OBSERVED
    assert items["web-smoke-journeys"]["status"] == tool.NOT_OBSERVED
    assert payload["verdict"] == "FAIL"
