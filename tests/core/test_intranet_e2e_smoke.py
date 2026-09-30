"""A smoke check that can be talked into passing is worse than none.

The first version of these tests monkeypatched the helpers and proved only that the
helpers returned what they were told to. A review showed what that missed: connect to
one host while passing a foreign issuer, and every identity observation passed. So most
of this file runs **real TLS servers on real sockets**, with two different certificate
authorities, and each finding's revival is a mutation that has to die here.

What is pinned:

* the identity under test comes from the control plane's configuration, not the
  command line, and the TLS target is derived from the issuer;
* verification cannot be disabled and resolution cannot be substituted, including
  through the environment;
* a name that does not resolve is BLOCKED_EXTERNAL, but a resolved host that will not
  answer is a FAIL;
* a refusal only counts when it is the canonical control plane's refusal;
* nothing in the output is an address, a token, a key or a credential.
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import http.server
import json
import socket
import ssl
import threading
from pathlib import Path

import pytest

from tools import intranet_e2e_smoke as smoke


TRUSTED_KID = "smoke-signing-kid"

CANONICAL_PROBLEM = {
    "type": "about:blank",
    "title": "Request rejected",
    "status": 401,
    "code": "AUTH-0050",
    "category": "AUTH",
    "detail": "A current access token is required",
    "retryable": False,
    "traceId": "0" * 32,
    "causeRef": None,
    "evidenceId": None,
}


# --- real certificate authorities and real TLS servers ----------------------------


def make_ca(common_name: str) -> dict:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = dt.datetime.now(dt.timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(days=1))
        .not_valid_after(now + dt.timedelta(days=30))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    der = certificate.public_bytes(serialization.Encoding.DER)
    return {
        "key": key,
        "cert": certificate,
        "pem": certificate.public_bytes(serialization.Encoding.PEM).decode(),
        "sha256": hashlib.sha256(der).hexdigest(),
    }


def make_leaf(ca: dict, host: str, directory: Path, stem: str) -> tuple[Path, Path]:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    now = dt.datetime.now(dt.timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, host)]))
        .issuer_name(ca["cert"].subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(days=1))
        .not_valid_after(now + dt.timedelta(days=20))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(host)]), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(ca["key"], hashes.SHA256())
    )
    cert_path = directory / f"{stem}-cert.pem"
    key_path = directory / f"{stem}-key.pem"
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return cert_path, key_path


class Responder(http.server.BaseHTTPRequestHandler):
    routes: dict = {}

    def _answer(self):
        entry = self.routes.get(self.path.split("?")[0])
        if entry is None:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        status, media, payload = entry
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", media)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    do_GET = _answer
    do_POST = _answer

    def log_message(self, *args):
        pass


def serve_tls(routes, cert_path, key_path):
    handler = type("TlsHandler", (Responder,), {"routes": dict(routes)})
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(str(cert_path), str(key_path))
    server.socket = context.wrap_socket(server.socket, server_side=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def serve_plain(routes):
    handler = type("PlainHandler", (Responder,), {"routes": dict(routes)})
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def idp_routes(issuer: str, *, kid: str = TRUSTED_KID, token_error: str = "unauthorized_client"):
    base = "/realms/" + issuer.split("/realms/")[1]
    return {
        f"{base}/.well-known/openid-configuration": (
            200,
            "application/json",
            {
                "issuer": issuer,
                "jwks_uri": f"{issuer}/protocol/openid-connect/certs",
                "token_endpoint": f"{issuer}/protocol/openid-connect/token",
                "authorization_endpoint": f"{issuer}/protocol/openid-connect/auth",
                "code_challenge_methods_supported": ["S256"],
            },
        ),
        f"{base}/protocol/openid-connect/certs": (
            200,
            "application/json",
            {"keys": [{"kty": "RSA", "alg": "RS256", "use": "sig", "kid": kid,
                       "n": "x", "e": "AQAB"}]},
        ),
        f"{base}/protocol/openid-connect/token": (400, "application/json", {"error": token_error}),
    }


DEFAULT_CP_ROUTES = {
    "/v1/session": (401, "application/problem+json", CANONICAL_PROBLEM),
    "/readyz": (200, "application/json", {"status": "ready"}),
}


@pytest.fixture
def world(tmp_path):
    """One internal CA, one foreign CA, an IdP on localhost, and a control plane."""
    internal = make_ca("smoke internal root")
    foreign = make_ca("smoke foreign root")
    cert, key = make_leaf(internal, "localhost", tmp_path, "idp")
    ca_bundle = tmp_path / "ca.pem"
    ca_bundle.write_text(internal["pem"], encoding="utf-8")
    holder: dict = {"servers": []}

    def start(*, routes=None, kid=TRUSTED_KID, token_error="unauthorized_client", cp_routes=None):
        server = serve_tls({}, cert, key)
        holder["servers"].append(server)
        port = server.server_address[1]
        issuer = f"https://localhost:{port}/realms/test"
        table = routes(issuer) if callable(routes) else idp_routes(
            issuer, kid=kid, token_error=token_error
        )
        server.RequestHandlerClass.routes = dict(table)
        control = serve_plain(cp_routes if cp_routes is not None else DEFAULT_CP_ROUTES)
        holder["servers"].append(control)
        bundle = tmp_path / "trust-bundle.json"
        bundle.write_text(
            json.dumps({"issuer": issuer, "expiresAt": 0,
                        "keys": [{"kid": TRUSTED_KID, "kty": "RSA",
                                  "alg": "RS256", "use": "sig"}]}),
            encoding="utf-8",
        )
        config = tmp_path / "api.json"
        config.write_text(
            json.dumps({"identity": {
                "tenant_id": "00000000-0000-4000-8000-000000000001",
                "issuer": issuer,
                "audience": "sv-api",
                "client_ids": ["sv-portal"],
                "jwks_file": str(bundle),
            }}),
            encoding="utf-8",
        )
        holder.update(
            issuer=issuer, server=server, control=control, config=config, bundle=bundle,
            ca_bundle=ca_bundle, internal=internal, foreign=foreign, tmp=tmp_path,
            leaf_cert=cert, cp_url=f"http://127.0.0.1:{control.server_address[1]}",
        )
        return holder

    yield start
    for server in holder["servers"]:
        server.shutdown()
        server.server_close()


def args_for(w, **overrides):
    return smoke.parser().parse_args([
        "--control-plane-config", str(overrides.get("config", w["config"])),
        "--ca-bundle", str(overrides.get("ca_bundle", w["ca_bundle"])),
        "--allowed-root-sha256", overrides.get("root", w["internal"]["sha256"]),
        "--control-plane-url", overrides.get("cp_url", w["cp_url"]),
        "--run-environment", "operator-workstation",
    ])


def run(w, **overrides):
    return smoke.run(args_for(w, **overrides), smoke.Deadline(20.0),
                     dt.datetime.now(dt.timezone.utc))


# --- the whole path, over real TLS ------------------------------------------------


def test_the_whole_path_passes_against_a_real_provider(world):
    w = world()
    observations, facts = run(w)
    failures = {n: o for n, o in observations.items() if o["status"] != "MEASURED_PASS"}
    assert failures == {}, failures
    assert smoke.smoke_verdict(observations) == "PASS"
    assert facts["issuer"] == w["issuer"]
    assert facts["keyLoggingDisabled"] is True


def test_the_identity_is_taken_from_the_configuration_not_the_command_line():
    """The review's central finding: three free-standing flags let a foreign issuer pass."""
    options = {a.option_strings[0] for a in smoke.parser()._actions if a.option_strings}
    for gone in ("--issuer", "--idp-host", "--idp-port", "--portal-client"):
        assert gone not in options, gone
    assert "--control-plane-config" in options


