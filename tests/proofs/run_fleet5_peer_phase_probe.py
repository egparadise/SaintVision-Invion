"""Opt-in CI-only native Go proof using exact accepted Python generator output.

No Docker/SSH/WSL, production PKI or live state. Fixture keys exist only in an
owned runner temporary directory, and are NEVER part of the public artifact.
The intended baseline mismatch exits 1; setup/compile/wrong-cause failures exit 2.
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "2fb52bbe5e500354b323eb8e46d5aa5066690d2d"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def check_source():
    paths = ["tools/lan_pilot.py", "tools/lan_pki.py", "deploy/lan/worker_leaf_rotation.py",
             "tests/test_lan_leaf_rotation.py"]
    listing = subprocess.run(["git", "ls-tree", "-r", "--name-only", SOURCE,
                              "services/node-agent", "packages/contracts-go"],
                             cwd=ROOT, capture_output=True, check=True).stdout.decode().splitlines()
    paths += [p for p in listing if p.endswith((".go", ".json", "go.mod", "go.sum"))]
    rows = []
    for relative in paths:
        expected = subprocess.run(["git", "cat-file", "blob", SOURCE + ":" + relative],
                                  cwd=ROOT, capture_output=True, check=True).stdout
        actual = (ROOT / relative).read_bytes().replace(b"\r\n", b"\n")
        if expected != actual:
            raise ValueError("Proof source differs from accepted source: " + relative)
        rows.append(dict(path=relative, sha256=digest(expected)))
    return rows


def fixtures(directory):
    sys.path[:0] = [str(ROOT / "tests"), str(ROOT / "tools"), str(ROOT / "deploy/lan")]
    from cryptography import x509
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    import lan_pilot
    from lan_pki import fingerprint, issue, pem, private_pem
    from test_lan_leaf_rotation import _ca

    now = datetime.now(timezone.utc).replace(microsecond=0)
    _, root, issuer_key, issuer = _ca(now)
    chain = pem(issuer) + pem(root)
    node_key, control_key = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
    tenant, epoch, node_id = "00000000-0000-4000-8000-000000000001", "00000000-0000-4000-8000-000000000002", "nod_" + "0" * 26
    state, node = dict(tenantId=tenant, epoch=epoch), dict(nodeId=node_id, nodeIP="192.0.2.2")
    current_node = issue(issuer_key, issuer, node_key.public_key(),
                         f"spiffe://saintvision.ai/tenant/{tenant}/node/{node_id}/epoch/{epoch}",
                         address=node["nodeIP"], now=now, valid_for=timedelta(hours=6))
    current_control = issue(issuer_key, issuer, control_key.public_key(),
                            f"spiffe://saintvision.ai/tenant/{tenant}/control-plane/epoch/{epoch}",
                            now=now, valid_for=timedelta(hours=6))
    (directory / "ca.pem").write_bytes(chain)
    (directory / "node-key.pem").write_bytes(private_pem(node_key))
    initial = dict(version=7, tenantId=tenant, nodeId=node_id, recoveryEpoch=epoch,
                   expiresAt=(now + timedelta(hours=5)).isoformat().replace("+00:00", "Z"),
                   clientFingerprints=[fingerprint(current_control)])
    (directory / "initial-peer.json").write_text(json.dumps(initial), encoding="utf-8")
    cycles = []
    public = []
    for index in (1, 2):
        folder = directory / f"cycle-{index}"
        raw, manifest, material = lan_pilot._write_rotation_public_material(
            folder, state=state, node=node, current_node=current_node, current_control=current_control,
            control_key=control_key, public_key=node_key.public_key(), ca_key=issuer_key,
            intermediate=issuer, chain_raw=chain, revocations=set(), now=now,
            current_version=6 + index, overlap_seconds=3600, leaf_valid_seconds=21600,
            rotation_id=str(index) * 32)
        # Exact unmodified helper validation of BOTH generated phase files.
        for phase, pins, expiry in (
            ("overlap", [fingerprint(current_control), manifest["nextControlCertificateSHA256"]], manifest["overlapExpiresAt"]),
            ("final", [manifest["nextControlCertificateSHA256"]], manifest["certificateNotAfter"]),
        ):
            lan_pilot.worker_rotation._policy(material[f"peer-policy-{phase}.json"],
                                              manifest=manifest, fingerprints=pins, expires=expiry)
        cycles.append(dict(Index=index, Overlap=f"cycle-{index}/peer-policy-overlap.json",
                           Final=f"cycle-{index}/peer-policy-final.json", Certificate=f"cycle-{index}/node-cert.pem",
                           DER_SHA256=manifest["nextNodeCertificateSHA256"]))
        overlap_value = json.loads(material["peer-policy-overlap.json"])
        final_value = json.loads(material["peer-policy-final.json"])
        public.append(dict(cycle=index, manifestSHA256=digest(raw), manifest=manifest,
                           overlapPolicySHA256=digest(material["peer-policy-overlap.json"]),
                           finalPolicySHA256=digest(material["peer-policy-final.json"]),
                           phaseVersionsEqual=overlap_value["version"] == final_value["version"],
                           phaseBytesDiffer=material["peer-policy-overlap.json"] != material["peer-policy-final.json"]))
        current_node = x509.load_pem_x509_certificate(material["node-cert.pem"])
        current_control = x509.load_pem_x509_certificate(material["control-cert.pem"])
    expired = json.loads((directory / cycles[-1]["Final"]).read_bytes())
    expired.update(version=10, expiresAt=(now - timedelta(seconds=60)).isoformat().replace("+00:00", "Z"))
    (directory / "expired-after-pin.json").write_text(json.dumps(expired), encoding="utf-8")
    (directory / "fixture.json").write_text(json.dumps(dict(TenantID=tenant, NodeID=node_id, Epoch=epoch, Cycles=cycles)), encoding="utf-8")
    for path in directory.rglob("*"):
        path.chmod(0o700 if path.is_dir() else 0o600)
    return public


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check-source-only", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    rows = check_source()
    receipt = dict(sourceSHA=SOURCE, headSHA=subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                   capture_output=True, text=True, check=True).stdout.strip(), sourceBindings=rows,
                   scope="source-only" if args.check_source_only else "ci-fixture-native-go-peer-phase",
                   hostDockerUsed=False, privateFixtureKeysUploaded=False, operationalAcceptanceAssessed=False)
    if args.check_source_only:
        (args.output / "source-check.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        print("Exact accepted source bindings verified; no fixture PKI or Go runtime invoked.")
        return 0
    if sys.platform != "linux" or os.environ.get("GITHUB_ACTIONS") != "true":
        raise ValueError("Fixture PKI/native proof is restricted to the isolated Linux CI runner")
    module = ROOT / "services/node-agent"
    test_source = ROOT / "tests/proofs/fleet5_peer_phase_probe_test.go"
    target = module / "transport/fleet5_peer_phase_generated_proof_test.go"
    if target.exists():
        raise ValueError("Proof test target already exists; no overwrite permitted")
    original = test_source.read_bytes()
    with TemporaryDirectory(prefix="fleet5-native-peer-fixture-") as temporary:
        fixture = Path(temporary)
        fixture.chmod(0o700)
        receipt["generatedCycles"] = fixtures(fixture)
        result_file = (args.output / "native-go-result.json").resolve()
        env = dict(os.environ, FLEET5_PEER_PROOF_FIXTURE=str(fixture), FLEET5_PEER_PROOF_REPORT=str(result_file))
        with target.open("xb") as stream:
            stream.write(original)
        try:
            with (args.output / "go-events.jsonl").open("wb") as log:
                result = subprocess.run(["go", "test", "-json", "./transport", "-run",
                                         "^TestFleet5GeneratedPeerPoliciesCompleteTwoNormalCycles$", "-count=1"],
                                        cwd=module, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=180)
        finally:
            if target.read_bytes() != original:
                raise ValueError("Created proof target changed; preserved for inspection")
            target.unlink()  # Only this newly-created, exact-byte CI fixture test.
        receipt["goTestExit"] = result.returncode
        observed = json.loads(result_file.read_text("utf-8")) if result_file.exists() else {}
        valid_red = result.returncode == 1 and observed.get("proofValid") is True and observed.get("baselineMismatchConfirmed") is True
        receipt["classification"] = "expected-baseline-contract-mismatch" if valid_red else "invalid-proof-or-unexpected-result"
        receipt["proofValid"] = valid_red
        (args.output / "publication-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({k: receipt[k] for k in ("sourceSHA", "headSHA", "goTestExit", "classification", "proofValid")}))
        return 1 if valid_red else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print("Native proof setup failed: " + str(error), file=sys.stderr)
        raise SystemExit(2)
