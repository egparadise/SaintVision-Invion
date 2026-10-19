"""Exercise the installed leaf-rotation runtime through the real restart seam.

This hosted-CI helper uses disposable public test certificates and a fake Docker
CLI.  The fake implements the exact cp/restart/inspect calls made by
``worker_config.py``; it never contacts a daemon or a live Node.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "deploy" / "lan" / "worker_leaf_rotation.py"
LAUNCHER = ROOT / "deploy" / "lan" / "leaf_rotation_standalone_runtime.py"


FAKE_DOCKER = r"""#!/usr/bin/env python3
import io
import os
from pathlib import Path
import sys
import tarfile

state = Path(os.environ["INV_FAKE_DOCKER_STATE"])
state.mkdir(parents=True, exist_ok=True)
args = sys.argv[1:]
if args[:3] == ["cp", "-a", "-"] and len(args) == 4 and args[3].endswith(":/state"):
    with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read())) as archive:
        for member in archive.getmembers():
            if not member.isfile() or "/" in member.name or "\\" in member.name:
                raise SystemExit(2)
            target = state / member.name
            target.write_bytes(archive.extractfile(member).read())
            target.chmod(0o600)
    raise SystemExit(0)
if len(args) == 3 and args[0] == "cp" and args[1].startswith("saintvision-") and args[2] == "-":
    name = args[1].rsplit("/", 1)[-1]
    raw = (state / name).read_bytes()
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as archive:
        item = tarfile.TarInfo(name)
        item.size = len(raw)
        item.uid = item.gid = 0
        item.mode = 0o600
        archive.addfile(item, io.BytesIO(raw))
    sys.stdout.buffer.write(stream.getvalue())
    raise SystemExit(0)
if len(args) == 2 and args[0] == "restart" and args[1].startswith("saintvision-"):
    marker = state / "restart-count"
    marker.write_text(str(int(marker.read_text() or "0") + 1) if marker.exists() else "1")
    print(args[1])
    raise SystemExit(0)
if len(args) >= 4 and args[0:2] == ["inspect", "--format"]:
    print("true false 0")
    raise SystemExit(0)
raise SystemExit(2)
"""


def _run(runtime: Path, arguments: list[str], env: dict[str, str]) -> dict:
    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            str(LAUNCHER),
            "run",
            "--runtime-dir",
            str(runtime),
            "--worker-script",
            str(WORKER),
            "--",
            *arguments,
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=90,
    )
    if completed.returncode != 0:
        raise RuntimeError("Standalone lifecycle command failed closed")
    return json.loads(completed.stdout.splitlines()[-1])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-dir", type=Path, required=True)
    args = parser.parse_args()
    definitions = runpy.run_path(str(ROOT / "tests" / "test_lan_leaf_rotation.py"))
    fixture_factory = definitions["_fixture"]
    canonical = definitions["rotation"]._canonical

    with tempfile.TemporaryDirectory(prefix="leaf-runtime-lifecycle-") as value:
        temporary = Path(value)
        fake_bin = temporary / "bin"
        fake_bin.mkdir()
        docker = fake_bin / "docker"
        docker.write_text(FAKE_DOCKER, encoding="utf-8")
        docker.chmod(0o700)
        env = {
            **os.environ,
            "PATH": str(fake_bin) + os.pathsep + os.environ.get("PATH", ""),
            "INV_FAKE_DOCKER_STATE": str(temporary / "fake-docker-state"),
        }

        now = datetime.now(timezone.utc).replace(microsecond=0)
        finalized = fixture_factory(temporary / "finalized", now=now)
        (finalized.worker / "signer.pub").write_bytes(b"\x01" * 32)
        receipt = _run(
            args.runtime_dir,
            ["install", "--bundle", str(finalized.bundle), "--worker-root", str(finalized.worker)],
            env,
        )
        body = {
            "schemaVersion": finalized.manifest["schemaVersion"],
            "rotationId": finalized.manifest["rotationId"],
            "proposalDigest": receipt["proposalDigest"],
            "nodeId": finalized.manifest["nodeId"],
            "channelVersion": finalized.manifest["targetChannelVersion"],
            "certificateSHA256": finalized.manifest["nextNodeCertificateSHA256"],
            "committed": True,
        }
        commit = {
            **body,
            "controlSignature": finalized.control_key.sign(canonical(body)).hex(),
        }
        commit_path = temporary / "commit.json"
        commit_path.write_text(json.dumps(commit), encoding="utf-8")
        final = _run(
            args.runtime_dir,
            [
                "finalize",
                "--bundle",
                str(finalized.bundle),
                "--worker-root",
                str(finalized.worker),
                "--commit-receipt",
                str(commit_path),
            ],
            env,
        )

        rolled_back = fixture_factory(temporary / "rolled-back", now=now)
        (rolled_back.worker / "signer.pub").write_bytes(b"\x02" * 32)
        _run(
            args.runtime_dir,
            [
                "install",
                "--bundle",
                str(rolled_back.bundle),
                "--worker-root",
                str(rolled_back.worker),
            ],
            env,
        )
        rollback = _run(
            args.runtime_dir,
            [
                "rollback",
                "--bundle",
                str(rolled_back.bundle),
                "--worker-root",
                str(rolled_back.worker),
            ],
            env,
        )
        restart_count = int((temporary / "fake-docker-state" / "restart-count").read_text())
        if (
            receipt.get("restartObserved") is not True
            or final.get("finalized") is not True
            or rollback.get("rolledBack") is not True
            or restart_count != 4
            or list(args.runtime_dir.rglob("__pycache__"))
        ):
            raise RuntimeError("Standalone lifecycle observations differ")
        print(
            json.dumps(
                {
                    "installRestartReceipt": True,
                    "finalized": True,
                    "rolledBack": True,
                    "restartCount": restart_count,
                    "bytecodeCacheCount": 0,
                },
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
