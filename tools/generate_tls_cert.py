"""
SaintVision Internal Enterprise TLS Certificate Generator
Generates self-signed TLS 1.3 certificate and private key with SAN for internal intranet deployment.
"""

from __future__ import annotations

import datetime as dt
import ipaddress
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def generate_certificates(output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    cert_path = output_dir / "saintvision.crt"
    key_path = output_dir / "saintvision.key"

    print(f"Generating 2048-bit RSA private key...")
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "KR"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "SaintVision Invenio Enterprise"),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "PACS Security Engineering"),
        x509.NameAttribute(NameOID.COMMON_NAME, "saintvision.internal"),
    ])

    san_list = [
        x509.DNSName("saintvision.internal"),
        x509.DNSName("*.node.saintvision.internal"),
        x509.DNSName("localhost"),
        x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
        x509.IPAddress(ipaddress.IPv4Address("192.168.1.101")),
        x509.IPAddress(ipaddress.IPv4Address("192.168.1.102")),
        x509.IPAddress(ipaddress.IPv4Address("192.168.1.103")),
        x509.IPAddress(ipaddress.IPv4Address("192.168.1.104")),
        x509.IPAddress(ipaddress.IPv4Address("192.168.1.105")),
    ]

    now = dt.datetime.now(dt.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + dt.timedelta(days=365))
        .add_extension(x509.SubjectAlternativeName(san_list), critical=False)
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=None),
            critical=True,
        )
        .sign(private_key, hashes.SHA256())
    )

    # Write Private Key
    with open(key_path, "wb") as f:
        f.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )

    # Write Certificate
    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    print(f"✔ Certificate generated: {cert_path}")
    print(f"✔ Private Key generated: {key_path}")
    return cert_path, key_path


if __name__ == "__main__":
    certs_dir = Path("deploy/certs")
    generate_certificates(certs_dir)
