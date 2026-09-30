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

SCHEMA_FILE="${PORTAL_RELEASE_SCHEMA:-${SCRIPT_DIR}/portal-release-evidence.schema.json}"
if [[ ! -f "$SCHEMA_FILE" ]]; then
    echo "ERROR: Release evidence schema not found at: $SCHEMA_FILE" >&2
    exit 1
fi

# -----------------------------------------------------------------------------
# 1. Strict Evidence Schema Validation (Fail-closed on unknown fields and types)
# -----------------------------------------------------------------------------
echo "Validating release evidence schema (strict, fail-closed)..."

TMP_PARSED=$(mktemp "${TMPDIR:-/tmp}/portal-ev-parsed.XXXXXX")
if ! "$PYTHON_BIN" - "$EVIDENCE_FILE" "$SCHEMA_FILE" > "$TMP_PARSED" 2>&1 <<'PYEOF'
import sys, json, re
from datetime import datetime

evidence_path = sys.argv[1]
schema_path = sys.argv[2]

try:
    with open(evidence_path, "r", encoding="utf-8") as f:
        data = json.load(f)
except Exception as e:
    sys.exit(f"ERROR: Failed to parse Evidence JSON: {e}")

if not isinstance(data, dict):
    sys.exit("ERROR: Evidence root must be a JSON object.")

try:
    with open(schema_path, "r", encoding="utf-8") as sf:
        schema = json.load(sf)
except Exception as e:
    sys.exit(f"ERROR: Failed to load release evidence schema: {e}")

required_keys = schema.get("required", [])
properties = schema.get("properties", {})
additional_properties = schema.get("additionalProperties", False)

# 1. Unknown fields check (additionalProperties: false)
if not additional_properties:
    unknown_keys = set(data.keys()) - set(properties.keys())
    if unknown_keys:
        sys.exit(f"ERROR: Unknown field(s) in Evidence JSON (fail-closed): {sorted(unknown_keys)}")

# 2. Required fields check
for k in required_keys:
    if k not in data or data[k] is None:
        sys.exit(f"ERROR: Missing required field in Evidence JSON: {k}")

# 3. Exact type, pattern, enum, and date-time validation for every field
for k, val in data.items():
    prop = properties.get(k, {})
    expected_type = prop.get("type")
    if expected_type == "string":
        if not isinstance(val, str):
            sys.exit(f"ERROR: Field '{k}' must be of type string, got {type(val).__name__} (fail-closed).")
        if "minLength" in prop and len(val) < prop["minLength"]:
            sys.exit(f"ERROR: Field '{k}' length must be >= {prop['minLength']}.")
        if "enum" in prop and val not in prop["enum"]:
            if k == "schemaVersion":
                sys.exit(f"ERROR: Unsupported schemaVersion: {val} (expected {prop['enum']})")
            sys.exit(f"ERROR: Unsupported {k}: '{val}' (expected one of {prop['enum']})")
        if "pattern" in prop and not re.fullmatch(prop["pattern"], val):
            sys.exit(f"ERROR: Field '{k}' value '{val}' does not match schema pattern {prop['pattern']}")
        if prop.get("format") == "date-time":
            dt_re = r"^\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})$"
            if not re.fullmatch(dt_re, val):
                sys.exit(f"ERROR: Invalid date-time format for {k}: '{val}' (expected RFC 3339 / ISO 8601)")
            try:
                iso_clean = val.replace("Z", "+00:00").replace("z", "+00:00")
                datetime.fromisoformat(iso_clean)
            except Exception as e:
                sys.exit(f"ERROR: Failed to parse date-time in {k}: '{val}' ({e})")
        if any(c in val for c in ("\r", "\n", "\0")):
            sys.exit(f"ERROR: Field '{k}' value contains forbidden newline or control character (fail-closed).")

# Emit exactly 5 verified values separated by NUL (\x00) bytes (NO NEWLINE AMBIGUITY, NO EVAL!)
items = [
    data["imageId"].encode("utf-8"),
    data["tarSha256"].encode("utf-8"),
    data["codeSha"].encode("utf-8"),
    data["buildRunId"].encode("utf-8"),
    data["buildTimestamp"].encode("utf-8"),
    b"",
]
sys.stdout.buffer.write(b"\x00".join(items))
PYEOF
then
    echo "ERROR: Release evidence schema validation failed (fail-closed):" >&2
    cat "$TMP_PARSED" >&2
    rm -f "$TMP_PARSED"
    exit 1
fi

{
    IFS= read -r -d '' EXP_IMAGE_ID
    IFS= read -r -d '' EXP_TAR_SHA256
    IFS= read -r -d '' EXP_CODE_SHA
    IFS= read -r -d '' EXP_BUILD_RUN_ID
    IFS= read -r -d '' EXP_BUILD_TIMESTAMP
} < "$TMP_PARSED"
rm -f "$TMP_PARSED"

if [[ -z "$EXP_IMAGE_ID" || -z "$EXP_TAR_SHA256" || -z "$EXP_CODE_SHA" || -z "$EXP_BUILD_RUN_ID" || -z "$EXP_BUILD_TIMESTAMP" ]]; then
    echo "ERROR: Failed to extract all required fields from release evidence (fail-closed)." >&2
    exit 1
fi

echo "✔ Release evidence schema validated successfully."
echo "  Sealed Image ID:   $EXP_IMAGE_ID"
echo "  Sealed Tar SHA256: $EXP_TAR_SHA256"
echo "  Sealed Code SHA:   $EXP_CODE_SHA"
echo "  Sealed Run ID:     $EXP_BUILD_RUN_ID"
echo "  Sealed Build Time: $EXP_BUILD_TIMESTAMP"

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
ACTUAL_TAR_SHA256="${ACTUAL_TAR_SHA256%$'\r'}"

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
    LOADED_ID="${LOADED_ID%$'\r'}"
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
