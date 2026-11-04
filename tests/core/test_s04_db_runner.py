import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools import run_s04_db_evidence


def paths(tmp_path, **changes):
    values = {
        "json_out": tmp_path / "evidence.json",
        "junit_out": tmp_path / "evidence.xml",
    }
    values.update(changes)
    return argparse.Namespace(**values)


def report():
    return {
        "schemaVersion": 1,
        "taskId": "S04-DB",
        "measurementScope": "disposable-postgresql-http-kernel",
        "operationalAcceptanceAssessed": False,
        "publicContractChanged": False,
        "migrationChanged": False,
        "physicalNodeDeliveryResumption": "UNMEASURED",
        "cases": [
            {"id": case_id, "status": "PASS"}
            for case_id in sorted(run_s04_db_evidence.EXPECTED_CASES)
        ],
    }


def test_paths_must_be_distinct(tmp_path):
    same = tmp_path / "same"
    with pytest.raises(ValueError, match="different files"):
        run_s04_db_evidence.validated_paths(paths(tmp_path, json_out=same, junit_out=same))


def test_direct_script_bootstraps_the_repository_tools_package():
    assert str(run_s04_db_evidence.ROOT) in run_s04_db_evidence.sys.path
    assert callable(run_s04_db_evidence.collect)


def test_expiry_case_does_not_mutate_the_immutable_approval_scope():
    source = run_s04_db_evidence.CASE_FILE.read_text(encoding="utf-8")
    assert "UPDATE inv.approval_requests" not in source
    assert 'return "<S04Api redacted>"' in source


@pytest.mark.parametrize(
    "change,match",
    [
        ({"schemaVersion": 2}, "schemaVersion"),
        ({"physicalNodeDeliveryResumption": "PASS"}, "UNMEASURED"),
        ({"publicContractChanged": True}, "public contract"),
        ({"migrationChanged": True}, "migration"),
        ({"operationalAcceptanceAssessed": True}, "operational acceptance"),
        ({"measurementScope": "live-five-node"}, "scope"),
    ],
)
def test_report_boundary_is_fail_closed(change, match):
    candidate = report()
    candidate.update(change)
    with pytest.raises(ValueError, match=match):
        run_s04_db_evidence.validate_report(candidate)


def test_report_rejects_missing_failed_or_secret_bearing_cases():
    missing = report()
    missing["cases"].pop()
    with pytest.raises(ValueError, match="inventory"):
        run_s04_db_evidence.validate_report(missing)
    failed = report()
    failed["cases"][0]["status"] = "FAIL"
    with pytest.raises(ValueError, match="all pass"):
        run_s04_db_evidence.validate_report(failed)
    secret = report()
    secret["diagnostic"] = "postgresql://secret@private/inv_test_deadbeef"
    with pytest.raises(ValueError, match="credential"):
        run_s04_db_evidence.validate_report(secret)


def test_missing_admin_dsn_does_not_create_artifacts(tmp_path, monkeypatch):
    monkeypatch.delenv("INV_TEST_ADMIN_DSN", raising=False)
    result = run_s04_db_evidence.main(
        [
            "--json-out",
            str(tmp_path / "evidence.json"),
            "--junit-out",
            str(tmp_path / "evidence.xml"),
        ]
    )
    assert result == 2
    assert list(tmp_path.iterdir()) == []


def test_missing_admin_dsn_removes_old_green_artifacts(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("INV_TEST_ADMIN_DSN", raising=False)
    json_out, junit_out = tmp_path / "old.json", tmp_path / "old.xml"
    json_out.write_text(json.dumps(report()), encoding="utf-8")
    junit_out.write_text("<old-green/>", encoding="utf-8")
    assert (
        run_s04_db_evidence.main(["--json-out", str(json_out), "--junit-out", str(junit_out)]) == 2
    )
    assert not json_out.exists() and not junit_out.exists()
    assert json.loads(capsys.readouterr().out)["status"] == "BLOCKED"


@pytest.mark.parametrize("bad_cases", [None, [None], [{"id": [], "status": "PASS"}]])
def test_malformed_case_inventory_is_a_refusal(bad_cases):
    candidate = report()
    candidate["cases"] = bad_cases
    with pytest.raises(ValueError):
        run_s04_db_evidence.validate_report(candidate)


def test_duplicate_green_case_cannot_replace_missing_execution():
    candidate = report()
    candidate["cases"].append(dict(candidate["cases"][0]))
    with pytest.raises(ValueError, match="inventory"):
        run_s04_db_evidence.validate_report(candidate)


@pytest.mark.parametrize(
    "xml",
    [
        "<testsuite tests='0'/>",
        "<testsuite tests='1'><testcase name='different_test'/></testsuite>",
        f"<testsuite tests='1'><testcase name='{run_s04_db_evidence.EXPECTED_TEST}'><skipped/></testcase></testsuite>",
        f"<testsuite tests='1' errors='1'><testcase name='{run_s04_db_evidence.EXPECTED_TEST}'/></testsuite>",
    ],
)
def test_empty_wrong_skipped_or_failed_junit_cannot_be_green(tmp_path, xml):
    path = tmp_path / "result.xml"
    path.write_text(xml, encoding="utf-8")
    with pytest.raises(ValueError, match="JUnit"):
        run_s04_db_evidence.validate_junit(path)


def test_failed_rerun_removes_stale_artifacts(tmp_path, monkeypatch):
    json_out = tmp_path / "evidence.json"
    junit_out = tmp_path / "evidence.xml"
    json_out.write_text('{"stale":true}', encoding="utf-8")
    junit_out.write_text("<stale/>", encoding="utf-8")
    monkeypatch.setenv("INV_TEST_ADMIN_DSN", "set-but-never-used-by-stub")
    monkeypatch.setattr(
        run_s04_db_evidence,
        "measurement_provenance",
        lambda: {"codeSha": "a" * 40},
    )
    monkeypatch.setattr(
        run_s04_db_evidence.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1),
    )
    result = run_s04_db_evidence.main(["--json-out", str(json_out), "--junit-out", str(junit_out)])
    assert result == 1
    assert not json_out.exists()
    assert not junit_out.exists()


