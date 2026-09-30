#!/usr/bin/env bash
# =============================================================================
# SaintVision Intranet Portal - Release Artifact Verification & Loader
# Card 156: Node-side Release Verification & Load Script
#
# Usage:
#   portal-load-release.sh --evidence <evidence.json> --tar <portal-image.tar> [--verify-only]
#   or:
#   portal-load-release.sh <evidence.json> <portal-image.tar> [--verify-only]
#
# Verification Pipeline:
#   1. Strict Evidence Schema Validation (fail-closed on unknown fields, missing fields, or format mismatch)
#   2. Release Tarball SHA-256 Checksum Verification
#   3. Docker Image Load ('docker load -i')
#   4. Docker Config .Id Verification against Evidence imageId
#   5. Hand-off to portal-up.sh with verified PORTAL_IMAGE_ID
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORTAL_UP_SCRIPT="${SCRIPT_DIR}/portal-up.sh"

EVIDENCE_FILE=""
TAR_FILE=""
VERIFY_ONLY="false"

# Parse CLI arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --evidence)
            EVIDENCE_FILE="$2"
            shift 2
            ;;
        --tar)
            TAR_FILE="$2"
            shift 2
            ;;
        --verify-only)
            VERIFY_ONLY="true"
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [--evidence <evidence.json>] [--tar <portal-image.tar>] [--verify-only]"
            exit 0
            ;;
        *)
            if [[ -z "$EVIDENCE_FILE" ]]; then
                EVIDENCE_FILE="$1"
            elif [[ -z "$TAR_FILE" ]]; then
                TAR_FILE="$1"
            elif [[ "$1" == "--verify-only" ]]; then
                VERIFY_ONLY="true"
            else
                echo "ERROR: Unknown argument: $1" >&2
                exit 1
            fi
            shift
            ;;
    esac
done

EVIDENCE_FILE="${EVIDENCE_FILE:-${PORTAL_RELEASE_EVIDENCE:-}}"
TAR_FILE="${TAR_FILE:-${PORTAL_RELEASE_TAR:-}}"

if [[ -z "$EVIDENCE_FILE" ]]; then
    echo "ERROR: Missing release evidence file. Specify --evidence <path> or set PORTAL_RELEASE_EVIDENCE." >&2
    exit 1
fi

if [[ -z "$TAR_FILE" ]]; then
    echo "ERROR: Missing release tarball file. Specify --tar <path> or set PORTAL_RELEASE_TAR." >&2
    exit 1
fi

if [[ ! -f "$EVIDENCE_FILE" ]]; then
    echo "ERROR: Release evidence file not found: $EVIDENCE_FILE" >&2
    exit 1
fi

if [[ ! -f "$TAR_FILE" ]]; then
    echo "ERROR: Release tarball file not found: $TAR_FILE" >&2
    exit 1
fi

# Locate functional Python binary for hermetic JSON & hash operations
PYTHON_BIN=""
for candidate in python3 python py; do
    if command -v "$candidate" >/dev/null 2>&1; then
        if "$candidate" -c "import sys" >/dev/null 2>&1; then
            PYTHON_BIN="$candidate"
            break
        fi
    fi
done

if [[ -z "$PYTHON_BIN" ]]; then
    echo "ERROR: Functional Python 3 is required for release evidence verification but not found." >&2
    exit 1
fi

echo "================================================================="
echo "SaintVision Portal - Release Verification & Image Load"
echo "Evidence File: $EVIDENCE_FILE"
echo "Tarball File:  $TAR_FILE"
echo "================================================================="

# -----------------------------------------------------------------------------
# 1. Strict Evidence Schema Validation (Fail-closed on unknown fields)
# -----------------------------------------------------------------------------
echo "Validating release evidence schema (strict, fail-closed)..."

VALIDATION_OUTPUT=$($PYTHON_BIN - <<'PYEOF' "$EVIDENCE_FILE"
import sys, json, re

evidence_path = sys.argv[1]
try:
    with open(evidence_path, "r", encoding="utf-8") as f:
        data = json.load(f)
except Exception as e:
    sys.exit(f"ERROR: Failed to parse Evidence JSON: {e}")

if not isinstance(data, dict):
    sys.exit("ERROR: Evidence root must be a JSON object.")

allowed_keys = {
    "$schema",
    "schemaVersion",
    "codeSha",
    "imageId",
    "tarSha256",
    "buildRunId",
    "buildTimestamp",
    "imageTag",
}
unknown_keys = set(data.keys()) - allowed_keys
if unknown_keys:
    sys.exit(f"ERROR: Unknown field(s) in Evidence JSON (fail-closed): {sorted(unknown_keys)}")

required_keys = [
    "schemaVersion",
    "codeSha",
    "imageId",
    "tarSha256",
    "buildRunId",
    "buildTimestamp",
]
for k in required_keys:
    if k not in data or data[k] is None or data[k] == "":
        sys.exit(f"ERROR: Missing required field in Evidence JSON: {k}")

if data["schemaVersion"] != "1.0.0":
    sys.exit(f"ERROR: Unsupported schemaVersion: {data['schemaVersion']} (expected '1.0.0')")

if not re.match(r"^[0-9a-f]{40}$", str(data["codeSha"])):
    sys.exit(f"ERROR: Invalid codeSha format (expected 40-hex lowercase): {data['codeSha']}")

if not re.match(r"^sha256:[0-9a-f]{64}$", str(data["imageId"])):
    sys.exit(f"ERROR: Invalid imageId format (expected 'sha256:<64-hex>'): {data['imageId']}")

if not re.match(r"^[0-9a-f]{64}$", str(data["tarSha256"])):
    sys.exit(f"ERROR: Invalid tarSha256 format (expected 64-hex lowercase): {data['tarSha256']}")

# Emit sanitized bash key-value pairs
print(f"EXP_IMAGE_ID='{data['imageId']}'")
print(f"EXP_TAR_SHA256='{data['tarSha256']}'")
print(f"EXP_CODE_SHA='{data['codeSha']}'")
print(f"EXP_IMAGE_TAG='{data.get('imageTag', '')}'")
PYEOF
) || {
    echo "$VALIDATION_OUTPUT" >&2
    exit 1
}

