"""Targeted regression and unit tests for verify_five_node_browser_acceptance."""

from __future__ import annotations

import json
from pathlib import Path
import time
from unittest.mock import MagicMock, patch
import pytest

from tools.verify_five_node_browser_acceptance import (
    validate_five_node_acceptance_config,
    sanitize_evidence_data,
    evaluate_heartbeat_freshness,
    load_nodes_from_inventory,
    FiveNodeAcceptanceRunner,
    FIXTURE_FIVE_NODE_IDS,
    FIXTURE_PROJECT_ID,
)


def test_validate_config_accepts_five_distinct_nodes():
    nodes = [f"nod_01M6TESTPC{i}A1B2C3D4E5F6G7H" for i in range(1, 6)]
    result = validate_five_node_acceptance_config(nodes, "prj_test_01")
    assert result["valid"] is True
    assert result["status"] == "CONFIG_VALID"
    assert len(result["expectedNodes"]) == 5
    assert result["errors"] == []


def test_validate_config_rejects_fewer_than_five_nodes():
    nodes = [f"nod_01M6TESTPC{i}A1B2C3D4E5F6G7H" for i in range(1, 5)]  # only 4 nodes
    result = validate_five_node_acceptance_config(nodes, "prj_test_01")
    assert result["valid"] is False
    assert result["status"] == "PREREQUISITES_MISSING"
    assert any("Expected exactly 5" in err for err in result["errors"])


def test_validate_config_rejects_more_than_five_nodes():
    nodes = [f"nod_01M6TESTPC{i}A1B2C3D4E5F6G7H" for i in range(1, 7)]  # 6 nodes
    result = validate_five_node_acceptance_config(nodes, "prj_test_01")
    assert result["valid"] is False
    assert result["status"] == "PREREQUISITES_MISSING"
    assert any("Expected exactly 5" in err for err in result["errors"])


def test_validate_config_rejects_duplicate_node_ids():
    nodes = [
        "nod_01M6TESTPC1A1B2C3D4E5F6G7H",
        "nod_02M6TESTPC2A1B2C3D4E5F6G7H",
        "nod_03M6TESTPC3A1B2C3D4E5F6G7H",
        "nod_04M6TESTPC4A1B2C3D4E5F6G7H",
        "nod_01M6TESTPC1A1B2C3D4E5F6G7H",  # duplicate of PC1
    ]
    result = validate_five_node_acceptance_config(nodes, "prj_test_01")
    assert result["valid"] is False
    assert result["status"] == "PREREQUISITES_MISSING"
    assert any("Duplicate node IDs" in err for err in result["errors"])


def test_validate_config_rejects_invalid_node_id_format():
    nodes = [
        "nod_01M6TESTPC1A1B2C3D4E5F6G7H",
        "nod_02M6TESTPC2A1B2C3D4E5F6G7H",
        "nod_03M6TESTPC3A1B2C3D4E5F6G7H",
        "nod_04M6TESTPC4A1B2C3D4E5F6G7H",
        "invalid_node_id_prefix",
    ]
    result = validate_five_node_acceptance_config(nodes, "prj_test_01")
    assert result["valid"] is False
    assert any("Invalid node ID format" in err for err in result["errors"])


def test_validate_config_rejects_empty_project_id():
    nodes = [f"nod_01M6TESTPC{i}A1B2C3D4E5F6G7H" for i in range(1, 6)]
    result = validate_five_node_acceptance_config(nodes, "")
    assert result["valid"] is False
    assert any("project_id must be a non-empty string" in err for err in result["errors"])


def test_sanitize_evidence_redacts_credentials():
    dirty = {
        "nodeId": "nod_01M6TESTPC1A1B2C3D4E5F6G7H",
        "authToken": "secret_token_12345",
        "bearer_token": "bearer eyJhbGciOi...",
        "user_password": "supersecretpassword",
        "sessionCookie": "session_id=abcd1234efgh",
        "nested": {
            "credentialKey": "private_key_data",
            "safeField": "public_data",
        },
        "rawHeader": "Authorization: Bearer supersecretvalue",
    }
    cleaned = sanitize_evidence_data(dirty)
    assert cleaned["authToken"] == "[REDACTED_CREDENTIAL]"
    assert cleaned["bearer_token"] == "[REDACTED_CREDENTIAL]"
    assert cleaned["user_password"] == "[REDACTED_CREDENTIAL]"
    assert cleaned["sessionCookie"] == "[REDACTED_CREDENTIAL]"
    assert cleaned["nested"]["credentialKey"] == "[REDACTED_CREDENTIAL]"
    assert cleaned["nested"]["safeField"] == "public_data"
    assert "supersecret" not in json.dumps(cleaned)


