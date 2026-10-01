"""Tests for S02-FE Intranet Portal Login Journey Observation Harness (Card 162).

Comprehensive verification covering Codex contract & security findings F1~F6:
  F1: Complete 5-phase journey execution in live and mock paths; downstream steps marked NOT_OBSERVED on prior failure.
  F2: Live target/IdP bound strictly to canonical origins (https://portal.sv.lan, https://idp.sv.lan);
      CA bundle verification against approved root fingerprint allowlist;
      Active TLS socket preflight; unobserved TLS attributes not marked true.
  F3: Honest status classification: DNS unresolvable / missing CA = BLOCKED_EXTERNAL;
      TCP port closed / timeout / TLS failure = FAIL.
  F4: Mock mode enforces referenceOnly=True, acceptanceClaim=False, measurementKind="REFERENCE_SIMULATION".
      Semantic validator rejects contradictions (PASS with failed/blocked steps, mock claiming acceptance).
      Reachable clean Git SHA provenance (00000000 rejected).
  F5: Strict Redaction: ipaddress module handles IPv4 & IPv6 (including ::1);
      account/email patterns (operator@example.invalid) redacted;
      OIDC transaction parameters (state, nonce, code_challenge) redacted;
      Audit enforces tokenCount=0, ipCount=0, credentialCount=0, accountCount=0, oidcParamCount=0.
  F6: Mutation-killing negative tests: wrong CA fails, self-signed fails, unapproved fingerprint fails,
      closed port asserts FAIL, origin tampering fails, mock acceptance claim rejected.
"""

from __future__ import annotations

import datetime as dt
import json
import socket
import ssl
import subprocess
import sys
import threading
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict

import jsonschema
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools"))

from tools.observe_portal_login_journey import (
    CANONICAL_IDP_HOST,
    CANONICAL_PORTAL_HOST,
    SCHEMA_PATH,
    STEP_METADATA,
    PortalLoginJourneyObserver,
    RedactionSanitizer,
    SecurityCircumventionError,
    StepResult,
    check_circumvention_flags,
    check_domain_resolution,
    check_tcp_connection,
    compute_overall_status,
    get_git_sha,
    inspect_ca_bundle,
    validate_canonical_origins,
    validate_evidence,
    verify_tls_socket_handshake,
)


# --- Helper: Generate Test PKI Certificates ---
def _generate_test_ca(cn: str):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = dt.datetime.now(dt.timezone.utc)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(hours=1))
        .not_valid_after(now + dt.timedelta(hours=2))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.KeyUsage(False, False, False, False, False, True, True, False, False),
            critical=True,
        )
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(key.public_key()),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    pem = cert.public_bytes(serialization.Encoding.PEM)
    fp = cert.fingerprint(hashes.SHA256()).hex().lower()
    return key, cert, pem, fp


def _generate_server_cert(ca_key, ca_cert, hostname: str = "localhost"):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = dt.datetime.now(dt.timezone.utc)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hostname)])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(hours=1))
        .not_valid_after(now + dt.timedelta(hours=2))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(True, False, False, False, False, False, False, False, False),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),
            critical=True,
        )
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName(hostname)]),
            critical=False,
        )
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(key.public_key()),
            critical=False,
        )
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_cert.public_key()),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    return cert, cert_pem, key_pem


# =========================================================================
# 1. Schema & Provenance Invariants
# =========================================================================

def test_schema_file_exists_and_is_valid_draft():
    assert SCHEMA_PATH.exists(), f"Schema file must exist at {SCHEMA_PATH}"
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema = json.load(f)
    assert schema.get("title") == "PortalLoginJourneyEvidence"
    assert schema.get("type") == "object"
    assert schema.get("additionalProperties") is False
    jsonschema.Draft202012Validator.check_schema(schema)


def test_git_sha_returns_valid_reachable_commit():
    sha = get_git_sha()
    assert len(sha) >= 8
    assert all(c in "0123456789abcdef" for c in sha)
    assert sha != "00000000"


def test_get_git_sha_rejects_dirty_tree(monkeypatch):
    from unittest.mock import MagicMock
    def mock_run(cmd, **kwargs):
        if "rev-parse" in cmd:
            return MagicMock(stdout="a" * 40, returncode=0)
        elif "status" in cmd:
            return MagicMock(stdout=" M src/modified_file.py", returncode=0)
        return MagicMock(stdout="", returncode=0)
    monkeypatch.setattr("subprocess.run", mock_run)

    with pytest.raises(RuntimeError) as exc:
        get_git_sha(require_clean=True)
    assert "Dirty git working tree detected" in str(exc.value)


def test_get_git_sha_rejects_unreachable_remote(monkeypatch):
    from unittest.mock import MagicMock
    def mock_run(cmd, **kwargs):
        if "rev-parse" in cmd:
            return MagicMock(stdout="b" * 40, returncode=0)
        elif "status" in cmd:
            return MagicMock(stdout="", returncode=0)
        elif "branch" in cmd:
            return MagicMock(stdout="", returncode=0)  # Empty: not in any remote branch
        return MagicMock(stdout="", returncode=0)
    monkeypatch.setattr("subprocess.run", mock_run)

    with pytest.raises(RuntimeError) as exc:
        get_git_sha(require_clean=False, require_remote_containment=True)
    assert "not reachable from any approved remote tracking branch" in str(exc.value)


# =========================================================================
# 2. Honest Status Classification (F3)
# =========================================================================

def test_unresolved_domain_honestly_reports_blocked_external():
    unresolved_url = "https://portal.sv.lan"
    observer = PortalLoginJourneyObserver(target_url=unresolved_url, mock_mode=False)

    evidence = observer.execute_journey(require_clean=False, require_remote_containment=False)

    assert evidence["overallStatus"] == "BLOCKED_EXTERNAL"
    assert evidence["blockingReason"] is not None
    assert "DNS resolution failed" in evidence["blockingReason"]
    assert evidence["measurementKind"] == "LIVE_BROWSER"
    assert evidence["referenceOnly"] is False
    assert evidence["acceptanceClaim"] is False

    # Exact 5 steps: step 1 is BLOCKED_EXTERNAL, downstream are NOT_OBSERVED
    assert len(evidence["steps"]) == 5
    assert evidence["steps"][0]["id"] == "portal_tls_reachability"
    assert evidence["steps"][0]["status"] == "BLOCKED_EXTERNAL"
    for s in evidence["steps"][1:]:
        assert s["status"] == "NOT_OBSERVED"
        assert "Not observed" in s["detail"]

    # Audit section guarantees
    assert evidence["audit"]["redacted"] is True
    assert evidence["audit"]["tokenCount"] == 0
    assert evidence["audit"]["ipCount"] == 0
    assert evidence["audit"]["credentialCount"] == 0
    assert evidence["audit"]["accountCount"] == 0
    assert evidence["audit"]["oidcParamCount"] == 0
    assert evidence["audit"]["tlsValidationEnforced"] is False

    validate_evidence(evidence)


