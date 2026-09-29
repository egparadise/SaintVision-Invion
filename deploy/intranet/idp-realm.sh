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
PORTAL_ORIGINS="${SV_IDP_PORTAL_ORIGINS:-https://portal.sv.lan http://portal.sv.lan http://localhost:3005}"
EMAIL_DOMAIN="${SV_IDP_EMAIL_DOMAIN:-sv.lan}"

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
  kc create realms -s "realm=$REALM" -s enabled=true -s accessTokenLifespan=300
fi

client_id_of() { csv get clients -r "$REALM" -q "clientId=$1" --fields id | head -1; }

# The API client exists only to name an audience; it never logs anyone in.
if [ -z "$(client_id_of "$API_CLIENT")" ]; then
  kc create clients -r "$REALM" -s "clientId=$API_CLIENT" -s enabled=true \
    -s publicClient=false -s standardFlowEnabled=false \
    -s directAccessGrantsEnabled=false -s serviceAccountsEnabled=false
fi

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
  "publicClient": true,
  "standardFlowEnabled": true,
  "directAccessGrantsEnabled": false,
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

echo "realm=$REALM portal=$PORTAL_CLIENT audience=$API_CLIENT scope=$SCOPE configured"
