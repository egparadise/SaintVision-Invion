"""Validate portable image content and preserve identity across installer retries."""
import json
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
        files[name] = path.read_bytes()
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


def install_files(container, directory):
    archive, files = credential_archive(directory)
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
