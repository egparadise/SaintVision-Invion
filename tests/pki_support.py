"""Synthetic test-only PKI. Private keys never enter tracked artifacts."""

from datetime import datetime, timedelta, timezone
from ipaddress import ip_address
from pathlib import Path
from types import SimpleNamespace
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID


def authority():
    key = Ed25519PrivateKey.generate()
    now = datetime.now(timezone.utc)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "synthetic-test-ca")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(hours=2))
        .not_valid_after(now + timedelta(hours=2))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.KeyUsage(False, False, False, False, False, True, True, None, None),
            critical=True,
        )
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False
        )
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(key.public_key()),
            critical=False,
        )
        .sign(key, None)
    )
    return SimpleNamespace(
        key=key, cert=cert, pem=cert.public_bytes(serialization.Encoding.PEM)
    )


def issue(ca, uri, *, server=False, expired=False, address="127.0.0.1", extra_uri=None):
    key = Ed25519PrivateKey.generate()
    now = datetime.now(timezone.utc)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "synthetic-peer")])
    names = [x509.UniformResourceIdentifier(uri), x509.IPAddress(ip_address(address))]
    if extra_uri:
        names.append(x509.UniformResourceIdentifier(extra_uri))
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(ca.cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(hours=1))
        .not_valid_after(now + timedelta(minutes=-1 if expired else 60))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(True, False, False, False, False, False, False, None, None),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage(
                [
                    (
                        ExtendedKeyUsageOID.SERVER_AUTH
                        if server
                        else ExtendedKeyUsageOID.CLIENT_AUTH
                    )
                ]
            ),
            critical=True,
        )
        .add_extension(x509.SubjectAlternativeName(names), critical=False)
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False
        )
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca.key.public_key()),
            critical=False,
        )
        .sign(ca.key, None)
    )
    return SimpleNamespace(
        key=key,
        cert=cert,
        der=cert.public_bytes(serialization.Encoding.DER),
        pem=cert.public_bytes(serialization.Encoding.PEM),
        private=key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
        fingerprint=cert.fingerprint(hashes.SHA256()).hex(),
    )


def credentials(path, ca, cert, *, prefix="peer"):
    path = Path(path)
    files = {
        "ca_file": path / (prefix + "-ca.pem"),
        "certificate_file": path / (prefix + "-cert.pem"),
        "key_file": path / (prefix + "-key.pem"),
    }
    for name, data in [
        ("ca_file", ca.pem),
        ("certificate_file", cert.pem),
        ("key_file", cert.private),
    ]:
        with files[name].open("wb") as stream:
            stream.write(data)
        files[name].chmod(0o600)
    return files
