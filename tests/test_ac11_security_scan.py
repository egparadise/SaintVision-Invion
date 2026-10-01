"""PG-free mutation tests for the AC-11 dependency/SAST evidence producer."""

from __future__ import annotations

import ast
import copy
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import run_ac11_security_scan as tool  # noqa: E402


SOURCE = "a" * 40
TREE = "b" * 40
OBJECT = "d" * 40


def base_allowlist() -> dict:
    return {
        "schemaVersion": "1.0.0",
        "verifiedAt": "2026-09-29T00:03:32+09:00",
        "producer": {"path": "tools/run_ac11_security_scan.py", "blob": OBJECT},
        "workflow": {"path": ".github/workflows/ac11-security-scan.yml", "blob": OBJECT},
        "importer": {"path": "tools/import_ac11_security_scan.py", "blob": OBJECT},
        "scanners": [
            {
                "id": "bandit",
                "version": "1.9.4",
                "scopePaths": ["services/control-plane/src", "src/saintvision"],
                "severityPolicy": "HIGH_ONLY",
            },
            {
                "id": "pip-audit",
                "version": "2.10.1",
                "scopePaths": ["requirements-core.txt"],
                "severityPolicy": "ANY_VULNERABILITY_AS_HIGH",
            },
        ],
        "acceptedFindings": [],
    }


