"""The trust bundle builder must refuse anything the verifier would refuse.

Each test here is one way a bundle could be wrong at the operator's terminal
instead of at startup, and the point of the tool is that the two answers agree.
The acceptance rules are ``inv.identity.AccessTokens._keys``; this file restates
them as inputs.
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import os

import pytest

from tools import make_oidc_trust_bundle as builder

try:  # The control plane needs 3.12+; these two tests are the point of the tool.
    from inv import identity as verifier
except Exception:  # pragma: no cover - exercised on the older interpreter only
    verifier = None

needs_verifier = pytest.mark.skipif(
    verifier is None, reason="inv.identity unavailable on this interpreter"
)


ISSUER = "https://idp.sv.lan/realms/saintvision"
NOW = dt.datetime(2026, 9, 29, 12, 0, tzinfo=dt.timezone.utc)


def _modulus(bits: int) -> str:
    raw = (1 << (bits - 1)).to_bytes(bits // 8, "big")
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _key(kid: str = "sig-1", *, bits: int = 2048, **overrides):
    key = {"kty": "RSA", "alg": "RS256", "use": "sig", "kid": kid, "n": _modulus(bits), "e": "AQAB"}
    key.update(overrides)
    return key


def _jwks(*keys):
    return {"keys": list(keys)}


def test_a_provider_jwks_becomes_the_three_key_bundle():
    bundle = builder.build_bundle(_jwks(_key()), issuer=ISSUER, now=NOW, ttl_seconds=7 * 86_400)
    assert set(bundle) == {"issuer", "expiresAt", "keys"}
    assert bundle["issuer"] == ISSUER
    assert bundle["keys"] == [_key()]
    assert bundle["expiresAt"] == int((NOW + dt.timedelta(days=7)).timestamp())


def test_encryption_and_other_algorithms_are_dropped_not_carried():
    """Keycloak publishes an RSA-OAEP encryption key beside the signing key."""
    jwks = _jwks(
        _key("sig-1"),
        _key("enc-1", alg="RSA-OAEP", use="enc"),
        _key("es-1", kty="EC", alg="ES256"),
    )
    keys, dropped = builder.signing_keys(jwks)
    assert [k["kid"] for k in keys] == ["sig-1"]
    assert dropped == 2
    bundle = builder.build_bundle(jwks, issuer=ISSUER, now=NOW, ttl_seconds=3600)
    assert [k["kid"] for k in bundle["keys"]] == ["sig-1"]


def test_a_private_key_is_refused_rather_than_stripped():
    """A private component in a trust bundle is an incident, not a format issue."""
    with pytest.raises(builder.BundleRefused, match="private component"):
        builder.signing_keys(_jwks(_key(d="c2VjcmV0")))


def test_a_ttl_beyond_seven_days_is_refused():
    with pytest.raises(builder.BundleRefused, match="ttl"):
        builder.build_bundle(_jwks(_key()), issuer=ISSUER, now=NOW, ttl_seconds=7 * 86_400 + 1)


def test_a_zero_or_negative_ttl_is_refused():
    for ttl in (0, -1):
        with pytest.raises(builder.BundleRefused, match="ttl"):
            builder.build_bundle(_jwks(_key()), issuer=ISSUER, now=NOW, ttl_seconds=ttl)


def test_no_signing_key_is_refused():
    with pytest.raises(builder.BundleRefused, match="1\\.\\.8"):
        builder.build_bundle(
            _jwks(_key("enc-1", alg="RSA-OAEP", use="enc")),
            issuer=ISSUER,
            now=NOW,
            ttl_seconds=3600,
        )


def test_more_than_eight_signing_keys_are_refused():
    jwks = _jwks(*[_key(f"sig-{index}") for index in range(9)])
    with pytest.raises(builder.BundleRefused, match="1\\.\\.8"):
        builder.build_bundle(jwks, issuer=ISSUER, now=NOW, ttl_seconds=3600)


def test_duplicate_kids_are_refused():
    with pytest.raises(builder.BundleRefused, match="duplicate kid"):
        builder.build_bundle(
            _jwks(_key("same"), _key("same", bits=3072)), issuer=ISSUER, now=NOW, ttl_seconds=3600
        )


@pytest.mark.parametrize("kid", [None, "", "x" * 129, 5])
def test_a_missing_or_oversized_kid_is_refused(kid):
    key = _key()
    if kid is None:
        key.pop("kid")
    else:
        key["kid"] = kid
    with pytest.raises(builder.BundleRefused, match="kid"):
        builder.build_bundle(_jwks(key), issuer=ISSUER, now=NOW, ttl_seconds=3600)


@pytest.mark.parametrize("bits", [1024, 8192])
def test_a_modulus_outside_2048_4096_is_refused(bits):
    with pytest.raises(builder.BundleRefused, match="bits"):
        builder.build_bundle(_jwks(_key(bits=bits)), issuer=ISSUER, now=NOW, ttl_seconds=3600)


@pytest.mark.parametrize("bits", [2048, 3072, 4096])
def test_the_permitted_modulus_sizes_are_accepted(bits):
    bundle = builder.build_bundle(_jwks(_key(bits=bits)), issuer=ISSUER, now=NOW, ttl_seconds=3600)
    assert len(bundle["keys"]) == 1


@pytest.mark.parametrize(
    "issuer",
    [
        "idp.sv.lan",
        # The IdP as first brought up, before the internal CA lands. AccessTokens
        # refuses this scheme outright, so the bundle builder must refuse it too --
        # otherwise the operator gets a bundle that only fails at startup.
        "http://idp.sv.lan:8080/realms/saintvision",
    ],
)
def test_a_non_https_issuer_is_refused(issuer):
    with pytest.raises(builder.BundleRefused, match="issuer"):
        builder.build_bundle(_jwks(_key()), issuer=issuer, now=NOW, ttl_seconds=3600)


def test_validate_rejects_an_expired_bundle():
    bundle = builder.build_bundle(_jwks(_key()), issuer=ISSUER, now=NOW, ttl_seconds=3600)
    with pytest.raises(builder.BundleRefused, match="future"):
        builder.validate_bundle(bundle, now=NOW + dt.timedelta(hours=2))


def test_validate_rejects_a_bundle_pinned_beyond_a_week():
    bundle = builder.build_bundle(_jwks(_key()), issuer=ISSUER, now=NOW, ttl_seconds=3600)
    bundle["expiresAt"] = int((NOW + dt.timedelta(days=30)).timestamp())
    with pytest.raises(builder.BundleRefused, match="seven days"):
        builder.validate_bundle(bundle, now=NOW)


def test_validate_rejects_an_extra_top_level_key():
    bundle = builder.build_bundle(_jwks(_key()), issuer=ISSUER, now=NOW, ttl_seconds=3600)
    bundle["realm"] = "saintvision"
    with pytest.raises(builder.BundleRefused, match="exactly"):
        builder.validate_bundle(bundle, now=NOW)


def test_validate_rejects_a_boolean_expiry():
    """``type(...) is not int`` matters: True would otherwise pass an int check."""
    bundle = builder.build_bundle(_jwks(_key()), issuer=ISSUER, now=NOW, ttl_seconds=3600)
    bundle["expiresAt"] = True
    with pytest.raises(builder.BundleRefused, match="integer"):
        builder.validate_bundle(bundle, now=NOW)


def test_cli_writes_a_bundle_and_refuses_to_overwrite_without_force(tmp_path):
    jwks_path = tmp_path / "jwks.json"
    jwks_path.write_text(json.dumps(_jwks(_key(), _key("enc", alg="RSA-OAEP", use="enc"))), encoding="utf-8")
    out = tmp_path / "bundle.json"
    argv = ["--issuer", ISSUER, "--jwks-file", str(jwks_path), "--output", str(out)]
    assert builder.main(argv) == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    assert set(written) == {"issuer", "expiresAt", "keys"}
    assert len(written["keys"]) == 1
    builder.validate_bundle(written, now=dt.datetime.now(dt.timezone.utc))
    assert builder.main(argv) == 2, "a second run must not silently replace the bundle"
    assert builder.main(argv + ["--force"]) == 0


def test_cli_refuses_a_private_key_without_writing(tmp_path):
    jwks_path = tmp_path / "jwks.json"
    jwks_path.write_text(json.dumps(_jwks(_key(d="c2VjcmV0"))), encoding="utf-8")
    out = tmp_path / "bundle.json"
    assert (
        builder.main(["--issuer", ISSUER, "--jwks-file", str(jwks_path), "--output", str(out)]) == 2
    )
    assert not out.exists(), "nothing may be written when the bundle is refused"


def test_cli_refuses_a_ttl_beyond_a_week_without_writing(tmp_path):
    jwks_path = tmp_path / "jwks.json"
    jwks_path.write_text(json.dumps(_jwks(_key())), encoding="utf-8")
    out = tmp_path / "bundle.json"
    argv = [
        "--issuer", ISSUER, "--jwks-file", str(jwks_path), "--output", str(out),
        "--ttl-seconds", str(7 * 86_400 + 60),
    ]
    assert builder.main(argv) == 2
    assert not out.exists()


def test_a_bundle_over_the_trusted_file_cap_is_not_written(tmp_path, monkeypatch):
    """``trusted_file`` refuses anything over 65536 bytes; do not hand one over."""
    monkeypatch.setattr(builder, "MAX_BUNDLE_BYTES", 200)
    jwks_path = tmp_path / "jwks.json"
    jwks_path.write_text(json.dumps(_jwks(_key())), encoding="utf-8")
    out = tmp_path / "bundle.json"
    assert (
        builder.main(["--issuer", ISSUER, "--jwks-file", str(jwks_path), "--output", str(out)]) == 2
    )
    assert not out.exists()


@pytest.mark.skipif(os.name == "nt", reason="POSIX mode bits; trusted_file skips them on Windows")
def test_the_written_bundle_is_not_group_or_world_writable(tmp_path):
    jwks_path = tmp_path / "jwks.json"
    jwks_path.write_text(json.dumps(_jwks(_key())), encoding="utf-8")
    out = tmp_path / "bundle.json"
    assert (
        builder.main(["--issuer", ISSUER, "--jwks-file", str(jwks_path), "--output", str(out)]) == 0
    )
    assert out.stat().st_mode & 0o022 == 0


def _real_jwks(kid="sig-live"):
    """A JWKS a provider could actually publish, from a real RSA public key."""
    from cryptography.hazmat.primitives.asymmetric import rsa

    public = rsa.generate_private_key(public_exponent=65537, key_size=2048).public_key()
    numbers = public.public_numbers()

    def b64(value: int) -> str:
        raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    return _jwks(
        {
            "kty": "RSA", "alg": "RS256", "use": "sig", "kid": kid,
            "n": b64(numbers.n), "e": b64(numbers.e),
        }
    )


@needs_verifier
def test_the_verifier_accepts_what_this_tool_writes(tmp_path):
    """The point of the tool: its answer and AccessTokens' answer are the same one."""
    identity = verifier
    jwks_path = tmp_path / "jwks.json"
    jwks_path.write_text(json.dumps(_real_jwks()), encoding="utf-8")
    out = tmp_path / "bundle.json"
    assert (
        builder.main(["--issuer", ISSUER, "--jwks-file", str(jwks_path), "--output", str(out)]) == 0
    )
    tokens = identity.AccessTokens(
        tenant_id="00000000-0000-4000-8000-000000000001",
        issuer=ISSUER,
        audience="sv-api",
        client_ids=["sv-portal"],
        jwks_file=str(out),
    )
    assert list(tokens._keys()) == ["sig-live"]