def test_heartbeat_freshness_evaluation():
    now = time.time()
    # 10 seconds ago -> fresh
    iso_recent = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - 10))
    res = evaluate_heartbeat_freshness(iso_recent, now, max_age_seconds=60.0)
    assert res["fresh"] is True

    # 120 seconds ago -> stale
    iso_stale = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - 120))
    res_stale = evaluate_heartbeat_freshness(iso_stale, now, max_age_seconds=60.0)
    assert res_stale["fresh"] is False
    assert "Heartbeat stale" in res_stale["reason"]

    # Absent -> not fresh
    res_absent = evaluate_heartbeat_freshness("미관측 (Heartbeat Absent)", now)
    assert res_absent["fresh"] is False


def test_load_nodes_from_inventory(tmp_path: Path):
    inv_file = tmp_path / "test-inventory.json"
    inv_data = {
        "projectId": "prj_inv_01",
        "nodes": [
            {"nodeId": f"nod_01M6TESTPC{i}A1B2C3D4E5F6G7H", "ip": f"192.168.1.{i}"}
            for i in range(1, 6)
        ],
    }
    inv_file.write_text(json.dumps(inv_data), encoding="utf-8")

    nodes, project = load_nodes_from_inventory(inv_file)
    assert len(nodes) == 5
    assert project == "prj_inv_01"


def test_fixture_mode_never_claims_live_pass():
    runner = FiveNodeAcceptanceRunner(
        expected_nodes=FIXTURE_FIVE_NODE_IDS,
        project_id=FIXTURE_PROJECT_ID,
        portal_url="http://127.0.0.1:9999",
        is_fixture=True,
    )
    report = runner._build_report(
        status="PASS",
        diagnostic="Fixture simulation passed",
        details={"observedCount": 5},
    )
    assert report["fixtureOnly"] is True
    assert report["realUserOrHardwareAcceptance"] is False
    assert "remainingLiveInputs" in report
    assert report["remainingLiveInputs"]["physicalNodes"] != ""
    assert report["remainingLiveInputs"]["controlPlaneState"] != ""


def _setup_mock_playwright(page_mock):
    browser_mock = MagicMock()
    browser_mock.new_page.return_value = page_mock
    chromium_mock = MagicMock()
    chromium_mock.launch.return_value = browser_mock
    pw_mock = MagicMock()
    pw_mock.chromium = chromium_mock
    cm = MagicMock()
    cm.__enter__.return_value = pw_mock
    cm.__exit__.return_value = None
    return cm


def test_runner_detects_unreachable_portal():
    page_mock = MagicMock()
    page_mock.goto.side_effect = Exception("Connection refused (ECONNREFUSED)")

    with patch("playwright.sync_api.sync_playwright", return_value=_setup_mock_playwright(page_mock)):
        runner = FiveNodeAcceptanceRunner(
            expected_nodes=FIXTURE_FIVE_NODE_IDS,
            project_id=FIXTURE_PROJECT_ID,
            portal_url="http://127.0.0.1:59999",
            is_fixture=False,
        )
        report = runner.run()

    assert report["status"] == "PREREQUISITES_MISSING"
    assert "unreachable" in report["diagnostic"]
    assert report["realUserOrHardwareAcceptance"] is False