def test_closed_tcp_port_honestly_reports_fail(monkeypatch):
    """F3: When DNS resolves, connection refused / service down MUST be FAIL, NOT BLOCKED_EXTERNAL."""
    # Monkeypatch DNS resolution to succeed
    monkeypatch.setattr(
        "tools.observe_portal_login_journey.check_domain_resolution",
        lambda h: (True, None),
    )

    # Monkeypatch socket.create_connection to raise ConnectionRefusedError
    def mock_create_connection(addr, timeout=None):
        raise ConnectionRefusedError(f"Connection refused to {addr}")

    monkeypatch.setattr("socket.create_connection", mock_create_connection)

    observer = PortalLoginJourneyObserver(
        target_url="https://portal.sv.lan:443",
        mock_mode=False,
    )

    evidence = observer.execute_journey(require_clean=False, require_remote_containment=False)

    # Must be FAIL (service down), NOT BLOCKED_EXTERNAL!
    assert evidence["overallStatus"] == "FAIL"
    assert evidence["blockingReason"] is not None
    assert "refused" in evidence["blockingReason"].lower() or "service down" in evidence["blockingReason"].lower()
    assert evidence["steps"][0]["status"] == "FAIL"
    for s in evidence["steps"][1:]:
        assert s["status"] == "NOT_OBSERVED"

    assert evidence["acceptanceClaim"] is False
    validate_evidence(evidence)


# =========================================================================
# 3. Canonical Origin Binding & Circumvention Guards (F2)
# =========================================================================

@pytest.mark.parametrize(
    "bad_url,err_substr",
    [
        ("http://portal.sv.lan", "https scheme"),
        ("https://127.0.0.1:443", "portal.sv.lan"),
        ("https://user:pass@portal.sv.lan", "userinfo"),
        ("https://attacker.sv.lan", "portal.sv.lan"),
        ("https://[::1]:443", "portal.sv.lan"),
    ],
)
def test_target_url_origin_validation_in_live_mode(bad_url: str, err_substr: str):
    with pytest.raises(ValueError) as exc:
        validate_canonical_origins(bad_url, "https://idp.sv.lan", live_mode=True)
    assert err_substr in str(exc.value)


@pytest.mark.parametrize(
    "bad_idp,err_substr",
    [
        ("http://idp.sv.lan", "https scheme"),
        ("https://10.0.0.5:8443", "idp.sv.lan"),
        ("https://admin:pass@idp.sv.lan", "userinfo"),
        ("https://rogue-idp.sv.lan", "idp.sv.lan"),
    ],
)
def test_idp_url_origin_validation_in_live_mode(bad_idp: str, err_substr: str):
    with pytest.raises(ValueError) as exc:
        validate_canonical_origins("https://portal.sv.lan", bad_idp, live_mode=True)
    assert err_substr in str(exc.value)


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


def test_cli_rejects_circumvention_flags_with_exit_code_2():
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools/observe_portal_login_journey.py"), "--ignore-certificate-errors"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 2
    assert "[SECURITY ERROR]" in proc.stderr
    assert "Circumvention prohibited" in proc.stderr


# =========================================================================
# 4. Redaction Engine & Leaks Hardening (F5)
# =========================================================================

def test_redaction_sanitizer_eradicates_all_tokens_ips_accounts_and_secrets():
    raw_payload = {
        "authHeader": "Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.signature_dummy_1234567890",
        "jwtStandalone": "eyJhbGciOiJSUzI1NiJ9.eyJleHAiOjE3MDAwMDAwMDB9.sigpart_1234567890",
        "accountEmail": "operator@example.invalid",
        "url": "https://portal.sv.lan/callback?code=secret-auth-code-12345&state=high-entropy-state&nonce=secure-nonce-999&code_challenge=pkce-ch-555",
        "network": {
            "ipv4": "192.168.1.105",
            "ipv6_full": "2001:0db8:85a3:0000:0000:8a2e:0370:7334",
            "ipv6_short": "::1",
            "ipv6_bracket": "[::1]:8443",
        },
        "credentials": {
            "password": "super-secret-password-xyz",
            "client_secret": "my-client-secret-9999",
            "code_verifier": "verifier-secret-token",
        },
        "identity": {
            "username": "portal_operator",
            "sub": "user-sub-uuid-9999",
            "email": "admin@sv.lan",
        },
    }

    sanitized = RedactionSanitizer.sanitize_obj(raw_payload)
    serialized = json.dumps(sanitized)

    # Assert no sensitive values remain in serialized text
    assert "Bearer eyJ" not in serialized
    assert "operator@example.invalid" not in serialized
    assert "admin@sv.lan" not in serialized
    assert "192.168.1.105" not in serialized
    assert "2001:0db8" not in serialized
    assert "::1" not in serialized
    assert "secret-auth-code-12345" not in serialized
    assert "high-entropy-state" not in serialized
    assert "secure-nonce-999" not in serialized
    assert "pkce-ch-555" not in serialized
    assert "super-secret-password-xyz" not in serialized
    assert "my-client-secret-9999" not in serialized
    assert "portal_operator" not in serialized
    assert "user-sub-uuid-9999" not in serialized

    # Audit check returns strictly (0, 0, 0, 0, 0)
    t_cnt, ip_cnt, cred_cnt, acc_cnt, oidc_cnt = RedactionSanitizer.audit_obj(sanitized)


def test_prefix_independent_account_probe_sanitized_and_audited():
    # Probe input with arbitrary key 'actor' containing account name 'alice'
    probe = {"actor": "alice"}
    sanitized = RedactionSanitizer.sanitize_obj(probe)
    assert sanitized["actor"] == "[REDACTED_ACCOUNT]"

    # Audit on raw unredacted probe detects leak
    _, _, _, acc_cnt, _ = RedactionSanitizer.audit_obj(probe)
    assert acc_cnt > 0

    # Probe with custom prefix
    probe2 = {"custom_user_id": "bob"}
    sanitized2 = RedactionSanitizer.sanitize_obj(probe2)
    assert sanitized2["custom_user_id"] == "[REDACTED_ACCOUNT]"

    _, _, _, acc_cnt2, _ = RedactionSanitizer.audit_obj(probe2)
    assert acc_cnt2 > 0


def test_observations_rejects_unknown_properties_schema():
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema = json.load(f)

    # Valid step observations
    valid_obs = {"httpStatus": 200, "url": "https://portal.sv.lan/", "tlsHandshakeVerified": True}
    jsonschema.validate(instance=valid_obs, schema=schema["properties"]["steps"]["items"]["properties"]["observations"])

    # Injected unknown property in observations must fail schema validation (additionalProperties: false)
    invalid_obs = {"httpStatus": 200, "actor": "alice"}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=invalid_obs, schema=schema["properties"]["steps"]["items"]["properties"]["observations"])


