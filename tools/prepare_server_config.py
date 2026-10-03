"""Copy API and worker credentials into separate NEW private Linux volumes.

Never updates an existing volume or starts a server. Secret bytes travel on stdin.
Worker configuration requires --worker-volume and may reference only its worker root.
"""

import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import stat
import subprocess
from uuid import UUID, uuid4

WORKER_KEYS = {"tenantId", "tls", "outputRoot", "buildExecution"}
TLS_KEYS = {"ca_file", "certificate_file", "key_file", "timeout"}
BUILD_EXECUTION_KEYS = {
    "buildctlPath",
    "address",
    "sourceRoot",
    "referenceHealthReceipt",
    "productReceiptDirectory",
    "builderInstanceId",
    "builderProfileId",
    "providerRecoveryEpoch",
    "nodeId",
}
BUILD_PLAN_AUTHORITY_KEYS = BUILD_EXECUTION_KEYS - {"productReceiptDirectory"}
API_ROOT = "/run/saintvision"
WORKER_ROOT = "/run/saintvision-worker"


def strict_json(raw):
    def object_pairs(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("Duplicate configuration key")
            value[key] = item
        return value

    return json.loads(raw, object_pairs_hook=object_pairs)


def docker(*args, payload=None):
    result = subprocess.run(
        ["docker", *args], input=payload, capture_output=True, text=True, timeout=90
    )
    if result.returncode:
        raise RuntimeError("Configuration volume operation failed; diagnostics suppressed")
    return result.stdout.strip()


def read_regular(path):
    info = path.lstat()
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_nlink != 1
        or getattr(info, "st_file_attributes", 0) & 0x400
        or info.st_size > 65536
    ):
        raise ValueError("Bounded regular configuration files required")
    return path.read_bytes()


