"""Private pilot PKI. Enrollment accepts a public CSR, never a remote private key."""
from datetime import datetime, timedelta, timezone
from ipaddress import ip_address
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID


def private_pem(key):
    return key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())


def ca_pair():
    key = Ed25519PrivateKey.generate()
    now = datetime.now(timezone.utc)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'SaintVision LAN pilot CA')])
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=7))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, None, None), critical=True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(key.public_key()), critical=False)
            .sign(key, None))
    return key, cert


def issue(ca_key, ca_cert, public_key, uri, *, address=None):
    now = datetime.now(timezone.utc)
    names = [x509.UniformResourceIdentifier(uri)]
    if address is not None:
        names.append(x509.IPAddress(ip_address(address)))
    cert = (x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'SaintVision LAN peer')]))
            .issuer_name(ca_cert.subject).public_key(public_key).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=5))
            .not_valid_after(min(now + timedelta(days=6), ca_cert.not_valid_after_utc))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.KeyUsage(True, False, False, False, False, False, False, None, None), critical=True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH if address else ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(public_key), critical=False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
            .add_extension(x509.SubjectAlternativeName(names), critical=False).sign(ca_key, None))
    return cert


def csr_public_key(raw, node_id):
    if len(raw) > 16384:
        raise ValueError('CSR exceeds limit')
    csr = x509.load_pem_x509_csr(raw)
    expected = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, node_id)])
    key = csr.public_key()
    if not csr.is_signature_valid or csr.subject != expected or not isinstance(key, Ed25519PublicKey) or len(csr.extensions):
        raise ValueError('Expected a signed Ed25519 CSR for the assigned Node without extensions')
    return key


def pem(cert):
    return cert.public_bytes(serialization.Encoding.PEM)


def fingerprint(cert):
    return cert.fingerprint(hashes.SHA256()).hex()
