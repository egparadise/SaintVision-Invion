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
import getpass
import hashlib
import http.server
import json
import os
import socket
import ssl
import sys
import tempfile
import threading
from pathlib import Path
from urllib.parse import urlsplit

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
    #: Every POST form this server was asked, so a test can pin which request a probe made
    #: rather than trusting the observation's own account of it.
    received: list

    def _answer(self):
        entry = self.routes.get(self.path.split("?")[0])
        length = int(self.headers.get("Content-Length") or 0)
        form = self.rfile.read(length).decode() if length else ""
        if form:
            getattr(type(self), "received", []).append(form)
        if entry is None:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if callable(entry):
            entry = entry(form)
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
    handler = type("TlsHandler", (Responder,), {"routes": dict(routes), "received": []})
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(str(cert_path), str(key_path))
    server.socket = context.wrap_socket(server.socket, server_side=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def serve_plain(routes):
    handler = type("PlainHandler", (Responder,), {"routes": dict(routes), "received": []})
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def b64uint(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def rsa_jwk(kid: str = TRUSTED_KID, *, bits: int = 2048, **overrides) -> dict:
    """A JWK `inv.identity.AccessTokens._keys()` accepts, unless an override breaks it.

    The fixture used `"n": "x"`, which is not an RSA modulus. Every bundle in this file
    was therefore one the product would refuse, and the tool's own weaker shape check was
    the only thing judging it -- which is the finding this round closes. A real key is
    generated once; the size-bound cases use a crafted odd modulus of the wrong length,
    since generating an 8192-bit key to be rejected is a waste of a test's time.
    """
    key = {"kty": "RSA", "alg": "RS256", "use": "sig", "kid": kid,
           "n": _MODULI[bits], "e": "AQAB"}
    key.update(overrides)
    return key


def _generated_modulus() -> str:
    from cryptography.hazmat.primitives.asymmetric import rsa

    return b64uint(rsa.generate_private_key(public_exponent=65537,
                                            key_size=2048).public_key().public_numbers().n)


#: 2048 is real; the others are odd integers of the wrong bit length, which construct as
#: RSA public keys and are refused by the product's 2048..4096 bound.
_MODULI = {
    2048: _generated_modulus(),
    1024: b64uint((1 << 1023) | 1),
    8192: b64uint((1 << 8191) | 1),
}

#: The modulus and exponent are compared, not only the key id, so the bundle and the
#: published key set have to agree on the key itself.
SIGNING_KEY = rsa_jwk()
TRUSTED_MODULUS = SIGNING_KEY["n"]


def token_answer(by_grant, default_status, default_error, default_body):
    """One token endpoint that answers by grant type.

    The two probes ask different grants on purpose now, and a real provider answers them
    differently: a public client is refused the password grant with `unauthorized_client`
    after being found, and cannot authenticate as a client for client-credentials at all.
    """
    def answer(form):
        from urllib.parse import parse_qs

        grant = (parse_qs(form).get("grant_type") or [""])[0]
        if grant in by_grant:
            status, error = by_grant[grant]
            return status, "application/json", {"error": error}
        return (default_status, "application/json",
                default_body if default_body is not None else {"error": default_error})

    return answer


def idp_routes(issuer: str, *, kid: str = TRUSTED_KID, token_error: str = "unauthorized_client",
               jwks_keys=None, token_status: int = 400, token_body=None,
               discovery_issuer: str | None = None, token_by_grant=None):
    base = "/realms/" + issuer.split("/realms/")[1]
    return {
        f"{base}/.well-known/openid-configuration": (
            200,
            "application/json",
            {
                "issuer": discovery_issuer if discovery_issuer is not None else issuer,
                "jwks_uri": f"{issuer}/protocol/openid-connect/certs",
                "token_endpoint": f"{issuer}/protocol/openid-connect/token",
                "authorization_endpoint": f"{issuer}/protocol/openid-connect/auth",
                "code_challenge_methods_supported": ["S256"],
            },
        ),
        f"{base}/protocol/openid-connect/certs": (
            200,
            "application/json",
            {"keys": jwks_keys if jwks_keys is not None else [{**SIGNING_KEY, "kid": kid}]},
        ),
        f"{base}/protocol/openid-connect/token": (
            token_answer(token_by_grant, token_status, token_error, token_body)
            if token_by_grant
            else (
                token_status,
                "application/json",
                token_body if token_body is not None else {"error": token_error},
            )
        ),
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

    def start(*, routes=None, kid=TRUSTED_KID, token_error="unauthorized_client", cp_routes=None,
              bundle_keys=None, bundle_extra=None, bundle_expires_at=None,
              expires_in=3 * 86_400, jwks_keys=None,
              token_status=400, token_body=None, discovery_issuer=None, relative_jwks=False,
              token_by_grant=None, tenant_id="00000000-0000-4000-8000-000000000001"):
        server = serve_tls({}, cert, key)
        holder["servers"].append(server)
        port = server.server_address[1]
        issuer = f"https://localhost:{port}/realms/test"
        table = routes(issuer) if callable(routes) else idp_routes(
            issuer, kid=kid, token_error=token_error, jwks_keys=jwks_keys,
            token_status=token_status, token_body=token_body,
            discovery_issuer=discovery_issuer, token_by_grant=token_by_grant,
        )
        server.RequestHandlerClass.routes = dict(table)
        control = serve_plain(cp_routes if cp_routes is not None else DEFAULT_CP_ROUTES)
        holder["servers"].append(control)
        bundle = tmp_path / "trust-bundle.json"
        now = int(dt.datetime.now(dt.timezone.utc).timestamp())
        document = {
            "issuer": issuer,
            "expiresAt": (now + expires_in) if bundle_expires_at is None else bundle_expires_at,
            "keys": bundle_keys if bundle_keys is not None else [dict(SIGNING_KEY)],
        }
        document.update(bundle_extra or {})
        bundle.write_text(json.dumps(document), encoding="utf-8")
        config = tmp_path / "api.json"
        config.write_text(
            json.dumps({"identity": {
                "tenant_id": tenant_id,
                "issuer": issuer,
                "audience": "sv-api",
                "client_ids": ["sv-portal"],
                "jwks_file": bundle.name if relative_jwks else str(bundle),
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


def test_the_whole_path_is_measured_against_a_real_provider(world):
    """Everything observable passes, and the one thing that is not observable says so.

    This used to assert a clean PASS. It cannot: nothing the control plane exposes ties
    the configuration file this report hashes to the process that is listening, so
    `controlPlaneConfigurationBound` is RECORDED_ONLY/NOT_BOUND and the run is
    NOT_OBSERVED. The gap is the finding, and it stays in the verdict rather than being
    absorbed by a pass.
    """
    w = world()
    observations, facts = run(w)
    binding = observations.pop("controlPlaneConfigurationBound")
    failures = {n: o for n, o in observations.items() if o["status"] != "MEASURED_PASS"}
    assert failures == {}, failures
    assert binding["status"] == "RECORDED_ONLY"
    assert binding["binding"] == "NOT_BOUND"
    assert binding["identityTrustConfigured"] is True
    assert binding["bindingGap"] == smoke.CONFIGURATION_BINDING_GAP
    observations["controlPlaneConfigurationBound"] = binding
    assert smoke.smoke_verdict(observations) == "NOT_OBSERVED"
    assert facts["issuer"] == w["issuer"]
    assert facts["keyLoggingDisabled"] is True
    assert facts["readyz"] == {"readyzHttpStatus": 200}


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
    assert "not exactly the keys the control plane trusts" in observation["reason"]
    assert observation["rogueKidSha256"] == [smoke.sha256_text("a-key-nobody-trusts")]
    assert observation["unservedTrustedKidSha256"] == [smoke.sha256_text(TRUSTED_KID)]
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
    pem = w["ca_bundle"].read_text(encoding="utf-8")
    assert smoke.certificate_authorities(context, pem) == [w["internal"]["sha256"]]
    w["ca_bundle"].write_text(w["foreign"]["pem"], encoding="utf-8")
    assert smoke.certificate_authorities(context, pem) == [w["internal"]["sha256"]]


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
    pem = w["ca_bundle"].read_text(encoding="utf-8")
    context = smoke.trusted_context(pem, {w["internal"]["sha256"]})
    assert smoke.certificate_authorities(context, pem) == [w["internal"]["sha256"]]
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
    # And it cannot be the deployment under test either: nothing answered readiness.
    assert observations["controlPlaneConfigurationBound"]["status"] == "MEASURED_FAIL"
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


# --- R1: every certificate in the bundle, not every one OpenSSL will list ----------


def self_signed_leaf(common_name: str, host: str) -> str:
    """A certificate that is its own issuer and says basicConstraints CA:FALSE."""
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
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(host)]), critical=False)
        .sign(key, hashes.SHA256())
    )
    return certificate.public_bytes(serialization.Encoding.PEM).decode()


def test_an_approved_root_beside_a_rogue_self_signed_leaf_is_refused(world):
    """The mutation that reads the store's list instead of the bundle has to die here.

    `context.get_ca_certs()` returns only CA certificates. A self-signed certificate with
    basicConstraints CA:FALSE is loaded into the store, anchors itself, and never appears
    on that list: measured as cert_store_stats {'x509': 2, 'x509_ca': 1} with
    get_ca_certs() returning one. So both the CA check and the allowlist used to read a
    list the rogue certificate was not on, and TLS against a server presenting it
    verified. The existing leaf-only test could not see this, because one certificate that
    is not a CA leaves the store with no authorities at all and exits by another branch.
    """
    w = world()
    both = w["tmp"] / "root-plus-rogue-leaf.pem"
    both.write_text(
        w["internal"]["pem"] + self_signed_leaf("rogue leaf", "localhost"), encoding="utf-8"
    )
    with pytest.raises(smoke.SmokeRefused, match="not a certificate authority"):
        run(w, ca_bundle=both)


def test_a_bundle_that_loads_more_than_it_parses_is_refused(world):
    """The count is reconciled, so a certificate loaded past this parse is not silent."""
    w = world()
    pem = w["ca_bundle"].read_text(encoding="utf-8")
    context = smoke.trusted_context(pem, {w["internal"]["sha256"]})
    context.cert_store_stats = lambda: {"x509": 7, "crl": 0, "x509_ca": 7}
    with pytest.raises(smoke.SmokeRefused, match="was not checked"):
        smoke.certificate_authorities(context, pem)


def test_a_store_authority_missing_from_the_checked_bytes_is_refused(world):
    """And the reverse: an authority OpenSSL trusts that these bytes do not contain."""
    w = world()
    pem = w["ca_bundle"].read_text(encoding="utf-8")
    context = smoke.trusted_context(pem, {w["internal"]["sha256"]})
    with pytest.raises(smoke.SmokeRefused, match="the checked bundle does not"):
        smoke.certificate_authorities(context, w["foreign"]["pem"])


# --- Codex 1: the served signing keys are exactly the trusted keys -----------------


def test_a_rogue_key_beside_a_trusted_one_fails(world):
    """An intersection is satisfied by a provider that also holds a key nobody trusts.

    That provider can mint tokens the control plane accepts *and* tokens signed with an
    unaccounted-for key. The old check read the first fact and reported a pass.
    """
    w = world(jwks_keys=[dict(SIGNING_KEY), rsa_jwk("rogue-signing-kid")])
    observations, _ = run(w)
    observation = observations["idpJwksMatchesTrustBundle"]
    assert observation["status"] == "MEASURED_FAIL"
    assert observation["rogueKidSha256"] == [smoke.sha256_text("rogue-signing-kid")]
    assert observation["unservedTrustedKidSha256"] == []
    assert "rogue-signing-kid" not in json.dumps(observation)


def test_a_trusted_key_the_provider_no_longer_serves_fails(world):
    """Drift in the other direction: the bundle outlives the key it names."""
    w = world(bundle_keys=[dict(SIGNING_KEY), rsa_jwk("retired-kid")])
    observations, _ = run(w)
    observation = observations["idpJwksMatchesTrustBundle"]
    assert observation["status"] == "MEASURED_FAIL"
    assert observation["unservedTrustedKidSha256"] == [smoke.sha256_text("retired-kid")]


def test_a_trusted_key_id_with_different_material_fails(world):
    """The substitution a trust bundle exists to prevent: right label, wrong key."""
    w = world(jwks_keys=[{**SIGNING_KEY, "n": b64uint((1 << 2047) | 3)}])
    observations, _ = run(w)
    observation = observations["idpJwksMatchesTrustBundle"]
    assert observation["status"] == "MEASURED_FAIL"
    assert "different key material" in observation["reason"]
    assert observation["substitutedKidSha256"] == [smoke.sha256_text(TRUSTED_KID)]


def test_one_key_id_published_twice_with_different_material_fails(world):
    w = world(jwks_keys=[dict(SIGNING_KEY), {**SIGNING_KEY, "n": b64uint((1 << 2047) | 5)}])
    observations, _ = run(w)
    observation = observations["idpJwksMatchesTrustBundle"]
    assert observation["status"] == "MEASURED_FAIL"
    assert "twice" in observation["reason"]


def test_keys_that_are_not_rs256_signing_keys_are_not_drift(world):
    """Encryption keys are published alongside and cannot sign an accepted token."""
    w = world(jwks_keys=[dict(SIGNING_KEY),
                         {**rsa_jwk("enc-kid"), "alg": "RSA-OAEP", "use": "enc"}])
    observations, _ = run(w)
    observation = observations["idpJwksMatchesTrustBundle"]
    assert observation["status"] == "MEASURED_PASS"
    assert observation["keyCount"] == 2
    assert observation["signingKeyCount"] == 1
    assert observation["keySetsIdentical"] is True


# --- Codex 2 and R4: the binding refutes, and never confirms -----------------------


def test_a_control_plane_that_is_not_ready_is_not_serving_this_configuration(world):
    """/v1/session answering 401 does not make an instance ready.

    A control plane whose readiness is 503 has no identity trust, or a trust bundle its
    own verifier will not load. Either way it is not running the configuration this
    report hashes, and a canonical 401 from it is not evidence that it is.
    """
    w = world(cp_routes={
        "/v1/session": (401, "application/problem+json", CANONICAL_PROBLEM),
        "/readyz": (503, "application/json",
                    {"status": "not_ready", "reason": "identity-and-database-configuration-pending"}),
    })
    observations, facts = run(w)
    binding = observations["controlPlaneConfigurationBound"]
    assert binding["status"] == "MEASURED_FAIL"
    assert binding["httpStatus"] == 503
    assert binding["readyzReason"] == "identity-and-database-configuration-pending"
    assert observations["controlPlaneRejectsBadToken"]["status"] == "MEASURED_PASS"
    assert smoke.smoke_verdict(observations) == "FAIL"
    assert facts["readyz"]["readyzHttpStatus"] == 503
    assert facts["readyz"]["readyzReason"] == "identity-and-database-configuration-pending"


def test_a_readiness_failure_with_a_problem_code_and_no_reason_records_the_code(world):
    """A 503 raised inside /readyz answers problem+json with a code and no reason field.

    Reading only `reason` recorded that as "unnamed", which drops the one field saying what
    went wrong.
    """
    w = world(cp_routes={
        "/v1/session": (401, "application/problem+json", CANONICAL_PROBLEM),
        "/readyz": (503, "application/problem+json", {
            "type": "about:blank", "title": "Configuration observation unavailable",
            "status": 503, "code": "SYS-0001", "category": "SYS",
            "detail": "Configuration observation unavailable", "retryable": True,
            "traceId": "0" * 32, "causeRef": None, "evidenceId": None,
        }),
    })
    observations, facts = run(w)
    binding = observations["controlPlaneConfigurationBound"]
    assert binding["status"] == "MEASURED_FAIL"
    assert binding["readyzProblemCode"] == "SYS-0001"
    assert binding["readyzProblemType"] == "about:blank"
    assert binding.get("readyzReason") != "unnamed"
    assert facts["readyz"]["readyzProblemCode"] == "SYS-0001"


def test_a_readiness_body_that_names_nothing_is_recorded_as_unnamed(world):
    w = world(cp_routes={
        "/v1/session": (401, "application/problem+json", CANONICAL_PROBLEM),
        "/readyz": (503, "text/plain", b"service unavailable"),
    })
    observations, _ = run(w)
    binding = observations["controlPlaneConfigurationBound"]
    assert binding["status"] == "MEASURED_FAIL"
    assert binding["readyzReason"] == "unnamed"


@pytest.mark.parametrize(
    ("overrides", "defect"),
    [
        ({"expires_in": -60}, "bundle-has-expired"),
        ({"expires_in": 8 * 86_400}, "bundle-window-exceeds-the-seven-day-ceiling"),
        ({"bundle_extra": {"note": "extra"}},
         "bundle-keys-are-not-exactly-issuer-expiresAt-keys"),
        ({"bundle_expires_at": "later"}, "expiresAt-is-not-an-integer"),
    ],
)
def test_a_ready_control_plane_with_an_unloadable_bundle_is_running_another_file(
    world, overrides, defect
):
    """The one positive discrimination available, and R7's unchecked window.

    /readyz calls tokens._keys(), which enforces the bundle's shape and its seven-day
    window. So a control plane that reports ready while the configured bundle is one that
    verifier would refuse has demonstrably loaded a different file.
    """
    w = world(**overrides)
    observations, _ = run(w)
    binding = observations["controlPlaneConfigurationBound"]
    assert binding["status"] == "MEASURED_FAIL"
    # The readable name, and beside it the verdict of the class that loads the bundle.
    assert defect in binding["bundleDefects"]
    assert any("refuses-this-configuration" in entry for entry in binding["bundleDefects"])
    assert "loaded some other bundle" in binding["reason"]
    assert smoke.smoke_verdict(observations) == "FAIL"


def test_the_binding_is_never_reported_as_a_pass():
    """Judge the code, not the prose: no branch of it may reach MEASURED_PASS.

    Hashing a file proves what the file says. The earlier version called passed() on that
    alone, so the observation asserted a deployment fact from a file fact. The mutation
    that reinstates it is a one-word edit, so it is pinned structurally.
    """
    import inspect

    # Outside the docstring and outside comments: the prose below explains the mistake
    # this replaced and so names the very thing being forbidden.
    parts = inspect.getsource(smoke.observe_configuration_bound).split('"""')
    code = "\n".join([parts[0]] + parts[2:])
    statements = [line for line in code.splitlines() if not line.strip().startswith("#")]
    assert "MEASURED_PASS" in inspect.getsource(smoke.observe_configuration_bound)
    assert not [line for line in statements if "passed(" in line]
    assert not [line for line in statements if "MEASURED_PASS" in line]


def test_the_binding_gap_names_what_the_product_would_have_to_expose():
    gap = smoke.CONFIGURATION_BINDING_GAP
    for phrase in ("no configuration digest", "AUTH-0050", "WWW-Authenticate"):
        assert phrase in gap
    assert smoke.CRITERIA["controlPlaneConfigurationBound"].count("NOT_BOUND") == 1


# --- Codex 3: a named OAuth error is only evidence with the provider's status ------


@pytest.mark.parametrize("status", [500, 502, 503, 404, 302])
def test_a_grant_error_from_a_status_no_token_endpoint_uses_fails(world, status):
    """(503, "unauthorized_client") used to read as a locked door.

    A maintenance page, a proxy or a sibling service can answer with that body. A service
    that is down is not a grant that is off.
    """
    w = world(token_status=status, token_error="unauthorized_client")
    observations, _ = run(w)
    for name in ("passwordGrantRefused", "clientCredentialsRefused", "portalClientKnown"):
        observation = observations[name]
        assert observation["status"] == "MEASURED_FAIL", name
        assert observation["httpStatus"] == status
    assert smoke.smoke_verdict(observations) == "FAIL"


def test_a_refusal_with_no_named_oauth_error_is_not_client_knowledge(world):
    """A 400 with no error object is not the token endpoint's own refusal."""
    w = world(token_status=400, token_body={})
    observations, _ = run(w)
    known = observations["portalClientKnown"]
    assert known["status"] == "MEASURED_FAIL"
    assert "does not show it resolved the configured client" in known["reason"]
    assert known["oauthError"] == "unnamed"
    assert known["answeredBeforeClientLookup"] is False


def test_only_a_400_refusal_speaks_about_the_grant_or_the_client(world):
    """RFC 6749 section 5.2 puts a grant the client may not use at 400.

    401 is for a client the endpoint could not authenticate -- a confidential client that
    sent no secret answers 401 -- so `unauthorized_client` at 401 is an authentication
    outcome, not a locked door. This case asserted the opposite: it required all three
    observations to PASS at 401 as well as 400.
    """
    w = world(token_status=400, token_error="unauthorized_client")
    observations, _ = run(w)
    for name in ("passwordGrantRefused", "clientCredentialsRefused", "portalClientKnown"):
        assert observations[name]["status"] == "MEASURED_PASS", name


def test_the_same_error_at_401_is_not_evidence_about_the_grant_or_the_client(world):
    w = world(token_status=401, token_error="unauthorized_client")
    observations, _ = run(w)
    known = observations["portalClientKnown"]
    assert known["status"] == "MEASURED_FAIL"
    assert "client-authentication outcome" in known["reason"]
    for name in ("passwordGrantRefused", "clientCredentialsRefused"):
        assert observations[name]["status"] == "MEASURED_FAIL", name
        assert "client-authentication outcome" in observations[name]["reason"], name
    assert smoke.smoke_verdict(observations) == "FAIL"


def test_the_status_that_carries_grant_evidence_is_pinned():
    assert smoke.GRANT_EVIDENCE_STATUS == 400
    assert smoke.GRANT_EVIDENCE_STATUS in smoke.TOKEN_REFUSAL_STATUSES


# --- Codex 4 and R6: the whole body, parsed strictly ------------------------------


@pytest.mark.parametrize(
    "body",
    [
        b'<html><script>var x = {"issuer": "https://idp.sv.lan/realms/sv"}</script></html>',
        b'{"issuer": "https://idp.sv.lan/realms/sv"} and then some trailing bytes',
        b'{"a": 1}{"b": 2}',
        b'[{"a": 1}]',
        b'"a string"',
        b"",
        b"\xff\xfe not utf-8 at all",
    ],
)
def test_json_must_be_the_whole_body(body):
    """Slicing from the first brace to the last read an object out of anything."""
    with pytest.raises(smoke.SmokeRefused):
        smoke.as_json(body)


def test_a_json_object_with_surrounding_whitespace_is_still_an_object():
    assert smoke.as_json(b'  {"a": 1}\n') == {"a": 1}


def test_a_page_that_merely_contains_json_is_not_discovery(world):
    def routes(issuer):
        table = dict(idp_routes(issuer))
        base = "/realms/" + issuer.split("/realms/")[1]
        table[f"{base}/.well-known/openid-configuration"] = (
            200,
            "application/json",
            b'<html><body>{"issuer": "' + issuer.encode() + b'"}</body></html>',
        )
        return table

    w = world(routes=routes)
    observations, _ = run(w)
    assert observations["idpDiscoveryIssuer"]["status"] == "MEASURED_FAIL"
    assert "not JSON" in observations["idpDiscoveryIssuer"]["reason"]


# --- R2: nine passes and a gap is not a pass --------------------------------------


def test_nine_passes_and_one_gap_is_not_a_pass():
    """`if statuses and all(...)` mutated to `if statuses` survives every earlier test."""
    observations = {name: {"status": "MEASURED_PASS"} for name in smoke.REQUIRED}
    observations["controlPlaneConfigurationBound"] = {"status": "RECORDED_ONLY"}
    assert smoke.smoke_verdict(observations) == "NOT_OBSERVED"
    observations["controlPlaneConfigurationBound"] = {"status": "NOT_OBSERVED"}
    assert smoke.smoke_verdict(observations) == "NOT_OBSERVED"


def test_a_missing_required_observation_is_not_a_pass():
    observations = {name: {"status": "MEASURED_PASS"} for name in smoke.REQUIRED}
    del observations["idpDiscoveryIssuer"]
    assert smoke.smoke_verdict(observations) == "NOT_OBSERVED"


# --- R3: the same realm path on another host --------------------------------------


def test_a_provider_announcing_the_same_realm_path_on_another_host_fails(world):
    """The earlier case differed in path too, so it could not isolate the host."""
    w = world(discovery_issuer="https://elsewhere.invalid:9443/realms/test")
    observations, _ = run(w)
    observation = observations["idpDiscoveryIssuer"]
    assert observation["status"] == "MEASURED_FAIL"
    assert observation["issuerMatches"] is False
    assert "elsewhere.invalid" not in json.dumps(observation)


# --- R7: the trust bundle has to be the same file for both readers ----------------


def test_a_relative_jwks_file_is_refused(world):
    """Read against the reader's own directory, it is not necessarily the same file."""
    w = world(relative_jwks=True)
    with pytest.raises(smoke.SmokeRefused, match="absolute path"):
        run(w)


# --- Codex 5: the bytes printed are the bytes checked -----------------------------


def test_stdout_carries_no_path_and_is_what_was_checked(world, capsys, monkeypatch):
    """--out-dir is the caller's input; an absolute path on this host names an account.

    The earlier version checked {"verdict": ...} and printed a larger object holding both
    written paths, so the guard did not cover the output at all.
    """
    w = world()
    monkeypatch.setattr(
        smoke, "collect_provenance_at_root",
        lambda executor: {"commit_sha": "0" * 40, "branch": "test",
                          "working_tree_clean_status": True, "content_clean_diff": True,
                          "executor": executor},
    )
    out = w["tmp"] / "evidence"
    exit_code = smoke.main([
        "--control-plane-config", str(w["config"]),
        "--ca-bundle", str(w["ca_bundle"]),
        "--allowed-root-sha256", w["internal"]["sha256"],
        "--control-plane-url", w["cp_url"],
        "--run-environment", "operator-workstation",
        "--out-dir", str(out),
        "--label", "smoke-stdout-probe",
    ])
    printed = capsys.readouterr().out.strip()
    assert exit_code == smoke.EXIT_BY_VERDICT["NOT_OBSERVED"]
    summary = json.loads(printed)
    assert summary["verdict"] == "NOT_OBSERVED"
    assert summary["json"] == "smoke-stdout-probe.json"
    assert summary["markdown"] == "smoke-stdout-probe.md"
    # `or True` made this line unfailable, and the account name below was hard-coded,
    # which committed this machine's account into the repository -- the very thing the
    # check exists to keep out of the output. Both fixed: a real assertion, and the
    # account read from the running environment.
    assert not {"/", "\\"} & set(printed), "a separator in the output means a path"
    # A very short account name ("ab") would appear inside ordinary words and make this a
    # false alarm, so only names long enough to be distinctive are searched for. The
    # separator assertion above is what actually rules a path out, whatever it is called.
    account = getpass.getuser()
    fragments = [str(out), str(w["tmp"]), "Users"]
    fragments += [name for name in (account, Path.home().name) if len(name) >= 4]
    for fragment in fragments:
        if fragment:
            assert fragment not in printed, fragment
    smoke.assert_publishable(printed)


# --- Codex r3 F1: an error answered before the client lookup proves nothing --------


@pytest.mark.parametrize("error", sorted(smoke.CLIENT_BLIND_ERRORS))
def test_an_error_answered_before_the_client_lookup_is_not_client_knowledge(world, error):
    """One typo in the client id used to make all three observations pass.

    `unsupported_grant_type` and `invalid_request` come out of grant-type and request
    validation, before any client is resolved, so a client id that does not exist draws
    exactly the same answer as a known client whose grant is off.
    """
    w = world(token_status=400, token_error=error)
    observations, _ = run(w)
    known = observations["portalClientKnown"]
    assert known["status"] == "MEASURED_FAIL"
    assert "does not show it resolved the configured client" in known["reason"]
    assert known["answeredBeforeClientLookup"] is True
    for name in ("passwordGrantRefused", "clientCredentialsRefused"):
        assert observations[name]["status"] == "MEASURED_FAIL", name
        assert "not as a disabled grant" in observations[name]["reason"]
    assert smoke.smoke_verdict(observations) == "FAIL"


def test_the_two_error_sets_are_pinned_and_say_different_things():
    """Pinned as sets, because widening either again is a one-word edit.

    `invalid_grant` shows the client was resolved -- the provider got as far as checking an
    account -- but it means the client MAY use the grant, so it is not a locked door.
    """
    assert smoke.GRANT_DISABLED_ERRORS == frozenset({"unauthorized_client"})
    assert smoke.CLIENT_RESOLVED_ERRORS == frozenset({"unauthorized_client", "invalid_grant"})
    assert "unsupported_grant_type" not in smoke.GRANT_DISABLED_ERRORS
    assert "unsupported_grant_type" not in smoke.CLIENT_RESOLVED_ERRORS
    assert smoke.GRANT_DISABLED_ERRORS < smoke.CLIENT_RESOLVED_ERRORS
    assert not smoke.CLIENT_BLIND_ERRORS & smoke.CLIENT_RESOLVED_ERRORS


def test_the_client_known_probe_reports_a_granted_token_as_its_own_finding(world):
    def routes(issuer):
        table = dict(idp_routes(issuer))
        base = "/realms/" + issuer.split("/realms/")[1]
        table[f"{base}/protocol/openid-connect/token"] = (
            200, "application/json", {"access_token": "x", "token_type": "Bearer"}
        )
        return table

    w = world(routes=routes)
    observations, _ = run(w)
    assert observations["portalClientKnown"]["status"] == "MEASURED_FAIL"
    assert "says nothing about the client id alone" in observations["portalClientKnown"]["reason"]
    assert observations["clientCredentialsRefused"]["status"] == "MEASURED_FAIL"


# --- Codex r3 F2: the bundle is judged by the class that loads it ------------------


def configuration(tmp_path, *, keys=None, document=None, issuer=None, tenant_id=None):
    """A control-plane configuration on disk, with no server involved."""
    issuer = issuer or "https://idp.example.invalid/realms/sv"
    bundle = tmp_path / "bundle.json"
    now = int(dt.datetime.now(dt.timezone.utc).timestamp())
    bundle.write_text(json.dumps(document if document is not None else {
        "issuer": issuer,
        "expiresAt": now + 3 * 86_400,
        "keys": [dict(SIGNING_KEY)] if keys is None else keys,
    }), encoding="utf-8")
    config = tmp_path / "api.json"
    config.write_text(json.dumps({"identity": {
        "tenant_id": tenant_id or "00000000-0000-4000-8000-000000000001",
        "issuer": issuer,
        "audience": "sv-api",
        "client_ids": ["sv-portal"],
        "jwks_file": str(bundle),
    }}), encoding="utf-8")
    return config


def test_the_shipped_bundle_shape_is_accepted_by_the_product(tmp_path):
    """The baseline: what these tests call valid, AccessTokens also calls valid."""
    config = smoke.read_control_plane_configuration(configuration(tmp_path))
    assert config["bundleDefects"] == []


@pytest.mark.parametrize(
    ("label", "keys"),
    [
        ("an encryption key", [{**SIGNING_KEY, "alg": "RSA-OAEP", "use": "enc"}]),
        ("a signing key with another algorithm", [{**SIGNING_KEY, "alg": "RS512"}]),
        ("a key that is not RSA", [{**SIGNING_KEY, "kty": "EC"}]),
        ("a private key", [{**SIGNING_KEY, "d": "c2VjcmV0"}]),
        ("nine keys", [rsa_jwk(f"kid-{n}") for n in range(9)]),
        ("an RSA key below 2048 bits", [rsa_jwk(bits=1024)]),
        ("an RSA key above 4096 bits", [rsa_jwk(bits=8192)]),
        ("a modulus that is not base64url", [{**SIGNING_KEY, "n": "!!! not base64 !!!"}]),
    ],
)
def test_a_bundle_the_product_verifier_refuses_is_a_defect(tmp_path, label, keys):
    """Each of these passed the tool's own shape check while AccessTokens refuses it.

    The tool used to answer "would the verifier accept this?" with a second, weaker
    implementation. Now it answers with the verifier.
    """
    config = smoke.read_control_plane_configuration(configuration(tmp_path, keys=keys))
    assert config["bundleDefects"], label
    assert any("refuses-this-configuration" in defect or defect.startswith("bundle-")
               for defect in config["bundleDefects"]), config["bundleDefects"]


@pytest.mark.parametrize(
    ("label", "keys", "expected"),
    [
        ("no keys at all", [], "carries no keys"),
        ("a repeated key id", [dict(SIGNING_KEY), dict(SIGNING_KEY)], "repeats a key id"),
        ("a key id that is not a string", [{**SIGNING_KEY, "kid": 7}], "carries no keys"),
    ],
)
def test_a_bundle_with_no_usable_key_id_refuses_the_run(tmp_path, label, keys, expected):
    """These cannot become observations: the probe token needs a trusted key id to name.

    So they refuse (exit 2) rather than reporting a measured failure. That is the honest
    outcome -- the run never gets far enough to measure anything -- and the control plane
    would refuse the same bundle at startup.
    """
    with pytest.raises(smoke.SmokeRefused, match=expected):
        smoke.read_control_plane_configuration(configuration(tmp_path, keys=keys))


def test_the_encryption_key_case_is_the_one_that_used_to_pass(tmp_path):
    """Named on its own because it is the reported example.

    `named_bundle_defects` sees nothing wrong with it: the shape is right, the window is
    right, the count is right. Only the verifier refuses it.
    """
    keys = [{**SIGNING_KEY, "alg": "RSA-OAEP", "use": "enc"}]
    document = {"issuer": "https://idp.example.invalid/realms/sv",
                "expiresAt": int(dt.datetime.now(dt.timezone.utc).timestamp()) + 3 * 86_400,
                "keys": keys}
    assert smoke.named_bundle_defects(document) == []
    config = smoke.read_control_plane_configuration(configuration(tmp_path, keys=keys))
    assert any("refuses-this-configuration" in defect for defect in config["bundleDefects"])


@pytest.mark.parametrize(
    ("label", "document"),
    [
        ("an expired bundle", {"issuer": None, "expiresAt": 1, "keys": None}),
        ("a window past seven days", {"issuer": None, "expiresAt": None, "keys": None}),
        ("an extra top-level key", {"issuer": None, "expiresAt": None, "keys": None,
                                    "note": "extra"}),
    ],
)
def test_the_named_defects_and_the_verifier_agree(tmp_path, label, document):
    """The readable names are a subset of what the verifier enforces, never a superset."""
    issuer = "https://idp.example.invalid/realms/sv"
    now = int(dt.datetime.now(dt.timezone.utc).timestamp())
    filled = {key: value for key, value in document.items()}
    filled["issuer"] = issuer
    if filled["expiresAt"] is None:
        filled["expiresAt"] = now + 8 * 86_400
    if filled["keys"] is None:
        filled["keys"] = [dict(SIGNING_KEY)]
    config = smoke.read_control_plane_configuration(
        configuration(tmp_path, document=filled, issuer=issuer)
    )
    assert config["bundleDefects"], label
    # Whatever the readable name says, the verifier refuses it too.
    assert any("refuses-this-configuration" in defect for defect in config["bundleDefects"])


def test_a_bundle_the_verifier_refuses_makes_a_ready_control_plane_a_failure(world):
    """End to end: the ready instance cannot have loaded a bundle its verifier refuses."""
    w = world(bundle_keys=[{**SIGNING_KEY, "alg": "RSA-OAEP", "use": "enc"}])
    observations, _ = run(w)
    binding = observations["controlPlaneConfigurationBound"]
    assert binding["status"] == "MEASURED_FAIL"
    assert "loaded some other bundle" in binding["reason"]
    assert any("refuses-this-configuration" in defect for defect in binding["bundleDefects"])
    assert smoke.smoke_verdict(observations) == "FAIL"


def test_an_unimportable_verifier_refuses_the_run_instead_of_weakening_the_check(
    tmp_path, monkeypatch
):
    """No fallback. A weaker local copy is the defect this closed, wearing a disguise."""
    def unavailable():
        raise smoke.SmokeRefused("the control plane's own verifier could not be imported")

    monkeypatch.setattr(smoke, "product_verifier", unavailable)
    with pytest.raises(smoke.SmokeRefused, match="could not be imported"):
        smoke.read_control_plane_configuration(configuration(tmp_path))


def test_the_verifier_is_the_control_planes_own_class():
    """Judge the import, not the prose: a local reimplementation would satisfy a name."""
    import inspect

    from inv.identity import AccessTokens

    assert smoke.product_verifier() is AccessTokens
    source = inspect.getsource(smoke.product_verifier)
    assert "from inv.identity import AccessTokens" in source


# --- Codex r3 F3: which control plane on this host --------------------------------


def test_the_input_binding_names_the_control_plane_port(world, monkeypatch):
    """"loopback" is every control plane on this host; the port is which one answered."""
    w = world()
    monkeypatch.setattr(
        smoke, "collect_provenance_at_root",
        lambda executor: {"commit_sha": "0" * 40, "branch": "test",
                          "working_tree_clean_status": True, "content_clean_diff": True,
                          "executor": executor},
    )
    port = urlsplit(w["cp_url"]).port
    out = w["tmp"] / "evidence"
    assert smoke.main([
        "--control-plane-config", str(w["config"]),
        "--ca-bundle", str(w["ca_bundle"]),
        "--allowed-root-sha256", w["internal"]["sha256"],
        "--control-plane-url", w["cp_url"],
        "--run-environment", "operator-workstation",
        "--out-dir", str(out),
        "--label", "smoke-port-binding",
    ]) == smoke.EXIT_BY_VERDICT["NOT_OBSERVED"]
    source = json.loads((out / "smoke-port-binding.json").read_text(encoding="utf-8"))["source"]
    assert source["controlPlanePort"] == port

    def binding(at_port):
        return smoke.input_binding_sha256({
            "controlPlaneConfigSha256": source["controlPlaneConfigSha256"],
            "trustBundleSha256": source["trustBundleSha256"],
            "caBundleSha256": source["caBundleSha256"],
            "allowedRootSha256": source["allowedRootSha256"],
            "controlPlaneUrl": f"loopback:{at_port}",
        })

    # Recomputed from the report's own inputs: the digest it recorded is the one that
    # includes this port, and a neighbouring port would have produced a different one.
    assert source["inputBindingSha256"] == binding(port)
    assert source["inputBindingSha256"] != binding(port + 1)


# --- the probe has to be a request that reaches client resolution -----------------


def test_the_client_known_probe_asks_the_grant_that_reaches_client_resolution(world):
    """Judge the request, not the observation's account of it.

    This asked with `client_credentials`, and a public client cannot authenticate as a
    client on that endpoint at all -- so a correctly configured portal client can answer
    `invalid_client` there and the narrowed check would have called it unknown.
    """
    w = world()
    observations, _ = run(w)
    assert observations["portalClientKnown"]["status"] == "MEASURED_PASS"
    asked = w["server"].RequestHandlerClass.received
    password_probes = [form for form in asked if "grant_type=password" in form]
    assert len(password_probes) == 2, asked
    assert all(f"username={smoke.SYNTHETIC_ACCOUNT}" in form for form in password_probes)


def test_invalid_grant_shows_the_client_was_resolved_and_the_grant_is_live(world):
    """Both facts from one answer, and they point opposite ways.

    Reaching credential checking means the client was found, so the client id is confirmed.
    It also means the client MAY use the password grant, which is the defect the card cares
    about.
    """
    w = world(token_error="invalid_grant")
    observations, _ = run(w)
    known = observations["portalClientKnown"]
    assert known["status"] == "MEASURED_PASS"
    assert known["clientResolvedBy"] == "invalid_grant"
    assert observations["passwordGrantRefused"]["status"] == "MEASURED_FAIL"
    assert "not as a disabled grant" in observations["passwordGrantRefused"]["reason"]
    assert smoke.smoke_verdict(observations) == "FAIL"


def test_a_public_client_refused_client_authentication_is_still_a_refusal(world):
    """The shape a real public portal client produces.

    Password grant: found, not allowed -> unauthorized_client. Client-credentials: a public
    client has no client authentication to offer -> invalid_client. The second is the
    refusal, and it is only read that way because the first established the client exists.
    """
    w = world(token_by_grant={
        "password": (400, "unauthorized_client"),
        "client_credentials": (401, "invalid_client"),
    })
    observations, _ = run(w)
    assert observations["portalClientKnown"]["status"] == "MEASURED_PASS"
    assert observations["passwordGrantRefused"]["status"] == "MEASURED_PASS"
    refused = observations["clientCredentialsRefused"]
    assert refused["status"] == "MEASURED_PASS"
    assert refused["refusedAs"] == "client-authentication-impossible-for-a-public-client"
    assert refused["clientKnownIndependently"] is True
    binding = observations.pop("controlPlaneConfigurationBound")
    assert not [o for o in observations.values() if o["status"] != "MEASURED_PASS"]
    observations["controlPlaneConfigurationBound"] = binding


def test_invalid_client_everywhere_is_a_mistyped_client_id_not_two_locked_doors(world):
    """The concession above must not become the pass it was made to avoid.

    With the client genuinely unknown, `invalid_client` on client-credentials is not
    permitted to read as a refusal, because portalClientKnown did not establish existence.
    """
    w = world(token_by_grant={
        "password": (401, "invalid_client"),
        "client_credentials": (401, "invalid_client"),
    })
    observations, _ = run(w)
    known = observations["portalClientKnown"]
    assert known["status"] == "MEASURED_FAIL"
    assert "is not known to the provider" in known["reason"]
    refused = observations["clientCredentialsRefused"]
    assert refused["status"] == "MEASURED_FAIL"
    assert "not as a disabled grant" in refused["reason"]
    assert smoke.smoke_verdict(observations) == "FAIL"


def test_the_concession_is_an_argument_and_not_a_broadened_error_set():
    """Judge the code: `invalid_client` must not be in either set."""
    assert smoke.UNKNOWN_CLIENT_ERROR not in smoke.GRANT_DISABLED_ERRORS
    assert smoke.UNKNOWN_CLIENT_ERROR not in smoke.CLIENT_RESOLVED_ERRORS
    observation = smoke.observe_grant_refused.__doc__ or ""
    assert "invalid_client" in observation


# --- Codex r4 M2: the verifier judges the bytes that were hashed -------------------


def test_the_verifier_judges_the_copy_of_the_bytes_that_were_hashed(tmp_path, monkeypatch):
    """A swap between the two reads must not change the verdict.

    The tool read the bundle and hashed it, then handed AccessTokens the *path*, which
    ``_keys()`` reads again. Codex reproduced the gap with a swap probe. The fix copies the
    already-hashed bytes into a file this run owns and points the verifier at the copy, so
    the second read cannot see different bytes.

    Here the original path is rewritten with a perfectly valid bundle immediately after the
    first read. The verdict must still be FAIL, because the bytes that were hashed carry an
    encryption key.
    """
    issuer = "https://idp.example.invalid/realms/sv"
    now = int(dt.datetime.now(dt.timezone.utc).timestamp())
    enc_bundle = {"issuer": issuer, "expiresAt": now + 3 * 86_400,
                  "keys": [{**SIGNING_KEY, "alg": "RSA-OAEP", "use": "enc"}]}
    good_bundle = {"issuer": issuer, "expiresAt": now + 3 * 86_400,
                   "keys": [dict(SIGNING_KEY)]}
    config = configuration(tmp_path, document=enc_bundle, issuer=issuer)
    bundle_path = tmp_path / "bundle.json"

    original = Path.read_bytes
    swapped = {"done": False}

    def read_then_swap(self, *args, **kwargs):
        data = original(self, *args, **kwargs)
        if Path(self) == bundle_path and not swapped["done"]:
            # The instant after the tool's read: the path now holds an acceptable bundle.
            swapped["done"] = True
            bundle_path.write_text(json.dumps(good_bundle), encoding="utf-8")
        return data

    monkeypatch.setattr(Path, "read_bytes", read_then_swap)
    result = smoke.read_control_plane_configuration(config)
    monkeypatch.undo()

    assert swapped["done"], "the probe did not get a chance to swap the file"
    assert json.loads(bundle_path.read_text(encoding="utf-8")) == good_bundle
    assert any("refuses-this-configuration" in defect for defect in result["bundleDefects"]), (
        result["bundleDefects"]
    )
    assert result["bundleSha256"] == hashlib.sha256(
        json.dumps(enc_bundle).encode()
    ).hexdigest()


def test_the_swap_in_the_other_direction_does_not_manufacture_a_pass(tmp_path, monkeypatch):
    """The mirror: hashed bytes are acceptable, the path becomes unacceptable."""
    issuer = "https://idp.example.invalid/realms/sv"
    now = int(dt.datetime.now(dt.timezone.utc).timestamp())
    good_bundle = {"issuer": issuer, "expiresAt": now + 3 * 86_400,
                   "keys": [dict(SIGNING_KEY)]}
    enc_bundle = {"issuer": issuer, "expiresAt": now + 3 * 86_400,
                  "keys": [{**SIGNING_KEY, "alg": "RSA-OAEP", "use": "enc"}]}
    config = configuration(tmp_path, document=good_bundle, issuer=issuer)
    bundle_path = tmp_path / "bundle.json"

    original = Path.read_bytes
    swapped = {"done": False}

    def read_then_swap(self, *args, **kwargs):
        data = original(self, *args, **kwargs)
        if Path(self) == bundle_path and not swapped["done"]:
            swapped["done"] = True
            bundle_path.write_text(json.dumps(enc_bundle), encoding="utf-8")
        return data

    monkeypatch.setattr(Path, "read_bytes", read_then_swap)
    result = smoke.read_control_plane_configuration(config)
    monkeypatch.undo()

    assert swapped["done"]
    assert result["bundleDefects"] == [], result["bundleDefects"]
    assert result["bundleSha256"] == hashlib.sha256(
        json.dumps(good_bundle).encode()
    ).hexdigest()


def test_the_bundle_copy_is_removed_and_its_directory_with_it(tmp_path):
    """Nothing this check writes may outlive it."""
    before = set(Path(tempfile.gettempdir()).glob("inv-smoke-bundle-*"))
    smoke.read_control_plane_configuration(configuration(tmp_path))
    after = set(Path(tempfile.gettempdir()).glob("inv-smoke-bundle-*"))
    assert after == before, sorted(after - before)


def test_the_copy_is_removed_even_when_the_verifier_raises(tmp_path):
    before = set(Path(tempfile.gettempdir()).glob("inv-smoke-bundle-*"))
    smoke.read_control_plane_configuration(
        configuration(tmp_path, keys=[{**SIGNING_KEY, "alg": "RSA-OAEP", "use": "enc"}])
    )
    after = set(Path(tempfile.gettempdir()).glob("inv-smoke-bundle-*"))
    assert after == before, sorted(after - before)


def test_the_verifier_is_given_the_copy_and_never_the_configured_path(tmp_path):
    """Judge the call: the path handed to AccessTokens must not be the configured one."""
    seen = {}

    class Recorder:
        def __init__(self, **identity):
            seen.update(identity)
            # Through the product reader: a verifier that never reads the bundle is
            # refused, because its verdict would not be about these bytes.
            trusted_file_of(Path(identity["jwks_file"]))

    configured = tmp_path / "bundle.json"
    smoke.verifier_refusal(
        Recorder,
        {"tenant_id": "00000000-0000-4000-8000-000000000001",
         "issuer": "https://idp.example.invalid/realms/sv",
         "audience": "sv-api", "client_ids": ["sv-portal"],
         "jwks_file": str(configured)},
        b'{"issuer": "x"}',
        hashlib.sha256(b'{"issuer": "x"}').hexdigest(),
    )
    assert seen["jwks_file"] != str(configured)
    assert Path(seen["jwks_file"]).name == "trust-bundle.json"
    assert "inv-smoke-bundle-" in seen["jwks_file"]


# --- Codex r4 M3: a real import failure, not a patched-out function ---------------


def test_an_unimportable_verifier_refuses_the_run_for_real(monkeypatch, tmp_path):
    """The earlier test patched `product_verifier` itself, so its except branch never ran.

    A mutation that replaced the except body with a permissive stub survived. This induces
    the real failure: the module cache is cleared, the control-plane source is taken off
    sys.path, and CONTROL_PLANE_SRC points at a directory with no `inv` package.
    """
    monkeypatch.setattr(smoke, "CONTROL_PLANE_SRC", tmp_path / "nowhere")
    monkeypatch.setattr(
        sys, "path", [p for p in sys.path if "control-plane" not in p.replace("\\", "/")]
    )
    for name in [n for n in list(sys.modules) if n == "inv" or n.startswith("inv.")]:
        monkeypatch.delitem(sys.modules, name, raising=False)
    with pytest.raises(smoke.SmokeRefused, match="could not be imported"):
        smoke.product_verifier()


def test_the_verifier_import_recovers_after_that(monkeypatch):
    """The previous test must not leave the tool unable to find the product."""
    from inv.identity import AccessTokens

    assert smoke.product_verifier() is AccessTokens


# --- Coordinator N7 / Codex r4 M4: the same root twice is not a finding ------------


def test_the_same_root_twice_is_accepted_and_counted_once(world):
    """OpenSSL keeps one copy, so counting PEM blocks refused a duplicate as unchecked."""
    w = world()
    doubled = w["tmp"] / "root-twice.pem"
    doubled.write_text(w["internal"]["pem"] + w["internal"]["pem"], encoding="utf-8")
    pem = doubled.read_text(encoding="utf-8")
    context = smoke.trusted_context(pem, {w["internal"]["sha256"]})
    assert smoke.certificate_authorities(context, pem) == [w["internal"]["sha256"]]
    observations, _ = run(w, ca_bundle=doubled)
    assert observations["idpHttpsVerified"]["status"] == "MEASURED_PASS"


def test_a_duplicate_root_still_has_to_be_an_approved_root(world):
    """Deduplicating must not also drop the allowlist."""
    w = world()
    doubled = w["tmp"] / "foreign-twice.pem"
    doubled.write_text(w["foreign"]["pem"] + w["foreign"]["pem"], encoding="utf-8")
    with pytest.raises(smoke.SmokeRefused, match="unapproved anchor"):
        run(w, ca_bundle=doubled)


# --- Codex/coordinator: the window is removed, so tampering in it is inert ---------
#
# Round 6 sealed the copy before and after the verifier ran. A review showed the seal is
# defeatable by swapping and *putting back*: rename the copy aside, drop another file in,
# rename the original back (the inode survives), or rewrite in place and restore the bytes
# and st_mtime_ns with os.utime. Both give a clean seal over a read that saw other bytes.
#
# The fix is not a tighter seal. For the length of the verifier call the product's own read
# function is replaced in process so it returns the bytes already hashed here, and the disk
# read disappears. These tests therefore assert the opposite of the round-6 ones: cases c, d
# and e change nothing, because there is nothing left for them to race.


def identity_for(tmp_path, issuer="https://idp.example.invalid/realms/sv"):
    return {
        "tenant_id": "00000000-0000-4000-8000-000000000001",
        "issuer": issuer,
        "audience": "sv-api",
        "client_ids": ["sv-portal"],
        "jwks_file": str(tmp_path / "configured.json"),
    }


def bundle_bytes(**overrides):
    now = int(dt.datetime.now(dt.timezone.utc).timestamp())
    document = {"issuer": "https://idp.example.invalid/realms/sv",
                "expiresAt": now + 3 * 86_400,
                "keys": [dict(SIGNING_KEY)]}
    document.update(overrides)
    return json.dumps(document).encode()


ENC_BUNDLE = None  # set per test; an encryption key is what the product refuses


def tampering_verifier(mode, replacement):
    """A verifier that attacks the copy the way the review did, then reads it.

    `mode` is the review's case: "c" swaps a different file in under the same name and
    renames the original back, "d" rewrites in place and restores the bytes and mtime_ns.
    Either defeats a before/after seal. Both must now be irrelevant.
    """
    class Tamperer:
        read: list = []

        def __init__(self, **identity):
            target = Path(identity["jwks_file"])
            original = target.read_bytes()
            before = os.stat(target)
            if mode == "c":
                aside = target.with_suffix(".aside")
                target.rename(aside)
                target.write_bytes(replacement)
                target.unlink()
                aside.rename(target)
            else:
                target.write_bytes(replacement)
                target.write_bytes(original)
                os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns))
            # What the product would read now, and what it actually gets.
            Tamperer.read.append(trusted_file_of(target))

    Tamperer.read = []
    return Tamperer


def trusted_file_of(path):
    """Whatever inv.identity's reader returns right now for this path."""
    import sys as _sys

    return _sys.modules["inv.identity"].trusted_file(path)


@pytest.mark.parametrize("mode", ["c", "d"])
def test_a_swap_that_is_put_back_cannot_change_the_verdict(tmp_path, mode):
    """The review's cases c and d, which defeated the round-6 seal.

    The sealed bytes carry an encryption key, so the verdict must be a defect no matter
    what the file on disk says while the verifier runs.
    """
    sealed = bundle_bytes(keys=[{**SIGNING_KEY, "alg": "RSA-OAEP", "use": "enc"}])
    verifier = tampering_verifier(mode, bundle_bytes())
    defects = smoke.verifier_refusal(
        verifier, identity_for(tmp_path), sealed, hashlib.sha256(sealed).hexdigest()
    )
    # The tamperer did get its swap in, and the reader still handed over the sealed bytes.
    assert verifier.read == [sealed], "the pinned reader returned something else"
    # A stub verifier raises nothing, so there is no defect to report -- what matters is
    # that the bytes the product would have read are the bytes that were hashed.
    assert defects == []


def test_case_e_cannot_manufacture_a_defect_either(tmp_path):
    """The mirror: acceptable bytes sealed, an unacceptable file on disk during the read."""
    sealed = bundle_bytes()
    verifier = tampering_verifier(
        "d", bundle_bytes(keys=[{**SIGNING_KEY, "alg": "RSA-OAEP", "use": "enc"}])
    )
    defects = smoke.verifier_refusal(
        verifier, identity_for(tmp_path), sealed, hashlib.sha256(sealed).hexdigest()
    )
    assert verifier.read == [sealed]
    assert defects == []


@pytest.mark.parametrize("mode", ["c", "d"])
def test_the_real_verifier_reaches_its_verdict_through_the_pin(tmp_path, mode):
    """End to end with the product class, while the file on disk is being swapped.

    The sealed bytes are unacceptable and the disk is made acceptable mid-read. Round 5
    would have reported clean; round 6 would have refused; this reports the defect, which
    is the honest answer about the bytes that were hashed.
    """
    sealed = bundle_bytes(keys=[{**SIGNING_KEY, "alg": "RSA-OAEP", "use": "enc"}])
    good = bundle_bytes()
    attacked = {"done": False}
    product = smoke.product_verifier()

    class Racing(product):
        def __init__(self, **identity):
            target = Path(identity["jwks_file"])
            if not attacked["done"]:
                attacked["done"] = True
                original = target.read_bytes()
                before = os.stat(target)
                if mode == "c":
                    aside = target.with_suffix(".aside")
                    target.rename(aside)
                    target.write_bytes(good)
                    target.unlink()
                    aside.rename(target)
                else:
                    target.write_bytes(good)
                    target.write_bytes(original)
                    os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns))
            super().__init__(**identity)

    defects = smoke.verifier_refusal(
        Racing, identity_for(tmp_path), sealed, hashlib.sha256(sealed).hexdigest()
    )
    assert attacked["done"], "the probe never ran"
    assert any("refuses-this-configuration" in defect for defect in defects), defects


