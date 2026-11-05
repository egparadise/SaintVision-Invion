"""Read a fresh signed floor from this exact owned plain Node container.

Never reads a host mirror, imports a key, creates a journal, or selects an
arbitrary SaintVision container on a multi-Node host.
"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
from uuid import uuid4
from cryptography import x509
from cryptography.hazmat.primitives import serialization

import peer_policy_phase as phase
from worker_config import repair_target


def regular(path):
    path = Path(path)
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= 65536:
        raise ValueError("Private operation file is missing or unsafe")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    with os.fdopen(fd, "rb") as stream:
        actual = os.fstat(stream.fileno())
        if (actual.st_dev, actual.st_ino, actual.st_size) != (before.st_dev, before.st_ino, before.st_size) or not stat.S_ISREG(actual.st_mode):
            raise ValueError("Private operation file changed")
        raw = stream.read(65537)
    if len(raw) != actual.st_size:
        raise ValueError("Private operation file size changed")
    return raw


def docker(*args):
    result = subprocess.run(["docker", *map(str, args)], capture_output=True, timeout=30)
    if result.returncode or len(result.stdout) > 1024 * 1024:
        raise ValueError("Owned Node floor operation unavailable; preserve state")
    return result.stdout


def _plain(manifest, value, *, current=True):
    static = deepcopy(value)
    static["State"] = dict(Status="exited", Running=False, Restarting=False)
    repair_target(manifest, static)
    args = value["Config"]["Cmd"]
    if any(arg.split("=", 1)[0] in ("--storage-policy", "-storage-policy") for arg in args):
        raise ValueError("Storage-configured Node requires separately accepted compound renewal")
    for flag in ("--state", "--peer-policy", "--tls-cert", "--tls-key", "--profile"):
        if args.count(flag) != 1 or not args[args.index(flag) + 1:args.index(flag) + 2]:
            raise ValueError("Actual Node floor path/profile arguments are ambiguous")
    if args[args.index("--state") + 1] != "/state/journal" or args[args.index("--peer-policy") + 1] != "/state/peer-policy.json":
        raise ValueError("Actual Node state paths require an explicit supported migration")
    if args[args.index("--profile") + 1] not in ("lan-observe-v1", "lan-test-v1", "lan-workspace-v1"):
        raise ValueError("Unsupported plain Node profile")
    for arg in args:
        if arg.split("=", 1)[0] in ("--socket", "-socket"):
            if arg != "--socket" or args.count("--socket") != 1 or args[args.index(arg) + 1:args.index(arg) + 2] != ["/var/run/docker.sock"]:
                raise ValueError("Only the existing default local daemon is supported")
    sockets = 0
    for mount in value.get("Mounts", []):
        if mount.get("Destination") == "/state":
            continue
        if (mount.get("Destination") == "/var/run/docker.sock" and mount.get("Type") == "bind"
                and mount.get("Source") == "/var/run/docker.sock" and mount.get("RW") is True
                and mount.get("Propagation") == "rprivate"):
            sockets += 1
            if sockets == 1:
                continue
        raise ValueError("Contribution or unknown mounts require separately accepted renewal")
    host = value.get("HostConfig", {})
    if host.get("Privileged") or not host.get("ReadonlyRootfs"):
        raise ValueError("Plain Node container isolation differs")
    if not re.fullmatch(r"[a-f0-9]{64}", value.get("Id", "")):
        raise ValueError("Actual container identity differs")
    if not current and (value["State"].get("Running") or host.get("RestartPolicy", {}).get("Name") != "no"):
        raise ValueError("A retained backup may not be a state-volume writer")
    return args


def target(worker_root):
    manifest = phase.strict(regular(Path(worker_root) / "manifest.json"))
    node = manifest["nodeId"]
    if not re.fullmatch(r"nod_[0-9A-HJKMNP-TV-Z]{26}", node):
        raise ValueError("Actual Node identity is invalid")
    name = "saintvision-" + node.lower()
    value = phase.strict(docker("container", "inspect", name))[0]
    args = _plain(manifest, value)
    volume_name = name + "-state"
    volume = phase.strict(docker("volume", "inspect", volume_name))[0]
    if volume.get("Name") != volume_name or volume.get("Labels", {}).get("ai.saintvision.node") != node:
        raise ValueError("Actual Node state volume ownership differs")
    consumers = docker("ps", "-aq", "--no-trunc", "--filter", "volume=" + volume_name).decode().split()
    if value["Id"] not in consumers or len(consumers) > 2 or len(consumers) != len(set(consumers)):
        raise ValueError("Actual Node state volume consumers differ")
    # Workspace preserves exactly one fenced predecessor. It is not a separate
    # journal backup and is never restarted here. Unknown consumers are refused.
    if len(consumers) == 2:
        record = phase.strict(regular(Path(worker_root) / "workspace-upgrade.json"))
        other = next(identifier for identifier in consumers if identifier != value["Id"])
        backup = phase.strict(docker("container", "inspect", other))[0]
        static = deepcopy(backup)
        static["Name"] = "/" + name
        _plain(manifest, static, current=False)
        if (record.get("phase") != "ready" or record.get("previousId") != other
                or backup["Name"] != "/" + record.get("backup", "")
                or value["Config"].get("Labels", {}).get("ai.saintvision.upgrade") != record.get("upgradeId")
                or value["Image"] != record.get("agentImage")):
            raise ValueError("Retained state consumer is not this exact fenced workspace predecessor")
    return manifest, name, value, args, volume, sorted(consumers)


def observe(worker_root, rotation, files, *, nonce=None):
    manifest, name, before, args, volume, consumers = target(worker_root)
    if (manifest["nodeId"], manifest["tenantId"], manifest["epoch"]) != (rotation["nodeId"], rotation["tenantId"], rotation["recoveryEpoch"]):
        raise ValueError("Floor target identity differs from proposal")
    if not before["State"].get("Running") or before["State"].get("Restarting"):
        raise ValueError("Actual running Node floor is unavailable; no fallback or reset")
    nonce = nonce or uuid4().hex + uuid4().hex
    command = ["exec", before["Id"], "/inv-node", "--observe-peer-policy-floor",
               "--state", args[args.index("--state") + 1],
               "--peer-policy", args[args.index("--peer-policy") + 1],
               "--tls-cert", args[args.index("--tls-cert") + 1],
               "--tls-key", args[args.index("--tls-key") + 1],
               "--tenant", manifest["tenantId"], "--node", manifest["nodeId"], "--epoch", manifest["epoch"],
               "--peer-floor-nonce", nonce]
    value = phase.strict(docker(*command))
    if value.get("servingPID") != 1:
        raise ValueError("Actual container serving process differs")
    cert = next((raw for key, raw in files.items() if key in ("node-cert.pem", "previous-node-cert.pem")
                 and phase.digest(x509.load_pem_x509_certificate(raw).public_bytes(serialization.Encoding.DER)) == value.get("certificateDER_SHA256")), None)
    if cert is None:
        raise ValueError("Actual floor DER is outside the immutable proposal")
    phase.verify_floor(value, cert, rotation, nonce=nonce)
    _, _, after, _, volume_after, consumers_after = target(worker_root)
    if not after["State"].get("Running") or after["State"].get("Restarting"):
        raise ValueError("Actual Node stopped during floor observation")
    if (before["Id"], before["Image"], before["Config"], before["Mounts"], before["State"].get("StartedAt"), before.get("RestartCount"), volume, consumers) != (after["Id"], after["Image"], after["Config"], after["Mounts"], after["State"].get("StartedAt"), after.get("RestartCount"), volume_after, consumers_after):
        raise ValueError("Owned container/state changed during actual floor observation")
    return value


def context(worker_root):
    manifest, _, value, _, volume, consumers = target(worker_root)
    # CreatedAt is not stable on Docker Desktop; identity is the owned named
    # volume plus exact retained container/consumer/config bindings.
    return dict(nodeId=manifest["nodeId"], containerId=value["Id"], image=value["Image"],
                configSHA256=phase.digest(phase.canonical(value["Config"])),
                mountsSHA256=phase.digest(phase.canonical(sorted(value["Mounts"], key=lambda m: m["Destination"]))),
                volumeSHA256=phase.digest(phase.canonical({k: v for k, v in volume.items() if k != "CreatedAt"})),
                consumers=consumers)