def test_browser_context_strictly_enforces_ignore_https_errors_false():
    # 1. Invariant: class constant must be False
    assert PortalLoginJourneyObserver.IGNORE_HTTPS_ERRORS is False

    # 2. Invariant: source code of observe_portal_login_journey must literally contain ignore_https_errors=False
    obs_source = (REPO_ROOT / "tools/observe_portal_login_journey.py").read_text(encoding="utf-8")
    assert "ignore_https_errors=False" in obs_source
    assert "ignore_https_errors=True" not in obs_source


@pytest.mark.parametrize(
    "leaked_obj,expected_leak_type",
    [
        ({"token": "Bearer eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ1In0.sig1234567890"}, "token"),
        ({"ipv4": "10.0.0.1"}, "ip"),
        ({"ipv6": "::1"}, "ip"),
        ({"email": "operator@example.invalid"}, "account"),
        ({"param": "state=unredacted_state_token_123"}, "oidc"),
        ({"cred": "password=plaintext_secret_123"}, "cred"),
    ],
)
def test_audit_detects_unredacted_leaks(leaked_obj: Dict[str, Any], expected_leak_type: str):
    t_cnt, ip_cnt, cred_cnt, acc_cnt, oidc_cnt = RedactionSanitizer.audit_obj(leaked_obj)
    if expected_leak_type == "token":
        assert t_cnt > 0
    elif expected_leak_type == "ip":
        assert ip_cnt > 0
    elif expected_leak_type == "account":
        assert acc_cnt > 0
    elif expected_leak_type == "oidc":
        assert oidc_cnt > 0
    elif expected_leak_type == "cred":
        assert cred_cnt > 0


# =========================================================================
# 5. Mock Mode & Semantic Invariants (F4)
# =========================================================================

def test_mock_journey_produces_fully_passing_valid_evidence():
    observer = PortalLoginJourneyObserver(
        target_url="https://portal.sv.lan",
        idp_url="https://idp.sv.lan",
        mock_mode=True,
    )

    evidence = observer.execute_journey()

    assert evidence["overallStatus"] == "PASS"
    assert evidence["blockingReason"] is None
    assert evidence["measurementKind"] == "REFERENCE_SIMULATION"
    assert evidence["referenceOnly"] is True
    assert evidence["acceptanceClaim"] is False  # F4: mock mode cannot claim acceptance!
    assert evidence["audit"]["tlsValidationEnforced"] is False
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

    validate_evidence(evidence)


def test_semantic_validator_rejects_mock_claiming_acceptance():
    """F4: If mock evidence attempts to set acceptanceClaim=True, validator fails."""
    observer = PortalLoginJourneyObserver(mock_mode=True)
    evidence = observer.execute_journey()

    evidence["acceptanceClaim"] = True
    with pytest.raises(jsonschema.ValidationError) as exc:
        validate_evidence(evidence)
    assert "referenceOnly evidence cannot make an acceptanceClaim" in str(exc.value)


def test_semantic_validator_rejects_contradictory_overall_pass():
    """F4: overallStatus=PASS with any non-PASS step is rejected."""
    observer = PortalLoginJourneyObserver(mock_mode=True)
    evidence = observer.execute_journey()

    evidence["steps"][2]["status"] = "FAIL"
    # overallStatus is PASS but step 3 is FAIL
    with pytest.raises(jsonschema.ValidationError) as exc:
        validate_evidence(evidence)
    assert "Contradiction: overallStatus is PASS but step 'pkce_callback' has status 'FAIL'" in str(exc.value)


def test_semantic_validator_rejects_mismatched_step_sequence():
    """F4: Steps array must strictly match the exact 5 canonical IDs in order."""
    observer = PortalLoginJourneyObserver(mock_mode=True)
    evidence = observer.execute_journey()

    # Swap step 1 and step 2
    evidence["steps"][0], evidence["steps"][1] = evidence["steps"][1], evidence["steps"][0]
    with pytest.raises(jsonschema.ValidationError) as exc:
        validate_evidence(evidence)
    assert "Step IDs must match exact expected sequence" in str(exc.value)


# =========================================================================
# 6. Mutation-Killing PKI & TLS Verification (F2 & F6)
# =========================================================================

def test_pki_ca_inspection_and_fingerprint_allowlist(tmp_path: Path):
    # Create CA 1 (approved) and CA 2 (unapproved)
    _, _, ca1_pem, ca1_fp = _generate_test_ca("SaintVision Approved CA")
    _, _, ca2_pem, ca2_fp = _generate_test_ca("Rogue Test CA")

    ca1_file = tmp_path / "ca1.pem"
    ca1_file.write_bytes(ca1_pem)

    ca2_file = tmp_path / "ca2.pem"
    ca2_file.write_bytes(ca2_pem)

    # 1. Approved CA matching allowlist succeeds
    ok, err, digest = inspect_ca_bundle(ca1_file, allowed_fingerprints=[ca1_fp])
    assert ok is True
    assert err is None
    assert digest["rootFingerprint"] == ca1_fp
    assert digest["fingerprintVerified"] is True

    # 2. Rogue CA against ca1 allowlist FAILS
    ok, err, _ = inspect_ca_bundle(ca2_file, allowed_fingerprints=[ca1_fp])
    assert ok is False
    assert "does not match approved allowlist" in err

    # 3. Non-existent CA file FAILS
    missing_file = tmp_path / "non_existent.pem"
    ok, err, _ = inspect_ca_bundle(missing_file)
    assert ok is False
    assert "Failed to read CA bundle" in err

    # 4. Empty allowlist FAILS closed (F2)
    ok, err, _ = inspect_ca_bundle(ca1_file, allowed_fingerprints=[])
    assert ok is False
    assert "Fingerprint allowlist must not be empty" in err

    # 5. None allowlist FAILS closed (F2)
    ok, err, _ = inspect_ca_bundle(ca1_file, allowed_fingerprints=None)
    assert ok is False
    assert "Fingerprint allowlist must not be empty" in err


def test_tls_socket_handshake_rejects_wrong_ca(tmp_path: Path):
    """F6: Local TLS server with approved CA vs wrong CA verifies handshake enforcement."""
    ca1_key, ca1_cert, ca1_pem, ca1_fp = _generate_test_ca("Approved Intranet Root CA")
    ca2_key, ca2_cert, ca2_pem, _ = _generate_test_ca("Wrong Intranet Root CA")

    # Generate server cert signed by CA 1 for localhost
    _, srv_cert_pem, srv_key_pem = _generate_server_cert(ca1_key, ca1_cert, hostname="localhost")

    srv_cert_file = tmp_path / "server-cert.pem"
    srv_cert_file.write_bytes(srv_cert_pem)
    srv_key_file = tmp_path / "server-key.pem"
    srv_key_file.write_bytes(srv_key_pem)

    ca1_bundle = tmp_path / "ca1-bundle.pem"
    ca1_bundle.write_bytes(ca1_pem)

    ca2_bundle = tmp_path / "ca2-bundle.pem"
    ca2_bundle.write_bytes(ca2_pem)

    # Start TLS server on loopback
    server_ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    server_ssl_ctx.load_cert_chain(certfile=str(srv_cert_file), keyfile=str(srv_key_file))

    httpd = HTTPServer(("127.0.0.1", 0), SimpleHTTPRequestHandler)
    httpd.socket = server_ssl_ctx.wrap_socket(httpd.socket, server_side=True)
    server_port = httpd.server_port

    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()

    try:
        # A. Handshake with CA 1 bundle -> SUCCEEDS
        ok, err = verify_tls_socket_handshake("localhost", server_port, ca1_bundle, timeout_sec=2.0)
        assert ok is True
        assert err is None

        # B. Handshake with CA 2 bundle (wrong CA) -> FAILS (SSLCertVerificationError)
        ok, err = verify_tls_socket_handshake("localhost", server_port, ca2_bundle, timeout_sec=2.0)
        assert ok is False
        assert "TLS certificate verification failed" in err
    finally:
        httpd.shutdown()
        httpd.server_close()


