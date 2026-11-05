"""Disposable structural proof; never invokes Docker, PKI, or a live Node.

Default exit 0 confirms the current rejection contract. --require-coexistence
exits 1 on the unchanged guarded source: that expected failure is the gap proof.
This does not establish Linux mount enforcement or authenticated storage health.
"""
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "deploy/lan"))
import worker_storage as storage
import worker_workspace as workspace


def rejected(call):
    try:
        call()
    except ValueError as error:
        return str(error)
    raise AssertionError("Unmodified source unexpectedly accepted this fixture")


def probe(directory, *, require_coexistence=False):
    private, source = directory / "private", directory / "provided"
    private.mkdir()
    source.mkdir()
    manifest = dict(nodeId="nod_" + "0" * 26,
                    tenantId="00000000-0000-4000-8000-000000000001",
                    epoch="00000000-0000-4000-8000-000000000002",
                    serverIP="192.0.2.1", nodeIP="192.0.2.2", nodePort=18443)
    policy = dict(channel=dict(tenant_id=manifest["tenantId"], node_id=manifest["nodeId"],
                               recovery_epoch=manifest["epoch"], version=1,
                               endpoint="https://192.0.2.2:18443", certificate_sha256="a" * 64),
                  contribution_id="stc_" + "0" * 26, root_version=1, root=storage.TARGET)
    path = private / "storage-policy.json"
    raw = (json.dumps(policy, indent=2) + "\n").encode()
    path.write_bytes(raw)
    plan = storage.prepare(manifest, path, str(source), storage.digest(raw), "sha256:" + "b" * 64)
    name = "saintvision-" + manifest["nodeId"]
    args = []
    for flag, value in {"--node": manifest["nodeId"], "--tenant": manifest["tenantId"],
                        "--epoch": manifest["epoch"], "--state": "/state/journal",
                        "--public-key": "/state/signer.pub", "--tls-key": "/state/node-key.pem",
                        "--tls-cert": "/state/node-cert.pem", "--client-ca": "/state/ca.pem",
                        "--peer-policy": "/state/peer-policy.json", "--profile": "lan-observe-v1",
                        "--image": plan["image"], "--executable": "/inv-node"}.items():
        args.extend([flag, value])
    state = dict(Destination="/state", Type="volume", Name=name + "-state", RW=True)
    contribution = dict(Destination=storage.TARGET, Type="bind", Source=str(source),
                        RW=False, Propagation="rprivate")
    socket = dict(Destination="/var/run/docker.sock", Type="bind", Source="/var/run/docker.sock",
                  RW=True, Propagation="rprivate")
    plain = dict(Id="c" * 64, Name="/" + name, Image=plan["image"], RestartCount=0,
                 Config=dict(User="", Labels={"ai.saintvision.node": manifest["nodeId"]}, Cmd=args),
                 State=dict(Status="created", Running=False, Restarting=False),
                 HostConfig=dict(ReadonlyRootfs=True, Privileged=False,
                                 Mounts=[dict(Target=storage.TARGET, BindOptions=dict(NonRecursive=True))]),
                 Mounts=[state])
    before = deepcopy(plain)
    assert workspace.validate_install_target(manifest, plain) == args
    plain["Mounts"].append(deepcopy(socket))
    assert workspace.validate_install_target(manifest, plain) == args
    storage_only = deepcopy(before)
    storage_only["Config"]["Cmd"] += ["--storage-policy", storage.POLICY]
    storage_only["Mounts"].append(deepcopy(contribution))
    storage.target(plan, storage_only)
    snapshot = deepcopy(storage_only)
    if require_coexistence:
        # A real acceptance requirement, evaluated against unmodified source.
        # Today this call raises ValueError; no manufactured failing assertion.
        workspace.validate_install_target(manifest, storage_only)
        workspace_reason = None
    else:
        workspace_reason = rejected(lambda: workspace.validate_install_target(manifest, storage_only))
    assert storage_only == snapshot and path.read_bytes() == raw
    combined = deepcopy(storage_only)
    combined["Mounts"].append(deepcopy(socket))
    combined["Config"]["Cmd"][combined["Config"]["Cmd"].index("--profile") + 1] = workspace.PROFILE
    combined_snapshot = deepcopy(combined)
    if require_coexistence:
        storage.target(plan, combined)
        storage_reason = None
    else:
        storage_reason = rejected(lambda: storage.target(plan, combined))
    assert combined == combined_snapshot and path.read_bytes() == raw
    # The guard also refuses aliases/equals spellings instead of dropping them.
    aliases = ["--storage-policy=" + storage.POLICY, "-storage-policy", "-storage-policy=" + storage.POLICY]
    for alias in aliases:
        invalid = deepcopy(before)
        invalid["Config"]["Cmd"] += [alias]
        rejected(lambda: workspace.validate_install_target(manifest, invalid))
    return dict(scope="synthetic-source-validator-only", policyBytesPreserved=True,
                plainStateOnlyAccepted=True, plainDefaultSocketAccepted=True,
                storageOnlyAccepted=True, workspaceStorageRejected=workspace_reason,
                storageWithWorkspaceSocketRejected=storage_reason, aliasesRejected=len(aliases),
                activeStorageAssessed=False, linuxMountEnforcementAssessed=False,
                sourceSHA256={name: hashlib.sha256((ROOT / "deploy/lan" / name).read_bytes()).hexdigest()
                              for name in ("worker_workspace.py", "worker_storage.py", "worker_config.py")})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-coexistence", action="store_true")
    args = parser.parse_args()
    try:
        with TemporaryDirectory(prefix="sv-fleet5-contract-fixture-") as directory:
            result = probe(Path(directory), require_coexistence=args.require_coexistence)
    except ValueError as error:
        if not args.require_coexistence:
            raise
        print(json.dumps(dict(scope="synthetic-source-validator-only", expectedFailure=True,
                              coexistenceSupported=False, rejectedByUnmodifiedSource=str(error)), indent=2))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