def test_a_foreign_issuer_cannot_be_smuggled_in(world):
    """The target is derived from the issuer, so a foreign issuer is a foreign server.

    And the trust bundle must agree with it, which is refused before any network call.
    """
    w = world()
    document = json.loads(w["config"].read_text(encoding="utf-8"))
    document["identity"]["issuer"] = "https://foreign.example/realms/test"
    other = w["tmp"] / "foreign.json"
    other.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(smoke.SmokeRefused, match="trust bundle issuer"):
        run(w, config=other)


@pytest.mark.parametrize(
    ("issuer", "expected"),
    [
        ("http://localhost/realms/test", "must be https"),
        ("https://user:pw@localhost/realms/test", "userinfo"),
        ("https://localhost/realms/test?x=1", "query or fragment"),
        ("https://localhost/realms/test#f", "query or fragment"),
        ("https://localhost/auth/realms/test", "canonical realm path"),
        ("https://localhost/realms/test/extra", "canonical realm path"),
        ("", "missing"),
    ],
)
def test_an_issuer_that_is_not_one_canonical_realm_is_refused(issuer, expected):
    with pytest.raises(smoke.SmokeRefused, match=expected):
        smoke.canonical_issuer(issuer)


def test_a_provider_announcing_another_issuer_fails(world):
    def routes(issuer):
        table = idp_routes(issuer)
        path = next(k for k in table if k.endswith("openid-configuration"))
        status, media, document = table[path]
        table[path] = (status, media, {**document, "issuer": "https://elsewhere.example/realms/x"})
        return table

    w = world(routes=routes)
    observations, _ = run(w)
    assert observations["idpDiscoveryIssuer"]["status"] == "MEASURED_FAIL"
    assert observations["idpDiscoveryIssuer"]["issuerMatches"] is False
    assert "elsewhere.example" not in json.dumps(observations)


