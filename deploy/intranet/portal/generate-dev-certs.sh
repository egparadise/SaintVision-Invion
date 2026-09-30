#!/usr/bin/env bash
# Generate Temporary ECDSA P-256 Self-Signed Certificate for Local Portal Smoke Testing
# NOTE: Production leaf certificates for portal.sv.lan are issued by Card 150 PKI CA.
# This script is strictly for local test environments and smoke validation.

set -euo pipefail
umask 077

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CERTS_DIR="${1:-${SCRIPT_DIR}/certs}"

mkdir -p "$CERTS_DIR"

KEY_FILE="${CERTS_DIR}/portal.key"
CERT_FILE="${CERTS_DIR}/portal.crt"

echo "Generating temporary ECDSA P-256 self-signed certificate for portal.sv.lan..."

# Generate ECDSA P-256 (prime256v1) private key
openssl ecparam -name prime256v1 -genkey -noout -out "$KEY_FILE"
chmod 600 "$KEY_FILE"

# Generate self-signed X.509 certificate with SAN DNS:portal.sv.lan
openssl req -new -x509 -sha256 -key "$KEY_FILE" \
    -subj "/C=KR/O=SaintVision/OU=IntranetPortal/CN=portal.sv.lan" \
    -addext "subjectAltName=DNS:portal.sv.lan" \
    -days 30 \
    -out "$CERT_FILE"
chmod 644 "$CERT_FILE"

echo "✔ Temporary certificate generated successfully:"
echo "  Certificate: $CERT_FILE"
echo "  Private Key: $KEY_FILE"
echo "  Algorithm:   ECDSA (prime256v1 / P-256)"
echo "  SAN:         DNS:portal.sv.lan"
echo "  DISCLAIMER:  LOCAL SMOKE TEST ONLY. Card 150 CA leaf required for production."