def test_runner_distinguishes_authentication_required():
    page_mock = MagicMock()
    page_mock.url = "http://127.0.0.1:8080/login"
    login_locator = MagicMock()
    login_locator.count.return_value = 1
    page_mock.locator.return_value = login_locator

    with patch("playwright.sync_api.sync_playwright", return_value=_setup_mock_playwright(page_mock)):
        runner = FiveNodeAcceptanceRunner(
            expected_nodes=FIXTURE_FIVE_NODE_IDS,
            project_id=FIXTURE_PROJECT_ID,
            portal_url="http://127.0.0.1:8080",
            is_fixture=False,
            skip_socket_probe=True,
        )
        report = runner.run()

    assert report["status"] == "AUTHENTICATION_REQUIRED"
    assert "authentication required" in report["diagnostic"]
    assert report["realUserOrHardwareAcceptance"] is False


def test_runner_distinguishes_incomplete_fleet():
    page_mock = MagicMock()
    page_mock.url = "http://127.0.0.1:8080/dashboard"

    # Mock locator: return count=1 only for PC1, PC2, PC3; count=0 for PC4, PC5
    observed = set(FIXTURE_FIVE_NODE_IDS[:3])
    def locator_mock(selector):
        loc = MagicMock()
        for nid in observed:
            if f"node-item-{nid}" in selector:
                loc.count.return_value = 1
                return loc
            if f"node-status-badge-{nid}" in selector:
                loc.count.return_value = 1
                loc.inner_text.return_value = "● ONLINE"
                return loc
            if f"node-cpu-{nid}" in selector:
                loc.count.return_value = 1
                loc.inner_text.return_value = "제공 500m"
                return loc
            if f"node-memory-{nid}" in selector:
                loc.count.return_value = 1
                loc.inner_text.return_value = "제공 64 MiB"
                return loc
            if f"node-heartbeat-{nid}" in selector:
                loc.count.return_value = 1
                loc.inner_text.return_value = "오후 9:00:00"
                return loc
        loc.count.return_value = 0
        return loc

    page_mock.locator.side_effect = locator_mock

    with patch("playwright.sync_api.sync_playwright", return_value=_setup_mock_playwright(page_mock)):
        runner = FiveNodeAcceptanceRunner(
            expected_nodes=FIXTURE_FIVE_NODE_IDS,
            project_id=FIXTURE_PROJECT_ID,
            portal_url="http://127.0.0.1:8080",
            is_fixture=False,
            skip_socket_probe=True,
        )
        report = runner.run()

    assert report["status"] == "INCOMPLETE_FLEET"
    assert report["details"]["observedCount"] == 3
    assert report["details"]["expectedCount"] == 5
    assert len(report["details"]["missingNodes"]) == 2
    assert report["realUserOrHardwareAcceptance"] is False


def test_runner_verifies_all_five_nodes_and_stable_dom():
    page_mock = MagicMock()
    page_mock.url = "http://127.0.0.1:8080/dashboard"

    def locator_mock(selector):
        loc = MagicMock()
        if any(login_kw in selector for login_kw in ('login-form', 'password')):
            loc.count.return_value = 0
            return loc
        if any(f"node-item-{nid}" in selector for nid in FIXTURE_FIVE_NODE_IDS):
            loc.count.return_value = 1
            return loc
        if any(f"node-status-badge-{nid}" in selector for nid in FIXTURE_FIVE_NODE_IDS):
            loc.count.return_value = 1
            loc.inner_text.return_value = "● ONLINE"
            return loc
        if any(f"node-cpu-{nid}" in selector for nid in FIXTURE_FIVE_NODE_IDS):
            loc.count.return_value = 1
            loc.inner_text.return_value = "제공 500m"
            return loc
        if any(f"node-memory-{nid}" in selector for nid in FIXTURE_FIVE_NODE_IDS):
            loc.count.return_value = 1
            loc.inner_text.return_value = "제공 64 MiB"
            return loc
        if any(f"node-heartbeat-{nid}" in selector for nid in FIXTURE_FIVE_NODE_IDS):
            loc.count.return_value = 1
            loc.inner_text.return_value = "오후 9:00:00"
            return loc
        if 'node-item-' in selector:
            loc.count.return_value = 5
            return loc
        loc.count.return_value = 0
        loc.inner_text.return_value = "Gateway: 12ms"
        return loc

    page_mock.locator.side_effect = locator_mock
    page_mock.evaluate.return_value = {"initialCards": 5, "removedNodes": 0, "removedDetails": []}

    with patch("playwright.sync_api.sync_playwright", return_value=_setup_mock_playwright(page_mock)):
        runner = FiveNodeAcceptanceRunner(
            expected_nodes=FIXTURE_FIVE_NODE_IDS,
            project_id=FIXTURE_PROJECT_ID,
            portal_url="http://127.0.0.1:8080",
            poll_duration_seconds=0.1,
            is_fixture=False,
            skip_socket_probe=True,
        )
        report = runner.run()

    assert report["status"] == "PASS"
    assert report["details"]["observedCount"] == 5
    assert report["details"]["stableDOM"] is True
    assert report["realUserOrHardwareAcceptance"] is True


