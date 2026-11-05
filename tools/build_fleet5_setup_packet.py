"""Build a new exact-source FLEET5 packet without executing any setup action.

Only committed Git blobs are read. No operator state, credentials, issuers,
legacy packets, Docker, transport, system configuration or external API is used.
Outputs go exclusively to this worktree's ignored task-owned directory.
"""

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile


ROOT = Path(__file__).resolve().parents[1]
TASK = "FLEET5-SETUP-INTEGRATION-20261105"
PLAN = "docs/vault/30_Development/Evidence/fleet5-setup-integration-20261105-codex/setup-plan.json"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def build(source):
    if not re.fullmatch(r"[0-9a-f]{40}", source):
        raise ValueError("An exact full source commit SHA is required")
    if git("rev-parse", source + "^{commit}").decode().strip() != source:
        raise ValueError("Source commit does not resolve exactly")
    work = ROOT / ".work" / "fleet5-setup-integration"
    if any(p.is_symlink() for p in (ROOT / ".work", work)):
        raise ValueError("Task output directory must not be redirected")
    work.mkdir(parents=True, exist_ok=True)
    output = work / ("packet-" + source)
    output.mkdir(exist_ok=False)  # Preserve any prior or partial attempt.
    archive = output / ("fleet5-candidate-source-" + source + ".zip")
    subprocess.run(["git", "archive", "--format=zip", "--output=" + str(archive), source], cwd=ROOT, check=True)
    expected = {}
    for entry in git("ls-tree", "-rz", "--full-tree", source).split(b"\0"):
        if not entry:
            continue
        metadata, name = entry.split(b"\t", 1)
        mode, kind, blob = metadata.split()
        if kind != b"blob":
            raise ValueError("Unsupported non-blob source tree entry")
        expected[name.decode("utf-8")] = {"gitBlobSHA1": blob.decode(), "mode": mode.decode()}
    inventory = []
    with zipfile.ZipFile(archive) as bundle:
        files = [item for item in bundle.infolist() if not item.is_dir()]
        names = [item.filename for item in files]
        if len(names) != len(set(names)) or set(names) != set(expected):
            raise ValueError("Source archive omits, adds or duplicates Git tree paths")
        for item in sorted(files, key=lambda value: value.filename):
            raw = bundle.read(item)
            # Git object identity comparison, never an authentication signature.
            blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw, usedforsecurity=False).hexdigest()
            if blob != expected[item.filename]["gitBlobSHA1"]:
                raise ValueError("Source archive bytes differ from Git blob: " + item.filename)
            inventory.append({"path": item.filename, **expected[item.filename], "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
        plan_raw = bundle.read(PLAN)
    plan = json.loads(plan_raw)
    if (
        plan["taskId"] != TASK
        or plan["executed"] is not False
        or plan["actualF5"]["queryExecuted"] is not False
        or any(value is not None for value in plan["actualF5"]["counts"].values())
        or plan["actualF5"]["physicalAcceptance"] is not False
    ):
        raise ValueError("Packet plan makes an unsupported execution/acceptance claim")
    inventory_raw = canonical(inventory)
    manifest = {
        "schemaVersion": "fleet5-exact-source-packet-manifest:1",
        "taskId": TASK,
        "createdAtKST": datetime.now().astimezone().isoformat(),
        "sourceCommit": source,
        "sourceTree": git("rev-parse", source + "^{tree}").decode().strip(),
        "sourceArchive": {"name": archive.name, "bytes": archive.stat().st_size, "sha256": sha256(archive)},
        "archiveInventory": {"name": "source-inventory.json", "entries": len(inventory), "sha256": hashlib.sha256(inventory_raw).hexdigest(), "everyGitBlobCompared": True},
        "setupPlan": {"sourcePath": PLAN, "packetPath": "setup-plan.json", "sha256": hashlib.sha256(plan_raw).hexdigest(), "executed": False},
        "source59fFrozenArchiveOpenedOrModified": False,
        "physicalAcceptance": False,
        "wholeProductAcceptance": False,
        "independentCombinedReview": "separate actual reviewer report required; this builder makes no review assertion",
        "candidateCI": "separate exact-source all-eight workflow evidence required",
    }
    manifest_raw = canonical(manifest)
    (output / "candidate-source-manifest.json").write_bytes(manifest_raw)
    (output / "source-inventory.json").write_bytes(inventory_raw)
    (output / "setup-plan.json").write_bytes(plan_raw)
    packet = output / ("fleet5-nonexecuting-setup-" + source + ".zip")
    with zipfile.ZipFile(packet, "x", compression=zipfile.ZIP_STORED) as bundle:
        bundle.write(archive, archive.name)
        bundle.writestr("candidate-source-manifest.json", manifest_raw)
        bundle.writestr("source-inventory.json", inventory_raw)
        bundle.writestr("setup-plan.json", plan_raw)
        bundle.writestr("NOTICE.txt", "NONEXECUTING REVIEW PACKET. No physical or product acceptance. No keys, enrollment, database, runtime, firewall or remote actions were performed.\n")
    # Re-read the actual delivered packet and compare every member to its input.
    with zipfile.ZipFile(packet) as bundle:
        if (
            hashlib.sha256(bundle.read(archive.name)).hexdigest() != manifest["sourceArchive"]["sha256"]
            or bundle.read("candidate-source-manifest.json") != manifest_raw
            or bundle.read("source-inventory.json") != inventory_raw
            or bundle.read("setup-plan.json") != plan_raw
            or bundle.testzip() is not None
        ):
            raise ValueError("Final packet readback differs")
    receipt = {"sourceCommit": source, "packet": packet.name, "bytes": packet.stat().st_size, "sha256": sha256(packet), "manifestSHA256": hashlib.sha256(manifest_raw).hexdigest(), "packetReadbackVerified": True, "executed": False}
    (output / "packet-receipt.json").write_bytes(canonical(receipt))
    print(json.dumps({"directory": str(output), **receipt}, indent=2))
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    build(parser.parse_args().source)
