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
    return {"status": "complete", "reason": None, "proofSha256": "c" * 64, "boundSha": "a" * 40,
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
    monkeypatch.setattr(tool, "remote_reachability", lambda sha, ref=None: {"reachable": True, "refs": ["origin/x"], "mode": "remote-containment"})
    monkeypatch.setattr(tool, "run_operational_readiness", lambda dsn_env, tenant, release, python=None: overrides.get("readiness", _readiness()))
    monkeypatch.setattr(tool, "run_pitr_readiness", lambda dsn_env, python=None: overrides.get("pitr", _pitr()))
    monkeypatch.setattr(tool, "run_pitr_dry_run", lambda dsn_env, a, b, now, python=None: overrides.get("dry", _dry_run()))
    monkeypatch.setattr(tool, "read_web_smoke_proof", lambda path, bound_sha=None: overrides.get("web", _web()))


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
                      "--readiness-dsn-env", "INV_S12_READINESS_DSN", "--pitr-dsn-env", "INV_S12_PITR_DSN",
                      "--allow-unpushed-head"])  # CI merges the PR into a synthetic head no remote ref contains; recorded, not hidden
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



# --------------------------------------------------------------------------
# Codex review of #153 (head 30f5ca83): F1..F4 revivals
# --------------------------------------------------------------------------


@pytest.mark.parametrize("value", [
    'secret"quote', "back\\slash", "ctrl\nnewline", "tab\there", "uni sep", 'mix"\\\n\t', 'quoted-"-and-\\-value'])
def test_f1_explicit_values_with_quotes_backslashes_or_control_chars_never_survive_serialization(value, tmp_path):
    """Revival: the old write path replaced the RAW value in an already-serialized JSON string,
    so an escaped representation (secret\\"quote) slipped through both redact and assert."""
    escaped = json.dumps(value)[1:-1]
    serialized = json.dumps({"release": value})
    with pytest.raises(ValueError, match="value:redacted"):
        tool.assert_redacted(serialized, explicit=(value,))          # escaped form is now caught
    assert escaped not in tool.redact_text(serialized, explicit=(value,))
    evidence = _build(note=f"release {value} end")
    evidence["inputs"]["operationalReadiness"]["reason"] = value        # nested structured value too
    json_path, md_path = tool.write_evidence(evidence, tmp_path, "f1", explicit=(value,))
    text = json_path.read_text(encoding="utf-8") + md_path.read_text(encoding="utf-8")
    assert value not in text and escaped not in text and json.dumps(value, ensure_ascii=False)[1:-1] not in text
    assert "<value:redacted>" in text


def test_f1_redact_value_walks_keys_lists_and_nested_dicts():
    obj = {"k": ["x rel_01HZZZZZZZZZZZZZZZZZZZZZZZ", {"deep": "10.0.0.7:5432"}], "secret-key-name": 1}
    out = tool.redact_value(obj, explicit=("secret-key-name",))
    assert out == {"k": ["x <id:redacted>", {"deep": "<host:port:redacted>"}], "<value:redacted>": 1}


def test_f2_unclassified_blocker_withholds_every_blocker_derived_pass():
    """Revival: blockers=['future unclassified blocker'] left recovery items PASS."""
    evidence = _build(readiness=_readiness(catalog=_catalog(blockers=("future unclassified blocker",))))
    for key in tool.BLOCKER_DERIVED_ITEMS:
        item = evidence["items"][key]
        assert item["status"] == tool.NOT_OBSERVED, key
        assert "unclassified blocker" in item["reason"] and "future unclassified blocker" in item["reason"]
    assert evidence["scope"][tool.PASS] and evidence["verdict"] == "PASS_MEASURED_PARTIAL"
    # a known blocker next to an unknown one still FAILs its own item
    evidence = _build(readiness=_readiness(catalog=_catalog(blockers=("future unclassified blocker", "no verified backup"))))
    assert evidence["items"]["verified-backup-in-retention"]["status"] == tool.FAIL
    assert evidence["items"]["verified-off-site-backup"]["status"] == tool.NOT_OBSERVED
    assert evidence["verdict"] == "FAIL"


