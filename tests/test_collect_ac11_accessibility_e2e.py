"""PG-free mutation tests for the AC-11 accessibility/E2E hosted collector."""

from __future__ import annotations

import copy
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import collect_ac11_accessibility_e2e as tool  # noqa: E402


SOURCE = "a" * 40
TREE = "b" * 40


def _journeys() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for name in sorted(tool.EXPECTED_JOURNEYS):
        if name == "test_full_studio_login_project_approval_and_logout":
            rows.extend(
                {"classname": "tests.browser", "name": f"{name}[{parameter}]"}
                for parameter in ("False", "True")
            )
        else:
            rows.append({"classname": "tests.browser", "name": name})
    return rows


def _proof() -> dict:
    return {
        "browserOptIn": True,
        "exitCode": 0,
        "subprocessExitCode": 0,
        "evidenceStatus": "complete",
        "isolatedContainerRemoved": True,
        "tests": {"failure": 0, "error": 0, "skipped": 0, "passed": 6},
    }


def _write_browser_junit(
    path: Path, *, failure_name: str | None = None, skipped_name: str | None = None
) -> None:
    suite = ET.Element("testsuite", tests="6")
    for row in _journeys():
        case = ET.SubElement(suite, "testcase", classname=row["classname"], name=row["name"])
        if row["name"] == failure_name:
            ET.SubElement(case, "failure", message="measured product failure")
        if row["name"] == skipped_name:
            ET.SubElement(case, "skipped", message="measured skip")
    ET.ElementTree(suite).write(path, encoding="utf-8", xml_declaration=True)


def _invariants() -> dict:
    rows = {
        "inv01_bidirectionalSwitcher": {"pass": True},
        "inv02_trafficLightControls": {"pass": True},
        "inv03_dynamicZIndex": {"pass": True},
        "inv04_dockIntegration": {"pass": True},
        "inv05_keyboardAltTab": {"pass": True},
        "inv06_modalEscapeDismissal": {
            "pass": "PARTIAL",
            "modalDismissed": True,
            "triggerFocusRestored": False,
        },
        "inv07_layoutPersistence": {"pass": True},
        "inv08_colorContrastAA": {"pass": True},
        "inv09_honestCapacityMetrics": {"pass": True},
    }
    contrast = [
        {
            "element": element,
            "numericalRatio": 7.0,
            "ratio": "7.00:1",
            "pass": True,
        }
        for element in sorted(tool.EXPECTED_CONTRAST)
    ]
    return {
        "gitCommitSha": SOURCE,
        "browser": "Google Chrome 140.0.0.0 (Blink engine)",
        "frontendTransport": "vite-dev-server-with-browser-node-fixture",
        "verified": True,
        "summary": {
            "totalChecks": 9,
            "passedChecks": 8,
            "partialChecks": 1,
            "failedChecks": 0,
        },
        "invariants": rows,
        "accessibility": {"contrastChecks": contrast, "keyboardNavigationPass": False},
    }


@pytest.fixture
def inputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    paths = {
        "proof": tmp_path / "proof.json",
        "identities": tmp_path / "identities.json",
        "browser_junit": tmp_path / "browser.xml",
        "invariants": tmp_path / "invariants.json",
    }
    paths["identities"].write_text(json.dumps(_journeys()), encoding="utf-8")
    _write_browser_junit(paths["browser_junit"])
    proof = _proof()
    proof["xmlSha256"] = tool.file_sha256(paths["browser_junit"])
    proof["caseIdentitiesSha256"] = tool.file_sha256(paths["identities"])
    paths["proof"].write_text(json.dumps(proof), encoding="utf-8")
    paths["invariants"].write_text(json.dumps(_invariants()), encoding="utf-8")
    monkeypatch.setattr(tool, "validate_checkout", lambda source: (TREE, True))
    return paths


def _build(paths: dict[str, Path]) -> dict:
    return tool.build_report(
        source_run_id="36790000000",
        source_head_sha=SOURCE,
        runner_image="Linux-X64",
        browser_version="Google Chrome 140.0.0.0 (Blink engine)",
        browser_proof_path=paths["proof"],
        case_identities_path=paths["identities"],
        browser_junit_path=paths["browser_junit"],
        invariant_path=paths["invariants"],
        started_at="2026-10-01T03:00:00Z",
    )


def test_complete_hosted_inputs_measure_known_failures_without_acceptance_claim(inputs):
    report = _build(inputs)
    assert report["verdict"] == "MEASURED_FAIL"
    assert report["acceptanceClaim"] is False
    observations = {row["metric"]: row for row in report["payload"]["observations"]}
    assert observations["canonicalJourneyFailureCount"]["value"] == 0
    assert observations["desktopInvariantFailureCount"]["value"] == 1
    assert observations["keyboardFailureCount"]["value"] == 1
    assert observations["manualAcceptanceMissingCount"]["value"] == 1
    assert report["payloadSha256"] == tool.canonical_sha256(report["payload"])


