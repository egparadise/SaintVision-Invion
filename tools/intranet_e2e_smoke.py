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

SCHEMA_VERSION = "intranet-e2e-smoke:3"
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
#: The only statuses an OAuth 2.0 token endpoint uses to refuse: 400 for a request or a
#: grant it will not honour, 401 for a client it cannot authenticate (RFC 6749 section
#: 5.2). A 404, 502 or 503 carrying `"error": "unauthorized_client"` came from something
#: that is not this provider's token endpoint -- a proxy page, a maintenance stub, a
#: sibling service -- and a named error inside such a body says nothing about the
#: client's grant configuration. Reading the error without the status let
#: (503, unauthorized_client) pass as a locked door.
TOKEN_REFUSAL_STATUSES = frozenset({400, 401})

#: The verifier accepts a trust bundle with exactly these keys and a window no longer
#: than seven days (``inv.identity.AccessTokens._keys``). A bundle outside that is one the
#: control plane would refuse, so a report that treats it as configuration is describing
#: something that cannot be running.
BUNDLE_KEYS = frozenset({"issuer", "expiresAt", "keys"})
MAX_BUNDLE_TTL_SECONDS = 7 * 86_400
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
        "configuration, whose bytes are hashed into this report, and the listening control "
        "plane is not contradicting that configuration: refuted when it is not ready or "
        "when it is ready despite a bundle its verifier would refuse, and reported "
        "NOT_BOUND rather than passed while nothing it exposes can confirm it"
    ),
    "idpNameResolves": "the system resolver finds the issuer's host; no substitute is accepted",
    "idpHttpsVerified": (
        "TLS to the issuer's own host verifies against an allowed internal root, with "
        "hostname checking on"
    ),
    "idpDiscoveryIssuer": "the announced issuer equals the configured issuer, on the same origin",
    "portalClientKnown": "the configured client id is known to the provider",
    "idpJwksMatchesTrustBundle": (
        "the RS256 signing keys the provider serves are exactly the keys the control plane "
        "trusts, key material included: no rogue key beside them, none of them missing, and "
        "no trusted key id carrying different material"
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


def key_material(key: dict[str, Any]) -> tuple[str, ...]:
    """What makes a key that key, not just what labels it.

    Comparing key ids alone would accept a provider publishing an attacker's modulus under
    a trusted key id -- the substitution a trust bundle exists to prevent. The modulus and
    exponent are the key; the type, algorithm and use are the terms on which it may be
    used, so a change in any of them is a different key.
    """
    return tuple(str(key.get(field)) for field in ("kty", "alg", "use", "n", "e"))


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
    if not Path(bundle_path).is_absolute():
        # A relative jwks_file is read against whatever directory the reader started in.
        # The control plane starts in its own, so the two would be different files while
        # this report hashed one of them and named the other.
        raise SmokeRefused("jwks_file must be an absolute path to be the same file for both")
    bundle_raw = Path(bundle_path).read_bytes()
    try:
        bundle = json.loads(bundle_raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise SmokeRefused(f"the trust bundle is not JSON: {type(error).__name__}")
    trusted: dict[str, tuple[str, ...]] = {}
    for key in bundle.get("keys") or []:
        if not isinstance(key, dict):
            continue
        kid = key.get("kid")
        if not isinstance(kid, str) or not kid:
            continue
        if kid in trusted:
            raise SmokeRefused("the trust bundle repeats a key id")
        trusted[kid] = key_material(key)
    if not trusted:
        raise SmokeRefused("the trust bundle carries no keys")
    if bundle.get("issuer") != issuer:
        raise SmokeRefused("the trust bundle issuer does not match the configured issuer")
    # Whether this bundle is one the verifier that loads it would accept. Not a refusal:
    # an expired bundle is a live defect worth reporting with evidence, and combined with
    # a ready control plane it is proof the process is running some other file.
    defects = []
    if set(bundle) != BUNDLE_KEYS:
        defects.append("bundle-keys-are-not-exactly-issuer-expiresAt-keys")
    expires_at = bundle.get("expiresAt")
    remaining = None
    if type(expires_at) is not int:
        defects.append("expiresAt-is-not-an-integer")
    else:
        remaining = expires_at - int(dt.datetime.now(dt.timezone.utc).timestamp())
        if remaining <= 0:
            defects.append("bundle-has-expired")
        elif remaining > MAX_BUNDLE_TTL_SECONDS:
            defects.append("bundle-window-exceeds-the-seven-day-ceiling")
    return {
        "issuer": issuer,
        "host": host,
        "port": port,
        "clientId": clients[0],
        "audience": audience,
        "trustedKids": sorted(trusted),
        "trustedKeys": trusted,
        "bundleDefects": defects,
        "bundleSecondsRemaining": remaining,
        "configSha256": hashlib.sha256(raw).hexdigest(),
        "bundleSha256": hashlib.sha256(bundle_raw).hexdigest(),
    }


# --- TLS built explicitly, from bytes read once ------------------------------------


def certificate_authorities(context: ssl.SSLContext, pem: str) -> list[str]:
    """SHA-256 of every certificate the bundle loaded, each checked to really be a CA.

    ``context.get_ca_certs()`` cannot be the source, and an earlier version of this
    function used it. OpenSSL's store lists CA certificates, so a self-signed certificate
    with basicConstraints CA:FALSE is loaded into the store, is usable as an anchor for
    itself, and is absent from that list. Measured here: a bundle of one approved root plus
    one rogue self-signed leaf gives ``cert_store_stats()`` ``{'x509': 2, 'x509_ca': 1}``,
    ``get_ca_certs()`` returns only the root, and TLS to a server presenting that leaf
    verifies. Both the CA check below and the caller's allowlist were reading a list the
    rogue certificate was never on.

    So the PEM is parsed directly and every certificate in it is checked, and the count is
    reconciled against ``cert_store_stats()['x509']`` -- if OpenSSL loaded something this
    parse did not see, that is a refusal rather than a silent gap.
    """
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes

    try:
        parsed = x509.load_pem_x509_certificates(pem.encode("utf-8"))
    except (ValueError, TypeError) as error:
        raise SmokeRefused(
            f"the CA bundle is not readable PEM: {type(error).__name__}"
        ) from None
    loaded = context.cert_store_stats().get("x509")
    if loaded != len(parsed):
        raise SmokeRefused(
            f"the trust store holds {loaded} certificate(s) but the bundle parsed as "
            f"{len(parsed)}: something was loaded that was not checked"
        )
    anchors = []
    for certificate in parsed:
        try:
            basic = certificate.extensions.get_extension_for_class(x509.BasicConstraints).value
        except x509.ExtensionNotFound:
            raise SmokeRefused(
                "a certificate in the CA bundle has no basicConstraints and cannot be a CA"
            ) from None
        if not basic.ca:
            raise SmokeRefused("a certificate in the CA bundle is not a certificate authority")
        anchors.append(certificate.fingerprint(hashes.SHA256()).hex())
    # The count above catches a certificate loaded but absent from this PEM. This catches
    # the reverse for the part of the store that can be listed: a CA OpenSSL is trusting
    # that the bytes handed to this function do not contain.
    listed = {hashlib.sha256(der).hexdigest() for der in context.get_ca_certs(binary_form=True)}
    if not listed <= set(anchors):
        raise SmokeRefused("the trust store lists an authority the checked bundle does not")
    return sorted(anchors)


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
    anchors = certificate_authorities(context, pem)
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
    """The whole body, parsed strictly as one JSON object.

    Slicing from the first ``{`` to the last ``}`` reads a JSON object out of a document
    that merely contains braces: an HTML error page with a script block, a JSON document
    with bytes appended after it, two documents concatenated. That is how something which
    is not the provider could have been read as the provider answering. What arrived
    either is the object or is not, and undecodable bytes are a finding rather than
    replacement characters.
    """
    try:
        decoded = body.decode("utf-8")
    except UnicodeError:
        raise SmokeRefused("response was not UTF-8") from None
    try:
        document = json.loads(decoded)
    except json.JSONDecodeError:
        raise SmokeRefused("response was not JSON") from None
    if not isinstance(document, dict):
        raise SmokeRefused("response was not a JSON object")
    return document


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
    served: dict[str, tuple[str, ...]] = {}
    for key in keys:
        if not isinstance(key, dict) or key.get("alg") != "RS256" or key.get("use") != "sig":
            # Encryption keys and other algorithms are published alongside and are not part
            # of this comparison: the verifier will not accept a token signed with one, so
            # their presence is not drift.
            continue
        kid = str(key.get("kid"))
        material = key_material(key)
        if kid in served and served[kid] != material:
            return failed("one key id is published twice with different key material",
                          duplicateKidSha256=sha256_text(kid))
        served[kid] = material
    if not served:
        return failed("no RS256 signing key is published", keyCount=len(keys))
    trusted = config["trustedKeys"]
    # An intersection was the old test, and an intersection is satisfied by a provider that
    # serves one trusted key beside a rogue one: tokens minted with the rogue key are
    # refused, but the provider can also mint accepted ones, so the smoke read PASS while
    # an unaccounted-for signing key was live. The sets must be equal.
    rogue = sorted(set(served) - set(trusted))
    unserved = sorted(set(trusted) - set(served))
    if rogue or unserved:
        return failed(
            "the published signing keys are not exactly the keys the control plane trusts",
            servedSigningKeyCount=len(served),
            trustedKeyCount=len(trusted),
            rogueKidSha256=[sha256_text(kid) for kid in rogue],
            unservedTrustedKidSha256=[sha256_text(kid) for kid in unserved],
        )
    substituted = sorted(kid for kid, material in served.items() if material != trusted[kid])
    if substituted:
        return failed(
            "a trusted key id is published with different key material",
            substitutedKidSha256=[sha256_text(kid) for kid in substituted],
        )
    return passed(
        keyCount=len(keys),
        signingKeyCount=len(served),
        trustedKeyCount=len(trusted),
        keySetsIdentical=True,
        servedSigningKidSha256=[sha256_text(kid) for kid in sorted(served)],
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
    reading as two locked doors. The status is read with the error: only an answer from an
    OAuth token endpoint says anything about what that endpoint knows.
    """
    try:
        status, error = post_token(context, config, deadline, {"grant_type": "client_credentials"})
    except Oversized as oversized:
        return failed(str(oversized))
    except (ssl.SSLError, OSError, SmokeRefused) as failure:
        return failed("the token endpoint could not be reached",
                      readReason=type(failure).__name__)
    if status not in TOKEN_REFUSAL_STATUSES | {200}:
        return failed("the token endpoint did not answer as an OAuth token endpoint",
                      httpStatus=status, oauthError=error or "unnamed")
    if error == UNKNOWN_CLIENT_ERROR:
        return failed("the configured client id is not known to the provider",
                      httpStatus=status, oauthError=error)
    if status in TOKEN_REFUSAL_STATUSES and not error:
        # A refusal with no OAuth error object is not the endpoint's own refusal, so it
        # does not show the client id was recognised on the way to being refused.
        return failed("the token endpoint refused without naming an OAuth error",
                      httpStatus=status)
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
    if status not in TOKEN_REFUSAL_STATUSES:
        # (503, "unauthorized_client") used to pass here. A service that is down is not a
        # grant that is off, and its body is not this provider's answer.
        return failed(f"{label} was refused with a status no OAuth token endpoint uses",
                      httpStatus=status, oauthError=error or "unnamed")
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


#: What the control plane would have to expose for the file this report hashes to be
#: provably the file the listening process loaded. Recorded verbatim so the gap is named in
#: the evidence instead of being implied away by a passing observation.
CONFIGURATION_BINDING_GAP = (
    "the control plane publishes no configuration digest or issuer on an unauthenticated "
    "endpoint, inv.identity.verify collapses every rejection into one AUTH-0050 body, and "
    "its WWW-Authenticate header carries no realm, so a trusted key id with a bad signature "
    "and an unknown key id are indistinguishable from outside and a file digest cannot be "
    "tied to the process that is listening"
)


def observe_configuration_bound(url, config, deadline):
    """Hashing a file proves what the file says, not what the process loaded.

    The earlier version returned MEASURED_PASS from the digest alone: a claim about a file
    dressed as a claim about a deployment. This one refutes where it can and never
    confirms, and it says which it did.

    * unreachable, or ``/readyz`` not 200 -- ``app.py`` answers 503
      ``identity-and-database-configuration-pending`` while ``tokens is None``, and
      ``/readyz`` also loads the bundle through ``tokens._keys()``. Either way this process
      is not serving the configuration under test, and ``/v1/session`` answering 401 does
      not make it ready. MEASURED_FAIL.
    * ready, but the configured bundle is one the verifier would refuse -- expired, or not
      exactly ``{issuer, expiresAt, keys}``. A ready control plane cannot have loaded it, so
      it is running some other file. MEASURED_FAIL, and this is the one positive
      discrimination available.
    * ready, bundle acceptable -- contract-valid trust is loaded, and which file it came
      from is not observable. NOT_BOUND, RECORDED_ONLY, with the gap named.

    This observation is required, so a NOT_BOUND run reports NOT_OBSERVED overall. That is
    the honest state and it is meant to stay visible rather than be absorbed into a pass.
    """
    facts = {
        "controlPlaneConfigSha256": config["configSha256"],
        "trustBundleSha256": config["bundleSha256"],
        "clientIdSha256": sha256_text(config["clientId"]),
        "trustedKeyCount": len(config["trustedKeys"]),
        "issuerIsCanonical": True,
    }
    try:
        status, _, body = plain_request(url, "/readyz", deadline)
    except Oversized as error:
        return failed(str(error), **facts), {"readyz": "oversized"}
    except (OSError, SmokeRefused) as error:
        return (
            failed("the control plane did not answer", readReason=type(error).__name__, **facts),
            {"readyz": type(error).__name__},
        )
    readyz = {"readyzHttpStatus": status}
    if status != 200:
        reason = ""
        try:
            reason = str(as_json(body).get("reason") or "")
        except SmokeRefused:
            pass
        return (
            failed(
                "the control plane is not ready, so it is not serving this configuration",
                httpStatus=status,
                readyzReason=reason or "unnamed",
                **facts,
            ),
            readyz,
        )
    if config["bundleDefects"]:
        return (
            failed(
                "the control plane is ready while the configured trust bundle is one its "
                "verifier would refuse, so it loaded some other bundle",
                bundleDefects=sorted(config["bundleDefects"]),
                **facts,
            ),
            readyz,
        )
    return (
        {
            "status": "RECORDED_ONLY",
            "binding": "NOT_BOUND",
            "identityTrustConfigured": True,
            "bindingGap": CONFIGURATION_BINDING_GAP,
            **facts,
        },
        readyz,
    )


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
        f"- configuration binding: **"
        f"{evidence['observations']['controlPlaneConfigurationBound'].get('binding', 'refuted')}"
        f"**",
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
    observations["controlPlaneConfigurationBound"], readyz = observe_configuration_bound(
        args.control_plane_url, config, deadline
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
        "readyz": readyz,
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
    for text in (serialised, rendered):
        assert_publishable(text)
    json_path, markdown_path = write_evidence(
        evidence, args.out_dir, label, render_markdown=render_markdown
    )
    # File names, not paths: --out-dir is the caller's own input, and an absolute path on
    # this host carries an account name into stdout, which is pasted into PR comments. And
    # the bytes printed are the bytes checked -- the earlier version checked
    # {"verdict": ...} and then printed a larger object containing those paths, so the
    # check did not cover the output at all.
    stdout = {
        "verdict": verdict,
        "json": json_path.name,
        "markdown": markdown_path.name,
        "writtenUnder": "the --out-dir given on the command line",
    }
    printed = json.dumps(stdout, ensure_ascii=False, sort_keys=True)
    assert_publishable(printed)
    print(printed)
    return EXIT_BY_VERDICT[verdict]


if __name__ == "__main__":
    raise SystemExit(main())
