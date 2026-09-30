#!/usr/bin/env bash
# SaintVision Intranet Portal Local Smoke / Dev Launcher (Card 156)
# Strictly separated from production portal-up.sh:
# - Separate container name: saintvision-portal-smoke
# - Separate instance tuple label: instance=smoke
# - Dedicated dev certs directory: certs/dev/
# - Allows local self-signed certificates for smoke validation

set -euo pipefail
umask 077

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

# Configuration
IMAGE_NAME="${PORTAL_IMAGE:-saintvision-portal:latest}"
CONTAINER_NAME="saintvision-portal-smoke"
HTTP_PORT="${PORTAL_HTTP_PORT:-8080}"
HTTPS_PORT="${PORTAL_HTTPS_PORT:-8443}"
PORTAL_UID="${PORTAL_UID:-$(id -u)}"
PORTAL_GID="${PORTAL_GID:-$(id -g)}"
UPSTREAM_CP_HOST="${PORTAL_UPSTREAM_CP_HOST:-cp.sv.lan:443}"

# Smoke owner tuple
LABEL_SERVICE="ai.saintvision.service=portal"
LABEL_WORKLOAD="ai.saintvision.workload=intranet-portal"
LABEL_NODE="ai.saintvision.node=node2"
LABEL_INSTANCE="ai.saintvision.instance=smoke"

DEV_CERTS_DIR="${SCRIPT_DIR}/certs/dev"
CERT_FILE="${DEV_CERTS_DIR}/portal.crt"
KEY_FILE="${DEV_CERTS_DIR}/portal.key"

# Generate dev certificates if not present
if [[ ! -f "$CERT_FILE" || ! -f "$KEY_FILE" ]]; then
    echo "Generating temporary smoke certificates in $DEV_CERTS_DIR..."
    bash "${SCRIPT_DIR}/generate-dev-certs.sh" "$DEV_CERTS_DIR"
fi

# Upstream mock configuration
UPSTREAM_CONF_DIR="/tmp/saintvision-portal-smoke-upstream"
mkdir -p "$UPSTREAM_CONF_DIR"
cat > "${UPSTREAM_CONF_DIR}/upstream.conf" <<EOF
upstream control_plane {
    server ${UPSTREAM_CP_HOST};
    keepalive 32;
}
EOF
chmod 644 "${UPSTREAM_CONF_DIR}/upstream.conf"

# Remove existing smoke container if present (verifies full 4-tuple, R3-M3)
if docker container inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
    existing_service=$(docker inspect --format '{{index .Config.Labels "ai.saintvision.service"}}' "$CONTAINER_NAME" 2>/dev/null || true)
    existing_workload=$(docker inspect --format '{{index .Config.Labels "ai.saintvision.workload"}}' "$CONTAINER_NAME" 2>/dev/null || true)
    existing_node=$(docker inspect --format '{{index .Config.Labels "ai.saintvision.node"}}' "$CONTAINER_NAME" 2>/dev/null || true)
    existing_instance=$(docker inspect --format '{{index .Config.Labels "ai.saintvision.instance"}}' "$CONTAINER_NAME" 2>/dev/null || true)

    if [[ "$existing_service" != "portal" || "$existing_workload" != "intranet-portal" || "$existing_node" != "node2" || "$existing_instance" != "smoke" ]]; then
        echo "ERROR: Container '$CONTAINER_NAME' does NOT match smoke owner 4-tuple (service='$existing_service', workload='$existing_workload', node='$existing_node', instance='$existing_instance')." >&2
        echo "Refusing to stop or remove non-matching container." >&2
        exit 1
    fi
    echo "Stopping existing smoke container..."
    docker stop "$CONTAINER_NAME" >/dev/null
    docker rm "$CONTAINER_NAME" >/dev/null
fi

CERT_FILE_ABS="$(cd -- "$(dirname -- "$CERT_FILE")" && pwd)/$(basename -- "$CERT_FILE")"
KEY_FILE_ABS="$(cd -- "$(dirname -- "$KEY_FILE")" && pwd)/$(basename -- "$KEY_FILE")"
UPSTREAM_CONF_ABS="$(cd -- "$(dirname -- "${UPSTREAM_CONF_DIR}/upstream.conf")" && pwd)/upstream.conf"

echo "Launching smoke container '$CONTAINER_NAME' on ports ${HTTP_PORT}/${HTTPS_PORT}..."

docker run -d \
    --name "$CONTAINER_NAME" \
    --label "${LABEL_SERVICE}" \
    --label "${LABEL_WORKLOAD}" \
    --label "${LABEL_NODE}" \
    --label "${LABEL_INSTANCE}" \
    --label "ai.saintvision.role=web-portal" \
    --restart "no" \
    --read-only \
    --cap-drop ALL \
    --security-opt no-new-privileges \
    --user "${PORTAL_UID}:${PORTAL_GID}" \
    --tmpfs /tmp:rw,noexec,nosuid,size=64m \
    --tmpfs /var/cache/nginx:rw,noexec,nosuid,size=64m \
    --tmpfs /var/run:rw,noexec,nosuid,size=16m \
    --publish "${HTTP_PORT}:80" \
    --publish "${HTTPS_PORT}:443" \
    --mount "type=bind,source=${CERT_FILE_ABS},target=/etc/nginx/certs/portal.crt,readonly" \
    --mount "type=bind,source=${KEY_FILE_ABS},target=/etc/nginx/certs/portal.key,readonly" \
    --mount "type=bind,source=${CERT_FILE_ABS},target=/etc/nginx/certs/ca-bundle.crt,readonly" \
    --mount "type=bind,source=${UPSTREAM_CONF_ABS},target=/etc/nginx/conf.d/upstream.conf,readonly" \
    "$IMAGE_NAME"

echo "✔ Smoke container launched successfully for local testing."
