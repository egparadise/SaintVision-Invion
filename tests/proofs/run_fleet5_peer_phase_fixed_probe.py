"""CI-only :3 proof: real inv-node process, real journal, signed observer and mTLS.

Docker ownership is covered by the separate provisioned integration case; this
early proof uses a real native process with an explicit fixture transport adapter.
No real-Go acknowledgement, policy floor, expiry or TLS authority is mocked.
"""
import argparse
import ast
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import http.client
import json
import os
from pathlib import Path
import shutil
import socket
import ssl
import subprocess
import sys
from tempfile import TemporaryDirectory
import time

ROOT = Path(__file__).resolve().parents[2]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def run_proof(output):
    if sys.platform != "linux" or os.environ.get("GITHUB_ACTIONS") != "true":
        raise ValueError("Real runtime/fixture PKI proof is restricted to isolated Linux CI")
    sys.path[:0] = [str(ROOT / "tests"), str(ROOT / "tools"), str(ROOT / "deploy/lan")]
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    import lan_pilot
    import worker_leaf_rotation as worker
    import peer_policy_phase as phase
    from lan_pki import issue, pem, private_pem, fingerprint
    from test_lan_leaf_rotation import _ca

    output.mkdir(parents=True, exist_ok=True)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    result = dict(headSHA=head, scope="native-go-plain-peer-phase-fixture", runtimeGOOS="linux",
                  completedNormalCycles=0, floors=[], events=[], productionDockerOwnershipAssessed=False,
                  actualPostgresCASAssessed=False, privateFixtureKeysUploaded=False, operationalAcceptanceAssessed=False)
    with TemporaryDirectory(prefix="fleet5-fixed-native-") as temporary:
        temp = Path(temporary)
        temp.chmod(0o700)
        binary = temp / "inv-node"
        subprocess.run(["go", "build", "-o", str(binary), "./cmd/inv-node"], cwd=ROOT / "services/node-agent", check=True, timeout=180)
        now = datetime.now(timezone.utc).replace(microsecond=0)
        _, root_ca, issuer_key, issuer = _ca(now)
        chain = pem(issuer) + pem(root_ca)
        node_key, control_key = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
        tenant, epoch, node_id = "00000000-0000-4000-8000-000000000001", "00000000-0000-4000-8000-000000000002", "nod_" + "0" * 26
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        state, node = dict(tenantId=tenant, epoch=epoch), dict(nodeId=node_id, nodeIP="127.0.0.1", nodePort=port)
        current_node = issue(issuer_key, issuer, node_key.public_key(), f"spiffe://saintvision.ai/tenant/{tenant}/node/{node_id}/epoch/{epoch}", address="127.0.0.1", now=now, valid_for=timedelta(hours=6))
        current_control = issue(issuer_key, issuer, control_key.public_key(), f"spiffe://saintvision.ai/tenant/{tenant}/control-plane/epoch/{epoch}", now=now, valid_for=timedelta(hours=6))
        folder = temp / "worker"
        folder.mkdir(mode=0o700)
        initial_policy = dict(version=7, tenantId=tenant, nodeId=node_id, recoveryEpoch=epoch,
                              expiresAt=(now + timedelta(hours=5)).isoformat().replace("+00:00", "Z"), clientFingerprints=[fingerprint(current_control)])
        for name, raw in {"ca.pem": chain, "node-key.pem": private_pem(node_key), "node-cert.pem": pem(current_node),
                          "signer.pub": os.urandom(32), "peer-policy.json": json.dumps(initial_policy).encode(),
                          "manifest.json": json.dumps(dict(nodeId=node_id, tenantId=tenant, epoch=epoch, serverIP="127.0.0.2", nodeIP="127.0.0.1", nodePort=port)).encode()}.items():
            (folder / name).write_bytes(raw)
            (folder / name).chmod(0o600)
        control_private = temp / "control-key.pem"
        control_private.write_bytes(private_pem(control_key)); control_private.chmod(0o600)
        old_control_file = temp / "control-initial.pem"
        old_control_file.write_bytes(pem(current_control))
        cp_policy_raw = (folder / "peer-policy.json").read_bytes()
        process = None
        log = (temp / "server.log").open("wb")
        arguments = [str(binary), "--serve", "--listen", f"127.0.0.1:{port}", "--tenant", tenant, "--node", node_id, "--epoch", epoch,
                     "--profile", "lan-observe-v1", "--image", "sha256:" + "a" * 64, "--executable", "/inv-node",
                     "--state", str(folder / "journal"), "--public-key", str(folder / "signer.pub"),
                     "--tls-cert", str(folder / "node-cert.pem"), "--tls-key", str(folder / "node-key.pem"),
                     "--client-ca", str(folder / "ca.pem"), "--peer-policy", str(folder / "peer-policy.json")]

        def stop():
            nonlocal process
            if process is not None and process.poll() is None:
                process.terminate()
                try: process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait(timeout=5)

        def start(_root=None):
            nonlocal process
            stop()
            process = subprocess.Popen(arguments, stdout=log, stderr=log)
            for _ in range(100):
                if process.poll() is not None:
                    raise ValueError("Actual inv-node startup failed: " + (temp / "server.log").read_text("utf-8")[-1200:])
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=.2):
                        return
                except OSError:
                    time.sleep(.05)
            raise ValueError("Actual inv-node listener did not start")

        def floor(_root=None, manifest=None, files=None):
            nonce = os.urandom(32).hex()
            raw = subprocess.run([str(binary), "--observe-peer-policy-floor", "--tenant", tenant, "--node", node_id, "--epoch", epoch,
                                  "--state", str(folder / "journal"), "--peer-policy", str(folder / "peer-policy.json"),
                                  "--tls-cert", str(folder / "node-cert.pem"), "--tls-key", str(folder / "node-key.pem"),
                                  "--peer-floor-nonce", nonce, "--peer-floor-serving-pid", str(process.pid)],
                                 capture_output=True, check=True, timeout=10).stdout
            value = phase.strict(raw)
            phase.verify_floor(value, (folder / "node-cert.pem").read_bytes(), {"tenantId": tenant, "nodeId": node_id, "epoch": epoch}, nonce=nonce)
            return value

        def heartbeat(certificate, expected_der, *, accepted=True):
            context = ssl.create_default_context(cafile=str(folder / "ca.pem"))
            context.load_cert_chain(str(certificate), str(control_private))
            connection = http.client.HTTPSConnection("127.0.0.1", port, context=context, timeout=3)
            try:
                connection.connect()
                if sha(connection.sock.getpeercert(binary_form=True)) != expected_der:
                    raise ValueError("Actual server DER differs from expected native phase")
                connection.request("POST", "/v1/heartbeats", body=json.dumps({"nonce": base64.b64encode(os.urandom(32)).decode()}), headers={"Content-Type": "application/json"})
                response = connection.getresponse()
                body = response.read()
                if response.status != 200:
                    raise ValueError("mTLS heartbeat rejected")
                if not accepted:
                    raise AssertionError("Old CP certificate remained authorized after final trust narrowing")
                assert json.loads(body)["nodeId"] == node_id
            except (ssl.SSLError, OSError, http.client.HTTPException, ValueError):
                if accepted:
                    raise
            finally:
                connection.close()

        # Fixture transport adapter replaces Docker only. The runtime observer,
        # journal, floor, listener, TLS and every acknowledgement are real Go.
        worker.observe_actual_floor = floor
        worker.floor_target_context = lambda _root: dict(nodeId=node_id, containerId=sha(b"native-fixture-container"), image="sha256:" + sha(binary.read_bytes()),
            configSHA256=sha(phase.canonical(arguments)), mountsSHA256=sha(b"native-fixture-no-docker-mount-claim"),
            volumeSHA256=sha(str(folder).encode()), consumers=[sha(b"native-fixture-container")])
        try:
            start()
            initial = floor()
            assert initial["peerPolicyVersion"] == 7
            result["floors"].append(initial)
            result["expiryBeforeWriteRejected"] = False
            result["rollbackAfterHandshakePinRejected"] = False
            result["sameProposalRetryFrozen"] = False
            result["predecessorResidueRejected"] = False
            result["predecessorExactReplaySettled"] = False
            for cycle in (1, 2):
                observation = floor()
                bundle = temp / f"cycle-{cycle}"
                current_raw = (folder / "node-cert.pem").read_bytes()
                generation_now = datetime.now(timezone.utc)
                kwargs = dict(state=state, node=node, current_node=x509.load_pem_x509_certificate(current_raw), current_control=current_control,
                              control_key=control_key, public_key=node_key.public_key(), ca_key=issuer_key, intermediate=issuer,
                              chain_raw=chain, revocations=set(), now=generation_now, current_version=6 + cycle, overlap_seconds=3600,
                              leaf_valid_seconds=21600, rotation_id=str(cycle) * 32, peer_floor_observation=observation,
                              peer_floor_nonce=observation["nonce"], current_policy_raw=cp_policy_raw, current_node_raw=current_raw)
                # Production generator rejects CP/floor mismatch before signing/writing.
                bad = temp / f"mismatched-cp-{cycle}"
                altered = dict(phase.strict(cp_policy_raw), version=6)
                try: lan_pilot._write_rotation_public_material(bad, **{**kwargs, "current_policy_raw": phase.canonical(altered)})
                except ValueError as error:
                    assert "CP-recorded peer policy differs" in str(error) and not bad.exists()
                else: raise AssertionError("CP/floor mismatch admitted")
                result["floorCPMismatchRejected"] = True
                raw, manifest, files = lan_pilot._write_rotation_public_material(bundle, **kwargs)
                assert manifest["currentPeerPolicyVersion"] == (7 if cycle == 1 else 9)
                assert manifest["targetChannelVersion"] == 7 + cycle
                if cycle == 1:
                    # Strict old 2fb reader refuses :3 before active state mutation.
                    import importlib.util
                    old_path = temp / "old-reader.py"
                    old_path.write_bytes(subprocess.run(["git", "cat-file", "blob", "2fb52bbe5e500354b323eb8e46d5aa5066690d2d:deploy/lan/worker_leaf_rotation.py"], cwd=ROOT, capture_output=True, check=True).stdout)
                    spec = importlib.util.spec_from_file_location("actual_2fb_reader", old_path)
                    old = importlib.util.module_from_spec(spec); spec.loader.exec_module(old)
                    before_policy = (folder / "peer-policy.json").read_bytes()
                    try: old.install(bundle, folder, restart=lambda _: (_ for _ in ()).throw(AssertionError("old reader reached mutation")))
                    except ValueError as error: assert "manifest shape" in str(error)
                    else: raise AssertionError("2fb reader admitted :3")
                    assert (folder / "peer-policy.json").read_bytes() == before_policy and not (folder / "leaf-rotation.json").exists()
                    result["strictOldReaderRejected"] = True
                    expired = temp / "expired-before-write"
                    shutil.copytree(bundle, expired)
                    invalid = dict(manifest, overlapExpiresAt=(datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat().replace("+00:00", "Z"))
                    (expired / "rotation.json").write_bytes(phase.canonical(invalid))
                    try: worker.install(expired, folder, restart=start)
                    except ValueError as error: assert "validity window" in str(error)
                    else: raise AssertionError("Expired candidate reached active write")
                    assert (folder / "peer-policy.json").read_bytes() == before_policy and floor()["peerPolicyVersion"] == 7
                    result["expiryBeforeWriteRejected"] = True
                    # Real handshake pins P+1 on the old running process before
                    # restart/receipt. The durable publication intent must forbid rollback.
                    def kill(point):
                        if point == "after-overlap-publication":
                            heartbeat(old_control_file, manifest["nextNodeCertificateSHA256"])
                            assert floor()["peerPolicyVersion"] == 8
                            raise RuntimeError("owned fixture publication fault after real handshake pin")
                    try: worker.install(bundle, folder, restart=start, kill=kill)
                    except RuntimeError: pass
                    else: raise AssertionError("Native publication fault did not execute")
                    pinned = floor()
                    try: worker.rollback(bundle, folder, restart=start)
                    except ValueError as error: assert "forward-only" in str(error)
                    else: raise AssertionError("Automatic/explicit old rollback admitted after possible publication")
                    assert floor()["peerPolicySHA256"] == pinned["peerPolicySHA256"]
                    result["rollbackAfterHandshakePinRejected"] = True
                else:
                    prior_archive = folder / "leaf-rotation-finalized" / ("1" * 32 + ".json")
                    original_archive = prior_archive.read_bytes()
                    prior_archive.with_name(prior_archive.name + ".next").write_bytes(original_archive)
                    prior_archive.with_name(prior_archive.name + ".next").chmod(0o600)
                    before_journal = (folder / "leaf-rotation.json").read_bytes()
                    try: worker.install(bundle, folder, restart=start)
                    except ValueError as error: assert "Predecessor staging residue" in str(error)
                    else: raise AssertionError("Successor ignored .next residue")
                    assert (folder / "leaf-rotation.json").read_bytes() == before_journal
                    result["predecessorResidueRejected"] = True
                    worker.finalize(temp / "cycle-1", folder, temp / "commit-1.json", restart=start)
                    assert prior_archive.read_bytes() == original_archive and not prior_archive.with_name(prior_archive.name + ".next").exists()
                    result["predecessorExactReplaySettled"] = True
                installed = worker.install(bundle, folder, restart=start)
                overlap = floor()
                assert overlap["peerPolicyVersion"] == 6 + cycle * 2
                phase.match_floor(overlap, manifest, "overlap")
                result["floors"].append(overlap)
                assert (bundle / "rotation.json").read_bytes() == raw
                result["sameProposalRetryFrozen"] = True
                next_control_file = bundle / "control-cert.pem"
                heartbeat(old_control_file, manifest["nextNodeCertificateSHA256"])
                heartbeat(next_control_file, manifest["nextNodeCertificateSHA256"])
                commit_body = phase.commit_body(manifest, raw)
                commit = {**commit_body, "controlSignature": control_key.sign(phase.canonical(commit_body)).hex()}
                commit_path = temp / f"commit-{cycle}.json"
                commit_path.write_bytes(phase.canonical(commit)); commit_path.chmod(0o600)
                # Native fixture models existing C->C+1 receipt; real PostgreSQL
                # CAS/ownership remains the separate main Core integration scope.
                cp_policy_raw = files["peer-policy-final.json"]
                worker.finalize(bundle, folder, commit_path, restart=start)
                final = floor()
                assert final["peerPolicyVersion"] == 7 + cycle * 2
                phase.match_floor(final, manifest, "final")
                result["floors"].append(final)
                heartbeat(next_control_file, manifest["nextNodeCertificateSHA256"])
                heartbeat(old_control_file, manifest["nextNodeCertificateSHA256"], accepted=False)
                attestation = worker.attest_finalized(bundle, folder)
                worker.verify_finalized_attestation(attestation, raw, files)
                result["events"].append(dict(cycle=cycle, channelVersion=manifest["targetChannelVersion"],
                    installedPreFloor=installed["prePeerFloor"]["peerPolicyVersion"], installedPostFloor=installed["postPeerFloor"]["peerPolicyVersion"],
                    finalFloor=final["peerPolicyVersion"], finalAccepted=True, oldCPRejectedAfterFinal=True,
                    attestationSHA256=sha(phase.canonical(attestation)), manifestSHA256=sha(raw)))
                result["completedNormalCycles"] += 1
                current_control = x509.load_pem_x509_certificate(files["control-cert.pem"])
                old_control_file = next_control_file
                time.sleep(1.05)  # natural later createdAt; no clock modification
            # Unit guard probe uses real Go packages and a DIFFERENT disposable
            # journal, retaining same-version defense and pin-before-expiry truth.
            fixture = temp / "guard-fixture"; fixture.mkdir(mode=0o700)
            (fixture / "ca.pem").write_bytes(chain)
            (fixture / "config.json").write_text(json.dumps(dict(TenantID=tenant, NodeID=node_id, Epoch=epoch)), encoding="utf-8")
            overlap_raw = (temp / "cycle-1/peer-policy-overlap.json").read_bytes()
            bad_final = phase.strict((temp / "cycle-1/peer-policy-final.json").read_bytes()); bad_final["version"] = 8
            expired = {**bad_final, "version": 12, "expiresAt": (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat().replace("+00:00", "Z")}
            for name, body in {"overlap.json": overlap_raw, "same-version-final.json": phase.canonical(bad_final), "expired.json": phase.canonical(expired)}.items():
                (fixture / name).write_bytes(body); (fixture / name).chmod(0o600)
            copied = ROOT / "services/node-agent/transport/fleet5_fixed_generated_guards_test.go"
            guard_source = (ROOT / "tests/proofs/fleet5_peer_phase_fixed_guards_test.go").read_bytes()
            with copied.open("xb") as stream: stream.write(guard_source)
            try:
                with (output / "go-guard-events.jsonl").open("wb") as log_file:
                    unit = subprocess.run(["go", "test", "-json", "./runtime", "./transport", "-run", "^TestActualPeerFloor|^TestFixedPeerPhaseGuards", "-count=1"],
                                          cwd=ROOT / "services/node-agent", env=dict(os.environ, FLEET5_FIXED_NATIVE_FIXTURE=str(fixture)), stdout=log_file, stderr=subprocess.STDOUT, timeout=180)
                if unit.returncode: raise ValueError("Actual native Go observer/defense tests failed; see guard events")
            finally:
                if copied.read_bytes() != guard_source: raise ValueError("Owned fixture test changed; preserve for inspection")
                copied.unlink()
            events = [json.loads(line) for line in (output / "go-guard-events.jsonl").read_text("utf-8").splitlines() if line.startswith("{")]
            assert not any(e.get("Action") in {"fail", "skip"} for e in events)
            assert any(e.get("Test") == "TestFixedPeerPhaseGuardsPreserveGoFloorDefense" and e.get("Action") == "pass" for e in events)
            result.update(sameVersionDifferentHashRejectedByActualGo=True, expiredDirectStartupStillPinsByActualGo=True,
                          actualGoObserverOwnershipAndLockTestsPassed=True, proofValid=True)
            assert [entry["peerPolicyVersion"] for entry in result["floors"]] == [7, 8, 9, 10, 11]
            assert result["completedNormalCycles"] == 2 and all(result[k] for k in ("expiryBeforeWriteRejected", "rollbackAfterHandshakePinRejected", "sameProposalRetryFrozen", "predecessorResidueRejected", "predecessorExactReplaySettled", "strictOldReaderRejected", "floorCPMismatchRejected"))
            (output / "native-fixed-result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            print(json.dumps({k: result[k] for k in ("headSHA", "proofValid", "completedNormalCycles", "scope")}))
            return 0
        finally:
            stop(); log.close()
            if not (output / "native-fixed-result.json").exists():
                result["proofValid"] = False
                (output / "native-fixed-result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            (output / "native-server.log").write_bytes((temp / "server.log").read_bytes())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    return run_proof(args.output.resolve())


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print("Fixed native proof failed (not green): " + type(error).__name__ + ": " + str(error), file=sys.stderr)
        raise SystemExit(1)
