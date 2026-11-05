"""Validate portable image content and preserve identity across installer retries."""
import json
import hashlib
from contextlib import contextmanager
import os
import io
from pathlib import Path
import re
import stat
import subprocess
import sys
import tarfile
import time

# The independently verified bundle authorizes a software update. Its image
# digest is verified separately and is not the durable Node/epoch identity.
IDENTITY = ('nodeId','tenantId','epoch','serverIP','nodeIP','nodePort')
CONFIG = ('User','Env','Cmd','WorkingDir','Entrypoint','OnBuild','Volumes','Labels',
          'Healthcheck','StopSignal','Shell','ExposedPorts','StopTimeout')
CREDENTIAL_FILES = ('node-cert.pem','node-key.pem','ca.pem','signer.pub','peer-policy.json')
_rotation_guard_depth = {}
_settled_verifier = None  # trusted in-process leaf entry; never an argv/env bypass


def strict_json(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError('Duplicate private protocol field')
            value[key] = item
        return value
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Invalid JSON number')))


def no_migration(directory, *, leaf_observation=False):
    root = Path(directory)
    for name in ('agent-binary-migration.json', 'agent-binary-migration.json.next', 'agent-mutation-fence.json', 'agent-mutation-fence.json.next'):
        path = root / name
        if path.exists() or path.is_symlink():
            raise ValueError('A migration marker requires its separately reviewed contract')
    if leaf_observation or (root/'leaf-rotation.json').exists():
        for name in ('storage-replacement.json','storage-replacement-input'):
            path = root/name
            if path.exists() or path.is_symlink():
                raise ValueError('A pending storage migration remains blocked')
        path = root/'workspace-upgrade.json'
        if path.exists() or path.is_symlink():
            value = strict_json(path.read_bytes())
            if not isinstance(value,dict) or value.get('phase') not in ('ready','rolled-back'):
                raise ValueError('A pending workspace migration remains blocked')


def validate_topology(manifest):
    """Fail closed when CP co-location metadata disagrees with immutable addresses."""
    if manifest.get('schemaVersion') != 3:
        raise ValueError(
            'Bundle schema v3 is required; do not run new scripts from an old v2 directory')
    colocated = manifest['serverIP'] == manifest['nodeIP']
    if (type(manifest.get('coLocatedWithControlPlane')) is not bool
            or manifest['coLocatedWithControlPlane'] != colocated):
        raise ValueError('Control Plane co-location metadata differs from Node addresses')
    eligibility = manifest.get('measurementEligible')
    if not isinstance(eligibility, dict) or set(eligibility) != {'s05','s07'}:
        raise ValueError('Measurement eligibility metadata is incomplete')
    expected = False if colocated else None
    if any(eligibility.get(name) is not expected for name in ('s05','s07')):
        raise ValueError('Measurement eligibility differs from co-location policy')
    reason = manifest.get('exclusionReason')
    if reason != ('cp-host-colocation' if colocated else None):
        raise ValueError('Measurement exclusion reason differs from co-location policy')


def credential_archive(directory):
    """Use explicit container ownership without changing the host private key."""
    files = {}
    for name in CREDENTIAL_FILES:
        path = Path(directory)/name
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= 65536:
            raise ValueError('Missing or unsafe Node credential file: '+name)
        fd = os.open(path, os.O_RDONLY | getattr(os,'O_NOFOLLOW',0) | getattr(os,'O_NONBLOCK',0) | getattr(os,'O_BINARY',0))
        with os.fdopen(fd,'rb') as source:
            opened = os.fstat(source.fileno())
            if (not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1
                    or (opened.st_dev,opened.st_ino,opened.st_size) != (info.st_dev,info.st_ino,info.st_size)):
                raise ValueError('Node credential changed before read: '+name)
            raw = source.read(65537)
            after = os.fstat(source.fileno())
        named = path.lstat()
        fields = ('st_dev','st_ino','st_size','st_mode','st_uid','st_gid','st_nlink','st_mtime_ns','st_ctime_ns')
        # Windows named stat and descriptor fstat expose different ctime APIs;
        # compare ctime across descriptor reads there, and also by name on Linux.
        changed = [k for k in fields if getattr(opened,k) != getattr(after,k)
                   or (not (os.name == 'nt' and k == 'st_ctime_ns') and getattr(opened,k) != getattr(named,k))]
        if len(raw) != opened.st_size or changed:
            raise ValueError('Node credential changed during read: '+name+' ('+','.join(changed)+')')
        files[name] = raw
    if len(files['signer.pub']) != 32:
        raise ValueError('Pinned public key must contain exactly 32 bytes')
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode='w') as tar:
        for name, data in files.items():
            entry = tarfile.TarInfo(name)
            entry.size = len(data)
            entry.uid = entry.gid = 0
            entry.mode = 0o600
            tar.addfile(entry, io.BytesIO(data))
    return archive.getvalue(), files


