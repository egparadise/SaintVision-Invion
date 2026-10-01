"""Record what a live IdP actually proved, separately from what the tests prove.

`tests/core/test_make_oidc_trust_bundle.py` passing says the builder and the verifier
agree about synthetic keys. It says nothing about whether the identity provider that
is actually running mints tokens this control plane accepts. Those are different
claims and a runbook sentence cannot tell them apart, so this collector produces the
second one as an artifact: a code SHA, a timestamp, the issuer mode, the verdict of
the real `AccessTokens.verify`, and whether the temporary material was cleaned up.

It measures three things and refuses to pass on fewer:

* ``bundleAccepted``      -- the provider's JWKS became a bundle the verifier loads.
* ``liveTokenVerified``   -- a token the provider actually issued passes ``verify``.
* ``tamperedTokenRefused``-- the same verifier rejects a one-character edit of it.

The third matters as much as the second. A verifier that accepts everything would
pass the second check, so measuring acceptance without measuring refusal measures
nothing.

Inputs may be supplied out of band -- the token and the JWKS fetched by whoever has
access and passed as files -- or the JWKS may be fetched here over TLS. Those are
different claims, so the artifact records which one it was in ``jwksTransport``:

* ``out-of-band-file`` -- the keys arrived as a file. **This artifact then says
  nothing about how they travelled.** Whatever verified that transport did so
  elsewhere, and this record must not be read as evidence of it.
* ``verified-https`` -- fetched here, same-origin with the issuer, against the trust
  anchor in ``SSL_CERT_FILE``, whose bytes are recorded as ``caBundleSha256``.

That anchor is a *trust anchor*, not a pin: it says which CA may vouch for the name,
not which certificate must appear. Recording its hash makes the anchor identifiable;
it does not make the leaf fixed.

The token never reaches the evidence -- only its lifetime, and the SHA-256 of the key
id that signed it.

Exit codes follow the house convention: 0 PASS, 1 FAIL, 3 NOT_OBSERVED.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any
from urllib.parse import urlsplit

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
CONTROL_PLANE_SRC = REPO_ROOT / "services" / "control-plane" / "src"
if str(CONTROL_PLANE_SRC) not in sys.path:
    sys.path.insert(0, str(CONTROL_PLANE_SRC))

from tools import make_oidc_trust_bundle as builder  # noqa: E402
from tools.operational_evidence import (  # noqa: E402
    COMMIT_PATTERN,
    SHA256_PATTERN,
    EXIT_BY_VERDICT,
    LABEL_PATTERN,
    assert_no_secrets,
    collect_provenance_at_root,
    collector_sha256,
    default_label,
    input_binding_sha256,
    iso,
    overall_verdict,
    sha256_text,
    write_evidence,
)

SCHEMA_VERSION = "oidc-identity-evidence:2"
#: Which provider was measured. A rehearsal proves the cutover shape on a throwaway
#: instance; it is not evidence about the provider users will actually log in to, and
#: conflating the two is exactly the confusion this field exists to prevent.
PROVIDER_ROLES = ("production", "cutover-rehearsal")
#: How the signing keys reached this run. See the module docstring: only
#: "verified-https" lets the artifact speak about the transport at all.
JWKS_TRANSPORTS = ("out-of-band-file", "verified-https")
DEFAULT_OUT_DIR = REPO_ROOT / "docs/vault/30_Development/Evidence/oidc-identity"
REQUIRED = ("bundleAccepted", "liveTokenVerified", "tamperedTokenRefused")
CRITERIA = {
    "bundleAccepted": "inv.identity.AccessTokens._keys loads the bundle this repo built",
    "liveTokenVerified": "a token the running provider issued passes AccessTokens.verify",
    "tamperedTokenRefused": "the same verifier refuses a one-character payload edit",
}


def unmeasured(reason: str) -> dict[str, Any]:
    return {"status": "NOT_OBSERVED", "reason": reason}


def segment(token: str, index: int) -> dict[str, Any]:
    raw = token.split(".")[index]
    return json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))


def tamper(token: str) -> str:
    """Change one payload character without touching the signature."""
    header, payload, signature = token.split(".")
    replacement = "B" if payload[-1] != "B" else "C"
    return f"{header}.{payload[:-1]}{replacement}.{signature}"


def measure(*, issuer, jwks, token, tenant_id, audience, client_id, now):
    """Run the three measurements, cleaning up the bundle we had to write."""
    observations: dict[str, dict[str, Any]] = {
        name: unmeasured("the measurement did not run") for name in REQUIRED
    }
    facts: dict[str, Any] = {}
    workspace = Path(tempfile.mkdtemp(prefix="oidc-evidence-"))
    try:
        # Imported here so an interpreter that cannot load the control plane produces
        # NOT_OBSERVED with the reason on record, rather than a traceback that leaves
        # no artifact at all.
        from inv.errors import DomainError
        from inv import identity as verifier

        bundle_path = workspace / "bundle.json"
        keys, dropped = builder.signing_keys(jwks)
        bundle = builder.build_bundle(jwks, issuer=issuer, now=now, ttl_seconds=3600)
        bundle_path.write_text(json.dumps(bundle), encoding="utf-8")
        facts["keyCount"] = len(bundle["keys"])
        facts["droppedNonSigningKeys"] = dropped
        facts["kidSha256"] = sorted(sha256_text(key["kid"]) for key in keys)

        tokens = verifier.AccessTokens(
            tenant_id=tenant_id,
            issuer=issuer,
            audience=audience,
            client_ids=[client_id],
            jwks_file=str(bundle_path),
        )
        observations["bundleAccepted"] = {
            "status": "MEASURED_PASS",
            "loadedKeyCount": len(tokens._keys()),
        }

        identity = tokens.verify(token)
        payload = segment(token, 1)
        facts["tokenLifetimeSeconds"] = payload["exp"] - payload["iat"]
        facts["signedByKidSha256"] = sha256_text(segment(token, 0)["kid"])
        observations["liveTokenVerified"] = {
            "status": "MEASURED_PASS",
            "tokenTypeHeader": segment(token, 0)["typ"],
            # public_subject hashes issuer+sub. Record that it is derived, not the value.
            "subjectIsDerivedPseudonym": identity.principal.subject_id.startswith("oidc:"),
            "expiresAtInFuture": identity.expires_at > int(now.timestamp()),
        }

        try:
            tokens.verify(tamper(token))
        except DomainError as refusal:
            observations["tamperedTokenRefused"] = {
                "status": "MEASURED_PASS",
                "code": refusal.code,
                "httpStatus": refusal.status,
            }
        else:
            observations["tamperedTokenRefused"] = {
                "status": "MEASURED_FAIL",
                "reason": "the verifier accepted an edited token",
            }
    except Exception as error:
        # Name the failure class, never the message: a message can echo a token.
        for name, observation in observations.items():
            if observation["status"] == "NOT_OBSERVED":
                observations[name] = unmeasured(f"measurement raised {type(error).__name__}")
    finally:
        shutil.rmtree(workspace, ignore_errors=True)
        facts["temporaryBundleRemoved"] = not workspace.exists()
    return observations, facts


def validate_evidence(evidence: dict[str, Any]) -> None:
    """The checks this collector adds; a pass may not be asserted by hand."""
    if evidence.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError("schemaVersion mismatch")
    if evidence.get("criteria") != CRITERIA:
        raise ValueError("criteria binding mismatch")
    observations = evidence.get("observations") or {}
    if set(observations) != set(REQUIRED):
        raise ValueError("observations must be exactly the three required ones")
    if evidence.get("verdict") != overall_verdict(observations, REQUIRED):
        raise ValueError("verdict was not recomputed from observations")
    if evidence.get("acceptanceClaim") is not (evidence.get("verdict") == "PASS"):
        raise ValueError("acceptanceClaim must follow the recomputed verdict")
    if not COMMIT_PATTERN.fullmatch(str(evidence.get("codeSha") or "")):
        raise ValueError("codeSha must be an exact 40-hex commit")
    provenance = evidence.get("provenance") or {}
    if provenance.get("workingTreeClean") is not True or provenance.get("contentClean") is not True:
        # codeSha names a commit. On a dirty tree it names bytes that were never in it,
        # so the artifact would claim provenance it does not have.
        raise ValueError("evidence source tree must be clean")
    source = evidence.get("source") or {}
    if source.get("issuerScheme") not in {"http", "https"}:
        raise ValueError("issuerScheme must be recorded")
    if source.get("providerRole") not in PROVIDER_ROLES:
        raise ValueError("providerRole must say which provider was measured")
    transport = source.get("jwksTransport")
    if transport not in JWKS_TRANSPORTS:
        raise ValueError("jwksTransport must say how the signing keys arrived")
    if transport == "verified-https" and not SHA256_PATTERN.fullmatch(
        str(source.get("caBundleSha256") or "")
    ):
        # Claiming a verified fetch without naming the trust anchor claims more than
        # was observed: any CA the process happened to trust would have done.
        raise ValueError("a verified-https fetch must record the trust anchor's SHA-256")
    if not SHA256_PATTERN.fullmatch(str(source.get("jwksSha256") or "")):
        raise ValueError("the JWKS bytes must be identified by SHA-256")
    if evidence["verdict"] == "PASS" and source.get("issuerScheme") != "https":
        # AccessTokens.__init__ refuses a non-https issuer, so a PASS here would mean
        # the evidence and the product disagree about what was even possible.
        raise ValueError("a PASS cannot be reported for a non-https issuer")
    if source.get("temporaryBundleRemoved") is not True:
        raise ValueError("cleanup was not confirmed")


def render_markdown(evidence: dict[str, Any]) -> str:
    source = evidence["source"]
    lines = [
        f"# OIDC identity evidence — {evidence['verdict']}",
        "",
        f"- code SHA: `{evidence['codeSha']}`",
        f"- collector SHA-256: `{evidence['collectorSha256']}`",
        f"- observed: {source['observedAt']}",
        f"- provider: **{source['providerRole']}**",
        f"- signing keys arrived: **{source['jwksTransport']}**"
        + (
            f", trust anchor SHA-256 `{source['caBundleSha256']}`"
            if source.get("caBundleSha256")
            else " (this artifact says nothing about that transport)"
        ),
        f"- issuer mode: **{source['issuerScheme']}**, issuer SHA-256 `{source['issuerSha256']}`",
        f"- keys in bundle: {source.get('keyCount')} (dropped non-signing: "
        f"{source.get('droppedNonSigningKeys')})",
        f"- temporary bundle removed: {source['temporaryBundleRemoved']}",
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
        "No token, username or key material is recorded here. A key id appears only as",
        "its SHA-256, and the issuer only as its scheme plus a SHA-256 of the string.",
        "",
    ]
    return "\n".join(lines)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n", 1)[0])
    result.add_argument("--issuer", required=True, help="exactly the configured identity.issuer")
    source = result.add_mutually_exclusive_group(required=True)
    source.add_argument("--jwks-file", type=Path, help="keys supplied out of band")
    source.add_argument("--jwks-url", help="fetch here over TLS, same origin as --issuer")
    result.add_argument("--token-file", required=True, type=Path, help="a live access token")
    result.add_argument("--tenant-id", required=True)
    result.add_argument("--audience", default="sv-api")
    result.add_argument("--client-id", default="sv-portal")
    result.add_argument(
        "--provider-role",
        required=True,
        choices=PROVIDER_ROLES,
        help="production, or cutover-rehearsal for a throwaway instance",
    )
    result.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    result.add_argument("--label")
    result.add_argument("--executor", default="claude")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    started = dt.datetime.now(dt.timezone.utc)
    provenance = collect_provenance_at_root(args.executor)
    if args.jwks_file is not None:
        raw_jwks = args.jwks_file.read_text(encoding="utf-8")
        jwks = json.loads(raw_jwks)
        transport = "out-of-band-file"
        anchor = None
    else:
        jwks = builder.read_jwks(
            jwks_file=None, jwks_url=args.jwks_url, issuer=args.issuer, timeout=15.0
        )
        raw_jwks = json.dumps(jwks, sort_keys=True, separators=(",", ":"))
        transport = "verified-https"
        bundle = os.environ.get("SSL_CERT_FILE")
        if not bundle:
            print(
                "refused: set SSL_CERT_FILE to the CA bundle before fetching over https",
                file=sys.stderr,
            )
            return 2
        anchor = sha256_text(Path(bundle).read_text(encoding="utf-8"))
    token = args.token_file.read_text(encoding="utf-8").strip()

    observations, facts = measure(
        issuer=args.issuer,
        jwks=jwks,
        token=token,
        tenant_id=args.tenant_id,
        audience=args.audience,
        client_id=args.client_id,
        now=started,
    )
    finished = dt.datetime.now(dt.timezone.utc)
    verdict = overall_verdict(observations, REQUIRED)
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
            "issuerScheme": urlsplit(args.issuer).scheme.lower(),
            "providerRole": args.provider_role,
            "jwksTransport": transport,
            "jwksSha256": sha256_text(raw_jwks),
            **({"caBundleSha256": anchor} if anchor else {}),
            "issuerSha256": sha256_text(args.issuer),
            "audienceSha256": sha256_text(args.audience),
            "clientIdSha256": sha256_text(args.client_id),
            "inputBindingSha256": input_binding_sha256(
                {
                    "issuer": args.issuer,
                    "audience": args.audience,
                    "clientId": args.client_id,
                    "jwks": jwks,
                }
            ),
            **facts,
        },
        "observations": observations,
        "verdict": verdict,
        "acceptanceClaim": verdict == "PASS",
    }
    validate_evidence(evidence)
    if not COMMIT_PATTERN.fullmatch(str(evidence["codeSha"] or "")):
        print("refused: codeSha is not an exact 40-hex commit", file=sys.stderr)
        return 2
    label = args.label or default_label("oidc-identity", evidence["codeSha"])
    if not LABEL_PATTERN.fullmatch(label):
        print(f"refused: label {label!r} is not a safe file name", file=sys.stderr)
        return 2
    serialised = json.dumps(evidence, ensure_ascii=False, sort_keys=True)
    assert_no_secrets(serialised)
    if token in serialised or args.tenant_id in serialised:
        raise ValueError("evidence would contain the token or the tenant id")
    json_path, markdown_path = write_evidence(
        evidence, args.out_dir, label, render_markdown=render_markdown
    )
    print(json.dumps({"verdict": verdict, "json": str(json_path), "markdown": str(markdown_path)}))
    return EXIT_BY_VERDICT[verdict]


if __name__ == "__main__":
    raise SystemExit(main())
