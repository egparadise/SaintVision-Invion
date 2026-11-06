"""Read a fresh signed floor from this exact owned plain Node container.

Never reads a host mirror, imports a key, creates a journal, or selects an
arbitrary SaintVision container on a multi-Node host.
"""
from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tarfile
import selectors
import time
from pathlib import PurePosixPath
from uuid import uuid4
from cryptography import x509
from cryptography.hazmat.primitives import serialization

import peer_policy_phase as phase
from worker_config import repair_target, no_migration


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


def _stopped_archive(cid):
    process = subprocess.Popen(['docker','cp',cid+':/state','-'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    limit, deadline, chunks, size = 16*1024*1024, time.monotonic()+30, [], 0
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while selector.get_map():
                remaining = deadline-time.monotonic()
                if remaining <= 0:
                    raise ValueError('RS1 stopped-volume read timed out')
                for key,_ in selector.select(min(1,remaining)):
                    block = os.read(key.fileobj.fileno(),min(65536,limit-size+1))
                    if not block:
                        selector.unregister(key.fileobj)
                        continue
                    size += len(block)
                    if size > limit:
                        raise ValueError('RS1 stopped-volume archive exceeds its bound')
                    chunks.append(block)
        if process.wait(timeout=max(.1,deadline-time.monotonic())) != 0 or size == 0:
            raise ValueError('RS1 stopped-volume read failed')
        return b''.join(chunks)
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)
        process.stdout.close()


def stopped_entries(worker_root, expected_context):
    """Unsigned actual-volume read ONLY for RS1 start eligibility, never an ack."""
    _, _, before, _, _, _ = target(worker_root)
    if context(worker_root) != expected_context or before["State"].get("Running") or before["State"].get("Restarting") or before["State"].get("Status") not in {"exited", "created"}:
        raise ValueError("RS1 requires this exact stopped owned Node")
    raw_archive = _stopped_archive(before['Id'])
    entries, seen = {}, set()
    required = {"node-cert.pem", "node-key.pem", "ca.pem", "signer.pub", "peer-policy.json", "journal/identity.json", "journal/.peer-policy"}
    with tarfile.open(fileobj=io.BytesIO(raw_archive),mode='r:') as archive:
        for member in archive:
            name = member.name.rstrip('/')
            path = PurePosixPath(name)
            if (len(seen) >= 2048 or name in seen or str(path) != name or path.is_absolute()
                    or '..' in path.parts or '\\' in name or not path.parts or path.parts[0] != 'state'
                    or member.uid != 0 or member.gid != 0
                    or any(k not in {'mtime','atime','ctime'} or not re.fullmatch(r'-?[0-9]{1,20}(\.[0-9]{1,9})?',v) for k,v in member.pax_headers.items())):
                raise ValueError("RS1 actual-volume metadata is unsafe")
            seen.add(name)
            if member.isdir():
                if member.mode & 0o022 or (name == 'state/journal' and member.mode & 0o7777 != 0o700):
                    raise ValueError("RS1 actual directory ownership/mode differs")
                continue
            if member.type not in {tarfile.REGTYPE,tarfile.AREGTYPE} or member.sparse or member.mode & 0o7777 != 0o600 or not 0 <= member.size <= 65536:
                raise ValueError("RS1 refuses links, unsafe modes and unbounded state entries")
            relative = name.removeprefix('state/')
            if relative in required:
                if member.size == 0:
                    raise ValueError('RS1 required state entry is empty')
                raw = archive.extractfile(member).read(65537)
                if len(raw) != member.size:
                    raise ValueError("RS1 actual entry changed")
                entries[relative] = raw
    if set(entries) != required or context(worker_root) != expected_context:
        raise ValueError("RS1 actual-volume identity changed or required state is missing")
    _, _, after, _, _, _ = target(worker_root)
    if after["State"].get("Running") or after["State"].get("Restarting"):
        raise ValueError("RS1 Node changed while reading stopped state")
    return entries


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
    no_migration(worker_root, leaf_observation=True)
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


OBSERVATION_CHANGE_PREFIX = "Owned container/state changed during actual floor observation"
_CONFIG_DIAGNOSTIC_FIELDS = ("Cmd", "Entrypoint", "Env", "Labels", "Image", "User", "WorkingDir",
                             "Hostname", "Domainname", "Volumes", "ExposedPorts", "Healthcheck",
                             "StopSignal", "StopTimeout", "Tty", "OpenStdin", "StdinOnce", "Shell")
_MOUNT_DIAGNOSTIC_FIELDS = ("Type", "Name", "Source", "Destination", "Driver", "Mode", "RW", "Propagation")
_VOLUME_DIAGNOSTIC_FIELDS = ("Name", "Driver", "Mountpoint", "CreatedAt", "Scope", "Labels", "Options", "Status")


def _diagnostic_hash(value):
    """A bounded whole-field digest, never repr/str or a secret-value digest list."""
    budget = [512, 65536]

    def bounded(item, depth):
        budget[0] -= 1
        if depth > 8 or budget[0] < 0:
            return False
        kind = type(item)
        if item is None or kind is bool:
            return True
        if kind is int:
            return item.bit_length() <= 64
        if kind is str:
            budget[1] -= len(item.encode("utf-8", errors="surrogatepass"))
            return len(item) <= 16384 and budget[1] >= 0
        if kind is list:
            return len(item) <= 64 and all(bounded(v, depth + 1) for v in item)
        if kind is dict:
            return (len(item) <= 64 and all(type(k) is str and len(k) <= 128
                    and bounded(k, depth + 1) and bounded(v, depth + 1) for k, v in item.items()))
        return False

    if not bounded(value, 0):
        return None
    raw = json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest() if len(raw) <= 131072 else None


def _diagnostic_paths(prefix, before, after, names):
    """Only predeclared API field names; no arbitrary keys or values escape."""
    if type(before) is not dict or type(after) is not dict:
        return [prefix]
    missing = object()
    paths = [prefix + "." + name for name in names if before.get(name, missing) != after.get(name, missing)]
    unknown_before = {k: v for k, v in before.items() if k not in names}
    unknown_after = {k: v for k, v in after.items() if k not in names}
    if unknown_before != unknown_after:
        paths.append(prefix + ".<other>")
    return paths or [prefix]


def _observation_diagnostic(before, after, volume, volume_after, consumers, consumers_after):
    """DIAGNOSIS ONLY: never participates in, normalizes or relaxes the guard.

    Original values are compared by the unchanged observe predicate below. These
    bounded paths/categories/hashes contain no Config/argv/env/key/cert/nonce/path
    values. Even an order-only/CreatedAt-only classification remains a refusal.
    """
    pairs = (("container.Id", before["Id"], after["Id"], "CONTAINER_ID_CHANGED"),
             ("container.Image", before["Image"], after["Image"], "IMAGE_CHANGED"),
             ("container.Config", before["Config"], after["Config"], "CONFIG_CHANGED"),
             ("container.Mounts", before["Mounts"], after["Mounts"], "MOUNTS_CHANGED"),
             ("container.State.StartedAt", before["State"].get("StartedAt"), after["State"].get("StartedAt"), "STARTED_AT_CHANGED"),
             ("container.RestartCount", before.get("RestartCount"), after.get("RestartCount"), "RESTART_COUNT_CHANGED"),
             ("volume", volume, volume_after, "VOLUME_CHANGED"),
             ("volumeConsumers", consumers, consumers_after, "CONSUMERS_CHANGED"))
    paths, categories, hashes = [], [], {}
    hash_unavailable = False
    for path, old, new, category in pairs:
        if old == new:
            continue
        hashes[path] = {"beforeSHA256": _diagnostic_hash(old), "afterSHA256": _diagnostic_hash(new)}
        hash_unavailable |= any(v is None for v in hashes[path].values())
        if path == "container.Config":
            paths.extend(_diagnostic_paths(path, old, new, _CONFIG_DIAGNOSTIC_FIELDS))
        elif path == "container.Mounts" and type(old) is list and type(new) is list:
            # Sorting digests classifies a potential representation difference;
            # the original raw Mounts list STILL refuses below. Preserve counts.
            old_hashes = [_diagnostic_hash(v) for v in old[:64]]
            new_hashes = [_diagnostic_hash(v) for v in new[:64]]
            if (len(old) == len(new) <= 64 and None not in old_hashes + new_hashes
                    and sorted(old_hashes) == sorted(new_hashes)):
                category = "MOUNTS_ORDER_ONLY"
                paths.append(path)
            else:
                paths.append(path)
                for i, (a, b) in enumerate(zip(old[:8], new[:8])):
                    if a != b:
                        paths.extend(_diagnostic_paths(path + "[" + str(i) + "]", a, b, _MOUNT_DIAGNOSTIC_FIELDS))
        elif path == "volume":
            paths.extend(_diagnostic_paths(path, old, new, _VOLUME_DIAGNOSTIC_FIELDS))
            if (type(old) is dict and type(new) is dict
                    and {k: v for k, v in old.items() if k != "CreatedAt"} == {k: v for k, v in new.items() if k != "CreatedAt"}):
                category = "VOLUME_CREATED_AT_FIELD_ONLY"
        else:
            paths.append(path)
        categories.append(category)
    # Fixed field names, <=24 paths, depth <=3, <=72 characters per path; eight
    # whole-field digest pairs maximum. Unknown/unhashable data never yields PASS.
    paths = list(dict.fromkeys(paths))
    result = dict(diagnosticVersion=1, classification="REFUSAL_DIAGNOSTIC_ONLY",
                  changedPaths=paths[:24], categories=categories or ["UNKNOWN_DIFFERENCE"],
                  hashes=hashes, truncated=len(paths) > 24 or hash_unavailable)
    raw = json.dumps(result, sort_keys=True, separators=(",", ":"))
    if len(raw) > 4096:
        raw = json.dumps(dict(diagnosticVersion=1, classification="REFUSAL_DIAGNOSTIC_ONLY",
                             changedPaths=list(hashes), categories=["DIAGNOSTIC_BOUND_EXCEEDED"],
                             hashes={}, truncated=True), sort_keys=True, separators=(",", ":"))
    return raw


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
        raise ValueError(OBSERVATION_CHANGE_PREFIX + "; diagnostic=" +
                         _observation_diagnostic(before, after, volume, volume_after, consumers, consumers_after))
    return value


def context(worker_root):
    manifest, _, value, _, volume, consumers = target(worker_root)
    # CreatedAt is not stable on Docker Desktop; identity is the owned named
    # volume plus exact retained container/consumer/config bindings.
    return dict(nodeId=manifest["nodeId"], containerId=value["Id"], image=value["Image"],
                configSHA256=phase.digest(phase.canonical(value["Config"])),
                hostConfigSHA256=phase.digest(phase.canonical(value['HostConfig'])),
                mountsSHA256=phase.digest(phase.canonical(sorted(value["Mounts"], key=lambda m: m["Destination"]))),
                volumeSHA256=phase.digest(phase.canonical({k: v for k, v in volume.items() if k != "CreatedAt"})),
                consumers=consumers)
