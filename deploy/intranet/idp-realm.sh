#!/usr/bin/env bash
# Configure the intranet Keycloak realm so it mints tokens inv.identity accepts.
#
# Run on the IdP node. Re-runnable, and re-runnable is the point: it re-applies the
# canonical values every time rather than only creating what is missing, because a
# relaxed setting leaves every object in place and a create-if-missing script would
# keep reporting success. It ends by reading the live configuration back and failing
# closed if anything drifted.
#
# The realm is not the interesting part -- the token shape is. inv.identity.verify
# is far stricter than a default OIDC client, and each setting below exists because
# the verifier refuses a token without it:
#
#   typ=at+jwt      header["typ"] must be at+jwt (RFC 9068), not the Keycloak default JWT
#   aud=sv-api      strict_aud forbids a list, so "account" must not be in the audience
#   client_id       "require" lists client_id; Keycloak emits azp instead
#   scope inv.api   the verifier refuses a token whose scope lacks inv.api, which needs
#                   both the default-scope assignment AND include.in.token.scope on the
#                   scope itself -- the assignment alone puts nothing in the token
#   exp-iat<=3600   accessTokenLifespan stays at 300s
#
# NO PASSWORD APPEARS IN ANY ARGV. The admin password is read inside the container
# from the mounted secrets file and handed to kcadm through KC_CLI_PASSWORD -- its
# interactive prompt is not usable here, because without a TTY kcadm refuses with
# "Console is not active". User passwords are sent as stdin JSON to the
# reset-password endpoint. tests/core/test_idp_scripts_keep_secrets_out_of_argv.py
# fails if this regresses.
set -euo pipefail

REALM="${SV_IDP_REALM:-saintvision}"
API_CLIENT="${SV_IDP_API_CLIENT:-sv-api}"
PORTAL_CLIENT="${SV_IDP_PORTAL_CLIENT:-sv-portal}"
SCOPE="${SV_IDP_SCOPE:-inv.api}"
CONTAINER="${SV_IDP_CONTAINER:-sv-idp}"
USERS_FILE="${SV_IDP_USERS_ENV:-$HOME/.sv-idp/env-users}"
SECRETS_IN_CONTAINER="${SV_IDP_CONTAINER_SECRETS:-/run/secrets/keycloak.env}"
# https, or loopback. A loopback redirect never leaves the machine, which is why
# native-app flows may use it; "http://portal.sv.lan" would carry codes over the LAN.
PORTAL_ORIGINS="${SV_IDP_PORTAL_ORIGINS:-https://portal.sv.lan http://localhost:3005}"
EMAIL_DOMAIN="${SV_IDP_EMAIL_DOMAIN:-sv.lan}"
TOKEN_LIFESPAN="${SV_IDP_TOKEN_LIFESPAN:-300}"
BROWSER_FLOW="${SV_IDP_BROWSER_FLOW:-browser}"
# "external" rather than "all": the plaintext listener is not published, so the only
# http reachability is inside the container, which is where kcadm runs. "all" would
# reject that path and buy nothing, because no network client can reach http at all.
SSL_REQUIRED="${SV_IDP_SSL_REQUIRED:-external}"
CHECKER="${SV_REALM_CHECKER:-}"

set -a; . "$USERS_FILE"; set +a

# -i only where a heredoc feeds kcadm. Without that split, a "docker exec -i"
# with no input of its own swallows the rest of this script when it is piped
# into bash -s, and the run stops after the login line with no error.
kc() { docker exec "$CONTAINER" /opt/keycloak/bin/kcadm.sh "$@"; }
kc_in() { docker exec -i "$CONTAINER" /opt/keycloak/bin/kcadm.sh "$@"; }
csv() { kc "$@" --format csv --noquotes; }