@pytest.fixture
def source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    root = tmp_path
    allowlist_path = (
        root
        / "docs"
        / "vault"
        / "30_Development"
        / "Evidence"
        / "s11-security-dependency-sast-allowlist-v1.json"
    )
    allowlist_path.parent.mkdir(parents=True)
    allowlist_path.write_text(json.dumps(base_allowlist()), encoding="utf-8")
    (root / "requirements-core.txt").write_text(
        "fastapi==0.141.1\npydantic==2.13.5\n", encoding="utf-8"
    )
    source_files = [
        root / "services" / "control-plane" / "src" / "inv" / "sample.py",
        root / "src" / "saintvision" / "sample.py",
    ]
    for path in source_files:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("VALUE = 1\n", encoding="utf-8")
    pip_path = root / "pip-audit.json"
    bandit_path = root / "bandit.json"
    pip_path.write_text(
        json.dumps(
            {
                "dependencies": [
                    {"name": "FastAPI", "version": "0.141.1", "vulns": []},
                    {"name": "Pydantic", "version": "2.13.5", "vulns": []},
                ]
            }
        ),
        encoding="utf-8",
    )
    bandit_path.write_text(
        json.dumps(
            {
                "results": [],
                "errors": [],
                "metrics": {
                    "services/control-plane/src/inv/sample.py": {},
                    "src/saintvision/sample.py": {},
                    "_totals": {},
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(tool, "ROOT", root)

    def fake_git(*args: str) -> str:
        if args == ("rev-parse", "HEAD"):
            return SOURCE
        if args == ("rev-parse", "HEAD^{tree}"):
            return TREE
        if args == ("status", "--porcelain"):
            return ""
        if args[0] == "rev-parse" and args[1].startswith("HEAD:"):
            return OBJECT
        raise AssertionError(args)

    monkeypatch.setattr(tool, "_git", fake_git)
    return {"allowlist": allowlist_path, "pip": pip_path, "bandit": bandit_path}


def build(source: dict[str, Path], **overrides: object) -> dict:
    values: dict[str, object] = {
        "source_run_id": "36440000000",
        "source_head_sha": SOURCE,
        "runner_image": "Linux-X64",
        "pip_audit_path": source["pip"],
        "bandit_path": source["bandit"],
        "pip_audit_exit": 0,
        "bandit_exit": 0,
        "pip_audit_version": "2.10.1",
        "bandit_version": "1.9.4",
        "scan_started_at": "2026-09-28T15:00:00Z",
        "allowlist_path": source["allowlist"],
    }
    values.update(overrides)
    return tool.build_report(**values)  # type: ignore[arg-type]


def test_complete_zero_finding_report_is_measured_pass_and_redacted(source):
    report = build(source)
    assert report["verdict"] == "MEASURED_PASS"
    assert report["failureClass"] == "NONE"
    assert report["payload"]["criticalHighFindings"] == []
    assert report["payload"]["auditedDependencies"] == [
        {"name": "fastapi", "version": "0.141.1"},
        {"name": "pydantic", "version": "2.13.5"},
    ]
    assert report["payload"]["summaries"]["bandit"]["scannedFileCount"] == 2
    assert report["environment"]["externalServicesRequired"] is True
    assert report["payloadSha256"] == tool.canonical_sha256(report["payload"])
    serialized = json.dumps(report).lower()
    assert "description" not in serialized
    assert "issue_text" not in serialized
    assert "more_info" not in serialized


def test_workflow_redaction_checks_fields_not_benign_path_substrings():
    workflow = (ROOT / ".github/workflows/ac11-security-scan.yml").read_text(encoding="utf-8")
    assert "forbidden_keys =" in workflow
    assert "assert_redacted(report)" in workflow
    assert "name in lowered" not in workflow


def test_reviewed_pyjwt_security_pin_is_identical_in_runtime_and_scan_input():
    expected = "PyJWT==2.15.1"
    requirements = (ROOT / "requirements-core.txt").read_text(encoding="utf-8").splitlines()
    project = (ROOT / "services/control-plane/pyproject.toml").read_text(encoding="utf-8")

    assert [line for line in requirements if line.startswith("PyJWT==")] == [expected]
    assert project.count(f'"{expected}"') == 1
    assert "PyJWT==2.13.0" not in project


def test_pip_audit_vulnerability_is_conservatively_high_and_cannot_be_ignored(source):
    source["pip"].write_text(
        json.dumps(
            {
                "dependencies": [
                    {"name": "fastapi", "version": "0.141.1", "vulns": []},
                    {"name": "pydantic", "version": "2.13.5", "vulns": []},
                    {
                        "name": "Example_Pkg",
                        "version": "1.2.3",
                        "vulns": [
                            {
                                "id": "PYSEC-2099-1",
                                "description": "must never be serialized",
                                "fix_versions": ["1.2.4"],
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    report = build(source, pip_audit_exit=1)
    finding = report["payload"]["criticalHighFindings"][0]
    assert finding == {
        "findingId": "pip-audit:example-pkg:1.2.3:PYSEC-2099-1",
        "scanner": "pip-audit",
        "severity": "HIGH",
        "ruleId": "PYSEC-2099-1",
        "component": "example-pkg",
        "location": "1.2.3",
    }
    assert report["verdict"] == "MEASURED_FAIL"
    assert report["failureClass"] == "UNALLOWLISTED_CRITICAL_HIGH"
    assert "must never be serialized" not in json.dumps(report)


def test_bandit_high_uses_repo_relative_identity_and_out_of_scope_fails(source):
    source["bandit"].write_text(
        json.dumps(
            {
                "results": [
                    {
                        "filename": "services/control-plane/src/inv/example.py",
                        "line_number": 17,
                        "issue_severity": "HIGH",
                        "test_id": "B999",
                        "issue_text": "never serialize source prose",
                    }
                ],
                "errors": [],
                "metrics": {
                    "services/control-plane/src/inv/sample.py": {},
                    "src/saintvision/sample.py": {},
                    "_totals": {},
                },
            }
        ),
        encoding="utf-8",
    )
    report = build(source, bandit_exit=1)
    assert report["payload"]["criticalHighFindings"][0]["findingId"] == (
        "bandit:B999:services/control-plane/src/inv/example.py:17"
    )
    assert report["verdict"] == "MEASURED_FAIL"

    value = json.loads(source["bandit"].read_text(encoding="utf-8"))
    value["results"][0]["filename"] = "tests/not-registered.py"
    with pytest.raises(tool.SecurityScanError, match="outside the registered scope"):
        tool.parse_bandit(value, ["services/control-plane/src", "src/saintvision"])


def test_bandit_errors_and_incomplete_inventory_fail_closed(source):
    value = json.loads(source["bandit"].read_text(encoding="utf-8"))
    value["errors"] = [{"filename": "src/saintvision/sample.py", "reason": "syntax"}]
    source["bandit"].write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(tool.SecurityScanError, match="did not parse every"):
        build(source)

    value["errors"] = []
    value["metrics"].pop("src/saintvision/sample.py")
    source["bandit"].write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(tool.SecurityScanError, match="inventory differs"):
        build(source)


@pytest.mark.parametrize(
    "value",
    [
        {"dependencies": []},
        {"dependencies": [{"name": "fastapi", "version": "0.141.1", "vulns": []}]},
        {
            "dependencies": [
                {"name": "fastapi", "version": "0.141.1", "vulns": []},
                {
                    "name": "pydantic",
                    "version": "2.13.5",
                    "vulns": [],
                    "skip_reason": "unresolved",
                },
            ]
        },
    ],
)
def test_pip_audit_empty_missing_or_skipped_pin_fails_closed(source, value):
    source["pip"].write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(tool.SecurityScanError):
        build(source)


def test_truncated_json_and_unknown_bandit_severity_fail_closed(source):
    source["pip"].write_text('{"dependencies":', encoding="utf-8")
    with pytest.raises(tool.SecurityScanError, match="report unreadable"):
        build(source)
    source["pip"].write_text(
        json.dumps(
            {
                "dependencies": [
                    {"name": "fastapi", "version": "0.141.1", "vulns": []},
                    {"name": "pydantic", "version": "2.13.5", "vulns": []},
                ]
            }
        ),
        encoding="utf-8",
    )
    value = json.loads(source["bandit"].read_text(encoding="utf-8"))
    value["results"] = [
        {
            "filename": "src/saintvision/sample.py",
            "line_number": 1,
            "issue_severity": "UNKNOWN",
            "test_id": "B999",
        }
    ]
    source["bandit"].write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(tool.SecurityScanError, match="severity is unsupported"):
        build(source)


def test_allowlist_requires_reason_expiry_and_exact_current_finding(source):
    source["pip"].write_text(
        json.dumps(
            {
                "dependencies": [
                    {"name": "fastapi", "version": "0.141.1", "vulns": []},
                    {"name": "pydantic", "version": "2.13.5", "vulns": []},
                    {
                        "name": "example",
                        "version": "1",
                        "vulns": [{"id": "CVE-2099-0001"}],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    accepted = base_allowlist()
    accepted["acceptedFindings"] = [
        {
            "findingId": "pip-audit:example:1:CVE-2099-0001",
            "severity": "HIGH",
            "reason": "temporary reviewed compatibility exception",
            "expiresAt": "2099-01-01T00:00:00Z",
        }
    ]
    source["allowlist"].write_text(json.dumps(accepted), encoding="utf-8")
    assert build(source, pip_audit_exit=1)["verdict"] == "MEASURED_PASS"

    missing_reason = copy.deepcopy(accepted)
    missing_reason["acceptedFindings"][0]["reason"] = ""
    source["allowlist"].write_text(json.dumps(missing_reason), encoding="utf-8")
    with pytest.raises(tool.SecurityScanError, match="reason is required"):
        build(source, pip_audit_exit=1)

    expired = copy.deepcopy(accepted)
    expired["acceptedFindings"][0]["expiresAt"] = "2020-01-01T00:00:00Z"
    source["allowlist"].write_text(json.dumps(expired), encoding="utf-8")
    report = build(source, pip_audit_exit=1)
    assert report["verdict"] == "MEASURED_FAIL"
    assert report["failureClass"] == "EXPIRED_ALLOWLIST"


def test_missing_or_failed_scanner_is_not_observed_not_zero_findings(source):
    report = build(source, pip_audit_exit=2)
    assert report["reportAvailable"] is False
    assert report["status"] == "unavailable"
    assert report["verdict"] == "NOT_OBSERVED"
    assert report["failureClass"] == "SCANNER_UNAVAILABLE"


def test_version_and_dirty_checkout_are_fail_closed(source, monkeypatch):
    with pytest.raises(tool.SecurityScanError, match="installed scanner versions"):
        build(source, bandit_version="1.0.0")

    original = tool._git

    def dirty_git(*args: str) -> str:
        if args == ("status", "--porcelain"):
            return "?? evidence/forged.json"
        return original(*args)

    monkeypatch.setattr(tool, "_git", dirty_git)
    with pytest.raises(tool.SecurityScanError, match="checkout is dirty"):
        build(source)


def test_git_sha1_wire_identity_is_explicitly_not_a_security_digest():
    path = ROOT / "services" / "control-plane" / "src" / "inv" / "remote_git.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "hashlib"
        and node.func.attr == "sha1"
    ]
    assert len(calls) == 1
    assert any(
        keyword.arg == "usedforsecurity"
        and isinstance(keyword.value, ast.Constant)
        and keyword.value.value is False
        for keyword in calls[0].keywords
    )