def test_an_endpoint_on_another_origin_fails(world):
    def routes(issuer):
        table = idp_routes(issuer)
        path = next(k for k in table if k.endswith("openid-configuration"))
        status, media, document = table[path]
        table[path] = (status, media, {**document, "jwks_uri": "https://elsewhere.example/certs"})
        return table

    w = world(routes=routes)
    observations, _ = run(w)
    assert observations["idpDiscoveryIssuer"]["status"] == "MEASURED_FAIL"
    assert "jwks_uri" in observations["idpDiscoveryIssuer"]["reason"]


def test_keys_outside_the_trust_bundle_fail(world):
    """A provider serving keys the control plane does not trust lines the pieces up
    against each other: every token it issues would be refused."""
    w = world(kid="a-key-nobody-trusts")
    observations, _ = run(w)
    observation = observations["idpJwksMatchesTrustBundle"]
    assert observation["status"] == "MEASURED_FAIL"
    assert "trust bundle" in observation["reason"]
    assert "a-key-nobody-trusts" not in json.dumps(observation)


# --- the certificate authority ----------------------------------------------------


def test_a_chain_from_another_authority_fails(world):
    w = world()
    other = w["tmp"] / "foreign-ca.pem"
    other.write_text(w["foreign"]["pem"], encoding="utf-8")
    observations, _ = run(w, ca_bundle=other, root=w["foreign"]["sha256"])
    assert observations["idpHttpsVerified"]["status"] == "MEASURED_FAIL"
    assert "did not verify" in observations["idpHttpsVerified"]["reason"]


def test_an_unapproved_anchor_is_refused_before_any_request(world):
    w = world()
    both = w["tmp"] / "two-roots.pem"
    both.write_text(w["internal"]["pem"] + w["foreign"]["pem"], encoding="utf-8")
    with pytest.raises(smoke.SmokeRefused, match="unapproved anchor"):
        run(w, ca_bundle=both)