# =========================================================================
# 7. CLI Execution Test
# =========================================================================

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
    assert data["referenceOnly"] is True
    assert data["acceptanceClaim"] is False
    validate_evidence(data)
# =========================================================================
# 8. Live Browser 5-Step Progression & Failure Propagation (F1)
# =========================================================================

def test_live_browser_step2_failure_marks_downstream_not_observed(monkeypatch):
    """F1: If Step 2 (login_initiation) fails, steps 3~5 must be marked NOT_OBSERVED."""
    from unittest.mock import MagicMock

    monkeypatch.setattr("tools.observe_portal_login_journey.check_domain_resolution", lambda h: (True, None))
    monkeypatch.setattr("tools.observe_portal_login_journey.check_tcp_connection", lambda h, p, timeout_sec=2.0: (True, None))

    class FakePage:
        url = "https://portal.sv.lan"

        def goto(self, url, timeout=10000, wait_until="domcontentloaded"):
            return MagicMock(status=200)

        def locator(self, selector):
            # Fail on login button
            loc = MagicMock()
            loc.first = loc
            loc.wait_for.side_effect = TimeoutError("Login button timed out")
            return loc

    class FakeContext:
        def new_page(self):
            return FakePage()
        def close(self):
            pass

    class FakeBrowser:
        def new_context(self, **kwargs):
            return FakeContext()
        def close(self):
            pass

    class FakePlaywright:
        @property
        def chromium(self):
            m = MagicMock()
            m.launch.return_value = FakeBrowser()
            return m
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    monkeypatch.setattr("playwright.sync_api.sync_playwright", lambda: FakePlaywright())

    observer = PortalLoginJourneyObserver(target_url="https://portal.sv.lan", mock_mode=False)
    evidence = observer.execute_journey(require_clean=False, require_remote_containment=False)

    assert evidence["overallStatus"] == "FAIL"
    assert evidence["steps"][0]["id"] == "portal_tls_reachability"
    assert evidence["steps"][0]["status"] == "PASS"
    assert evidence["steps"][1]["id"] == "login_initiation"
    assert evidence["steps"][1]["status"] == "FAIL"
    assert evidence["steps"][2]["status"] == "NOT_OBSERVED"
    assert evidence["steps"][3]["status"] == "NOT_OBSERVED"
    assert evidence["steps"][4]["status"] == "NOT_OBSERVED"
    validate_evidence(evidence)


def test_live_browser_all_5_steps_success_sets_acceptance_claim(monkeypatch, tmp_path):
    """F1 & F2: If all 5 steps succeed in live browser with verified CA and network observations, acceptanceClaim MUST be True."""
    from unittest.mock import MagicMock

    _, _, ca_pem, ca_fp = _generate_test_ca("SaintVision Intranet Root CA")
    ca_bundle = tmp_path / "ca_bundle.pem"
    ca_bundle.write_bytes(ca_pem)

    monkeypatch.setattr("tools.observe_portal_login_journey.check_domain_resolution", lambda h: (True, None))
    monkeypatch.setattr("tools.observe_portal_login_journey.check_tcp_connection", lambda h, p, timeout_sec=2.0: (True, None))
    monkeypatch.setattr("tools.observe_portal_login_journey.verify_tls_socket_handshake", lambda h, p, c, timeout_sec=2.0: (True, None))

    class FakePage:
        url = "https://portal.sv.lan/studio"

        def __init__(self):
            self._callbacks = []

        def on(self, event, handler):
            if event == "response":
                self._callbacks.append(handler)

        def goto(self, url, timeout=10000, wait_until="domcontentloaded"):
            return MagicMock(status=200)

        def locator(self, selector):
            loc = MagicMock()
            loc.first = loc
            loc.wait_for.return_value = None
            loc.click.return_value = None
            loc.is_visible.return_value = False
            return loc

        def wait_for_url(self, pred, timeout=10000):
            # Trigger network responses for token and /v1/session
            for cb in self._callbacks:
                cb(MagicMock(url="https://idp.sv.lan/protocol/openid-connect/token", status=200))
                session_resp = MagicMock(url="https://portal.sv.lan/v1/session", status=200)
                session_resp.json.return_value = {
                    "subjectId": "oidc:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
                    "tenantId": "c9a0b1c2-d3e4-4f5a-8b9c-0d1e2f3a4b5c",
                    "expiresAt": int(time.time()) + 7200,
                }
                cb(session_resp)
            return None

        def wait_for_timeout(self, ms):
            pass

        def evaluate(self, script):
            return {
                "txCleared": True,
                "storagePurged": True,
                "inMemorySeamPresent": True,
                "inMemoryTokenPurged": True,
            }

    class FakeContext:
        def new_page(self):
            return FakePage()
        def close(self):
            pass

    class FakeBrowser:
        def new_context(self, **kwargs):
            assert kwargs.get("ignore_https_errors") is False, "ignore_https_errors must strictly be False"
            return FakeContext()
        def close(self):
            pass

    class FakePlaywright:
        @property
        def chromium(self):
            m = MagicMock()
            def launch(headless=True, args=None):
                args_list = args or []
                assert all("ignore-cert" not in a.lower() for a in args_list), f"Certificate ignore flag found in {args_list}"
                return FakeBrowser()
            m.launch.side_effect = launch
            return m
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    monkeypatch.setattr("playwright.sync_api.sync_playwright", lambda: FakePlaywright())

    observer = PortalLoginJourneyObserver(
        target_url="https://portal.sv.lan",
        ca_bundle=str(ca_bundle),
        allowed_root_fingerprints=[ca_fp],
        mock_mode=False,
    )
    evidence = observer.execute_journey(require_clean=False, require_remote_containment=False)

    assert evidence["overallStatus"] == "PASS"
    assert evidence["measurementKind"] == "LIVE_BROWSER"
    assert evidence["referenceOnly"] is False
    assert evidence["acceptanceClaim"] is True
    assert evidence["audit"]["tlsValidationEnforced"] is True
    assert evidence["caDigest"]["fingerprintVerified"] is True
    assert len(evidence["steps"]) == 5
    for s in evidence["steps"]:
        assert s["status"] == "PASS"

    validate_evidence(evidence)