def test_the_verdict_comes_from_the_hashed_bytes_not_the_file_on_disk(tmp_path):
    """The test that shows the pin is load-bearing, with the real product class.

    Cases c and d restore the bytes before the read, so the verdict happens to come out the
    same with or without the pin -- they pin the review's scenarios, not the pin's necessity.
    This one leaves the disk holding an ACCEPTABLE bundle while the hashed bytes carry an
    encryption key, and does not put anything back. Without the pin the product reads the
    file and reports no defect; with it the verdict is about the bytes that were hashed.
    """
    sealed = bundle_bytes(keys=[{**SIGNING_KEY, "alg": "RSA-OAEP", "use": "enc"}])
    good = bundle_bytes()
    swapped = {"done": False}
    product = smoke.product_verifier()

    class LeavesGoodBytesOnDisk(product):
        def __init__(self, **identity):
            target = Path(identity["jwks_file"])
            swapped["done"] = True
            target.write_bytes(good)   # and it stays that way
            super().__init__(**identity)

    defects = smoke.verifier_refusal(
        LeavesGoodBytesOnDisk, identity_for(tmp_path), sealed,
        hashlib.sha256(sealed).hexdigest(),
    )
    assert swapped["done"]
    assert any("refuses-this-configuration" in defect for defect in defects), (
        "the verdict followed the file on disk instead of the hashed bytes"
    )


