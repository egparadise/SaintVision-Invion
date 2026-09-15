"""Upgrade one owned, idle Node without replacing its identity or journal."""
import argparse
from copy import deepcopy
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from uuid import uuid4

from worker_config import same_identity, image_id, repair_target, install_files, check_running, credential_archive

PROFILE = 'lan-workspace-v1'
EXECUTABLE = '/usr/local/bin/python3'


def docker(*args, timeout=30):
    result = subprocess.run(['docker', *map(str, args)], capture_output=True, timeout=timeout)
    if result.returncode:
        raise ValueError('Docker '+str(args[0])+' failed; exit '+str(result.returncode)+'; existing state preserved')
    return result.stdout


def inspect(name):
    result = subprocess.run(['docker', 'container', 'inspect', name], capture_output=True, timeout=15)
    if result.returncode:
        if b'No such' in result.stderr:
            return None
        raise ValueError('Docker inspection unavailable; no installation change permitted')
    return json.loads(result.stdout)[0]


def atomic(path, value):
    temporary = path.with_suffix('.tmp')
    with temporary.open('w', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


@contextmanager
def exclusive_lock(path):
    import fcntl
    with path.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def validate_target(manifest, value):
    if value is None:
        raise ValueError('Existing Node container is required')
    # repair_target also checks all durable identity arguments and /state mount.
    # This call checks configuration before stopping; actual state is checked later.
    static = deepcopy(value)
    static['State'] = dict(Status='exited', Running=False, Restarting=False)
    repair_target(manifest, static)
    args = value['Config']['Cmd']
    for flag in ('--profile', '--image', '--executable'):
        if args.count(flag) != 1 or not args[args.index(flag)+1:args.index(flag)+2]:
            raise ValueError('Ambiguous Node configuration: '+flag)
    if args[args.index('--profile')+1] not in ('lan-observe-v1', 'lan-test-v1', PROFILE):
        raise ValueError('Unknown existing profile; explicit migration required')
    return list(args)


def idle(node):
    # Even a stopped but uncollected workload is not safe to discard or migrate.
    if docker('ps', '-aq', '--filter', 'label=ai.saintvision.node='+node,
              '--filter', 'label=ai.saintvision.command').strip():
        raise ValueError('Node has an owned workload; finish cancellation/recovery before upgrade')


def verify_credentials(folder, state):
    _, files = credential_archive(state)
    manifest = json.loads((folder/'manifest.json').read_text('utf-8'))
    if hashlib.sha256(files['node-cert.pem']).hexdigest() != manifest['certificateSHA256']:
        raise ValueError('Existing Node certificate differs from the assigned public certificate')
    for name in ('ca.pem', 'signer.pub', 'peer-policy.json'):
        if (folder/name).read_bytes() != files[name]:
            raise ValueError('Existing trust material differs: '+name+'; no rotation performed')
    commands = [
        ['openssl', 'verify', '-CAfile', str(state/'ca.pem'), '-purpose', 'sslserver', str(state/'node-cert.pem')],
        ['openssl', 'x509', '-in', str(state/'node-cert.pem'), '-checkend', '600', '-noout'],
    ]
    for cmd in commands:
        if subprocess.run(cmd, capture_output=True, timeout=15).returncode:
            raise ValueError('Existing Node certificate is invalid or expires within ten minutes')
    key = subprocess.run(['openssl', 'pkey', '-in', str(state/'node-key.pem'), '-pubout'], capture_output=True, timeout=15, check=True).stdout
    cert = subprocess.run(['openssl', 'x509', '-in', str(state/'node-cert.pem'), '-pubkey', '-noout'], capture_output=True, timeout=15, check=True).stdout
    if key != cert:
        raise ValueError('Existing private key and certificate differ')


def load_image(folder, spec, archive):
    path = folder/archive
    if path.is_symlink() or not path.is_file():
        raise ValueError('Missing image archive')
    with path.open('rb') as stream:
        actual = hashlib.file_digest(stream, 'sha256').hexdigest() if hasattr(hashlib, 'file_digest') else None
    if actual is None:
        hasher = hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024*1024), b''):
                hasher.update(block)
        actual = hasher.hexdigest()
    if actual != spec['archiveSHA256']:
        raise ValueError('Image archive checksum differs')
    docker('load', '-i', path, timeout=180)
    return image_id(spec, json.loads(docker('image', 'inspect', spec['agentTag']))[0])


def rollback(manifest, state, record):
    name = 'saintvision-'+manifest['nodeId'].lower()
    if record.get('phase') == 'ready':
        raise ValueError('Successful upgrade may contain new work; automatic downgrade is refused')
    idle(manifest['nodeId'])
    backup = inspect(record['backup'])
    current = inspect(name)
    if backup is None:
        if current and current['Id'] == record['previousId']:
            docker('start', name)
            check_running(name)
            record['phase'] = 'rolled-back'
            atomic(state/'workspace-upgrade.json', record)
            return
        raise ValueError('Previous container is unavailable; preserve both containers and journal')
    previous = deepcopy(backup)
    previous['Name'] = '/'+name
    validate_target(manifest, previous)
    if backup['Id'] != record['previousId'] or backup['State']['Running']:
        raise ValueError('Rollback backup identity or state differs')
    if current:
        validate_target(manifest, current)
        if (current['Image'] != record['agentImage'] or
                current['Config']['Labels'].get('ai.saintvision.upgrade') != record['upgradeId']):
            raise ValueError('Current container is not owned by this upgrade')
        docker('stop', name)
        docker('rename', name, name+'-upgrade-failed-'+uuid4().hex[:8])
    docker('rename', record['backup'], name)
    docker('update', '--restart=unless-stopped', name)
    docker('start', name)
    check_running(name)
    record['phase'] = 'rolled-back'
    atomic(state/'workspace-upgrade.json', record)


