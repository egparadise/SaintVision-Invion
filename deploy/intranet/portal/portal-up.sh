#!/usr/bin/env bash
# SaintVision Intranet Portal Up Launcher (Card 156)
# Hardened, non-root Nginx container launcher for node2 (object store node)
# Production deployment requires CA-signed leaf certificates and explicit Control Plane upstream.
# Safe preflight container replacement pattern: validates staging container before touching existing service.

set -euo pipefail
umask 077

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

# Default Configuration Variables
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

UPSTREAM_CP_HOST="${PORTAL_UPSTREAM_CP_HOST:-}"
STATE_DIR="${PORTAL_STATE_DIR:-${HOME}/.local/state/saintvision-portal/${PORTAL_INSTANCE}}"
STAGING_NAME=""

# -----------------------------------------------------------------------------
# Function Definitions for Modular Testing and Safe Execution (R3-H2)
# -----------------------------------------------------------------------------

validate_argv_secrets() {
    for arg in "${@:-}"; do
        case "$arg" in
            *password*|*secret*|*private_key*|*-e*|*--env*|*--env-file*)
                echo "ERROR: Passing secrets or injecting environment variables (-e/--env/--env-file) via argv is strictly forbidden." >&2
                echo "Nginx runtime configuration is static and TLS keys must be mounted as read-only files." >&2
                return 1
                ;;
        esac
    done
    return 0
}

validate_environment() {
    # 1. Reject root UID execution (R3-M2)
    if [[ "$PORTAL_UID" -eq 0 ]]; then
        echo "ERROR: PORTAL_UID cannot be 0 (root execution is strictly prohibited)." >&2
        return 1
    fi

    # 2. Strict Upstream Control Plane Host Verification (M2)
    if [[ "$UPSTREAM_CP_HOST" != "cp.sv.lan:443" ]]; then
        echo "ERROR: PORTAL_UPSTREAM_CP_HOST must be exactly 'cp.sv.lan:443' (found: '$UPSTREAM_CP_HOST')." >&2
        echo "Configuration injection prevented. Startup aborted (fail-closed)." >&2
        return 1
    fi

    # 3. Verify key file owner UID matches PORTAL_UID (R3-M2)
    if [[ -f "$KEY_FILE" ]]; then
        local key_owner
        key_owner=$(stat -c '%u' "$KEY_FILE" 2>/dev/null || stat -f '%u' "$KEY_FILE" 2>/dev/null || true)
        if [[ -n "$key_owner" && "$key_owner" -ne "$PORTAL_UID" ]]; then
            echo "ERROR: Private key $KEY_FILE owner UID ($key_owner) does not match PORTAL_UID ($PORTAL_UID)." >&2
            return 1
        fi
    fi

    # 4. State directory validation
    if [[ -L "$STATE_DIR" ]]; then
        echo "ERROR: State directory $STATE_DIR is a symbolic link. Aborting for security." >&2
        return 1
    fi
    mkdir -p "$STATE_DIR"
    chmod 0700 "$STATE_DIR"

    return 0
}

prepare_upstream_config() {
    local temp_conf
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
}

