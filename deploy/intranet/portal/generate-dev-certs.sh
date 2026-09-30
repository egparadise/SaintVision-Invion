#!/usr/bin/env bash
# Generate Temporary ECDSA P-256 Self-Signed Certificate for Local Portal Smoke Testing
# NOTE: Production leaf certificates for portal.sv.lan are issued by Card 150 PKI CA.
# This script is strictly for local test environments and smoke validation.

set -euo pipefail
umask 077

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CERTS_DIR="${1:-${SCRIPT_DIR}/certs/dev}"

mkdir -p "$CERTS_DIR"

KEY_FILE="${CERTS_DIR}/portal.key"
CERT_FILE="${CERTS_DIR}/portal.crt"

(
    cd "$CERTS_DIR"

    # Generate ECDSA P-256 (prime256v1) private key
    openssl ecparam -name prime256v1 -genkey -noout -out "portal.key"
    chmod 600 "portal.key"

    # Generate self-signed X.509 certificate with SAN DNS:portal.sv.lan using config file
    # This avoids MSYS path conversion issues on Windows Git Bash and empty subject issues on Linux
    cat > "req.cnf" << 'EOF'
[req]
distinguished_name = req_distinguished_name
x509_extensions = v3_req
prompt = no

[req_distinguished_name]
C = KR
O = SaintVision
OU = IntranetPortal
CN = portal.sv.lan

[v3_req]
subjectAltName = DNS:portal.sv.lan
EOF

    openssl req -new -x509 -sha256 -key "portal.key" \
        -config "req.cnf" \
        -days 30 \
        -out "portal.crt"

    rm -f "req.cnf"
    chmod 644 "portal.crt"
)

echo "✔ Temporary certificate generated successfully:"
echo "  Certificate: $CERT_FILE"
echo "  Private Key: $KEY_FILE"
echo "  Algorithm:   ECDSA (prime256v1 / P-256)"
echo "  SAN:         DNS:portal.sv.lan"
echo "  DISCLAIMER:  LOCAL SMOKE TEST ONLY. Card 150 CA leaf required for production."
