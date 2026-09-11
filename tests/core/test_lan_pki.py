"""Enrollment must prove the assigned key and must not copy CSR authority claims."""
from pathlib import Path
import sys
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from lan_pki import ca_pair, csr_public_key, issue

NODE = 'nod_01K00000000000000000000000'


def request(key, name=NODE, *, extension=False):
    builder = x509.CertificateSigningRequestBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,name)]))
    if extension:
        builder = builder.add_extension(x509.BasicConstraints(ca=True,path_length=None),critical=True)
    return builder.sign(key,hashes.SHA256() if isinstance(key,rsa.RSAPrivateKey) else None).public_bytes(serialization.Encoding.PEM)


def test_worker_keeps_private_key_and_operator_accepts_only_its_public_csr():
    key = ed25519.Ed25519PrivateKey.generate()
    assert csr_public_key(request(key),NODE).public_bytes_raw() == key.public_key().public_bytes_raw()


@pytest.mark.parametrize('fault',['wrong-node','requested-ca','wrong-key-type','damaged-signature','oversized'])
def test_rejects_unassigned_or_unsafe_certificate_request(fault):
    key = ed25519.Ed25519PrivateKey.generate()
    if fault == 'wrong-node':
        raw = request(key,'another-node')
    elif fault == 'requested-ca':
        raw = request(key,extension=True)
    elif fault == 'wrong-key-type':
        raw = request(rsa.generate_private_key(public_exponent=65537,key_size=2048))
    elif fault == 'damaged-signature':
        csr = x509.load_pem_x509_csr(request(key))
        der = bytearray(csr.public_bytes(serialization.Encoding.DER))
        der[-1] ^= 1
        raw = x509.load_der_x509_csr(bytes(der)).public_bytes(serialization.Encoding.PEM)
    else:
        raw = b'x'*16385
    with pytest.raises(ValueError):
        csr_public_key(raw,NODE)


def test_issued_certificate_has_only_operator_selected_identity_and_server_usage():
    ca_key, ca = ca_pair()
    key = ed25519.Ed25519PrivateKey.generate()
    uri = 'spiffe://saintvision.ai/tenant/pilot/node/assigned/epoch/current'
    cert = issue(ca_key,ca,key.public_key(),uri,address='192.168.45.225')
    ca.public_key().verify(cert.signature,cert.tbs_certificate_bytes)
    san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    assert san.get_values_for_type(x509.UniformResourceIdentifier) == [uri]
    assert str(san.get_values_for_type(x509.IPAddress)[0]) == '192.168.45.225'
    assert not cert.extensions.get_extension_for_class(x509.BasicConstraints).value.ca
    assert list(cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value) == [ExtendedKeyUsageOID.SERVER_AUTH]
    assert cert.not_valid_after_utc <= ca.not_valid_after_utc


def test_generated_pki_passes_strict_tls_verification_in_both_directions(tmp_path):
    import socket
    import ssl
    from concurrent.futures import ThreadPoolExecutor
    from lan_pki import pem, private_pem
    from inv.node_transport import NodeTLSClient
    ca_key, ca = ca_pair()
    server_key, client_key = ed25519.Ed25519PrivateKey.generate(), ed25519.Ed25519PrivateKey.generate()
    server_cert = issue(ca_key, ca, server_key.public_key(), 'spiffe://pilot/server', address='127.0.0.1')
    client_cert = issue(ca_key, ca, client_key.public_key(), 'spiffe://pilot/client')
    for name, data in [('ca.pem',pem(ca)),('server.pem',pem(server_cert)),('server.key',private_pem(server_key)),
                       ('client.pem',pem(client_cert)),('client.key',private_pem(client_key))]:
        (tmp_path/name).write_bytes(data)
        (tmp_path/name).chmod(0o600)
    server = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server.load_cert_chain(tmp_path/'server.pem', tmp_path/'server.key')
    server.load_verify_locations(cafile=str(tmp_path/'ca.pem'))
    server.verify_mode = ssl.CERT_REQUIRED
    server.verify_flags |= ssl.VERIFY_X509_STRICT
    server.minimum_version = ssl.TLSVersion.TLSv1_3
    client = NodeTLSClient(ca_file=tmp_path/'ca.pem', certificate_file=tmp_path/'client.pem', key_file=tmp_path/'client.key')
    with socket.socket() as listener:
        listener.bind(('127.0.0.1',0))
        listener.listen(1)
        listener.settimeout(5)
        def accept():
            peer, _ = listener.accept()
            peer.settimeout(5)
            with server.wrap_socket(peer,server_side=True) as tls_peer:
                tls_peer.sendall(b'verified')
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(accept)
            with socket.create_connection(listener.getsockname(),timeout=5) as peer:
                with client.context.wrap_socket(peer,server_hostname='127.0.0.1') as tls_peer:
                    assert tls_peer.recv(32) == b'verified'
            future.result(timeout=5)