def test_a_leaf_used_as_an_anchor_is_refused(world):
    """basicConstraints is read, so a leaf cannot smuggle itself in as an authority."""
    w = world()
    bundle = w["tmp"] / "leaf-anchor.pem"
    bundle.write_text(w["leaf_cert"].read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(smoke.SmokeRefused, match="certificate authority"):
        run(w, ca_bundle=bundle)


def test_the_bytes_that_are_trusted_are_the_bytes_that_were_hashed(world):
    """cadata, not cafile: the file cannot be swapped between verifying and recording."""
    w = world()
    context = smoke.trusted_context(w["ca_bundle"].read_text(encoding="utf-8"),
                                    {w["internal"]["sha256"]})
    assert smoke.certificate_authorities(context) == [w["internal"]["sha256"]]
    w["ca_bundle"].write_text(w["foreign"]["pem"], encoding="utf-8")
    assert smoke.certificate_authorities(context) == [w["internal"]["sha256"]]


def test_the_anchor_is_loaded_from_the_hashed_bytes_and_never_from_a_path():
    """A path read twice is a path that can change between the two reads.

    The earlier version verified with `cafile` and hashed the file again after every
    network call, so a swap in between would have left the recorded digest describing
    bytes that were never trusted. This is the mutation that test could not see.
    """
    import inspect

    # Judge the call, not the prose: the docstring explains the choice and says both
    # words, so a naive substring check would pass on either implementation.
    calls = [
        line for line in inspect.getsource(smoke.trusted_context).splitlines()
        if "load_verify_locations" in line and not line.lstrip().startswith("#")
    ]
    assert calls, "the context loads no trust anchors at all"
    assert all("cadata=" in line for line in calls), calls
    assert not any("cafile=" in line for line in calls), calls


def test_the_ca_file_is_read_exactly_once_per_run(world, monkeypatch):
    """One read means the trusted bytes and the recorded digest cannot diverge."""
    w = world()
    reads = []
    original = Path.read_text

    def counting_read_text(self, *args, **kwargs):
        if self == w["ca_bundle"]:
            reads.append(1)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", counting_read_text)
    _, facts = run(w)
    assert len(reads) == 1, f"the CA file was read {len(reads)} times"
    assert facts["caBundleSha256"] == smoke.sha256_text(w["internal"]["pem"])


# --- the environment cannot weaken the context ------------------------------------


@pytest.mark.parametrize(
    "variable",
    ["SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE", "PYTHONHTTPSVERIFY", "CURL_CA_BUNDLE"],
)
def test_trust_is_not_taken_from_the_environment(world, monkeypatch, variable):
    w = world()
    other = w["tmp"] / "env-ca.pem"
    other.write_text(w["foreign"]["pem"], encoding="utf-8")
    monkeypatch.setenv(variable, str(other))
    context = smoke.trusted_context(w["ca_bundle"].read_text(encoding="utf-8"),
                                    {w["internal"]["sha256"]})
    assert smoke.certificate_authorities(context) == [w["internal"]["sha256"]]
    assert context.verify_mode is ssl.CERT_REQUIRED
    assert context.check_hostname is True


def test_tls_secrets_are_never_written_to_a_keylog(world, monkeypatch, tmp_path):
    """`ssl.create_default_context()` honours SSLKEYLOGFILE and would export secrets.

    The second assertion is the point: it shows the mutation this guards against --
    going back to the default context -- would actually enable key logging here.
    """
    w = world()
    monkeypatch.setenv("SSLKEYLOGFILE", str(tmp_path / "keys.log"))
    context = smoke.trusted_context(w["ca_bundle"].read_text(encoding="utf-8"),
                                    {w["internal"]["sha256"]})
    assert getattr(context, "keylog_filename", None) is None
    assert getattr(ssl.create_default_context(), "keylog_filename", None) is not None


def test_there_is_no_option_to_skip_verification_or_override_resolution():
    options = {a.option_strings[0] for a in smoke.parser()._actions if a.option_strings}
    assert options & {"--insecure", "--no-verify", "--skip-verify", "-k", "--allow-insecure"} == set()
    assert options & {"--resolve", "--address", "--ip", "--connect-to"} == set()


# --- resolved but unreachable is a failure, not a precondition --------------------


def test_an_unresolved_name_is_blocked_and_records_no_address(monkeypatch, world):
    w = world()

    def refuse(*args, **kwargs):
        raise socket.gaierror("no such host")

    monkeypatch.setattr(smoke.socket, "getaddrinfo", refuse)
    observations, _ = run(w)
    assert observations["idpNameResolves"] == {"status": "BLOCKED_EXTERNAL",
                                              "reason": "hosts-not-applied"}
    smoke.assert_no_addresses(json.dumps(observations["idpNameResolves"]))


def test_a_resolved_name_records_a_count_not_the_address():
    observation, addresses = smoke.observe_name("localhost")
    assert observation["status"] == "MEASURED_PASS"
    assert observation["resolvedAddressCount"] >= 1
    smoke.assert_no_addresses(json.dumps(observation))
    assert addresses


def test_a_resolved_host_that_stops_answering_fails(world):
    """A deployed service that will not answer is a defect, not somebody's homework."""
    w = world()
    w["server"].shutdown()
    w["server"].server_close()
    observations, _ = run(w)
    for name in ("idpHttpsVerified", "portalClientKnown", "passwordGrantRefused",
                 "clientCredentialsRefused"):
        assert observations[name]["status"] == "MEASURED_FAIL", name
    assert smoke.smoke_verdict(observations) == "FAIL"


def test_a_control_plane_that_is_down_fails(world):
    w = world()
    w["control"].shutdown()
    w["control"].server_close()
    observations, _ = run(w)
    assert observations["controlPlaneRejectsBadToken"]["status"] == "MEASURED_FAIL"
    assert smoke.smoke_verdict(observations) == "FAIL"


def test_a_measured_failure_outranks_a_missing_precondition():
    observations = {name: {"status": "MEASURED_PASS"} for name in smoke.REQUIRED}
    observations["idpNameResolves"] = smoke.blocked("hosts-not-applied")
    assert smoke.smoke_verdict(observations) == "BLOCKED_EXTERNAL"
    observations["idpHttpsVerified"] = smoke.failed("the certificate did not verify")
    assert smoke.smoke_verdict(observations) == "FAIL"


def test_an_empty_observation_set_is_not_a_pass():
    """`all()` over nothing is True; the mutation that removes this guard must die."""
    assert smoke.smoke_verdict({}, required=()) == "NOT_OBSERVED"


@pytest.mark.parametrize(
    ("verdict", "code"), [("PASS", 0), ("FAIL", 1), ("BLOCKED_EXTERNAL", 3), ("NOT_OBSERVED", 3)]
)
def test_every_verdict_has_an_exit_code(verdict, code):
    assert smoke.EXIT_BY_VERDICT[verdict] == code


# --- the crash paths --------------------------------------------------------------


def test_a_certificate_verification_failure_produces_an_observation_not_a_crash(world):
    """This path once raised TypeError from a duplicate `reason` keyword, and the run
    ended with no evidence at all -- on the certificate check, of all places."""
    w = world()
    context = smoke.trusted_context(w["foreign"]["pem"], {w["foreign"]["sha256"]})
    host, port = smoke.canonical_issuer(w["issuer"])
    observation, body, headers = smoke.observe_https(
        context, host, port, "/realms/test/.well-known/openid-configuration",
        smoke.Deadline(30.0),
    )
    assert observation["status"] == "MEASURED_FAIL"
    assert observation["reason"] == "the certificate did not verify"
    assert body is None and headers == {}


def test_failed_never_raises_on_a_duplicate_reason():
    observation = smoke.failed("the real reason", reason="a duplicate", extra=1)
    assert observation["reason"] == "the real reason"
    assert observation["extra"] == 1


def test_a_plain_socket_where_tls_is_expected_fails_without_crashing(world):
    w = world()
    plain = serve_plain({"/realms/test/.well-known/openid-configuration":
                         (200, "application/json", {"issuer": w["issuer"]})})
    try:
        context = smoke.trusted_context(w["ca_bundle"].read_text(encoding="utf-8"),
                                        {w["internal"]["sha256"]})
        observation, _, _ = smoke.observe_https(
            context, "localhost", plain.server_address[1],
            "/realms/test/.well-known/openid-configuration", smoke.Deadline(30.0),
        )
        assert observation["status"] == "MEASURED_FAIL"
    finally:
        plain.shutdown()
        plain.server_close()


def test_an_expired_deadline_stops_the_run(world):
    """The deadline ends the run rather than being absorbed as more failures.

    If DeadlineExceeded were a SmokeRefused subclass every observation would catch it,
    and a run that simply ran out of time would blame the deployment.
    """
    w = world()
    assert not issubclass(smoke.DeadlineExceeded, smoke.SmokeRefused)
    with pytest.raises(smoke.DeadlineExceeded, match="deadline"):
        smoke.run(args_for(w), smoke.Deadline(0.0), dt.datetime.now(dt.timezone.utc))


def test_an_oversized_response_is_refused_not_truncated():
    """Silently cutting a response off would turn a wrong answer into a short one."""
    payload = b"x" * (smoke.MAX_BODY_BYTES + 10)
    position = {"at": 0}

    def receive(size):
        start = position["at"]
        position["at"] += size
        return payload[start : start + size]

    with pytest.raises(smoke.Oversized, match="exceeded"):
        smoke.read_bounded(receive)


# --- the client id, and what a refusal has to be ----------------------------------


def test_an_unknown_client_is_its_own_finding_not_a_locked_door(world):
    """`invalid_client` means the client id is unknown. Accepting it as a disabled grant
    would let a typo read as two locked doors."""
    assert "invalid_client" not in smoke.GRANT_DISABLED_ERRORS
    w = world(token_error="invalid_client")
    observations, _ = run(w)
    assert observations["portalClientKnown"]["status"] == "MEASURED_FAIL"
    assert observations["passwordGrantRefused"]["status"] == "MEASURED_FAIL"
    assert observations["clientCredentialsRefused"]["status"] == "MEASURED_FAIL"


def test_a_refusal_for_bad_credentials_means_the_grant_is_enabled(world):
    """invalid_grant is the wrong refusal: it means the client MAY use this grant."""
    w = world(token_error="invalid_grant")
    observations, _ = run(w)
    observation = observations["passwordGrantRefused"]
    assert observation["status"] == "MEASURED_FAIL"
    assert "not as a disabled grant" in observation["reason"]


def test_a_granted_token_is_a_failure(world):
    def routes(issuer):
        table = idp_routes(issuer)
        table[next(k for k in table if k.endswith("/token"))] = (
            200, "application/json", {"access_token": "granted"}
        )
        return table

    w = world(routes=routes)
    observations, _ = run(w)
    assert observations["passwordGrantRefused"]["status"] == "MEASURED_FAIL"
    assert "was granted" in observations["passwordGrantRefused"]["reason"]


def test_the_probe_account_cannot_exist():
    assert "nonexistent" in smoke.SYNTHETIC_ACCOUNT
    assert smoke.SYNTHETIC_ACCOUNT not in {"sv.operator", "sv.viewer"}


# --- only the canonical control plane's refusal counts ----------------------------


@pytest.mark.parametrize(
    ("label", "session", "expected"),
    [
        ("a bare 401 from any process on loopback",
         (401, "application/json", {}), "canonical problem+json"),
        ("problem+json with the wrong shape",
         (401, "application/problem+json", {"code": "AUTH-0050"}),
         "canonical ProblemDetails shape"),
        ("problem+json with another code",
         (401, "application/problem+json", {**CANONICAL_PROBLEM, "code": "AUTH-0001"}),
         "another code"),
        ("a 503 because identity trust is unconfigured",
         (503, "application/problem+json", {**CANONICAL_PROBLEM, "status": 503}),
         "identity trust"),
        ("a 200 that lets the caller in",
         (200, "application/json", {"subjectId": "x"}), "did not answer 401"),
    ],
)
def test_a_refusal_that_is_not_the_canonical_one_fails(world, label, session, expected):
    w = world(cp_routes={"/v1/session": session, "/readyz": (200, "application/json", {})})
    observations, _ = run(w)
    observation = observations["controlPlaneRejectsBadToken"]
    assert observation["status"] == "MEASURED_FAIL", label
    assert expected in observation["reason"], (label, observation)


def test_the_canonical_refusal_passes(world):
    w = world()
    observations, _ = run(w)
    for name in ("controlPlaneRejectsBadToken", "controlPlaneRejectsMissingToken"):
        assert observations[name]["status"] == "MEASURED_PASS"
        assert observations[name]["problemCode"] == "AUTH-0050"
        assert observations[name]["canonicalShape"] is True


def test_the_bad_token_reaches_signature_verification(world):
    """`not.a.valid.token` is refused while parsing the header, so it never exercises
    the issuer, audience, key-id or signature path at all."""
    w = world()
    config = smoke.read_control_plane_configuration(w["config"])
    token = smoke.signed_but_invalid_token(config, dt.datetime.now(dt.timezone.utc))
    header, claims, signature = token.split(".")

    def decode(segment):
        return json.loads(base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4)))

    assert decode(header) == {"alg": "RS256", "typ": "at+jwt", "kid": TRUSTED_KID}
    body = decode(claims)
    assert body["iss"] == w["issuer"]
    assert body["aud"] == "sv-api"
    assert body["client_id"] == "sv-portal"
    assert set(body) >= {"iss", "aud", "sub", "iat", "exp", "jti", "client_id", "scope"}
    assert 0 < body["exp"] - body["iat"] <= 3600
    assert len(signature) > 100