def test_f2_catalog_complete_false_without_blockers_is_fail_not_pass():
    """Revival: catalogComplete=false was copied into the summary but never judged."""
    catalog = _catalog()
    catalog["catalogComplete"] = False
    evidence = _build(readiness=_readiness(catalog=catalog))
    for key in tool.BLOCKER_DERIVED_ITEMS:
        assert evidence["items"][key]["status"] == tool.FAIL, key
        assert "catalogComplete" in evidence["items"][key]["reason"]
    assert evidence["verdict"] == "FAIL"


def test_f2_catalog_complete_false_is_expected_without_a_release_and_does_not_fail():
    """Without --release the tool always reports catalogComplete=false; that is the BLOCKED_EXTERNAL
    release case, not an inconsistency, and the recovery items may still PASS on their blockers."""
    evidence = _build(readiness=_readiness(catalog=_catalog(assessed=False)), release_given=False)
    assert evidence["items"]["verified-backup-in-retention"]["status"] == tool.PASS
    assert evidence["items"]["release-manifest-recorded"]["status"] == tool.BLOCKED_EXTERNAL


def test_f2_every_blocker_pilot_readiness_emits_today_is_classified():
    source = (REPO_ROOT / "src" / "saintvision" / "services" / "pilot.py").read_text(encoding="utf-8")
    emitted = re.findall(r'blockers\.append\(\s*f?"([^"]+)"', source)
    assert emitted, "pilot_readiness blocker texts not found"
    known = tuple(p for ps in tool.KNOWN_BLOCKER_PREFIXES.values() for p in ps)
    for text in emitted:
        assert tool._matches(text.replace("{len(unhealthy)}", "2"), known), text


def test_f3_browser_opt_in_false_is_not_observed_even_with_perfect_counts():
    """Revival: a proof from a run without a real browser (browserOptIn=false) passed the web item."""
    web = _web()
    web["payload"]["browserOptIn"] = False
    item = _build(web=web)["items"]["web-smoke-journeys"]
    assert item["status"] == tool.NOT_OBSERVED and "browserOptIn" in item["reason"]


@pytest.mark.parametrize("bound, proof_sha, expected, why", [
    (None, None, tool.NOT_OBSERVED, "not bound"),
    ("b" * 40, None, tool.NOT_OBSERVED, "different code SHA"),
    ("a" * 40, None, tool.PASS, None),
    ("a" * 12, None, tool.PASS, None),                 # short SHA from gh run view
    (None, "a" * 40, tool.PASS, None),                 # codeSha carried inside the proof
    (None, "c" * 40, tool.NOT_OBSERVED, "different code SHA"),
])
def test_f3_web_proof_must_be_bound_to_this_bundles_code_sha(bound, proof_sha, expected, why):
    web = _web()
    web["boundSha"] = bound
    if proof_sha:
        web["payload"]["codeSha"] = proof_sha
    item = _build(web=web)["items"]["web-smoke-journeys"]
    assert item["status"] == expected, item
    if why:
        assert why in item["reason"]


def test_f3_default_web_fixture_is_bound_so_earlier_pass_expectations_stay_honest():
    assert _web()["boundSha"] == "a" * 40 and _prov()["commit_sha"] == "a" * 40


def test_f4_unpushed_head_is_refused_by_default_and_recorded_when_allowed(tmp_path, monkeypatch):
    """Revival: a clean but local-only commit produced evidence nobody could check out."""
    monkeypatch.setenv("INV_READINESS_DSN", "postgresql://inv:pw@127.0.0.1:1/postgres")
    monkeypatch.setattr(tool, "collect_provenance", lambda executor=None: _prov())
    _stub_runners(monkeypatch)
    monkeypatch.setattr(tool, "remote_reachability", lambda sha, ref=None: {"reachable": False, "refs": [], "mode": "remote-containment"})
    assert tool.main(["--out-dir", str(tmp_path), "--label", "u", "--tenant", TENANT]) == 2
    assert not (tmp_path / "u.json").exists()
    assert tool.main(["--out-dir", str(tmp_path), "--label", "u", "--tenant", TENANT, "--allow-unpushed-head"]) == 0
    prov = json.loads((tmp_path / "u.json").read_text(encoding="utf-8"))["provenance"]
    assert prov["remoteReachable"] is False and prov["unpushedHeadAllowed"] is True and prov["remoteRefCount"] == 0


