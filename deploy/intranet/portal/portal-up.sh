#!/usr/bin/env bash
# SaintVision Intranet Portal Up Launcher (Card 156)
# Deploys the static web portal container onto node 2 with:
# - Strict owner label enforcement (ai.saintvision.service=portal)
# - No secrets in argv or environment (-e forbidden)
# - Single-file read-only bind mounts for TLS certificate and private key
# - Hardened container profile: --read-only rootfs, --cap-drop ALL, non-root user (101:101)

set -euo pipefail
umask 077

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

# Configuration
IMAGE_NAME="${PORTAL_IMAGE:-saintvision-portal:latest}"
CONTAINER_NAME="${PORTAL_CONTAINER_NAME:-saintvision-portal}"
HTTP_PORT="${PORTAL_HTTP_PORT:-80}"
HTTPS_PORT="${PORTAL_HTTPS_PORT:-443}"
CERTS_DIR="${PORTAL_CERTS_DIR:-${SCRIPT_DIR}/certs}"
CERT_FILE="${PORTAL_CERT_FILE:-${CERTS_DIR}/portal.crt}"
KEY_FILE="${PORTAL_KEY_FILE:-${CERTS_DIR}/portal.key}"

# Owner label contract: only containers matching this label may be manipulated
OWNER_LABEL_KEY="ai.saintvision.service"
OWNER_LABEL_VAL="portal"
OWNER_LABEL="${OWNER_LABEL_KEY}=${OWNER_LABEL_VAL}"

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

# 2. TLS Certificate & Key Integrity Check
if [[ ! -f "$CERT_FILE" || ! -f "$KEY_FILE" ]]; then
    echo "ERROR: TLS certificate ($CERT_FILE) or private key ($KEY_FILE) not found." >&2
    echo "Production leaf certificates for portal.sv.lan are issued by Card 150 PKI CA." >&2
    echo "To generate a local self-signed smoke test certificate, execute:" >&2
    echo "  bash ${SCRIPT_DIR}/generate-dev-certs.sh" >&2
    exit 1
fi

if [[ -L "$CERT_FILE" || -L "$KEY_FILE" ]]; then
    echo "ERROR: Certificate or key path is a symlink; regular files required." >&2
    exit 1
fi

# Verify ECDSA public key hash match between certificate and private key
cert_pubkey_hash=$(openssl x509 -in "$CERT_FILE" -pubkey -noout 2>/dev/null | sha256sum | awk '{print $1}')
key_pubkey_hash=$(openssl pkey -in "$KEY_FILE" -pubout 2>/dev/null | sha256sum | awk '{print $1}')

if [[ -z "$cert_pubkey_hash" || -z "$key_pubkey_hash" ]]; then
    echo "ERROR: Failed to extract public keys from certificate or private key." >&2
    exit 1
fi

if [[ "$cert_pubkey_hash" != "$key_pubkey_hash" ]]; then
    echo "ERROR: TLS certificate and private key public keys do not match." >&2
    exit 1
fi

# Ensure private key is not world-readable
chmod 600 "$KEY_FILE" 2>/dev/null || true
chmod 644 "$CERT_FILE" 2>/dev/null || true

# 3. Owner Label Container Replacement Guard: only touch containers with our owner label
if docker container inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
    existing_owner=$(docker inspect --format '{{index .Config.Labels "ai.saintvision.service"}}' "$CONTAINER_NAME" 2>/dev/null || true)
    if [[ "$existing_owner" != "$OWNER_LABEL_VAL" ]]; then
        echo "ERROR: Existing container '$CONTAINER_NAME' is NOT owned by '$OWNER_LABEL' (found: '$existing_owner')." >&2
        echo "Refusing to modify or delete non-owned container on this node." >&2
        exit 1
    fi
    echo "Stopping and replacing existing portal container '$CONTAINER_NAME' (owned by $OWNER_LABEL)..."
    docker stop "$CONTAINER_NAME" >/dev/null
    docker rm "$CONTAINER_NAME" >/dev/null
fi

# Clean up any stale stopped containers matching our exact owner label
stale_ids=$(docker ps -aq --filter "label=${OWNER_LABEL}" 2>/dev/null || true)
if [[ -n "$stale_ids" ]]; then
    echo "Cleaning up stale container(s) matching ${OWNER_LABEL}..."
    docker rm -f $stale_ids >/dev/null 2>&1 || true
fi

# 4. Resolve absolute paths for single-file read-only bind mounts
CERT_FILE_ABS="$(cd -- "$(dirname -- "$CERT_FILE")" && pwd)/$(basename -- "$CERT_FILE")"
KEY_FILE_ABS="$(cd -- "$(dirname -- "$KEY_FILE")" && pwd)/$(basename -- "$KEY_FILE")"

# 5. Launch Hardened Portal Container
# Security Invariants:
# - Read-only rootfs (--read-only)
# - Drop all Linux capabilities (--cap-drop ALL)
# - Prevent privilege escalation (--security-opt no-new-privileges)
# - Run as unprivileged UID:GID 101:101 (--user 101:101)
# - Tmpfs mounts for nginx temp directories and PID
# - TLS key mounted strictly as single file read-only (--mount type=bind,...,readonly)
# - Owner labels for lifecycle tracking
echo "Launching SaintVision Intranet Portal container '$CONTAINER_NAME'..."

docker run -d \
    --name "$CONTAINER_NAME" \
    --label "${OWNER_LABEL}" \
    --label "ai.saintvision.role=web-portal" \
    --label "ai.saintvision.node=node2" \
    --label "ai.saintvision.workload=intranet-portal" \
    --restart unless-stopped \
    --read-only \
    --cap-drop ALL \
    --security-opt no-new-privileges \
    --user 101:101 \
    --tmpfs /tmp:rw,noexec,nosuid,size=64m \
    --tmpfs /var/cache/nginx:rw,noexec,nosuid,size=64m \
    --tmpfs /var/run:rw,noexec,nosuid,size=16m \
    --publish "${HTTP_PORT}:80" \
    --publish "${HTTPS_PORT}:443" \
    --mount "type=bind,source=${CERT_FILE_ABS},target=/etc/nginx/certs/portal.crt,readonly" \
    --mount "type=bind,source=${KEY_FILE_ABS},target=/etc/nginx/certs/portal.key,readonly" \
    "$IMAGE_NAME"

# 6. Post-launch Verification
echo "Verifying container status..."
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

echo "✔ SaintVision Intranet Portal successfully launched and verified running."
echo "  Container: $CONTAINER_NAME"
echo "  Owner Label: $OWNER_LABEL"
echo "  HTTP Port: $HTTP_PORT -> 80 (HTTPS redirect)"
echo "  HTTPS Port: $HTTPS_PORT -> 443"
echo "  TLS Mount: read-only bind ($CERT_FILE_ABS, $KEY_FILE_ABS)"