# --- loopback, including IPv6 -----------------------------------------------------


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1", "[::1]", "127.1.2.3"])
def test_loopback_is_recognised_in_both_families(host):
    assert smoke.loopback_host(host)


@pytest.mark.parametrize("url", ["http://127.0.0.1:8080", "http://[::1]:8080",
                                 "http://localhost:8080"])
def test_a_loopback_url_is_labelled_loopback(url):
    assert smoke.control_plane_label(url) == "loopback"


@pytest.mark.parametrize("url", ["http://10.0.0.5:8080", "http://192.168.1.2:8080",
                                 "http://cp.sv.lan:8080"])
def test_a_non_loopback_control_plane_url_is_refused(url):
    assert smoke.control_plane_label(url) == "non-loopback"
    with pytest.raises(smoke.SmokeRefused, match="loopback"):
        smoke.plain_request(url, "/v1/session", smoke.Deadline(5.0))


# --- the report carries no address, token, key or credential ----------------------


@pytest.mark.parametrize(
    "value",
    ["192.168.45.143", "10.0.0.1", "127.0.0.1", "fe80::1234:5678", "::1",
     "2001:0db8:0000:0000:0000:ff00:0042:8329"],
)
def test_an_address_in_the_output_is_refused(value):
    with pytest.raises(smoke.SmokeRefused, match="address-like"):
        smoke.assert_no_addresses(json.dumps({"x": value}))


