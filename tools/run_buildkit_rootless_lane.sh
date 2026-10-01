#!/usr/bin/env bash
set -euo pipefail

: "${SV_BUILDKIT_BIN_DIR:?}"
: "${SV_BUILDKIT_RUNTIME_IMAGE:?}"
: "${SV_BUILDKIT_CONTAINER_NAME:?}"
: "${SV_BUILDKIT_OUTPUT_DIR:?}"
: "${SV_BUILDKIT_RUNTIME_DIR:?}"
: "${INV_EVIDENCE_CODE_SHA:?}"

mkdir -p "$SV_BUILDKIT_OUTPUT_DIR" "$SV_BUILDKIT_RUNTIME_DIR"
chmod 700 "$SV_BUILDKIT_RUNTIME_DIR"

export SV_BUILDCTL="$SV_BUILDKIT_BIN_DIR/buildctl"
export SV_BUILDKIT_ADDRESS="tcp://127.0.0.1:1234"
export SV_BUILDKIT_HEALTH="$SV_BUILDKIT_RUNTIME_DIR/health.json"
export SV_BUILDKIT_LOG="$SV_BUILDKIT_OUTPUT_DIR/buildkitd.log"

cleanup() {
  docker logs "$SV_BUILDKIT_CONTAINER_NAME" >"$SV_BUILDKIT_LOG" 2>&1 || true
  if docker inspect "$SV_BUILDKIT_CONTAINER_NAME" >/dev/null 2>&1; then
    test "$(docker inspect --format '{{index .Config.Labels "ai.saintvision.s08-buildkit-reference"}}' "$SV_BUILDKIT_CONTAINER_NAME")" = "$GITHUB_RUN_ID"
    test "$(docker inspect --format '{{.Name}}' "$SV_BUILDKIT_CONTAINER_NAME")" = "/$SV_BUILDKIT_CONTAINER_NAME"
    docker rm --force --volumes "$SV_BUILDKIT_CONTAINER_NAME" >/dev/null
  fi
}
trap cleanup EXIT

docker pull --platform linux/amd64 "$SV_BUILDKIT_RUNTIME_IMAGE"
docker run --detach --platform linux/amd64 \
  --name "$SV_BUILDKIT_CONTAINER_NAME" \
  --label "ai.saintvision.s08-buildkit-reference=$GITHUB_RUN_ID" \
  --security-opt seccomp=unconfined \
  --security-opt apparmor=unconfined \
  --security-opt systempaths=unconfined \
  --tmpfs /home/user/.local/share/buildkit:rw,nosuid,nodev,size=2g,uid=1000,gid=1000,mode=0700 \
  --publish 127.0.0.1:1234:1234 \
  "$SV_BUILDKIT_RUNTIME_IMAGE" >/dev/null

for attempt in $(seq 1 60); do
  if "$SV_BUILDCTL" --addr "$SV_BUILDKIT_ADDRESS" debug workers >/dev/null 2>&1; then
    break
  fi
  if test "$(docker inspect --format '{{.State.Running}}' "$SV_BUILDKIT_CONTAINER_NAME")" != true; then
    echo "rootless buildkitd exited before health became ready" >&2
    exit 1
  fi
  if test "$attempt" = 60; then
    echo "rootless buildkitd did not become ready" >&2
    exit 1
  fi
  sleep 1
done

INV_BUILDKIT_REFERENCE_ENABLED=1 \
  python tools/run_buildkit_rootless_roundtrip.py \
  --buildctl "$SV_BUILDCTL" \
  --container-name "$SV_BUILDKIT_CONTAINER_NAME" \
  --runtime-image "$SV_BUILDKIT_RUNTIME_IMAGE" \
  --address "$SV_BUILDKIT_ADDRESS" \
  --health-receipt "$SV_BUILDKIT_HEALTH" \
  --output-dir "$SV_BUILDKIT_OUTPUT_DIR" \
  --junit "$SV_BUILDKIT_OUTPUT_DIR/rootless-buildkit-reference.xml"