def test_runner_captures_card_loss_during_polling():
    page_mock = MagicMock()
    page_mock.url = "http://127.0.0.1:8080/dashboard"

    def locator_mock(selector):
        loc = MagicMock()
        if any(login_kw in selector for login_kw in ('login-form', 'password')):
            loc.count.return_value = 0
            return loc
        if any(f"node-item-{nid}" in selector for nid in FIXTURE_FIVE_NODE_IDS):
            loc.count.return_value = 1
            return loc
        if 'node-item-' in selector:
            loc.count.return_value = 4  # one card lost
            return loc
        loc.count.return_value = 0
        loc.inner_text.return_value = "ONLINE"
        return loc

    page_mock.locator.side_effect = locator_mock
    # Simulate MutationObserver recording that a card was removed
    page_mock.evaluate.return_value = {
        "initialCards": 5,
        "removedNodes": 1,
        "removedDetails": ["node-item-nod_01M6PHYPC1A1B2C3D4E5F6G7H"],
    }

    with patch("playwright.sync_api.sync_playwright", return_value=_setup_mock_playwright(page_mock)):
        runner = FiveNodeAcceptanceRunner(
            expected_nodes=FIXTURE_FIVE_NODE_IDS,
            project_id=FIXTURE_PROJECT_ID,
            portal_url="http://127.0.0.1:8080",
            poll_duration_seconds=0.1,
            is_fixture=False,
            skip_socket_probe=True,
        )
        report = runner.run()

    assert report["status"] == "FAIL"
    assert "Card loss detected" in report["diagnostic"]
    assert report["details"]["stableDOM"] is False
    assert report["realUserOrHardwareAcceptance"] is False


def test_runner_rejects_duplicate_node_ids_before_browser_execution():
    duplicate_nodes = [
        FIXTURE_FIVE_NODE_IDS[0],
        FIXTURE_FIVE_NODE_IDS[1],
        FIXTURE_FIVE_NODE_IDS[2],
        FIXTURE_FIVE_NODE_IDS[3],
        FIXTURE_FIVE_NODE_IDS[0],  # duplicate PC1
    ]
    runner = FiveNodeAcceptanceRunner(
        expected_nodes=duplicate_nodes,
        project_id=FIXTURE_PROJECT_ID,
        portal_url="http://127.0.0.1:8080",
        skip_socket_probe=True,
    )
    report = runner.run()

    assert report["status"] == "PREREQUISITES_MISSING"
    assert "Duplicate node IDs" in report["diagnostic"]
    assert report["realUserOrHardwareAcceptance"] is False


