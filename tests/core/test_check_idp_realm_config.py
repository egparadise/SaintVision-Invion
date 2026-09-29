"""Every relaxation of the realm must be reported, not tolerated.

The realm configurator creates what is missing, so it keeps exiting 0 after someone
loosens an existing setting in the admin console. This checker is what notices. These
tests take a realm that matches the contract and relax exactly one thing at a time --
if any of them stops failing, drift has become invisible again.
"""

from __future__ import annotations

import copy
import json

import pytest

from tools import check_idp_realm_config as checker


def matching_config():
    return {
        "realm": {"realm": "saintvision", "enabled": True, "accessTokenLifespan": 300},
        "clients": {
            "sv-api": {
                "publicClient": False,
                "standardFlowEnabled": False,
                "directAccessGrantsEnabled": False,
                "implicitFlowEnabled": False,
                "serviceAccountsEnabled": False,
            },
            "sv-portal": {
                "publicClient": True,
                "standardFlowEnabled": True,
                "directAccessGrantsEnabled": False,
                "implicitFlowEnabled": False,
                "serviceAccountsEnabled": False,
                "attributes": {
                    "pkce.code.challenge.method": "S256",
                    "access.token.header.type.rfc9068": "true",
                },
                "defaultClientScopes": ["acr", "basic", "email", "profile", "inv.api"],
                "redirectUris": ["https://portal.sv.lan/*", "http://localhost:3005/*"],
                "webOrigins": ["https://portal.sv.lan", "http://127.0.0.1:3005"],
                "protocolMappers": [
                    {
                        "name": "sv-api-audience",
                        "protocolMapper": "oidc-audience-mapper",
                        "config": {
                            "included.client.audience": "sv-api",
                            "access.token.claim": "true",
                            "id.token.claim": "false",
                        },
                    },
                    {
                        "name": "client-id",
                        "protocolMapper": "oidc-hardcoded-claim-mapper",
                        "config": {
                            "claim.name": "client_id",
                            "claim.value": "sv-portal",
                            "access.token.claim": "true",
                        },
                    },
                ],
            },
        },
    }


def findings(config):
    return checker.drift(
        config, realm="saintvision", api_client="sv-api", portal_client="sv-portal", scope="inv.api"
    )


def test_the_configured_realm_reports_no_drift():
    assert findings(matching_config()) == []


def relax(mutate):
    config = matching_config()
    mutate(config, config["clients"]["sv-portal"], config["clients"]["sv-api"])
    return findings(config)


