"""Build the operator-supplied OIDC trust bundle the verifier reads.

The control plane verifies access tokens offline: it does not fetch keys at
verification time, because that would make the identity provider's availability a
dependency of every request and its DNS a trust boundary. It reads a *file* an
operator supplied -- ``identity.jwks_file`` -- and refuses to start if that file
is not exactly what ``inv.identity.AccessTokens`` expects.

This tool turns a provider's published JWKS into that file, and refuses to write
anything the verifier would reject. The rules below are the verifier's, restated
here so a bad bundle fails at the operator's terminal rather than at startup:

* exactly three top-level keys -- ``issuer``, ``expiresAt``, ``keys``;
* ``issuer`` equal to the issuer the deployment is configured with, and
  ``https://``: ``AccessTokens.__init__`` refuses any other scheme before it ever
  opens the bundle, so a plain-HTTP provider cannot be trusted by this control
  plane at all;
* ``expiresAt`` an integer, in the future, and **at most seven days ahead**, so a
  bundle has to be reissued weekly rather than pinned once and forgotten;
* one to eight keys, each ``kty=RSA``, ``alg=RS256``, ``use=sig``, with a unique
  ``kid`` of 1..128 characters and an RSA modulus of 2048..4096 bits;
* no private component: a key carrying ``d`` is refused rather than stripped,
  because a private key reaching a trust bundle is an incident, not a formatting
  problem.

Keys the provider publishes for other purposes -- encryption keys, other
algorithms, other curves -- are dropped, and the tool says how many it dropped.
Provider entries are otherwise copied verbatim: a trust bundle is not the place
to rewrite key material.

The file is written ``0644``. ``trusted_file`` refuses a bundle that is group- or
world-writable, or larger than 65536 bytes, so both are checked here first.

Usage:
    python tools/make_oidc_trust_bundle.py --issuer URL --jwks-file in.json --output bundle.json
    python tools/make_oidc_trust_bundle.py --issuer URL --jwks-url URL --output bundle.json

Exit codes: 0 written, 2 refused (nothing written).
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
from pathlib import Path
import sys
from typing import Any


BUNDLE_KEYS = ("issuer", "expiresAt", "keys")
MAX_TTL_SECONDS = 7 * 86_400
MAX_KEYS = 8
MIN_MODULUS_BITS = 2048
MAX_MODULUS_BITS = 4096
KID_MAX = 128
MAX_BUNDLE_BYTES = 65_536  # trusted_file
BUNDLE_MODE = 0o644  # trusted_file refuses group/other write


class BundleRefused(ValueError):
    """The bundle would not be accepted by the verifier, so it is not written."""


def _modulus_bits(value: str) -> int:
    padding = "=" * (-len(value) % 4)
    raw = base64.urlsafe_b64decode(value + padding)
    # Leading zero bytes are not part of the modulus length.
    trimmed = raw.lstrip(b"\x00")
    if not trimmed:
        return 0
    return len(trimmed) * 8 - (8 - trimmed[0].bit_length())


def signing_keys(jwks: Any) -> tuple[list[dict[str, Any]], int]:
    """Return the RS256 signing keys, and how many entries were dropped."""
    if not isinstance(jwks, dict) or not isinstance(jwks.get("keys"), list):
        raise BundleRefused("JWKS must be an object with a keys array")
    selected: list[dict[str, Any]] = []
    for entry in jwks["keys"]:
        if not isinstance(entry, dict):
            raise BundleRefused("every JWKS entry must be an object")
        if "d" in entry:
            raise BundleRefused("a JWKS entry carries a private component")
        if entry.get("kty") == "RSA" and entry.get("alg") == "RS256" and entry.get("use") == "sig":
            selected.append(entry)
    return selected, len(jwks["keys"]) - len(selected)


def build_bundle(
    jwks: Any, *, issuer: str, now: dt.datetime, ttl_seconds: int
) -> dict[str, Any]:
    if not isinstance(issuer, str) or not issuer.startswith("https://"):
        # AccessTokens.__init__ refuses anything else; refusing here says so earlier.
        raise BundleRefused("issuer must be an https:// URL")
    if ttl_seconds <= 0 or ttl_seconds > MAX_TTL_SECONDS:
        raise BundleRefused(f"ttl must be in (0, {MAX_TTL_SECONDS}] seconds")
    keys, _ = signing_keys(jwks)
    if not 1 <= len(keys) <= MAX_KEYS:
        raise BundleRefused(f"a bundle carries 1..{MAX_KEYS} RS256 signing keys, found {len(keys)}")
    seen: set[str] = set()
    for key in keys:
        kid = key.get("kid")
        if not isinstance(kid, str) or not 1 <= len(kid) <= KID_MAX:
            raise BundleRefused("every key needs a kid of 1..128 characters")
        if kid in seen:
            raise BundleRefused(f"duplicate kid: {kid}")
        seen.add(kid)
        modulus = key.get("n")
        if not isinstance(modulus, str) or not modulus:
            raise BundleRefused(f"key {kid} has no modulus")
        bits = _modulus_bits(modulus)
        if not MIN_MODULUS_BITS <= bits <= MAX_MODULUS_BITS:
            raise BundleRefused(f"key {kid} is {bits} bits; {MIN_MODULUS_BITS}..{MAX_MODULUS_BITS} required")
    expires_at = int((now + dt.timedelta(seconds=ttl_seconds)).timestamp())
    bundle = {"issuer": issuer, "expiresAt": expires_at, "keys": keys}
    validate_bundle(bundle, now=now)
    return bundle


def validate_bundle(bundle: Any, *, now: dt.datetime) -> None:
    """The verifier's own acceptance test, run before anything is written."""
    if not isinstance(bundle, dict) or set(bundle) != set(BUNDLE_KEYS):
        raise BundleRefused("a bundle has exactly issuer, expiresAt and keys")
    expires_at = bundle["expiresAt"]
    if type(expires_at) is not int:
        raise BundleRefused("expiresAt must be an integer")
    moment = now.timestamp()
    if not moment < expires_at <= moment + MAX_TTL_SECONDS:
        raise BundleRefused("expiresAt must be in the future and at most seven days ahead")
    keys = bundle["keys"]
    if not isinstance(keys, list) or not 1 <= len(keys) <= MAX_KEYS:
        raise BundleRefused(f"a bundle carries 1..{MAX_KEYS} keys")
    for key in keys:
        if "d" in key:
            raise BundleRefused("a key carries a private component")
        if key.get("kty") != "RSA" or key.get("alg") != "RS256" or key.get("use") != "sig":
            raise BundleRefused("every key must be an RS256 RSA signing key")