@pytest.mark.parametrize(
    "value",
    ["2026-09-30T00:14:45Z", "2026-09-30T09:10:10+09:00", "2026-12-28",
     "ae8816d9369e5861cd6ac6b9a4269fae617855bb3adb4cb7088649ba5466bd93",
     "idp.sv.lan", "https://idp.sv.lan/realms/saintvision"],
)
def test_the_guard_is_silent_on_what_the_report_legitimately_carries(value):
    smoke.assert_publishable(json.dumps({"x": value}))


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Bearer eyJhbGciOiJSUzI1NiJ9.e30.sig", "bearer token"),
        ("eyJhbGciOiJSUzI1NiIsInR5cCI6ImF0K2p3dCJ9", "JWT"),
        ("-----BEGIN PRIVATE KEY-----", "-----BEGIN"),
        ("https://user:supersecret@idp.sv.lan/realms/x", "userinfo"),
        ("Authorization: Bearer x", "Authorization:"),
    ],
)
def test_a_credential_in_the_output_is_refused(value, expected):
    with pytest.raises(smoke.SmokeRefused, match=expected.replace("-", "-")):
        smoke.assert_no_credentials(json.dumps({"x": value}))


def test_the_whole_report_is_checked_not_only_the_json(world):
    """JSON, Markdown and the stdout summary all go through the same guard."""
    w = world()
    observations, facts = run(w)
    evidence = {
        "schemaVersion": smoke.SCHEMA_VERSION,
        "codeSha": "0" * 40,
        "collectorSha256": "a" * 64,
        "criteria": dict(smoke.CRITERIA),
        "provenance": {"workingTreeClean": True, "contentClean": True},
        "source": {
            "observedAt": "2026-09-30T00:00:00Z",
            "runEnvironment": "operator-workstation",
            "controlPlaneHost": "loopback",
            "controlPlanePort": 8080,
            "verificationDisabled": False,
            "resolutionOverridden": False,
            "allowedRootSha256": [w["internal"]["sha256"]],
            **facts,
        },
        "observations": observations,
        "verdict": smoke.smoke_verdict(observations),
        "acceptanceClaim": smoke.smoke_verdict(observations) == "PASS",
    }
    # The issuer here is https://localhost:PORT/..., which carries a loopback name but
    # no address, so the guard must be satisfied by the real thing.
    for text in (json.dumps(evidence, sort_keys=True), smoke.render_markdown(evidence),
                 json.dumps({"verdict": evidence["verdict"]})):
        smoke.assert_publishable(text)
    smoke.validate_evidence(evidence)


