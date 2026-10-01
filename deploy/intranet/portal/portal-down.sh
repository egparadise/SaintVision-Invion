#!/usr/bin/env bash
# SaintVision Intranet Portal Down Teardown (Card 156)
# Safely stops and removes only containers matching the full 4-tuple owner label:
# service=portal, workload=intranet-portal, node=node2, instance=${PORTAL_INSTANCE}

set -euo pipefail

CONTAINER_NAME="${PORTAL_CONTAINER_NAME:-saintvision-portal}"
PORTAL_INSTANCE="${PORTAL_INSTANCE:-main}"

LABEL_SERVICE="ai.saintvision.service=portal"
LABEL_WORKLOAD="ai.saintvision.workload=intranet-portal"
LABEL_NODE="ai.saintvision.node=node2"
LABEL_INSTANCE="ai.saintvision.instance=${PORTAL_INSTANCE}"

if docker container inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
    existing_service=$(docker inspect --format '{{index .Config.Labels "ai.saintvision.service"}}' "$CONTAINER_NAME" 2>/dev/null || true)
    existing_workload=$(docker inspect --format '{{index .Config.Labels "ai.saintvision.workload"}}' "$CONTAINER_NAME" 2>/dev/null || true)
    existing_node=$(docker inspect --format '{{index .Config.Labels "ai.saintvision.node"}}' "$CONTAINER_NAME" 2>/dev/null || true)
    existing_instance=$(docker inspect --format '{{index .Config.Labels "ai.saintvision.instance"}}' "$CONTAINER_NAME" 2>/dev/null || true)

    if [[ "$existing_service" != "portal" || "$existing_workload" != "intranet-portal" || "$existing_node" != "node2" || "$existing_instance" != "$PORTAL_INSTANCE" ]]; then
        echo "ERROR: Existing container '$CONTAINER_NAME' does NOT match owner tuple." >&2
        echo "Found: service='$existing_service', workload='$existing_workload', node='$existing_node', instance='$existing_instance'." >&2
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

# Clean up only exited containers matching the exact 4-tuple
stale_ids=$(docker ps -aq \
    --filter "status=exited" \
    --filter "label=${LABEL_SERVICE}" \
    --filter "label=${LABEL_WORKLOAD}" \
    --filter "label=${LABEL_NODE}" \
    --filter "label=${LABEL_INSTANCE}" 2>/dev/null || true)
if [[ -n "$stale_ids" ]]; then
    echo "Cleaning up exited container(s) matching exact tuple..."
    docker rm $stale_ids >/dev/null 2>&1 || true
fi
