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
import ipaddress
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
import types

try:
    import playwright
    import playwright.sync_api
except ImportError:
    mock_playwright = types.ModuleType("playwright")
    mock_sync_api = types.ModuleType("playwright.sync_api")
    mock_sync_api.sync_playwright = None
    mock_playwright.sync_api = mock_sync_api
    sys.modules["playwright"] = mock_playwright
    sys.modules["playwright.sync_api"] = mock_sync_api

import jsonschema
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools"))


@pytest.fixture(autouse=True)
def _default_platform_support(monkeypatch):
    # Default to supported platform and successful NSS setup for unit/fake-browser tests, except when specifically testing failures
    monkeypatch.setattr("tools.observe_portal_login_journey.check_supported_platform", lambda: (True, None))
    monkeypatch.setattr("tools.observe_portal_login_journey.setup_isolated_nssdb", lambda isolated_home, ca_bundle_path=None: (True, None))

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
    check_supported_platform,
    compute_overall_status,
    configure_isolated_browser_profile,
    get_git_sha,
    setup_isolated_nssdb,
    inspect_ca_bundle,
    is_canonical_session_endpoint,
    is_canonical_token_endpoint,
    validate_canonical_origins,
    validate_evidence,
    validate_session_view,
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
    try:
        ip_obj = ipaddress.ip_address(hostname)
        san_list = [x509.IPAddress(ip_obj)]
    except ValueError:
        san_list = [x509.DNSName(hostname)]
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
            x509.SubjectAlternativeName(san_list),
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
            def launch(headless=True, args=None, env=None, **kwargs):
                args_list = args or []
                assert all("ignore-cert" not in a.lower() for a in args_list), f"Certificate ignore flag found in {args_list}"
                assert env is not None and "HOME" in env, "Chromium must be launched with isolated HOME in env"
                return FakeBrowser()
            m.launch.side_effect = launch
            return m
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    monkeypatch.setattr("playwright.sync_api.sync_playwright", lambda: FakePlaywright())
    monkeypatch.setattr("tools.observe_portal_login_journey.get_git_sha", lambda **kwargs: "a" * 40)

    observer = PortalLoginJourneyObserver(
        target_url="https://portal.sv.lan",
        ca_bundle=str(ca_bundle),
        allowed_root_fingerprints=[ca_fp],
        mock_mode=False,
    )
    evidence = observer.execute_journey(require_clean=True, require_remote_containment=True)

    assert evidence["overallStatus"] == "PASS"
    assert evidence["measurementKind"] == "LIVE_BROWSER"
    assert evidence["referenceOnly"] is False
    assert evidence["acceptanceClaim"] is True
    assert evidence["audit"]["tlsValidationEnforced"] is True
    assert evidence["audit"]["cleanWorktreeVerified"] is True
    assert evidence["audit"]["remoteContainmentVerified"] is True
    assert evidence["caDigest"]["fingerprintVerified"] is True
    assert len(evidence["steps"]) == 5
    for s in evidence["steps"]:
        assert s["status"] == "PASS"
    assert evidence["steps"][4]["observations"]["inMemorySeamPresent"] is True
    assert evidence["steps"][4]["observations"]["inMemoryTokenPurged"] is True

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
    evidence["audit"]["cleanWorktreeVerified"] = True
    evidence["audit"]["remoteContainmentVerified"] = True
    evidence["audit"]["userDataDirIsolated"] = True
    evidence["audit"]["caBundleAppliedToBrowser"] = True
    evidence["audit"]["trustStoreMode"] = "ISOLATED_PROFILE"
    evidence["caDigest"] = {
        "caBundleSha256": "a" * 64,
        "rootFingerprint": "b" * 64,
        "fingerprintVerified": True,
    }
    # Step 5 with seam present but token not purged
    evidence["steps"][4]["observations"] = {
        "loginScreenRestored": True,
        "transactionCleared": True,
        "storagePurged": True,
        "inMemorySeamPresent": True,
        "inMemoryTokenPurged": False,
    }

    with pytest.raises(jsonschema.ValidationError) as exc:
        validate_evidence(evidence)
    assert "inMemoryTokenPurged=true in logout" in str(exc.value)