eval "$VALIDATION_OUTPUT"
echo "✔ Release evidence schema validated successfully."
echo "  Sealed Image ID:   $EXP_IMAGE_ID"
echo "  Sealed Tar SHA256: $EXP_TAR_SHA256"
echo "  Sealed Code SHA:   $EXP_CODE_SHA"

# -----------------------------------------------------------------------------
# 2. Release Tarball SHA-256 Checksum Verification
# -----------------------------------------------------------------------------
echo "Verifying release tarball checksum..."
ACTUAL_TAR_SHA256=$($PYTHON_BIN - <<'PYEOF' "$TAR_FILE"
import sys, hashlib
tar_path = sys.argv[1]
h = hashlib.sha256()
with open(tar_path, "rb") as f:
    while chunk := f.read(65536):
        h.update(chunk)
print(h.hexdigest())
PYEOF
)

if [[ "$ACTUAL_TAR_SHA256" != "$EXP_TAR_SHA256" ]]; then
    echo "ERROR: Release tarball SHA-256 mismatch (fail-closed)!" >&2
    echo "  Expected (from evidence): $EXP_TAR_SHA256" >&2
    echo "  Actual (from file):       $ACTUAL_TAR_SHA256" >&2
    exit 1
fi
echo "✔ Tarball SHA-256 verified successfully: $ACTUAL_TAR_SHA256"

# -----------------------------------------------------------------------------
# 3. Docker Image Load ('docker load -i')
# -----------------------------------------------------------------------------
echo "Loading container image into Docker daemon..."
if ! command -v docker >/dev/null 2>&1; then
    echo "ERROR: docker command not found." >&2
    exit 1
fi

LOAD_OUTPUT=$(docker load -i "$TAR_FILE" 2>&1) || {
    echo "ERROR: 'docker load -i' failed (exit $?):" >&2
    echo "$LOAD_OUTPUT" >&2
    exit 1
}
echo "$LOAD_OUTPUT"

# -----------------------------------------------------------------------------
# 4. Verify Loaded Image Config .Id against Evidence imageId
# -----------------------------------------------------------------------------
echo "Verifying loaded image config .Id against evidence imageId..."
LOADED_ID=""
if docker image inspect "$EXP_IMAGE_ID" >/dev/null 2>&1; then
    LOADED_ID=$(docker image inspect --format '{{.Id}}' "$EXP_IMAGE_ID" 2>/dev/null || true)
elif [[ -n "$EXP_IMAGE_TAG" ]] && docker image inspect "$EXP_IMAGE_TAG" >/dev/null 2>&1; then
    LOADED_ID=$(docker image inspect --format '{{.Id}}' "$EXP_IMAGE_TAG" 2>/dev/null || true)
fi

if [[ -z "$LOADED_ID" ]]; then
    echo "ERROR: Loaded image not found in docker daemon using ID $EXP_IMAGE_ID!" >&2
    exit 1
fi

if [[ "$LOADED_ID" != "$EXP_IMAGE_ID" ]]; then
    echo "ERROR: Loaded image config .Id mismatch (fail-closed)!" >&2
    echo "  Expected (from evidence): $EXP_IMAGE_ID" >&2
    echo "  Actual (from inspect):    $LOADED_ID" >&2
    exit 1
fi
echo "✔ Loaded image config .Id verified successfully: $LOADED_ID"

# -----------------------------------------------------------------------------
# 5. Hand-off to portal-up.sh with verified PORTAL_IMAGE_ID
# -----------------------------------------------------------------------------
if [[ "$VERIFY_ONLY" == "true" ]]; then
    echo "✔ Release verification and image load succeeded (--verify-only specified; skipping portal-up.sh)."
    exit 0
fi

if [[ ! -f "$PORTAL_UP_SCRIPT" ]]; then
    echo "ERROR: portal-up.sh not found at: $PORTAL_UP_SCRIPT" >&2
    exit 1
fi

echo "Proceeding to launch production portal container via portal-up.sh..."
export PORTAL_IMAGE_ID="$EXP_IMAGE_ID"
exec bash "$PORTAL_UP_SCRIPT" "$@"