def no_rotation_mutation(directory):
    """Legacy installers cannot resume or undo an owned leaf publication."""
    root = Path(directory)
    no_migration(root)
    for name in ('leaf-rotation.json', 'leaf-rotation.json.next', 'leaf-rotation-finalized'):
        path = root / name
        if path.exists() or path.is_symlink():
            raise ValueError('Leaf rotation state requires its exact forward-only protocol; legacy repair/upgrade/rollback is blocked')


def _settled(directory):
    if _settled_verifier is not None:
        value = _settled_verifier(Path(directory))
    else:
        launcher = Path(__file__).with_name('leaf_rotation_standalone_runtime.py')
        entry = Path(__file__).with_name('worker_leaf_rotation.py')
        runtime = Path.home()/'.local/share/saintvision/leaf-rotation-runtime'
        if not launcher.is_file() or launcher.is_symlink() or not entry.is_file() or entry.is_symlink():
            raise ValueError('The reviewed pinned five-module verifier is required')
        command = [sys.executable,'-I','-B',str(launcher),'run','--runtime-dir',str(runtime),
                   '--worker-script',str(entry),'--','verify-settled','--worker-root',str(directory)]
        result = subprocess.run(command,capture_output=True,check=True,timeout=30)
        if not 0 < len(result.stdout) <= 65536:
            raise ValueError('Settled verification result is unavailable')
        value = strict_json(result.stdout)
    if (not isinstance(value,dict) or set(value) != {'schemaVersion','verified','archiveSHA256','journalSHA256','credentialsSHA256','context','actualFinalPeerFloor'}
            or value['schemaVersion'] != 'saintvision-settled-rotation-verification:1' or value['verified'] is not True):
        raise ValueError('Settled verifier result differs')
    return value


def _stable_settled(value):
    floor = {k:v for k,v in value['actualFinalPeerFloor'].items() if k not in ('nonce','observedAt','nodeSignature')}
    return json.dumps({**value,'actualFinalPeerFloor':floor},sort_keys=True,separators=(',',':'),allow_nan=False)


@contextmanager
def rotation_mutation_guard(directory, *, action=None):
    """Serialize generic mutation with leaf publication; never steal stale intent."""
    root = Path(directory)
    key = os.path.abspath(root)
    if key in _rotation_guard_depth:
        token = _rotation_guard_depth[key]
        if token is not None and action not in ('idempotent','same-byte-copy'):
            raise ValueError('A migration cannot inherit a settled idempotent guard')
        yield token
        return
    path = root / 'leaf-rotation.lock'
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise ValueError('Another leaf rotation writer owns the Node lock; preserve state') from None
    try:
        os.close(fd)
        no_migration(root)
        token = None
        try:
            no_rotation_mutation(root)
        except ValueError:
            if action not in ('idempotent','same-byte-copy'):
                raise
            token = _settled(root)
        _rotation_guard_depth[key] = token
        yield token
        if token is not None and _stable_settled(_settled(root)) != _stable_settled(token):
            raise ValueError('Same-byte/idempotent action changed settled identity, history or ownership')
    finally:
        _rotation_guard_depth.pop(key, None)
        path.unlink(missing_ok=True)


def install_files(container, directory, *, rotation_publication=False):
    no_migration(directory)
    if rotation_publication:
        return _install_files(container, directory, rotation_publication=True)
    with rotation_mutation_guard(directory, action='same-byte-copy') as settled:
        if settled is None:
            return _install_files(container, directory)
        archive, files = credential_archive(directory)
        if {name:hashlib.sha256(raw).hexdigest() for name,raw in files.items()} != settled['credentialsSHA256']:
            raise ValueError('SF1 repair may only copy the exact settled credential bytes')
        context = settled['context']
        node = strict_json((Path(directory)/'manifest.json').read_bytes())['nodeId']
        if container not in (context['containerId'],'saintvision-'+node.lower()):
            raise ValueError('SF1 repair container differs')
        cid = context['containerId']
        subprocess.run(['docker','stop',cid],capture_output=True,check=True,timeout=60)
        _install_files(cid,directory,settled=True,frozen=(archive,files))
        subprocess.run(['docker','start',cid],capture_output=True,check=True,timeout=60)
        check_running(cid)


def _install_files(container, directory, *, rotation_publication=False, settled=False, frozen=None):
    no_migration(directory)
    if not rotation_publication and not settled:
        no_rotation_mutation(directory)
    archive, files = credential_archive(directory) if frozen is None else frozen
    if rotation_publication:
        root = Path(directory)
        record = strict_json((root / 'leaf-rotation.json').read_bytes())
        binding = record.get('peerPhaseBinding', {})
        name = {'installed': 'overlap', 'finalizing': 'final'}.get(record.get('phase'))
        policy = strict_json(files['peer-policy.json'])
        if (record.get('peerSchemaVersion') != 3 or record.get('publicationIntent') is not True
                or name is None or type(policy.get('version')) is not int
                or policy['version'] != binding.get(name+'PeerPolicyVersion')
                or hashlib.sha256(files['peer-policy.json']).hexdigest() != binding.get(name+'PeerPolicySHA256')):
            raise ValueError('Credential publication does not match the frozen forward-only phase')
    subprocess.run(['docker','cp','-a','-',container+':/state'], input=archive,
                   capture_output=True, check=True, timeout=30)
    # Keep private contents in memory; never write an archive or log its bytes.
    for name, expected in files.items():
        copied = subprocess.run(['docker','cp',container+':/state/'+name,'-'],
                                capture_output=True, check=True, timeout=30)
        with tarfile.open(fileobj=io.BytesIO(copied.stdout)) as tar:
            entries = tar.getmembers()
            if len(entries) != 1:
                raise ValueError('Unexpected copied credential archive: '+name)
            entry = entries[0]
            if (not entry.isfile() or entry.name != name or entry.uid != 0
                    or entry.gid != 0 or entry.mode & 0o7777 != 0o600
                    or entry.size != len(expected)
                    or tar.extractfile(entry).read() != expected):
                raise ValueError('Copied credential content or ownership differs: '+name)
    print('Node credential files verified: owner 0:0, permissions 600.')


