"""Operate the private SaintVision intranet PKI without exporting Node keys.

All private material must live below an ignored operator directory.  The root
key is used only to create the issuing intermediate; day-to-day server and Node
certificates are signed by the intermediate.  Commands print redacted metadata,
never a private key or passphrase.
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import ipaddress
import json
import os
import re
import secrets
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

ROOT_COMMON_NAME = "SaintVision Intranet HTTPS Root CA 2026"
INTERMEDIATE_COMMON_NAME = "SaintVision Intranet HTTPS Issuing CA 2026"
NODE_ROOT_COMMON_NAME = "SaintVision Intranet Node mTLS Root CA 2026"
NODE_INTERMEDIATE_COMMON_NAME = "SaintVision Intranet Node mTLS Issuing CA 2026"
ROOT_VALID_DAYS = 3650
INTERMEDIATE_VALID_DAYS = 1095
SERVER_VALID_DAYS = 90
_HOSTNAME = re.compile(
    r"(?=.{1,253}\Z)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z"
)
_REASONS = {
    "key-compromise": x509.ReasonFlags.key_compromise,
    "affiliation-changed": x509.ReasonFlags.affiliation_changed,
    "superseded": x509.ReasonFlags.superseded,
    "cessation-of-operation": x509.ReasonFlags.cessation_of_operation,
    "privilege-withdrawn": x509.ReasonFlags.privilege_withdrawn,
}


def _run(args: list[object]) -> None:
    completed = subprocess.run(
        [str(value) for value in args],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=15,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(f"{Path(str(args[0])).name} failed")


def private_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError("PKI directory must not be a symlink")
    if os.name == "nt":
        _run(
            [
                "icacls.exe",
                path,
                "/inheritance:r",
                "/grant:r",
                f"{getpass.getuser()}:(OI)(CI)F",
                "*S-1-5-18:(OI)(CI)F",
                "*S-1-5-32-544:(OI)(CI)F",
            ]
        )
    else:
        path.chmod(0o700)


def secure_write(path: Path, data: bytes) -> None:
    if path.exists() or path.is_symlink():
        raise ValueError(f"Refusing to replace {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)
    path.chmod(0o600)


def _name(common_name: str) -> x509.Name:
    return x509.Name(
        [
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Inviz"),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ]
    )


def _key_usage() -> x509.KeyUsage:
    return x509.KeyUsage(
        digital_signature=False,
        content_commitment=False,
        key_encipherment=False,
        data_encipherment=False,
        key_agreement=False,
        key_cert_sign=True,
        crl_sign=True,
        encipher_only=None,
        decipher_only=None,
    )


def _encrypted_key(key: Any, password: bytes) -> bytes:
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.BestAvailableEncryption(password),
    )


def _public_key_bytes(key: Any) -> bytes:
    return key.public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def _certificate_fingerprint(certificate: x509.Certificate) -> str:
    return certificate.fingerprint(hashes.SHA256()).hex()


def _paths(ca_dir: Path) -> dict[str, Path]:
    return {
        "root_key": ca_dir / "root" / "private" / "root-key.pem",
        "root_certificate": ca_dir / "root" / "certs" / "root-cert.pem",
        "intermediate_key": ca_dir / "intermediate" / "private" / "intermediate-key.pem",
        "intermediate_password": ca_dir / "intermediate" / "private" / "intermediate-key.pass",
        "intermediate_certificate": ca_dir / "intermediate" / "certs" / "intermediate-cert.pem",
        "chain": ca_dir / "intermediate" / "certs" / "ca-chain.pem",
        "crl": ca_dir / "intermediate" / "crl" / "intermediate.crl.pem",
        "revocations": ca_dir / "intermediate" / "crl" / "revocations.json",
        "metadata": ca_dir / "public-metadata.json",
    }


def _load_private_key(key_path: Path, password_path: Path) -> Any:
    if key_path.is_symlink() or password_path.is_symlink():
        raise ValueError("Private key inputs must not be symlinks")
    password = password_path.read_bytes().strip()
    key = serialization.load_pem_private_key(key_path.read_bytes(), password=password)
    if not isinstance(key, (ec.EllipticCurvePrivateKey, Ed25519PrivateKey)):
        raise ValueError("Expected an ECDSA P-256 or Ed25519 private key")
    if isinstance(key, ec.EllipticCurvePrivateKey) and not isinstance(key.curve, ec.SECP256R1):
        raise ValueError("Expected an ECDSA P-256 private key")
    return key


def _signature_algorithm(key: Any) -> hashes.HashAlgorithm | None:
    return hashes.SHA256() if isinstance(key, ec.EllipticCurvePrivateKey) else None


def _verify_certificate_signature(issuer: x509.Certificate, certificate: x509.Certificate) -> None:
    public_key = issuer.public_key()
    if isinstance(public_key, ec.EllipticCurvePublicKey):
        public_key.verify(
            certificate.signature,
            certificate.tbs_certificate_bytes,
            ec.ECDSA(certificate.signature_hash_algorithm),
        )
    else:
        public_key.verify(certificate.signature, certificate.tbs_certificate_bytes)


def _build_crl(
    issuer_key: Any,
    issuer_certificate: x509.Certificate,
    revocations: list[dict[str, str]],
    *,
    now: datetime,
) -> x509.CertificateRevocationList:
    builder = (
        x509.CertificateRevocationListBuilder()
        .issuer_name(issuer_certificate.subject)
        .last_update(now - timedelta(minutes=1))
        .next_update(now + timedelta(days=7))
    )
    for item in revocations:
        revoked_at = datetime.fromisoformat(item["revokedAt"])
        revoked = (
            x509.RevokedCertificateBuilder()
            .serial_number(int(item["serialNumber"], 16))
            .revocation_date(revoked_at)
            .add_extension(x509.CRLReason(_REASONS[item["reason"]]), critical=False)
            .build()
        )
        builder = builder.add_revoked_certificate(revoked)
    return builder.sign(issuer_key, algorithm=_signature_algorithm(issuer_key))


def initialize(
    ca_dir: Path,
    *,
    root_password_file: Path,
    profile: str = "https",
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    private_directory(ca_dir)
    paths = _paths(ca_dir)
    if any(path.exists() for path in paths.values()):
        raise ValueError("PKI already exists; rotation requires a separate reviewed directory")
    root_password_file = root_password_file.resolve()
    if root_password_file.is_symlink() or root_password_file.exists():
        raise ValueError("Root passphrase destination must be a new regular path")
    try:
        root_password_file.relative_to(ca_dir.resolve())
    except ValueError:
        pass
    else:
        raise ValueError("Root passphrase must be stored outside the online CA directory")
    private_directory(root_password_file.parent)

    if profile == "https":
        root_key = ec.generate_private_key(ec.SECP256R1())
        intermediate_key = ec.generate_private_key(ec.SECP256R1())
        root_common_name = ROOT_COMMON_NAME
        intermediate_common_name = INTERMEDIATE_COMMON_NAME
        purpose = "browser-compatible-https"
        public_key_algorithm = "ECDSA-P256"
    elif profile == "node-mtls":
        root_key = Ed25519PrivateKey.generate()
        intermediate_key = Ed25519PrivateKey.generate()
        root_common_name = NODE_ROOT_COMMON_NAME
        intermediate_common_name = NODE_INTERMEDIATE_COMMON_NAME
        purpose = "node-mtls-only"
        public_key_algorithm = "Ed25519"
    else:
        raise ValueError("Unsupported PKI profile")
    root_name = _name(root_common_name)
    root_certificate = (
        x509.CertificateBuilder()
        .subject_name(root_name)
        .issuer_name(root_name)
        .public_key(root_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=ROOT_VALID_DAYS))
        .add_extension(x509.BasicConstraints(ca=True, path_length=1), critical=True)
        .add_extension(_key_usage(), critical=True)
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(root_key.public_key()),
            critical=False,
        )
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(root_key.public_key()),
            critical=False,
        )
        .sign(root_key, algorithm=_signature_algorithm(root_key))
    )

    intermediate_certificate = (
        x509.CertificateBuilder()
        .subject_name(_name(intermediate_common_name))
        .issuer_name(root_certificate.subject)
        .public_key(intermediate_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=INTERMEDIATE_VALID_DAYS))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(_key_usage(), critical=True)
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(intermediate_key.public_key()),
            critical=False,
        )
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(root_key.public_key()),
            critical=False,
        )
        .sign(root_key, algorithm=_signature_algorithm(root_key))
    )

    root_password = secrets.token_hex(32).encode("ascii")
    intermediate_password = secrets.token_hex(32).encode("ascii")
    root_pem = root_certificate.public_bytes(serialization.Encoding.PEM)
    intermediate_pem = intermediate_certificate.public_bytes(serialization.Encoding.PEM)
    secure_write(paths["root_key"], _encrypted_key(root_key, root_password))
    secure_write(root_password_file, root_password)
    secure_write(paths["root_certificate"], root_pem)
    secure_write(
        paths["intermediate_key"],
        _encrypted_key(intermediate_key, intermediate_password),
    )
    secure_write(paths["intermediate_password"], intermediate_password)
    secure_write(paths["intermediate_certificate"], intermediate_pem)
    secure_write(paths["chain"], intermediate_pem + root_pem)
    secure_write(paths["revocations"], b"[]\n")
    crl = _build_crl(intermediate_key, intermediate_certificate, [], now=now).public_bytes(
        serialization.Encoding.PEM
    )
    secure_write(paths["crl"], crl)

    metadata = {
        "schemaVersion": (
            "saintvision-intranet-https-pki:2"
            if profile == "https"
            else "saintvision-intranet-node-mtls-pki:1"
        ),
        "createdAt": now.isoformat(),
        "purpose": purpose,
        "publicKeyAlgorithm": public_key_algorithm,
        "root": {
            "commonName": root_common_name,
            "notAfter": root_certificate.not_valid_after_utc.isoformat(),
            "sha256": _certificate_fingerprint(root_certificate),
            "offline": False,
            "operatorIsolated": True,
            "passphraseSeparated": True,
        },
        "intermediate": {
            "commonName": intermediate_common_name,
            "notAfter": intermediate_certificate.not_valid_after_utc.isoformat(),
            "sha256": _certificate_fingerprint(intermediate_certificate),
        },
        "profiles": {
            "controlPlaneHttpsDays": SERVER_VALID_DAYS,
            "pilotNodeMtlsDays": 6,
        },
        "revocation": {
            "crlNextUpdateDays": 7,
            "distributionEnforced": False,
            "emergencyAction": (
                "replace-trust-bundle-and-leaf"
                if profile == "https"
                else "revoke-node-channel-and-replace-trust-bundle"
            ),
        },
    }
    secure_write(
        paths["metadata"],
        (json.dumps(metadata, indent=2, ensure_ascii=False) + "\n").encode("utf-8"),
    )
    return metadata


def issue_server(
    ca_dir: Path,
    output: Path,
    *,
    hostname: str,
    address: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    hostname = hostname.strip().lower()
    if not _HOSTNAME.fullmatch(hostname) or not hostname.endswith(".sv.lan"):
        raise ValueError("Server hostname must be a canonical .sv.lan DNS name")
    ip = ipaddress.ip_address(address)
    if ip.version != 4 or not ip.is_private or ip.is_loopback:
        raise ValueError("Server address must be a private non-loopback IPv4 address")
    paths = _paths(ca_dir)
    intermediate_key = _load_private_key(paths["intermediate_key"], paths["intermediate_password"])
    if not isinstance(intermediate_key, ec.EllipticCurvePrivateKey) or not isinstance(
        intermediate_key.curve, ec.SECP256R1
    ):
        raise ValueError("HTTPS server certificates require the ECDSA P-256 CA profile")
    intermediate = x509.load_pem_x509_certificate(paths["intermediate_certificate"].read_bytes())
    root_pem = paths["root_certificate"].read_bytes()
    key = ec.generate_private_key(ec.SECP256R1())
    certificate = (
        x509.CertificateBuilder()
        .subject_name(_name(hostname))
        .issuer_name(intermediate.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(
            min(
                now + timedelta(days=SERVER_VALID_DAYS),
                intermediate.not_valid_after_utc,
            )
        )
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=None,
                decipher_only=None,
            ),
            critical=True,
        )
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName(hostname), x509.IPAddress(ip)]),
            critical=False,
        )
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(intermediate_key.public_key()),
            critical=False,
        )
        .sign(intermediate_key, algorithm=hashes.SHA256())
    )
    private_directory(output)
    certificate_pem = certificate.public_bytes(serialization.Encoding.PEM)
    intermediate_pem = intermediate.public_bytes(serialization.Encoding.PEM)
    secure_write(
        output / "server-key.pem",
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
    )
    secure_write(output / "server-cert.pem", certificate_pem)
    secure_write(output / "server-chain.pem", certificate_pem + intermediate_pem)
    secure_write(output / "trust-chain.pem", intermediate_pem + root_pem)
    return {
        "schemaVersion": "saintvision-intranet-https-server-certificate:2",
        "hostname": hostname,
        "address": str(ip),
        "notAfter": certificate.not_valid_after_utc.isoformat(),
        "certificateSHA256": _certificate_fingerprint(certificate),
        "privateKeyExported": False,
        "publicKeyAlgorithm": "ECDSA-P256",
    }


def _refresh_crl(ca_dir: Path, *, now: datetime) -> tuple[x509.CertificateRevocationList, int]:
    paths = _paths(ca_dir)
    entries = json.loads(paths["revocations"].read_text(encoding="utf-8"))
    if not isinstance(entries, list):
        raise ValueError("Revocation registry is invalid")
    issuer = x509.load_pem_x509_certificate(paths["intermediate_certificate"].read_bytes())
    issuer_key = _load_private_key(paths["intermediate_key"], paths["intermediate_password"])
    crl = _build_crl(issuer_key, issuer, entries, now=now)
    crl_temp = paths["crl"].with_suffix(".tmp")
    crl_temp.write_bytes(crl.public_bytes(serialization.Encoding.PEM))
    crl_temp.chmod(0o600)
    os.replace(crl_temp, paths["crl"])
    return crl, len(entries)


def refresh_crl(ca_dir: Path, *, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    crl, count = _refresh_crl(ca_dir, now=now)
    return {
        "schemaVersion": "saintvision-intranet-crl-refresh:1",
        "revocationCount": count,
        "crlSHA256": hashlib.sha256(crl.public_bytes(serialization.Encoding.DER)).hexdigest(),
        "nextUpdate": crl.next_update_utc.isoformat(),
        "distributionEnforced": False,
    }


def revoke(
    ca_dir: Path,
    certificate_path: Path,
    *,
    reason: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    if reason not in _REASONS:
        raise ValueError("Unsupported revocation reason")
    paths = _paths(ca_dir)
    certificate = x509.load_pem_x509_certificate(certificate_path.read_bytes())
    issuer = x509.load_pem_x509_certificate(paths["intermediate_certificate"].read_bytes())
    if certificate.issuer != issuer.subject:
        raise ValueError("Certificate was not issued by this intermediate")
    _verify_certificate_signature(issuer, certificate)
    serial = format(certificate.serial_number, "x")
    entries = json.loads(paths["revocations"].read_text(encoding="utf-8"))
    if not isinstance(entries, list):
        raise ValueError("Revocation registry is invalid")
    existing = [item for item in entries if item.get("serialNumber") == serial]
    if existing:
        if existing[0].get("reason") != reason:
            raise ValueError("Certificate is already revoked for another reason")
    else:
        entries.append(
            {
                "serialNumber": serial,
                "certificateSHA256": _certificate_fingerprint(certificate),
                "reason": reason,
                "revokedAt": now.isoformat(),
            }
        )
    entries.sort(key=lambda item: item["serialNumber"])
    registry_temp = paths["revocations"].with_suffix(".tmp")
    registry_temp.write_text(
        json.dumps(entries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    registry_temp.chmod(0o600)
    os.replace(registry_temp, paths["revocations"])
    crl, _ = _refresh_crl(ca_dir, now=now)
    return {
        "schemaVersion": "saintvision-intranet-revocation:1",
        "revokedCertificateSHA256": _certificate_fingerprint(certificate),
        "reason": reason,
        "revocationCount": len(entries),
        "crlSHA256": hashlib.sha256(crl.public_bytes(serialization.Encoding.DER)).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ca-dir", type=Path, required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    initialization = commands.add_parser("init")
    initialization.add_argument("--root-password-file", type=Path, required=True)
    node_initialization = commands.add_parser("init-node-mtls")
    node_initialization.add_argument("--root-password-file", type=Path, required=True)
    issue = commands.add_parser("issue-server")
    issue.add_argument("--hostname", required=True)
    issue.add_argument("--address", required=True)
    issue.add_argument("--output", type=Path, required=True)
    revocation = commands.add_parser("revoke")
    revocation.add_argument("--certificate", type=Path, required=True)
    revocation.add_argument("--reason", choices=sorted(_REASONS), required=True)
    commands.add_parser("refresh-crl")
    args = parser.parse_args()
    ca_dir = args.ca_dir.resolve()
    try:
        if args.command in {"init", "init-node-mtls"}:
            result = initialize(
                ca_dir,
                root_password_file=args.root_password_file.resolve(),
                profile="node-mtls" if args.command == "init-node-mtls" else "https",
            )
        elif args.command == "issue-server":
            result = issue_server(
                ca_dir,
                args.output.resolve(),
                hostname=args.hostname,
                address=args.address,
            )
        elif args.command == "revoke":
            result = revoke(
                ca_dir,
                args.certificate.resolve(),
                reason=args.reason,
            )
        else:
            result = refresh_crl(ca_dir)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as error:
        print(
            f"Intranet PKI {args.command} failed ({type(error).__name__}); "
            "no private material printed.",
            file=os.sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