def test_automatic_success_still_cannot_fabricate_manual_acceptance(inputs):
    report = _invariants()
    row = report["invariants"]["inv06_modalEscapeDismissal"]
    row.update({"pass": True, "triggerFocusRestored": True})
    report["summary"].update(passedChecks=9, partialChecks=0)
    report["accessibility"]["keyboardNavigationPass"] = True
    inputs["invariants"].write_text(json.dumps(report), encoding="utf-8")
    built = _build(inputs)
    observations = {row["metric"]: row for row in built["payload"]["observations"]}
    assert observations["desktopInvariantFailureCount"]["value"] == 0
    assert observations["keyboardFailureCount"]["value"] == 0
    assert observations["manualAcceptanceMissingCount"]["errorsByClass"] == {
        "manual-acceptance-not-supplied": 1
    }
    assert built["verdict"] == "MEASURED_FAIL"


def test_missing_or_extra_journey_is_invalid_not_a_smaller_denominator(inputs):
    identities = _journeys()[:-1]
    proof = _proof()
    proof["tests"]["passed"] = 5
    inputs["identities"].write_text(json.dumps(identities), encoding="utf-8")
    proof["xmlSha256"] = tool.file_sha256(inputs["browser_junit"])
    proof["caseIdentitiesSha256"] = tool.file_sha256(inputs["identities"])
    inputs["proof"].write_text(json.dumps(proof), encoding="utf-8")
    with pytest.raises(tool.AccessibilityEvidenceError, match="identity set drifted"):
        _build(inputs)


def test_skip_is_measured_as_a_failed_logical_journey(inputs):
    proof = _proof()
    skipped_name = _journeys()[0]["name"]
    _write_browser_junit(inputs["browser_junit"], skipped_name=skipped_name)
    proof["tests"].update(passed=5, skipped=1)
    proof["xmlSha256"] = tool.file_sha256(inputs["browser_junit"])
    proof["caseIdentitiesSha256"] = tool.file_sha256(inputs["identities"])
    inputs["proof"].write_text(json.dumps(proof), encoding="utf-8")
    report = _build(inputs)
    observation = next(
        row for row in report["payload"]["observations"]
        if row["metric"] == "canonicalJourneyFailureCount"
    )
    assert observation["failureCount"] == 1


def test_product_journey_failure_is_measured_not_treated_as_missing(inputs):
    proof = _proof()
    proof.update(exitCode=1, subprocessExitCode=1, evidenceStatus="partial")
    failure_name = _journeys()[0]["name"]
    _write_browser_junit(inputs["browser_junit"], failure_name=failure_name)
    proof["tests"].update(passed=5, failure=1)
    proof["xmlSha256"] = tool.file_sha256(inputs["browser_junit"])
    proof["caseIdentitiesSha256"] = tool.file_sha256(inputs["identities"])
    inputs["proof"].write_text(json.dumps(proof), encoding="utf-8")
    report = _build(inputs)
    observation = next(
        row for row in report["payload"]["observations"]
        if row["metric"] == "canonicalJourneyFailureCount"
    )
    assert observation["failureCount"] == 1
    assert report["verdict"] == "MEASURED_FAIL"


def test_partial_invariant_cannot_be_labeled_pass_by_summary(inputs):
    report = _invariants()
    report["summary"].update(passedChecks=9, partialChecks=0)
    inputs["invariants"].write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(tool.AccessibilityEvidenceError, match="summary differs"):
        _build(inputs)


def test_contrast_boolean_is_recomputed_from_numeric_ratio(inputs):
    report = _invariants()
    report["accessibility"]["contrastChecks"][0]["numericalRatio"] = 3.5
    inputs["invariants"].write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(tool.AccessibilityEvidenceError, match="differs from ratio"):
        _build(inputs)


def test_source_head_mismatch_is_invalid(inputs):
    report = _invariants()
    report["gitCommitSha"] = "c" * 40
    inputs["invariants"].write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(tool.AccessibilityEvidenceError, match="not bound"):
        _build(inputs)


def test_browser_junit_and_identity_digests_are_recomputed(inputs):
    proof = json.loads(inputs["proof"].read_text(encoding="utf-8"))
    proof["xmlSha256"] = "0" * 64
    inputs["proof"].write_text(json.dumps(proof), encoding="utf-8")
    with pytest.raises(tool.AccessibilityEvidenceError, match="JUnit digest drifted"):
        _build(inputs)


