"""PG-free checks for the private root/intermediate certificate boundary."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.x509.oid import ExtendedKeyUsageOID

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import intranet_pki


def test_initializes_encrypted_offline_root_and_issuing_chain(tmp_path: Path):
    ca_dir = tmp_path / "ca"

    metadata = intranet_pki.initialize(ca_dir)

    paths = intranet_pki._paths(ca_dir)
    root = x509.load_pem_x509_certificate(paths["root_certificate"].read_bytes())
    intermediate = x509.load_pem_x509_certificate(paths["intermediate_certificate"].read_bytes())
    root.public_key().verify(intermediate.signature, intermediate.tbs_certificate_bytes)
    chain = paths["chain"].read_bytes()
    assert chain.startswith(intermediate.public_bytes(serialization.Encoding.PEM))
    assert chain.endswith(root.public_bytes(serialization.Encoding.PEM))
    assert root.extensions.get_extension_for_class(x509.BasicConstraints).value.path_length == 1
    assert (
        intermediate.extensions.get_extension_for_class(x509.BasicConstraints).value.path_length
        == 0
    )
    with pytest.raises(TypeError):
        serialization.load_pem_private_key(paths["root_key"].read_bytes(), password=None)
    with pytest.raises(TypeError):
        serialization.load_pem_private_key(paths["intermediate_key"].read_bytes(), password=None)
    assert metadata["root"]["offline"] is True
    assert json.loads(paths["revocations"].read_text(encoding="utf-8")) == []

    with pytest.raises(ValueError, match="already exists"):
        intranet_pki.initialize(ca_dir)


def test_issues_exact_cp_dns_and_private_ip_without_printing_key(tmp_path: Path):
    ca_dir = tmp_path / "ca"
    output = tmp_path / "cp"
    intranet_pki.initialize(ca_dir)

    result = intranet_pki.issue_server(
        ca_dir,
        output,
        hostname="cp.sv.lan",
        address="192.168.45.74",
    )

    certificate = x509.load_pem_x509_certificate((output / "server-cert.pem").read_bytes())
    san = certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    assert san.get_values_for_type(x509.DNSName) == ["cp.sv.lan"]
    assert [str(value) for value in san.get_values_for_type(x509.IPAddress)] == ["192.168.45.74"]
    assert list(certificate.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value) == [
        ExtendedKeyUsageOID.SERVER_AUTH
    ]
    assert result["privateKeyExported"] is False
    assert "PRIVATE" not in json.dumps(result)
    intermediate = x509.load_pem_x509_certificate(
        intranet_pki._paths(ca_dir)["intermediate_certificate"].read_bytes()
    )
    intermediate.public_key().verify(certificate.signature, certificate.tbs_certificate_bytes)

    with pytest.raises(ValueError, match="canonical .sv.lan"):
        intranet_pki.issue_server(
            ca_dir,
            tmp_path / "wrong",
            hostname="cp.example.com",
            address="192.168.45.74",
        )


def test_revocation_registry_and_crl_bind_the_issued_certificate(tmp_path: Path):
    ca_dir = tmp_path / "ca"
    output = tmp_path / "cp"
    intranet_pki.initialize(ca_dir)
    intranet_pki.issue_server(
        ca_dir,
        output,
        hostname="cp.sv.lan",
        address="192.168.45.74",
    )
    certificate_path = output / "server-cert.pem"
    certificate = x509.load_pem_x509_certificate(certificate_path.read_bytes())

    result = intranet_pki.revoke(
        ca_dir,
        certificate_path,
        reason="superseded",
        now=datetime.now(timezone.utc),
    )

    paths = intranet_pki._paths(ca_dir)
    crl = x509.load_pem_x509_crl(paths["crl"].read_bytes())
    assert crl.get_revoked_certificate_by_serial_number(certificate.serial_number) is not None
    entries = json.loads(paths["revocations"].read_text(encoding="utf-8"))
    assert entries[0]["certificateSHA256"] == result["revokedCertificateSHA256"]
    assert entries[0]["reason"] == "superseded"


def test_rejects_a_certificate_from_another_issuer(tmp_path: Path):
    ca_dir = tmp_path / "ca"
    intranet_pki.initialize(ca_dir)
    foreign_key = Ed25519PrivateKey.generate()
    now = datetime.now(timezone.utc)
    # The parser reaches the issuer check before any use of this certificate.
    foreign = (
        x509.CertificateBuilder()
        .subject_name(intranet_pki._name("foreign"))
        .issuer_name(intranet_pki._name("foreign"))
        .public_key(foreign_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now.replace(year=now.year + 1))
        .sign(foreign_key, algorithm=None)
    )
    certificate_path = tmp_path / "foreign.pem"
    certificate_path.write_bytes(foreign.public_bytes(serialization.Encoding.PEM))

    with pytest.raises(ValueError, match="not issued"):
        intranet_pki.revoke(ca_dir, certificate_path, reason="key-compromise", now=now)
