"""PG-free mutation tests for the AC-11 accessibility/E2E hosted collector."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import collect_ac11_accessibility_e2e as tool  # noqa: E402


SOURCE = "a" * 40
TREE = "b" * 40


def _journeys() -> list[dict[str, str]]:
    return [
        {"classname": "tests.browser", "name": name}
        for name in sorted(tool.EXPECTED_JOURNEYS)
    ]


def _proof() -> dict:
    return {
        "browserOptIn": True,
        "exitCode": 0,
        "subprocessExitCode": 0,
        "evidenceStatus": "complete",
        "isolatedContainerRemoved": True,
        "tests": {"failure": 0, "error": 0, "skipped": 0, "passed": 5},
    }


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
        "verified": True,
        "summary": {
            "totalChecks": 9,
            "passedChecks": 8,
            "partialChecks": 1,
            "failedChecks": 0,
        },
        "invariants": rows,
        "accessibility": {"contrastChecks": contrast, "keyboardNavigationPass": True},
    }


@pytest.fixture
def inputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    paths = {
        "proof": tmp_path / "proof.json",
        "identities": tmp_path / "identities.json",
        "invariants": tmp_path / "invariants.json",
    }
    paths["proof"].write_text(json.dumps(_proof()), encoding="utf-8")
    paths["identities"].write_text(json.dumps(_journeys()), encoding="utf-8")
    paths["invariants"].write_text(json.dumps(_invariants()), encoding="utf-8")
    monkeypatch.setattr(tool, "validate_checkout", lambda source: (TREE, True))
    return paths


def _build(paths: dict[str, Path]) -> dict:
    return tool.build_report(
        source_run_id="36790000000",
        source_head_sha=SOURCE,
        runner_image="Linux-X64",
        browser_proof_path=paths["proof"],
        case_identities_path=paths["identities"],
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
    proof["tests"]["passed"] = 4
    inputs["identities"].write_text(json.dumps(identities), encoding="utf-8")
    inputs["proof"].write_text(json.dumps(proof), encoding="utf-8")
    with pytest.raises(tool.AccessibilityEvidenceError, match="identity set drifted"):
        _build(inputs)


def test_skip_cannot_be_reported_as_a_completed_browser_run(inputs):
    proof = _proof()
    proof["tests"].update(passed=4, skipped=1)
    inputs["proof"].write_text(json.dumps(proof), encoding="utf-8")
    with pytest.raises(tool.AccessibilityEvidenceError, match="outcome differs"):
        _build(inputs)


def test_product_journey_failure_is_measured_not_treated_as_missing(inputs):
    proof = _proof()
    proof.update(exitCode=1, subprocessExitCode=1, evidenceStatus="partial")
    proof["tests"].update(passed=4, failure=1)
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


def test_junit_preserves_each_failed_metric(tmp_path: Path, inputs):
    report = _build(inputs)
    junit = tmp_path / "evidence.xml"
    tool.write_junit(report, junit)
    text = junit.read_text(encoding="utf-8")
    assert 'tests="5"' in text
    assert 'failures="3"' in text
    assert "manualAcceptanceMissingCount" in text


def test_target_pin_and_criteria_are_literal_and_complete():
    assert tool.TARGET_COMMIT == "a3ed04f189d5b2b7672348069b160a95be620267"
    assert tool.TARGET_BLOB == "7ec8eb1409531011737eaea79c4516bb130cf990"
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
    assert "tools/collect_ac11_accessibility_e2e.py" in workflow
    assert "retention-days: 30" in workflow
