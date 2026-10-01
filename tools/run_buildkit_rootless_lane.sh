#!/usr/bin/env bash
set -euo pipefail

: "${SV_BUILDKIT_BIN_DIR:?}"
: "${SV_ROOTLESSKIT_BIN:?}"
: "${SV_BUILDKIT_OUTPUT_DIR:?}"
: "${SV_BUILDKIT_RUNTIME_DIR:?}"
: "${INV_EVIDENCE_CODE_SHA:?}"

mkdir -p "$SV_BUILDKIT_OUTPUT_DIR" "$SV_BUILDKIT_RUNTIME_DIR"
chmod 700 "$SV_BUILDKIT_RUNTIME_DIR"

export SV_BUILDKITD="$SV_BUILDKIT_BIN_DIR/buildkitd"
export SV_BUILDCTL="$SV_BUILDKIT_BIN_DIR/buildctl"
export SV_BUILDKIT_ADDRESS="unix://$SV_BUILDKIT_RUNTIME_DIR/buildkitd.sock"
export SV_BUILDKIT_STATE="$SV_BUILDKIT_RUNTIME_DIR/state"
export SV_BUILDKIT_HEALTH="$SV_BUILDKIT_RUNTIME_DIR/health.json"
export SV_BUILDKIT_LOG="$SV_BUILDKIT_OUTPUT_DIR/buildkitd.log"
export XDG_RUNTIME_DIR="$SV_BUILDKIT_RUNTIME_DIR/xdg"

"$SV_ROOTLESSKIT_BIN" \
  --state-dir="$SV_BUILDKIT_RUNTIME_DIR/rootlesskit-state" \
  --net=slirp4netns \
  --copy-up=/etc \
  --disable-host-loopback \
  bash -euo pipefail -c '
    mkdir -p "$XDG_RUNTIME_DIR" "$SV_BUILDKIT_STATE"
    chmod 700 "$XDG_RUNTIME_DIR" "$SV_BUILDKIT_STATE"
    "$SV_BUILDKITD" \
      --addr "$SV_BUILDKIT_ADDRESS" \
      --root "$SV_BUILDKIT_STATE" \
      --oci-worker-snapshotter=native \
      >"$SV_BUILDKIT_LOG" 2>&1 &
    daemon_pid=$!
    cleanup() {
      kill "$daemon_pid" 2>/dev/null || true
      wait "$daemon_pid" 2>/dev/null || true
    }
    trap cleanup EXIT
    for attempt in $(seq 1 60); do
      if "$SV_BUILDCTL" --addr "$SV_BUILDKIT_ADDRESS" debug workers >/dev/null 2>&1; then
        break
      fi
      if ! kill -0 "$daemon_pid" 2>/dev/null; then
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
      --buildkitd "$SV_BUILDKITD" \
      --rootlesskit "$SV_ROOTLESSKIT_BIN" \
      --address "$SV_BUILDKIT_ADDRESS" \
      --daemon-pid "$daemon_pid" \
      --health-receipt "$SV_BUILDKIT_HEALTH" \
      --output-dir "$SV_BUILDKIT_OUTPUT_DIR" \
      --junit "$SV_BUILDKIT_OUTPUT_DIR/rootless-buildkit-reference.xml"
  '