def read_jwks(*, jwks_file: Path | None, jwks_url: str | None, timeout: float) -> Any:
    if jwks_file is not None:
        return json.loads(jwks_file.read_text(encoding="utf-8"))
    if jwks_url is None:  # pragma: no cover - argparse enforces one of the two
        raise BundleRefused("either --jwks-file or --jwks-url is required")
    if not jwks_url.startswith(("http://", "https://")):
        raise BundleRefused("--jwks-url must be an absolute http(s) URL")
    from urllib.request import urlopen

    with urlopen(jwks_url, timeout=timeout) as response:  # noqa: S310 - operator-supplied URL
        if response.status != 200:
            raise BundleRefused(f"JWKS endpoint answered {response.status}")
        return json.loads(response.read().decode("utf-8"))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n", 1)[0])
    result.add_argument("--issuer", required=True, help="exactly the configured identity.issuer")
    source = result.add_mutually_exclusive_group(required=True)
    source.add_argument("--jwks-file", type=Path)
    source.add_argument("--jwks-url")
    result.add_argument("--output", required=True, type=Path)
    result.add_argument("--ttl-seconds", type=int, default=MAX_TTL_SECONDS)
    result.add_argument("--timeout-seconds", type=float, default=10.0)
    result.add_argument(
        "--force", action="store_true", help="replace an existing bundle (reissue)"
    )
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    now = dt.datetime.now(dt.timezone.utc)
    try:
        jwks = read_jwks(
            jwks_file=args.jwks_file, jwks_url=args.jwks_url, timeout=args.timeout_seconds
        )
        _, dropped = signing_keys(jwks)
        bundle = build_bundle(jwks, issuer=args.issuer, now=now, ttl_seconds=args.ttl_seconds)
    except BundleRefused as refusal:
        print(f"refused: {refusal}", file=sys.stderr)
        return 2
    except Exception as error:
        # A provider error can echo a URL with credentials in it; only the class.
        print(f"refused: {type(error).__name__}", file=sys.stderr)
        return 2
    if args.output.exists() and not args.force:
        print("refused: output exists; pass --force to reissue", file=sys.stderr)
        return 2
    serialised = json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    encoded = serialised.encode("utf-8")
    if len(encoded) > MAX_BUNDLE_BYTES:
        # trusted_file caps the file, so a bundle nobody can read is not written.
        print(
            f"refused: bundle is {len(encoded)} bytes; the cap is {MAX_BUNDLE_BYTES}",
            file=sys.stderr,
        )
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded)
    try:
        args.output.chmod(BUNDLE_MODE)
    except OSError:  # pragma: no cover - chmod is advisory on Windows
        pass
    expires = dt.datetime.fromtimestamp(bundle["expiresAt"], dt.timezone.utc)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "issuer": bundle["issuer"],
                "keyCount": len(bundle["keys"]),
                "droppedNonSigningKeys": dropped,
                "expiresAt": expires.isoformat(timespec="seconds").replace("+00:00", "Z"),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
