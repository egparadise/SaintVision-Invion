"""Test the LAN Bash installer with synthetic PKI and owned Docker storage only."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import socket
import subprocess
import sys
from uuid import uuid4
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def run(args, timeout=60):
    r = subprocess.run([str(v) for v in args], capture_output=True, timeout=timeout)
    if r.returncode:
        raise RuntimeError("Owned test command failed; private diagnostics retained separately")
    return r.stdout.decode().strip()


def main(prepared, bridge_only=False):
    p = json.loads(prepared.read_text())
    name = "sv-storage-bundle-" + uuid4().hex[:12]
    work = ROOT / ".work" / name
    work.mkdir()
    context = work / "context"
    context.mkdir()
    binary = Path(p["work"]) / "context/binaries/inv-node"
    # Reuse a tested Node binary only when its exact Go source still matches.
    for path, expected in p["sourceHashes"].items():
        if path.startswith(("services/node-agent/", "packages/contracts-go/")):
            assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected
    assert hashlib.sha256(binary.read_bytes()).hexdigest() == p["binaryHashes"]["inv-node"]
    shutil.copyfile(binary, context / "inv-node")
    shutil.copyfile(ROOT / "deploy/lan/Dockerfile.node", context / "Dockerfile")
    agent = run(["docker", "build", "-q", context], 180)
    source = (work / "source").resolve()
    source.mkdir()
    # Docker Desktop exposes Windows drives here in its Linux daemon.
    mount = (
        ("/run/desktop/mnt/host/" + source.drive[0].lower() + source.as_posix()[2:])
        if sys.platform == "win32"
        else str(source)
    )
    runner = name + "-runner"
    created = False
    with socket.socket() as available:
        available.bind(("127.0.0.1", 0))
        test_port = available.getsockname()[1]
    try:
        run(
            [
                "docker",
                "create",
                "--name",
                runner,
                "--label",
                "ai.saintvision.storage-test=" + name,
                "--network",
                "none",
                "--pids-limit",
                "256",
                "--memory",
                "768m",
                "--cpus",
                "1",
                "--mount",
                "type=bind,source=/var/run/docker.sock,target=/var/run/docker.sock",
                "--mount",
                f"type=bind,source={source},target={mount}",
                "--env",
                "INV_STORAGE_SOURCE_ROOT=" + mount,
                "--env",
                "INV_STORAGE_AGENT_IMAGE=" + agent,
                "--env",
                "INV_STORAGE_TEST_PORT=" + str(test_port),
                "--entrypoint",
                "python",
                p["kernelImage"],
                "-m",
                "pytest",
                "-x",
                "-q",
                "tests/integration/test_lan_storage_install.py",
                "--junitxml=/evidence/storage.xml",
                *(["-k", "storage_bridge"] if bridge_only else []),
            ]
        )
        created = True
        run(["docker", "cp", ROOT / "deploy/lan", runner + ":/app/deploy/lan"])
        run(
            [
                "docker",
                "cp",
                ROOT / "tests/integration/test_lan_storage_install.py",
                runner + ":/app/tests/integration/test_lan_storage_install.py",
            ]
        )
        r = subprocess.run(["docker", "start", "-a", runner], capture_output=True, timeout=900)
        (work / "private.log").write_bytes(r.stdout + r.stderr)
        run(["docker", "cp", runner + ":/evidence/storage.xml", work / "tests.xml"])
        cases = [
            dict(
                name=c.get("name"),
                passed=not any(c.find(t) is not None for t in ("failure", "error", "skipped")),
            )
            for c in ET.parse(work / "tests.xml").iter("testcase")
        ]
        files = [
            "deploy/lan/worker_storage.py",
            "deploy/lan/worker_replacement.py",
            "deploy/lan/worker_replace.py",
            "deploy/lan/worker_storage_bridge.py",
            "deploy/lan/Replace-Storage.ps1",
            "deploy/lan/start-node.sh",
            "deploy/lan/finish-worker.sh",
            "deploy/lan/Start-Worker.ps1",
            "deploy/lan/worker_config.py",
            "tools/lan_pilot.py",
            "tools/check_storage_bundle.py",
            "tests/integration/test_lan_storage_install.py",
        ]
        proof = dict(
            at=datetime.now(timezone.utc).isoformat(),
            codeSHA=run(["git", "rev-parse", "HEAD"]),
            dirty=bool(run(["git", "status", "--porcelain"])),
            runtimeCodeSHA=p["codeSHA"],
            agentImage=agent,
            scope="isolated-real-docker-new-container-installation-synthetic-pki-not-wsl-or-remote-pc",
            exitCode=r.returncode,
            cases=cases,
            sourceHashes={f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest() for f in files},
        )
        (work / "evidence.json").write_text(json.dumps(proof, indent=2) + "\n")
        print(
            json.dumps(
                dict(evidence=str(work / "evidence.json"), exitCode=r.returncode, cases=cases)
            )
        )
        return (
            r.returncode == 0
            and len(cases) == (1 if bridge_only else 12)
            and all(c["passed"] for c in cases)
        )
    finally:
        if created:
            value = json.loads(run(["docker", "inspect", runner]))[0]
            assert value["Config"]["Labels"]["ai.saintvision.storage-test"] == name
            if value["State"]["Running"]:
                run(["docker", "stop", runner])
            run(["docker", "rm", runner])
        # Retain the isolated source fixture beside its evidence; no host deletion.


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--bridge-only", action="store_true")
    args = parser.parse_args()
    raise SystemExit(0 if main(args.prepared, args.bridge_only) else 1)