@pytest.mark.parametrize(
    ("label", "mutate", "expected"),
    [
        # The verifier refuses exp - iat > 3600, so a wider window is unusable...
        ("lifespan beyond the verifier's bound",
         lambda c, p, a: c["realm"].__setitem__("accessTokenLifespan", 7200), "exceeds"),
        # ...and a narrower-but-changed one is still someone editing the contract.
        ("lifespan quietly widened",
         lambda c, p, a: c["realm"].__setitem__("accessTokenLifespan", 1800), "drifted"),
        ("realm disabled", lambda c, p, a: c["realm"].__setitem__("enabled", False), "not enabled"),
        ("api client made public",
         lambda c, p, a: a.__setitem__("publicClient", True), "public client"),
        ("api client allowed to log in",
         lambda c, p, a: a.__setitem__("standardFlowEnabled", True), "must not log anyone in"),
        ("api client given a service account",
         lambda c, p, a: a.__setitem__("serviceAccountsEnabled", True), "must not log anyone in"),
        ("portal made confidential",
         lambda c, p, a: p.__setitem__("publicClient", False), "not a public client"),
        ("portal given a password grant",
         lambda c, p, a: p.__setitem__("directAccessGrantsEnabled", True),
         "directAccessGrantsEnabled"),
        ("portal given the implicit flow",
         lambda c, p, a: p.__setitem__("implicitFlowEnabled", True), "implicitFlowEnabled"),
        ("pkce downgraded to plain",
         lambda c, p, a: p["attributes"].__setitem__("pkce.code.challenge.method", "plain"),
         "PKCE S256"),
        ("pkce removed",
         lambda c, p, a: p["attributes"].pop("pkce.code.challenge.method"), "PKCE S256"),
        ("rfc9068 token type turned off",
         lambda c, p, a: p["attributes"].__setitem__("access.token.header.type.rfc9068", "false"),
         "at\\+jwt"),
        ("inv.api scope removed",
         lambda c, p, a: p["defaultClientScopes"].remove("inv.api"), "missing the inv.api"),
        # This one is subtle: adding a scope back makes aud a list, which strict_aud bans.
        ("roles scope added back",
         lambda c, p, a: p["defaultClientScopes"].append("roles"), "makes aud a list"),
        ("audience mapper removed",
         lambda c, p, a: p["protocolMappers"].pop(0), "no audience mapper"),
        ("audience mapper points elsewhere",
         lambda c, p, a: p["protocolMappers"][0]["config"].__setitem__(
             "included.client.audience", "other"), "no audience mapper"),
        ("audience mapper stops writing the access token",
         lambda c, p, a: p["protocolMappers"][0]["config"].__setitem__(
             "access.token.claim", "false"), "does not write to the access token"),
        ("client_id mapper removed",
         lambda c, p, a: p["protocolMappers"].pop(1), "client_id claim"),
        ("client_id claims another client",
         lambda c, p, a: p["protocolMappers"][1]["config"].__setitem__(
             "claim.value", "somebody-else"), "client_id claim is not sv-portal"),
        ("plaintext redirect on a real host",
         lambda c, p, a: p["redirectUris"].append("http://portal.sv.lan/*"),
         "plaintext or wildcard"),
        ("wildcard redirect",
         lambda c, p, a: p["redirectUris"].append("*"), "plaintext or wildcard"),
        ("plaintext web origin on a real host",
         lambda c, p, a: p["webOrigins"].append("http://portal.sv.lan"),
         "plaintext or wildcard"),
        ("redirect uris emptied",
         lambda c, p, a: p.__setitem__("redirectUris", None), "has no redirectUris"),
    ],
)
def test_one_relaxation_at_a_time_is_reported(label, mutate, expected):
    import re

    reported = relax(mutate)
    assert reported, f"{label} went unreported"
    assert any(re.search(expected, line) for line in reported), f"{label}: {reported}"


def test_loopback_http_is_allowed_but_a_real_host_is_not():
    """A loopback redirect never crosses the network; that is why it is permitted."""
    assert not checker.insecure_url("http://localhost:3005/callback")
    assert not checker.insecure_url("http://127.0.0.1:3005/callback")
    assert not checker.insecure_url("https://portal.sv.lan/callback")
    assert checker.insecure_url("http://portal.sv.lan/callback")
    assert checker.insecure_url("http://10.0.0.5/callback")


def test_a_missing_client_is_unusable_not_merely_drift():
    """Silence about an absent client would read as "no problems found"."""
    config = matching_config()
    del config["clients"]["sv-portal"]
    with pytest.raises(checker.ConfigUnusable, match="sv-portal"):
        findings(config)


def test_the_cli_separates_drift_from_an_unusable_snapshot(tmp_path, capsys):
    good = tmp_path / "good.json"
    good.write_text(json.dumps(matching_config()), encoding="utf-8")
    assert checker.main(["--config", str(good)]) == 0

    drifted = copy.deepcopy(matching_config())
    drifted["clients"]["sv-portal"]["directAccessGrantsEnabled"] = True
    path = tmp_path / "drift.json"
    path.write_text(json.dumps(drifted), encoding="utf-8")
    assert checker.main(["--config", str(path)]) == 1

    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    assert checker.main(["--config", str(broken)]) == 2
