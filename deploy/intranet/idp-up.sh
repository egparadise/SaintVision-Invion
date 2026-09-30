#!/usr/bin/env bash
# Bring up the intranet identity provider: Keycloak with its own PostgreSQL.
#
# Run on the IdP node. Re-runnable: it recreates the containers from the same
# pinned digests and the same secrets files, and never regenerates a password that
# already exists -- regenerating one would lock Keycloak out of its own database.
#
# Images are pinned by digest, not tag: a tag is a moving target, and an identity
# provider is the last place to accept one. The tags the digests resolved to on
# 2026-09-30 are recorded beside them so a human can tell what they are looking at.
#
# SECRETS NEVER APPEAR IN ARGV OR IN THE CONTAINER CONFIG.
# "docker run -e PASSWORD=$SECRET" leaks twice: once into the host process list
# while it runs, and then permanently into "docker inspect" output, which is
# readable by anyone who can reach the daemon. So:
#   * PostgreSQL reads POSTGRES_PASSWORD_FILE;
#   * Keycloak starts through a launcher that sources a mounted file and execs
#     kc.sh, so KC_DB_PASSWORD and the bootstrap admin password exist only inside
#     the process, never in Config.Env.
#
# EACH CONTAINER GETS ONLY THE FILES IT NEEDS, mounted one by one. Mounting the
# whole secrets directory into both would hand the database container the
# Keycloak bootstrap admin password -- a credential it has no use for, in a
# container whose job is to serve one database to one client. The database sees
# exactly one file; Keycloak sees its own env file and the launcher.
# tests/core/test_idp_scripts_keep_secrets_out_of_argv.py fails if this regresses.
#
# THE 0700/0400/0500 MODES DEPEND ON A UID COINCIDENCE, and it is worth stating.
# These files are owned by the host user (uid 1000 on this node) and the Keycloak
# image runs as uid 1000, so the container reads them as their owner. The PostgreSQL
# image starts as root and drops to postgres afterwards, so root reads db-password
# before the step-down regardless of mode. On a host where the login user is not
# uid 1000, Keycloak would be unable to read its own secrets and would fail to start
# -- loudly, not silently, but the cause would be non-obvious. Fixing that properly
# means aligning the ownership rather than loosening the mode.
#
# TLS: pass SV_IDP_CERT_DIR pointing at a directory holding server-chain.pem and
# server-key.pem, and set SV_IDP_HOSTNAME_URL to the https issuer. Without it the
# server stays plaintext and is bound to loopback only -- see BIND_ADDRESS.
set -euo pipefail

KEYCLOAK_IMAGE="${SV_IDP_IMAGE:-quay.io/keycloak/keycloak@sha256:4ee8200b0fd00de0e3743b48220f4feadbdb52deb29730ed804f9364bc2be23f}"  # 26.4.7
POSTGRES_IMAGE="${SV_IDP_DB_IMAGE:-postgres@sha256:ab8380566c3ea09690a9ecaa85a59d82bfc6eb86744151a2a54335866c83a3e9}"          # 16.10
SV_IDP_HOME="${SV_IDP_HOME:-$HOME/.sv-idp}"
NETWORK="${SV_IDP_NETWORK:-sv-idp-net}"
VOLUME="${SV_IDP_VOLUME:-sv-idp-db-data}"
DB_CONTAINER="${SV_IDP_DB_CONTAINER:-sv-idp-db}"
CONTAINER="${SV_IDP_CONTAINER:-sv-idp}"
# Every container this script creates carries this label, and it refuses to remove
# a container carrying somebody else's. Other projects run on these nodes.
OWNER="${SV_IDP_OWNER:-card152-intranet-idp}"
OWNER_KEY="sv.owner"

# The issuer Keycloak advertises. Every token carries it and the control plane
# compares it byte for byte, so changing this is a coordinated change: see the
# TLS cutover step in the runbook.
HOSTNAME_URL="${SV_IDP_HOSTNAME_URL:-http://idp.sv.lan:8080}"
# Ignore the request Host header and always issue the configured hostname. With
# hostname-strict=false a request arriving under any other name would be echoed
# back into the URLs Keycloak publishes.
HOSTNAME_STRICT="${SV_IDP_HOSTNAME_STRICT:-true}"
# A directory holding server-chain.pem (leaf + intermediate) and server-key.pem.
# Empty means plaintext, which is only acceptable on loopback.
CERT_DIR="${SV_IDP_CERT_DIR:-}"
HTTPS_PORT="${SV_IDP_HTTPS_PORT:-443}"
# Plaintext port. Published only when there is no TLS; with TLS it stays inside
# the container network so kcadm can reach it through "docker exec" without a
# Java truststore, and nothing on the LAN can reach it at all.
PORT="${SV_IDP_PORT:-8080}"
# Loopback by default. Before TLS termination exists, publishing the plaintext
# port on the LAN puts a login form and a token endpoint on the network.
BIND_ADDRESS="${SV_IDP_BIND_ADDRESS:-127.0.0.1}"

umask 077
mkdir -p "$SV_IDP_HOME"
SECRETS="$SV_IDP_HOME/secrets"
mkdir -p "$SECRETS"
chmod 700 "$SECRETS"

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