def test_success_uses_only_the_approved_single_integration_file(tmp_path, monkeypatch):
    json_out = tmp_path / "evidence.json"
    junit_out = tmp_path / "evidence.xml"
    observed = {}
    monkeypatch.setenv("INV_TEST_ADMIN_DSN", "set-but-never-used-by-stub")
    monkeypatch.setattr(
        run_s04_db_evidence,
        "measurement_provenance",
        lambda: {"codeSha": "a" * 40},
    )

    def completed(command, **kwargs):
        observed["command"] = command
        environment = kwargs["env"]
        Path(environment["INV_S04_DB_EVIDENCE_JSON"]).write_text(
            json.dumps(report()), encoding="utf-8"
        )
        junit_out.write_text(
            f"<testsuite tests='1'><testcase name='{run_s04_db_evidence.EXPECTED_TEST}'/></testsuite>",
            encoding="utf-8",
        )
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(run_s04_db_evidence.subprocess, "run", completed)
    result = run_s04_db_evidence.main(["--json-out", str(json_out), "--junit-out", str(junit_out)])
    assert result == 0
    normalized = [item.replace("\\", "/") for item in observed["command"]]
    assert normalized.count("tests/integration/s04_db_runner_case.py") == 1
    assert not any("test_approvals.py" in item for item in normalized)
    assert not any("test_postgres.py" in item for item in normalized)


@pytest.mark.parametrize("exit_code", [0, 1])
def test_green_json_without_successful_executable_junit_is_removed(
    tmp_path, monkeypatch, exit_code
):
    json_out, junit_out = tmp_path / "evidence.json", tmp_path / "evidence.xml"
    monkeypatch.setenv("INV_TEST_ADMIN_DSN", "stub-only")
    monkeypatch.setattr(run_s04_db_evidence, "measurement_provenance", lambda: {})

    def completed(*args, **kwargs):
        json_out.write_text(json.dumps(report()), encoding="utf-8")
        return SimpleNamespace(returncode=exit_code)

    monkeypatch.setattr(run_s04_db_evidence.subprocess, "run", completed)
    assert (
        run_s04_db_evidence.main(["--json-out", str(json_out), "--junit-out", str(junit_out)]) != 0
    )
    assert not json_out.exists()


@pytest.mark.parametrize("invalid_part", ["report", "junit", "missing-report"])
def test_post_validation_failure_removes_the_requested_evidence_pair(tmp_path, monkeypatch, invalid_part):
    json_out, junit_out = tmp_path / "evidence.json", tmp_path / "evidence.xml"
    monkeypatch.setenv("INV_TEST_ADMIN_DSN", "stub-only")
    monkeypatch.setattr(run_s04_db_evidence, "measurement_provenance", lambda: {})

    def completed(*args, **kwargs):
        payload = report()
        if invalid_part == "report":
            payload["physicalNodeDeliveryResumption"] = "PASS"
        if invalid_part != "missing-report":
            json_out.write_text(json.dumps(payload), encoding="utf-8")
        name = "unapproved_case" if invalid_part == "junit" else run_s04_db_evidence.EXPECTED_TEST
        junit_out.write_text(f"<testsuite tests='1'><testcase name='{name}'/></testsuite>", encoding="utf-8")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(run_s04_db_evidence.subprocess, "run", completed)
    assert run_s04_db_evidence.main(["--json-out", str(json_out), "--junit-out", str(junit_out)]) == 2
    assert not json_out.exists()
    assert not junit_out.exists()