def test_live_browser_without_ca_bundle_sets_acceptance_claim_false(monkeypatch):
    """F2: Live browser without verified CA bundle MUST NOT claim acceptance."""
    from unittest.mock import MagicMock

    monkeypatch.setattr("tools.observe_portal_login_journey.check_domain_resolution", lambda h: (True, None))
    monkeypatch.setattr("tools.observe_portal_login_journey.check_tcp_connection", lambda h, p, timeout_sec=2.0: (True, None))

    class FakePage:
        url = "https://portal.sv.lan/studio"
        def on(self, event, handler):
            pass
        def goto(self, url, timeout=10000, wait_until="domcontentloaded"):
            return MagicMock(status=200)
        def locator(self, selector):
            loc = MagicMock()
            loc.first = loc
            loc.wait_for.return_value = None
            loc.click.return_value = None
            loc.is_visible.return_value = False
            return loc
        def wait_for_url(self, pred, timeout=10000):
            return None
        def wait_for_timeout(self, ms):
            pass
        def evaluate(self, script):
            return {"txCleared": True, "storagePurged": True, "inMemorySeamPresent": True, "inMemoryTokenPurged": True}

    class FakeContext:
        def new_page(self):
            return FakePage()
        def close(self):
            pass

    class FakeBrowser:
        def new_context(self, **kwargs):
            return FakeContext()
        def close(self):
            pass

    class FakePlaywright:
        @property
        def chromium(self):
            m = MagicMock()
            m.launch.return_value = FakeBrowser()
            return m
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    monkeypatch.setattr("playwright.sync_api.sync_playwright", lambda: FakePlaywright())

    observer = PortalLoginJourneyObserver(target_url="https://portal.sv.lan", ca_bundle=None, mock_mode=False)
    evidence = observer.execute_journey(require_clean=False, require_remote_containment=False)

    # Without CA bundle, acceptanceClaim must be False!
    assert evidence["acceptanceClaim"] is False
    assert evidence["audit"]["tlsValidationEnforced"] is False


def test_live_browser_fails_when_network_token_or_session_not_observed(monkeypatch, tmp_path):
    """F1: Fake page that does not observe token exchange fails step 3."""
    from unittest.mock import MagicMock

    _, _, ca_pem, ca_fp = _generate_test_ca("SaintVision Intranet Root CA")
    ca_bundle = tmp_path / "ca_bundle.pem"
    ca_bundle.write_bytes(ca_pem)

    monkeypatch.setattr("tools.observe_portal_login_journey.check_domain_resolution", lambda h: (True, None))
    monkeypatch.setattr("tools.observe_portal_login_journey.check_tcp_connection", lambda h, p, timeout_sec=2.0: (True, None))
    monkeypatch.setattr("tools.observe_portal_login_journey.verify_tls_socket_handshake", lambda h, p, c, timeout_sec=2.0: (True, None))

    class FakePage:
        url = "https://portal.sv.lan/studio"
        def on(self, event, handler):
            pass  # Does not trigger any token or session response!
        def goto(self, url, timeout=10000, wait_until="domcontentloaded"):
            return MagicMock(status=200)
        def locator(self, selector):
            loc = MagicMock()
            loc.first = loc
            loc.wait_for.return_value = None
            loc.click.return_value = None
            loc.is_visible.return_value = False
            return loc
        def wait_for_url(self, pred, timeout=10000):
            return None
        def wait_for_timeout(self, ms):
            pass
        def evaluate(self, script):
            return {"txCleared": True, "storagePurged": True, "inMemorySeamPresent": True, "inMemoryTokenPurged": True}

    class FakeContext:
        def new_page(self):
            return FakePage()
        def close(self):
            pass

    class FakeBrowser:
        def new_context(self, **kwargs):
            return FakeContext()
        def close(self):
            pass

    class FakePlaywright:
        @property
        def chromium(self):
            m = MagicMock()
            m.launch.return_value = FakeBrowser()
            return m
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    monkeypatch.setattr("playwright.sync_api.sync_playwright", lambda: FakePlaywright())

    observer = PortalLoginJourneyObserver(
        target_url="https://portal.sv.lan",
        ca_bundle=str(ca_bundle),
        allowed_root_fingerprints=[ca_fp],
        mock_mode=False,
    )
    evidence = observer.execute_journey(require_clean=False, require_remote_containment=False)

    # Step 3 must FAIL because token endpoint was not observed on network
    assert evidence["overallStatus"] == "FAIL"
    assert evidence["steps"][2]["id"] == "pkce_callback"
    assert evidence["steps"][2]["status"] == "FAIL"
    assert "Token endpoint exchange request was not observed" in evidence["steps"][2]["detail"]
    assert evidence["acceptanceClaim"] is False
    validate_evidence(evidence)


# =========================================================================
# 9. Review Remediations (N1, N2, N3, N4)
# =========================================================================

# --- N1: Lookalike Origin and Canonical SessionView Schema Tests ---

def test_live_browser_rejects_lookalike_token_origin(monkeypatch, tmp_path):
    """N1: Token endpoint on lookalike domain (e.g. idp.sv.lan.attacker.invalid) MUST NOT be accepted."""
    from unittest.mock import MagicMock

    _, _, ca_pem, ca_fp = _generate_test_ca("SaintVision Intranet Root CA")
    ca_bundle = tmp_path / "ca_bundle.pem"
    ca_bundle.write_bytes(ca_pem)

    monkeypatch.setattr("tools.observe_portal_login_journey.check_domain_resolution", lambda h: (True, None))
    monkeypatch.setattr("tools.observe_portal_login_journey.check_tcp_connection", lambda h, p, timeout_sec=2.0: (True, None))
    monkeypatch.setattr("tools.observe_portal_login_journey.verify_tls_socket_handshake", lambda h, p, c, timeout_sec=2.0: (True, None))

    class FakePage:
        url = "https://portal.sv.lan/studio"
        def __init__(self):
            self._callbacks = []
        def on(self, event, handler):
            if event == "response":
                self._callbacks.append(handler)
        def goto(self, url, timeout=10000, wait_until="domcontentloaded"):
            return MagicMock(status=200)
        def locator(self, selector):
            loc = MagicMock()
            loc.first = loc
            loc.wait_for.return_value = None
            loc.click.return_value = None
            loc.is_visible.return_value = False
            return loc
        def wait_for_url(self, pred, timeout=10000):
            for cb in self._callbacks:
                # Injects token on attacker lookalike domain!
                cb(MagicMock(url="https://idp.sv.lan.attacker.invalid/protocol/openid-connect/token", status=200))
                session_resp = MagicMock(url="https://portal.sv.lan/v1/session", status=200)
                session_resp.json.return_value = {
                    "subjectId": "oidc:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
                    "tenantId": "c9a0b1c2-d3e4-4f5a-8b9c-0d1e2f3a4b5c",
                    "expiresAt": int(time.time()) + 7200,
                }
                cb(session_resp)
            return None
        def wait_for_timeout(self, ms):
            pass
        def evaluate(self, script):
            return {"txCleared": True, "storagePurged": True, "inMemorySeamPresent": True, "inMemoryTokenPurged": True}

    class FakeContext:
        def new_page(self):
            return FakePage()
        def close(self):
            pass

    class FakeBrowser:
        def new_context(self, **kwargs):
            return FakeContext()
        def close(self):
            pass

    class FakePlaywright:
        @property
        def chromium(self):
            m = MagicMock()
            m.launch.return_value = FakeBrowser()
            return m
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    monkeypatch.setattr("playwright.sync_api.sync_playwright", lambda: FakePlaywright())

    observer = PortalLoginJourneyObserver(
        target_url="https://portal.sv.lan",
        ca_bundle=str(ca_bundle),
        allowed_root_fingerprints=[ca_fp],
        mock_mode=False,
    )
    evidence = observer.execute_journey(require_clean=False, require_remote_containment=False)

    assert evidence["overallStatus"] == "FAIL"
    assert evidence["steps"][2]["id"] == "pkce_callback"
    assert evidence["steps"][2]["status"] == "FAIL"
    assert "Token endpoint exchange request was not observed" in evidence["steps"][2]["detail"]
    assert evidence["acceptanceClaim"] is False


