"""End-to-end smoke check across the intranet identity path.

Each piece of this path has been measured on its own. That does not say the pieces
line up *as deployed*: that the name resolves, that the certificate is the one the
internal CA issued, that the issuer the provider announces is the issuer the control
plane was configured with, that the keys it serves are the keys the control plane
trusts, and that the control plane refuses a token it should refuse.

**The identity under test is not a command-line argument.** An earlier version took
``--idp-host``, ``--idp-port`` and ``--issuer`` separately and then checked the
provider's discovery document against the string the caller had supplied. A review
showed what that allows: connect to one host, pass a foreign issuer, and both the
issuer and JWKS observations pass while nothing about the deployment has been
checked. So the issuer, the client id and the trusted keys now come from the control
plane's own configuration file, whose bytes are hashed into the report, and the TLS
connection target is *derived from that issuer* -- which makes the SNI, the Host
header and the announced issuer the same string by construction rather than by
agreement between three flags.

Three things this will not do, each enforced rather than promised:

* **It never turns verification off.** There is no flag, and the context is built
  explicitly rather than from ``ssl.create_default_context()``, which honours
  ``SSLKEYLOGFILE`` and would write TLS session secrets to a file of the
  environment's choosing.
* **It never substitutes its own name resolution.** If the issuer's host does not
  resolve the answer is ``BLOCKED_EXTERNAL``, because the deployment either resolves
  the name or it does not. But once a name *has* resolved, a connection, TLS or
  endpoint failure is a ``MEASURED_FAIL`` -- a deployed service that will not answer
  is a defect, not a precondition somebody still owes.
* **It never uses a real user's password grant.** That grant is disabled on the
  portal client on purpose, and the refusal is confirmed with an account name that
  cannot exist. ``invalid_client`` is **not** accepted as proof: it says the client is
  unknown, not that a known client may not use the grant, so a typo in the client id
  would otherwise read as a locked door.

The report carries no address, token, key or credential. That is checked on the
serialised output -- JSON, Markdown and stdout -- rather than trusted to the code
that builds it.

Exit codes: 0 PASS, 1 FAIL, 3 BLOCKED_EXTERNAL or NOT_OBSERVED, 2 refused.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import ipaddress
import json
import re
import secrets
import socket
import ssl
import time
from pathlib import Path
import sys
from typing import Any
from urllib.parse import urlencode, urlsplit

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.operational_evidence import (  # noqa: E402
    COMMIT_PATTERN,
    LABEL_PATTERN,
    SHA256_PATTERN,
    STATUSES,
    assert_no_secrets,
    collect_provenance_at_root,
    collector_sha256,
    default_label,
    input_binding_sha256,
    iso,
    sha256_text,
    write_evidence,
)

SCHEMA_VERSION = "intranet-e2e-smoke:2"
DEFAULT_OUT_DIR = REPO_ROOT / "docs/vault/30_Development/Evidence/intranet-e2e-smoke"
#: A response larger than this is a finding, not something to quietly truncate.
MAX_BODY_BYTES = 262_144
TIMEOUT = 10.0
#: One wall-clock budget for the whole run, so a hung endpoint cannot stall it
#: indefinitely while individual timeouts keep resetting.
DEADLINE_SECONDS = 180.0

#: Where the run happened. A report from a place where the name resolves is not a
#: report about a place where it does not.
RUN_ENVIRONMENTS = ("operator-workstation", "idp-node-container")

#: The canonical realm path shape. A discovery document served from somewhere else in
#: the URL space is not this realm, however well its issuer string matches.
REALM_PATH = re.compile(r"^/realms/[A-Za-z0-9._-]+$")

#: `inv.app` answers with exactly these keys and no others (contracts ProblemDetails,
#: additionalProperties false).
PROBLEM_KEYS = frozenset(
    {"type", "title", "status", "code", "category", "detail", "retryable", "traceId",
     "causeRef", "evidenceId"}
)
PROBLEM_MEDIA_TYPE = "application/problem+json"
EXPECTED_PROBLEM_CODE = "AUTH-0050"
EXPECTED_PROBLEM_CATEGORY = "AUTH"

#: OAuth errors that mean "this client may not use this grant".
#: `invalid_client` is deliberately absent: it says the client is unknown, which is a
#: different fact, and accepting it would let a mistyped client id pass as a refusal.
GRANT_DISABLED_ERRORS = frozenset({"unauthorized_client", "unsupported_grant_type"})
UNKNOWN_CLIENT_ERROR = "invalid_client"
#: A username that cannot exist. Used so a refusal can be observed without a key.
SYNTHETIC_ACCOUNT = "smoke-nonexistent-account"

REQUIRED = (
    "controlPlaneConfigurationBound",
    "idpNameResolves",
    "idpHttpsVerified",
    "idpDiscoveryIssuer",
    "portalClientKnown",
    "idpJwksMatchesTrustBundle",
    "passwordGrantRefused",
    "clientCredentialsRefused",
    "controlPlaneRejectsBadToken",
    "controlPlaneRejectsMissingToken",
)

CRITERIA = {
    "controlPlaneConfigurationBound": (
        "the issuer, client id and trusted keys come from the control plane's own "
        "configuration, whose bytes are hashed into this report"
    ),
    "idpNameResolves": "the system resolver finds the issuer's host; no substitute is accepted",
    "idpHttpsVerified": (
        "TLS to the issuer's own host verifies against an allowed internal root, with "
        "hostname checking on"
    ),
    "idpDiscoveryIssuer": "the announced issuer equals the configured issuer, on the same origin",
    "portalClientKnown": "the configured client id is known to the provider",
    "idpJwksMatchesTrustBundle": (
        "the signing keys the provider serves are the keys the control plane trusts"
    ),
    "passwordGrantRefused": "the portal client refuses a password grant (synthetic account only)",
    "clientCredentialsRefused": "the portal client refuses a client-credentials grant",
    "controlPlaneRejectsBadToken": (
        "GET /v1/session with a signed-but-invalid bearer answers 401 as canonical "
        "ProblemDetails with code AUTH-0050"
    ),
    "controlPlaneRejectsMissingToken": (
        "GET /v1/session with no Authorization answers the same canonical 401"
    ),
}


class SmokeRefused(RuntimeError):
    """An input is unusable, so the run does not start."""


class DeadlineExceeded(RuntimeError):
    """The run ran out of time. Deliberately not caught by any observation: a
    half-finished walk reported as failures would blame the deployment for a clock."""


def blocked(reason: str) -> dict[str, Any]:
    return {"status": "BLOCKED_EXTERNAL", "reason": reason}


def unmeasured(reason: str) -> dict[str, Any]:
    return {"status": "NOT_OBSERVED", "reason": reason}


def failed(reason: str, /, **facts: Any) -> dict[str, Any]:
    """The reason is positional-only, which is the whole point.

    An earlier version declared it as a normal parameter and was called as
    failed("...", reason=...). That raised TypeError before the body ran, so a
    certificate-verification failure ended the run with no evidence at all. Making it
    positional-only means a stray `reason=` lands in facts and is dropped instead.
    """
    facts.pop("reason", None)
    return {"status": "MEASURED_FAIL", "reason": reason, **facts}


def passed(**facts: Any) -> dict[str, Any]:
    return {"status": "MEASURED_PASS", **facts}


def smoke_verdict(observations: dict[str, dict[str, Any]], required=REQUIRED) -> str:
    """A measured failure outranks a missing precondition, which outranks a gap."""
    statuses = [observations.get(name, {}).get("status") for name in required]
    if any(status == "MEASURED_FAIL" for status in statuses):
        return "FAIL"
    if any(status == "BLOCKED_EXTERNAL" for status in statuses):
        return "BLOCKED_EXTERNAL"
    if statuses and all(status == "MEASURED_PASS" for status in statuses):
        return "PASS"
    return "NOT_OBSERVED"


EXIT_BY_VERDICT = {"PASS": 0, "FAIL": 1, "BLOCKED_EXTERNAL": 3, "NOT_OBSERVED": 3}


# --- redaction: checked on the output, not trusted to the builder -----------------

#: Runs that could be an address. Judged by ``ipaddress``, so compressed IPv6 such as
#: ``::1`` is caught, while SHA-256 hex and ISO dates are not mistaken for addresses.
ADDRESS_CANDIDATE = re.compile(r"[0-9A-Fa-f:.]{3,}")
TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T[\d:.]+(?:Z|[+-]\d{2}:\d{2})")
SECRET_MARKERS = ("-----BEGIN", "PRIVATE KEY", "Authorization:")
# A credential-shaped value, not the English word: the criteria text says
# "a signed-but-invalid bearer answers 401", which must not read as a token.
BEARER = re.compile(r"[Bb]earer\s+[A-Za-z0-9._~+/=-]{16,}")
JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{6,}")
USERINFO = re.compile(r"//[^/\s\"']*:[^/\s\"']*@")


def addresses_in(text: str) -> list[str]:
    found = []
    for match in ADDRESS_CANDIDATE.finditer(TIMESTAMP.sub("<time>", text)):
        raw = match.group(0)
        # Both forms: stripping punctuation finds an address inside a sentence, and the
        # raw form finds compressed IPv6 such as "::1", whose colons are the address.
        for candidate in (raw, raw.strip(".:")):
            if not candidate:
                continue
            try:
                ipaddress.ip_address(candidate)
            except ValueError:
                continue
            found.append(candidate)
            break
    return found


def assert_no_addresses(text: str) -> None:
    found = addresses_in(text)
    if found:
        raise SmokeRefused(f"the report would contain {len(found)} address-like value(s)")


def assert_no_credentials(text: str) -> None:
    """Refuse anything that is a credential by shape, not by field name."""
    for marker in SECRET_MARKERS:
        if marker in text:
            raise SmokeRefused(f"the report would contain {marker!r}")
    for pattern, label in ((BEARER, "a bearer token"), (JWT, "a JWT"), (USERINFO, "URL userinfo")):
        if pattern.search(text):
            raise SmokeRefused(f"the report would contain {label}")


def assert_publishable(text: str) -> None:
    assert_no_secrets(text)
    assert_no_addresses(text)
    assert_no_credentials(text)


# --- the identity under test comes from the control plane's configuration ---------


def canonical_issuer(value: Any) -> tuple[str, int]:
    """Refuse an issuer that is not one unambiguous realm on one https origin.

    Returns the host and effective port, which is how the TLS connection is addressed,
    so the SNI, the Host header and the announced issuer cannot disagree.
    """
    if not isinstance(value, str) or not value:
        raise SmokeRefused("the configured issuer is missing")
    parts = urlsplit(value)
    if parts.scheme != "https":
        raise SmokeRefused("the configured issuer must be https")
    if parts.username or parts.password:
        raise SmokeRefused("the configured issuer must not carry userinfo")
    if parts.query or parts.fragment:
        raise SmokeRefused("the configured issuer must not carry a query or fragment")
    if not parts.hostname:
        raise SmokeRefused("the configured issuer has no host")
    if not REALM_PATH.match(parts.path):
        raise SmokeRefused("the configured issuer path is not a canonical realm path")
    return parts.hostname.lower(), parts.port or 443


def same_origin(url: str, issuer: str) -> bool:
    def origin(value: str) -> tuple[str, str, int]:
        parts = urlsplit(value)
        if parts.username or parts.password or parts.fragment:
            raise SmokeRefused("a URL with userinfo or a fragment is refused")
        if not parts.hostname:
            raise SmokeRefused("a URL without a host is refused")
        default = 443 if parts.scheme == "https" else 80
        return parts.scheme.lower(), parts.hostname.lower(), parts.port or default

    return origin(url) == origin(issuer)


def read_control_plane_configuration(path: Path) -> dict[str, Any]:
    """The issuer, the client id and the trusted keys, from the deployment itself."""
    raw = path.read_bytes()
    try:
        config = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise SmokeRefused(f"the control plane configuration is not JSON: {type(error).__name__}")
    identity = (config or {}).get("identity")
    if not isinstance(identity, dict):
        raise SmokeRefused("the control plane configuration has no identity section")
    issuer = identity.get("issuer")
    host, port = canonical_issuer(issuer)
    clients = identity.get("client_ids")
    if not isinstance(clients, list) or len(clients) != 1 or not isinstance(clients[0], str):
        # More than one would make "the configured client" ambiguous, and this check is
        # about one client's grant configuration.
        raise SmokeRefused("the configuration must name exactly one client id")
    audience = identity.get("audience")
    if not isinstance(audience, str) or not audience:
        raise SmokeRefused("the configuration names no audience")
    bundle_path = identity.get("jwks_file")
    if not isinstance(bundle_path, str) or not bundle_path:
        raise SmokeRefused("the configuration names no jwks_file")
    bundle_raw = Path(bundle_path).read_bytes()
    try:
        bundle = json.loads(bundle_raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise SmokeRefused(f"the trust bundle is not JSON: {type(error).__name__}")
    trusted = sorted(
        str(key.get("kid")) for key in (bundle.get("keys") or []) if isinstance(key, dict)
    )
    if not trusted:
        raise SmokeRefused("the trust bundle carries no keys")
    if bundle.get("issuer") != issuer:
        raise SmokeRefused("the trust bundle issuer does not match the configured issuer")
    return {
        "issuer": issuer,
        "host": host,
        "port": port,
        "clientId": clients[0],
        "audience": audience,
        "trustedKids": trusted,
        "configSha256": hashlib.sha256(raw).hexdigest(),
        "bundleSha256": hashlib.sha256(bundle_raw).hexdigest(),
    }


# --- TLS built explicitly, from bytes read once ------------------------------------


def certificate_authorities(context: ssl.SSLContext) -> list[str]:
    """SHA-256 of every loaded anchor, after checking each really is a CA.

    A leaf smuggled into the bundle would otherwise act as its own anchor, so
    basicConstraints is read rather than assumed.
    """
    from cryptography import x509

    anchors = []
    for der in context.get_ca_certs(binary_form=True):
        parsed = x509.load_der_x509_certificate(der)
        try:
            basic = parsed.extensions.get_extension_for_class(x509.BasicConstraints).value
        except x509.ExtensionNotFound:
            raise SmokeRefused("an anchor has no basicConstraints and cannot be a CA")
        if not basic.ca:
            raise SmokeRefused("an anchor is not a certificate authority")
        anchors.append(hashlib.sha256(der).hexdigest())
    return anchors


def trusted_context(pem: str, allowed_roots: set[str]) -> ssl.SSLContext:
    """A context that verifies, from bytes already hashed, ignoring the environment.

    `ssl.create_default_context()` is not used: it honours `SSLKEYLOGFILE`, which would
    write TLS session secrets to a path the environment chooses, and it would load the
    system trust store, so an unrelated public root could anchor this chain.
    """
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    # cadata, not cafile: the bytes that were hashed are the bytes that are trusted, so
    # the file cannot be swapped between verifying and recording.
    context.load_verify_locations(cadata=pem)
    if getattr(context, "keylog_filename", None) is not None:
        raise SmokeRefused("TLS key logging is enabled in this environment")
    anchors = certificate_authorities(context)
    if not anchors:
        raise SmokeRefused("the CA bundle contains no certificate authority")
    unexpected = sorted(set(anchors) - allowed_roots)
    if unexpected:
        raise SmokeRefused(f"the CA bundle carries {len(unexpected)} unapproved anchor(s)")
    return context


# --- transport -------------------------------------------------------------------


class Deadline:
    def __init__(self, seconds: float) -> None:
        self.expires_at = time.monotonic() + seconds

    def remaining(self) -> float:
        left = self.expires_at - time.monotonic()
        if left <= 0:
            raise DeadlineExceeded("the run exceeded its deadline")
        return min(left, TIMEOUT)


class Oversized(RuntimeError):
    """The response exceeded the bound. Recorded, never silently truncated."""


def read_bounded(receive) -> bytes:
    chunks, total = [], 0
    while True:
        block = receive(65536)
        if not block:
            return b"".join(chunks)
        chunks.append(block)
        total += len(block)
        if total > MAX_BODY_BYTES:
            raise Oversized(f"response exceeded {MAX_BODY_BYTES} bytes")


def https_request(
    context: ssl.SSLContext,
    host: str,
    port: int,
    path: str,
    deadline: Deadline,
    *,
    method: str = "GET",
    body: str | None = None,
) -> tuple[int, dict[str, str], bytes]:
    """One request over verified TLS to the issuer's own host, with a bounded read."""
    headers = {"Host": host if port == 443 else f"{host}:{port}",
               "Connection": "close", "Accept": "application/json"}
    payload = b""
    if body is not None:
        payload = body.encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        headers["Content-Length"] = str(len(payload))
    head = f"{method} {path} HTTP/1.1\r\n" + "".join(f"{k}: {v}\r\n" for k, v in headers.items())
    with socket.create_connection((host, port), timeout=deadline.remaining()) as raw:
        with context.wrap_socket(raw, server_hostname=host) as tls:
            tls.settimeout(deadline.remaining())
            tls.sendall(head.encode() + b"\r\n" + payload)
            return split_response(read_bounded(tls.recv))


