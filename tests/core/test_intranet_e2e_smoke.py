"""A smoke check that can be talked into passing is worse than none.

These tests run without a network. They pin the three things that make the report
worth reading: that certificate verification cannot be switched off, that a name which
does not resolve becomes BLOCKED_EXTERNAL rather than a substituted address, and that
no address, token or key reaches the output.
"""

from __future__ import annotations

import datetime as dt
import json
import ssl

import pytest

from tools import intranet_e2e_smoke as smoke


ISSUER = "https://idp.sv.lan/realms/saintvision"


def passing_observations():
    return {name: {"status": "MEASURED_PASS"} for name in smoke.REQUIRED}


def passing_evidence():
    return {
        "schemaVersion": smoke.SCHEMA_VERSION,
        "codeSha": "0" * 40,
        "collectorSha256": "a" * 64,
        "criteria": dict(smoke.CRITERIA),
        "provenance": {"workingTreeClean": True, "contentClean": True},
        "source": {
            "observedAt": "2026-09-30T00:00:00Z",
            "runEnvironment": "operator-workstation",
            "idpHost": "idp.sv.lan",
            "expectedIssuer": ISSUER,
            "caBundleSha256": "b" * 64,
            "controlPlaneHost": "loopback",
            "controlPlanePort": 8080,
            "verificationDisabled": False,
            "resolutionOverridden": False,
        },
        "observations": passing_observations(),
        "verdict": "PASS",
        "acceptanceClaim": True,
    }


# --- verification is not optional -------------------------------------------------


def test_there_is_no_option_to_skip_verification():
    """The point of the check is the certificate. An escape hatch would hollow it out."""
    options = {action.option_strings[0] for action in smoke.parser()._actions if action.option_strings}
    forbidden = {"--insecure", "--no-verify", "--skip-verify", "-k", "--allow-insecure"}
    assert options & forbidden == set()
    assert "--ca-bundle" in options


def test_there_is_no_option_to_override_resolution():
    """A --resolve flag would turn a missing hosts entry into a silent pass."""
    options = {action.option_strings[0] for action in smoke.parser()._actions if action.option_strings}
    assert options & {"--resolve", "--address", "--ip", "--connect-to"} == set()


def test_the_context_verifies_with_hostname_checking(tmp_path):
    bundle = tmp_path / "ca.pem"
    bundle.write_text(_self_signed_pem(), encoding="utf-8")
    context = smoke.trusted_context(bundle)
    assert context.verify_mode is ssl.CERT_REQUIRED
    assert context.check_hostname is True


