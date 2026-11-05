"""Synthetic transports for Python protocol units; never actual Go/Docker evidence.

Only pytest fixtures call these functions, on their own temporary directories.
The native CI proof neither installs these adapters nor consumes their results.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import serialization

import lan_pilot
import peer_policy_phase as phase
import worker_leaf_rotation as worker
import worker_plain_rotation as plain


def observation(policy_raw, certificate_raw, key, scope, now, nonce):
    policy = phase.strict(policy_raw)
    cert = x509.load_pem_x509_certificate(certificate_raw)
    body = dict(schemaVersion="saintvision-node-peer-policy-floor:2", tenantId=scope["tenantId"], nodeId=scope["nodeId"],
                recoveryEpoch=scope.get("recoveryEpoch", scope.get("epoch")), nonce=nonce, observedAt=int(now.timestamp()),
                certificateDER_SHA256=phase.digest(cert.public_bytes(serialization.Encoding.DER)),
                peerPolicyVersion=policy["version"], peerPolicySHA256=phase.digest(policy_raw),
                floorSHA256=phase.digest(b"SYNTHETIC PYTHON UNIT FLOOR"), journalIdentitySHA256=phase.digest(b"SYNTHETIC PYTHON UNIT IDENTITY"),
                journalUID=0, servingPID=1, servingProcessSHA256=phase.digest(b"SYNTHETIC PYTHON UNIT PROCESS"), servingExecutableSHA256=phase.digest(b"SYNTHETIC UNIT EXECUTABLE BYTES"), plainServingProcess=True)
    return {**body, "nodeSignature": key.sign(phase.DOMAIN + phase.floor_canonical(body)).hex()}


def install_unit_adapters(monkeypatch, temporary_root):
    root = Path(temporary_root).resolve()

    def own(path):
        value = Path(path).resolve()
        if not value.is_relative_to(root):
            raise AssertionError("Synthetic observation may only read this pytest fixture")
        return value

    class UnitClock(datetime):
        @classmethod
        def now(cls, tz=None):
            instant = lan_pilot.datetime.now(timezone.utc)
            return instant.astimezone(tz) if tz else instant.replace(tzinfo=None)

    monkeypatch.setattr(phase, "datetime", UnitClock)
    monkeypatch.setattr(plain, "datetime", UnitClock)
    monkeypatch.setattr(worker, "datetime", UnitClock)

    def floor(path, manifest, files):
        path = own(path)
        key = serialization.load_pem_private_key((path / "node-key.pem").read_bytes(), password=None)
        return observation((path / "peer-policy.json").read_bytes(), (path / "node-cert.pem").read_bytes(), key,
                           manifest, UnitClock.now(timezone.utc), os.urandom(32).hex())

    def target(path):
        path = own(path)
        node = json.loads((path / "manifest.json").read_bytes())["nodeId"]
        token = phase.digest(str(path).encode())
        return dict(nodeId=node, containerId=token, image="sha256:" + "a" * 64,
                    configSHA256="b" * 64, hostConfigSHA256="e" * 64, mountsSHA256="c" * 64, volumeSHA256="d" * 64, consumers=[token])

    monkeypatch.setattr(worker, "observe_actual_floor", floor)
    monkeypatch.setattr(worker, "floor_target_context", target)

    def refresh(args):
        if not hasattr(args, "_unit_keys"):
            return
        path = own(args.state)
        state = lan_pilot.load(path)
        destination = root / "synthetic-floor-inputs"
        destination.mkdir(exist_ok=True)
        nonce = os.urandom(32).hex()
        for node in lan_pilot.active_configured_nodes(state):
            node_id = node["nodeId"]
            value = observation(lan_pilot.node_policy_path(path, state, node).read_bytes(),
                                lan_pilot.node_certificate_path(path, state, node).read_bytes(), args._unit_keys[node_id],
                                {"tenantId": state["tenantId"], "nodeId": node_id, "epoch": state["epoch"]},
                                UnitClock.now(timezone.utc), nonce)
            (destination / (node_id + ".json")).write_bytes(phase.canonical(value))
        args.peer_floor_nonce = nonce
        args.peer_floor_observations = destination
        args.peer_floor_observation = destination / (state["nodes"][0]["nodeId"] + ".json")

    for name in ("prepare_leaf_rotation", "prepare_leaf_rotation_batch"):
        original = getattr(lan_pilot, name)

        def prepared(args, original=original):
            refresh(args)
            return original(args)

        monkeypatch.setattr(lan_pilot, name, prepared)
    return {"refresh": refresh}