def install(folder, state, *, undo=False):
    manifest = json.loads((folder/'manifest.json').read_text('utf-8'))
    if manifest.get('scope') != 'workspace-node-acceptance' or manifest.get('profile') != PROFILE:
        raise ValueError('Unexpected workspace installation scope')
    node = manifest['nodeId']
    if not re.fullmatch(r'nod_[0-9A-HJKMNP-TV-Z]{26}', node):
        raise ValueError('Invalid Node identity')
    if state.is_symlink() or not state.is_dir():
        raise ValueError('Existing private Node state directory is required')
    same_identity(json.loads((state/'manifest.json').read_text('utf-8')), manifest)
    with exclusive_lock(state/'workspace-upgrade.lock'):
        record_path = state/'workspace-upgrade.json'
        record = json.loads(record_path.read_text('utf-8')) if record_path.exists() else None
        if undo:
            if not record:
                raise ValueError('No recorded upgrade to roll back')
            rollback(manifest, state, record)
            return {'nodeId': node, 'status': 'rolled-back'}
        if record and record['phase'] not in ('ready', 'rolled-back'):
            raise ValueError('Interrupted upgrade preserved; run Enable-Workspace.ps1 -Rollback first')
        name = 'saintvision-'+node.lower()
        current = inspect(name)
        args = validate_target(manifest, current)
        idle(node)
        volume = json.loads(docker('volume', 'inspect', name+'-state'))[0]
        if (volume.get('Labels') or {}).get('ai.saintvision.node') != node:
            raise ValueError('Existing volume ownership differs')
        verify_credentials(folder, state)
        agent = load_image(folder, manifest['agent'], 'node-agent.tar')
        workload = load_image(folder, manifest['workload'], 'workspace-image.tar')
        desired = {'--profile': PROFILE, '--image': workload, '--executable': EXECUTABLE}
        if current['Image'] == agent and all(args[args.index(k)+1] == v for k,v in desired.items()):
            check_running(name)
        else:
            if record and record['phase'] == 'ready':
                raise ValueError('A different completed upgrade exists; explicit version migration required')
            record = dict(phase='prepared', upgradeId=uuid4().hex, previousId=current['Id'],
                          agentImage=agent, workloadImage=workload, backup=name+'-pre-workspace-'+uuid4().hex[:8])
            atomic(record_path, record)
            try:
                docker('stop', name)
                stopped = inspect(name)
                if stopped['Id'] != record['previousId']:
                    raise ValueError('Container changed during upgrade')
                repair_target(manifest, stopped)
                idle(node)
                docker('rename', name, record['backup'])
                docker('update', '--restart=no', record['backup'])
                record['phase'] = 'renamed'
                atomic(record_path, record)
                for key,value in desired.items():
                    args[args.index(key)+1] = value
                docker('create', '--name', name, '--label', 'ai.saintvision.node='+node,
                       '--label', 'ai.saintvision.upgrade='+record['upgradeId'],
                       '--restart', 'unless-stopped', '--read-only', '--cap-drop', 'ALL',
                       '--security-opt', 'no-new-privileges', '--pids-limit', '128',
                       '--memory', '256m', '--cpus', '0.5',
                       '--publish', str(manifest['nodeIP'])+':'+str(manifest['nodePort'])+':18443',
                       '--mount', 'type=volume,source='+name+'-state,target=/state',
                       '--mount', 'type=bind,source=/var/run/docker.sock,target=/var/run/docker.sock',
                       agent, *args)
                record['phase'] = 'created'
                atomic(record_path, record)
                install_files(name, state)
                docker('start', name)
                check_running(name)
                record['phase'] = 'ready'
                atomic(record_path, record)
            except (ValueError, OSError, subprocess.SubprocessError):
                rollback(manifest, state, record)
                raise
        result = dict(nodeId=node, profile=PROFILE, agentImage=agent, executionImage=workload,
                      imageCodeSHA=manifest['imageCodeSHA'], status='awaiting-server-mtls-verification',
                      workloadLimits=dict(cpuMillis=1000, memoryMiB=512, timeoutSeconds=30, network='none'),
                      identityPreserved=True, journalPreserved=True)
        atomic(state/'workspace-ready.json', result)
        print(json.dumps(result))
        return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rollback', action='store_true')
    args = parser.parse_args()
    os.umask(0o077)
    folder = Path(__file__).resolve().parent
    try:
        node = json.loads((folder/'manifest.json').read_text('utf-8'))['nodeId']
        install(folder, Path.home()/'.local/share/saintvision'/node, undo=args.rollback)
    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
        print('Workspace Node upgrade stopped: '+str(error), file=sys.stderr)
        raise SystemExit(1)
