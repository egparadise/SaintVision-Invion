"""PG-free checks for the private root/intermediate certificate boundary."""

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID
from cryptography.x509.verification import PolicyBuilder, Store

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import intranet_pki


REPO_ROOT = Path(__file__).resolve().parents[1]


def initialize(tmp_path: Path) -> tuple[Path, Path]:
    ca_dir = tmp_path / "ca"
    root_password = tmp_path / "offline-secret" / "root-key.pass"
    intranet_pki.initialize(ca_dir, root_password_file=root_password)
    return ca_dir, root_password


def test_initializes_browser_compatible_chain_with_separated_root_passphrase(tmp_path: Path):
    ca_dir = tmp_path / "ca"
    root_password = tmp_path / "offline-secret" / "root-key.pass"

    metadata = intranet_pki.initialize(ca_dir, root_password_file=root_password)

    paths = intranet_pki._paths(ca_dir)
    root = x509.load_pem_x509_certificate(paths["root_certificate"].read_bytes())
    intermediate = x509.load_pem_x509_certificate(paths["intermediate_certificate"].read_bytes())
    root.public_key().verify(
        intermediate.signature,
        intermediate.tbs_certificate_bytes,
        ec.ECDSA(intermediate.signature_hash_algorithm),
    )
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
    assert isinstance(root.public_key(), ec.EllipticCurvePublicKey)
    assert isinstance(root.public_key().curve, ec.SECP256R1)
    assert isinstance(intermediate.public_key().curve, ec.SECP256R1)
    assert metadata["root"]["offline"] is False
    assert metadata["root"]["operatorIsolated"] is True
    assert metadata["root"]["passphraseSeparated"] is True
    assert root_password.is_file()
    assert ca_dir.resolve() not in root_password.resolve().parents
    assert json.loads(paths["revocations"].read_text(encoding="utf-8")) == []

    with pytest.raises(ValueError, match="already exists"):
        intranet_pki.initialize(ca_dir, root_password_file=tmp_path / "another.pass")

    with pytest.raises(ValueError, match="outside the online CA"):
        intranet_pki.initialize(
            tmp_path / "other-ca",
            root_password_file=tmp_path / "other-ca" / "root.pass",
        )


def test_issues_exact_cp_dns_and_private_ip_without_printing_key(tmp_path: Path):
    ca_dir, _ = initialize(tmp_path)
    output = tmp_path / "cp"

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
    assert result["publicKeyAlgorithm"] == "ECDSA-P256"
    assert "PRIVATE" not in json.dumps(result)
    intermediate = x509.load_pem_x509_certificate(
        intranet_pki._paths(ca_dir)["intermediate_certificate"].read_bytes()
    )
    intermediate.public_key().verify(
        certificate.signature,
        certificate.tbs_certificate_bytes,
        ec.ECDSA(certificate.signature_hash_algorithm),
    )
    root = x509.load_pem_x509_certificate(
        intranet_pki._paths(ca_dir)["root_certificate"].read_bytes()
    )
    verifier = PolicyBuilder().store(Store([root])).build_server_verifier(x509.DNSName("cp.sv.lan"))
    verified = verifier.verify(certificate, [intermediate])
    assert verified[0] == certificate

    with pytest.raises(ValueError, match="canonical .sv.lan"):
        intranet_pki.issue_server(
            ca_dir,
            tmp_path / "wrong",
            hostname="cp.example.com",
            address="192.168.45.74",
        )


def test_revocation_registry_and_crl_bind_the_issued_certificate(tmp_path: Path):
    ca_dir, _ = initialize(tmp_path)
    output = tmp_path / "cp"
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

    refreshed = intranet_pki.refresh_crl(
        ca_dir,
        now=datetime.now(timezone.utc),
    )
    assert refreshed["revocationCount"] == 1
    assert refreshed["distributionEnforced"] is False
    assert refreshed["nextUpdate"]


def test_rejects_a_certificate_from_another_issuer(tmp_path: Path):
    ca_dir, _ = initialize(tmp_path)
    foreign_key = ec.generate_private_key(ec.SECP256R1())
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
        .sign(foreign_key, algorithm=hashes.SHA256())
    )
    certificate_path = tmp_path / "foreign.pem"
    certificate_path.write_bytes(foreign.public_bytes(serialization.Encoding.PEM))

    with pytest.raises(ValueError, match="not issued"):
        intranet_pki.revoke(ca_dir, certificate_path, reason="key-compromise", now=now)


def test_public_pilot_evidence_is_redacted_and_bound_to_the_tooling():
    evidence_path = (
        REPO_ROOT
        / "docs"
        / "vault"
        / "30_Development"
        / "Evidence"
        / "card150-intranet-pki-lan-pilot.json"
    )
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    serialized = json.dumps(evidence, sort_keys=True).lower()

    assert not re.search(
        r"\b(?:10|192\.168|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}\b", serialized
    )
    assert ".sv.lan" not in serialized
    assert "nod_" not in serialized
    assert "fingerprint" not in serialized
    assert evidence["pki"]["https"]["rootOffline"] is False
    assert evidence["pki"]["https"]["publicKeyAlgorithm"] == "ECDSA-P256"
    assert evidence["databaseBoundary"]["pilotStateRebound"] is False

    for relative_path, expected in evidence["source"]["toolSHA256"].items():
        actual = hashlib.sha256((REPO_ROOT / relative_path).read_bytes()).hexdigest()
        assert actual == expected
