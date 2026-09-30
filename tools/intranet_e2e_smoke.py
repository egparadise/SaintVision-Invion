"""End-to-end smoke check across the intranet identity path.

Separate pieces of this system have each been measured on their own: the identity
provider serves https, the trust bundle builder and the verifier agree, the realm
matches the token contract. None of that says the pieces line up *as deployed* --
that the name resolves, that the certificate the provider presents is the one the
internal CA issued, that the issuer string in its discovery document is the string
the control plane was configured with, and that the control plane refuses a token
it should refuse. This walks that path and says what it found.

What it will not do:

* **It never turns verification off.** There is no flag for it. A smoke check that
  can be told to skip the certificate is a smoke check that will eventually be run
  that way, and its PASS would mean nothing.
* **It never substitutes its own name resolution.** If ``idp.sv.lan`` does not
  resolve, the answer is ``BLOCKED_EXTERNAL`` with ``hosts-not-applied``, not a
  quiet fallback to an address. The deployment either resolves the name or it does
  not, and pretending otherwise would hide the one thing an operator still has to
  do.
* **It never uses a real user's password grant.** That grant is deliberately
  disabled on the portal client, and this check confirms the refusal using a
  synthetic account name -- confirming a door is locked without holding a key.

Every observation carries one of the house statuses, and the run's verdict is
recomputed from them: ``FAIL`` if anything was measured wrong, ``BLOCKED_EXTERNAL``
if an external precondition is missing, ``NOT_OBSERVED`` if an input was simply not
supplied, ``PASS`` only when every required observation was measured and held.

The report is redacted by construction: no address, no token, no key material. A
resolved address appears only as a count, a key id only as its SHA-256.

Exit codes: 0 PASS, 1 FAIL, 3 BLOCKED_EXTERNAL or NOT_OBSERVED.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import socket
import ssl
from pathlib import Path
import sys
from typing import Any
from urllib.parse import urlencode, urlsplit

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.operational_evidence import (  # noqa: E402
    COMMIT_PATTERN,
    SHA256_PATTERN,
    STATUSES,
    LABEL_PATTERN,
    assert_no_secrets,
    collect_provenance_at_root,
    collector_sha256,
    default_label,
    input_binding_sha256,
    iso,
    sha256_text,
    write_evidence,
)

SCHEMA_VERSION = "intranet-e2e-smoke:1"
DEFAULT_OUT_DIR = REPO_ROOT / "docs/vault/30_Development/Evidence/intranet-e2e-smoke"
DEFAULT_CONTROL_PLANE = "http://127.0.0.1:8080"
MAX_BODY_BYTES = 262_144
TIMEOUT = 10.0

REQUIRED = (
    "idpNameResolves",
    "idpHttpsVerified",
    "idpDiscoveryIssuer",
    "idpJwksSameOrigin",
    "passwordGrantRefused",
    "clientCredentialsRefused",
    "controlPlaneRejectsBadToken",
    "controlPlaneRejectsMissingToken",
)

CRITERIA = {
    "idpNameResolves": "the system resolver finds the IdP name; no substitute is accepted",
    "idpHttpsVerified": "TLS verifies against the internal CA bundle with hostname checking on",
    "idpDiscoveryIssuer": "the discovery issuer equals the string the control plane is given",
    "idpJwksSameOrigin": "jwks_uri shares the issuer's origin and serves an RS256 signing key",
    "passwordGrantRefused": "the public client refuses a password grant (synthetic account only)",
    "clientCredentialsRefused": "the public client refuses a client-credentials grant",
    "controlPlaneRejectsBadToken": "GET /v1/session with a malformed bearer answers 401",
    "controlPlaneRejectsMissingToken": "GET /v1/session with no Authorization answers 401",
}

#: OAuth errors that mean "this client may not use this grant", as opposed to
#: "those credentials were wrong". Only the former proves the grant is disabled.
GRANT_DISABLED_ERRORS = frozenset({"unauthorized_client", "invalid_client", "unsupported_grant_type"})
#: A username that cannot exist. Used so a refusal can be observed without a key.
SYNTHETIC_ACCOUNT = "smoke-nonexistent-account"

#: Where the run happened. A report from a place where the name resolves is not a
#: report about a place where it does not, and the two must not be confused after
#: the fact. This tool never arranges resolution itself either way.
RUN_ENVIRONMENTS = ("operator-workstation", "idp-node-container")


def origin(url: str) -> tuple[str, str, int | None]:
    """Scheme, host and port -- what "the same server" has to mean here.

    Deliberately a local copy: this branch is based on landed integration, which does
    not carry the trust-bundle builder, and a smoke check should not need an unlanded
    module to run. If the two ever disagree, that is a real defect, so the shapes are
    kept identical on purpose.
    """
    parts = urlsplit(url)
    if parts.username or parts.password or parts.fragment or not parts.hostname:
        raise SmokeAborted("a URL with credentials, a fragment or no host is refused")
    return parts.scheme.lower(), parts.hostname.lower(), parts.port


class SmokeAborted(RuntimeError):
    """A precondition failed in a way that makes later observations meaningless."""


def blocked(reason: str) -> dict[str, Any]:
    return {"status": "BLOCKED_EXTERNAL", "reason": reason}


def unmeasured(reason: str) -> dict[str, Any]:
    return {"status": "NOT_OBSERVED", "reason": reason}


def failed(reason: str, **facts: Any) -> dict[str, Any]:
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
    if all(status == "MEASURED_PASS" for status in statuses):
        return "PASS"
    return "NOT_OBSERVED"


EXIT_BY_VERDICT = {"PASS": 0, "FAIL": 1, "BLOCKED_EXTERNAL": 3, "NOT_OBSERVED": 3}


def control_plane_label(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    return "loopback" if host in {"127.0.0.1", "::1", "localhost"} else "non-loopback"


def trusted_context(ca_bundle: Path) -> ssl.SSLContext:
    """A context that verifies. There is deliberately no way to get one that does not."""
    context = ssl.create_default_context(cafile=str(ca_bundle))
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    return context


def resolve(host: str) -> list[str]:
    """Only the system resolver. A caller-supplied address would defeat the check."""
    try:
        return sorted({info[4][0] for info in socket.getaddrinfo(host, None)})
    except socket.gaierror:
        return []


def https_request(
    context: ssl.SSLContext, host: str, port: int, path: str, *, method="GET", body=None, headers=None
) -> tuple[int, bytes]:
    """One request over verified TLS, with a bounded read."""
    request_headers = {"Host": host, "Connection": "close", "Accept": "application/json"}
    request_headers.update(headers or {})
    payload = b""
    if body is not None:
        payload = body.encode() if isinstance(body, str) else body
        request_headers["Content-Type"] = "application/x-www-form-urlencoded"
        request_headers["Content-Length"] = str(len(payload))
    head = f"{method} {path} HTTP/1.1\r\n" + "".join(
        f"{key}: {value}\r\n" for key, value in request_headers.items()
    )
    with socket.create_connection((host, port), timeout=TIMEOUT) as raw:
        with context.wrap_socket(raw, server_hostname=host) as tls:
            tls.sendall(head.encode() + b"\r\n" + payload)
            chunks, total = [], 0
            while total <= MAX_BODY_BYTES:
                block = tls.recv(65536)
                if not block:
                    break
                chunks.append(block)
                total += len(block)
    return split_response(b"".join(chunks))


def plain_request(url: str, *, headers=None) -> tuple[int, bytes]:
    """Loopback only. A loopback request never crosses the network."""
    parts = urlsplit(url)
    if parts.scheme != "http" or parts.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise SmokeAborted("the control plane URL must be loopback http or https")
    request_headers = {"Host": parts.netloc, "Connection": "close", "Accept": "application/json"}
    request_headers.update(headers or {})
    head = f"GET {parts.path or '/'} HTTP/1.1\r\n" + "".join(
        f"{key}: {value}\r\n" for key, value in request_headers.items()
    )
    with socket.create_connection((parts.hostname, parts.port or 80), timeout=TIMEOUT) as raw:
        raw.sendall(head.encode() + b"\r\n")
        chunks, total = [], 0
        while total <= MAX_BODY_BYTES:
            block = raw.recv(65536)
            if not block:
                break
            chunks.append(block)
            total += len(block)
    return split_response(b"".join(chunks))


def split_response(raw: bytes) -> tuple[int, bytes]:
    head, _, body = raw.partition(b"\r\n\r\n")
    if not head:
        raise SmokeAborted("empty response")
    status_line = head.split(b"\r\n", 1)[0].decode("latin-1")
    parts = status_line.split()
    status = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    if b"Transfer-Encoding: chunked" in head or b"transfer-encoding: chunked" in head:
        body = dechunk(body)
    return status, body


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
        raise SmokeAborted("response was not a JSON object")
    return json.loads(text[start : end + 1])


#: Anything that looks like an address must not reach the report. The rule is checked
#: on the serialised output, not trusted to the code that builds it.
IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
IPV6 = re.compile(r"\b[0-9a-fA-F]{0,4}(?::[0-9a-fA-F]{0,4}){2,}\b")
#: ISO timestamps carry colons and would read as IPv6. They are removed first, so
#: the guard stays strict about addresses without flagging every observation time.
TIMESTAMP = re.compile(
    r"\d{4}-\d{2}-\d{2}T[\d:.]+(?:Z|[+-]\d{2}:\d{2})"
)


def assert_no_addresses(text: str) -> None:
    scrubbed = TIMESTAMP.sub("<time>", text)
    found = IPV4.findall(scrubbed) + IPV6.findall(scrubbed)
    if found:
        raise SmokeAborted(f"the report would contain {len(found)} address-like value(s)")


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
    if not SHA256_PATTERN.fullmatch(str(source.get("caBundleSha256") or "")):
        raise ValueError("the CA bundle must be identified by SHA-256")
    if source.get("runEnvironment") not in RUN_ENVIRONMENTS:
        raise ValueError("runEnvironment must say where the run happened")


# --- the observations ------------------------------------------------------------


def observe_name(host: str) -> tuple[dict[str, Any], list[str]]:
    """Resolution is the first gate, and it is the one an operator still owes.

    No address is recorded: a count is enough to say the name resolves, and the
    address is the thing this report is not allowed to carry.
    """
    addresses = resolve(host)
    if not addresses:
        return blocked("hosts-not-applied"), []
    families = sorted({"ipv6" if ":" in address else "ipv4" for address in addresses})
    return passed(resolvedAddressCount=len(addresses), addressFamilies=families), addresses


def observe_https(context: ssl.SSLContext, host: str, port: int) -> tuple[dict[str, Any], Any]:
    try:
        status, body = https_request(context, host, port, "/realms/saintvision/.well-known/openid-configuration")
    except ssl.SSLCertVerificationError as error:
        return failed("certificate did not verify", reason=error.verify_message or "unverified"), None
    except OSError:
        return blocked("idp-unreachable"), None
    if status != 200:
        return failed("discovery did not answer 200", httpStatus=status), None
    with socket.create_connection((host, port), timeout=TIMEOUT) as raw:
        with context.wrap_socket(raw, server_hostname=host) as tls:
            peer = tls.getpeercert()
            protocol = tls.version()
    names = sorted(value for kind, value in peer.get("subjectAltName", ()) if kind == "DNS")
    addresses = sum(1 for kind, _ in peer.get("subjectAltName", ()) if kind != "DNS")
    return (
        passed(
            tlsVersion=protocol,
            hostnameCheckEnabled=context.check_hostname,
            verifyMode=context.verify_mode.name,
            leafCommonName=dict(pair[0] for pair in peer["subject"]).get("commonName"),
            leafSanDnsNames=names,
            leafSanAddressCount=addresses,
            leafNotAfterDate=expiry_date(peer.get("notAfter")),
        ),
        body,
    )


def expiry_date(not_after: Any) -> str | None:
    """`Dec 28 23:05:05 2026 GMT` -> `2026-12-28`.

    The clock time is dropped deliberately: it reads as an IPv6 address to the guard
    below, and a certificate's expiry day is what anyone reading this needs.
    """
    if not isinstance(not_after, str) or not not_after:
        return None
    try:
        return dt.datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").date().isoformat()
    except ValueError:
        return "unparsed"


def observe_discovery(body: Any, expected_issuer: str) -> tuple[dict[str, Any], Any]:
    try:
        document = as_json(body)
    except (SmokeAborted, json.JSONDecodeError):
        return failed("discovery was not JSON"), None
    issuer = document.get("issuer")
    if issuer != expected_issuer:
        # The issuer is not a secret -- the control plane is configured with it -- but
        # only the mismatch is worth recording, not the wrong value on repeat.
        return failed("issuer does not match the configured issuer", issuerMatches=False), document
    return passed(issuer=issuer, pkceMethods=document.get("code_challenge_methods_supported")), document


def observe_jwks(
    context: ssl.SSLContext, document: Any, issuer: str, host: str, port: int
) -> dict[str, Any]:
    uri = (document or {}).get("jwks_uri")
    if not isinstance(uri, str) or not uri:
        return failed("discovery published no jwks_uri")
    try:
        if origin(uri) != origin(issuer):
            return failed("jwks_uri is on another origin")
    except Exception:
        return failed("jwks_uri is not a usable URL")
    try:
        status, body = https_request(context, host, port, urlsplit(uri).path)
        keys = as_json(body).get("keys")
    except (OSError, SmokeAborted, json.JSONDecodeError):
        return blocked("jwks-unreachable")
    if status != 200 or not isinstance(keys, list) or not keys:
        return failed("jwks did not serve a key set", httpStatus=status)
    signing = [key for key in keys if key.get("alg") == "RS256" and key.get("use") == "sig"]
    if not signing:
        return failed("no RS256 signing key is published", keyCount=len(keys))
    return passed(
        keyCount=len(keys),
        signingKeyCount=len(signing),
        algorithms=sorted({str(key.get("alg")) for key in keys}),
        signingKidSha256=sorted(sha256_text(str(key.get("kid"))) for key in signing),
    )


def observe_grant_refused(
    context: ssl.SSLContext, host: str, port: int, client_id: str, form: dict[str, str], label: str
) -> dict[str, Any]:
    """A refusal observed without holding a credential.

    The password grant is disabled on this client on purpose, so the way to confirm it
    is to ask for one with an account that cannot exist: a client that may not use the
    grant is refused on the grant, before any account is considered. A refusal naming
    bad credentials would mean the grant is *enabled*, which is the finding.
    """
    try:
        status, body = https_request(
            context, host, port, "/realms/saintvision/protocol/openid-connect/token",
            method="POST", body=urlencode({**form, "client_id": client_id}),
        )
    except OSError:
        return blocked("token-endpoint-unreachable")
    error = ""
    try:
        error = str(as_json(body).get("error") or "")
    except (SmokeAborted, json.JSONDecodeError):
        pass
    if status == 200:
        return failed(f"{label} was granted", httpStatus=200)
    if error in GRANT_DISABLED_ERRORS:
        return passed(httpStatus=status, oauthError=error)
    return failed(
        f"{label} was refused, but not as a disabled grant",
        httpStatus=status,
        oauthError=error or "unnamed",
    )


def observe_control_plane(url: str, *, authorization: str | None) -> dict[str, Any]:
    """The control plane must refuse, and refusal is all this asks of it."""
    headers = {"Authorization": authorization} if authorization else {}
    try:
        status, body = plain_request(url.rstrip("/") + "/v1/session", headers=headers)
    except OSError:
        return blocked("control-plane-not-running")
    except SmokeAborted as error:
        return unmeasured(str(error))
    code = ""
    try:
        document = as_json(body)
        code = str(document.get("code") or document.get("type") or "")
    except (SmokeAborted, json.JSONDecodeError):
        pass
    if status == 401:
        return passed(httpStatus=401, problemCode=code or "unnamed")
    return failed("the control plane did not answer 401", httpStatus=status)


def render_markdown(evidence: dict[str, Any]) -> str:
    source = evidence["source"]
    lines = [
        f"# Intranet end-to-end smoke — {evidence['verdict']}",
        "",
        f"- code SHA: `{evidence['codeSha']}`",
        f"- collector SHA-256: `{evidence['collectorSha256']}`",
        f"- observed: {source['observedAt']}",
        f"- ran in: **{source['runEnvironment']}**",
        f"- IdP name: `{source['idpHost']}` (no address is recorded)",
        f"- expected issuer: `{source['expectedIssuer']}`",
        f"- CA bundle SHA-256: `{source['caBundleSha256']}` — a trust anchor, not a pin",
        f"- control plane: `{source['controlPlaneHost']}:{source['controlPlanePort']}`",
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
        "Certificate verification is on and cannot be turned off; name resolution is the",
        "system resolver and has no override. A `BLOCKED_EXTERNAL` here is a precondition",
        "an operator still owes, not a defect to route around.",
        "",
    ]
    return "\n".join(lines)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n", 1)[0])
    result.add_argument("--idp-host", default="idp.sv.lan")
    result.add_argument("--idp-port", type=int, default=443)
    result.add_argument("--issuer", default="https://idp.sv.lan/realms/saintvision")
    result.add_argument(
        "--ca-bundle",
        required=True,
        type=Path,
        help="the internal CA chain. There is no option to skip verification.",
    )
    result.add_argument("--portal-client", default="sv-portal")
    result.add_argument("--control-plane-url", default=DEFAULT_CONTROL_PLANE)
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


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    started = dt.datetime.now(dt.timezone.utc)
    provenance = collect_provenance_at_root(args.executor)
    context = trusted_context(args.ca_bundle)

    observations: dict[str, dict[str, Any]] = {}
    observations["idpNameResolves"], addresses = observe_name(args.idp_host)

    if not addresses:
        # Everything downstream needs the name. Saying so once is honest; inventing an
        # address to keep going would make the rest of the report meaningless.
        reason = "the IdP name does not resolve on this host"
        for name in REQUIRED[1:6]:
            observations[name] = blocked(reason)
    else:
        observations["idpHttpsVerified"], body = observe_https(context, args.idp_host, args.idp_port)
        document = None
        if observations["idpHttpsVerified"]["status"] == "MEASURED_PASS":
            observations["idpDiscoveryIssuer"], document = observe_discovery(body, args.issuer)
        else:
            observations["idpDiscoveryIssuer"] = blocked("https did not verify")
        if document is not None:
            observations["idpJwksSameOrigin"] = observe_jwks(
                context, document, args.issuer, args.idp_host, args.idp_port
            )
        else:
            observations["idpJwksSameOrigin"] = blocked("discovery unavailable")
        observations["passwordGrantRefused"] = observe_grant_refused(
            context, args.idp_host, args.idp_port, args.portal_client,
            {"grant_type": "password", "username": SYNTHETIC_ACCOUNT, "password": "x", "scope": "openid"},
            "the password grant",
        )
        observations["clientCredentialsRefused"] = observe_grant_refused(
            context, args.idp_host, args.idp_port, args.portal_client,
            {"grant_type": "client_credentials", "scope": "openid"},
            "the client-credentials grant",
        )

    observations["controlPlaneRejectsBadToken"] = observe_control_plane(
        args.control_plane_url, authorization="Bearer not.a.valid.token"
    )
    observations["controlPlaneRejectsMissingToken"] = observe_control_plane(
        args.control_plane_url, authorization=None
    )

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
            "idpHost": args.idp_host,
            "expectedIssuer": args.issuer,
            "caBundleSha256": sha256_text(args.ca_bundle.read_text(encoding="utf-8")),
            "controlPlaneHost": control_plane_label(args.control_plane_url),
            "controlPlanePort": urlsplit(args.control_plane_url).port or 80,
            "verificationDisabled": False,
            "resolutionOverridden": False,
            "inputBindingSha256": input_binding_sha256(
                {
                    "idpHost": args.idp_host,
                    "issuer": args.issuer,
                    "portalClient": args.portal_client,
                    "controlPlaneUrl": args.control_plane_url,
                }
            ),
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
    assert_no_secrets(serialised)
    assert_no_addresses(serialised)
    json_path, markdown_path = write_evidence(
        evidence, args.out_dir, label, render_markdown=render_markdown
    )
    print(json.dumps({"verdict": verdict, "json": str(json_path), "markdown": str(markdown_path)}))
    return EXIT_BY_VERDICT[verdict]


if __name__ == "__main__":
    raise SystemExit(main())
