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

# Coordinator Decision B2/Codex3: Method B unification
# Container runs as the SSH subject's host UID:GID matching the owner of server-key.pem (0400)
PORTAL_UID="${PORTAL_UID:-$(id -u)}"
PORTAL_GID="${PORTAL_GID:-$(id -g)}"

# Owner label 4-tuple for strict lifecycle isolation
LABEL_SERVICE="ai.saintvision.service=portal"
LABEL_WORKLOAD="ai.saintvision.workload=intranet-portal"
LABEL_NODE="ai.saintvision.node=node2"
PORTAL_INSTANCE="${PORTAL_INSTANCE:-main}"
LABEL_INSTANCE="ai.saintvision.instance=${PORTAL_INSTANCE}"

CERTS_DIR="${PORTAL_CERTS_DIR:-${SCRIPT_DIR}/certs}"
# Card 150 PKI outputs: server-chain.pem (0600, leaf+intermediate) and server-key.pem (0400)
# Fallback to portal.crt/key removed from production script (L3)
CERT_FILE="${PORTAL_CERT_FILE:-${CERTS_DIR}/server-chain.pem}"
KEY_FILE="${PORTAL_KEY_FILE:-${CERTS_DIR}/server-key.pem}"

if [[ -n "${PORTAL_CA_BUNDLE:-}" ]]; then
    CA_BUNDLE_FILE="$PORTAL_CA_BUNDLE"
elif [[ -f "${CERTS_DIR}/ca-bundle.crt" ]]; then
    CA_BUNDLE_FILE="${CERTS_DIR}/ca-bundle.crt"
elif [[ -f "${CERTS_DIR}/trust-chain.pem" ]]; then
    CA_BUNDLE_FILE="${CERTS_DIR}/trust-chain.pem"
elif [[ -f "${CERTS_DIR}/ca.pem" ]]; then
    CA_BUNDLE_FILE="${CERTS_DIR}/ca.pem"
else
    CA_BUNDLE_FILE="${CERTS_DIR}/ca-bundle.crt"
fi

# 1. Secret Prohibition Guard: secrets in argv or -e/--env flags are strictly forbidden
for arg in "${@:-}"; do
    case "$arg" in
        *password*|*secret*|*private_key*|*-e*|*--env*|*--env-file*)
            echo "ERROR: Passing secrets or injecting environment variables (-e/--env/--env-file) via argv is strictly forbidden." >&2
            echo "Nginx runtime configuration is static and TLS keys must be mounted as read-only files." >&2
            exit 1
            ;;
    esac
done

# 2. Upstream Control Plane Requirement (Fail-closed & Strict Validation, M2)
# The portal acts as same-origin reverse proxy for /v1/ API, SSE, and Terminal WebSocket.
UPSTREAM_CP_HOST="${PORTAL_UPSTREAM_CP_HOST:-}"
if [[ "$UPSTREAM_CP_HOST" != "cp.sv.lan:443" ]]; then
    echo "ERROR: PORTAL_UPSTREAM_CP_HOST must be exactly 'cp.sv.lan:443' (found: '$UPSTREAM_CP_HOST')." >&2
    echo "Configuration injection prevented. Startup aborted (fail-closed)." >&2
    exit 1
fi

# Persistent private 0700 state directory (protects against /tmp prediction and reboot pruning, M2)
STATE_DIR="${PORTAL_STATE_DIR:-${HOME}/.local/state/saintvision-portal/${PORTAL_INSTANCE}}"
if [[ -L "$STATE_DIR" ]]; then
    echo "ERROR: State directory $STATE_DIR is a symbolic link. Aborting for security." >&2
    exit 1
fi
mkdir -p "$STATE_DIR"
chmod 0700 "$STATE_DIR"

temp_conf=$(mktemp "${STATE_DIR}/upstream.conf.tmp.XXXXXX")
cat > "$temp_conf" <<EOF
upstream control_plane {
    server ${UPSTREAM_CP_HOST};
    keepalive 32;
}
EOF
chmod 0644 "$temp_conf"
mv -f "$temp_conf" "${STATE_DIR}/upstream.conf"
UPSTREAM_CONF_ABS="${STATE_DIR}/upstream.conf"

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

