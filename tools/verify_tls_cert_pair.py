"""Verify that a PEM certificate and private key contain the same public key."""

from __future__ import annotations

import argparse
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import serialization


def verify_pair(certificate_path: Path, private_key_path: Path) -> None:
    certificate = x509.load_pem_x509_certificate(certificate_path.read_bytes())
    private_key = serialization.load_pem_private_key(private_key_path.read_bytes(), password=None)
    certificate_public = certificate.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    key_public = private_key.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    if certificate_public != key_public:
        raise ValueError("TLS certificate and private key public keys do not match")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a TLS certificate/private-key pair")
    parser.add_argument("--certificate", type=Path, required=True)
    parser.add_argument("--private-key", type=Path, required=True)
    args = parser.parse_args()
    try:
        verify_pair(args.certificate, args.private_key)
    except Exception as exc:
        print(f"TLS certificate/key verification failed: {exc}")
        return 1
    print("TLS certificate/key public keys match")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