def repair_target(manifest, container):
    name='saintvision-'+manifest['nodeId'].lower()
    config=container.get('Config',{})
    state=container.get('State',{})
    if (container.get('Name')!='/'+name
            or config.get('Labels',{}).get('ai.saintvision.node')!=manifest['nodeId']
            or state.get('Status') not in ('exited','created')
            or state.get('Running') or state.get('Restarting')
            or config.get('User','')!=''):
        raise ValueError('Repair requires this Node\'s stopped root-user container')
    mounts=[m for m in container.get('Mounts',[]) if m.get('Destination')=='/state']
    if (len(mounts)!=1 or mounts[0].get('Type')!='volume'
            or mounts[0].get('Name')!=name+'-state' or not mounts[0].get('RW')):
        raise ValueError('Repair state volume differs; journal preserved')
    args=config.get('Cmd',[])
    required={'--node':manifest['nodeId'],'--tenant':manifest['tenantId'],
              '--epoch':manifest['epoch'],'--state':'/state/journal',
              '--public-key':'/state/signer.pub','--tls-key':'/state/node-key.pem',
              '--tls-cert':'/state/node-cert.pem','--client-ca':'/state/ca.pem',
              '--peer-policy':'/state/peer-policy.json'}
    for flag,value in required.items():
        if args.count(flag)!=1 or args[args.index(flag)+1:args.index(flag)+2]!=[value]:
            raise ValueError('Repair container identity or file path differs: '+flag)


def check_running(container):
    baseline=None
    for attempt in range(6):
        raw=subprocess.run(['docker','inspect','--format',
                            '{{.State.Running}} {{.State.Restarting}} {{.RestartCount}}',container],
                           capture_output=True, text=True, check=True, timeout=10).stdout.strip()
        parts=raw.split()
        if baseline is None: baseline=parts
        if len(parts)!=3 or parts[:2]!=['true','false'] or parts!=baseline:
            raise ValueError('Node did not remain running; preserve its journal and inspect docker logs')
        if attempt<5: time.sleep(1)
    print('Node remained running for five seconds; server mTLS verification is still required.')


def same_identity(previous, current):
    changed = [k for k in IDENTITY if previous.get(k) != current.get(k)]
    if changed:
        raise ValueError('Existing Node identity differs: '+', '.join(changed)+'; private key and journal preserved')


def image_id(manifest, image):
    if image.get('Os') != 'linux' or image.get('Architecture') != 'amd64':
        raise ValueError('Linux amd64 image required')
    if image.get('RootFS',{}).get('Layers') != manifest['imageLayers']:
        raise ValueError('Loaded image filesystem content differs')
    for key in CONFIG:
        expected = manifest['imageConfig'].get(key)
        actual = image.get('Config',{}).get(key)
        if key in ('User','WorkingDir'):
            expected = '' if expected is None else expected
            actual = '' if actual is None else actual
        if key in ('Cmd','OnBuild','Volumes','Labels'):
            expected, actual = expected or None, actual or None
        if actual != expected:
            raise ValueError('Loaded image execution configuration differs: '+key)
    identifier = image.get('Id','')
    if not re.fullmatch(r'sha256:[0-9a-f]{64}',identifier):
        raise ValueError('Loaded image has no content identifier')
    return identifier


if __name__ == '__main__':
    try:
        if sys.argv[1]=='install-files':
            install_files(sys.argv[2], sys.argv[3])
            raise SystemExit(0)
        if sys.argv[1]=='check-running':
            check_running(sys.argv[2])
            raise SystemExit(0)
        first=json.loads(Path(sys.argv[2]).read_text())
        if sys.argv[1]=='topology':
            validate_topology(first)
            raise SystemExit(0)
        second=json.loads(Path(sys.argv[3]).read_text())
        if sys.argv[1]=='identity':
            same_identity(first,second)
        elif sys.argv[1]=='image':
            print(image_id(first,second[0]))
        elif sys.argv[1]=='repair-target':
            repair_target(first,second[0])
        else:
            raise ValueError('Unknown operation')
    except (ValueError,KeyError,IndexError,OSError,tarfile.TarError,subprocess.SubprocessError) as error:
        print('Node configuration rejected: '+str(error),file=sys.stderr)
        raise SystemExit(1)
