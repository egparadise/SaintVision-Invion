"""Opt-in storage mount for new Node containers; never replaces an existing Node."""

from copy import deepcopy
import hashlib
import io
import ipaddress
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tarfile
from uuid import UUID

from worker_config import repair_target

TARGET = "/contribution"
POLICY = "/state/storage-policy.json"


def reject():
    raise ValueError("Storage installation scope, path, bytes or receipt differs")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def regular(path):
    before = Path(path).lstat()
    if not stat.S_ISREG(before.st_mode):
        reject()
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    with os.fdopen(fd, "rb") as f:
        info = os.fstat(f.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or (info.st_dev, info.st_ino) != (before.st_dev, before.st_ino)
            or not 0 < info.st_size <= 65536
        ):
            reject()
        raw = f.read(65537)
    if len(raw) > 65536:
        reject()
    return raw


def strict(raw):
    def pairs(items):
        result = {}
        for k, v in items:
            if k in result:
                reject()
            result[k] = v
        return result

    return json.loads(raw, object_pairs_hook=pairs)


def source_identity(source, private):
    source = Path(source)
    if (
        not source.is_absolute()
        or str(source) != str(source.absolute())
        or ".." in source.parts
        or any(c in str(source) for c in ",\n\r\x00")
    ):
        reject()
    if source == Path(source.anchor) or re.fullmatch(r"/mnt/[a-zA-Z]", str(source)):
        reject()
    for path in (*reversed(source.parents), source):
        if not stat.S_ISDIR(path.lstat().st_mode):
            reject()
    resolved, private = source.resolve(), Path(private).resolve()
    if (
        resolved != source
        or resolved == private
        or resolved in private.parents
        or private in resolved.parents
    ):
        reject()
    info = source.stat()
    return [info.st_dev, info.st_ino]


def prepare(manifest, policy_path, source, expected_hash, image):
    if (
        type(manifest["nodePort"]) is not int
        or not 1 <= manifest["nodePort"] <= 65535
        or str(ipaddress.IPv4Address(manifest["nodeIP"])) != manifest["nodeIP"]
    ):
        reject()
    if not re.fullmatch(r"[a-f0-9]{64}", expected_hash) or not re.fullmatch(
        r"sha256:[a-f0-9]{64}", image
    ):
        reject()
    raw = regular(policy_path)
    if digest(raw) != expected_hash:
        reject()
    policy = strict(raw)
    if (
        set(policy) != {"channel", "contribution_id", "root_version", "root"}
        or policy["root"] != TARGET
    ):
        reject()
    channel = policy["channel"]
    if set(channel) != {
        "tenant_id",
        "node_id",
        "recovery_epoch",
        "version",
        "endpoint",
        "certificate_sha256",
    }:
        reject()
    if (channel["tenant_id"], channel["node_id"], channel["recovery_epoch"]) != (
        manifest["tenantId"],
        manifest["nodeId"],
        manifest["epoch"],
    ):
        reject()
    for value in (manifest["tenantId"], manifest["epoch"]):
        if str(UUID(value)) != value:
            reject()
    if not re.fullmatch(r"nod_[0-9A-HJKMNP-TV-Z]{26}", manifest["nodeId"]) or not re.fullmatch(
        r"stc_[0-9A-HJKMNP-TV-Z]{26}", policy["contribution_id"]
    ):
        reject()
    if channel[
        "endpoint"
    ] != f"https://{manifest['nodeIP']}:{manifest['nodePort']}" or not re.fullmatch(
        r"[a-f0-9]{64}", channel["certificate_sha256"]
    ):
        reject()
    for value in (policy["root_version"], channel["version"]):
        if type(value) is not int or not 1 <= value <= 9007199254740991:
            reject()
    if not Path(source).is_absolute():
        reject()
    source = str(Path(source).absolute())
    identity = source_identity(source, Path(policy_path).parent)
    return dict(
        manifest=manifest,
        source=source,
        sourceIdentity=identity,
        policyPath=str(Path(policy_path).absolute()),
        policySHA256=expected_hash,
        policy=policy,
        image=image,
    )


def current(plan):
    actual = prepare(
        plan["manifest"], plan["policyPath"], plan["source"], plan["policySHA256"], plan["image"]
    )
    if actual != plan:
        reject()


def mount_args(plan):
    current(plan)
    return [
        "--mount",
        f"type=bind,source={plan['source']},target={TARGET},readonly,bind-propagation=rprivate,bind-recursive=disabled",
    ]


def docker(*args, input=None):
    result = subprocess.run(["docker", *args], input=input, capture_output=True, timeout=30)
    if result.returncode:
        raise ValueError("Docker storage operation failed; Node identity and journal preserved")
    return result.stdout