def test_runner_distinguishes_typed_missing_pc1_and_pc5_enrollment_outcome():
    page_mock = MagicMock()
    page_mock.url = "http://127.0.0.1:8080/dashboard"

    # PC1 and PC5 are missing; only PC2, PC3, PC4 observed
    observed = set(FIXTURE_FIVE_NODE_IDS[1:4])
    def locator_mock(selector):
        loc = MagicMock()
        for nid in observed:
            if f"node-item-{nid}" in selector:
                loc.count.return_value = 1
                return loc
            if f"node-status-badge-{nid}" in selector:
                loc.count.return_value = 1
                loc.inner_text.return_value = "● ONLINE"
                return loc
            if f"node-cpu-{nid}" in selector:
                loc.count.return_value = 1
                loc.inner_text.return_value = "제공 500m"
                return loc
            if f"node-memory-{nid}" in selector:
                loc.count.return_value = 1
                loc.inner_text.return_value = "제공 64 MiB"
                return loc
            if f"node-heartbeat-{nid}" in selector:
                loc.count.return_value = 1
                loc.inner_text.return_value = "오후 9:00:00"
                return loc
        loc.count.return_value = 0
        return loc

    page_mock.locator.side_effect = locator_mock

    with patch("playwright.sync_api.sync_playwright", return_value=_setup_mock_playwright(page_mock)):
        runner = FiveNodeAcceptanceRunner(
            expected_nodes=FIXTURE_FIVE_NODE_IDS,
            project_id=FIXTURE_PROJECT_ID,
            portal_url="http://127.0.0.1:8080",
            skip_socket_probe=True,
        )
        report = runner.run()

    assert report["status"] == "INCOMPLETE_FLEET"
    assert report["details"]["observedCount"] == 3
    assert report["details"]["expectedCount"] == 5
    expected_missing = sorted([FIXTURE_FIVE_NODE_IDS[0], FIXTURE_FIVE_NODE_IDS[4]])
    assert report["details"]["missingNodes"] == expected_missing
    assert FIXTURE_FIVE_NODE_IDS[0] in report["details"]["missingNodes"]
    assert FIXTURE_FIVE_NODE_IDS[4] in report["details"]["missingNodes"]
    assert report["realUserOrHardwareAcceptance"] is False


def test_runner_fails_when_heartbeat_is_stale_preventing_acceptance():
    page_mock = MagicMock()
    page_mock.url = "http://127.0.0.1:8080/dashboard"

    # All 5 nodes present, but PC5 has stale heartbeat (10 minutes old ISO)
    def locator_mock(selector):
        loc = MagicMock()
        if any(login_kw in selector for login_kw in ('login-form', 'password')):
            loc.count.return_value = 0
            return loc
        if any(f"node-item-{nid}" in selector for nid in FIXTURE_FIVE_NODE_IDS):
            loc.count.return_value = 1
            return loc
        if any(f"node-status-badge-{nid}" in selector for nid in FIXTURE_FIVE_NODE_IDS):
            loc.count.return_value = 1
            loc.inner_text.return_value = "● ONLINE"
            return loc
        if any(f"node-cpu-{nid}" in selector for nid in FIXTURE_FIVE_NODE_IDS):
            loc.count.return_value = 1
            loc.inner_text.return_value = "제공 500m"
            return loc
        if any(f"node-memory-{nid}" in selector for nid in FIXTURE_FIVE_NODE_IDS):
            loc.count.return_value = 1
            loc.inner_text.return_value = "제공 64 MiB"
            return loc
        # For PC5, return an old timestamp (>600s ago)
        if f"node-heartbeat-{FIXTURE_FIVE_NODE_IDS[4]}" in selector:
            loc.count.return_value = 1
            loc.inner_text.return_value = "2020-01-01T00:00:00Z"
            return loc
        if any(f"node-heartbeat-{nid}" in selector for nid in FIXTURE_FIVE_NODE_IDS):
            loc.count.return_value = 1
            loc.inner_text.return_value = "오후 9:00:00"
            return loc
        if 'node-item-' in selector:
            loc.count.return_value = 5
            return loc
        loc.count.return_value = 0
        loc.inner_text.return_value = "Gateway: 12ms"
        return loc

    page_mock.locator.side_effect = locator_mock
    page_mock.evaluate.return_value = {"initialCards": 5, "removedNodes": 0, "removedDetails": []}

    with patch("playwright.sync_api.sync_playwright", return_value=_setup_mock_playwright(page_mock)):
        runner = FiveNodeAcceptanceRunner(
            expected_nodes=FIXTURE_FIVE_NODE_IDS,
            project_id=FIXTURE_PROJECT_ID,
            portal_url="http://127.0.0.1:8080",
            poll_duration_seconds=0.1,
            skip_socket_probe=True,
        )
        report = runner.run()

    assert report["status"] == "FAIL"
    assert "Stale or unobserved heartbeat detected" in report["diagnostic"]
    assert FIXTURE_FIVE_NODE_IDS[4] in report["details"]["staleNodes"]
    assert report["realUserOrHardwareAcceptance"] is False