def test_f4_reachable_head_passes_and_explicit_ref_uses_ancestry(tmp_path, monkeypatch):
    monkeypatch.setenv("INV_READINESS_DSN", "postgresql://inv:pw@127.0.0.1:1/postgres")
    monkeypatch.setattr(tool, "collect_provenance", lambda executor=None: _prov())
    _stub_runners(monkeypatch)
    seen = {}

    def fake_reach(sha, ref=None):
        seen["ref"] = ref
        return {"reachable": True, "refs": [ref or "origin/x"], "mode": "explicit-ref" if ref else "remote-containment"}
    monkeypatch.setattr(tool, "remote_reachability", fake_reach)
    assert tool.main(["--out-dir", str(tmp_path), "--label", "r", "--tenant", TENANT, "--reachable-ref", "origin/integration/all-agents-unified"]) == 0
    assert seen["ref"] == "origin/integration/all-agents-unified"
    prov = json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))["provenance"]
    assert prov["remoteReachable"] is True and prov["remoteRefCount"] == 1 and prov["unpushedHeadAllowed"] is False


def test_f4_remote_reachability_reads_git_and_fails_closed_without_output(monkeypatch):
    monkeypatch.setattr(tool, "_git_lines", lambda *args: [])
    assert tool.remote_reachability("a" * 40) == {"reachable": False, "refs": [], "mode": "remote-containment", "freshness": None}
    monkeypatch.setattr(tool, "_git_lines", lambda *args: ["origin/HEAD -> origin/main", "origin/agent/claude/x"])
    assert tool.remote_reachability("a" * 40)["refs"] == ["origin/agent/claude/x"]
    assert tool.remote_reachability(None)["reachable"] is False


# --------------------------------------------------------------------------
# Codex re-review of #153 (head 663aad65): F3/F4 residual bypasses
# --------------------------------------------------------------------------


@pytest.mark.parametrize("proof_sha, expected, why", [
    ("a", tool.NOT_OBSERVED, "not 12..40 lowercase hex"),                 # 1 char matched the old mutual-prefix check
    ("a" * 11, tool.NOT_OBSERVED, "not 12..40 lowercase hex"),            # 11 chars
    ("A" * 12, tool.NOT_OBSERVED, "not 12..40 lowercase hex"),            # uppercase is NOT folded: mutant that lowercases first must die
    ("g" * 12, tool.NOT_OBSERVED, "not 12..40 lowercase hex"),            # non-hex
    ("zz" + "a" * 38, tool.NOT_OBSERVED, "not 12..40 lowercase hex"),
    ("b" * 40, tool.NOT_OBSERVED, "different code SHA"),                  # a different full SHA
    ("a" * 41, tool.NOT_OBSERVED, "not 12..40 lowercase hex"),
    ("a" * 12, tool.PASS, None),
    ("a" * 40, tool.PASS, None),
])
def test_f3_binding_requires_12_to_40_lowercase_hex_and_prefix_agreement(proof_sha, expected, why):
    web = _web()
    web["boundSha"] = proof_sha
    item = _build(web=web)["items"]["web-smoke-journeys"]
    assert item["status"] == expected, item
    if why:
        assert why in item["reason"]


def test_f3_uppercase_is_rejected_on_the_original_text_and_bundle_sha_is_validated_too():
    """Kills the ``.lower()``-before-match mutant: an uppercase proof SHA is not a binding."""
    ok, why = tool.sha_binding("A" * 40, "a" * 40)
    assert not ok and "lowercase hex" in why
    ok, why = tool.sha_binding("a" * 40, "A" * 40)
    assert not ok and "bundle code sha" in why
    ok, why = tool.sha_binding("a" * 40, "not-a-sha")
    assert not ok and "bundle code sha" in why
    assert tool.sha_binding(None, "a" * 40)[0] is False


def _fake_git(mapping):
    def lines(*args):
        return mapping.get(args, [])
    return lines