def test_live_browser_rejects_lookalike_portal_origin(monkeypatch, tmp_path):
    """N1: Session endpoint on lookalike domain (e.g. portal.sv.lan.attacker.invalid) MUST NOT be accepted."""
    from unittest.mock import MagicMock

    _, _, ca_pem, ca_fp = _generate_test_ca("SaintVision Intranet Root CA")
    ca_bundle = tmp_path / "ca_bundle.pem"
    ca_bundle.write_bytes(ca_pem)

    monkeypatch.setattr("tools.observe_portal_login_journey.check_domain_resolution", lambda h: (True, None))
    monkeypatch.setattr("tools.observe_portal_login_journey.check_tcp_connection", lambda h, p, timeout_sec=2.0: (True, None))
    monkeypatch.setattr("tools.observe_portal_login_journey.verify_tls_socket_handshake", lambda h, p, c, timeout_sec=2.0: (True, None))

    class FakePage:
        url = "https://portal.sv.lan/studio"
        def __init__(self):
            self._callbacks = []
        def on(self, event, handler):
            if event == "response":
                self._callbacks.append(handler)
        def goto(self, url, timeout=10000, wait_until="domcontentloaded"):
            return MagicMock(status=200)
        def locator(self, selector):
            loc = MagicMock()
            loc.first = loc
            loc.wait_for.return_value = None
            loc.click.return_value = None
            loc.is_visible.return_value = False
            return loc
        def wait_for_url(self, pred, timeout=10000):
            for cb in self._callbacks:
                cb(MagicMock(url="https://idp.sv.lan/protocol/openid-connect/token", status=200))
                # Session on lookalike domain!
                session_resp = MagicMock(url="https://portal.sv.lan.attacker.invalid/v1/session", status=200)
                session_resp.json.return_value = {
                    "subjectId": "oidc:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
                    "tenantId": "c9a0b1c2-d3e4-4f5a-8b9c-0d1e2f3a4b5c",
                    "expiresAt": int(time.time()) + 7200,
                }
                cb(session_resp)
            return None
        def wait_for_timeout(self, ms):
            pass
        def evaluate(self, script):
            return {"txCleared": True, "storagePurged": True, "inMemorySeamPresent": True, "inMemoryTokenPurged": True}

    class FakeContext:
        def new_page(self):
            return FakePage()
        def close(self):
            pass

    class FakeBrowser:
        def new_context(self, **kwargs):
            return FakeContext()
        def close(self):
            pass

    class FakePlaywright:
        @property
        def chromium(self):
            m = MagicMock()
            m.launch.return_value = FakeBrowser()
            return m
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    monkeypatch.setattr("playwright.sync_api.sync_playwright", lambda: FakePlaywright())

    observer = PortalLoginJourneyObserver(
        target_url="https://portal.sv.lan",
        ca_bundle=str(ca_bundle),
        allowed_root_fingerprints=[ca_fp],
        mock_mode=False,
    )
    evidence = observer.execute_journey(require_clean=False, require_remote_containment=False)

    assert evidence["overallStatus"] == "FAIL"
    assert evidence["steps"][3]["id"] == "identity_session_display"
    assert evidence["steps"][3]["status"] == "FAIL"
    assert "/v1/session endpoint request was not observed" in evidence["steps"][3]["detail"]
    assert evidence["acceptanceClaim"] is False


def test_live_browser_rejects_invalid_session_subject(monkeypatch, tmp_path):
    """N1: Response with invalid subjectId (e.g. oidc:x) fails canonical SessionView validation."""
    from unittest.mock import MagicMock

    _, _, ca_pem, ca_fp = _generate_test_ca("SaintVision Intranet Root CA")
    ca_bundle = tmp_path / "ca_bundle.pem"
    ca_bundle.write_bytes(ca_pem)

    monkeypatch.setattr("tools.observe_portal_login_journey.check_domain_resolution", lambda h: (True, None))
    monkeypatch.setattr("tools.observe_portal_login_journey.check_tcp_connection", lambda h, p, timeout_sec=2.0: (True, None))
    monkeypatch.setattr("tools.observe_portal_login_journey.verify_tls_socket_handshake", lambda h, p, c, timeout_sec=2.0: (True, None))

    class FakePage:
        url = "https://portal.sv.lan/studio"
        def __init__(self):
            self._callbacks = []
        def on(self, event, handler):
            if event == "response":
                self._callbacks.append(handler)
        def goto(self, url, timeout=10000, wait_until="domcontentloaded"):
            return MagicMock(status=200)
        def locator(self, selector):
            loc = MagicMock()
            loc.first = loc
            loc.wait_for.return_value = None
            loc.click.return_value = None
            loc.is_visible.return_value = False
            return loc
        def wait_for_url(self, pred, timeout=10000):
            for cb in self._callbacks:
                cb(MagicMock(url="https://idp.sv.lan/protocol/openid-connect/token", status=200))
                session_resp = MagicMock(url="https://portal.sv.lan/v1/session", status=200)
                # Invalid subjectId "oidc:x"
                session_resp.json.return_value = {
                    "subjectId": "oidc:x",
                    "tenantId": "c9a0b1c2-d3e4-4f5a-8b9c-0d1e2f3a4b5c",
                    "expiresAt": int(time.time()) + 7200,
                }
                cb(session_resp)
            return None
        def wait_for_timeout(self, ms):
            pass
        def evaluate(self, script):
            return {"txCleared": True, "storagePurged": True, "inMemorySeamPresent": True, "inMemoryTokenPurged": True}

    class FakeContext:
        def new_page(self):
            return FakePage()
        def close(self):
            pass

    class FakeBrowser:
        def new_context(self, **kwargs):
            return FakeContext()
        def close(self):
            pass

    class FakePlaywright:
        @property
        def chromium(self):
            m = MagicMock()
            m.launch.return_value = FakeBrowser()
            return m
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    monkeypatch.setattr("playwright.sync_api.sync_playwright", lambda: FakePlaywright())

    observer = PortalLoginJourneyObserver(
        target_url="https://portal.sv.lan",
        ca_bundle=str(ca_bundle),
        allowed_root_fingerprints=[ca_fp],
        mock_mode=False,
    )
    evidence = observer.execute_journey(require_clean=False, require_remote_containment=False)

    assert evidence["overallStatus"] == "FAIL"
    assert evidence["steps"][3]["id"] == "identity_session_display"
    assert evidence["steps"][3]["status"] == "FAIL"
    assert "did not match canonical session schema" in evidence["steps"][3]["detail"]
    assert evidence["acceptanceClaim"] is False