# Check that certificate is not self-signed via DN normalization (RFC2253 without prefix, H1)
subj_dn=$(openssl x509 -in "$CERT_FILE" -noout -subject -nameopt RFC2253 2>/dev/null | sed -e 's/^subject= *//')
issuer_dn=$(openssl x509 -in "$CERT_FILE" -noout -issuer -nameopt RFC2253 2>/dev/null | sed -e 's/^issuer= *//')
if [[ -n "$subj_dn" && "$subj_dn" == "$issuer_dn" ]]; then
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

# Verify Basic Constraints: MUST explicitly contain CA:FALSE and MUST NOT contain CA:TRUE (H1)
if ! openssl x509 -in "$CERT_FILE" -noout -text 2>/dev/null | grep -q "CA:FALSE"; then
    echo "ERROR: Certificate Basic Constraints must explicitly contain CA:FALSE." >&2
    exit 1
fi
if openssl x509 -in "$CERT_FILE" -noout -text 2>/dev/null | grep -q "CA:TRUE"; then
    echo "ERROR: Certificate Basic Constraints has CA:TRUE. Leaf certificate must have CA:FALSE." >&2
    exit 1
fi

# Verify certificate validity period (not expired, valid within next 24h)
if ! openssl x509 -in "$CERT_FILE" -noout -checkend 86400 >/dev/null 2>&1; then
    echo "ERROR: Certificate is expired or will expire within 24 hours." >&2
    exit 1
fi

# Verify root CA fingerprint allowlist if configured (H1)
if [[ -n "${PORTAL_ALLOWED_ROOT_FINGERPRINTS:-}" ]]; then
    ca_matched="false"
    ca_fp=$(openssl x509 -in "$CA_BUNDLE_FILE" -noout -fingerprint -sha256 2>/dev/null | sed -e 's/.*=//' -e 's/://g' || true)
    for allowed in ${PORTAL_ALLOWED_ROOT_FINGERPRINTS}; do
        norm_allowed=$(echo "$allowed" | sed -e 's/://g')
        if [[ "${ca_fp,,}" == "${norm_allowed,,}" ]]; then
            ca_matched="true"
            break
        fi
    done
    if [[ "$ca_matched" != "true" ]]; then
        echo "ERROR: CA bundle root fingerprint does not match allowlist." >&2
        exit 1
    fi
fi

# Operator permissions (0400 for key, 0600 for chain) are strictly preserved.
# No chmod is performed on operator files. Non-root container access is achieved via --user "${PORTAL_UID}:${PORTAL_GID}".

# Verify key matches certificate public key
cert_pubkey_hash=$(openssl x509 -in "$CERT_FILE" -noout -pubkey 2>/dev/null | openssl sha256)
key_pubkey_hash=$(openssl pkey -in "$KEY_FILE" -pubout 2>/dev/null | openssl sha256)
if [[ "$cert_pubkey_hash" != "$key_pubkey_hash" ]]; then
    echo "ERROR: TLS private key ($KEY_FILE) does NOT match certificate public key ($CERT_FILE)." >&2
    exit 1
fi

# 4. Image Verification & Exact Digest Resolution (M3)
echo "Inspecting target image $IMAGE_NAME..."
if ! docker image inspect "$IMAGE_NAME" >/dev/null 2>&1; then
    echo "ERROR: Target image $IMAGE_NAME not found locally. Image must be loaded or pulled." >&2
    exit 1
fi

RESOLVED_IMAGE_ID=$(docker image inspect --format '{{.Id}}' "$IMAGE_NAME" 2>/dev/null || true)
if [[ ! "$RESOLVED_IMAGE_ID" =~ ^sha256:[0-9a-f]{64}$ ]]; then
    echo "ERROR: Failed to resolve valid 64-hex sha256 image ID for $IMAGE_NAME (got: '$RESOLVED_IMAGE_ID')." >&2
    exit 1
fi

