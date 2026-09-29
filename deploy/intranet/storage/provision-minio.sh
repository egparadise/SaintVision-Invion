#!/bin/sh
set -eu

IMAGE='docker.io/coollabsio/minio@sha256:72b4794d7faa001823364f8ee239717141327fc450a3264414f573a6abf3c629'
NAME='saintvision-intranet-minio'
ROLLBACK_NAME='saintvision-intranet-minio-card151-rollback'
CONFIG_DIR="${SV_STORAGE_CONFIG_DIR:-$HOME/.config/saintvision-intranet}"
DATA_DIR="${SV_STORAGE_DATA_DIR:-$HOME/.local/share/saintvision-intranet/minio/data}"
BIND_ADDRESS="${SV_STORAGE_BIND_ADDRESS:-192.168.45.210}"
PORT="${SV_STORAGE_PORT:-9000}"
ROOT_ENV="$CONFIG_DIR/minio-root.env"
SERVICE_ENV="$CONFIG_DIR/minio-service-user.env"
PITR_ENV="$CONFIG_DIR/pitr-service-user.env"
PRODUCT_POLICY="$CONFIG_DIR/product-policy.json"
PITR_POLICY="$CONFIG_DIR/pitr-policy.json"
CERT_DIR="$CONFIG_DIR/minio-certs"

fail() {
  printf '%s\n' "$1" >&2
  exit 2
}

for file in "$ROOT_ENV" "$SERVICE_ENV" "$PITR_ENV" "$PRODUCT_POLICY" "$PITR_POLICY"; do
  [ -f "$file" ] || fail "required protected input is absent"
  [ ! -L "$file" ] || fail "protected input must not be a symlink"
done

mode() {
  stat -c '%a' "$1"
}
[ "$(mode "$ROOT_ENV")" = 600 ] || fail "root credential mode must be 0600"
[ "$(mode "$SERVICE_ENV")" = 600 ] || fail "service credential mode must be 0600"
[ "$(mode "$PITR_ENV")" = 600 ] || fail "PITR credential mode must be 0600"

mkdir -p "$DATA_DIR"
chmod 700 "$CONFIG_DIR" "$DATA_DIR"

TLS_ENABLED=false
if [ -f "$CERT_DIR/public.crt" ] || [ -f "$CERT_DIR/private.key" ] || [ -f "$CERT_DIR/ca-chain.pem" ]; then
  [ -f "$CERT_DIR/public.crt" ] && [ -f "$CERT_DIR/private.key" ] && [ -f "$CERT_DIR/ca-chain.pem" ] \
    || fail "partial TLS input is forbidden"
  [ ! -L "$CERT_DIR/public.crt" ] && [ ! -L "$CERT_DIR/private.key" ] && [ ! -L "$CERT_DIR/ca-chain.pem" ] \
    || fail "TLS input must not be a symlink"
  [ "$(mode "$CERT_DIR/private.key")" = 600 ] || fail "TLS private key mode must be 0600"
  TLS_ENABLED=true
fi

OLD_PRESERVED=false
rollback() {
  status=$?
  trap - EXIT HUP INT TERM
  if [ "$status" -ne 0 ] && [ "$OLD_PRESERVED" = true ]; then
    if docker inspect "$NAME" >/dev/null 2>&1; then
      owner="$(docker inspect --format '{{ index .Config.Labels "ai.saintvision.owner" }}' "$NAME")"
      task="$(docker inspect --format '{{ index .Config.Labels "ai.saintvision.task" }}' "$NAME")"
      if [ "$owner" = codex ] && [ "$task" = intranet-storage-card151 ]; then
        docker rm -f "$NAME" >/dev/null 2>&1 || true
      fi
    fi
    docker rename "$ROLLBACK_NAME" "$NAME" >/dev/null
    docker start "$NAME" >/dev/null
  fi
  exit "$status"
}
trap rollback EXIT HUP INT TERM

if docker inspect "$NAME" >/dev/null 2>&1; then
  owner="$(docker inspect --format '{{ index .Config.Labels "ai.saintvision.owner" }}' "$NAME")"
  task="$(docker inspect --format '{{ index .Config.Labels "ai.saintvision.task" }}' "$NAME")"
  [ "$owner" = codex ] && [ "$task" = intranet-storage-card151 ] \
    || fail "refusing to replace an unowned container"
  docker inspect "$ROLLBACK_NAME" >/dev/null 2>&1 \
    && fail "a preserved rollback container already exists"
  docker stop "$NAME" >/dev/null
  docker rename "$NAME" "$ROLLBACK_NAME" >/dev/null
  OLD_PRESERVED=true
fi

set -- docker run -d \
  --name "$NAME" \
  --label ai.saintvision.owner=codex \
  --label ai.saintvision.task=intranet-storage-card151 \
  --restart unless-stopped \
  --user "$(id -u):$(id -g)" \
  --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,nodev,size=67108864 \
  --security-opt no-new-privileges \
  --cap-drop ALL \
  -v "$ROOT_ENV:/run/secrets/root.env:ro" \
  -v "$DATA_DIR:/data" \
  -p "$BIND_ADDRESS:$PORT:9000"
