#!/usr/bin/env bash
# SaintVision Intranet Portal Up Launcher (Card 156)
# Hardened, non-root Nginx container launcher for node2 (object store node)
# Production deployment requires CA-signed leaf certificates and explicit Control Plane upstream.
# Safe preflight container replacement pattern: validates staging container before touching existing service.

set -euo pipefail
umask 077

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

# Configuration
IMAGE_NAME="${PORTAL_IMAGE:-saintvision-portal:latest}"
CONTAINER_NAME="${PORTAL_CONTAINER_NAME:-saintvision-portal}"
HTTP_PORT="${PORTAL_HTTP_PORT:-80}"
HTTPS_PORT="${PORTAL_HTTPS_PORT:-443}"
PORTAL_UID="${PORTAL_UID:-101}"
PORTAL_GID="${PORTAL_GID:-101}"

# Owner label 4-tuple for strict lifecycle isolation
LABEL_SERVICE="ai.saintvision.service=portal"
LABEL_WORKLOAD="ai.saintvision.workload=intranet-portal"
LABEL_NODE="ai.saintvision.node=node2"
PORTAL_INSTANCE="${PORTAL_INSTANCE:-main}"
LABEL_INSTANCE="ai.saintvision.instance=${PORTAL_INSTANCE}"

CERTS_DIR="${PORTAL_CERTS_DIR:-${SCRIPT_DIR}/certs}"
# Card 150 PKI outputs: server-chain.pem (0600, leaf+intermediate) and server-key.pem (0400)
# Fall back to server-cert.pem or portal.crt/key if present
if [[ -n "${PORTAL_CERT_FILE:-}" ]]; then
    CERT_FILE="$PORTAL_CERT_FILE"
elif [[ -f "${CERTS_DIR}/server-chain.pem" ]]; then
    CERT_FILE="${CERTS_DIR}/server-chain.pem"
elif [[ -f "${CERTS_DIR}/server-cert.pem" ]]; then
    CERT_FILE="${CERTS_DIR}/server-cert.pem"
elif [[ -f "${CERTS_DIR}/portal.crt" ]]; then
    CERT_FILE="${CERTS_DIR}/portal.crt"
else
    CERT_FILE="${CERTS_DIR}/server-chain.pem"
fi

if [[ -n "${PORTAL_KEY_FILE:-}" ]]; then
    KEY_FILE="$PORTAL_KEY_FILE"
elif [[ -f "${CERTS_DIR}/server-key.pem" ]]; then
    KEY_FILE="${CERTS_DIR}/server-key.pem"
elif [[ -f "${CERTS_DIR}/portal.key" ]]; then
    KEY_FILE="${CERTS_DIR}/portal.key"
else
    KEY_FILE="${CERTS_DIR}/server-key.pem"
fi

if [[ -n "${PORTAL_CA_BUNDLE:-}" ]]; then
    CA_BUNDLE_FILE="$PORTAL_CA_BUNDLE"
elif [[ -f "${CERTS_DIR}/ca-bundle.crt" ]]; then
    CA_BUNDLE_FILE="${CERTS_DIR}/ca-bundle.crt"
elif [[ -f "${CERTS_DIR}/ca.pem" ]]; then
    CA_BUNDLE_FILE="${CERTS_DIR}/ca.pem"
elif [[ -f "${CERTS_DIR}/trust-chain.pem" ]]; then
    CA_BUNDLE_FILE="${CERTS_DIR}/trust-chain.pem"
else
    CA_BUNDLE_FILE="${CERTS_DIR}/ca-bundle.crt"
fi

# 1. Secret Prohibition Guard: secrets in argv or -e flags are strictly forbidden
for arg in "${@:-}"; do
    case "$arg" in
        *password*|*secret*|*private_key*|*-e*|*--env*)
            echo "ERROR: Passing secrets or injecting environment variables (-e/--env) via argv is strictly forbidden." >&2
            echo "Nginx runtime configuration is static and TLS keys must be mounted as read-only files." >&2
            exit 1
            ;;
    esac
done

# 2. Upstream Control Plane Requirement (Fail-closed)
# The portal acts as same-origin reverse proxy for /v1/ API, SSE, and Terminal WebSocket.
UPSTREAM_CP_HOST="${PORTAL_UPSTREAM_CP_HOST:-}"
if [[ -z "$UPSTREAM_CP_HOST" ]]; then
    echo "ERROR: PORTAL_UPSTREAM_CP_HOST is not set. Upstream Control Plane host (e.g. cp.sv.lan:443) must be configured." >&2
    echo "Startup aborted (fail-closed)." >&2
    exit 1