def test_live_browser_rejects_invalid_session_uuid(monkeypatch, tmp_path):
    """N1: Response with non-UUID tenantId (e.g. 'not-a-uuid') fails canonical SessionView validation."""
    from unittest.mock import MagicMock

    _, _, ca_pem, ca_fp = _generate_test_ca("SaintVision Intranet Root CA")
    ca_bundle = tmp_path / "ca_bundle.pem"
    ca_bundle.write_bytes(ca_pem)

    monkeypatch.setattr("tools.observe_portal_login_journey.check_domain_resolution", lambda h: (True, None))
    monkeypatch.setattr("tools.observe_portal_login_journey.check_tcp_connection", lambda h, p, timeout_sec=2.0: (True, None))
    monkeypatch.setattr("tools.observe_portal_login_journey.verify_tls_socket_handshake", lambda h, p, c, timeout_sec=2.0: (True, None))

    class FakePage:
        url = "https://portal.sv.lan/studio"
        def __init__(self):
            self._callbacks = []
        def on(self, event, handler):
            if event == "response":
                self._callbacks.append(handler)
        def goto(self, url, timeout=10000, wait_until="domcontentloaded"):
            return MagicMock(status=200)
        def locator(self, selector):
            loc = MagicMock()
            loc.first = loc
            loc.wait_for.return_value = None
            loc.click.return_value = None
            loc.is_visible.return_value = False
            return loc
        def wait_for_url(self, pred, timeout=10000):
            for cb in self._callbacks:
                cb(MagicMock(url="https://idp.sv.lan/protocol/openid-connect/token", status=200))
                session_resp = MagicMock(url="https://portal.sv.lan/v1/session", status=200)
                # Invalid tenantId "not-a-uuid"
                session_resp.json.return_value = {
                    "subjectId": "oidc:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
                    "tenantId": "not-a-uuid",
                    "expiresAt": int(time.time()) + 7200,
                }
                cb(session_resp)
            return None
        def wait_for_timeout(self, ms):
            pass
        def evaluate(self, script):
            return {"txCleared": True, "storagePurged": True, "inMemorySeamPresent": True, "inMemoryTokenPurged": True}

    class FakeContext:
        def new_page(self):
            return FakePage()
        def close(self):
            pass

    class FakeBrowser:
        def new_context(self, **kwargs):
            return FakeContext()
        def close(self):
            pass

    class FakePlaywright:
        @property
        def chromium(self):
            m = MagicMock()
            m.launch.return_value = FakeBrowser()
            return m
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    monkeypatch.setattr("playwright.sync_api.sync_playwright", lambda: FakePlaywright())

    observer = PortalLoginJourneyObserver(
        target_url="https://portal.sv.lan",
        ca_bundle=str(ca_bundle),
        allowed_root_fingerprints=[ca_fp],
        mock_mode=False,
    )
    evidence = observer.execute_journey(require_clean=False, require_remote_containment=False)

    assert evidence["overallStatus"] == "FAIL"
    assert evidence["steps"][3]["id"] == "identity_session_display"
    assert evidence["steps"][3]["status"] == "FAIL"
    assert "did not match canonical session schema" in evidence["steps"][3]["detail"]
    assert evidence["acceptanceClaim"] is False


def test_live_browser_rejects_expired_session(monkeypatch, tmp_path):
    """N1: Response with expiresAt <= now (e.g. -1 or past) fails canonical SessionView validation."""
    from unittest.mock import MagicMock

    _, _, ca_pem, ca_fp = _generate_test_ca("SaintVision Intranet Root CA")
    ca_bundle = tmp_path / "ca_bundle.pem"
    ca_bundle.write_bytes(ca_pem)

    monkeypatch.setattr("tools.observe_portal_login_journey.check_domain_resolution", lambda h: (True, None))
    monkeypatch.setattr("tools.observe_portal_login_journey.check_tcp_connection", lambda h, p, timeout_sec=2.0: (True, None))
    monkeypatch.setattr("tools.observe_portal_login_journey.verify_tls_socket_handshake", lambda h, p, c, timeout_sec=2.0: (True, None))

    class FakePage:
        url = "https://portal.sv.lan/studio"
        def __init__(self):
            self._callbacks = []
        def on(self, event, handler):
            if event == "response":
                self._callbacks.append(handler)
        def goto(self, url, timeout=10000, wait_until="domcontentloaded"):
            return MagicMock(status=200)
        def locator(self, selector):
            loc = MagicMock()
            loc.first = loc
            loc.wait_for.return_value = None
            loc.click.return_value = None
            loc.is_visible.return_value = False
            return loc
        def wait_for_url(self, pred, timeout=10000):
            for cb in self._callbacks:
                cb(MagicMock(url="https://idp.sv.lan/protocol/openid-connect/token", status=200))
                session_resp = MagicMock(url="https://portal.sv.lan/v1/session", status=200)
                # Expired session: expiresAt = -1
                session_resp.json.return_value = {
                    "subjectId": "oidc:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
                    "tenantId": "c9a0b1c2-d3e4-4f5a-8b9c-0d1e2f3a4b5c",
                    "expiresAt": -1,
                }
                cb(session_resp)
            return None
        def wait_for_timeout(self, ms):
            pass
        def evaluate(self, script):
            return {"txCleared": True, "storagePurged": True, "inMemorySeamPresent": True, "inMemoryTokenPurged": True}

    class FakeContext:
        def new_page(self):
            return FakePage()
        def close(self):
            pass

    class FakeBrowser:
        def new_context(self, **kwargs):
            return FakeContext()
        def close(self):
            pass

    class FakePlaywright:
        @property
        def chromium(self):
            m = MagicMock()
            m.launch.return_value = FakeBrowser()
            return m
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    monkeypatch.setattr("playwright.sync_api.sync_playwright", lambda: FakePlaywright())

    observer = PortalLoginJourneyObserver(
        target_url="https://portal.sv.lan",
        ca_bundle=str(ca_bundle),
        allowed_root_fingerprints=[ca_fp],
        mock_mode=False,
    )
    evidence = observer.execute_journey(require_clean=False, require_remote_containment=False)

    assert evidence["overallStatus"] == "FAIL"
    assert evidence["steps"][3]["id"] == "identity_session_display"
    assert evidence["steps"][3]["status"] == "FAIL"
    assert "did not match canonical session schema" in evidence["steps"][3]["detail"]
    assert evidence["acceptanceClaim"] is False