if [ "$TLS_ENABLED" = true ]; then
  set -- "$@" -v "$CERT_DIR:/certs:ro"
fi
set -- "$@" --entrypoint /bin/sh "$IMAGE" -ceu \
  '. /run/secrets/root.env; export MINIO_ROOT_USER MINIO_ROOT_PASSWORD; exec /usr/bin/minio "$@"' shell \
  server /data --address :9000
[ "$TLS_ENABLED" = true ] && set -- "$@" --certs-dir /certs
"$@" >/dev/null

scheme=http
[ "$TLS_ENABLED" = true ] && scheme=https
admin_host=127.0.0.1
[ "$TLS_ENABLED" = true ] && admin_host="$BIND_ADDRESS"
. "$ROOT_ENV"
. "$SERVICE_ENV"
. "$PITR_ENV"
case "$MINIO_ROOT_USER$MINIO_ROOT_PASSWORD$SVC_KEY$SVC_SECRET$PITR_KEY$PITR_SECRET" in
  *[!A-Za-z0-9._-]*) fail "credential alphabet is not URL-safe" ;;
esac
ADMIN_ALIAS="$scheme://${MINIO_ROOT_USER}:${MINIO_ROOT_PASSWORD}@$admin_host:9000"
mc_exec_stdin() {
  if [ "$TLS_ENABLED" = true ]; then
    docker exec -i -e SSL_CERT_FILE=/certs/ca-chain.pem "$@"
  else
    docker exec -i "$@"
  fi
}
mc_ready() {
  if [ "$TLS_ENABLED" = true ]; then
    printf '%s\n' "$ADMIN_ALIAS" | timeout 3 docker exec -i \
      -e SSL_CERT_FILE=/certs/ca-chain.pem "$NAME" /bin/sh -eu -c \
      'IFS= read -r MC_HOST_local; export MC_HOST_local; [ "$(/usr/bin/mc ready local 2>/dev/null | wc -l)" -ge 1 ]'
  else
    printf '%s\n' "$ADMIN_ALIAS" | timeout 3 docker exec -i \
      "$NAME" /bin/sh -eu -c \
      'IFS= read -r MC_HOST_local; export MC_HOST_local; [ "$(/usr/bin/mc ready local 2>/dev/null | wc -l)" -ge 1 ]'
  fi
}
attempt=0
until mc_ready >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  [ "$attempt" -lt 30 ] || fail "MinIO did not become ready"
  sleep 1
done

# Root and scoped credentials stay in protected host files and travel through
# exec stdin, never host process arguments or container configuration. They are
# never printed; docker-group membership is the administrative boundary. The
# server never mounts the broader config tree.
docker exec -i "$NAME" /bin/sh -eu -c 'cat > /tmp/product-policy.json' < "$PRODUCT_POLICY"
docker exec -i "$NAME" /bin/sh -eu -c 'cat > /tmp/pitr-policy.json' < "$PITR_POLICY"
printf '%s\n' "$ADMIN_ALIAS" "$SVC_KEY" "$SVC_SECRET" "$PITR_KEY" "$PITR_SECRET" | \
  mc_exec_stdin "$NAME" /bin/sh -eu -c '
    IFS= read -r MC_HOST_local
    IFS= read -r SVC_KEY
    IFS= read -r SVC_SECRET
    IFS= read -r PITR_KEY
    IFS= read -r PITR_SECRET
    export MC_HOST_local
    /usr/bin/mc mb --ignore-existing local/saintvision-objects >/dev/null
    /usr/bin/mc mb --ignore-existing local/saintvision-pitr >/dev/null
    /usr/bin/mc version enable local/saintvision-pitr >/dev/null
    /usr/bin/mc admin policy create local saintvision-product /tmp/product-policy.json >/dev/null
    /usr/bin/mc admin policy create local saintvision-pitr /tmp/pitr-policy.json >/dev/null
    printf "%s\n%s\n" "$SVC_KEY" "$SVC_SECRET" | /usr/bin/mc admin user add local >/dev/null
    /usr/bin/mc admin policy attach local saintvision-product --user "$SVC_KEY" >/dev/null
    printf "%s\n%s\n" "$PITR_KEY" "$PITR_SECRET" | /usr/bin/mc admin user add local >/dev/null
    /usr/bin/mc admin policy attach local saintvision-pitr --user "$PITR_KEY" >/dev/null
  '
docker exec "$NAME" /bin/sh -eu -c 'rm -f /tmp/product-policy.json /tmp/pitr-policy.json'

if [ "$OLD_PRESERVED" = true ]; then
  docker rm "$ROLLBACK_NAME" >/dev/null
  OLD_PRESERVED=false
fi
trap - EXIT HUP INT TERM
printf 'minioReady=true tlsEnabled=%s bindPort=%s\n' "$TLS_ENABLED" "$PORT"