# The admin password is read from the mounted 0400 file INSIDE the container and
# handed to kcadm through KC_CLI_PASSWORD, which is kcadm's own documented
# alternative to --password. What this achieves, precisely:
#   * nothing on the host command line, so it is not in the host process list;
#   * nothing in "docker run -e", so it is not in Config.Env and not in the
#     permanent record "docker inspect" returns;
#   * nothing in any argv, so no process list on either side shows it.
# It is in the environment of that one short-lived process, readable through
# /proc by uid 1000 in this container -- the same uid that can already read the
# mounted file, so this adds no reader. kcadm's interactive prompt is not an
# option here: without a TTY it refuses with "Console is not active".
docker exec "$CONTAINER" sh -c '
  set -eu
  . '"$SECRETS_IN_CONTAINER"'
  KC_CLI_PASSWORD="$KC_BOOTSTRAP_ADMIN_PASSWORD" \
    /opt/keycloak/bin/kcadm.sh config credentials \
      --server http://localhost:8080 --realm master --user "$KC_BOOTSTRAP_ADMIN_USERNAME"
' >/dev/null

if ! kc get "realms/$REALM" --fields realm >/dev/null 2>&1; then
  kc create realms -s "realm=$REALM" -s enabled=true
fi
# Re-asserted every run, not only on create. The verifier refuses exp - iat > 3600,
# so a widened lifespan is a broken realm that still has all the right objects in it,
# and a "create if missing" script would keep reporting success.
kc update "realms/$REALM" -s enabled=true -s "accessTokenLifespan=$TOKEN_LIFESPAN" \
  -s "sslRequired=$SSL_REQUIRED"

client_id_of() { csv get clients -r "$REALM" -q "clientId=$1" --fields id | head -1; }

# The API client exists only to name an audience; it never logs anyone in.
if [ -z "$(client_id_of "$API_CLIENT")" ]; then
  kc create clients -r "$REALM" -s "clientId=$API_CLIENT" -s enabled=true
fi
API_ID="$(client_id_of "$API_CLIENT")"
kc update "clients/$API_ID" -r "$REALM" -s enabled=true -s publicClient=false \
  -s standardFlowEnabled=false -s directAccessGrantsEnabled=false \
  -s implicitFlowEnabled=false -s serviceAccountsEnabled=false

# The portal is a browser client: public, so PKCE S256 is mandatory, and no
# direct access grants -- a password grant from a public client is a credential
# funnel, and the code below turns it off on every run in case someone enabled it.
if [ -z "$(client_id_of "$PORTAL_CLIENT")" ]; then
  kc create clients -r "$REALM" -s "clientId=$PORTAL_CLIENT" -s enabled=true \
    -s publicClient=true -s standardFlowEnabled=true
fi
PORTAL_ID="$(client_id_of "$PORTAL_CLIENT")"

redirects=""; origins=""
for origin in $PORTAL_ORIGINS; do
  redirects="$redirects\"$origin/*\","; origins="$origins\"$origin\","
done
kc_in update "clients/$PORTAL_ID" -r "$REALM" -f - <<JSON
{
  "enabled": true,
  "publicClient": true,
  "standardFlowEnabled": true,
  "directAccessGrantsEnabled": false,
  "implicitFlowEnabled": false,
  "serviceAccountsEnabled": false,
  "redirectUris": [${redirects%,}],
  "webOrigins": [${origins%,}],
  "attributes": {
    "pkce.code.challenge.method": "S256",
    "access.token.header.type.rfc9068": "true"
  }
}
JSON

mapper_id() { csv get "clients/$PORTAL_ID/protocol-mappers/models" -r "$REALM" --fields id,name \
  | awk -F, -v want="$1" '$2 == want {print $1}' | head -1; }

# Created if absent, then overwritten either way: a mapper that stopped writing to
# the access token is still a mapper, and "create if missing" would leave it alone.
if [ -z "$(mapper_id "$API_CLIENT-audience")" ]; then
  kc_in create "clients/$PORTAL_ID/protocol-mappers/models" -r "$REALM" -f - <<JSON
{"name": "$API_CLIENT-audience", "protocol": "openid-connect",
 "protocolMapper": "oidc-audience-mapper",
 "config": {"included.client.audience": "$API_CLIENT",
            "access.token.claim": "true", "id.token.claim": "false"}}