def plain_request(url: str, path: str, deadline: Deadline, *, headers=None):
    """Loopback only. A loopback request never crosses the network."""
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if parts.scheme != "http" or not loopback_host(host):
        raise SmokeRefused("the control plane URL must be loopback http")
    port = parts.port or 80
    authority = f"[{host}]:{port}" if ":" in host else f"{host}:{port}"
    request_headers = {"Host": authority, "Connection": "close", "Accept": "application/json"}
    request_headers.update(headers or {})
    head = f"GET {path} HTTP/1.1\r\n" + "".join(
        f"{k}: {v}\r\n" for k, v in request_headers.items()
    )
    with socket.create_connection((host, port), timeout=deadline.remaining()) as raw:
        raw.settimeout(deadline.remaining())
        raw.sendall(head.encode() + b"\r\n")
        return split_response(read_bounded(raw.recv))


def loopback_host(host: str) -> bool:
    if host in {"localhost", "localhost.localdomain"}:
        return True
    try:
        return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return False


def control_plane_label(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    return "loopback" if loopback_host(host) else "non-loopback"


def split_response(raw: bytes) -> tuple[int, dict[str, str], bytes]:
    head, _, body = raw.partition(b"\r\n\r\n")
    if not head:
        raise SmokeRefused("empty response")
    lines = head.split(b"\r\n")
    parts = lines[0].decode("latin-1").split()
    status = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    headers: dict[str, str] = {}
    for line in lines[1:]:
        name, sep, value = line.decode("latin-1").partition(":")
        if sep:
            headers[name.strip().lower()] = value.strip()
    if headers.get("transfer-encoding", "").lower() == "chunked":
        body = dechunk(body)
    return status, headers, body


def dechunk(body: bytes) -> bytes:
    out = bytearray()
    while True:
        line, _, rest = body.partition(b"\r\n")
        try:
            size = int(line.split(b";")[0] or b"0", 16)
        except ValueError:
            return bytes(out) or body
        if size == 0:
            return bytes(out)
        out += rest[:size]
        body = rest[size + 2 :]


def as_json(body: bytes) -> Any:
    text = body.decode("utf-8", "replace")
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise SmokeRefused("response was not a JSON object")
    return json.loads(text[start : end + 1])


# --- the observations ------------------------------------------------------------
#
# Every one of these takes a resolved name as given. Beyond that point a connection,
# TLS or endpoint failure is MEASURED_FAIL: a deployed service that will not answer is
# a defect, and calling it BLOCKED_EXTERNAL would file a fault as somebody's homework.


def observe_name(host: str) -> tuple[dict[str, Any], list[str]]:
    """Resolution is the one gate an operator still owes. No address is recorded."""
    try:
        addresses = sorted({info[4][0] for info in socket.getaddrinfo(host, None)})
    except socket.gaierror:
        return blocked("hosts-not-applied"), []
    families = sorted({"ipv6" if ":" in address else "ipv4" for address in addresses})
    return passed(resolvedAddressCount=len(addresses), addressFamilies=families), addresses


def peer_certificate(context, host, port, deadline):
    with socket.create_connection((host, port), timeout=deadline.remaining()) as raw:
        with context.wrap_socket(raw, server_hostname=host) as tls:
            return tls.getpeercert(), tls.version()


def expiry_date(not_after: Any) -> str | None:
    """`Dec 28 23:05:05 2026 GMT` -> `2026-12-28`.

    The clock time is dropped deliberately: it parses as an IPv6 address to the guard
    above, and a certificate's expiry day is what anyone reading this needs.
    """
    if not isinstance(not_after, str) or not not_after:
        return None
    try:
        return dt.datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").date().isoformat()
    except ValueError:
        return "unparsed"


def observe_https(context, host, port, path, deadline):
    """TLS to the issuer's own host. Every failure past resolution is a failure."""
    try:
        status, headers, body = https_request(context, host, port, path, deadline)
        if status != 200:
            return failed("discovery did not answer 200", httpStatus=status), None, headers
        peer, protocol = peer_certificate(context, host, port, deadline)
    except ssl.SSLCertVerificationError as error:
        return failed("the certificate did not verify", verifyCode=error.verify_code), None, {}
    except ssl.SSLError as error:
        # An SSLError that is not a verification error is still a TLS failure, and
        # SSLError subclasses OSError, so it must be caught before the OSError arm.
        return failed("TLS failed", sslReason=type(error).__name__), None, {}
    except Oversized as error:
        return failed(str(error)), None, {}
    except (OSError, SmokeRefused) as error:
        # The second handshake is inside this try on purpose: an earlier version put it
        # outside and a failure there ended the run with no evidence at all.
        return failed("the resolved host did not complete a request",
                      osReason=type(error).__name__), None, {}
    names = sorted(value for kind, value in peer.get("subjectAltName", ()) if kind == "DNS")
    if host not in names:
        return failed("the certificate does not cover the issuer's host",
                      leafSanDnsNames=names), body, headers
    return (
        passed(
            tlsVersion=protocol,
            hostnameCheckEnabled=context.check_hostname,
            verifyMode=context.verify_mode.name,
            keyLoggingDisabled=getattr(context, "keylog_filename", None) is None,
            leafCommonName=dict(pair[0] for pair in peer["subject"]).get("commonName"),
            leafSanDnsNames=names,
            leafSanAddressCount=sum(
                1 for kind, _ in peer.get("subjectAltName", ()) if kind != "DNS"
            ),
            leafNotAfterDate=expiry_date(peer.get("notAfter")),
        ),
        body,
        headers,
    )


def observe_discovery(body, issuer):
    if body is None:
        return failed("no discovery document was read"), None
    try:
        document = as_json(body)
    except (SmokeRefused, json.JSONDecodeError):
        return failed("discovery was not JSON"), None
    if document.get("issuer") != issuer:
        # The wrong value is not echoed: that it differs is the whole finding.
        return failed("the announced issuer is not the configured issuer",
                      issuerMatches=False), document
    for field in ("token_endpoint", "jwks_uri", "authorization_endpoint"):
        value = document.get(field)
        try:
            ok = isinstance(value, str) and same_origin(value, issuer)
        except SmokeRefused:
            ok = False
        if not ok:
            return failed(f"{field} is not on the issuer's origin"), document
    return (
        passed(issuerMatches=True,
               pkceMethods=document.get("code_challenge_methods_supported")),
        document,
    )


def observe_jwks(context, document, config, deadline):
    """The keys served must be the keys the control plane trusts."""
    uri = (document or {}).get("jwks_uri")
    if not isinstance(uri, str):
        return failed("discovery published no jwks_uri")
    try:
        status, _, body = https_request(
            context, config["host"], config["port"], urlsplit(uri).path, deadline
        )
        keys = as_json(body).get("keys")
    except Oversized as error:
        return failed(str(error))
    except (ssl.SSLError, OSError, SmokeRefused, json.JSONDecodeError) as error:
        return failed("the key set could not be read", readReason=type(error).__name__)
    if status != 200 or not isinstance(keys, list) or not keys:
        return failed("jwks did not serve a key set", httpStatus=status)
    signing = sorted(
        str(key.get("kid")) for key in keys
        if isinstance(key, dict) and key.get("alg") == "RS256" and key.get("use") == "sig"
    )
    if not signing:
        return failed("no RS256 signing key is published", keyCount=len(keys))
    trusted = set(config["trustedKids"])
    if not trusted & set(signing):
        # A provider serving keys the control plane does not trust means every token it
        # issues will be refused: the pieces are lined up against each other.
        return failed(
            "no served signing key is in the control plane's trust bundle",
            servedSigningKidSha256=[sha256_text(kid) for kid in signing],
            trustedKidSha256=[sha256_text(kid) for kid in sorted(trusted)],
        )
    return passed(
        keyCount=len(keys),
        signingKeyCount=len(signing),
        trustedAndServedKidCount=len(trusted & set(signing)),
        servedSigningKidSha256=[sha256_text(kid) for kid in signing],
    )


def post_token(context, config, deadline, form):
    path = urlsplit(config["issuer"]).path + "/protocol/openid-connect/token"
    status, _, body = https_request(
        context, config["host"], config["port"], path, deadline,
        method="POST", body=urlencode({**form, "client_id": config["clientId"]}),
    )
    error = ""
    try:
        error = str(as_json(body).get("error") or "")
    except (SmokeRefused, json.JSONDecodeError):
        pass
    return status, error


def observe_client_known(context, config, deadline):
    """`invalid_client` means the client id is not known, which is its own finding.

    Separating this from the grant checks is what stops a typo in the client id from
    reading as two locked doors.
    """
    try:
        status, error = post_token(context, config, deadline, {"grant_type": "client_credentials"})
    except Oversized as oversized:
        return failed(str(oversized))
    except (ssl.SSLError, OSError, SmokeRefused) as failure:
        return failed("the token endpoint could not be reached",
                      readReason=type(failure).__name__)
    if error == UNKNOWN_CLIENT_ERROR:
        return failed("the configured client id is not known to the provider",
                      httpStatus=status, oauthError=error)
    return passed(httpStatus=status, oauthError=error or "none")


def observe_grant_refused(context, config, deadline, form, label):
    """A refusal observed without holding a credential.

    The password grant is disabled on this client on purpose, so the way to confirm it
    is to ask with an account that cannot exist: a client that may not use the grant is
    refused on the grant, before any account is considered. `invalid_grant` would mean
    the client MAY use it, and `invalid_client` would mean the client is unknown --
    neither is proof that a known client's grant is off.
    """
    try:
        status, error = post_token(context, config, deadline, form)
    except Oversized as oversized:
        return failed(str(oversized))
    except (ssl.SSLError, OSError, SmokeRefused) as failure:
        return failed("the token endpoint could not be reached",
                      readReason=type(failure).__name__)
    if status == 200:
        return failed(f"{label} was granted", httpStatus=200)
    if error in GRANT_DISABLED_ERRORS:
        return passed(httpStatus=status, oauthError=error)
    return failed(f"{label} was refused, but not as a disabled grant",
                  httpStatus=status, oauthError=error or "unnamed")


def signed_but_invalid_token(config, now):
    """A token that reaches signature verification instead of stopping at the header.

    `not.a.valid.token` is refused while parsing the header, so it never exercises the
    issuer, audience, key-id or signature path at all. This one is well formed, names a
    key the control plane trusts and carries every required claim, so the only thing
    wrong with it is the signature -- which is exactly the refusal worth observing.
    """
    def segment(value):
        raw = json.dumps(value, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    issued = int(now.timestamp())
    header = {"alg": "RS256", "typ": "at+jwt", "kid": config["trustedKids"][0]}
    claims = {
        "iss": config["issuer"],
        "aud": config["audience"],
        "sub": "smoke-probe-subject",
        "iat": issued,
        "exp": issued + 300,
        "jti": secrets.token_hex(16),
        "client_id": config["clientId"],
        "scope": "openid inv.api",
    }
    signature = base64.urlsafe_b64encode(secrets.token_bytes(256)).decode().rstrip("=")
    return f"{segment(header)}.{segment(claims)}.{signature}"


def observe_control_plane(url, deadline, *, authorization, label):
    """Refusal is all this asks -- but it must be the canonical control plane's refusal.

    Any process on loopback can answer 401. What only this control plane answers is a
    canonical ProblemDetails body with exactly the contract's keys and code AUTH-0050.
    A 503 carrying the same code means its identity trust is not configured, which is a
    different state and must not be counted as a refusal.
    """
    headers = {"Authorization": authorization} if authorization else {}
    try:
        status, response_headers, body = plain_request(
            url, "/v1/session", deadline, headers=headers
        )
    except Oversized as error:
        return failed(str(error))
    except (OSError, SmokeRefused) as error:
        return failed("the control plane did not answer", readReason=type(error).__name__)
    media = response_headers.get("content-type", "").split(";")[0].strip().lower()
    if status == 503:
        return failed("the control plane reports its identity trust is not configured",
                      httpStatus=503)
    if status != 401:
        return failed("the control plane did not answer 401", httpStatus=status)
    if media != PROBLEM_MEDIA_TYPE:
        return failed("the refusal was not canonical problem+json",
                      contentType=media or "absent")
    try:
        document = as_json(body)
    except (SmokeRefused, json.JSONDecodeError):
        return failed("the refusal body was not JSON")
    if set(document) != PROBLEM_KEYS:
        return failed("the refusal body is not the canonical ProblemDetails shape",
                      keyCount=len(document))
    if document.get("code") != EXPECTED_PROBLEM_CODE:
        return failed("the refusal carried another code",
                      problemCode=str(document.get("code")))
    if document.get("category") != EXPECTED_PROBLEM_CATEGORY or document.get("status") != 401:
        return failed("the refusal body disagrees with its own status line")
    return passed(httpStatus=401, contentType=media, problemCode=EXPECTED_PROBLEM_CODE,
                  canonicalShape=True, probe=label)


def observe_readyz(url, deadline):
    """Recorded, not required: which process answered is worth knowing either way."""
    try:
        status, _, _ = plain_request(url, "/readyz", deadline)
    except Oversized:
        return {"status": "RECORDED_ONLY", "readyz": "oversized"}
    except (OSError, SmokeRefused) as error:
        return {"status": "RECORDED_ONLY", "readyz": type(error).__name__}
    return {"status": "RECORDED_ONLY", "readyzHttpStatus": status}


# --- the report ------------------------------------------------------------------


def validate_evidence(evidence: dict[str, Any]) -> None:
    """This collector's own checks. A pass may not be asserted by hand."""
    if evidence.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError("schemaVersion mismatch")
    if evidence.get("criteria") != CRITERIA:
        raise ValueError("criteria binding mismatch")
    observations = evidence.get("observations") or {}
    if set(observations) != set(REQUIRED):
        raise ValueError("observations must be exactly the required ones")
    for name, observation in observations.items():
        if observation.get("status") not in STATUSES:
            raise ValueError(f"{name} has no recognised status")
    if evidence.get("verdict") != smoke_verdict(observations):
        raise ValueError("verdict was not recomputed from observations")
    if evidence.get("acceptanceClaim") is not (evidence.get("verdict") == "PASS"):
        raise ValueError("acceptanceClaim must follow the recomputed verdict")
    if not COMMIT_PATTERN.fullmatch(str(evidence.get("codeSha") or "")):
        raise ValueError("codeSha must be an exact 40-hex commit")
    provenance = evidence.get("provenance") or {}
    if provenance.get("workingTreeClean") is not True or provenance.get("contentClean") is not True:
        # codeSha names a commit. On a dirty tree it names bytes that were never in it.
        raise ValueError("evidence source tree must be clean")
    source = evidence.get("source") or {}
    if source.get("verificationDisabled") is not False:
        raise ValueError("certificate verification is never disabled")
    if source.get("resolutionOverridden") is not False:
        raise ValueError("name resolution is never overridden")
    if source.get("keyLoggingDisabled") is not True:
        raise ValueError("TLS key logging must be off")
    for field in ("caBundleSha256", "controlPlaneConfigSha256", "trustBundleSha256"):
        if not SHA256_PATTERN.fullmatch(str(source.get(field) or "")):
            raise ValueError(f"{field} must identify the input by SHA-256")
    if source.get("runEnvironment") not in RUN_ENVIRONMENTS:
        raise ValueError("runEnvironment must say where the run happened")
    if not isinstance(source.get("allowedRootSha256"), list) or not source["allowedRootSha256"]:
        raise ValueError("the approved trust anchors must be recorded")


def render_markdown(evidence: dict[str, Any]) -> str:
    source = evidence["source"]
    lines = [
        f"# Intranet end-to-end smoke — {evidence['verdict']}",
        "",
        f"- code SHA: `{evidence['codeSha']}`",
        f"- collector SHA-256: `{evidence['collectorSha256']}`",
        f"- observed: {source['observedAt']}",
        f"- ran in: **{source['runEnvironment']}**",
        f"- issuer under test: `{source['issuer']}` (taken from the control plane's own config)",
        f"- control plane config SHA-256: `{source['controlPlaneConfigSha256']}`",
        f"- trust bundle SHA-256: `{source['trustBundleSha256']}`",
        f"- CA bundle SHA-256: `{source['caBundleSha256']}` — a trust anchor, not a pin",
        f"- approved anchors: {len(source['allowedRootSha256'])}",
        f"- control plane: `{source['controlPlaneHost']}:{source['controlPlanePort']}`"
        f" (readyz: {source.get('readyz', {}).get('readyzHttpStatus', 'not observed')})",
        "",
        "| observation | status | detail |",
        "|---|---|---|",
    ]
    for name in REQUIRED:
        observation = evidence["observations"][name]
        detail = ", ".join(f"{k}={v}" for k, v in observation.items() if k != "status")
        lines.append(f"| `{name}` | {observation['status']} | {detail or '—'} |")
    lines += [
        "",
        "The issuer, the client id and the trusted key ids come from the control plane's",
        "configuration, not from this command line, and the TLS target is derived from that",
        "issuer -- so the SNI, the Host header and the announced issuer are one string.",
        "Verification cannot be turned off and resolution cannot be substituted. Once a name",
        "has resolved, a connection or TLS failure is a failure, not a missing precondition.",
        "",
    ]
    return "\n".join(lines)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n", 1)[0])
    result.add_argument(
        "--control-plane-config",
        required=True,
        type=Path,
        help="the control plane's INV_API_CONFIG file: the issuer, client and trusted keys",
    )
    result.add_argument(
        "--ca-bundle",
        required=True,
        type=Path,
        help="the internal CA chain. There is no option to skip verification.",
    )
    result.add_argument(
        "--allowed-root-sha256",
        required=True,
        action="append",
        metavar="HEX",
        help="SHA-256 of a root that may anchor this chain; repeat for more than one",
    )
    result.add_argument(
        "--control-plane-url",
        required=True,
        help="loopback http URL of the control plane under test",
    )
    result.add_argument(
        "--run-environment",
        required=True,
        choices=RUN_ENVIRONMENTS,
        help="where this ran; a resolving environment is not the operator workstation",
    )
    result.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    result.add_argument("--label")
    result.add_argument("--executor", default="claude")
    return result


def run(args, deadline: Deadline, now: dt.datetime) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Every observation, plus the facts the report binds them to."""
    observations: dict[str, dict[str, Any]] = {}
    config = read_control_plane_configuration(args.control_plane_config)
    pem = args.ca_bundle.read_text(encoding="utf-8")
    ca_sha = sha256_text(pem)
    allowed = {value.strip().lower() for value in args.allowed_root_sha256}
    for value in allowed:
        if not SHA256_PATTERN.fullmatch(value):
            raise SmokeRefused("--allowed-root-sha256 takes 64-hex digests")
    context = trusted_context(pem, allowed)
    observations["controlPlaneConfigurationBound"] = passed(
        issuerIsCanonical=True,
        clientIdSha256=sha256_text(config["clientId"]),
        trustedKeyCount=len(config["trustedKids"]),
    )

    observations["idpNameResolves"], addresses = observe_name(config["host"])
    realm_path = urlsplit(config["issuer"]).path
    if not addresses:
        reason = "the issuer's host does not resolve on this host"
        for name in ("idpHttpsVerified", "idpDiscoveryIssuer", "portalClientKnown",
                     "idpJwksMatchesTrustBundle", "passwordGrantRefused",
                     "clientCredentialsRefused"):
            observations[name] = blocked(reason)
    else:
        observations["idpHttpsVerified"], body, _ = observe_https(
            context, config["host"], config["port"],
            f"{realm_path}/.well-known/openid-configuration", deadline,
        )
        document = None
        if observations["idpHttpsVerified"]["status"] == "MEASURED_PASS":
            observations["idpDiscoveryIssuer"], document = observe_discovery(body, config["issuer"])
        else:
            observations["idpDiscoveryIssuer"] = failed("https to the issuer's host did not succeed")
        if document is not None and observations["idpDiscoveryIssuer"]["status"] == "MEASURED_PASS":
            observations["idpJwksMatchesTrustBundle"] = observe_jwks(
                context, document, config, deadline
            )
        else:
            observations["idpJwksMatchesTrustBundle"] = failed("discovery did not succeed")
        observations["portalClientKnown"] = observe_client_known(context, config, deadline)
        observations["passwordGrantRefused"] = observe_grant_refused(
            context, config, deadline,
            {"grant_type": "password", "username": SYNTHETIC_ACCOUNT,
             "password": secrets.token_urlsafe(8), "scope": "openid"},
            "the password grant",
        )
        observations["clientCredentialsRefused"] = observe_grant_refused(
            context, config, deadline, {"grant_type": "client_credentials", "scope": "openid"},
            "the client-credentials grant",
        )

    observations["controlPlaneRejectsBadToken"] = observe_control_plane(
        args.control_plane_url, deadline,
        authorization="Bearer " + signed_but_invalid_token(config, now),
        label="signed-but-invalid",
    )
    observations["controlPlaneRejectsMissingToken"] = observe_control_plane(
        args.control_plane_url, deadline, authorization=None, label="no-authorization",
    )

    facts = {
        "issuer": config["issuer"],
        "controlPlaneConfigSha256": config["configSha256"],
        "trustBundleSha256": config["bundleSha256"],
        "caBundleSha256": ca_sha,
        "allowedRootSha256": sorted(allowed),
        "clientIdSha256": sha256_text(config["clientId"]),
        "keyLoggingDisabled": getattr(context, "keylog_filename", None) is None,
        "readyz": observe_readyz(args.control_plane_url, deadline),
    }
    return observations, facts


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    started = dt.datetime.now(dt.timezone.utc)
    deadline = Deadline(DEADLINE_SECONDS)
    provenance = collect_provenance_at_root(args.executor)
    try:
        observations, facts = run(args, deadline, started)
    except DeadlineExceeded as refusal:
        print(f"refused: {refusal}", file=sys.stderr)
        return 2
    except SmokeRefused as refusal:
        print(f"refused: {refusal}", file=sys.stderr)
        return 2
    except OSError as error:
        print(f"refused: {type(error).__name__}", file=sys.stderr)
        return 2
    finished = dt.datetime.now(dt.timezone.utc)
    verdict = smoke_verdict(observations)
    evidence = {
        "schemaVersion": SCHEMA_VERSION,
        "codeSha": provenance.get("commit_sha"),
        "collectorSha256": collector_sha256(__file__),
        "criteria": CRITERIA,
        "provenance": {
            "branch": provenance.get("branch"),
            "workingTreeClean": provenance.get("working_tree_clean_status"),
            "contentClean": provenance.get("content_clean_diff"),
            "executor": provenance.get("executor"),
        },
        "source": {
            "observedAt": iso(started),
            "sourceStartedAt": iso(started),
            "sourceFinishedAt": iso(finished),
            "runEnvironment": args.run_environment,
            "controlPlaneHost": control_plane_label(args.control_plane_url),
            "controlPlanePort": urlsplit(args.control_plane_url).port or 80,
            "verificationDisabled": False,
            "resolutionOverridden": False,
            "inputBindingSha256": input_binding_sha256(
                {
                    "controlPlaneConfigSha256": facts["controlPlaneConfigSha256"],
                    "trustBundleSha256": facts["trustBundleSha256"],
                    "caBundleSha256": facts["caBundleSha256"],
                    "allowedRootSha256": facts["allowedRootSha256"],
                    "controlPlaneUrl": control_plane_label(args.control_plane_url),
                }
            ),
            **facts,
        },
        "observations": observations,
        "verdict": verdict,
        "acceptanceClaim": verdict == "PASS",
    }
    validate_evidence(evidence)
    label = args.label or default_label("intranet-e2e-smoke", evidence["codeSha"])
    if not LABEL_PATTERN.fullmatch(label):
        print(f"refused: label {label!r} is not a safe file name", file=sys.stderr)
        return 2
    serialised = json.dumps(evidence, ensure_ascii=False, sort_keys=True)
    rendered = render_markdown(evidence)
    summary = json.dumps({"verdict": verdict})
    for text in (serialised, rendered, summary):
        assert_publishable(text)
    json_path, markdown_path = write_evidence(
        evidence, args.out_dir, label, render_markdown=render_markdown
    )
    print(json.dumps({"verdict": verdict, "json": str(json_path), "markdown": str(markdown_path)}))
    return EXIT_BY_VERDICT[verdict]


if __name__ == "__main__":
    raise SystemExit(main())
