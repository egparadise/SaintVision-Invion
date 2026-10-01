"""Every relaxation of the realm must be reported, not tolerated.

The realm configurator creates what is missing, so it keeps exiting 0 after someone
loosens an existing setting in the admin console. This checker is what notices. These
tests take a realm that matches the contract and relax exactly one thing at a time --
if any of them stops failing, drift has become invisible again.
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from tools import check_idp_realm_config as checker


ROOT = Path(__file__).resolve().parents[2]


def matching_config():
    return {
        "realm": {
            "realm": "saintvision",
            "enabled": True,
            "accessTokenLifespan": 300,
            "sslRequired": "external",
        },
        "clients": {
            "sv-api": {
                "enabled": True,
                "publicClient": False,
                "standardFlowEnabled": False,
                "directAccessGrantsEnabled": False,
                "implicitFlowEnabled": False,
                "serviceAccountsEnabled": False,
            },
            "sv-portal": {
                "enabled": True,
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
                    {
                        "name": "fresh-auth-time",
                        "protocolMapper": "oidc-usersessionmodel-note-mapper",
                        "config": {
                            "user.session.note": "AUTH_TIME",
                            "claim.name": "auth_time",
                            "jsonType.label": "long",
                            "access.token.claim": "true",
                            "id.token.claim": "false",
                            "userinfo.token.claim": "false",
                        },
                    },
                    {
                        "name": "fresh-auth-amr",
                        "protocolMapper": "oidc-amr-mapper",
                        "config": {
                            "access.token.claim": "true",
                            "id.token.claim": "false",
                            "lightweight.claim": "false",
                        },
                    },
                ],
            },
        },
        "clientScopes": {
            "inv.api": {
                "name": "inv.api",
                "protocol": "openid-connect",
                "attributes": {
                    "include.in.token.scope": "true",
                    "display.on.consent.screen": "false",
                },
            },
        },
        "authenticatorReferences": {
            "auth-username-password-form": {
                "config": {
                    "default.reference.value": "pwd",
                    "default.reference.maxAge": "300",
                }
            },
            "auth-otp-form": {
                "config": {
                    "default.reference.value": "otp",
                    "default.reference.maxAge": "300",
                }
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


def relax_scope(mutate):
    config = matching_config()
    mutate(config["clientScopes"]["inv.api"])
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
        ("auth_time mapper removed",
         lambda c, p, a: p["protocolMappers"].pop(2), "fresh-auth-time"),
        ("auth_time mapper reads another session note",
         lambda c, p, a: p["protocolMappers"][2]["config"].__setitem__(
             "user.session.note", "user-input"), "exactly bind AUTH_TIME"),
        ("auth_time mapper writes a string",
         lambda c, p, a: p["protocolMappers"][2]["config"].__setitem__(
             "jsonType.label", "String"), "exactly bind AUTH_TIME"),
        ("amr mapper removed",
         lambda c, p, a: p["protocolMappers"].pop(3), "fresh-auth-amr"),
        ("amr mapper stops writing access tokens",
         lambda c, p, a: p["protocolMappers"][3]["config"].__setitem__(
             "access.token.claim", "false"), "access-token-only"),
        ("amr mapper starts writing id tokens",
         lambda c, p, a: p["protocolMappers"][3]["config"].__setitem__(
             "id.token.claim", "true"), "access-token-only"),
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
        # The three Codex r2 named: a disabled client on either side, and a scope
        # that is assigned but contributes nothing to the token.
        ("api client disabled",
         lambda c, p, a: a.__setitem__("enabled", False), "sv-api is disabled"),
        ("portal client disabled",
         lambda c, p, a: p.__setitem__("enabled", False), "sv-portal is disabled"),
        ("realm stops requiring https",
         lambda c, p, a: c["realm"].__setitem__("sslRequired", "none"), "sslRequired"),
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


# --- the scope's own representation, not just its name on the client -------------
#
# Assigning inv.api to the client and leaving include.in.token.scope false is the
# failure mode that looks exactly like success: the scope is listed, the token has
# no inv.api in it, the product answers 401, and the configurator exits 0.


def test_a_scope_that_contributes_nothing_to_the_token_is_reported():
    reported = relax_scope(
        lambda scope: scope["attributes"].__setitem__("include.in.token.scope", "false")
    )
    assert any("include.in.token.scope" in line for line in reported), reported


def test_a_scope_with_the_attribute_removed_is_reported():
    reported = relax_scope(lambda scope: scope["attributes"].pop("include.in.token.scope"))
    assert any("include.in.token.scope" in line for line in reported), reported


def test_a_scope_with_no_attributes_at_all_is_reported():
    reported = relax_scope(lambda scope: scope.pop("attributes"))
    assert any("no attributes" in line for line in reported), reported


def test_a_scope_on_another_protocol_is_reported():
    reported = relax_scope(lambda scope: scope.__setitem__("protocol", "saml"))
    assert any("openid-connect" in line for line in reported), reported


def test_an_absent_scope_representation_is_unusable_not_silent():
    """Judging the assignment while the scope itself is unknown would read as a pass."""
    config = matching_config()
    del config["clientScopes"]["inv.api"]
    with pytest.raises(checker.ConfigUnusable, match="clientScopes"):
        findings(config)
    config = matching_config()
    del config["clientScopes"]
    with pytest.raises(checker.ConfigUnusable, match="clientScopes"):
        findings(config)


@pytest.mark.parametrize("value", ["external", "all"])
def test_both_https_enforcement_levels_are_accepted(value):
    config = matching_config()
    config["realm"]["sslRequired"] = value
    assert findings(config) == []


@pytest.mark.parametrize(
    ("provider", "field", "value", "expected"),
    [
        ("auth-username-password-form", "default.reference.value", "webauthn", "RFC 8176 pwd"),
        ("auth-username-password-form", "default.reference.maxAge", "301", "300 seconds"),
        ("auth-otp-form", "default.reference.value", "mfa", "RFC 8176 otp"),
        ("auth-otp-form", "default.reference.maxAge", "0", "300 seconds"),
    ],
)
def test_fresh_auth_execution_references_are_exact(provider, field, value, expected):
    config = matching_config()
    config["authenticatorReferences"][provider]["config"][field] = value
    assert any(expected in finding for finding in findings(config))


def test_missing_reference_snapshot_is_unusable_not_a_false_pass():
    config = matching_config()
    del config["authenticatorReferences"]
    with pytest.raises(checker.ConfigUnusable, match="authenticatorReferences"):
        findings(config)


def test_realm_configurator_emits_the_exact_fresh_auth_snapshot():
    script = (ROOT / "deploy" / "intranet" / "idp-realm.sh").read_text(encoding="utf-8")
    for required in (
        '"protocolMapper": "oidc-usersessionmodel-note-mapper"',
        '"user.session.note": "AUTH_TIME"',
        '"claim.name": "auth_time"',
        '"protocolMapper": "oidc-amr-mapper"',
        '"default.reference.maxAge": "300"',
        'ensure_execution_reference "auth-username-password-form" "pwd"',
        'ensure_execution_reference "auth-otp-form" "otp"',
        '"authenticatorReferences"',
    ):
        assert required in script


def test_both_amr_mapper_writes_are_access_token_only():
    script = (ROOT / "deploy" / "intranet" / "idp-realm.sh").read_text(encoding="utf-8")
    exact = (
        '"config": {"access.token.claim": "true", "id.token.claim": "false",\n'
        '            "lightweight.claim": "false"}'
    )
    assert script.count('"name": "fresh-auth-amr"') == 2
    assert script.count(exact) == 2


def test_fresh_auth_only_mode_cannot_read_or_mutate_user_records():
    script = (ROOT / "deploy" / "intranet" / "idp-realm.sh").read_text(encoding="utf-8")

    assert 'APPLY_MODE="${SV_IDP_APPLY_MODE:-full}"' in script
    assert "full|fresh-auth-only" in script
    assert (
        'if [ "$APPLY_MODE" = "full" ]; then\n'
        '  set -a; . "$USERS_FILE"; set +a\n'
        "fi"
    ) in script
    user_guard = (
        'if [ "$APPLY_MODE" = "full" ]; then\n'
        '  for pair in "$SV_USER1:$SV_USER1_PASSWORD" "$SV_USER2:$SV_USER2_PASSWORD"; do'
    )
    assert user_guard in script
    assert script.index(user_guard) < script.index('kc_in update "users/$uid"')
    assert script.index(user_guard) < script.index('kc_in update "users/$uid/reset-password"')


def test_fresh_auth_only_mode_fails_closed_on_missing_prerequisites():
    script = (ROOT / "deploy" / "intranet" / "idp-realm.sh").read_text(encoding="utf-8")

    for prerequisite in ("realm", "client", "client scope"):
        assert f"fresh-auth-only refuses to create missing {prerequisite}" in script


def _fake_docker(tmp_path: Path) -> tuple[Path, Path]:
    """Return a fake docker CLI and its call log for the fresh-auth-only path."""
    log = tmp_path / "docker-calls.jsonl"
    executable = tmp_path / "docker"
    executable.write_text(
        """#!/usr/bin/env python3