validate_ca_bundle_and_allowlist() {
    if [[ ! -f "$CA_BUNDLE_FILE" ]]; then
        echo "ERROR: CA bundle ($CA_BUNDLE_FILE) not found. Required for leaf verification." >&2
        return 1
    fi

    # Mandatory Root CA Fingerprint Allowlist (R3-H1)
    if [[ -z "${PORTAL_ALLOWED_ROOT_FINGERPRINTS:-}" ]]; then
        echo "ERROR: PORTAL_ALLOWED_ROOT_FINGERPRINTS is mandatory in production (fail-closed)." >&2
        return 1
    fi

    # Split CA bundle to examine every trust anchor individually (R3-H1)
    local split_dir
    split_dir=$(mktemp -d "${STATE_DIR}/ca-split.XXXXXX")
    awk -v out_dir="$split_dir" '
        /-----BEGIN CERTIFICATE-----/ { idx++; out = sprintf("%s/cert-%03d.crt", out_dir, idx) }
        out { print > out }
        /-----END CERTIFICATE-----/ { close(out); out="" }
    ' "$CA_BUNDLE_FILE"

    local root_certs=()
    local intermediate_certs=()

    for c in "$split_dir"/cert-*.crt; do
        [[ -f "$c" ]] || continue
        local c_subj c_issuer
        c_subj=$(openssl x509 -in "$c" -noout -subject -nameopt RFC2253 2>/dev/null | sed -e 's/^subject= *//')
        c_issuer=$(openssl x509 -in "$c" -noout -issuer -nameopt RFC2253 2>/dev/null | sed -e 's/^issuer= *//')
        if [[ -n "$c_subj" && "$c_subj" == "$c_issuer" ]]; then
            root_certs+=("$c")
        else
            intermediate_certs+=("$c")
        fi
    done

    # Reject if no root CA or multiple root CAs present (R3-H1)
    if [[ "${#root_certs[@]}" -eq 0 ]]; then
        echo "ERROR: No root CA (self-signed trust anchor) found in CA bundle $CA_BUNDLE_FILE." >&2
        rm -rf "$split_dir"
        return 1
    fi
    if [[ "${#root_certs[@]}" -gt 1 ]]; then
        echo "ERROR: Multiple root CAs (${#root_certs[@]}) found in CA bundle $CA_BUNDLE_FILE. Untrusted extra trust anchor rejected." >&2
        rm -rf "$split_dir"
        return 1
    fi

    # Verify single root CA fingerprint matches approved allowlist
    local root_cert="${root_certs[0]}"
    local root_fp
    root_fp=$(openssl x509 -in "$root_cert" -noout -fingerprint -sha256 2>/dev/null | sed -e 's/.*=//' -e 's/://g' -e 's/ //g' | tr '[:upper:]' '[:lower:]')

    local ca_matched="false"
    for allowed in ${PORTAL_ALLOWED_ROOT_FINGERPRINTS//,/ }; do
        local norm_allowed
        norm_allowed=$(echo "$allowed" | sed -e 's/://g' -e 's/ //g' | tr '[:upper:]' '[:lower:]')
        if [[ "$root_fp" == "$norm_allowed" ]]; then
            ca_matched="true"
            break
        fi
    done

    if [[ "$ca_matched" != "true" ]]; then
        echo "ERROR: CA bundle root fingerprint ($root_fp) does NOT match approved allowlist." >&2
        rm -rf "$split_dir"
        return 1
    fi

    # Verify each intermediate in bundle is signed by the verified root CA (R3-H1)
    for inter in "${intermediate_certs[@]}"; do
        if ! openssl verify -CAfile "$root_cert" "$inter" >/dev/null 2>&1; then
            echo "ERROR: Intermediate CA ($inter) in bundle not signed by approved root CA." >&2
            rm -rf "$split_dir"
            return 1
        fi
    done

    rm -rf "$split_dir"
    return 0
}

validate_leaf_certificate() {
    if [[ ! -f "$CERT_FILE" || ! -f "$KEY_FILE" ]]; then
        echo "ERROR: TLS certificate ($CERT_FILE) or private key ($KEY_FILE) not found." >&2
        return 1
    fi

    # Reject self-signed leaf certificates in production via DN normalization (RFC2253 without prefix, H1)
    local subj_dn issuer_dn
    subj_dn=$(openssl x509 -in "$CERT_FILE" -noout -subject -nameopt RFC2253 2>/dev/null | sed -e 's/^subject= *//')
    issuer_dn=$(openssl x509 -in "$CERT_FILE" -noout -issuer -nameopt RFC2253 2>/dev/null | sed -e 's/^issuer= *//')
    if [[ -n "$subj_dn" && "$subj_dn" == "$issuer_dn" ]]; then
        echo "ERROR: Self-signed certificate rejected in production portal-up.sh." >&2
        return 1
    fi

    # Verify leaf chain against CA bundle
    if ! openssl verify -CAfile "$CA_BUNDLE_FILE" -untrusted "$CERT_FILE" "$CERT_FILE" >/dev/null 2>&1 &&        ! openssl verify -CAfile "$CA_BUNDLE_FILE" "$CERT_FILE" >/dev/null 2>&1; then
        echo "ERROR: Certificate chain verification failed against CA bundle $CA_BUNDLE_FILE." >&2
        return 1
    fi

    # Verify SAN contains portal.sv.lan
    if ! openssl x509 -in "$CERT_FILE" -noout -text 2>/dev/null | grep -E "DNS:portal\.sv\.lan(\s|,|$)" >/dev/null; then
        echo "ERROR: Certificate SAN does not contain DNS:portal.sv.lan." >&2
        return 1
    fi

    # Verify Extended Key Usage includes serverAuth
    if ! openssl x509 -in "$CERT_FILE" -noout -text 2>/dev/null | grep -E "TLS Web Server Authentication|serverAuth" >/dev/null; then
        echo "ERROR: Certificate EKU must include TLS Web Server Authentication (serverAuth)." >&2
        return 1
    fi

    # Verify Basic Constraints: MUST explicitly contain CA:FALSE and MUST NOT contain CA:TRUE (H1)
    if openssl x509 -in "$CERT_FILE" -noout -text 2>/dev/null | grep -q "CA:TRUE"; then
        echo "ERROR: Certificate Basic Constraints has CA:TRUE. Leaf certificate must have CA:FALSE." >&2
        return 1
    fi
    if ! openssl x509 -in "$CERT_FILE" -noout -text 2>/dev/null | grep -q "CA:FALSE"; then
        echo "ERROR: Certificate Basic Constraints must explicitly contain CA:FALSE." >&2
        return 1
    fi

    # Verify certificate validity period (not expired, valid within next 24h)
    if ! openssl x509 -in "$CERT_FILE" -noout -checkend 86400 >/dev/null 2>&1; then
        echo "ERROR: Certificate is expired or will expire within 24 hours." >&2
        return 1
    fi

    # Verify key matches certificate public key
    local cert_pubkey_hash key_pubkey_hash
    cert_pubkey_hash=$(openssl x509 -in "$CERT_FILE" -noout -pubkey 2>/dev/null | openssl sha256)
    key_pubkey_hash=$(openssl pkey -in "$KEY_FILE" -pubout 2>/dev/null | openssl sha256)
    if [[ "$cert_pubkey_hash" != "$key_pubkey_hash" ]]; then
        echo "ERROR: TLS private key ($KEY_FILE) does NOT match certificate public key ($CERT_FILE)." >&2
        return 1
    fi

    return 0
}

validate_image_and_digest() {
    # Mandatory image digest requirement (R3-M1)
    if [[ -z "${PORTAL_IMAGE_DIGEST:-}" ]]; then
        echo "ERROR: PORTAL_IMAGE_DIGEST is mandatory in production (fail-closed, provenance enforcement)." >&2
        return 1
    fi
    if [[ ! "$PORTAL_IMAGE_DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]]; then
        echo "ERROR: PORTAL_IMAGE_DIGEST must be a valid 64-hex sha256 digest." >&2
        return 1
    fi

    echo "Inspecting target image $IMAGE_NAME..."
    if ! docker image inspect "$IMAGE_NAME" >/dev/null 2>&1; then
        echo "ERROR: Target image $IMAGE_NAME not found locally. Image must be loaded or pulled." >&2
        return 1
    fi

    local resolved_id
    resolved_id=$(docker image inspect --format '{{.Id}}' "$IMAGE_NAME" 2>/dev/null || true)
    if [[ "$resolved_id" != "$PORTAL_IMAGE_DIGEST" ]]; then
        echo "ERROR: Image ID mismatch. Expected $PORTAL_IMAGE_DIGEST, got $resolved_id." >&2
        return 1
    fi

    TARGET_IMAGE="$resolved_id"
    return 0
}

validate_owner_tuple() {
    local c_name="$1"
    local exp_service="$2"
    local exp_workload="$3"
    local exp_node="$4"
    local exp_instance="$5"

    local existing_service existing_workload existing_node existing_instance
    existing_service=$(docker inspect --format '{{index .Config.Labels "ai.saintvision.service"}}' "$c_name" 2>/dev/null || true)
    existing_workload=$(docker inspect --format '{{index .Config.Labels "ai.saintvision.workload"}}' "$c_name" 2>/dev/null || true)
    existing_node=$(docker inspect --format '{{index .Config.Labels "ai.saintvision.node"}}' "$c_name" 2>/dev/null || true)
    existing_instance=$(docker inspect --format '{{index .Config.Labels "ai.saintvision.instance"}}' "$c_name" 2>/dev/null || true)

    if [[ "$existing_service" != "$exp_service" || "$existing_workload" != "$exp_workload" || "$existing_node" != "$exp_node" || "$existing_instance" != "$exp_instance" ]]; then
        echo "ERROR: Container '$c_name' does NOT match expected owner tuple (service='$existing_service', workload='$existing_workload', node='$existing_node', instance='$existing_instance')." >&2
        return 1
    fi
    return 0
}

staging_cleanup() {
    if [[ -n "${STAGING_NAME:-}" ]] && docker inspect "$STAGING_NAME" >/dev/null 2>&1; then
        echo "Cleaning up staging container '$STAGING_NAME'..." >&2
        docker stop "$STAGING_NAME" >/dev/null 2>&1 || true
        docker rm -f "$STAGING_NAME" >/dev/null 2>&1 || true
    fi
}

run_staging_preflight() {
    STAGING_NAME="${CONTAINER_NAME}-staging-$$"
    echo "Launching staging preflight container '$STAGING_NAME' ($TARGET_IMAGE)..."

    # Trap cleanup on unexpected exit or interrupt during staging (R3-M3)
    trap staging_cleanup EXIT INT TERM

    local add_host_args=()
    if [[ -n "${PORTAL_ADD_HOSTS:-}" ]]; then
        for entry in $PORTAL_ADD_HOSTS; do
            add_host_args+=(--add-host "$entry")
        done
    fi

    docker run -d \
        --name "$STAGING_NAME" \
        --label "${LABEL_SERVICE}" \
        --label "${LABEL_WORKLOAD}" \
        --label "${LABEL_NODE}" \
        --label "ai.saintvision.instance=preflight" \
        --read-only \
        --cap-drop ALL \
        --cap-add NET_BIND_SERVICE \
        --security-opt no-new-privileges \
        --user "${PORTAL_UID}:${PORTAL_GID}" \
        --tmpfs /tmp:rw,noexec,nosuid,size=64m \
        --tmpfs /var/cache/nginx:rw,noexec,nosuid,size=64m \
        --tmpfs /var/run:rw,noexec,nosuid,size=16m \
        "${add_host_args[@]}" \
        --mount "type=bind,source=${CERT_FILE_ABS},target=/etc/nginx/certs/portal.crt,readonly" \
        --mount "type=bind,source=${KEY_FILE_ABS},target=/etc/nginx/certs/portal.key,readonly" \
        --mount "type=bind,source=${CA_BUNDLE_ABS},target=/etc/nginx/certs/ca-bundle.crt,readonly" \
        --mount "type=bind,source=${UPSTREAM_CONF_ABS},target=/etc/nginx/conf.d/upstream.conf,readonly" \
        "$TARGET_IMAGE"

    local staging_running="false"
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
        return 1
    fi

    echo "Running preflight 'nginx -t' in staging container..."
    local nginx_t_out
    if ! nginx_t_out="$(docker exec "$STAGING_NAME" nginx -t 2>&1)"; then
        echo "ERROR: Preflight 'nginx -t' failed in staging container. Existing container preserved; aborting." >&2
        echo "$nginx_t_out" >&2
        docker logs "$STAGING_NAME" 2>&1 || true
        staging_cleanup
        return 1
    fi
    echo "✔ Preflight 'nginx -t' passed."

    # Preflight verified HTTPS probes with CA chain and hostname verification (R3-L1: strict TLS verification)
    echo "Running preflight verified HTTPS health check in staging container..."
    if ! docker exec "$STAGING_NAME" curl -fsS             --cacert /etc/nginx/certs/ca-bundle.crt             --resolve portal.sv.lan:443:127.0.0.1             https://portal.sv.lan/healthz >/dev/null 2>&1; then
        echo "ERROR: Staging preflight verified HTTPS /healthz failed. Existing container preserved; aborting." >&2
        docker logs "$STAGING_NAME" 2>&1 || true
        staging_cleanup
        return 1
    fi

    echo "Verifying static assets via HTTPS in staging container..."
    if ! docker exec "$STAGING_NAME" curl -fsS             --cacert /etc/nginx/certs/ca-bundle.crt             --resolve portal.sv.lan:443:127.0.0.1             https://portal.sv.lan/index.html >/dev/null 2>&1; then
        echo "ERROR: Staging preflight verified HTTPS /index.html failed. Existing container preserved; aborting." >&2
        docker logs "$STAGING_NAME" 2>&1 || true
        staging_cleanup
        return 1
    fi

    if ! docker exec "$STAGING_NAME" curl -fsS             --cacert /etc/nginx/certs/ca-bundle.crt             --resolve portal.sv.lan:443:127.0.0.1             https://portal.sv.lan/auth-config.js >/dev/null 2>&1; then
        echo "ERROR: Staging preflight verified HTTPS /auth-config.js failed. Existing container preserved; aborting." >&2
        docker logs "$STAGING_NAME" 2>&1 || true
        staging_cleanup
        return 1
    fi

    echo "✔ Preflight staging verified HTTPS health & static asset checks passed."
    staging_cleanup
    trap - EXIT INT TERM
    STAGING_NAME=""
    return 0
}

swap_and_launch_production() {
    # Owner Label 4-Tuple Verification and Safe Container Replacement
    if docker container inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
        if ! validate_owner_tuple "$CONTAINER_NAME" "portal" "intranet-portal" "node2" "$PORTAL_INSTANCE"; then
            echo "Refusing to touch non-matching container on node2." >&2
            return 1
        fi

        echo "Stopping and replacing existing owned portal container '$CONTAINER_NAME'..."
        docker stop "$CONTAINER_NAME" >/dev/null
        docker rm "$CONTAINER_NAME" >/dev/null
    fi

    # Clean up only stopped/exited containers matching the exact 4-tuple
    local stale_ids
    stale_ids=$(docker ps -aq         --filter "status=exited"         --filter "label=${LABEL_SERVICE}"         --filter "label=${LABEL_WORKLOAD}"         --filter "label=${LABEL_NODE}"         --filter "label=${LABEL_INSTANCE}" 2>/dev/null || true)
    if [[ -n "$stale_ids" ]]; then
        echo "Cleaning up exited stale container(s) matching exact tuple..."
        docker rm $stale_ids >/dev/null 2>&1 || true
    fi

    local add_host_args=()
    if [[ -n "${PORTAL_ADD_HOSTS:-}" ]]; then
        for entry in $PORTAL_ADD_HOSTS; do
            add_host_args+=(--add-host "$entry")
        done
    fi

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
        --cap-add NET_BIND_SERVICE \
        --security-opt no-new-privileges \
        --user "${PORTAL_UID}:${PORTAL_GID}" \
        --tmpfs /tmp:rw,noexec,nosuid,size=64m \
        --tmpfs /var/cache/nginx:rw,noexec,nosuid,size=64m \
        --tmpfs /var/run:rw,noexec,nosuid,size=16m \
        "${add_host_args[@]}" \
        --publish "${HTTP_PORT}:80" \
        --publish "${HTTPS_PORT}:443" \
        --mount "type=bind,source=${CERT_FILE_ABS},target=/etc/nginx/certs/portal.crt,readonly" \
        --mount "type=bind,source=${KEY_FILE_ABS},target=/etc/nginx/certs/portal.key,readonly" \
        --mount "type=bind,source=${CA_BUNDLE_ABS},target=/etc/nginx/certs/ca-bundle.crt,readonly" \
        --mount "type=bind,source=${UPSTREAM_CONF_ABS},target=/etc/nginx/conf.d/upstream.conf,readonly" \
        "$TARGET_IMAGE"

    echo "Verifying production container status and stability..."
    local running="false"
    for i in {1..15}; do
        if [[ "$(docker inspect --format '{{.State.Running}}' "$CONTAINER_NAME" 2>/dev/null || true)" == "true" ]]; then
            running="true"
            break
        fi
        sleep 1
    done

    if [[ "$running" != "true" ]]; then
        echo "ERROR: Portal container '$CONTAINER_NAME' failed to enter running state." >&2
        docker logs "$CONTAINER_NAME" 2>&1 || true
        return 1
    fi

    local restart_count
    restart_count=$(docker inspect --format '{{.RestartCount}}' "$CONTAINER_NAME" 2>/dev/null || echo "0")
    if [[ "$restart_count" -ne 0 ]]; then
        echo "ERROR: Portal container has restarted $restart_count times (crash loop detected)." >&2
        docker logs "$CONTAINER_NAME" 2>&1 || true
        return 1
    fi

    sleep 1
    local restart_count_after
    restart_count_after=$(docker inspect --format '{{.RestartCount}}' "$CONTAINER_NAME" 2>/dev/null || echo "0")
    if [[ "$restart_count_after" -ne 0 ]]; then
        echo "ERROR: Portal container crashed during startup stabilization ($restart_count_after restarts)." >&2
        docker logs "$CONTAINER_NAME" 2>&1 || true
        return 1
    fi

    # Production verified HTTPS health probe (Codex note)
    echo "Running production verified HTTPS health probe on '$CONTAINER_NAME'..."
    if ! docker exec "$CONTAINER_NAME" curl -fsS             --cacert /etc/nginx/certs/ca-bundle.crt             --resolve portal.sv.lan:443:127.0.0.1             https://portal.sv.lan/healthz >/dev/null 2>&1; then
        echo "ERROR: Production verified HTTPS /healthz failed." >&2
        docker logs "$CONTAINER_NAME" 2>&1 || true
        return 1
    fi

    echo "✔ SaintVision Intranet Portal successfully launched and verified running."
    echo "  Container:    $CONTAINER_NAME"
    echo "  Image ID:     $TARGET_IMAGE"
    echo "  Tuple:        service=portal, workload=intranet-portal, node=node2, instance=${PORTAL_INSTANCE}"
    echo "  HTTP Port:    $HTTP_PORT -> 80 (HTTPS redirect)"
    echo "  HTTPS Port:   $HTTPS_PORT -> 443"
    echo "  Upstream:     ${UPSTREAM_CP_HOST}"
    echo "  RestartCount: $restart_count_after (clean start)"
    return 0
}

# -----------------------------------------------------------------------------
# Main Execution Entrypoint
# -----------------------------------------------------------------------------
main() {
    validate_argv_secrets "$@"
    validate_environment
    prepare_upstream_config
    validate_ca_bundle_and_allowlist
    validate_leaf_certificate
    validate_image_and_digest

    CERT_FILE_ABS="$(cd -- "$(dirname -- "$CERT_FILE")" && pwd)/$(basename -- "$CERT_FILE")"
    KEY_FILE_ABS="$(cd -- "$(dirname -- "$KEY_FILE")" && pwd)/$(basename -- "$KEY_FILE")"
    CA_BUNDLE_ABS="$(cd -- "$(dirname -- "$CA_BUNDLE_FILE")" && pwd)/$(basename -- "$CA_BUNDLE_FILE")"

    run_staging_preflight
    swap_and_launch_production
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