# Verify image digest exact equality if specified (M3)
if [[ -n "${PORTAL_IMAGE_DIGEST:-}" ]]; then
    if [[ "$RESOLVED_IMAGE_ID" != "$PORTAL_IMAGE_DIGEST" ]]; then
        echo "ERROR: Image ID mismatch. Expected $PORTAL_IMAGE_DIGEST, got $RESOLVED_IMAGE_ID." >&2
        exit 1
    fi
fi

# Execute container strictly by resolved immutable sha256 image ID (prevents tag TOCTOU, M3)
TARGET_IMAGE="$RESOLVED_IMAGE_ID"

CERT_FILE_ABS="$(cd -- "$(dirname -- "$CERT_FILE")" && pwd)/$(basename -- "$CERT_FILE")"
KEY_FILE_ABS="$(cd -- "$(dirname -- "$KEY_FILE")" && pwd)/$(basename -- "$KEY_FILE")"
CA_BUNDLE_ABS="$(cd -- "$(dirname -- "$CA_BUNDLE_FILE")" && pwd)/$(basename -- "$CA_BUNDLE_FILE")"

# 5. Safe Preflight Container Verification (Staging Canary Test, M3 & M4)
# Before touching or stopping any existing production container, launch a temporary staging container
# with identical mounts and security configuration to verify nginx -t and HTTPS health.
STAGING_NAME="${CONTAINER_NAME}-staging-$$"
echo "Launching staging preflight container '$STAGING_NAME' ($TARGET_IMAGE)..."

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
    "$TARGET_IMAGE"

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

# Preflight test 3: HTTPS internal health and static asset probes (no HTTP fallback, M4)
echo "Running preflight HTTPS health check in staging container..."
if ! docker exec "$STAGING_NAME" wget -qO- --spider --no-check-certificate https://127.0.0.1/healthz >/dev/null 2>&1; then
    echo "ERROR: Staging preflight HTTPS /healthz failed. Existing container preserved; aborting." >&2
    docker logs "$STAGING_NAME" 2>&1 || true
    staging_cleanup
    exit 1
fi

echo "Verifying static assets in staging container..."
if ! docker exec "$STAGING_NAME" wget -qO- --spider --no-check-certificate https://127.0.0.1/index.html >/dev/null 2>&1; then
    echo "ERROR: Staging preflight /index.html failed. Existing container preserved; aborting." >&2
    docker logs "$STAGING_NAME" 2>&1 || true
    staging_cleanup
    exit 1
fi

if ! docker exec "$STAGING_NAME" wget -qO- --spider --no-check-certificate https://127.0.0.1/auth-config.js >/dev/null 2>&1; then
    echo "ERROR: Staging preflight /auth-config.js failed. Existing container preserved; aborting." >&2
    docker logs "$STAGING_NAME" 2>&1 || true
    staging_cleanup
    exit 1
fi
echo "✔ Preflight staging health & static asset checks passed."
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
echo "Launching SaintVision Intranet Portal container '$CONTAINER_NAME' ($TARGET_IMAGE)..."

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
    "$TARGET_IMAGE"

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

# Post-launch stabilization check
sleep 1
restart_count_after=$(docker inspect --format '{{.RestartCount}}' "$CONTAINER_NAME" 2>/dev/null || echo "0")
if [[ "$restart_count_after" -ne 0 ]]; then
    echo "ERROR: Portal container crashed during startup stabilization ($restart_count_after restarts)." >&2
    docker logs "$CONTAINER_NAME" 2>&1 || true
    exit 1
fi

echo "✔ SaintVision Intranet Portal successfully launched and verified running."
echo "  Container:    $CONTAINER_NAME"
echo "  Image ID:     $TARGET_IMAGE"
echo "  Tuple:        service=portal, workload=intranet-portal, node=node2, instance=${PORTAL_INSTANCE}"
echo "  HTTP Port:    $HTTP_PORT -> 80 (HTTPS redirect)"
echo "  HTTPS Port:   $HTTPS_PORT -> 443"
echo "  Upstream:     ${UPSTREAM_CP_HOST}"
echo "  RestartCount: $restart_count_after (clean start)"