# Rewritten every run from the one source of truth, so the mounted copies can
# never drift from $SV_IDP_HOME/env. The previous run left them read-only, so make
# them writable again first -- a re-run must not fail on its own hardening.
chmod u+w "$SECRETS"/* 2>/dev/null || true
printf '%s' "$SV_IDP_DB_PASSWORD" > "$SECRETS/db-password"
{
  printf 'KC_DB_PASSWORD=%s\n' "$SV_IDP_DB_PASSWORD"
  printf 'KC_BOOTSTRAP_ADMIN_USERNAME=%s\n' "$SV_IDP_ADMIN_USER"
  printf 'KC_BOOTSTRAP_ADMIN_PASSWORD=%s\n' "$SV_IDP_ADMIN_PASSWORD"
} > "$SECRETS/keycloak.env"
chmod 400 "$SECRETS/db-password" "$SECRETS/keycloak.env"

# The launcher is not secret; the file it reads is. Keeping the export inside the
# container is what keeps the values out of Config.Env.
cat > "$SECRETS/keycloak-entry.sh" <<'LAUNCHER'
#!/bin/sh
set -eu
set -a
. /run/secrets/keycloak.env
set +a
exec /opt/keycloak/bin/kc.sh "$@"
LAUNCHER
chmod 500 "$SECRETS/keycloak-entry.sh"

# A container we did not create is never removed. An unlabelled container under
# our own name is one of ours from before labels existed, so that one we replace.
remove_if_ours() {
  name="$1"
  owner="$(docker inspect --format "{{index .Config.Labels \"$OWNER_KEY\"}}" "$name" 2>/dev/null || true)"
  if [ -n "$owner" ] && [ "$owner" != "$OWNER" ]; then
    echo "refusing to remove $name: owned by '$owner', not '$OWNER'" >&2
    exit 2
  fi
  docker rm -f "$name" >/dev/null 2>&1 || true
}

docker network inspect "$NETWORK" >/dev/null 2>&1 || docker network create "$NETWORK" >/dev/null
docker volume inspect "$VOLUME" >/dev/null 2>&1 || docker volume create "$VOLUME" >/dev/null

# The database is not published. Keycloak reaches it over the container network,
# and nothing else has any business talking to it.
remove_if_ours "$DB_CONTAINER"
docker run -d --name "$DB_CONTAINER" --network "$NETWORK" --restart unless-stopped \
  --label "$OWNER_KEY=$OWNER" \
  -e POSTGRES_DB=keycloak -e POSTGRES_USER=keycloak \
  -e POSTGRES_PASSWORD_FILE=/run/secrets/db-password \
  -v "$SECRETS/db-password:/run/secrets/db-password:ro" \
  -v "$VOLUME:/var/lib/postgresql/data" \
  "$POSTGRES_IMAGE" >/dev/null

for _ in $(seq 1 60); do
  docker exec "$DB_CONTAINER" pg_isready -U keycloak -d keycloak >/dev/null 2>&1 && break
  sleep 1
done

start_args="start --hostname=$HOSTNAME_URL --hostname-strict=$HOSTNAME_STRICT --http-enabled=true"
publish=""
mounts=""
if [ -n "$CERT_DIR" ]; then
  [ -f "$CERT_DIR/server-chain.pem" ] || { echo "$CERT_DIR/server-chain.pem missing" >&2; exit 2; }
  [ -f "$CERT_DIR/server-key.pem" ] || { echo "$CERT_DIR/server-key.pem missing" >&2; exit 2; }
  chmod 700 "$CERT_DIR"; chmod 444 "$CERT_DIR/server-chain.pem"; chmod 400 "$CERT_DIR/server-key.pem"
  start_args="$start_args --https-port=8443"
  start_args="$start_args --https-certificate-file=/run/certs/server-chain.pem"
  start_args="$start_args --https-certificate-key-file=/run/certs/server-key.pem"
  mounts="-v $CERT_DIR:/run/certs:ro"
  # With TLS the plaintext port is deliberately NOT published.
  publish="-p $HTTPS_PORT:8443"
else
  publish="-p $BIND_ADDRESS:$PORT:8080"
fi

remove_if_ours "$CONTAINER"
# shellcheck disable=SC2086
docker run -d --name "$CONTAINER" --network "$NETWORK" --restart unless-stopped \
  --label "$OWNER_KEY=$OWNER" \
  $publish $mounts \
  -e KC_DB=postgres -e KC_DB_URL_HOST="$DB_CONTAINER" -e KC_DB_USERNAME=keycloak \
  -e KC_HEALTH_ENABLED=true \
  -v "$SECRETS/keycloak.env:/run/secrets/keycloak.env:ro" \
  -v "$SECRETS/keycloak-entry.sh:/run/secrets/keycloak-entry.sh:ro" \
  --entrypoint /run/secrets/keycloak-entry.sh \
  "$KEYCLOAK_IMAGE" \
  $start_args >/dev/null

for i in $(seq 1 120); do
  # HTTP/1.1 with a Host header. Vert.x answers an HTTP/1.0 request that omits one
  # by throwing, so a probe without it reports a healthy server as unreachable.
  if docker exec "$CONTAINER" sh -c '
      exec 3<>/dev/tcp/127.0.0.1/8080 || exit 1
      printf "GET /realms/master HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n" >&3
      head -1 <&3' 2>/dev/null | grep -q " 200"; then
    if [ -n "$CERT_DIR" ]; then
      echo "idp up after ${i}s, https on $HTTPS_PORT, issuing as $HOSTNAME_URL (plaintext port unpublished)"
    else
      echo "idp up after ${i}s on $BIND_ADDRESS:$PORT, issuing as $HOSTNAME_URL"
    fi
    exit 0
  fi
  sleep 1
done
echo "idp did not answer" >&2
exit 1
