"""Forward-only replacement of one stopped observation Node; never deletes state."""

import base64
import io
from contextlib import contextmanager, redirect_stdout
from copy import deepcopy
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tarfile
from uuid import uuid4

import worker_replacement as preflight
import worker_storage as storage
from worker_config import image_id, check_running


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def save(path, value):
    raw = preflight.canonical(value)
    if len(raw) > 65536:
        storage.reject()
    temporary = path.parent / (".replacement-" + uuid4().hex + ".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    sync_directory(path.parent)


@contextmanager
def locked(directory):
    import fcntl

    directory = Path(directory)
    for p in (*reversed(directory.parents), directory):
        if not stat.S_ISDIR(p.lstat().st_mode):
            storage.reject()
    info = directory.stat()
    if info.st_uid != os.geteuid() or info.st_mode & 0o077:
        storage.reject()
    fd = os.open(directory / ".storage-replace.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
            storage.reject()
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(fd)


def optional(name):
    result = subprocess.run(
        ["docker", "container", "inspect", name], capture_output=True, timeout=30
    )
    if result.returncode:
        if b"No such" in result.stderr:
            return None
        storage.reject()
    value = storage.strict(result.stdout)[0]
    value["Mounts"] = sorted(value["Mounts"], key=lambda m: m["Destination"])
    return value


def validate_volume(previous, current, expected_hash):
    # Docker Desktop can change CreatedAt after writes to a retained volume.
    # Identity is anchored by the retained container ID and its unchanged mount,
    # checked separately; preserve every other volume metadata field.
    if storage.digest(preflight.canonical(previous)) != expected_hash:
        storage.reject()
    if {k: v for k, v in previous.items() if k != "CreatedAt"} != {
        k: v for k, v in current.items() if k != "CreatedAt"
    }:
        storage.reject()


def command(plan):
    m = plan["manifest"]
    return [
        "--serve",
        "--listen",
        "0.0.0.0:18443",
        "--tenant",
        m["tenantId"],
        "--node",
        m["nodeId"],
        "--epoch",
        m["epoch"],
        "--profile",
        "lan-observe-v1",
        "--image",
        m["agentImage"],
        "--executable",
        "/inv-node",
        "--state",
        "/state/journal",
        "--public-key",
        "/state/signer.pub",
        "--tls-cert",
        "/state/node-cert.pem",
        "--tls-key",
        "/state/node-key.pem",
        "--client-ca",
        "/state/ca.pem",
        "--peer-policy",
        "/state/peer-policy.json",
        "--storage-policy",
        storage.POLICY,
    ]


def preserved(plan, container):
    return preflight.state_digest(
        preflight.state_archive(container),
        plan["manifest"],
        exclude=(
            "state/storage-policy.json",
            "state/journal/.storage-" + plan["policy"]["contribution_id"],
        ),
    )


def start_and_confirm(name, container_id, checkpoint):
    """Cross the startup fault seam only after journal initialization is stable."""
    storage.docker("start", container_id)
    with redirect_stdout(io.StringIO()):
        check_running(name)
    checkpoint("starting")


def old_target(record, value):
    if value is None or value["Id"] != record["previous"]["Id"]:
        storage.reject()
    adjusted = deepcopy(value)
    adjusted["Name"] = record["previous"]["Name"]
    adjusted["HostConfig"]["RestartPolicy"] = record["previous"]["HostConfig"]["RestartPolicy"]
    if adjusted != record["previous"] or value["State"]["Running"]:
        storage.reject()
    if value["HostConfig"]["RestartPolicy"]["Name"] not in (
        "no",
        record["previous"]["HostConfig"]["RestartPolicy"]["Name"],
    ):
        storage.reject()


def new_target(plan, record, value):
    if record.get("currentId") and (value is None or value["Id"] != record["currentId"]):
        storage.reject()
    if (
        value is None
        or value["Config"]["Labels"].get("ai.saintvision.storage-replace") != record["id"]
    ):
        storage.reject()
    storage.target(plan, value, running=value["State"]["Running"])
    host = value["HostConfig"]
    if (
        value["Config"]["Cmd"] != command(plan)
        or host["RestartPolicy"]["Name"] != "no"
        or host["PortBindings"]
        != {
            "18443/tcp": [
                {
                    "HostIp": plan["manifest"]["nodeIP"],
                    "HostPort": str(plan["manifest"]["nodePort"]),
                }
            ]
        }
        or host.get("CapDrop") != ["ALL"]
        or host.get("SecurityOpt") != ["no-new-privileges"]
        or host.get("PidsLimit") != 128
        or host.get("Memory") != 268435456
        or host.get("NanoCpus") != 500000000
    ):
        storage.reject()


def run(plan, receipt, *, checkpoint=lambda phase: None):
    """checkpoint is a test fault seam, never a CLI argument or environment option."""
    directory = Path(plan["policyPath"]).parent
    with locked(directory):
        storage.current(plan)
        if (
            image_id(
                plan["manifest"],
                storage.strict(storage.docker("image", "inspect", plan["image"]))[0],
            )
            != plan["image"]
        ):
            storage.reject()
        path = directory / "storage-replacement.json"
        name = "saintvision-" + plan["manifest"]["nodeId"].lower()
        if path.exists() or path.is_symlink():
            info = path.lstat()
            if info.st_uid != os.geteuid() or info.st_mode & 0o077:
                storage.reject()
            record = storage.strict(storage.regular(path))
            if (
                record["phase"]
                not in (
                    "prepared",
                    "fenced",
                    "renamed",
                    "created",
                    "installed",
                    "starting",
                    "ready",
                )
                or record["planHash"] != storage.digest(preflight.canonical(plan))
                or record["receipt"] != receipt
            ):
                storage.reject()
        else:
            preflight.recheck(plan, receipt)
            old = preflight.inspected(name)
            expected_cmd = command(plan)
            prior_cmd = old["Config"]["Cmd"]
            image_index = expected_cmd.index("--image") + 1
            if prior_cmd.count("--image") != 1:
                storage.reject()
            expected_cmd[image_index] = prior_cmd[prior_cmd.index("--image") + 1]
            if "--storage-policy" not in prior_cmd:
                expected_cmd = expected_cmd[:-2]
            if prior_cmd != expected_cmd:
                storage.reject()
            previous_policy = None
            with tarfile.open(fileobj=io.BytesIO(preflight.state_archive(old["Id"]))) as archive:
                for entry in archive:
                    if entry.name == "state/storage-policy.json":
                        previous_policy = base64.b64encode(
                            archive.extractfile(entry).read()
                        ).decode("ascii")
            record = dict(
                previousPolicyBase64=previous_policy,
                id=uuid4().hex,
                phase="prepared",
                planHash=storage.digest(preflight.canonical(plan)),
                receipt=receipt,
                previous=old,
                previousVolume=storage.strict(storage.docker("volume", "inspect", name + "-state"))[
                    0
                ],
                backup=name + "-storage-backup-" + uuid4().hex[:12],
                protectedHash=preserved(plan, old["Id"]),
            )
            preflight.recheck(plan, receipt)
            save(path, record)
            checkpoint("prepared")

        def phase(label):
            checkpoint(label)  # crash immediately after the action, before recording it
            record["phase"] = label
            save(path, record)

        old = optional(record["previous"]["Id"])
        old_target(record, old)
        if preserved(plan, old["Id"]) != record["protectedHash"]:
            storage.reject()
        node = plan["manifest"]["nodeId"]
        if storage.docker(
            "ps",
            "-aq",
            "--filter",
            "label=ai.saintvision.node=" + node,
            "--filter",
            "label=ai.saintvision.command",
        ).strip():
            storage.reject()
        if old["HostConfig"]["RestartPolicy"]["Name"] != "no":
            storage.docker("update", "--restart=no", old["Id"])
            phase("fenced")
        old = optional(old["Id"])
        old_target(record, old)
        if old["Name"] == "/" + name:
            storage.docker("rename", old["Id"], record["backup"])
            phase("renamed")
        elif old["Name"] != "/" + record["backup"]:
            storage.reject()
        current = optional(name)
        consumers = set(
            storage.docker("ps", "-aq", "--no-trunc", "--filter", "volume=" + name + "-state")
            .decode()
            .split()
        )
        expected = {old["Id"]} | ({current["Id"]} if current else set())
        volume = storage.strict(storage.docker("volume", "inspect", name + "-state"))[0]
        if consumers != expected:
            raise ValueError("Replacement volume consumers differ")
        validate_volume(record["previousVolume"], volume, receipt["volumeSHA256"])
        if current is None:
            if record.get("currentId") or record["phase"] in ("starting", "ready"):
                raise ValueError("Previously started replacement is missing")
            storage.docker(
                "create",
                "--name",
                name,
                "--label",
                "ai.saintvision.node=" + node,
                "--label",
                "ai.saintvision.storage-replace=" + record["id"],
                "--restart",
                "no",
                "--read-only",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "--pids-limit",
                "128",
                "--memory",
                "256m",
                "--cpus",
                "0.5",
                "--publish",
                plan["manifest"]["nodeIP"] + ":" + str(plan["manifest"]["nodePort"]) + ":18443",
                "--mount",
                "type=volume,source=" + name + "-state,target=/state",
                *storage.mount_args(plan),
                plan["image"],
                *command(plan),
            )
            current = optional(name)
            record["currentId"] = current["Id"]
            phase("created")
        new_target(plan, record, current)
        if not record.get("currentId"):
            record["currentId"] = current["Id"]
            save(path, record)
        if not current["State"]["Running"]:
            if current["State"]["Status"] == "created":
                storage.install(name, plan)
                phase("installed")
            elif record["phase"] not in ("starting", "ready"):
                storage.reject()
            # Starting may persist a new floor. Never restore the old policy/container.
            record["phase"] = "starting"
            save(path, record)
            start_and_confirm(name, current["Id"], checkpoint)
            record["phase"] = "starting"
            save(path, record)
        else:
            with redirect_stdout(io.StringIO()):
                check_running(name)
        current = optional(name)
        new_target(plan, record, current)
        result = storage.receipt(
            plan,
            current,
            storage.docker(
                "logs", "--since", current["State"]["StartedAt"], "--tail", "10", current["Id"]
            ),
        )
        if preserved(plan, current["Id"]) != record["protectedHash"]:
            storage.reject()
        result.update(
            previousContainerId=old["Id"],
            previousContainerPreserved=True,
            restartPolicy="no",
            status="awaiting-server-mtls-verification",
        )
        phase("ready")
        return result


if __name__ == "__main__":
    try:
        if len(sys.argv) != 3:
            storage.reject()
        print(
            json.dumps(
                run(
                    storage.strict(storage.regular(sys.argv[1])),
                    storage.strict(storage.regular(sys.argv[2])),
                )
            )
        )
    except (
        ValueError,
        KeyError,
        IndexError,
        TypeError,
        OSError,
        tarfile.TarError,
        subprocess.SubprocessError,
    ):
        print(
            "Storage replacement interrupted; preserve both containers and state; resume the same plan.",
            file=sys.stderr,
        )
        raise SystemExit(1)