def target(plan, inspected, running=False):
    current(plan)
    static = deepcopy(inspected)
    if running:
        if (
            not inspected["State"]["Running"]
            or inspected["State"]["Restarting"]
            or inspected.get("RestartCount") != 0
        ):
            reject()
        static["State"] = dict(Status="exited", Running=False, Restarting=False)
    repair_target(plan["manifest"], static)
    args = inspected["Config"]["Cmd"]
    if args.count("--storage-policy") != 1 or args[
        args.index("--storage-policy") + 1 : args.index("--storage-policy") + 2
    ] != [POLICY]:
        reject()
    mounts = [m for m in inspected["Mounts"] if m["Destination"] == TARGET]
    if (
        len(inspected["Mounts"]) != 2
        or len(mounts) != 1
        or mounts[0].get("Type") != "bind"
        or mounts[0].get("RW") is not False
        or mounts[0].get("Source") != plan["source"]
        or mounts[0].get("Propagation") != "rprivate"
    ):
        reject()
    host = inspected["HostConfig"]
    specifications = [m for m in host.get("Mounts", []) if m.get("Target") == TARGET]
    if (
        len(specifications) != 1
        or specifications[0].get("BindOptions", {}).get("NonRecursive") is not True
    ):
        reject()
    if (
        inspected["Image"] != plan["image"]
        or not host.get("ReadonlyRootfs")
        or host.get("Privileged")
    ):
        reject()


def install(container, plan):
    target(plan, strict(docker("inspect", container))[0])
    raw = regular(plan["policyPath"])
    if digest(raw) != plan["policySHA256"]:
        reject()
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w") as tar:
        entry = tarfile.TarInfo("storage-policy.json")
        entry.size = len(raw)
        entry.mode = 0o600
        entry.uid = entry.gid = 0
        tar.addfile(entry, io.BytesIO(raw))
    docker("cp", "-a", "-", container + ":/state", input=archive.getvalue())
    with tarfile.open(fileobj=io.BytesIO(docker("cp", container + ":" + POLICY, "-"))) as tar:
        entries = tar.getmembers()
        if len(entries) != 1:
            reject()
        e = entries[0]
        if (
            not e.isfile()
            or e.name != "storage-policy.json"
            or e.uid != 0
            or e.gid != 0
            or e.mode & 0o7777 != 0o600
            or e.size != len(raw)
            or tar.extractfile(e).read() != raw
        ):
            reject()
    target(plan, strict(docker("inspect", container))[0])


def receipt(plan, inspected, logs):
    target(plan, inspected, running=True)
    if len(logs) > 65536:
        reject()
    rows = []
    for line in logs.splitlines():
        try:
            value = strict(line)
        except (ValueError, TypeError):
            continue
        if isinstance(value, dict) and "storagePolicy" in value:
            rows.append(value)
    if len(rows) != 1:
        reject()
    value = rows[0]
    p = value["storagePolicy"]
    if not isinstance(p, dict):
        reject()
    policy = plan["policy"]
    m = plan["manifest"]
    if (value.get("tenantId"), value.get("nodeId"), value.get("recoveryEpoch")) != (
        m["tenantId"],
        m["nodeId"],
        m["epoch"],
    ) or value.get("operationalAcceptanceAssessed") is not False:
        reject()
    expected = dict(
        contributionId=policy["contribution_id"],
        rootVersion=policy["root_version"],
        channelVersion=policy["channel"]["version"],
        policySha256=plan["policySHA256"],
        rootSha256=digest(TARGET.encode()),
    )
    if any(p.get(k) != v for k, v in expected.items()) or not re.fullmatch(
        r"[0-9a-f]{64}", p.get("channelSha256", "")
    ):
        reject()
    return dict(
        nodeId=m["nodeId"],
        tenantId=m["tenantId"],
        recoveryEpoch=m["epoch"],
        containerId=inspected["Id"],
        agentImage=inspected["Image"],
        storagePolicy=expected,
        readOnlyMount=True,
        status="awaiting-server-mtls-verification",
        operationalAcceptanceAssessed=False,
    )


if __name__ == "__main__":
    try:
        op = sys.argv[1]
        if op == "prepare":
            print(
                json.dumps(
                    prepare(
                        strict(regular(sys.argv[2])),
                        sys.argv[3],
                        sys.argv[4],
                        sys.argv[5],
                        sys.argv[6],
                    )
                )
            )
        else:
            plan = strict(regular(sys.argv[2]))
            if op == "mount-args":
                sys.stdout.buffer.write(b"\0".join(s.encode() for s in mount_args(plan)) + b"\0")
            elif op == "install":
                install(sys.argv[3], plan)
            elif op == "receipt":
                before = strict(docker("inspect", sys.argv[3]))[0]
                result = receipt(plan, before, docker("logs", "--tail", "10", sys.argv[3]))
                after = strict(docker("inspect", sys.argv[3]))[0]
                target(plan, after, running=True)
                if (before["Id"], before["State"]["StartedAt"]) != (
                    after["Id"],
                    after["State"]["StartedAt"],
                ):
                    reject()
                print(json.dumps(result))
            else:
                reject()
    except (
        ValueError,
        KeyError,
        IndexError,
        TypeError,
        OSError,
        subprocess.SubprocessError,
        tarfile.TarError,
    ):
        print(
            "Storage installation rejected; preserve Node keys, volume and journal.",
            file=sys.stderr,
        )
        raise SystemExit(1)