def collect(directory):
    directory = Path(directory)
    info = directory.lstat()
    if not stat.S_ISDIR(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise ValueError("Regular configuration directory required")
    api_files = {"api.json": read_regular(directory / "api.json")}
    config = strict_json(api_files["api.json"])
    api_names = {"api.json"}
    api_private = set()
    worker_files = {}
    worker_names = set()
    worker_private = set()

    def reference(value, *, root, names, private, secret=False):
        if not isinstance(value, str) or not re.fullmatch(
            re.escape(root) + r"/[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", value
        ):
            raise ValueError(f"Configuration references must be flat {root} paths")
        name = value.rsplit("/", 1)[1]
        if name in {"api.json", "worker.json"}:
            raise ValueError("Credential reference aliases the configuration")
        names.add(name)
        if secret:
            private.add(name)

    def api_reference(value, *, secret=False):
        reference(
            value,
            root=API_ROOT,
            names=api_names,
            private=api_private,
            secret=secret,
        )

    def worker_reference(value, *, secret=False):
        reference(
            value,
            root=WORKER_ROOT,
            names=worker_names,
            private=worker_private,
            secret=secret,
        )

    api_reference(config["identity"]["jwks_file"])
    readiness = config.get("configurationReadiness")
    if readiness is not None:
        if not isinstance(readiness, dict) or set(readiness) - {
            "nodeMtlsCaBundle",
            "objectStoreEndpoint",
            "objectStore",
        }:
            raise ValueError("Invalid configurationReadiness settings")
        if "objectStoreEndpoint" in readiness and "objectStore" in readiness:
            raise ValueError("Duplicate legacy and objectStore settings")
        if "nodeMtlsCaBundle" in readiness:
            api_reference(readiness["nodeMtlsCaBundle"])
        if "objectStore" in readiness:
            object_store = readiness["objectStore"]
            if not isinstance(object_store, dict) or set(object_store) != {
                "providerId",
                "endpoint",
                "bucket",
                "region",
                "credentialFile",
                "prefix",
            }:
                raise ValueError("Invalid objectStore settings")
            api_reference(object_store["credentialFile"], secret=True)
    plan_authority = config.get("buildPlanAuthority")
    if plan_authority is not None and (
        not isinstance(plan_authority, dict)
        or set(plan_authority) != BUILD_PLAN_AUTHORITY_KEYS
        or any(
            not isinstance(plan_authority[name], str) or not plan_authority[name]
            for name in BUILD_PLAN_AUTHORITY_KEYS - {"providerRecoveryEpoch"}
        )
        or type(plan_authority["providerRecoveryEpoch"]) is not int
        or plan_authority["providerRecoveryEpoch"] < 1
    ):
        raise ValueError("Invalid API build plan authority configuration")
    workspace = config.get("workspace")
    if workspace is not None:
        targets = [workspace, *workspace.get("destinations", [])]
        if len(targets) > 5:
            raise ValueError("At most five Workspace configurations")
        for target in targets:
            api_reference(target["signingKeyFile"], secret=True)
            for name in ("ca_file", "certificate_file", "key_file"):
                api_reference(target["tls"][name], secret=name == "key_file")
    worker_path = directory / "worker.json"
    if worker_path.exists():
        worker_files["worker.json"] = read_regular(worker_path)
        worker_names.add("worker.json")
        worker = strict_json(worker_files["worker.json"])
        if (
            not isinstance(worker, dict)
            or not {"tenantId", "tls"} <= set(worker)
            or set(worker) - WORKER_KEYS
            or not isinstance(worker["tenantId"], str)
            or not isinstance(worker["tls"], dict)
        ):
            raise ValueError("Invalid worker configuration")
        try:
            if str(UUID(worker["tenantId"])) != worker["tenantId"]:
                raise ValueError("Invalid worker tenantId")
        except (ValueError, AttributeError):
            raise ValueError("Invalid worker tenantId") from None
        tls = worker["tls"]
        if not {"ca_file", "certificate_file", "key_file"} <= set(tls) or set(tls) - TLS_KEYS:
            raise ValueError("Invalid worker TLS configuration")
        if "timeout" in tls and (
            type(tls["timeout"]) not in (int, float) or not 0.1 <= tls["timeout"] <= 40
        ):
            raise ValueError("Invalid worker TLS timeout")
        for name in ("ca_file", "certificate_file", "key_file"):
            worker_reference(tls[name], secret=name == "key_file")
        if "outputRoot" in worker and (
            not isinstance(worker["outputRoot"], str) or not worker["outputRoot"]
        ):
            raise ValueError("Invalid worker outputRoot")
        if "buildExecution" in worker:
            build = worker["buildExecution"]
            if (
                not isinstance(build, dict)
                or set(build) != BUILD_EXECUTION_KEYS
                or any(
                    not isinstance(build[name], str) or not build[name]
                    for name in BUILD_EXECUTION_KEYS - {"providerRecoveryEpoch"}
                )
                or type(build["providerRecoveryEpoch"]) is not int
                or build["providerRecoveryEpoch"] < 1
            ):
                raise ValueError("Invalid build execution configuration")
    overlap = api_names & worker_names
    if overlap:
        raise ValueError("API and worker configuration references must use distinct files")
    for name in sorted(api_names - {"api.json"}):
        api_files[name] = read_regular(directory / name)
    for name in sorted(worker_names - {"worker.json"}):
        worker_files[name] = read_regular(directory / name)
    return api_files, api_private, worker_files, worker_private


WRITE = r"""
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
"""

VERIFY_API = r"""
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
assert not (root/'worker.json').exists()
config=strict_object(trusted_file(root/'api.json'))
AccessTokens(**config['identity'])._keys()
"""


VERIFY_WORKER = r"""
import hashlib,json,os,sys
from pathlib import Path
from inv.identity import trusted_file
from inv.node_transport import NodeTLSClient,private_key
from inv.worker import validated_worker_configuration
data=json.load(sys.stdin); root=Path('/run/saintvision-worker')
assert os.geteuid()==65532
for name,digest in data['hashes'].items():
    p=root/name; s=p.stat()
    assert s.st_uid==65532 and s.st_mode&0o777==0o600
    assert hashlib.sha256(p.read_bytes()).hexdigest()==digest
for name in data['private']: private_key(root/name)
assert not (root/'api.json').exists()
worker_config=validated_worker_configuration(trusted_file(root/'worker.json'))
NodeTLSClient(**worker_config['tls'])
"""


def _volume_name(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{2,90}", value):
        raise ValueError("Explicit bounded volume name required")
    return value


def _write_and_verify(volume, image, files, private, *, target, verify):
    hashes = {name: hashlib.sha256(raw).hexdigest() for name, raw in files.items()}
    docker(
        "run",
        "--rm",
        "-i",
        "--network",
        "none",
        "--user",
        "0:0",
        "--mount",
        f"type=volume,source={volume},target=/config,volume-nocopy",
        image,
        "python",
        "-c",
        WRITE,
        payload=json.dumps({n: base64.b64encode(b).decode() for n, b in files.items()}),
    )
    docker(
        "run",
        "--rm",
        "-i",
        "--network",
        "none",
        "--read-only",
        "--user",
        "65532:65532",
        "--mount",
        f"type=volume,source={volume},target={target},readonly",
        image,
        "python",
        "-c",
        verify,
        payload=json.dumps({"hashes": hashes, "private": sorted(private)}),
    )


def prepare(directory, volume, image, worker_volume=None):
    volume = _volume_name(volume)
    if worker_volume is not None:
        worker_volume = _volume_name(worker_volume)
        if worker_volume == volume:
            raise ValueError("API and worker configuration volumes must differ")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
        raise ValueError("Pinned local candidate image ID required")
    api_files, api_private, worker_files, worker_private = collect(directory)
    if worker_files and worker_volume is None:
        raise ValueError("Separate worker configuration volume required")
    if not worker_files and worker_volume is not None:
        raise ValueError("Worker configuration required for a worker volume")
    plans = [
        (volume, api_files, api_private, API_ROOT, VERIFY_API),
    ]
    if worker_volume is not None:
        plans.append(
            (
                worker_volume,
                worker_files,
                worker_private,
                WORKER_ROOT,
                VERIFY_WORKER,
            )
        )
    existing = set(docker("volume", "ls", "--format", "{{.Name}}").splitlines())
    if any(name in existing for name, *_ in plans):
        raise ValueError("Existing volume must never be overwritten")
    label = uuid4().hex
    created = []
    try:
        for name, files, private, target, verify in plans:
            docker(
                "volume",
                "create",
                "--label",
                "ai.saintvision.config=" + label,
                name,
            )
            owned = (
                docker(
                    "volume",
                    "inspect",
                    "--format",
                    '{{index .Labels "ai.saintvision.config"}}',
                    name,
                )
                == label
            )
            if not owned:
                raise ValueError("Volume was concurrently created by another owner")
            created.append(name)
            _write_and_verify(
                name,
                image,
                files,
                private,
                target=target,
                verify=verify,
            )
    except Exception:
        for name in reversed(created):
            if (
                docker(
                    "volume",
                    "inspect",
                    "--format",
                    '{{index .Labels "ai.saintvision.config"}}',
                    name,
                )
                == label
            ):
                docker("volume", "rm", name)
        raise
    # Do not publish private credential hashes or file contents.
    return {
        "volume": volume,
        "workerVolume": worker_volume,
        "imageId": image,
        "filesVerified": len(api_files) + len(worker_files),
        "apiFilesVerified": len(api_files),
        "workerFilesVerified": len(worker_files),
        "uid": 65532,
        "mode": "0600",
        "serverStarted": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", required=True)
    parser.add_argument("--volume", required=True)
    parser.add_argument("--worker-volume")
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    try:
        print(
            json.dumps(
                prepare(
                    args.directory,
                    args.volume,
                    args.image,
                    worker_volume=args.worker_volume,
                )
            )
        )
    except Exception:
        raise SystemExit(
            "Configuration preparation rejected; existing volumes and source files preserved"
        )