def test_parameterized_journey_requires_both_physical_cases(inputs):
    identities = _journeys()
    identities.pop()
    inputs["identities"].write_text(json.dumps(identities), encoding="utf-8")
    proof = json.loads(inputs["proof"].read_text(encoding="utf-8"))
    proof["caseIdentitiesSha256"] = tool.file_sha256(inputs["identities"])
    inputs["proof"].write_text(json.dumps(proof), encoding="utf-8")
    with pytest.raises(tool.AccessibilityEvidenceError, match="identity set drifted"):
        _build(inputs)


def test_empty_identity_list_is_rejected(inputs):
    inputs["identities"].write_text("[]", encoding="utf-8")
    proof = json.loads(inputs["proof"].read_text(encoding="utf-8"))
    proof["caseIdentitiesSha256"] = tool.file_sha256(inputs["identities"])
    inputs["proof"].write_text(json.dumps(proof), encoding="utf-8")
    with pytest.raises(tool.AccessibilityEvidenceError, match="empty or malformed"):
        _build(inputs)


def test_junit_preserves_each_failed_metric(tmp_path: Path, inputs):
    report = _build(inputs)
    junit = tmp_path / "evidence.xml"
    tool.write_junit(report, junit)
    text = junit.read_text(encoding="utf-8")
    assert 'tests="5"' in text
    assert 'failures="3"' in text
    assert "manualAcceptanceMissingCount" in text


def test_target_pin_and_criteria_are_literal_and_complete():
    assert tool.TARGET_COMMIT == "4b6d4fab2925bb422f1deb6db2794fac0ccaa54f"
    assert tool.TARGET_BLOB == "30bc37df03e1568f4af126843ab1fefb71b23de0"
    assert set(tool.CRITERIA) == {
        "canonicalJourneyFailureCount",
        "desktopInvariantFailureCount",
        "contrastFailureCount",
        "keyboardFailureCount",
        "manualAcceptanceMissingCount",
    }


def test_workflow_is_opt_in_exact_head_and_does_not_cancel_measurement():
    workflow = (ROOT / ".github/workflows/ac11-accessibility-e2e.yml").read_text(encoding="utf-8")
    assert "run-ac11-accessibility" in workflow
    assert "ref: ${{ env.SOURCE_HEAD_SHA }}" in workflow
    assert "fetch-depth: 0" in workflow
    assert "persist-credentials: false" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "types: [opened, labeled, synchronize, reopened]" in workflow
    assert "--browser-junit" in workflow
    assert "tools/collect_ac11_accessibility_e2e.py" in workflow
    assert "retention-days: 30" in workflow
    assert "Build exact frontend candidate image" not in workflow


def test_real_browser_bootstrap_uses_the_current_resolved_oidc_config_shape():
    source = (ROOT / "tools/run_real_browser_acceptance.py").read_text(encoding="utf-8")
    assert "redirectUri: '{frontend_url}/callback'" in source
    assert "redirectUri: '{frontend_url}/callback',\n                    config: testConfig" in source
    assert source.index("clientId: 'saintvision-web'") < source.index("scope: 'openid profile email'")
    assert source.index("scope: 'openid profile email'") < source.index("idpAuthorizeUrl: '{frontend_url}/oauth/authorize'")
    assert source.index("idpTokenUrl: '{frontend_url}/oauth/token'") < source.index("redirectUri: '{frontend_url}/callback'")
    assert "vite-dev-server-with-browser-node-fixture" in source
    assert '"keyboardNavigationPass": focus_is_trigger' in source
    assert '"pass": contrast_pass' in source
    assert '"pass": capacity_pass' in source
    assert "page.route(route_glob, fulfill_node_page)" in source
    assert "lambda route, body=" not in source
    assert '"passedChecks": 8' not in source
    assert '"keyboardNavigationPass": True' not in source


def test_main_returns_two_when_report_validation_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        tool,
        "build_report",
        lambda **kwargs: (_ for _ in ()).throw(tool.AccessibilityEvidenceError("invalid fixture")),
    )
    args = [
        "--source-run-id", "1",
        "--source-head-sha", SOURCE,
        "--runner-image", "Linux-X64",
        "--browser-version", "Google Chrome 140",
        "--browser-proof", str(tmp_path / "proof.json"),
        "--case-identities", str(tmp_path / "identities.json"),
        "--browser-junit", str(tmp_path / "browser.xml"),
        "--desktop-invariants", str(tmp_path / "invariants.json"),
        "--started-at", "2026-10-01T03:00:00Z",
        "--report", str(tmp_path / "report.json"),
        "--junit", str(tmp_path / "report.xml"),
    ]
    assert tool.main(args) == 2