# --- the verdict cannot be asserted by hand ---------------------------------------


def passing_evidence(w, facts):
    verdict = "PASS"
    return {
        "schemaVersion": smoke.SCHEMA_VERSION,
        "codeSha": "0" * 40,
        "collectorSha256": "a" * 64,
        "criteria": dict(smoke.CRITERIA),
        "provenance": {"workingTreeClean": True, "contentClean": True},
        "source": {
            "observedAt": "2026-09-30T00:00:00Z",
            "runEnvironment": "operator-workstation",
            "controlPlaneHost": "loopback",
            "controlPlanePort": 8080,
            "verificationDisabled": False,
            "resolutionOverridden": False,
            "allowedRootSha256": [w["internal"]["sha256"]],
            **facts,
        },
        "observations": {name: {"status": "MEASURED_PASS"} for name in smoke.REQUIRED},
        "verdict": verdict,
        "acceptanceClaim": True,
    }


@pytest.fixture
def evidence(world):
    w = world()
    config = smoke.read_control_plane_configuration(w["config"])
    facts = {
        "issuer": config["issuer"],
        "controlPlaneConfigSha256": config["configSha256"],
        "trustBundleSha256": config["bundleSha256"],
        "caBundleSha256": smoke.sha256_text(w["ca_bundle"].read_text(encoding="utf-8")),
        "allowedRootSha256": [w["internal"]["sha256"]],
        "clientIdSha256": smoke.sha256_text(config["clientId"]),
        "keyLoggingDisabled": True,
        "readyz": {"status": "RECORDED_ONLY", "readyzHttpStatus": 200},
    }
    return w, passing_evidence(w, facts)