JSON
fi
AUDIENCE_MAPPER_ID="$(mapper_id "$API_CLIENT-audience")"
kc_in update "clients/$PORTAL_ID/protocol-mappers/models/$AUDIENCE_MAPPER_ID" -r "$REALM" -f - <<JSON
{"id": "$AUDIENCE_MAPPER_ID", "name": "$API_CLIENT-audience", "protocol": "openid-connect",
 "protocolMapper": "oidc-audience-mapper",
 "config": {"included.client.audience": "$API_CLIENT",
            "access.token.claim": "true", "id.token.claim": "false"}}
JSON

# inv.identity requires a client_id claim; Keycloak emits azp and nothing else.
if [ -z "$(mapper_id "client-id")" ]; then
  kc_in create "clients/$PORTAL_ID/protocol-mappers/models" -r "$REALM" -f - <<JSON
{"name": "client-id", "protocol": "openid-connect",
 "protocolMapper": "oidc-hardcoded-claim-mapper",
 "config": {"claim.name": "client_id", "claim.value": "$PORTAL_CLIENT",
            "jsonType.label": "String",
            "access.token.claim": "true", "id.token.claim": "false"}}
JSON
fi
CLIENT_ID_MAPPER_ID="$(mapper_id "client-id")"
kc_in update "clients/$PORTAL_ID/protocol-mappers/models/$CLIENT_ID_MAPPER_ID" -r "$REALM" -f - <<JSON
{"id": "$CLIENT_ID_MAPPER_ID", "name": "client-id", "protocol": "openid-connect",
 "protocolMapper": "oidc-hardcoded-claim-mapper",
 "config": {"claim.name": "client_id", "claim.value": "$PORTAL_CLIENT",
            "jsonType.label": "String",
            "access.token.claim": "true", "id.token.claim": "false"}}
JSON

# The release-acceptance boundary never decodes an unverified token to recover
# these values.  auth_time comes from Keycloak's server-side user-session note;
# AMR comes from the completed authenticator execution references configured
# below.  Both mappers write access tokens only.  Keycloak 26 also assigns a
# realm-wide "basic" scope with an auth_time mapper.  This client-local mapper
# deliberately pins the same AUTH_TIME source, so the contract does not depend
# on realm-default-scope membership; both writers produce the same scalar.
if [ -z "$(mapper_id "fresh-auth-time")" ]; then
  kc_in create "clients/$PORTAL_ID/protocol-mappers/models" -r "$REALM" -f - <<JSON
{"name": "fresh-auth-time", "protocol": "openid-connect",
 "protocolMapper": "oidc-usersessionmodel-note-mapper",
 "config": {"user.session.note": "AUTH_TIME", "claim.name": "auth_time",
            "jsonType.label": "long", "access.token.claim": "true",
            "id.token.claim": "false", "userinfo.token.claim": "false"}}
JSON
fi
AUTH_TIME_MAPPER_ID="$(mapper_id "fresh-auth-time")"
kc_in update "clients/$PORTAL_ID/protocol-mappers/models/$AUTH_TIME_MAPPER_ID" -r "$REALM" -f - <<JSON
{"id": "$AUTH_TIME_MAPPER_ID", "name": "fresh-auth-time", "protocol": "openid-connect",
 "protocolMapper": "oidc-usersessionmodel-note-mapper",
 "config": {"user.session.note": "AUTH_TIME", "claim.name": "auth_time",
            "jsonType.label": "long", "access.token.claim": "true",
            "id.token.claim": "false", "userinfo.token.claim": "false"}}
JSON

if [ -z "$(mapper_id "fresh-auth-amr")" ]; then
  kc_in create "clients/$PORTAL_ID/protocol-mappers/models" -r "$REALM" -f - <<JSON
{"name": "fresh-auth-amr", "protocol": "openid-connect",
 "protocolMapper": "oidc-amr-mapper",
 "config": {"access.token.claim": "true", "id.token.claim": "false",
            "lightweight.claim": "false"}}
JSON
fi
AMR_MAPPER_ID="$(mapper_id "fresh-auth-amr")"
kc_in update "clients/$PORTAL_ID/protocol-mappers/models/$AMR_MAPPER_ID" -r "$REALM" -f - <<JSON
{"id": "$AMR_MAPPER_ID", "name": "fresh-auth-amr", "protocol": "openid-connect",
 "protocolMapper": "oidc-amr-mapper",
 "config": {"access.token.claim": "true", "id.token.claim": "false",
            "lightweight.claim": "false"}}