def test_f4_reachable_ref_accepts_only_verified_remote_tracking_refs(monkeypatch):
    """Revival: ``--reachable-ref HEAD`` always passed because merge-base was run on the raw string."""
    git = _fake_git({
        ("remote",): ["origin"],
        ("rev-parse", "--verify", "--quiet", "refs/remotes/origin/integration/all-agents-unified^{commit}"): ["c" * 40],
        ("ls-remote", "--heads", "origin", "integration/all-agents-unified"): ["c" * 40 + "\trefs/heads/integration/all-agents-unified"],
    })
    monkeypatch.setattr(tool, "_git_lines", git)
    monkeypatch.setattr(tool, "_git_ok", lambda *args: True)
    for bad in ("HEAD", "main", "v1.0.0", "refs/heads/main", "refs/tags/v1", "upstream/main", "origin/"):
        result = tool.remote_reachability("a" * 40, bad)
        assert result["reachable"] is False and result["mode"] == "invalid-ref", (bad, result)
    good = tool.remote_reachability("a" * 40, "origin/integration/all-agents-unified")
    assert good["reachable"] is True and good["refs"] == ["refs/remotes/origin/integration/all-agents-unified"] and good["freshness"] == "fresh"
    assert tool.remote_reachability("a" * 40, "refs/remotes/origin/integration/all-agents-unified")["reachable"] is True


def test_f4_stale_or_unverifiable_remote_tracking_ref_does_not_count(monkeypatch):
    base = {
        ("remote",): ["origin"],
        ("rev-parse", "--verify", "--quiet", "refs/remotes/origin/x^{commit}"): ["c" * 40],
    }
    monkeypatch.setattr(tool, "_git_ok", lambda *args: True)
    monkeypatch.setattr(tool, "_git_lines", _fake_git({**base, ("ls-remote", "--heads", "origin", "x"): ["d" * 40 + "\trefs/heads/x"]}))
    stale = tool.remote_reachability("a" * 40, "origin/x")
    assert stale["reachable"] is False and stale["freshness"] == "stale" and "stale" in stale["reason"]
    monkeypatch.setattr(tool, "_git_lines", _fake_git(base))  # ls-remote gave nothing (offline/auth/missing)
    unverified = tool.remote_reachability("a" * 40, "origin/x")
    assert unverified["reachable"] is False and unverified["freshness"] == "unverified"   # fail-closed, not reachable
    assert "could not be verified" in unverified["reason"]
    monkeypatch.setattr(tool, "_git_ok", lambda *args: False)
    assert tool.remote_reachability("a" * 40, "origin/x")["reason"] == "not an ancestor"


def test_f4_cli_rejects_head_local_branch_and_tag_as_reachable_ref(tmp_path, monkeypatch):
    monkeypatch.setenv("INV_READINESS_DSN", "postgresql://inv:pw@127.0.0.1:1/postgres")
    monkeypatch.setattr(tool, "collect_provenance", lambda executor=None: _prov())
    _stub_runners(monkeypatch)
    monkeypatch.setattr(tool, "remote_reachability", lambda sha, ref=None: (
        {"reachable": False, "refs": [], "mode": "invalid-ref", "reason": "not a remote-tracking ref", "freshness": None} if ref in ("HEAD", "main", "v1")
        else {"reachable": True, "refs": ["refs/remotes/origin/x"], "mode": "explicit-ref", "freshness": "fresh", "reason": None}))
    for bad in ("HEAD", "main", "v1"):
        assert tool.main(["--out-dir", str(tmp_path), "--label", "bad-" + bad, "--tenant", TENANT, "--reachable-ref", bad,
                          "--allow-unpushed-head"]) == 2, bad   # even the opt-out does not accept an invalid ref
        assert not (tmp_path / f"bad-{bad}.json").exists()
    assert tool.main(["--out-dir", str(tmp_path), "--label", "ok", "--tenant", TENANT, "--reachable-ref", "origin/x"]) == 0
    prov = json.loads((tmp_path / "ok.json").read_text(encoding="utf-8"))["provenance"]
    assert prov["remoteRefFreshness"] == "fresh" and prov["remoteReachable"] is True