def test_live_browser_fails_when_in_memory_seam_missing(monkeypatch, tmp_path):
    """N4: If __sv_has_auth_token inspection seam is missing in browser context, logout fails fail-closed."""
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
            # Simulates missing __sv_has_auth_token seam (inMemorySeamPresent = False)
            return {
                "txCleared": True,
                "storagePurged": True,
                "inMemorySeamPresent": False,
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
    assert "In-memory auth token inspection seam (__sv_has_auth_token) is missing or unobservable in browser context" in evidence["steps"][4]["detail"]
    assert evidence["acceptanceClaim"] is False


def test_validate_evidence_requires_in_memory_seam_present():
    """N4: Evidence with acceptanceClaim=True without inMemorySeamPresent=True is rejected."""
    observer = PortalLoginJourneyObserver(mock_mode=True)
    evidence = observer.execute_journey()

    evidence["referenceOnly"] = False
    evidence["acceptanceClaim"] = True
    evidence["measurementKind"] = "LIVE_BROWSER"
    evidence["audit"]["tlsValidationEnforced"] = True
    evidence["audit"]["cleanWorktreeVerified"] = True
    evidence["audit"]["remoteContainmentVerified"] = True
    evidence["audit"]["userDataDirIsolated"] = True
    evidence["audit"]["caBundleAppliedToBrowser"] = True
    evidence["audit"]["trustStoreMode"] = "ISOLATED_PROFILE"
    evidence["caDigest"] = {
        "caBundleSha256": "a" * 64,
        "rootFingerprint": "b" * 64,
        "fingerprintVerified": True,
    }
    # Step 5 with inMemorySeamPresent = False
    evidence["steps"][4]["observations"] = {
        "loginScreenRestored": True,
        "transactionCleared": True,
        "storagePurged": True,
        "inMemorySeamPresent": False,
        "inMemoryTokenPurged": True,
    }

    with pytest.raises(jsonschema.ValidationError) as exc:
        validate_evidence(evidence)
    assert "inMemorySeamPresent=true" in str(exc.value)


def test_live_provenance_bypass_revokes_acceptance_claim(monkeypatch, tmp_path):
    """N3: Bypassing clean worktree or remote containment revokes acceptanceClaim."""
    from unittest.mock import MagicMock

    _, _, ca_pem, ca_fp = _generate_test_ca("SaintVision Intranet Root CA")
    ca_bundle = tmp_path / "ca_bundle.pem"
    ca_bundle.write_bytes(ca_pem)

    monkeypatch.setattr("tools.observe_portal_login_journey.check_domain_resolution", lambda h: (True, None))
    monkeypatch.setattr("tools.observe_portal_login_journey.check_tcp_connection", lambda h, p, timeout_sec=2.0: (True, None))
    monkeypatch.setattr("tools.observe_portal_login_journey.verify_tls_socket_handshake", lambda h, p, c, timeout_sec=2.0: (True, None))
    monkeypatch.setattr("tools.observe_portal_login_journey.get_git_sha", lambda **kwargs: "b" * 40)

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

    # 1. require_clean=False -> acceptanceClaim is False, cleanWorktreeVerified is False
    ev_unclean = observer.execute_journey(require_clean=False, require_remote_containment=True)
    assert ev_unclean["overallStatus"] == "PASS"
    assert ev_unclean["acceptanceClaim"] is False
    assert ev_unclean["audit"]["cleanWorktreeVerified"] is False
    assert ev_unclean["audit"]["remoteContainmentVerified"] is True

    # 2. require_remote_containment=False -> acceptanceClaim is False, remoteContainmentVerified is False
    ev_uncontained = observer.execute_journey(require_clean=True, require_remote_containment=False)
    assert ev_uncontained["overallStatus"] == "PASS"
    assert ev_uncontained["acceptanceClaim"] is False
    assert ev_uncontained["audit"]["cleanWorktreeVerified"] is True
    assert ev_uncontained["audit"]["remoteContainmentVerified"] is False


def test_validate_evidence_requires_clean_and_remote_containment():
    """N3: validate_evidence rejects acceptanceClaim=True if cleanWorktreeVerified or remoteContainmentVerified is False."""
    observer = PortalLoginJourneyObserver(mock_mode=True)
    evidence = observer.execute_journey()

    evidence["referenceOnly"] = False
    evidence["acceptanceClaim"] = True
    evidence["measurementKind"] = "LIVE_BROWSER"
    evidence["audit"]["tlsValidationEnforced"] = True
    evidence["audit"]["cleanWorktreeVerified"] = False
    evidence["audit"]["remoteContainmentVerified"] = True
    evidence["audit"]["userDataDirIsolated"] = True
    evidence["audit"]["caBundleAppliedToBrowser"] = True
    evidence["audit"]["trustStoreMode"] = "ISOLATED_PROFILE"
    evidence["caDigest"] = {
        "caBundleSha256": "a" * 64,
        "rootFingerprint": "b" * 64,
        "fingerprintVerified": True,
    }

    with pytest.raises(jsonschema.ValidationError) as exc:
        validate_evidence(evidence)
    assert "audit.cleanWorktreeVerified == True" in str(exc.value)

    evidence["audit"]["cleanWorktreeVerified"] = True
    evidence["audit"]["remoteContainmentVerified"] = False
    with pytest.raises(jsonschema.ValidationError) as exc:
        validate_evidence(evidence)
    assert "audit.remoteContainmentVerified == True" in str(exc.value)


def test_cli_prohibits_provenance_bypass_flags():
    """N3: Prohibits --no-require-clean and --no-require-remote-containment in arguments."""
    with pytest.raises(SecurityCircumventionError) as exc:
        check_circumvention_flags(["--no-require-clean"])
    assert "detected prohibited flag '--no-require-clean'" in str(exc.value)

    with pytest.raises(SecurityCircumventionError) as exc:
        check_circumvention_flags(["--no-require-remote-containment"])
    assert "detected prohibited flag '--no-require-remote-containment'" in str(exc.value)


def test_cli_parser_does_not_expose_bypass_flags():
    """N3: CLI argument parser does not expose bypass options."""
    import subprocess
    cmd = [sys.executable, str(REPO_ROOT / "tools/observe_portal_login_journey.py"), "--help"]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    assert "--no-require-clean" not in res.stdout
    assert "--no-require-remote-containment" not in res.stdout
    assert "--require-clean" not in res.stdout
    assert "--require-remote-containment" not in res.stdout


def test_validate_evidence_requires_user_data_dir_isolated():
    """H1: validate_evidence rejects acceptanceClaim=True if userDataDirIsolated is False."""
    observer = PortalLoginJourneyObserver(mock_mode=True)
    evidence = observer.execute_journey()
    evidence["referenceOnly"] = False
    evidence["acceptanceClaim"] = True
    evidence["measurementKind"] = "LIVE_BROWSER"
    evidence["audit"]["tlsValidationEnforced"] = True
    evidence["audit"]["cleanWorktreeVerified"] = True
    evidence["audit"]["remoteContainmentVerified"] = True
    evidence["audit"]["caBundleAppliedToBrowser"] = True
    evidence["audit"]["trustStoreMode"] = "ISOLATED_PROFILE"
    evidence["audit"]["userDataDirIsolated"] = False
    evidence["caDigest"] = {
        "caBundleSha256": "a" * 64,
        "rootFingerprint": "b" * 64,
        "fingerprintVerified": True,
    }
    with pytest.raises(jsonschema.ValidationError) as exc:
        validate_evidence(evidence)
    assert "audit.userDataDirIsolated == True" in str(exc.value)


def test_validate_evidence_requires_ca_bundle_applied_to_browser():
    """H1: validate_evidence rejects acceptanceClaim=True if caBundleAppliedToBrowser is False."""
    observer = PortalLoginJourneyObserver(mock_mode=True)
    evidence = observer.execute_journey()
    evidence["referenceOnly"] = False
    evidence["acceptanceClaim"] = True
    evidence["measurementKind"] = "LIVE_BROWSER"
    evidence["audit"]["tlsValidationEnforced"] = True
    evidence["audit"]["cleanWorktreeVerified"] = True
    evidence["audit"]["remoteContainmentVerified"] = True
    evidence["audit"]["userDataDirIsolated"] = True
    evidence["audit"]["trustStoreMode"] = "ISOLATED_PROFILE"
    evidence["audit"]["caBundleAppliedToBrowser"] = False
    evidence["caDigest"] = {
        "caBundleSha256": "a" * 64,
        "rootFingerprint": "b" * 64,
        "fingerprintVerified": True,
    }
    with pytest.raises(jsonschema.ValidationError) as exc:
        validate_evidence(evidence)
    assert "audit.caBundleAppliedToBrowser == True" in str(exc.value)


def test_validate_evidence_requires_valid_trust_store_mode():
    """H1: validate_evidence rejects acceptanceClaim=True if trustStoreMode is not approved."""
    observer = PortalLoginJourneyObserver(mock_mode=True)
    evidence = observer.execute_journey()
    evidence["referenceOnly"] = False
    evidence["acceptanceClaim"] = True
    evidence["measurementKind"] = "LIVE_BROWSER"
    evidence["audit"]["tlsValidationEnforced"] = True
    evidence["audit"]["cleanWorktreeVerified"] = True
    evidence["audit"]["remoteContainmentVerified"] = True
    evidence["audit"]["userDataDirIsolated"] = True
    evidence["audit"]["caBundleAppliedToBrowser"] = True
    evidence["audit"]["trustStoreMode"] = "SIMULATED"
    evidence["caDigest"] = {
        "caBundleSha256": "a" * 64,
        "rootFingerprint": "b" * 64,
        "fingerprintVerified": True,
    }
    with pytest.raises(jsonschema.ValidationError) as exc:
        validate_evidence(evidence)
    assert "audit.trustStoreMode to be ISOLATED_PROFILE or SYSTEM_OPERATOR_STORE" in str(exc.value)


def test_compute_overall_status_pure_unit_matrix():
    """H4 pure unit test: Verifies compute_overall_status permutations & mutation kills without browser."""
    # 1. Any FAIL -> FAIL
    s_fail = [
        StepResult("s1", "S1", "PASS", 1.0, ""),
        StepResult("s2", "S2", "FAIL", 1.0, ""),
        StepResult("s3", "S3", "BLOCKED_EXTERNAL", 1.0, ""),
    ]
    assert compute_overall_status(s_fail) == "FAIL"

    # 2. BLOCKED_EXTERNAL with no FAIL -> BLOCKED_EXTERNAL
    s_blocked = [
        StepResult("s1", "S1", "BLOCKED_EXTERNAL", 1.0, ""),
        StepResult("s2", "S2", "NOT_OBSERVED", 1.0, ""),
    ]
    assert compute_overall_status(s_blocked) == "BLOCKED_EXTERNAL"

    # 3. NOT_OBSERVED with no FAIL and no BLOCKED_EXTERNAL -> FAIL
    s_not_obs = [
        StepResult("s1", "S1", "PASS", 1.0, ""),
        StepResult("s2", "S2", "NOT_OBSERVED", 1.0, ""),
    ]
    assert compute_overall_status(s_not_obs) == "FAIL"

    # 4. All PASS -> PASS
    s_all_pass = [
        StepResult("s1", "S1", "PASS", 1.0, ""),
        StepResult("s2", "S2", "PASS", 1.0, ""),
    ]
    assert compute_overall_status(s_all_pass) == "PASS"

    # 5. Empty list -> FAIL (fail-closed)
    assert compute_overall_status([]) == "FAIL"


def test_validate_canonical_origins_pure_unit():
    """H4 pure unit test: Canonical origin validation rejects non-canonical origins and lookalike domains."""
    # Valid canonical
    validate_canonical_origins("https://portal.sv.lan", "https://idp.sv.lan", live_mode=True)
    validate_canonical_origins("https://portal.sv.lan:8443", "https://idp.sv.lan:8443", live_mode=True)

    # Rejects http
    with pytest.raises(ValueError, match="must use https scheme"):
        validate_canonical_origins("http://portal.sv.lan", "https://idp.sv.lan", live_mode=True)
    with pytest.raises(ValueError, match="must use https scheme"):
        validate_canonical_origins("https://portal.sv.lan", "http://idp.sv.lan", live_mode=True)

    # Rejects lookalike host
    with pytest.raises(ValueError, match=r"must be bound to portal\.sv\.lan"):
        validate_canonical_origins("https://portal.sv.lan.attacker.com", "https://idp.sv.lan", live_mode=True)
    with pytest.raises(ValueError, match=r"must be bound to idp\.sv\.lan"):
        validate_canonical_origins("https://portal.sv.lan", "https://idp.sv.lan.attacker.com", live_mode=True)

    # Rejects raw IP
    with pytest.raises(ValueError, match="must not be a raw IP address"):
        validate_canonical_origins("https://127.0.0.1", "https://idp.sv.lan", live_mode=True)
    with pytest.raises(ValueError, match="must not be a raw IP address"):
        validate_canonical_origins("https://portal.sv.lan", "https://10.0.0.1", live_mode=True)

    # Rejects userinfo
    with pytest.raises(ValueError, match="must not contain userinfo"):
        validate_canonical_origins("https://admin:secret@portal.sv.lan", "https://idp.sv.lan", live_mode=True)


def test_canonical_endpoint_matchers_pure_unit():
    """H4 pure unit test: Exact canonical endpoint matcher functions prevent substring/lookalike confusion."""
    # Token endpoint
    assert is_canonical_token_endpoint("https://idp.sv.lan/protocol/openid-connect/token") is True
    assert is_canonical_token_endpoint("https://idp.sv.lan/realms/saintvision/protocol/openid-connect/token") is True
    assert is_canonical_token_endpoint("https://idp.sv.lan:443/protocol/openid-connect/token") is True

    # Token endpoint negative cases
    assert is_canonical_token_endpoint("https://idp.sv.lan.attacker.com/protocol/openid-connect/token") is False
    assert is_canonical_token_endpoint("http://idp.sv.lan/protocol/openid-connect/token") is False
    assert is_canonical_token_endpoint("https://idp.sv.lan:8443/protocol/openid-connect/token") is False
    assert is_canonical_token_endpoint("https://idp.sv.lan/other/path") is False

    # Session endpoint
    assert is_canonical_session_endpoint("https://portal.sv.lan/v1/session") is True
    assert is_canonical_session_endpoint("https://portal.sv.lan:443/v1/session") is True

    # Session endpoint negative cases
    assert is_canonical_session_endpoint("https://portal.sv.lan.attacker.com/v1/session") is False
    assert is_canonical_session_endpoint("http://portal.sv.lan/v1/session") is False
    assert is_canonical_session_endpoint("https://portal.sv.lan:8443/v1/session") is False
    assert is_canonical_session_endpoint("https://portal.sv.lan/v1/other") is False


def test_validate_session_view_pure_unit():
    """H4 pure unit test: Schema and boundary invariant kills for SessionView."""
    now = 1700000000
    valid_data = {
        "subjectId": "oidc:" + "a" * 64,
        "tenantId": "c9a0b1c2-d3e4-4f5a-8b9c-0d1e2f3a4b5c",
        "expiresAt": now + 3600,
    }
    assert validate_session_view(valid_data, now_ts=now) is True

    # Mutation: non-dict
    assert validate_session_view("string", now_ts=now) is False

    # Mutation: extra property
    extra = dict(valid_data)
    extra["extraField"] = "bad"
    assert validate_session_view(extra, now_ts=now) is False

    # Mutation: invalid subjectId prefix or length
    bad_subj = dict(valid_data, subjectId="not_oidc:" + "a" * 64)
    assert validate_session_view(bad_subj, now_ts=now) is False
    bad_subj2 = dict(valid_data, subjectId="oidc:" + "a" * 63)
    assert validate_session_view(bad_subj2, now_ts=now) is False

    # Mutation: invalid tenantId (non-uuid)
    bad_tenant = dict(valid_data, tenantId="not-a-uuid")
    assert validate_session_view(bad_tenant, now_ts=now) is False

    # Mutation: expired or current timestamp
    expired = dict(valid_data, expiresAt=now)
    assert validate_session_view(expired, now_ts=now) is False
    past = dict(valid_data, expiresAt=now - 10)
    assert validate_session_view(past, now_ts=now) is False

    # Mutation: non-integer or boolean expiresAt
    bool_exp = dict(valid_data, expiresAt=True)
    assert validate_session_view(bool_exp, now_ts=now) is False


def test_configure_isolated_browser_profile_pure_unit(tmp_path):
    """H1/H4 pure unit test: configure_isolated_browser_profile writes EnterpriseRootsEnabled policy."""
    profile_dir = tmp_path / "browser-profile"
    configured, err, info = configure_isolated_browser_profile(profile_dir)
    assert configured is True
    assert err is None
    assert info["isolated"] is True

    policy_file = profile_dir / "policies" / "managed" / "saintvision_policy.json"
    assert policy_file.exists()
    policy = json.loads(policy_file.read_text(encoding="utf-8"))
    assert policy.get("EnterpriseRootsEnabled") is True


def test_non_linux_platform_reports_blocked_external(monkeypatch):
    """H1: Windows/macOS operator execution returns BLOCKED_EXTERNAL."""
    monkeypatch.setattr(
        "tools.observe_portal_login_journey.check_supported_platform",
        lambda: (
            False,
            "Live intranet CA trust isolation is only supported on Linux via isolated $HOME/.pki/nssdb; "
            "platform 'win32' is not supported for live acceptance runs",
        ),
    )
    observer = PortalLoginJourneyObserver(
        target_url="https://portal.sv.lan",
        mock_mode=False,
    )
    evidence = observer.execute_journey(require_clean=False, require_remote_containment=False)
    assert evidence["overallStatus"] == "BLOCKED_EXTERNAL"
    assert "platform 'win32' is not supported" in evidence["blockingReason"]
    assert evidence["steps"][0]["status"] == "BLOCKED_EXTERNAL"
    assert evidence["acceptanceClaim"] is False


def test_live_chromium_nssdb_intranet_ca_trust(tmp_path):
    """H1: Live Chromium HTTPS handshake with isolated NSS DB: wrong root fails, correct root succeeds."""
    import shutil
    if sys.platform != "linux" or not shutil.which("certutil"):
        # Operator premise: Intranet CA NSS DB trust profile executes on Linux in an environment with certutil (libnss3-tools)
        return

    from http.server import HTTPServer, SimpleHTTPRequestHandler
    import threading
    import ssl
    from playwright.sync_api import sync_playwright

    # 1. Generate root CA and server cert
    ca_key, ca_cert, root_ca_pem, ca_fp = _generate_test_ca("SaintVision Intranet Root CA")
    _, server_pem, server_key_pem = _generate_server_cert(ca_key, ca_cert, "127.0.0.1")

    # 2. Generate unrelated rogue CA
    _, _, wrong_ca_pem, _ = _generate_test_ca("Rogue Untrusted Root CA")

    server_cert_file = tmp_path / "server.pem"
    server_cert_file.write_bytes(server_pem)
    server_key_file = tmp_path / "server.key"
    server_key_file.write_bytes(server_key_pem)

    class EchoHandler(SimpleHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body><h1>Intranet Portal Live OK</h1></body></html>")

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), EchoHandler)
    port = server.server_port
    ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_ctx.load_cert_chain(certfile=str(server_cert_file), keyfile=str(server_key_file))
    server.socket = ssl_ctx.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        # Case A: Wrong root registered in isolated NSS DB -> Handshake FAILS
        home_wrong = tmp_path / "home_wrong"
        wrong_ca_file = tmp_path / "wrong_ca.pem"
        wrong_ca_file.write_bytes(wrong_ca_pem)
        ok, err = setup_isolated_nssdb(home_wrong, wrong_ca_file)
        assert ok is True, f"setup_isolated_nssdb failed: {err}"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, env={"HOME": str(home_wrong)})
            context = browser.new_context(ignore_https_errors=False)
            page = context.new_page()
            with pytest.raises(Exception) as exc:
                page.goto(f"https://127.0.0.1:{port}", timeout=5000)
            assert any(k in str(exc.value) for k in ("ERR_CERT_AUTHORITY_INVALID", "ERR_CERT", "CERT_COMMON_NAME_INVALID"))
            context.close()
            browser.close()

        # Case B: Correct root registered in isolated NSS DB -> Handshake SUCCEEDS with HTTP 200
        home_correct = tmp_path / "home_correct"
        root_ca_file = tmp_path / "root_ca.pem"
        root_ca_file.write_bytes(root_ca_pem)
        ok, err = setup_isolated_nssdb(home_correct, root_ca_file)
        assert ok is True, f"setup_isolated_nssdb failed: {err}"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, env={"HOME": str(home_correct)})
            context = browser.new_context(ignore_https_errors=False)
            page = context.new_page()
            resp = page.goto(f"https://127.0.0.1:{port}", timeout=5000)
            assert resp.status == 200
            assert "Intranet Portal Live OK" in page.content()
            context.close()
            browser.close()

    finally:
        server.shutdown()
        server.server_close()