JSON

# Keycloak's AMR mapper reports only completed executions that have an explicit
# RFC 8176 reference.  The default browser flow has password and conditional OTP
# executions; pin both to the 300-second step-up window.  Hardware/software key
# values remain supported by the server policy, but are not claimed here because
# this realm does not yet configure such an execution.
BROWSER_EXECUTIONS="$(kc get "authentication/flows/$BROWSER_FLOW/executions" -r "$REALM")"
execution_info() {
  printf '%s' "$BROWSER_EXECUTIONS" | python3 -c '
import json, sys
provider = sys.argv[1]
matches = [item for item in json.load(sys.stdin) if item.get("providerId") == provider]
if len(matches) != 1:
    raise SystemExit(f"expected one {provider} execution, found {len(matches)}")
item = matches[0]
print(item.get("id", "") + "\t" + (item.get("authenticationConfig") or ""))
' "$1"
}

ensure_execution_reference() {
  provider="$1"; reference="$2"; alias="$3"
  info="$(execution_info "$provider")"
  execution_id="${info%%$'\t'*}"
  config_id="${info#*$'\t'}"
  if [ -z "$execution_id" ]; then
    echo "refusing to report success: $provider execution has no id" >&2
    exit 2
  fi
  if [ -z "$config_id" ]; then
    kc_in create "authentication/executions/$execution_id/config" -r "$REALM" -f - >/dev/null <<JSON
{"alias": "$alias", "config": {"default.reference.value": "$reference",
 "default.reference.maxAge": "300"}}
JSON
    BROWSER_EXECUTIONS="$(kc get "authentication/flows/$BROWSER_FLOW/executions" -r "$REALM")"
    info="$(execution_info "$provider")"
    config_id="${info#*$'\t'}"
  fi
  if [ -z "$config_id" ]; then
    echo "refusing to report success: $provider reference config was not created" >&2
    exit 2
  fi
  kc_in update "authentication/config/$config_id" -r "$REALM" -f - >/dev/null <<JSON
{"id": "$config_id", "alias": "$alias",
 "config": {"default.reference.value": "$reference", "default.reference.maxAge": "300"}}
JSON
  printf '%s' "$config_id"
}

PWD_REFERENCE_CONFIG_ID="$(ensure_execution_reference "auth-username-password-form" "pwd" "sv-amr-pwd")"
OTP_REFERENCE_CONFIG_ID="$(ensure_execution_reference "auth-otp-form" "otp" "sv-amr-otp")"

# strict_aud forbids an audience list, and the built-in "roles" scope adds
# "account" through its audience-resolve mapper. Drop the scope, not the mapper:
# the mapper lives in a realm-wide scope other clients may still want.
ROLES_ID="$(csv get "clients/$PORTAL_ID/default-client-scopes" -r "$REALM" --fields id,name \
  | awk -F, '$2 == "roles" {print $1}' | head -1)"
if [ -n "$ROLES_ID" ]; then
  kc delete "clients/$PORTAL_ID/default-client-scopes/$ROLES_ID" -r "$REALM"
fi

scope_id() { csv get client-scopes -r "$REALM" --fields id,name \
  | awk -F, -v want="$1" '$2 == want {print $1}' | head -1; }

if [ -z "$(scope_id "$SCOPE")" ]; then
  kc_in create client-scopes -r "$REALM" -f - <<JSON
{"name": "$SCOPE", "protocol": "openid-connect",
 "attributes": {"include.in.token.scope": "true", "display.on.consent.screen": "false"}}
JSON
fi
SCOPE_ID="$(scope_id "$SCOPE")"
# Re-applied every run. Assigning the scope to the client is not enough: with
# include.in.token.scope false the scope is assigned and the token still has no
# inv.api in it, so the verifier answers 401 while this script reports success.
kc_in update "client-scopes/$SCOPE_ID" -r "$REALM" -f - <<JSON
{"id": "$SCOPE_ID", "name": "$SCOPE", "protocol": "openid-connect",
 "attributes": {"include.in.token.scope": "true", "display.on.consent.screen": "false"}}
