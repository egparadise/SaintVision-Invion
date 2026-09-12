"""Real packaged Bash entry point, Docker mounts/copy and Go startup receipt."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
from uuid import uuid4

import pytest
from inv.ids import new_id
from inv.node_channels import node_uri
from inv.tooling import NodePrincipal
from pki_support import authority, issue
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "deploy/lan"))
import worker_storage as storage

pytestmark = pytest.mark.skipif(
    sys.platform != "linux" or not os.getenv("INV_STORAGE_SOURCE_ROOT"),
    reason="Opt-in owned Docker storage installer test",
)


@pytest.fixture
def installation(tmp_path):
    node = new_id("nod")
    tenant = str(uuid4())
    epoch = str(uuid4())
    name = "saintvision-" + node.lower()
    folder = tmp_path / "bundle"
    folder.mkdir()
    source = Path(os.environ["INV_STORAGE_SOURCE_ROOT"]) / ("provided-" + uuid4().hex)
    source.mkdir()
    (source / "data.bin").write_bytes(b"actual contribution bytes")
    ca = authority()
    cert = issue(ca, node_uri(NodePrincipal(tenant, node), epoch), server=True)
    control = issue(ca, f"spiffe://saintvision.ai/tenant/{tenant}/control-plane/epoch/{epoch}")
    originals = {
        "node-cert.pem": cert.pem,
        "node-key.pem": cert.private,
        "ca.pem": ca.pem,
        "signer.pub": Ed25519PrivateKey.generate().public_key().public_bytes_raw(),
    }
    originals["peer-policy.json"] = json.dumps(
        dict(
            version=1,
            tenantId=tenant,
            nodeId=node,
            recoveryEpoch=epoch,
            expiresAt=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            clientFingerprints=[control.fingerprint],
        )
    ).encode()
    for filename, raw in originals.items():
        (folder / filename).write_bytes(raw)
        (folder / filename).chmod(0o600)
    agent = os.environ["INV_STORAGE_AGENT_IMAGE"]
    image = json.loads(storage.docker("image", "inspect", agent))[0]
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    manifest = dict(
        nodeId=node,
        tenantId=tenant,
        epoch=epoch,
        serverIP="127.0.0.2",
        nodeIP="127.0.0.1",
        nodePort=port,
        agentImage=agent,
        agentTag=agent,
        imageLayers=image["RootFS"]["Layers"],
        imageConfig=image["Config"],
    )
    policy = dict(
        channel=dict(
            tenant_id=tenant,
            node_id=node,
            recovery_epoch=epoch,
            version=1,
            endpoint=f"https://127.0.0.1:{port}",
            certificate_sha256=cert.fingerprint,
        ),
        contribution_id=new_id("stc"),
        root_version=1,
        root=storage.TARGET,
    )
    (folder / "manifest.json").write_text(json.dumps(manifest))
    (folder / "storage-policy.json").write_text(json.dumps(policy))
    (folder / "node-agent.tar").write_bytes(storage.docker("save", agent))
    for file in ["start-node.sh", "worker_config.py", "worker_storage.py"]:
        shutil.copyfile(Path(__file__).resolve().parents[2] / "deploy/lan" / file, folder / file)
    try:
        yield dict(folder=folder, source=source, name=name, node=node, originals=originals)
    finally:
        result = subprocess.run(["docker", "inspect", name], capture_output=True)
        if result.returncode == 0:
            owned = json.loads(result.stdout)[0]
            assert owned["Config"]["Labels"]["ai.saintvision.node"] == node
            storage.docker("rm", "-f", name)
        result = subprocess.run(
            ["docker", "volume", "inspect", name + "-state"], capture_output=True
        )
        if result.returncode == 0:
            assert json.loads(result.stdout)[0]["Labels"]["ai.saintvision.node"] == node
            storage.docker("volume", "rm", name + "-state")


def start(a, hash_value=None):
    expected = (
        hash_value or hashlib.sha256((a["folder"] / "storage-policy.json").read_bytes()).hexdigest()
    )
    return subprocess.run(
        ["bash", str(a["folder"] / "start-node.sh"), str(a["source"]), expected],
        capture_output=True,
        timeout=180,
    )


def test_real_bundle_mounts_readonly_copies_policy_and_matches_go_receipt(installation):
    a = installation
    r = start(a)
    assert r.returncode == 0, (
        r.stdout.decode(errors="replace")[-1500:] + r.stderr.decode(errors="replace")[-1500:]
    )
    result = json.loads((a["folder"] / "storage-ready.json").read_text())
    assert result["readOnlyMount"] and not result["operationalAcceptanceAssessed"]
    value = json.loads(storage.docker("inspect", a["name"]))[0]
    mount = next(m for m in value["Mounts"] if m["Destination"] == storage.TARGET)
    assert mount["Source"] == str(a["source"]) and mount["RW"] is False
    assert (a["source"] / "data.bin").read_bytes() == b"actual contribution bytes"
    for name, raw in a["originals"].items():
        assert (a["folder"] / name).read_bytes() == raw
    identity = storage.docker("cp", a["name"] + ":/state/journal/identity.json", "-")
    # Re-running never stops or replaces an existing Node.
    assert start(a).returncode != 0
    assert json.loads(storage.docker("inspect", a["name"]))[0]["Id"] == value["Id"]
    assert storage.docker("cp", a["name"] + ":/state/journal/identity.json", "-") == identity


def test_real_bad_policy_hash_creates_no_node_or_volume(installation):
    a = installation
    assert start(a, "0" * 64).returncode != 0
    assert subprocess.run(["docker", "inspect", a["name"]], capture_output=True).returncode != 0
    assert (
        subprocess.run(
            ["docker", "volume", "inspect", a["name"] + "-state"], capture_output=True
        ).returncode
        != 0
    )


def test_real_replacement_preflight_preserves_state_and_rejects_stale_restart(installation):
    import worker_replacement as replacement

    a = installation
    assert start(a).returncode == 0
    plan = json.loads((a["folder"] / "storage-plan.json").read_text())
    # Running Nodes are not stopped by preflight.
    with pytest.raises(ValueError):
        replacement.capture(plan)
    assert json.loads(storage.docker("inspect", a["name"]))[0]["State"]["Running"]
    storage.docker("stop", a["name"])
    original = replacement.state_archive(a["name"])
    receipt = replacement.capture(plan)
    assert receipt["replacementAuthorized"] is False
    assert receipt["operationalAcceptanceAssessed"] is False
    assert replacement.recheck(plan, receipt) == receipt
    assert replacement.state_digest(original, plan["manifest"]) == receipt["stateSHA256"]
    # A restart invalidates the old inspection even when the same container survives.
    storage.docker("start", a["name"])
    storage.docker("stop", a["name"])
    with pytest.raises(ValueError):
        replacement.recheck(plan, receipt)
    fresh = replacement.capture(plan)
    assert fresh["containerId"] == receipt["containerId"]
    assert fresh["stateSHA256"] == receipt["stateSHA256"]
