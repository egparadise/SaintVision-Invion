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


@pytest.mark.parametrize(
    "change,match",
    [
        ({"schemaVersion": 2}, "schemaVersion"),
        ({"physicalNodeDeliveryResumption": "PASS"}, "UNMEASURED"),
        ({"publicContractChanged": True}, "public contract"),
        ({"migrationChanged": True}, "migration"),
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
        junit_out.write_text("<testsuite/>", encoding="utf-8")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(run_s04_db_evidence.subprocess, "run", completed)
    result = run_s04_db_evidence.main(["--json-out", str(json_out), "--junit-out", str(junit_out)])
    assert result == 0
    normalized = [item.replace("\\", "/") for item in observed["command"]]
    assert normalized.count("tests/integration/s04_db_runner_case.py") == 1
    assert not any("test_approvals.py" in item for item in normalized)
    assert not any("test_postgres.py" in item for item in normalized)