JSON
if ! csv get "clients/$PORTAL_ID/default-client-scopes" -r "$REALM" --fields name \
  | grep -qx "$SCOPE"; then
  kc update "clients/$PORTAL_ID/default-client-scopes/$SCOPE_ID" -r "$REALM"
fi

for pair in "$SV_USER1:$SV_USER1_PASSWORD" "$SV_USER2:$SV_USER2_PASSWORD"; do
  username="${pair%%:*}"; password="${pair#*:}"
  if [ -z "$(csv get users -r "$REALM" -q "username=$username" --fields id | head -1)" ]; then
    kc create users -r "$REALM" -s "username=$username" -s enabled=true
  fi
  uid="$(csv get users -r "$REALM" -q "username=$username" --fields id | head -1)"
  # A user with no profile trips the VERIFY_PROFILE required action, and every grant
  # then fails with "Account is not fully set up" -- which reads like a realm fault
  # rather than a missing surname. Fill the profile and clear the actions.
  kc_in update "users/$uid" -r "$REALM" -f - <<JSON
{"enabled": true, "emailVerified": true, "requiredActions": [],
 "email": "$username@$EMAIL_DOMAIN",
 "firstName": "${username%%.*}", "lastName": "${username#*.}"}
JSON
  # reset-password over stdin, so the value is in no argv. "kcadm set-password
  # --new-password X" would put it in both the host and the container process list.
  kc_in update "users/$uid/reset-password" -r "$REALM" -f - <<JSON
{"type": "password", "value": "$password", "temporary": false}
JSON
done

# Setting the realm is not the same as knowing it is still set. Read the live
# configuration back and judge it; an admin-console click that relaxes any of this
# leaves every object in place, so only a read-back catches it.
if [ -z "$CHECKER" ]; then
  for candidate in "$(dirname "${BASH_SOURCE[0]}")/../../tools/check_idp_realm_config.py" \
                   "$HOME/.sv-idp/bin/check_idp_realm_config.py"; do
    [ -f "$candidate" ] && CHECKER="$candidate" && break
  done
fi
if [ -z "$CHECKER" ]; then
  echo "refusing to report success: check_idp_realm_config.py not found." \
       "Set SV_REALM_CHECKER to its path." >&2
  exit 2
fi

SNAPSHOT="$(
  {
    kc get "realms/$REALM"
    kc get "clients/$API_ID" -r "$REALM"
    kc get "clients/$PORTAL_ID" -r "$REALM"
    kc get "clients/$PORTAL_ID/default-client-scopes" -r "$REALM"
    kc get "client-scopes/$SCOPE_ID" -r "$REALM"
    kc get "authentication/config/$PWD_REFERENCE_CONFIG_ID" -r "$REALM"
    kc get "authentication/config/$OTP_REFERENCE_CONFIG_ID" -r "$REALM"
  } | python3 -c '
import json, sys
# kcadm prints one JSON document per call; read them in order.
decoder, text, at, documents = json.JSONDecoder(), sys.stdin.read(), 0, []
while at < len(text):
    while at < len(text) and text[at].isspace():
        at += 1
    if at >= len(text):
        break
    value, at = decoder.raw_decode(text, at)
    documents.append(value)
realm, api, portal, scopes, scope, password_ref, otp_ref = documents
portal["defaultClientScopes"] = [s.get("name") for s in scopes]
print(json.dumps({"realm": realm,
                  "clients": {api["clientId"]: api, portal["clientId"]: portal},
                  "clientScopes": {scope["name"]: scope},
                  "authenticatorReferences": {
                      "auth-username-password-form": password_ref,
                      "auth-otp-form": otp_ref}}))
'
)"

printf "%s" "$SNAPSHOT" | python3 "$CHECKER" --realm "$REALM" \
  --api-client "$API_CLIENT" --portal-client "$PORTAL_CLIENT" --scope "$SCOPE"
