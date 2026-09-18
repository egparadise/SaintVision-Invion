"""Pinned ZIP bytes and metadata do not prove a remote installation or mTLS."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys
from zipfile import ZipFile

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.x509.oid import NameOID

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from check_workspace_package import INSTALLERS, inspect_package, archive_checksums

NOW = datetime(2026, 9, 18, tzinfo=timezone.utc)


@pytest.fixture
def package(tmp_path):
    state, source = tmp_path / 'state', tmp_path / 'source'
    (state / 'public').mkdir(parents=True)
    (source / 'deploy/lan').mkdir(parents=True)
    identity = dict(tenantId='synthetic-tenant', nodeId='synthetic-node',
                    epoch='synthetic-epoch', nodeIP='192.0.2.1', nodePort=18443)
    policy = dict(tenantId=identity['tenantId'], nodeId=identity['nodeId'],
                  recoveryEpoch=identity['epoch'], expiresAt='2026-09-19T00:00:00Z',
                  clientFingerprints=['a' * 64])
    key = Ed25519PrivateKey.generate()
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'synthetic-only')])
    cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(NOW - timedelta(days=1)).not_valid_after(NOW + timedelta(days=1))
            .sign(key, None).public_bytes(serialization.Encoding.PEM))
    (state / 'public/node-cert.pem').write_bytes(cert)
    scripts = {name: b'synthetic installer ' + name.encode() for name in INSTALLERS}
    for name, content in scripts.items():
        (source / 'deploy/lan' / name).write_bytes(content)
    image = dict(agentImage='sha256:' + 'b' * 64, archiveSHA256='c' * 64)
    manifest = dict(identity, schemaVersion=1, scope='workspace-node-acceptance',
                    profile='lan-workspace-v1', packageDirty=False,
                    certificateSHA256=hashlib.sha256(cert).hexdigest(),
                    installerHashes={n: hashlib.sha256(b).hexdigest() for n, b in scripts.items()},
                    agent=image, workload=image)

    def write(*, duplicate=False, malformed=False):
        policy_bytes = json.dumps(policy).encode()
        (state / 'peer-policy.json').write_bytes(policy_bytes)
        path = state / 'public/workspace-worker.zip'
        with ZipFile(path, 'w') as archive:
            archive.writestr('manifest.json', b'SYNTHETIC_SECRET_INVALID_JSON' if malformed else json.dumps(manifest).encode())
            archive.writestr('peer-policy.json', policy_bytes)
            for name, content in scripts.items():
                archive.writestr(name, content)
            for name in ('node-agent.tar', 'workspace-image.tar'):
                archive.writestr(name, b'not an image; metadata cannot prove contents')
            if duplicate:
                with pytest.warns(UserWarning, match='Duplicate name'):
                    archive.writestr('manifest.json', json.dumps(manifest))
        (state / 'public/workspace-worker.sha256').write_text(hashlib.sha256(path.read_bytes()).hexdigest())

    write()
    return state, source, identity, manifest, policy, write


def inspect(package):
    state, source, identity, *_ = package
    return inspect_package(state, identity, source_root=source, now=NOW)


def test_matching_metadata_never_certifies_remote_or_image_contents(package):
    report = inspect(package)
    assert report['metadataConsistent'] is True
    for name in ('imageContentsVerified', 'installationVerified', 'mtlsVerified', 'executionAuthorized'):
        assert report[name] is False


@pytest.mark.parametrize('field,value,failed', [
    ('profile', 'lan-observe-v1', 'packageScope'),
    ('packageDirty', True, 'packageScope'),
    ('nodeId', 'SYNTHETIC_SECRET_OTHER_NODE', 'identity'),
    ('epoch', 'other-epoch', 'identity'),
    ('certificateSHA256', '0' * 64, 'certificateBinding'),
])
def test_stale_or_different_target_is_blocked_without_echo(package, field, value, failed):
    package[3][field] = value
    package[5]()
    report = inspect(package)
    assert failed in report['blockers'] and not report['metadataConsistent']
    assert 'SYNTHETIC_SECRET' not in json.dumps(report)


def test_expired_policy_is_not_fresh_even_with_matching_archive(package):
    package[4]['expiresAt'] = NOW.isoformat()
    package[5]()
    report = inspect(package)
    assert report['checks']['peerPolicyBinding'] is True
    assert 'peerPolicyFresh' in report['blockers']


def test_local_policy_rotation_invalidates_old_package(package):
    (package[0] / 'peer-policy.json').write_text('SYNTHETIC_SECRET_ROTATION')
    assert 'peerPolicyBinding' in inspect(package)['blockers']


def test_repository_installer_change_invalidates_old_package(package):
    (package[1] / 'deploy/lan' / INSTALLERS[0]).write_bytes(b'new installer')
    assert 'currentInstallers' in inspect(package)['blockers']


def test_duplicate_manifest_cannot_choose_an_arbitrary_identity(package):
    package[5](duplicate=True)
    assert 'uniqueMembers' in inspect(package)['blockers']


def test_checksum_mismatch_is_rejected_before_parsing(package):
    (package[0] / 'public/workspace-worker.zip').write_bytes(b'SYNTHETIC_SECRET_BAD_ZIP')
    report = inspect(package)
    assert 'archiveChecksum' in report['blockers']
    assert 'SYNTHETIC_SECRET' not in json.dumps(report)


def test_malformed_manifest_diagnostic_is_redacted(package):
    package[5](malformed=True)
    report = inspect(package)
    assert not report['metadataConsistent'] and report['inspectionIncomplete']
    assert 'SYNTHETIC_SECRET' not in json.dumps(report)


def test_certificate_expiry_is_checked_even_if_hash_matches(package):
    state, source, identity, *_ = package
    report = inspect_package(state, identity, source_root=source, now=NOW + timedelta(days=1))
    assert report['checks']['certificateBinding']
    assert 'certificateFresh' in report['blockers']


def test_not_yet_valid_certificate_is_not_installation_evidence(package):
    state, source, identity, *_ = package
    report = inspect_package(state, identity, source_root=source, now=NOW - timedelta(days=2))
    assert 'certificateFresh' in report['blockers']


def payload_inspect(package, **kwargs):
    state, source, identity, *_ = package
    return inspect_package(state, identity, source_root=source, now=NOW,
                           verify_image_archives=True, **kwargs)


def pin_payload(package):
    # Deliberately not a Docker image: a matching file hash must not certify one.
    expected = hashlib.sha256(b'not an image; metadata cannot prove contents').hexdigest()
    package[3]['agent'] = dict(package[3]['agent'], archiveSHA256=expected)
    package[3]['workload'] = dict(package[3]['workload'], archiveSHA256=expected)
    package[5]()


def test_opt_in_detects_inner_mismatch_even_when_outer_zip_matches(package):
    assert inspect(package)['metadataConsistent']
    report = payload_inspect(package)
    assert report['metadataConsistent']
    assert not report['requestedChecksPassed']
    assert report['blockers'] == ['imageArchiveChecksums']


def test_matching_payload_hashes_never_certify_docker_image_identity(package):
    pin_payload(package)
    report = payload_inspect(package)
    assert report['requestedChecksPassed']
    assert report['imageArchiveChecksums']['verified']
    assert not report['imageArchiveChecksums']['imageIdentityVerified']
    for name in ('imageContentsVerified', 'installationVerified', 'mtlsVerified', 'executionAuthorized'):
        assert report[name] is False


@pytest.mark.parametrize('kind', ['agent', 'workload'])
def test_both_payloads_are_independently_required(package, kind):
    pin_payload(package)
    package[3][kind]['archiveSHA256'] = '0' * 64
    package[5]()
    report = payload_inspect(package)
    assert not report['imageArchiveChecksums'][kind]
    assert report['imageArchiveChecksums']['workload' if kind == 'agent' else 'agent']
    assert not report['requestedChecksPassed']


def test_combined_budget_rejects_before_reading_any_image(package, monkeypatch):
    pin_payload(package)
    with ZipFile(package[0] / 'public/workspace-worker.zip') as archive:
        monkeypatch.setattr(archive, 'open', lambda *_: pytest.fail('budget must be checked before reading'))
        one_size = archive.getinfo('node-agent.tar').file_size
        with pytest.raises(ValueError, match='budget'):
            archive_checksums(archive, package[3], one_size)


def test_budget_failure_is_fixed_diagnostic_and_keeps_authorization_false(package):
    pin_payload(package)
    report = payload_inspect(package, max_image_archive_bytes=1)
    assert report['inspectionIncomplete']
    assert report['blockers'] == ['imageArchiveChecksums']
    assert not report['requestedChecksPassed']


def test_expired_credentials_still_block_with_matching_payloads(package):
    pin_payload(package)
    package[4]['expiresAt'] = NOW.isoformat()
    package[5]()
    report = payload_inspect(package)
    assert report['imageArchiveChecksums']['verified']
    assert 'peerPolicyFresh' in report['blockers']
    assert not report['requestedChecksPassed']