def test_the_shape_this_collector_writes_is_accepted(evidence):
    _, document = evidence
    smoke.validate_evidence(document)


@pytest.mark.parametrize("name", smoke.REQUIRED)
def test_a_single_blocked_observation_cannot_be_carried_by_a_pass(evidence, name):
    _, document = evidence
    document["observations"][name] = smoke.blocked("something external")
    with pytest.raises(ValueError, match="verdict"):
        smoke.validate_evidence(document)


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("verificationDisabled", True, "verification is never disabled"),
        ("resolutionOverridden", True, "resolution is never overridden"),
        ("keyLoggingDisabled", False, "key logging"),
        ("caBundleSha256", "not-a-hash", "caBundleSha256"),
        ("controlPlaneConfigSha256", "not-a-hash", "controlPlaneConfigSha256"),
        ("trustBundleSha256", "not-a-hash", "trustBundleSha256"),
        ("runEnvironment", "somewhere", "runEnvironment"),
        ("allowedRootSha256", [], "trust anchors"),
    ],
)
def test_a_weakened_claim_is_refused(evidence, field, value, expected):
    _, document = evidence
    document["source"][field] = value
    with pytest.raises(ValueError, match=expected):
        smoke.validate_evidence(document)


def test_evidence_from_a_dirty_tree_is_refused(evidence):
    _, document = evidence
    for field in ("workingTreeClean", "contentClean"):
        copy = json.loads(json.dumps(document))
        copy["provenance"][field] = False
        with pytest.raises(ValueError, match="clean"):
            smoke.validate_evidence(copy)


def test_an_unrecognised_status_is_refused(evidence):
    _, document = evidence
    document["observations"]["idpNameResolves"] = {"status": "PROBABLY_FINE"}
    with pytest.raises(ValueError, match="recognised status"):
        smoke.validate_evidence(document)


def test_the_rendered_report_names_every_observation(evidence):
    _, document = evidence
    rendered = smoke.render_markdown(document)
    for name in smoke.REQUIRED:
        assert f"`{name}`" in rendered
    assert "trust anchor, not a pin" in rendered
    assert "taken from the control plane" in rendered