fi

UPSTREAM_CONF_DIR="${PORTAL_UPSTREAM_DIR:-/tmp/saintvision-portal-upstream-${PORTAL_INSTANCE}}"
mkdir -p "$UPSTREAM_CONF_DIR"
cat > "${UPSTREAM_CONF_DIR}/upstream.conf" <<EOF
upstream control_plane {
    server ${UPSTREAM_CP_HOST};
    keepalive 32;
}
EOF
chmod 644 "${UPSTREAM_CONF_DIR}/upstream.conf"

# 3. Production Leaf Certificate & CA Integrity Verification
if [[ ! -f "$CERT_FILE" || ! -f "$KEY_FILE" ]]; then
    echo "ERROR: TLS certificate ($CERT_FILE) or private key ($KEY_FILE) not found." >&2
    echo "Production leaf certificates for portal.sv.lan are issued by Card 150 PKI CA." >&2
    echo "For dev/smoke testing, use portal-smoke-up.sh instead." >&2
    exit 1
fi

if [[ ! -f "$CA_BUNDLE_FILE" ]]; then
    echo "ERROR: CA bundle ($CA_BUNDLE_FILE) not found. Required for leaf verification." >&2
    exit 1
fi

# Check that certificate is not self-signed
cert_subject=$(openssl x509 -in "$CERT_FILE" -noout -subject 2>/dev/null || true)
cert_issuer=$(openssl x509 -in "$CERT_FILE" -noout -issuer 2>/dev/null || true)
if [[ "$cert_subject" == "$cert_issuer" ]]; then
    echo "ERROR: Self-signed certificate rejected in production portal-up.sh." >&2
    echo "Production deployment requires CA-signed leaf. Use portal-smoke-up.sh for dev smoke." >&2
    exit 1
fi

# Verify leaf chain against CA bundle
if ! openssl verify -CAfile "$CA_BUNDLE_FILE" -untrusted "$CERT_FILE" "$CERT_FILE" >/dev/null 2>&1 && \
   ! openssl verify -CAfile "$CA_BUNDLE_FILE" "$CERT_FILE" >/dev/null 2>&1; then
    echo "ERROR: Certificate chain verification failed against CA bundle $CA_BUNDLE_FILE." >&2
    exit 1
fi

# Verify SAN contains portal.sv.lan
if ! openssl x509 -in "$CERT_FILE" -noout -text 2>/dev/null | grep -E "DNS:portal\.sv\.lan(\s|,|$)" >/dev/null; then
    echo "ERROR: Certificate SAN does not contain DNS:portal.sv.lan." >&2
    exit 1
fi

# Verify Extended Key Usage includes serverAuth
if ! openssl x509 -in "$CERT_FILE" -noout -text 2>/dev/null | grep -E "TLS Web Server Authentication|serverAuth" >/dev/null; then
    echo "ERROR: Certificate EKU must include TLS Web Server Authentication (serverAuth)." >&2
    exit 1
fi

# Verify Basic Constraints CA is FALSE
if openssl x509 -in "$CERT_FILE" -noout -text 2>/dev/null | grep -E "CA:TRUE" >/dev/null; then
    echo "ERROR: Certificate Basic Constraints has CA:TRUE. Leaf certificate must have CA:FALSE." >&2
    exit 1
fi

# Verify certificate validity period (not expired, valid within next 24h)
if ! openssl x509 -in "$CERT_FILE" -noout -checkend 86400 >/dev/null 2>&1; then
    echo "ERROR: Certificate is expired or will expire within 24 hours." >&2
    exit 1
fi

# Note: Operator permissions (0400 for key, 0600 for chain) are strictly preserved.
# No chmod is performed on operator files. Non-root container access is achieved via --user.

# Verify key matches certificate public key
cert_pubkey_hash=$(openssl x509 -in "$CERT_FILE" -noout -pubkey 2>/dev/null | openssl sha256)
key_pubkey_hash=$(openssl pkey -in "$KEY_FILE" -pubout 2>/dev/null | openssl sha256)
if [[ "$cert_pubkey_hash" != "$key_pubkey_hash" ]]; then
    echo "ERROR: TLS private key ($KEY_FILE) does NOT match certificate public key ($CERT_FILE)." >&2
    exit 1
fi

# 4. Image Verification
echo "Inspecting target image $IMAGE_NAME..."
if ! docker image inspect "$IMAGE_NAME" >/dev/null 2>&1; then
    echo "ERROR: Target image $IMAGE_NAME not found locally. Image must be loaded or pulled." >&2
    exit 1
