#!/usr/bin/env bash
# Bring up the intranet identity provider: Keycloak with its own PostgreSQL.
#
# Run on the IdP node. Re-runnable: it recreates the containers from the same
# pinned digests and the same secrets file, and never regenerates a password that
# already exists -- regenerating one would lock Keycloak out of its own database.
#
# Images are pinned by digest, not tag: a tag is a moving target, and an identity
# provider is the last place to accept one. The tags the digests resolved to on
# 2026-09-30 are recorded beside them so a human can tell what they are looking at.
#
# Secrets are generated into $SV_IDP_HOME/env with mode 0600 and are never printed.
# They are not in this repository and must not be.
set -euo pipefail

KEYCLOAK_IMAGE="${SV_IDP_IMAGE:-quay.io/keycloak/keycloak@sha256:4ee8200b0fd00de0e3743b48220f4feadbdb52deb29730ed804f9364bc2be23f}"  # 26.4.7
POSTGRES_IMAGE="${SV_IDP_DB_IMAGE:-postgres@sha256:ab8380566c3ea09690a9ecaa85a59d82bfc6eb86744151a2a54335866c83a3e9}"          # 16.10
SV_IDP_HOME="${SV_IDP_HOME:-$HOME/.sv-idp}"
NETWORK="${SV_IDP_NETWORK:-sv-idp-net}"
VOLUME="${SV_IDP_VOLUME:-sv-idp-db-data}"
DB_CONTAINER="${SV_IDP_DB_CONTAINER:-sv-idp-db}"
CONTAINER="${SV_IDP_CONTAINER:-sv-idp}"
PORT="${SV_IDP_PORT:-8080}"
# The issuer Keycloak advertises. Every token carries it and the control plane
# compares it byte for byte, so changing this is a coordinated change: see the
# TLS cutover step in the runbook.
HOSTNAME_URL="${SV_IDP_HOSTNAME_URL:-http://idp.sv.lan:8080}"

umask 077
mkdir -p "$SV_IDP_HOME"

if [ ! -f "$SV_IDP_HOME/env" ]; then
  {
    printf 'SV_IDP_DB_PASSWORD=%s\n' "$(openssl rand -hex 32)"
    printf 'SV_IDP_ADMIN_USER=%s\n' "${SV_IDP_ADMIN_USER:-sv-idp-admin}"
    printf 'SV_IDP_ADMIN_PASSWORD=%s\n' "$(openssl rand -hex 32)"
  } > "$SV_IDP_HOME/env"
  chmod 600 "$SV_IDP_HOME/env"
  echo "generated $SV_IDP_HOME/env (0600)"
fi
if [ ! -f "$SV_IDP_HOME/env-users" ]; then
  {
    printf 'SV_USER1=%s\n' "${SV_USER1:-sv.operator}"
    printf 'SV_USER1_PASSWORD=%s\n' "$(openssl rand -hex 24)"
    printf 'SV_USER2=%s\n' "${SV_USER2:-sv.viewer}"
    printf 'SV_USER2_PASSWORD=%s\n' "$(openssl rand -hex 24)"
  } > "$SV_IDP_HOME/env-users"
  chmod 600 "$SV_IDP_HOME/env-users"
  echo "generated $SV_IDP_HOME/env-users (0600)"
fi
set -a; . "$SV_IDP_HOME/env"; set +a

docker network inspect "$NETWORK" >/dev/null 2>&1 || docker network create "$NETWORK" >/dev/null
docker volume inspect "$VOLUME" >/dev/null 2>&1 || docker volume create "$VOLUME" >/dev/null

# The database is not published. Keycloak reaches it over the container network,
# and nothing else has any business talking to it.
docker rm -f "$DB_CONTAINER" >/dev/null 2>&1 || true
docker run -d --name "$DB_CONTAINER" --network "$NETWORK" --restart unless-stopped \
  -e POSTGRES_DB=keycloak -e POSTGRES_USER=keycloak \
  -e POSTGRES_PASSWORD="$SV_IDP_DB_PASSWORD" \
  -v "$VOLUME:/var/lib/postgresql/data" \
  "$POSTGRES_IMAGE" >/dev/null

for _ in $(seq 1 60); do
  docker exec "$DB_CONTAINER" pg_isready -U keycloak -d keycloak >/dev/null 2>&1 && break
  sleep 1
done

docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
docker run -d --name "$CONTAINER" --network "$NETWORK" --restart unless-stopped \
  -p "$PORT:8080" \
  -e KC_DB=postgres -e KC_DB_URL_HOST="$DB_CONTAINER" \
  -e KC_DB_USERNAME=keycloak -e KC_DB_PASSWORD="$SV_IDP_DB_PASSWORD" \
  -e KC_BOOTSTRAP_ADMIN_USERNAME="$SV_IDP_ADMIN_USER" \
  -e KC_BOOTSTRAP_ADMIN_PASSWORD="$SV_IDP_ADMIN_PASSWORD" \
  -e KC_HEALTH_ENABLED=true \
  "$KEYCLOAK_IMAGE" \
  start --http-enabled=true "--hostname=$HOSTNAME_URL" --hostname-strict=false >/dev/null

for i in $(seq 1 120); do
  if curl -fsS "http://127.0.0.1:$PORT/realms/master" >/dev/null 2>&1; then
    echo "idp up after ${i}s on port $PORT, issuing as $HOSTNAME_URL"
    exit 0
  fi
  sleep 1
done
echo "idp did not answer on port $PORT" >&2
exit 1