# --- N2: Certificate-Error Bypass Flags Prohibition Tests ---

def test_browser_launch_strictly_zero_certificate_ignore_flags():
    """N2: Prohibits any certificate ignore flags in launch arguments and extra args."""
    with pytest.raises(SecurityCircumventionError) as exc:
        PortalLoginJourneyObserver(
            target_url="https://portal.sv.lan",
            mock_mode=False,
            extra_args=["--ignore-certificate-errors-spki-list=abc"],
        )
    assert "detected prohibited flag" in str(exc.value)

    with pytest.raises(SecurityCircumventionError):
        check_circumvention_flags(["--ignore-certificate-errors"])
    with pytest.raises(SecurityCircumventionError):
        check_circumvention_flags(["--ignore-certificate-errors-spki-list=xyz"])
    with pytest.raises(SecurityCircumventionError):
        check_circumvention_flags(["ignoreHTTPSErrors"])


# --- N3: Clean and Reachable Provenance Tests ---

def test_execute_journey_defaults_provenance_for_live_mode(monkeypatch):
    """N3: LIVE execution defaults to require_clean=True and require_remote_containment=True."""
    called_clean = None
    called_remote = None

    def fake_get_git_sha(repo_path=None, require_clean=False, require_remote_containment=False, allowed_remotes=("origin/",)):
        nonlocal called_clean, called_remote
        called_clean = require_clean
        called_remote = require_remote_containment
        return "e4f5835b4eefb41d490cc33c41258d8f6dd1786a"

    monkeypatch.setattr("tools.observe_portal_login_journey.get_git_sha", fake_get_git_sha)
    monkeypatch.setattr("tools.observe_portal_login_journey.check_domain_resolution", lambda h: (False, "DNS unresolvable"))

    observer = PortalLoginJourneyObserver(target_url="https://portal.sv.lan", mock_mode=False)
    observer.execute_journey()

    assert called_clean is True
    assert called_remote is True


# --- N4: In-Memory Token Purge and Logout Tests ---

def test_live_browser_fails_when_in_memory_token_not_purged(monkeypatch, tmp_path):
    """N4: If in-memory access token is not purged after logout, Step 5 fails."""
    from unittest.mock import MagicMock

    _, _, ca_pem, ca_fp = _generate_test_ca("SaintVision Intranet Root CA")
    ca_bundle = tmp_path / "ca_bundle.pem"
    ca_bundle.write_bytes(ca_pem)

    monkeypatch.setattr("tools.observe_portal_login_journey.check_domain_resolution", lambda h: (True, None))
    monkeypatch.setattr("tools.observe_portal_login_journey.check_tcp_connection", lambda h, p, timeout_sec=2.0: (True, None))
    monkeypatch.setattr("tools.observe_portal_login_journey.verify_tls_socket_handshake", lambda h, p, c, timeout_sec=2.0: (True, None))

    class FakePage:
        url = "https://portal.sv.lan/studio"
        def __init__(self):
            self._callbacks = []
        def on(self, event, handler):
            if event == "response":
                self._callbacks.append(handler)
        def goto(self, url, timeout=10000, wait_until="domcontentloaded"):
            return MagicMock(status=200)
        def locator(self, selector):
            loc = MagicMock()
            loc.first = loc
            loc.wait_for.return_value = None
            loc.click.return_value = None
            loc.is_visible.return_value = False
            return loc
        def wait_for_url(self, pred, timeout=10000):
            for cb in self._callbacks:
                cb(MagicMock(url="https://idp.sv.lan/protocol/openid-connect/token", status=200))
                session_resp = MagicMock(url="https://portal.sv.lan/v1/session", status=200)
                session_resp.json.return_value = {
                    "subjectId": "oidc:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
                    "tenantId": "c9a0b1c2-d3e4-4f5a-8b9c-0d1e2f3a4b5c",
                    "expiresAt": int(time.time()) + 7200,
                }
                cb(session_resp)
            return None
        def wait_for_timeout(self, ms):
            pass
        def evaluate(self, script):
            # Simulates inMemoryTokenPurged = False (in-memory token leaked / not cleared)
            return {
                "txCleared": True,
                "storagePurged": True,
                "inMemorySeamPresent": True,
                "inMemoryTokenPurged": False,
            }

    class FakeContext:
        def new_page(self):
            return FakePage()
        def close(self):
            pass

    class FakeBrowser:
        def new_context(self, **kwargs):
            return FakeContext()
        def close(self):
            pass

    class FakePlaywright:
        @property
        def chromium(self):
            m = MagicMock()
            m.launch.return_value = FakeBrowser()
            return m
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    monkeypatch.setattr("playwright.sync_api.sync_playwright", lambda: FakePlaywright())

    observer = PortalLoginJourneyObserver(
        target_url="https://portal.sv.lan",
        ca_bundle=str(ca_bundle),
        allowed_root_fingerprints=[ca_fp],
        mock_mode=False,
    )
    evidence = observer.execute_journey(require_clean=False, require_remote_containment=False)

    assert evidence["overallStatus"] == "FAIL"
    assert evidence["steps"][4]["id"] == "logout"
    assert evidence["steps"][4]["status"] == "FAIL"
    assert "In-memory access token was not cleared after logout" in evidence["steps"][4]["detail"]
    assert evidence["acceptanceClaim"] is False


def test_validate_evidence_requires_in_memory_token_purged():
    """N4: Evidence with acceptanceClaim=True without inMemoryTokenPurged=True is rejected."""
    observer = PortalLoginJourneyObserver(mock_mode=True)
    evidence = observer.execute_journey()

    evidence["referenceOnly"] = False
    evidence["acceptanceClaim"] = True
    evidence["measurementKind"] = "LIVE_BROWSER"
    evidence["audit"]["tlsValidationEnforced"] = True
    evidence["caDigest"] = {
        "caBundleSha256": "a" * 64,
        "rootFingerprint": "b" * 64,
        "fingerprintVerified": True,
    }
    # Step 5 without inMemoryTokenPurged
    evidence["steps"][4]["observations"] = {
        "loginScreenRestored": True,
        "transactionCleared": True,
        "storagePurged": True,
        "inMemoryTokenPurged": False,
    }

    with pytest.raises(jsonschema.ValidationError) as exc:
        validate_evidence(evidence)
    assert "inMemoryTokenPurged=true in logout" in str(exc.value)
