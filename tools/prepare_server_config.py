"""Copy explicitly referenced server credentials into a NEW private Linux volume.

Never updates an existing volume or starts a server. Secret bytes travel on stdin.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import stat
import subprocess
from uuid import uuid4


def docker(*args, payload=None):
    result = subprocess.run(["docker", *args], input=payload, capture_output=True,
                            text=True, timeout=90)
    if result.returncode:
        raise RuntimeError("Configuration volume operation failed; diagnostics suppressed")
    return result.stdout.strip()


def read_regular(path):
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            or getattr(info, "st_file_attributes", 0) & 0x400
            or info.st_size > 65536):
        raise ValueError("Bounded regular configuration files required")
    return path.read_bytes()


def collect(directory):
    directory = Path(directory)
    info = directory.lstat()
    if not stat.S_ISDIR(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise ValueError("Regular configuration directory required")
    files = {"api.json": read_regular(directory / "api.json")}
    config = json.loads(files["api.json"])
    names = {"api.json"}
    private = set()

    def reference(value, *, secret=False):
        if not isinstance(value, str) or not re.fullmatch(r"/run/saintvision/[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", value):
            raise ValueError("Configuration references must be flat /run/saintvision paths")
        name = value.rsplit("/", 1)[1]
        if name == "api.json":
            raise ValueError("Credential reference aliases the configuration")
        names.add(name)
        if secret:
            private.add(name)

    reference(config["identity"]["jwks_file"])
    workspace = config.get("workspace")
    if workspace is not None:
        targets = [workspace, *workspace.get("destinations", [])]
        if len(targets) > 5:
            raise ValueError("At most five Workspace configurations")
        for target in targets:
            reference(target["signingKeyFile"], secret=True)
            for name in ("ca_file", "certificate_file", "key_file"):
                reference(target["tls"][name], secret=name == "key_file")
    for name in sorted(names - {"api.json"}):
        files[name] = read_regular(directory / name)
    return files, private


WRITE = r'''
import base64,hashlib,json,os,sys
from pathlib import Path
data=json.load(sys.stdin); root=Path('/config')
if list(root.iterdir()): raise ValueError('New empty volume required')
os.chown(root,65532,65532); os.chmod(root,0o700)
for name,value in data.items():
    raw=base64.b64decode(value,validate=True)
    p=root/name
    with p.open('xb') as f:
        os.chmod(p,0o600); f.write(raw); f.flush(); os.fsync(f.fileno())
    os.chown(p,65532,65532)
fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY); os.fsync(fd); os.close(fd)
'''

VERIFY = r'''
import hashlib,json,os,sys
from pathlib import Path
from inv.identity import AccessTokens,trusted_file,strict_object
from inv.node_transport import private_key
data=json.load(sys.stdin); root=Path('/run/saintvision')
assert os.geteuid()==65532
for name,digest in data['hashes'].items():
    p=root/name; s=p.stat()
    assert s.st_uid==65532 and s.st_mode&0o777==0o600
    assert hashlib.sha256(p.read_bytes()).hexdigest()==digest
for name in data['private']: private_key(root/name)
config=strict_object(trusted_file(root/'api.json'))
AccessTokens(**config['identity'])._keys()
'''


def prepare(directory, volume, image):
    if not re.fullmatch(r"[a-z][a-z0-9_-]{2,90}", volume):
        raise ValueError("Explicit bounded volume name required")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
        raise ValueError("Pinned local candidate image ID required")
    files, private = collect(directory)
    if volume in docker("volume", "ls", "--format", "{{.Name}}").splitlines():
        raise ValueError("Existing volume must never be overwritten")
    label = uuid4().hex
    docker("volume", "create", "--label", "ai.saintvision.config=" + label, volume)
    owned = docker("volume", "inspect", "--format", '{{index .Labels "ai.saintvision.config"}}', volume) == label
    if not owned:
        raise ValueError("Volume was concurrently created by another owner")
    hashes = {name: hashlib.sha256(raw).hexdigest() for name, raw in files.items()}
    try:
        docker("run", "--rm", "-i", "--network", "none", "--user", "0:0", "--mount",
               f"type=volume,source={volume},target=/config,volume-nocopy", image, "python", "-c", WRITE,
               payload=json.dumps({n: base64.b64encode(b).decode() for n, b in files.items()}))
        docker("run", "--rm", "-i", "--network", "none", "--read-only", "--user", "65532:65532",
               "--mount", f"type=volume,source={volume},target=/run/saintvision,readonly",
               image, "python", "-c", VERIFY, payload=json.dumps({"hashes": hashes, "private": sorted(private)}))
    except Exception:
        if docker("volume", "inspect", "--format", '{{index .Labels "ai.saintvision.config"}}', volume) == label:
            docker("volume", "rm", volume)
        raise
    # Do not publish private credential hashes or file contents.
    return {"volume": volume, "imageId": image, "filesVerified": len(files),
            "uid": 65532, "mode": "0600", "serverStarted": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", required=True)
    parser.add_argument("--volume", required=True)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(prepare(args.directory, args.volume, args.image)))
    except Exception:
        raise SystemExit("Configuration preparation rejected; existing volumes and source files preserved")
