"""Stage one immutable request in existing WSL Node state; apply by exact hash."""

import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tarfile
from uuid import uuid4

import worker_storage as storage
import worker_replacement as preflight
import worker_replace as replacement
from worker_config import same_identity, image_id


def bridge(mode, bundle, source, policy_hash, request_hash=None):
    if mode not in ("prepare", "apply") or (mode == "apply") != (request_hash is not None):
        storage.reject()
    if request_hash is not None and not re.fullmatch(r"[0-9a-f]{64}", request_hash):
        storage.reject()
    bundle = Path(bundle)
    manifest = storage.strict(storage.regular(bundle / "manifest.json"))
    node = manifest["nodeId"]
    if not re.fullmatch(r"nod_[0-9A-HJKMNP-TV-Z]{26}", node):
        storage.reject()
    root = Path.home() / ".local/share/saintvision" / node
    # Existing identity is authoritative; no enrollment or key copying here.
    same_identity(storage.strict(storage.regular(root / "manifest.json")), manifest)
    raw = storage.regular(bundle / "storage-policy.json")
    if storage.digest(raw) != policy_hash:
        storage.reject()
    # Validate scope and source before importing an image or writing staged inputs.
    storage.prepare(
        manifest, bundle / "storage-policy.json", source, policy_hash, manifest["agentImage"]
    )
    storage.source_identity(source, root)
    with replacement.locked(root):
        stage = root / "storage-replacement-input"
        if not stage.exists():
            if mode != "prepare":
                storage.reject()
            stage.mkdir(mode=0o700)
            replacement.sync_directory(root)
        with replacement.locked(stage):
            path = stage / "request.json"
            if path.exists() or path.is_symlink():
                info = path.lstat()
                if info.st_uid != os.geteuid() or info.st_mode & 0o077:
                    storage.reject()
                original = storage.regular(path)
                request = storage.strict(original)
                plan = request["plan"]
                storage.current(plan)
                if (
                    plan["manifest"] != manifest
                    or plan["source"] != str(Path(source).absolute())
                    or plan["policySHA256"] != policy_hash
                    or plan["policyPath"] != str(stage / "storage-policy.json")
                ):
                    storage.reject()
            else:
                if mode != "prepare" or (stage / "storage-replacement.json").exists():
                    storage.reject()
                archive = bundle / "node-agent.tar"
                if not stat.S_ISREG(archive.lstat().st_mode):
                    storage.reject()
                result = subprocess.run(
                    ["docker", "load", "-i", str(archive)], capture_output=True, timeout=180
                )
                if result.returncode:
                    storage.reject()
                image = image_id(
                    manifest,
                    storage.strict(storage.docker("image", "inspect", manifest["agentTag"]))[0],
                )
                policy = stage / "storage-policy.json"
                if policy.exists() or policy.is_symlink():
                    if storage.regular(policy) != raw:
                        storage.reject()
                else:
                    temporary = stage / (".policy-" + uuid4().hex + ".tmp")
                    fd = os.open(
                        temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
                    )
                    with os.fdopen(fd, "wb") as stream:
                        stream.write(raw)
                        stream.flush()
                        os.fsync(stream.fileno())
                    os.link(temporary, policy)
                    temporary.unlink()
                replacement.sync_directory(stage)
                plan = storage.prepare(manifest, policy, source, policy_hash, image)
                request = dict(plan=plan, receipt=preflight.capture(plan))
                replacement.save(path, request)
                original = storage.regular(path)
            digest = storage.digest(original)
            if mode == "apply" and digest != request_hash:
                storage.reject()
        # Release the stage lock before the executor takes the same lock itself.
        # The root lock continues serializing bridge prepare/apply invocations.
        common = dict(
            nodeId=node,
            tenantId=manifest["tenantId"],
            recoveryEpoch=manifest["epoch"],
            policySHA256=policy_hash,
            requestSHA256=digest,
            operationalAcceptanceAssessed=False,
        )
        if mode == "prepare":
            return dict(common, status="prepared", replacementAuthorized=False)
        outcome = replacement.run(request["plan"], request["receipt"])
        if (
            outcome["nodeId"] != node
            or outcome["operationalAcceptanceAssessed"] is not False
            or outcome["storagePolicy"]["policySha256"] != policy_hash
            or not outcome["previousContainerPreserved"]
        ):
            storage.reject()
        return dict(
            common,
            status="awaiting-server-mtls-verification",
            containerId=outcome["containerId"],
            previousContainerId=outcome["previousContainerId"],
            restartPolicy="no",
        )


if __name__ == "__main__":
    try:
        if len(sys.argv) not in (5, 6):
            storage.reject()
        print(json.dumps(bridge(*sys.argv[1:])))
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
            "Storage bridge rejected or interrupted; preserve existing Node state and retry the same request.",
            file=sys.stderr,
        )
        raise SystemExit(1)
