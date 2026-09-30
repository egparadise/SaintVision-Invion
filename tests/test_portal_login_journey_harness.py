"""Tests for S02-FE Intranet Portal Login Journey Observation Harness (Card 162).

Verifies:
  1. Honest reporting of BLOCKED_EXTERNAL when DNS resolution fails (e.g. portal.sv.lan not in hosts).
  2. Honest reporting of BLOCKED_EXTERNAL when TCP port is closed/unreachable.
  3. Strict fail-closed rejection of circumvention flags (--host-resolver-rules, --ignore-certificate-errors, etc.).
  4. Redaction engine guarantee: 0 tokens, 0 IPs, 0 credentials.
  5. Schema validation and fail-closed rejection if any token/IP count > 0.
  6. Complete 5-phase journey execution in mock/unit mode producing 100% valid Evidence.
  7. CLI execution and evidence file persistence.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / 'tools'))

from tools.observe_portal_login_journey import (
    PortalLoginJourneyObserver,
    RedactionSanitizer,
    SecurityCircumventionError,
    SCHEMA_PATH,
    check_circumvention_flags,
    validate_evidence,
)


def test_schema_file_exists_and_is_valid_draft():
    assert SCHEMA_PATH.exists(), f"Schema file must exist at {SCHEMA_PATH}"
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema = json.load(f)
    assert schema.get("title") == "PortalLoginJourneyEvidence"
    assert schema.get("type") == "object"
    assert schema.get("additionalProperties") is False


def test_unresolved_domain_honestly_reports_blocked_external():
    # Use a non-existent intranet hostname that will fail DNS resolution
    unresolved_url = "https://unresolved-portal-node99.sv.lan"
    observer = PortalLoginJourneyObserver(target_url=unresolved_url, mock_mode=False)

    evidence = observer.execute_journey()

    assert evidence["overallStatus"] == "BLOCKED_EXTERNAL"
    assert evidence["blockingReason"] is not None
    assert "DNS resolution failed" in evidence["blockingReason"]

    # All 5 steps must be present and marked BLOCKED_EXTERNAL
    assert len(evidence["steps"]) == 5
    step_ids = [s["id"] for s in evidence["steps"]]
    assert step_ids == [
        "portal_tls_reachability",
        "login_initiation",
        "pkce_callback",
        "identity_session_display",
        "logout",
    ]
    for step in evidence["steps"]:
        assert step["status"] == "BLOCKED_EXTERNAL"
        assert "Blocked" in step["detail"] or "blocked" in step["detail"]

    # Audit section guarantees
    assert evidence["audit"]["redacted"] is True
    assert evidence["audit"]["tokenCount"] == 0
    assert evidence["audit"]["ipCount"] == 0
    assert evidence["audit"]["credentialCount"] == 0
    assert evidence["audit"]["circumventionFlagsDetected"] is False
    assert evidence["audit"]["tlsValidationEnforced"] is True

    # Strict schema validation
    validate_evidence(evidence)


def test_closed_tcp_port_honestly_reports_blocked_external():
    # Use loopback with an unused port that refuses connection
    closed_port_url = "http://127.0.0.1:59998"
    observer = PortalLoginJourneyObserver(target_url=closed_port_url, mock_mode=False)

    evidence = observer.execute_journey()

    assert evidence["overallStatus"] == "BLOCKED_EXTERNAL"
    assert evidence["blockingReason"] is not None
    assert "refused" in evidence["blockingReason"].lower() or "connection" in evidence["blockingReason"].lower()
    for step in evidence["steps"]:
        assert step["status"] == "BLOCKED_EXTERNAL"

    # Redacted audit check
    assert evidence["audit"]["tokenCount"] == 0
    assert evidence["audit"]["ipCount"] == 0
    validate_evidence(evidence)


@pytest.mark.parametrize(
    "flag",
    [
        "--host-resolver-rules=MAP portal.sv.lan 127.0.0.1",
        "--ignore-certificate-errors",
        "--disable-web-security",
        "--allow-running-insecure-content",
        "ignoreHTTPSErrors=true",
        "--flag-with-ignore_https_errors",
    ],
)
def test_circumvention_flags_fail_closed_in_observer(flag: str):
    with pytest.raises(SecurityCircumventionError) as exc_info:
        PortalLoginJourneyObserver(target_url="https://portal.sv.lan", extra_args=[flag])
    assert "Circumvention prohibited" in str(exc_info.value)


@pytest.mark.parametrize(
    "flag",
    [
        "--host-resolver-rules=MAP portal.sv.lan 127.0.0.1",
        "--ignore-certificate-errors",
    ],
)
def test_cli_rejects_circumvention_flags_with_exit_code_2(flag: str):
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools/observe_portal_login_journey.py"), flag],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 2
    assert "[SECURITY ERROR]" in proc.stderr
    assert "Circumvention prohibited" in proc.stderr


def test_redaction_sanitizer_eradicates_all_tokens_ips_and_secrets():
    raw_payload = {
        "authHeader": "Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
        "jwtStandalone": "eyJhbGciOiJSUzI1NiJ9.eyJleHAiOjE3MDAwMDAwMDB9.signature-part-here-1234567890",
        "url": "https://portal.sv.lan/callback?code=super-secret-auth-code-12345&state=high-entropy-state&code_verifier=abcdefghijklmnopqrstuvwxyz01234567890123456789",
        "network": {
            "serverIp": "192.168.1.105",
            "gatewayIp": "10.0.0.1",
            "altIp": "172.16.50.2",
        },
        "credentials": {
            "client_secret": "my-client-secret-9999",
            "password": "super-user-password",
        },
    }

    sanitized = RedactionSanitizer.sanitize_obj(raw_payload)
    serialized = json.dumps(sanitized)

    # Assert no sensitive values remain in serialized text
    assert "Bearer eyJ" not in serialized
    assert "192.168.1.105" not in serialized
    assert "10.0.0.1" not in serialized
    assert "172.16.50.2" not in serialized
    assert "super-secret-auth-code-12345" not in serialized
    assert "super-user-password" not in serialized
    assert "my-client-secret-9999" not in serialized

    # Audit check returns strictly (0, 0, 0)
    token_cnt, ip_cnt, cred_cnt = RedactionSanitizer.audit_obj(sanitized)
    assert token_cnt == 0
    assert ip_cnt == 0
    assert cred_cnt == 0


def test_audit_detects_unredacted_leaks():
    leaked_token_obj = {"token": "Bearer eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ1c3IifQ.sigpart1234567890"}
    t_cnt, _, _ = RedactionSanitizer.audit_obj(leaked_token_obj)
    assert t_cnt > 0

    leaked_ip_obj = {"node": "192.168.0.50"}
    _, ip_cnt, _ = RedactionSanitizer.audit_obj(leaked_ip_obj)
    assert ip_cnt > 0


def test_mock_journey_produces_fully_passing_valid_evidence():
    observer = PortalLoginJourneyObserver(
        target_url="https://portal.sv.lan",
        idp_url="https://idp.sv.lan",
        mock_mode=True,
    )

    evidence = observer.execute_journey()

    assert evidence["overallStatus"] == "PASS"
    assert evidence["blockingReason"] is None
    assert len(evidence["steps"]) == 5

    expected_steps = [
        "portal_tls_reachability",
        "login_initiation",
        "pkce_callback",
        "identity_session_display",
        "logout",
    ]
    for i, step_id in enumerate(expected_steps):
        step = evidence["steps"][i]
        assert step["id"] == step_id
        assert step["status"] == "PASS"
        assert step["durationMs"] > 0
        assert len(step["detail"]) > 10
        assert isinstance(step["observations"], dict)

    assert evidence["audit"]["redacted"] is True
    assert evidence["audit"]["tokenCount"] == 0
    assert evidence["audit"]["ipCount"] == 0
    assert evidence["audit"]["credentialCount"] == 0
    assert evidence["audit"]["circumventionFlagsDetected"] is False
    assert evidence["audit"]["tlsValidationEnforced"] is True

    # Validate against strict schema
    validate_evidence(evidence)


def test_schema_enforces_zero_token_and_ip_counts():
    observer = PortalLoginJourneyObserver(mock_mode=True)
    valid_evidence = observer.execute_journey()

    # 1. Non-zero tokenCount should fail
    bad_tokens = json.loads(json.dumps(valid_evidence))
    bad_tokens["audit"]["tokenCount"] = 1
    with pytest.raises(jsonschema.ValidationError):
        validate_evidence(bad_tokens)

    # 2. Non-zero ipCount should fail
    bad_ips = json.loads(json.dumps(valid_evidence))
    bad_ips["audit"]["ipCount"] = 1
    with pytest.raises(jsonschema.ValidationError):
        validate_evidence(bad_ips)

    # 3. True circumventionFlagsDetected should fail
    bad_circumvention = json.loads(json.dumps(valid_evidence))
    bad_circumvention["audit"]["circumventionFlagsDetected"] = True
    with pytest.raises(jsonschema.ValidationError):
        validate_evidence(bad_circumvention)

    # 4. Unknown property in root should fail (additionalProperties: false)
    bad_property = json.loads(json.dumps(valid_evidence))
    bad_property["unknown_field"] = "malicious"
    with pytest.raises(jsonschema.ValidationError):
        validate_evidence(bad_property)


def test_cli_execution_with_output_file(tmp_path: Path):
    evidence_file = tmp_path / "portal-login-journey-evidence.json"
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "tools/observe_portal_login_journey.py"),
            "--mock-mode",
            "--output-evidence",
            str(evidence_file),
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "[EVIDENCE SAVED]" in proc.stdout
    assert evidence_file.exists()

    with open(evidence_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["overallStatus"] == "PASS"
    validate_evidence(data)