fi

# Verify image digest if specified
if [[ -n "${PORTAL_IMAGE_DIGEST:-}" ]]; then
    actual_repo_digests=$(docker inspect --format '{{json .RepoDigests}}' "$IMAGE_NAME" 2>/dev/null || true)
    if [[ "$actual_repo_digests" != *"${PORTAL_IMAGE_DIGEST}"* ]]; then
        echo "ERROR: Image digest mismatch. Expected $PORTAL_IMAGE_DIGEST, got $actual_repo_digests." >&2
        exit 1
    fi
fi

CERT_FILE_ABS="$(cd -- "$(dirname -- "$CERT_FILE")" && pwd)/$(basename -- "$CERT_FILE")"
KEY_FILE_ABS="$(cd -- "$(dirname -- "$KEY_FILE")" && pwd)/$(basename -- "$KEY_FILE")"
CA_BUNDLE_ABS="$(cd -- "$(dirname -- "$CA_BUNDLE_FILE")" && pwd)/$(basename -- "$CA_BUNDLE_FILE")"
UPSTREAM_CONF_ABS="$(cd -- "$(dirname -- "${UPSTREAM_CONF_DIR}/upstream.conf")" && pwd)/upstream.conf"

# 5. Safe Preflight Container Verification (Staging Canary Test)
# Before touching or stopping any existing production container, launch a temporary staging container
# with identical mounts and security configuration to verify nginx -t and HTTPS health.
STAGING_NAME="${CONTAINER_NAME}-staging-$$"
echo "Launching staging preflight container '$STAGING_NAME' for configuration & HTTPS healthcheck..."

docker run -d \
    --name "$STAGING_NAME" \
    --label "${LABEL_SERVICE}" \
    --label "${LABEL_WORKLOAD}" \
    --label "${LABEL_NODE}" \
    --label "ai.saintvision.instance=preflight" \
    --read-only \
    --cap-drop ALL \
    --security-opt no-new-privileges \
    --user "${PORTAL_UID}:${PORTAL_GID}" \
    --tmpfs /tmp:rw,noexec,nosuid,size=64m \
    --tmpfs /var/cache/nginx:rw,noexec,nosuid,size=64m \
    --tmpfs /var/run:rw,noexec,nosuid,size=16m \
    --mount "type=bind,source=${CERT_FILE_ABS},target=/etc/nginx/certs/portal.crt,readonly" \
    --mount "type=bind,source=${KEY_FILE_ABS},target=/etc/nginx/certs/portal.key,readonly" \
    --mount "type=bind,source=${CA_BUNDLE_ABS},target=/etc/nginx/certs/ca-bundle.crt,readonly" \
    --mount "type=bind,source=${UPSTREAM_CONF_ABS},target=/etc/nginx/conf.d/upstream.conf,readonly" \
    "$IMAGE_NAME"

staging_cleanup() {
    docker stop "$STAGING_NAME" >/dev/null 2>&1 || true
    docker rm -f "$STAGING_NAME" >/dev/null 2>&1 || true
}

# Preflight test 1: nginx -t inside staging container
echo "Running preflight 'nginx -t' in staging container..."
if ! docker exec "$STAGING_NAME" nginx -t >/dev/null 2>&1; then
    echo "ERROR: Preflight 'nginx -t' failed in staging container. Existing container preserved; aborting." >&2
    staging_cleanup
    exit 1
fi
echo "✔ Preflight 'nginx -t' passed."

# Preflight test 2: Wait for staging container running status
staging_running="false"
for i in {1..10}; do
    if [[ "$(docker inspect --format '{{.State.Running}}' "$STAGING_NAME" 2>/dev/null || true)" == "true" ]]; then
        staging_running="true"
        break
    fi
    sleep 1
done
if [[ "$staging_running" != "true" ]]; then
    echo "ERROR: Staging preflight container failed to enter running state. Existing container preserved; aborting." >&2
    docker logs "$STAGING_NAME" 2>&1 || true
    staging_cleanup
    exit 1
fi

# Preflight test 3: HTTPS internal healthcheck via wget in staging container
echo "Running preflight HTTPS health check in staging container..."
if ! docker exec "$STAGING_NAME" wget -qO- --spider --no-check-certificate https://127.0.0.1/healthz >/dev/null 2>&1 && \
   ! docker exec "$STAGING_NAME" wget -qO- --spider http://127.0.0.1/healthz >/dev/null 2>&1; then
    echo "ERROR: Staging preflight HTTPS healthcheck failed. Existing container preserved; aborting." >&2
    docker logs "$STAGING_NAME" 2>&1 || true
    staging_cleanup
    exit 1
