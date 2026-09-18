"""Offline metadata inspection of an enrolled Node's existing Workspace package.

Never installs, contacts a Node, changes identity, or certifies image contents/mTLS.
Only fixed diagnostic keys are emitted; package-controlled values are not echoed.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from zipfile import ZipFile
from cryptography import x509

ROOT = Path(__file__).resolve().parents[1]
INSTALLERS = ('worker_config.py', 'worker_workspace.py', 'Enable-Workspace.ps1')
CHECKS = ('archiveChecksum', 'uniqueMembers', 'packageScope', 'identity',
          'certificateBinding', 'certificateFresh', 'peerPolicyBinding', 'peerPolicyFresh',
          'currentInstallers', 'imageMetadata')


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def bounded(archive, name, limit):
    info = archive.getinfo(name)
    if info.is_dir() or not 0 < info.file_size <= limit:
        raise ValueError('Invalid member size')
    with archive.open(info) as stream:
        body = stream.read(limit + 1)
    if len(body) > limit:
        raise ValueError('Oversized member')
    return body


def inspect_package(state_path, identity, *, source_root=ROOT, now=None):
    now = now or datetime.now(timezone.utc)
    report = {'scope': 'offline-package-metadata-only',
              'checks': {name: False for name in CHECKS},
              'imageContentsVerified': False, 'installationVerified': False,
              'mtlsVerified': False, 'executionAuthorized': False}
    checks = report['checks']
    public = state_path / 'public'
    try:
        package = public / 'workspace-worker.zip'
        expected = (public / 'workspace-worker.sha256').read_text('ascii').strip()
        checks['archiveChecksum'] = bool(re.fullmatch('[0-9a-f]{64}', expected)) and digest(package) == expected
        if not checks['archiveChecksum']:
            raise ValueError('Unpinned archive')
        with ZipFile(package) as archive:
            names = archive.namelist()
            checks['uniqueMembers'] = len(names) <= 64 and len(names) == len(set(names))
            if not checks['uniqueMembers']:
                raise ValueError('Ambiguous members')
            manifest = json.loads(bounded(archive, 'manifest.json', 262144))
            checks['packageScope'] = (manifest.get('schemaVersion') == 1
                and manifest.get('scope') == 'workspace-node-acceptance'
                and manifest.get('profile') == 'lan-workspace-v1'
                and manifest.get('packageDirty') is False)
            fields = ('tenantId', 'nodeId', 'epoch', 'nodeIP', 'nodePort')
            checks['identity'] = all(identity.get(k) is not None and manifest.get(k) == identity[k] for k in fields)
            checks['certificateBinding'] = manifest.get('certificateSHA256') == digest(public / 'node-cert.pem')
            certificate = x509.load_pem_x509_certificate((public / 'node-cert.pem').read_bytes())
            checks['certificateFresh'] = certificate.not_valid_before_utc <= now < certificate.not_valid_after_utc
            policy_raw = bounded(archive, 'peer-policy.json', 65536)
            checks['peerPolicyBinding'] = hashlib.sha256(policy_raw).hexdigest() == digest(state_path / 'peer-policy.json')
            policy = json.loads(policy_raw)
            expires = datetime.fromisoformat(policy['expiresAt'].replace('Z', '+00:00'))
            checks['peerPolicyFresh'] = (expires.tzinfo is not None and expires > now
                and policy.get('tenantId') == identity['tenantId']
                and policy.get('nodeId') == identity['nodeId']
                and policy.get('recoveryEpoch') == identity['epoch']
                and isinstance(policy.get('clientFingerprints'), list)
                and 0 < len(policy['clientFingerprints']) <= 64
                and all(isinstance(x, str) and re.fullmatch('[0-9a-f]{64}', x)
                        for x in policy['clientFingerprints']))
            checks['currentInstallers'] = all(
                hashlib.sha256(bounded(archive, name, 1048576)).hexdigest()
                == manifest['installerHashes'].get(name)
                == digest(source_root / 'deploy' / 'lan' / name)
                for name in INSTALLERS)
            checks['imageMetadata'] = all(
                isinstance(manifest.get(kind), dict)
                and isinstance(manifest[kind].get('agentImage'), str)
                and re.fullmatch('sha256:[0-9a-f]{64}', manifest[kind]['agentImage']) is not None
                and isinstance(manifest[kind].get('archiveSHA256'), str)
                and re.fullmatch('[0-9a-f]{64}', manifest[kind]['archiveSHA256']) is not None
                and filename in names
                for kind, filename in [('agent', 'node-agent.tar'), ('workload', 'workspace-image.tar')])
    except Exception:
        # ZIP, JSON, filesystem and parser diagnostics may contain private inputs.
        report['inspectionIncomplete'] = True
    report['metadataConsistent'] = all(checks.values())
    report['blockers'] = [name for name, passed in checks.items() if not passed]
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        from lan_pilot import load
        report = inspect_package(args.state, load(args.state))
        args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    except Exception:
        print('Offline package inspection unavailable; no installation verified.')
        return 2
    print(json.dumps(report))
    return 0 if report['metadataConsistent'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