def _self_signed_pem() -> str:
    """A throwaway CA so trusted_context has something loadable."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "smoke-test-ca")])
    now = dt.datetime.now(dt.timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(days=1))
        .not_valid_after(now + dt.timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    return certificate.public_bytes(serialization.Encoding.PEM).decode()


# --- an unresolved name is a precondition, not a pass ------------------------------


def test_an_unresolved_name_is_blocked_and_records_no_address(monkeypatch):
    monkeypatch.setattr(smoke, "resolve", lambda host: [])
    observation, addresses = smoke.observe_name("idp.sv.lan")
    assert observation == {"status": "BLOCKED_EXTERNAL", "reason": "hosts-not-applied"}
    assert addresses == []


def test_a_resolved_name_records_a_count_not_the_address(monkeypatch):
    monkeypatch.setattr(smoke, "resolve", lambda host: ["192.168.45.143", "fe80::1"])
    observation, addresses = smoke.observe_name("idp.sv.lan")
    assert observation["status"] == "MEASURED_PASS"
    assert observation["resolvedAddressCount"] == 2
    assert observation["addressFamilies"] == ["ipv4", "ipv6"]
    smoke.assert_no_addresses(json.dumps(observation))
    # The addresses are returned for the caller to connect with, never for the report.
    assert addresses


def test_the_verdict_is_blocked_when_the_name_does_not_resolve():
    observations = passing_observations()
    observations["idpNameResolves"] = smoke.blocked("hosts-not-applied")
    assert smoke.smoke_verdict(observations) == "BLOCKED_EXTERNAL"


def test_a_measured_failure_outranks_a_missing_precondition():
    """A wrong certificate is a defect; it must not be reported as "not ready yet"."""
    observations = passing_observations()
    observations["idpNameResolves"] = smoke.blocked("hosts-not-applied")
    observations["idpHttpsVerified"] = smoke.failed("certificate did not verify")
    assert smoke.smoke_verdict(observations) == "FAIL"


@pytest.mark.parametrize(
    ("verdict", "code"), [("PASS", 0), ("FAIL", 1), ("BLOCKED_EXTERNAL", 3), ("NOT_OBSERVED", 3)]
)
def test_every_verdict_has_an_exit_code(verdict, code):
    assert smoke.EXIT_BY_VERDICT[verdict] == code


# --- the issuer must match, and the keys must come from it ------------------------


def test_a_mismatched_issuer_fails_and_does_not_echo_the_wrong_value():
    body = json.dumps({"issuer": "https://somewhere.else/realms/x"}).encode()
    observation, document = smoke.observe_discovery(body, ISSUER)
    assert observation["status"] == "MEASURED_FAIL"
    assert observation["issuerMatches"] is False
    assert "somewhere.else" not in json.dumps(observation)
    assert document is not None


def test_the_expected_issuer_passes():
    body = json.dumps({"issuer": ISSUER, "code_challenge_methods_supported": ["S256"]}).encode()
    observation, _ = smoke.observe_discovery(body, ISSUER)
    assert observation["status"] == "MEASURED_PASS"
    assert observation["issuer"] == ISSUER


def test_a_jwks_uri_on_another_origin_fails(monkeypatch):
    """Keys vouched for by the issuer must come from the issuer."""
    document = {"jwks_uri": "https://evil.example/certs"}
    observation = smoke.observe_jwks(None, document, ISSUER, "idp.sv.lan", 443)
    assert observation["status"] == "MEASURED_FAIL"
    assert "another origin" in observation["reason"]


def test_a_key_set_without_an_rs256_signing_key_fails(monkeypatch):
    document = {"jwks_uri": ISSUER + "/protocol/openid-connect/certs"}
    payload = json.dumps({"keys": [{"alg": "RSA-OAEP", "use": "enc", "kid": "e"}]}).encode()
    monkeypatch.setattr(smoke, "https_request", lambda *a, **k: (200, payload))
    observation = smoke.observe_jwks(None, document, ISSUER, "idp.sv.lan", 443)
    assert observation["status"] == "MEASURED_FAIL"
    assert observation["keyCount"] == 1


def test_a_signing_key_is_recorded_only_as_a_hash(monkeypatch):
    document = {"jwks_uri": ISSUER + "/protocol/openid-connect/certs"}
    payload = json.dumps(
        {"keys": [{"alg": "RS256", "use": "sig", "kid": "secret-looking-kid"},
                  {"alg": "RSA-OAEP", "use": "enc", "kid": "enc"}]}
    ).encode()
    monkeypatch.setattr(smoke, "https_request", lambda *a, **k: (200, payload))
    observation = smoke.observe_jwks(None, document, ISSUER, "idp.sv.lan", 443)
    assert observation["status"] == "MEASURED_PASS"
    assert observation["signingKeyCount"] == 1
    assert "secret-looking-kid" not in json.dumps(observation)
    assert observation["signingKidSha256"] == [smoke.sha256_text("secret-looking-kid")]


# --- a refusal, observed without holding a credential -----------------------------


@pytest.mark.parametrize("error", sorted(smoke.GRANT_DISABLED_ERRORS))
def test_a_grant_refused_as_disabled_passes(monkeypatch, error):
    payload = json.dumps({"error": error}).encode()
    monkeypatch.setattr(smoke, "https_request", lambda *a, **k: (400, payload))
    observation = smoke.observe_grant_refused(None, "h", 443, "sv-portal", {}, "the password grant")
    assert observation["status"] == "MEASURED_PASS"
    assert observation["oauthError"] == error


def test_a_refusal_for_bad_credentials_means_the_grant_is_enabled(monkeypatch):
    """invalid_grant is the wrong refusal: it means the client MAY use this grant.

    That is the finding, not a pass. Accepting any non-200 here would have reported a
    live password grant as a locked door.
    """
    payload = json.dumps({"error": "invalid_grant"}).encode()
    monkeypatch.setattr(smoke, "https_request", lambda *a, **k: (401, payload))
    observation = smoke.observe_grant_refused(None, "h", 443, "sv-portal", {}, "the password grant")
    assert observation["status"] == "MEASURED_FAIL"
    assert "not as a disabled grant" in observation["reason"]


def test_a_granted_token_is_a_failure(monkeypatch):
    monkeypatch.setattr(smoke, "https_request", lambda *a, **k: (200, b'{"access_token":"x"}'))
    observation = smoke.observe_grant_refused(None, "h", 443, "sv-portal", {}, "the password grant")
    assert observation["status"] == "MEASURED_FAIL"
    assert "was granted" in observation["reason"]


def test_the_probe_account_cannot_exist():
    """The refusal is observed with a synthetic name, never a real user's credential."""
    assert "nonexistent" in smoke.SYNTHETIC_ACCOUNT
    assert smoke.SYNTHETIC_ACCOUNT not in {"sv.operator", "sv.viewer"}