fi
echo "✔ Preflight staging health check passed."
staging_cleanup

# 6. Owner Label 4-Tuple Verification and Safe Container Replacement
if docker container inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
    existing_service=$(docker inspect --format '{{index .Config.Labels "ai.saintvision.service"}}' "$CONTAINER_NAME" 2>/dev/null || true)
    existing_workload=$(docker inspect --format '{{index .Config.Labels "ai.saintvision.workload"}}' "$CONTAINER_NAME" 2>/dev/null || true)
    existing_node=$(docker inspect --format '{{index .Config.Labels "ai.saintvision.node"}}' "$CONTAINER_NAME" 2>/dev/null || true)
    existing_instance=$(docker inspect --format '{{index .Config.Labels "ai.saintvision.instance"}}' "$CONTAINER_NAME" 2>/dev/null || true)

    if [[ "$existing_service" != "portal" || "$existing_workload" != "intranet-portal" || "$existing_node" != "node2" || "$existing_instance" != "$PORTAL_INSTANCE" ]]; then
        echo "ERROR: Container '$CONTAINER_NAME' does NOT match owner tuple (found: service='$existing_service', workload='$existing_workload', node='$existing_node', instance='$existing_instance')." >&2
        echo "Refusing to touch non-matching container on node 2." >&2
        exit 1
    fi

    echo "Stopping and replacing existing owned portal container '$CONTAINER_NAME'..."
    docker stop "$CONTAINER_NAME" >/dev/null
    docker rm "$CONTAINER_NAME" >/dev/null
fi

# Clean up only stopped/exited containers matching the exact 4-tuple
stale_ids=$(docker ps -aq \
    --filter "status=exited" \
    --filter "label=${LABEL_SERVICE}" \
    --filter "label=${LABEL_WORKLOAD}" \
    --filter "label=${LABEL_NODE}" \
    --filter "label=${LABEL_INSTANCE}" 2>/dev/null || true)
if [[ -n "$stale_ids" ]]; then
    echo "Cleaning up exited stale container(s) matching exact tuple..."
    docker rm $stale_ids >/dev/null 2>&1 || true
fi

# 7. Launch Hardened Production Portal Container
echo "Launching SaintVision Intranet Portal container '$CONTAINER_NAME'..."

docker run -d \
    --name "$CONTAINER_NAME" \
    --label "${LABEL_SERVICE}" \
    --label "${LABEL_WORKLOAD}" \
    --label "${LABEL_NODE}" \
    --label "${LABEL_INSTANCE}" \
    --label "ai.saintvision.role=web-portal" \
    --restart unless-stopped \
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
    --mount "type=bind,source=${CA_BUNDLE_ABS},target=/etc/nginx/certs/ca-bundle.crt,readonly" \
    --mount "type=bind,source=${UPSTREAM_CONF_ABS},target=/etc/nginx/conf.d/upstream.conf,readonly" \
    "$IMAGE_NAME"

# 8. Post-launch Health and Stability Verification
echo "Verifying container status and stability..."
RUNNING="false"
for i in {1..15}; do
    if [[ "$(docker inspect --format '{{.State.Running}}' "$CONTAINER_NAME" 2>/dev/null || true)" == "true" ]]; then
        RUNNING="true"
        break
    fi
    sleep 1
done

if [[ "$RUNNING" != "true" ]]; then
    echo "ERROR: Portal container '$CONTAINER_NAME' failed to enter running state." >&2
    docker logs "$CONTAINER_NAME" 2>&1 || true
    exit 1
fi

# Verify no crash looping (restart count == 0)
restart_count=$(docker inspect --format '{{.RestartCount}}' "$CONTAINER_NAME" 2>/dev/null || echo "0")
if [[ "$restart_count" -ne 0 ]]; then
    echo "ERROR: Portal container has restarted $restart_count times (crash loop detected)." >&2
    docker logs "$CONTAINER_NAME" 2>&1 || true
    exit 1
fi

echo "✔ SaintVision Intranet Portal successfully launched and verified running."
echo "  Container: $CONTAINER_NAME"
echo "  Tuple:     service=portal, workload=intranet-portal, node=node2, instance=${PORTAL_INSTANCE}"
echo "  HTTP Port: $HTTP_PORT -> 80 (HTTPS redirect)"
echo "  HTTPS:     $HTTPS_PORT -> 443"
echo "  Upstream:  ${UPSTREAM_CP_HOST}"
echo "  RestartCount: $restart_count (clean start)"