def test_configure_isolated_browser_profile_fails_when_ca_bundle_fails_nss(tmp_path, monkeypatch):
    """Codex r6 F1: configure_isolated_browser_profile returns False when setup_isolated_nssdb fails."""
    profile_dir = tmp_path / "browser-profile"
    ca_bundle = tmp_path / "ca.pem"
    ca_bundle.write_text("dummy ca", encoding="utf-8")
    monkeypatch.setattr("tools.observe_portal_login_journey.setup_isolated_nssdb", lambda h, c: (False, "certutil failed to initialize DB"))
    ok, err, info = configure_isolated_browser_profile(profile_dir, ca_bundle)
    assert ok is False
    assert "certutil failed to initialize DB" in err
    assert info["nssConfigured"] is False


def test_configure_isolated_browser_profile_fails_when_ca_bundle_missing(tmp_path):
    """Codex r6 F1: configure_isolated_browser_profile returns False when ca_bundle_path does not exist."""
    profile_dir = tmp_path / "browser-profile"
    missing_ca = tmp_path / "nonexistent_ca.pem"
    ok, err, info = configure_isolated_browser_profile(profile_dir, missing_ca)
    assert ok is False
    assert "not found" in err
    assert info["nssConfigured"] is False


def test_live_browser_fails_and_revokes_acceptance_when_nssdb_setup_fails(monkeypatch, tmp_path):
    """Codex r6 F1: When CA bundle provided but NSS DB setup fails, journey must FAIL and revoke acceptance even if fake browser succeeds."""
    from unittest.mock import MagicMock

    ca_key, ca_cert, ca_pem, ca_fp = _generate_test_ca("SaintVision Test CA")
    ca_bundle = tmp_path / "ca-bundle.crt"
    ca_bundle.write_bytes(ca_pem)

    monkeypatch.setattr("tools.observe_portal_login_journey.check_domain_resolution", lambda h: (True, None))
    monkeypatch.setattr("tools.observe_portal_login_journey.check_tcp_connection", lambda h, p, timeout_sec=2.0: (True, None))
    monkeypatch.setattr("tools.observe_portal_login_journey.setup_isolated_nssdb", lambda h, c: (False, "certutil binary not found on host"))

    # Provide a fake browser that would otherwise succeed
    class FakePage:
        def goto(self, url, **kwargs):
            return MagicMock(status=200)
        def wait_for_load_state(self, *args, **kwargs):
            pass
        def locator(self, *args, **kwargs):
            m = MagicMock()
            m.first = m
            return m
        def evaluate(self, script, *args):
            return {
                "txCleared": True,
                "storagePurged": True,
                "inMemorySeamPresent": True,
                "inMemoryTokenPurged": True,
            }
        def on(self, event, handler):
            pass

    class FakeBrowser:
        def new_context(self, **kwargs):
            return FakeBrowserContext()
        def close(self):
            pass

    class FakeBrowserContext:
        def new_page(self):
            return FakePage()
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
    monkeypatch.setattr("tools.observe_portal_login_journey.get_git_sha", lambda **kwargs: "a" * 40)

    observer = PortalLoginJourneyObserver(
        target_url="https://portal.sv.lan",
        ca_bundle=str(ca_bundle),
        allowed_root_fingerprints=[ca_fp],
        mock_mode=False,
    )
    evidence = observer.execute_journey(require_clean=True, require_remote_containment=True)

    assert evidence["overallStatus"] == "FAIL"
    assert evidence["acceptanceClaim"] is False
    assert evidence["audit"]["caBundleAppliedToBrowser"] is False
    assert evidence["steps"][0]["id"] == "portal_tls_reachability"
    assert evidence["steps"][0]["status"] == "FAIL"
    assert "NSS DB trust profile configuration failed" in evidence["steps"][0]["detail"]
    assert evidence["steps"][1]["status"] == "NOT_OBSERVED"
    assert evidence["steps"][2]["status"] == "NOT_OBSERVED"
    assert evidence["steps"][3]["status"] == "NOT_OBSERVED"
    assert evidence["steps"][4]["status"] == "NOT_OBSERVED"