# --- the control plane must refuse ------------------------------------------------


def test_a_401_from_the_control_plane_passes(monkeypatch):
    monkeypatch.setattr(smoke, "plain_request", lambda *a, **k: (401, b'{"code":"AUTH-0050"}'))
    observation = smoke.observe_control_plane("http://127.0.0.1:8080", authorization="Bearer x")
    assert observation == {"status": "MEASURED_PASS", "httpStatus": 401, "problemCode": "AUTH-0050"}


@pytest.mark.parametrize("status", [200, 403, 500])
def test_any_other_status_from_the_control_plane_fails(monkeypatch, status):
    monkeypatch.setattr(smoke, "plain_request", lambda *a, **k: (status, b"{}"))
    observation = smoke.observe_control_plane("http://127.0.0.1:8080", authorization=None)
    assert observation["status"] == "MEASURED_FAIL"
    assert observation["httpStatus"] == status


def test_an_absent_control_plane_is_blocked_not_failed(monkeypatch):
    def refuse(*args, **kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr(smoke, "plain_request", refuse)
    observation = smoke.observe_control_plane("http://127.0.0.1:8080", authorization=None)
    assert observation == {"status": "BLOCKED_EXTERNAL", "reason": "control-plane-not-running"}


def test_a_non_loopback_control_plane_url_is_refused():
    with pytest.raises(smoke.SmokeAborted, match="loopback"):
        smoke.plain_request("http://10.0.0.5:8080/v1/session")


# --- the report carries no address, token or key ----------------------------------


@pytest.mark.parametrize(
    "value",
    ["192.168.45.143", "10.0.0.1", "127.0.0.1", "fe80::1234:5678",
     "2001:0db8:0000:0000:0000:ff00:0042:8329"],
)
def test_an_address_in_the_output_is_refused(value):
    with pytest.raises(smoke.SmokeAborted, match="address-like"):
        smoke.assert_no_addresses(json.dumps({"x": value}))


@pytest.mark.parametrize(
    "value",
    ["2026-09-30T00:14:45Z", "2026-09-30T09:10:10+09:00", "2026-12-28",
     "ae8816d9369e5861cd6ac6b9a4269fae617855bb3adb4cb7088649ba5466bd93",
     "idp.sv.lan", "https://idp.sv.lan/realms/saintvision"],
)
def test_the_guard_is_silent_on_what_the_report_legitimately_carries(value):
    smoke.assert_no_addresses(json.dumps({"x": value}))


def test_the_certificate_expiry_is_recorded_without_a_clock_time():
    """`Dec 28 23:05:05 2026 GMT` would read as an IPv6 address to the guard."""
    assert smoke.expiry_date("Dec 28 23:05:05 2026 GMT") == "2026-12-28"
    smoke.assert_no_addresses(json.dumps({"leafNotAfterDate": "2026-12-28"}))
    with pytest.raises(smoke.SmokeAborted):
        smoke.assert_no_addresses(json.dumps({"leafNotAfter": "Dec 28 23:05:05 2026 GMT"}))


def test_the_control_plane_is_named_not_addressed():
    assert smoke.control_plane_label("http://127.0.0.1:8080") == "loopback"
    assert smoke.control_plane_label("http://10.1.2.3:8080") == "non-loopback"


# --- the verdict cannot be asserted by hand ---------------------------------------


def test_the_shape_this_collector_writes_is_accepted():
    smoke.validate_evidence(passing_evidence())


@pytest.mark.parametrize("name", smoke.REQUIRED)
def test_a_single_blocked_observation_cannot_be_carried_by_a_pass(name):
    evidence = passing_evidence()
    evidence["observations"][name] = smoke.blocked("something external")
    with pytest.raises(ValueError, match="verdict"):
        smoke.validate_evidence(evidence)


def test_a_hand_written_pass_is_refused():
    evidence = passing_evidence()
    evidence["observations"]["idpHttpsVerified"] = smoke.failed("certificate did not verify")
    evidence["verdict"] = "PASS"
    with pytest.raises(ValueError, match="verdict"):
        smoke.validate_evidence(evidence)


def test_claiming_verification_was_disabled_is_refused():
    evidence = passing_evidence()
    evidence["source"]["verificationDisabled"] = True
    with pytest.raises(ValueError, match="verification is never disabled"):
        smoke.validate_evidence(evidence)


def test_claiming_resolution_was_overridden_is_refused():
    evidence = passing_evidence()
    evidence["source"]["resolutionOverridden"] = True
    with pytest.raises(ValueError, match="resolution is never overridden"):
        smoke.validate_evidence(evidence)


def test_the_ca_bundle_must_be_identified():
    evidence = passing_evidence()
    evidence["source"]["caBundleSha256"] = "not-a-hash"
    with pytest.raises(ValueError, match="CA bundle"):
        smoke.validate_evidence(evidence)


def test_an_unrecognised_status_is_refused():
    evidence = passing_evidence()
    evidence["observations"]["idpNameResolves"] = {"status": "PROBABLY_FINE"}
    with pytest.raises(ValueError, match="recognised status"):
        smoke.validate_evidence(evidence)


def test_the_rendered_report_names_every_observation():
    evidence = passing_evidence()
    rendered = smoke.render_markdown(evidence)
    for name in smoke.REQUIRED:
        assert f"`{name}`" in rendered
    assert "trust anchor, not a pin" in rendered
    smoke.assert_no_addresses(rendered)


def test_evidence_from_a_dirty_tree_is_refused():
    """codeSha names a commit; on a dirty tree it names bytes that were never in it."""
    for field in ("workingTreeClean", "contentClean"):
        evidence = passing_evidence()
        evidence["provenance"][field] = False
        with pytest.raises(ValueError, match="clean"):
            smoke.validate_evidence(evidence)


def test_a_short_or_absent_code_sha_is_refused():
    for value in (None, "", "abc123", "g" * 40):
        evidence = passing_evidence()
        evidence["codeSha"] = value
        with pytest.raises(ValueError, match="codeSha"):
            smoke.validate_evidence(evidence)


def test_the_run_environment_must_be_named():
    """A report from where the name resolves is not a report about where it does not."""
    evidence = passing_evidence()
    del evidence["source"]["runEnvironment"]
    with pytest.raises(ValueError, match="runEnvironment"):
        smoke.validate_evidence(evidence)
    evidence["source"]["runEnvironment"] = "somewhere"
    with pytest.raises(ValueError, match="runEnvironment"):
        smoke.validate_evidence(evidence)


def test_the_run_environment_is_a_required_argument():
    required = {
        action.option_strings[0]
        for action in smoke.parser()._actions
        if action.option_strings and action.required
    }
    assert "--run-environment" in required
    assert "--ca-bundle" in required