@needs_verifier
def test_the_verifier_refuses_a_bundle_repinned_past_a_week(tmp_path):
    """The weekly reissue is the verifier's rule, not a convention of this tool."""
    identity = verifier
    jwks_path = tmp_path / "jwks.json"
    jwks_path.write_text(json.dumps(_real_jwks()), encoding="utf-8")
    out = tmp_path / "bundle.json"
    assert (
        builder.main(["--issuer", ISSUER, "--jwks-file", str(jwks_path), "--output", str(out)]) == 0
    )
    tampered = json.loads(out.read_text(encoding="utf-8"))
    tampered["expiresAt"] += 86_400
    out.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(ValueError, match="trust bundle"):
        identity.AccessTokens(
            tenant_id="00000000-0000-4000-8000-000000000001",
            issuer=ISSUER,
            audience="sv-api",
            client_ids=["sv-portal"],
            jwks_file=str(out),
        )


# --- the JWKS fetch is bound to the issuer, not to whatever answers -------------
#
# The bundle stamps --issuer onto the keys it fetched. If the fetch may come from
# anywhere, this tool becomes a way to present a stranger's signing key as the
# issuer's own, and the resulting file looks entirely correct.


def test_a_plain_http_jwks_url_is_refused():
    with pytest.raises(builder.BundleRefused, match="https"):
        builder.assert_same_origin("http://idp.sv.lan/realms/saintvision/certs", ISSUER)


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example/realms/saintvision/protocol/openid-connect/certs",
        "https://idp.sv.lan:8443/realms/saintvision/protocol/openid-connect/certs",
        "https://idp.sv.lan.evil.example/realms/saintvision/certs",
    ],
)
def test_a_jwks_url_on_another_origin_is_refused(url):
    with pytest.raises(builder.BundleRefused, match="same origin"):
        builder.assert_same_origin(url, ISSUER)