import json, os, sys

args = sys.argv[1:]
with open(os.environ["SV_FAKE_DOCKER_LOG"], "a", encoding="utf-8") as handle:
    handle.write(json.dumps(args, separators=(",", ":")) + "\\n")

if args[:2] == ["exec", "sv-idp"] and args[2:4] == ["sh", "-c"]:
    raise SystemExit(0)
if args and args[0] == "exec":
    at = 1
    if args[at] == "-i":
        at += 1
    at += 2  # container and kcadm path
    method = args[at]
    path = args[at + 1] if at + 1 < len(args) and not args[at + 1].startswith("-") else ""
    joined = " ".join(args)
    if method == "get" and path == "realms/saintvision":
        print(json.dumps({"realm":"saintvision","enabled":True,"accessTokenLifespan":300,"sslRequired":"external"}))
    elif method == "get" and path == "clients" and "clientId=sv-api" in joined:
        print("api-id")
    elif method == "get" and path == "clients" and "clientId=sv-portal" in joined:
        print("portal-id")
    elif method == "get" and path == "clients/api-id":
        print(json.dumps({"clientId":"sv-api"}))
    elif method == "get" and path == "clients/portal-id":
        print(json.dumps({"clientId":"sv-portal"}))
    elif method == "get" and path == "clients/portal-id/protocol-mappers/models":
        print("time-id,fresh-auth-time")
        print("amr-id,fresh-auth-amr")
    elif method == "get" and path == "authentication/flows/browser/executions":
        print(json.dumps([
            {"id":"pwd-exec","providerId":"auth-username-password-form","authenticationConfig":"pwd-config"},
            {"id":"otp-exec","providerId":"auth-otp-form","authenticationConfig":"otp-config"}
        ]))
    elif method == "get" and path == "client-scopes":
        print("scope-id,inv.api")
    elif method == "get" and path == "clients/portal-id/default-client-scopes":
        print(json.dumps([{"name":"inv.api"}]))
    elif method == "get" and path == "client-scopes/scope-id":
        print(json.dumps({"name":"inv.api"}))
    elif method == "get" and path == "authentication/config/pwd-config":
        print(json.dumps({"config":{}}))
    elif method == "get" and path == "authentication/config/otp-config":
        print(json.dumps({"config":{}}))
    raise SystemExit(0)
