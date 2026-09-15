"""Read-only replacement preflight. A receipt is not permission to delete a Node."""

from copy import deepcopy
import io
import json
from pathlib import PurePosixPath
import re
import subprocess
import sys
import tarfile
import threading

import worker_storage as storage
from worker_config import CREDENTIAL_FILES, repair_target

LIMIT = 16 * 1024 * 1024


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def inspected(name):
    value = storage.strict(storage.docker("inspect", name))[0]
    # Docker returns mount map entries in unspecified order. Preserve every field.
    value = deepcopy(value)
    value["Mounts"] = sorted(value["Mounts"], key=lambda m: m["Destination"])
    return value


def state_archive(container):
    # Bound both bytes and time; private state stays in memory, never in logs.
    with subprocess.Popen(
        ["docker", "cp", container + ":/state", "-"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    ) as process:
        timer = threading.Timer(30, process.kill)
        timer.start()
        try:
            raw = process.stdout.read(LIMIT + 1)
            if len(raw) > LIMIT:
                process.kill()
                storage.reject()
            if process.wait(timeout=5):
                storage.reject()
            return raw
        finally:
            timer.cancel()
            if process.poll() is None:
                process.kill()


def state_digest(raw, manifest, *, exclude=()):
    if len(raw) > LIMIT:
        storage.reject()
    files, rows, seen = {}, [], set()
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as archive:
        for entry in archive:
            path = PurePosixPath(entry.name)
            if (
                path.is_absolute()
                or ".." in path.parts
                or not path.parts
                or path.parts[0] != "state"
                or str(path) in seen
                or not (entry.isfile() or entry.isdir())
                or entry.size < 0
                or entry.size > LIMIT
            ):
                storage.reject()
            seen.add(str(path))
            data = archive.extractfile(entry).read() if entry.isfile() else b""
            if entry.isfile():
                if len(data) != entry.size:
                    storage.reject()
                files[str(path)] = (entry, data)
            if str(path) in exclude:
                continue
            rows.append(
                [
                    str(path),
                    entry.isdir(),
                    entry.mode & 0o7777,
                    entry.uid,
                    entry.gid,
                    len(data),
                    storage.digest(data),
                ]
            )
    for name in (*CREDENTIAL_FILES, "journal/identity.json"):
        entry, data = files["state/" + name]
        if entry.uid != 0 or entry.gid != 0 or entry.mode & 0o7777 != 0o600 or not data:
            storage.reject()
    identity = storage.strict(files["state/journal/identity.json"][1])
    if identity != dict(
        Tenant=manifest["tenantId"], Node=manifest["nodeId"], Epoch=manifest["epoch"]
    ):
        storage.reject()
    return storage.digest(canonical(sorted(rows)))


def stopped_target(plan, value, volume, consumers):
    storage.current(plan)
    repair_target(plan["manifest"], value)
    if not re.fullmatch(r"[0-9a-f]{64}", value["Id"]):
        storage.reject()
    state = value["State"]
    if state["Status"] != "exited" or state.get("OOMKilled") or state.get("ExitCode") != 0:
        storage.reject()
    args = value["Config"]["Cmd"]
    if args.count("--profile") != 1 or args[
        args.index("--profile") + 1 : args.index("--profile") + 2
    ] != ["lan-observe-v1"]:
        storage.reject()
    host = value["HostConfig"]
    if host.get("Privileged") or not host.get("ReadonlyRootfs"):
        storage.reject()
    name = "saintvision-" + plan["manifest"]["nodeId"].lower() + "-state"
    if (
        volume.get("Name") != name
        or volume.get("Labels", {}).get("ai.saintvision.node") != plan["manifest"]["nodeId"]
        or consumers != [value["Id"]]
    ):
        storage.reject()
    # Do not silently remove an unknown workspace/device/extra mount in a replacement.
    destinations = sorted(m["Destination"] for m in value["Mounts"])
    if destinations not in (["/state"], ["/contribution", "/state"]):
        storage.reject()
    if "/contribution" in destinations:
        mounts = [m for m in value["Mounts"] if m["Destination"] == "/contribution"]
        if mounts[0].get("Type") != "bind" or mounts[0].get("RW") is not False:
            storage.reject()
    return name


def capture(plan):
    name = "saintvision-" + plan["manifest"]["nodeId"].lower()
    before = inspected(name)
    volume = storage.strict(storage.docker("volume", "inspect", name + "-state"))[0]
    consumers = (
        storage.docker("ps", "-aq", "--no-trunc", "--filter", "volume=" + name + "-state")
        .decode()
        .split()
    )
    stopped_target(plan, before, volume, consumers)
    state = state_digest(state_archive(before["Id"]), plan["manifest"])
    after = inspected(name)
    volume_after = storage.strict(storage.docker("volume", "inspect", name + "-state"))[0]
    consumers_after = (
        storage.docker("ps", "-aq", "--no-trunc", "--filter", "volume=" + name + "-state")
        .decode()
        .split()
    )
    stopped_target(plan, after, volume_after, consumers_after)
    # A second bounded state read detects writes during the first inspection.
    if (
        before != after
        or volume != volume_after
        or state != state_digest(state_archive(before["Id"]), plan["manifest"])
        or after != inspected(name)
    ):
        storage.reject()
    return dict(
        version=1,
        containerId=before["Id"],
        containerSHA256=storage.digest(canonical(before)),
        volumeSHA256=storage.digest(canonical(volume)),
        stateSHA256=state,
        proposedPlanSHA256=storage.digest(canonical(plan)),
        operationalAcceptanceAssessed=False,
        replacementAuthorized=False,
    )


def recheck(plan, receipt):
    current = capture(plan)
    if canonical(current) != canonical(receipt):
        storage.reject()
    return current


if __name__ == "__main__":
    try:
        plan = storage.strict(storage.regular(sys.argv[2]))
        if sys.argv[1] == "preflight" and len(sys.argv) == 3:
            result = capture(plan)
        elif sys.argv[1] == "recheck" and len(sys.argv) == 4:
            result = recheck(plan, storage.strict(storage.regular(sys.argv[3])))
        else:
            storage.reject()
        print(json.dumps(result))
    except (
        ValueError,
        KeyError,
        IndexError,
        TypeError,
        OSError,
        tarfile.TarError,
        subprocess.SubprocessError,
    ):
        print("Replacement preflight rejected; no Node or volume changed.", file=sys.stderr)
        raise SystemExit(1)
