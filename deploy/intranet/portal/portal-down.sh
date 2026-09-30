#!/usr/bin/env bash
# SaintVision Intranet Portal Down Teardown (Card 156)
# Safely stops and removes only containers matching the owner label ai.saintvision.service=portal

set -euo pipefail

CONTAINER_NAME="${PORTAL_CONTAINER_NAME:-saintvision-portal}"
OWNER_LABEL_KEY="ai.saintvision.service"
OWNER_LABEL_VAL="portal"
OWNER_LABEL="${OWNER_LABEL_KEY}=${OWNER_LABEL_VAL}"

if docker container inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
    existing_owner=$(docker inspect --format '{{index .Config.Labels "ai.saintvision.service"}}' "$CONTAINER_NAME" 2>/dev/null || true)
    if [[ "$existing_owner" != "$OWNER_LABEL_VAL" ]]; then
        echo "ERROR: Existing container '$CONTAINER_NAME' is NOT owned by '$OWNER_LABEL' (found: '$existing_owner')." >&2
        echo "Refusing to stop or remove non-owned container." >&2
        exit 1
    fi
    echo "Stopping owned portal container '$CONTAINER_NAME'..."
    docker stop "$CONTAINER_NAME" >/dev/null
    docker rm "$CONTAINER_NAME" >/dev/null
    echo "✔ Portal container '$CONTAINER_NAME' stopped and removed."
else
    echo "Portal container '$CONTAINER_NAME' is not currently present."
fi

# Clean up any leftover containers carrying the portal owner label
stale_ids=$(docker ps -aq --filter "label=${OWNER_LABEL}" 2>/dev/null || true)
if [[ -n "$stale_ids" ]]; then
    echo "Cleaning up additional container(s) matching ${OWNER_LABEL}..."
    docker rm -f $stale_ids >/dev/null 2>&1 || true
fi