""",
        encoding="utf-8",
    )
    executable.chmod(0o700)
    if os.name == "nt":
        python3 = tmp_path / "python3"
        python3.write_text(
            f"#!/usr/bin/env bash\nexec '{Path(sys.executable).as_posix()}' \"$@\"\n",
            encoding="utf-8",
        )
        python3.chmod(0o700)
    return executable, log


def _bash() -> str | None:
    if os.name == "nt":
        git_bash = Path(r"C:\Program Files\Git\bin\bash.exe")
        return str(git_bash) if git_bash.is_file() else None
    return shutil.which("bash")


def test_fresh_auth_only_behaviour_allows_exactly_four_realm_mutations(tmp_path):
    """A removed realm/client/scope guard must add a call and fail this allowlist."""
    bash = _bash()
    if bash is None:
        pytest.skip("bash is required to execute the configurator behaviour test")
    _fake, log = _fake_docker(tmp_path)
    checker = tmp_path / "checker.py"
    checker.write_text("import sys; sys.stdin.read(); raise SystemExit(0)\n", encoding="utf-8")
    env = {
        **os.environ,
        "PATH": str(tmp_path) + os.pathsep + os.environ.get("PATH", ""),
        "SV_FAKE_DOCKER_LOG": str(log),
        "SV_IDP_APPLY_MODE": "fresh-auth-only",
        "SV_REALM_CHECKER": str(checker),
    }
    completed = subprocess.run(
        [bash, "deploy/intranet/idp-realm.sh"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    calls = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    mutations = []
    for call in calls:
        if not call or call[0] != "exec":
            continue
        at = 1 + (call[1] == "-i")
        method_at = at + 2
        if len(call) <= method_at + 1 or call[method_at] not in {"create", "update", "delete"}:
            continue
        mutations.append((call[method_at], call[method_at + 1]))
    assert mutations == [
        ("update", "clients/portal-id/protocol-mappers/models/time-id"),
        ("update", "clients/portal-id/protocol-mappers/models/amr-id"),
        ("update", "authentication/config/pwd-config"),
        ("update", "authentication/config/otp-config"),
    ]


def test_unknown_apply_mode_exits_before_any_docker_call(tmp_path):
    bash = _bash()
    if bash is None:
        pytest.skip("bash is required to execute the configurator behaviour test")
    _fake, log = _fake_docker(tmp_path)
    env = {
        **os.environ,
        "PATH": str(tmp_path) + os.pathsep + os.environ.get("PATH", ""),
        "SV_FAKE_DOCKER_LOG": str(log),
        "SV_IDP_APPLY_MODE": "unexpected",
    }
    completed = subprocess.run(
        [bash, "deploy/intranet/idp-realm.sh"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 2
    assert "unsupported SV_IDP_APPLY_MODE" in completed.stderr
    assert not log.exists()