def test_the_mirror_of_that_does_not_manufacture_a_defect(tmp_path):
    """Acceptable bytes hashed, an unacceptable file left on disk: still no defect."""
    sealed = bundle_bytes()
    bad = bundle_bytes(keys=[{**SIGNING_KEY, "alg": "RSA-OAEP", "use": "enc"}])
    product = smoke.product_verifier()

    class LeavesBadBytesOnDisk(product):
        def __init__(self, **identity):
            Path(identity["jwks_file"]).write_bytes(bad)
            super().__init__(**identity)

    assert smoke.verifier_refusal(
        LeavesBadBytesOnDisk, identity_for(tmp_path), sealed,
        hashlib.sha256(sealed).hexdigest(),
    ) == []


def test_an_acceptable_bundle_still_passes_through_the_pin(tmp_path):
    """The control, with the real product class and no interference."""
    sealed = bundle_bytes()
    assert smoke.verifier_refusal(
        smoke.product_verifier(), identity_for(tmp_path), sealed,
        hashlib.sha256(sealed).hexdigest(),
    ) == []


def test_a_verifier_that_never_reads_the_bundle_refuses_the_run(tmp_path):
    """A verdict reached without reading the bundle is not a verdict about the bundle."""
    class Lazy:
        def __init__(self, **identity):
            pass

    sealed = bundle_bytes()
    with pytest.raises(smoke.SmokeRefused, match="did not read the trust bundle"):
        smoke.verifier_refusal(
            Lazy, identity_for(tmp_path), sealed, hashlib.sha256(sealed).hexdigest()
        )