def test_the_issuers_own_certs_endpoint_is_accepted():
    builder.assert_same_origin(ISSUER + "/protocol/openid-connect/certs", ISSUER)


@pytest.mark.parametrize(
    ("url", "reason"),
    [
        ("https://user:pass@idp.sv.lan/certs", "credentials"),
        ("https://idp.sv.lan/certs#fragment", "fragment"),
        ("https:///certs", "without a host"),
    ],
)
def test_a_url_carrying_credentials_or_a_fragment_is_refused(url, reason):
    with pytest.raises(builder.BundleRefused, match=reason):
        builder.origin(url)


def test_a_cross_origin_redirect_is_not_followed():
    handler = builder.SameOriginOnly(builder.origin(ISSUER))
    with pytest.raises(builder.BundleRefused, match="redirected"):
        handler.redirect_request(None, None, 302, "Found", {}, "https://evil.example/certs")


def test_a_same_origin_redirect_is_still_followed():
    """A realm may redirect within itself; only leaving the origin is the problem."""
    from email.message import Message
    from urllib.request import Request

    handler = builder.SameOriginOnly(builder.origin(ISSUER))
    target = ISSUER + "/protocol/openid-connect/certs"
    followed = handler.redirect_request(
        Request(ISSUER + "/certs"), None, 302, "Found", Message(), target
    )
    assert followed.get_full_url() == target


def test_a_downgrade_to_http_counts_as_another_origin():
    handler = builder.SameOriginOnly(builder.origin(ISSUER))
    with pytest.raises(builder.BundleRefused, match="redirected"):
        handler.redirect_request(None, None, 302, "Found", {}, "http://idp.sv.lan/certs")


class _Body:
    def __init__(self, size):
        self._payload = b"x" * size

    def read(self, limit):
        return self._payload[:limit]


def test_an_oversized_jwks_body_is_refused_rather_than_read():
    with pytest.raises(builder.BundleRefused, match="exceeds"):
        builder.read_bounded(_Body(builder.MAX_JWKS_BYTES + 1))


def test_a_body_at_the_bound_is_accepted():
    assert len(builder.read_bounded(_Body(builder.MAX_JWKS_BYTES))) == builder.MAX_JWKS_BYTES
