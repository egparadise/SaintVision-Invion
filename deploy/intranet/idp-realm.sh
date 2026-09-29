#!/usr/bin/env bash
# Configure the intranet Keycloak realm so it mints tokens inv.identity accepts.
#
# Run on the IdP node. Re-runnable: every step checks before it creates.
#
# The realm is not the interesting part -- the token shape is. inv.identity.verify
# is far stricter than a default OIDC client, and each setting below exists because
# the verifier refuses a token without it:
#
#   typ=at+jwt      header["typ"] must be at+jwt (RFC 9068), not the Keycloak default JWT
#   aud=sv-api      strict_aud forbids a list, so "account" must not be in the audience
#   client_id       "require" lists client_id; Keycloak emits azp instead
#   scope inv.api   the verifier refuses a token whose scope lacks inv.api
#   exp-iat<=3600   accessTokenLifespan stays at 300s
#
# Secrets come from ~/.sv-idp/env and ~/.sv-idp/env-users (0600, never printed).
set -euo pipefail

REALM="${SV_IDP_REALM:-saintvision}"
API_CLIENT="${SV_IDP_API_CLIENT:-sv-api}"
PORTAL_CLIENT="${SV_IDP_PORTAL_CLIENT:-sv-portal}"
SCOPE="${SV_IDP_SCOPE:-inv.api}"
CONTAINER="${SV_IDP_CONTAINER:-sv-idp}"
ENV_FILE="${SV_IDP_ENV:-$HOME/.sv-idp/env}"
USERS_FILE="${SV_IDP_USERS_ENV:-$HOME/.sv-idp/env-users}"
# https, or loopback. A loopback redirect never leaves the machine, which is why
# native-app flows may use it; "http://portal.sv.lan" would carry codes over the LAN.
PORTAL_ORIGINS="${SV_IDP_PORTAL_ORIGINS:-https://portal.sv.lan http://localhost:3005}"
EMAIL_DOMAIN="${SV_IDP_EMAIL_DOMAIN:-sv.lan}"
TOKEN_LIFESPAN="${SV_IDP_TOKEN_LIFESPAN:-300}"
CHECKER="${SV_REALM_CHECKER:-}"

set -a; . "$ENV_FILE"; . "$USERS_FILE"; set +a

# -i only where a heredoc feeds kcadm. Without that split, a "docker exec -i"
# with no input of its own swallows the rest of this script when it is piped
# into bash -s, and the run stops after the login line with no error.
kc() { docker exec "$CONTAINER" /opt/keycloak/bin/kcadm.sh "$@"; }
kc_in() { docker exec -i "$CONTAINER" /opt/keycloak/bin/kcadm.sh "$@"; }
csv() { kc "$@" --format csv --noquotes; }

kc config credentials --server http://localhost:8080 --realm master \
  --user "$SV_IDP_ADMIN_USER" --password "$SV_IDP_ADMIN_PASSWORD" >/dev/null

if ! kc get "realms/$REALM" --fields realm >/dev/null 2>&1; then
  kc create realms -s "realm=$REALM" -s enabled=true
fi
# Re-asserted every run, not only on create. The verifier refuses exp - iat > 3600,
# so a widened lifespan is a broken realm that still has all the right objects in it,
# and a "create if missing" script would keep reporting success.
kc update "realms/$REALM" -s enabled=true -s "accessTokenLifespan=$TOKEN_LIFESPAN"

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
  kc set-password -r "$REALM" --userid "$uid" --new-password "$password"
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
realm, api, portal, scopes = documents
portal["defaultClientScopes"] = [s.get("name") for s in scopes]
print(json.dumps({"realm": realm,
                  "clients": {api["clientId"]: api, portal["clientId"]: portal}}))
'
)"

printf "%s" "$SNAPSHOT" | python3 "$CHECKER" --realm "$REALM" \
  --api-client "$API_CLIENT" --portal-client "$PORTAL_CLIENT" --scope "$SCOPE"