def test_the_pin_is_restored_afterwards(tmp_path):
    """In process means the product must be exactly as it was when this returns."""
    import sys as _sys

    module = _sys.modules["inv.identity"]
    before = module.trusted_file
    sealed = bundle_bytes()
    smoke.verifier_refusal(
        smoke.product_verifier(), identity_for(tmp_path), sealed,
        hashlib.sha256(sealed).hexdigest(),
    )
    assert module.trusted_file is before

    class Exploding:
        def __init__(self, **identity):
            # Through the product reader, as the product does -- a direct read would not
            # exercise the pin and would be refused for not having read the bundle.
            trusted_file_of(Path(identity["jwks_file"]))
            raise RuntimeError("boom")

    smoke.verifier_refusal(
        Exploding, identity_for(tmp_path), sealed, hashlib.sha256(sealed).hexdigest()
    )
    assert module.trusted_file is before, "not restored on the exception path"

    with pytest.raises(smoke.SmokeRefused):
        smoke.verifier_refusal(
            type("NoRead", (), {"__init__": lambda self, **kw: None}),
            identity_for(tmp_path), sealed, hashlib.sha256(sealed).hexdigest(),
        )
    assert module.trusted_file is before, "not restored on the refusal path"


def test_the_pin_delegates_every_other_path(tmp_path):
    """Only our copy is pinned; the product reads anything else as it always would."""
    other = tmp_path / "somebody-elses.json"
    other.write_bytes(b'{"unrelated": true}')
    copy = tmp_path / "ours.json"
    copy.write_bytes(b'{"ours": true}')
    with smoke.bundle_read_pinned(copy, b'{"pinned": true}') as reads:
        assert trusted_file_of(copy) == b'{"pinned": true}'
        assert trusted_file_of(other) == b'{"unrelated": true}'
    assert reads == [str(copy)]


def test_the_pin_fails_loudly_if_the_product_has_no_such_reader(tmp_path, monkeypatch):
    """A pin that silently does not apply would put the disk read back."""
    import sys as _sys

    monkeypatch.delattr(_sys.modules["inv.identity"], smoke.PRODUCT_READER)
    with pytest.raises(AttributeError):
        with smoke.bundle_read_pinned(tmp_path / "x", b"{}"):
            pass


def test_bytes_that_do_not_match_the_recorded_digest_refuse_the_run(tmp_path):
    with pytest.raises(smoke.SmokeRefused, match="do not hash to the digest"):
        smoke.verifier_refusal(
            smoke.product_verifier(), identity_for(tmp_path), b'{"issuer": "x"}', "0" * 64
        )
