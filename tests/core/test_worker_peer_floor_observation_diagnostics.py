"""Stage1 controlled-adapter tests of ACTUAL observe; no Docker/producer proof."""
import ast
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest
from cryptography.hazmat.primitives import serialization

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "deploy/lan"))
import worker_peer_floor as floor


@pytest.fixture
def observation(monkeypatch):
    """Only adapter seams are controlled; the full actual observe body executes.

    This does NOT authenticate a real Node/certificate/signature. Separate tests
    prove calls to the existing verifier/nonce/DER gates remain mandatory.
    """
    node = "nod_" + "0" * 26
    manifest = dict(nodeId=node, tenantId="synthetic-tenant", epoch="synthetic-epoch")
    before = dict(Id="a" * 64, Image="sha256:" + "b" * 64,
                  Config=dict(Cmd=["--state", "/state/journal", "--peer-policy", "/state/peer-policy.json",
                                   "--tls-cert", "/state/node-cert.pem", "--tls-key", "/state/node-key.pem"],
                              Env=["PRIVATE_SENTINEL_ENV=do-not-log"], Labels={"private-dynamic-key": "PRIVATE_SENTINEL_LABEL"}),
                  Mounts=[dict(Type="volume", Name="owned-state", Source="/PRIVATE_SENTINEL_PATH", Destination="/state", RW=True),
                          dict(Type="bind", Source="/var/run/docker.sock", Destination="/var/run/docker.sock", RW=True)],
                  State=dict(Running=True, Restarting=False, Status="running", StartedAt="2030-01-01T00:00:00Z"),
                  RestartCount=0)
    after = deepcopy(before)
    volume = dict(Name="owned-state", Labels={"ai.saintvision.node": node}, CreatedAt="2030-01-01T00:00:00Z")
    after_volume = deepcopy(volume)
    consumers, after_consumers = [before["Id"]], [before["Id"]]
    public_der = b"SYNTHETIC PUBLIC DER ADAPTER ONLY"
    wire = dict(servingPID=1, certificateDER_SHA256=floor.phase.digest(public_der))
    rotation = dict(nodeId=node, tenantId=manifest["tenantId"], recoveryEpoch=manifest["epoch"])
    seen = dict(targets=0, execs=[], verifies=[])

    def target(_):
        seen["targets"] += 1
        current, vol, cs = (before, volume, consumers) if seen["targets"] == 1 else (after, after_volume, after_consumers)
        return manifest, "owned-name", current, before["Config"]["Cmd"], vol, cs

    def docker(*args):
        seen["execs"].append(args)
        return floor.phase.canonical(wire)

    class PublicCertificateAdapter:
        def public_bytes(self, encoding):
            assert encoding == serialization.Encoding.DER
            return public_der

    def verify(value, cert, scope, *, nonce):
        seen["verifies"].append((value, cert, scope, nonce))

    monkeypatch.setattr(floor, "target", target)
    monkeypatch.setattr(floor, "docker", docker)
    monkeypatch.setattr(floor.x509, "load_pem_x509_certificate", lambda raw: PublicCertificateAdapter())
    monkeypatch.setattr(floor.phase, "verify_floor", verify)
    return dict(before=before, after=after, volume=volume, after_volume=after_volume,
                consumers=consumers, after_consumers=after_consumers, wire=wire,
                rotation=rotation, seen=seen, files={"node-cert.pem": b"SYNTHETIC PUBLIC CERT ADAPTER"})


def run_observe(a):
    return floor.observe("PRIVATE_SENTINEL_WORKER_ROOT", a["rotation"], a["files"], nonce="PRIVATE_SENTINEL_NONCE")


def diagnostic(a):
    with pytest.raises(ValueError, match=floor.OBSERVATION_CHANGE_PREFIX) as caught:
        run_observe(a)
    message = str(caught.value)
    assert message.startswith(floor.OBSERVATION_CHANGE_PREFIX + "; diagnostic=")
    value = json.loads(message.split("; diagnostic=", 1)[1])
    assert value["classification"] == "REFUSAL_DIAGNOSTIC_ONLY"
    assert len(message.split("; diagnostic=", 1)[1]) <= 4096
    assert len(value["changedPaths"]) <= 24
    assert all(len(p) <= 72 for p in value["changedPaths"])
    for forbidden in ("PRIVATE_SENTINEL", "private-dynamic-key", "/state/", "sha256:", "2030-01-01"):
        assert forbidden not in message
    assert len(value["hashes"]) <= 8
    for hashes in value["hashes"].values():
        for h in hashes.values():
            assert h is None or len(h) == 64 and set(h) <= set("0123456789abcdef")
    return value


def test_exact_observation_passes_and_preserves_nonce_der_verifier_calls(observation):
    a = observation
    assert run_observe(a) == a["wire"]
    assert a["seen"]["targets"] == 2 and len(a["seen"]["execs"]) == len(a["seen"]["verifies"]) == 1
    command = a["seen"]["execs"][0]
    assert command[:3] == ("exec", a["before"]["Id"], "/inv-node")
    assert command[-2:] == ("--peer-floor-nonce", "PRIVATE_SENTINEL_NONCE")
    assert a["seen"]["verifies"][0][2:] == (a["rotation"], "PRIVATE_SENTINEL_NONCE")


@pytest.mark.parametrize("field,path,category", [
    ("Id", "container.Id", "CONTAINER_ID_CHANGED"),
    ("Image", "container.Image", "IMAGE_CHANGED"),
    ("Config", "container.Config.Env", "CONFIG_CHANGED"),
    ("Mounts", "container.Mounts[0].Source", "MOUNTS_CHANGED"),
    ("StartedAt", "container.State.StartedAt", "STARTED_AT_CHANGED"),
    ("RestartCount", "container.RestartCount", "RESTART_COUNT_CHANGED"),
    ("volume", "volume.Name", "VOLUME_CHANGED"),
    ("consumers", "volumeConsumers", "CONSUMERS_CHANGED"),
])
def test_every_original_tuple_field_still_refuses(observation, field, path, category):
    a = observation
    if field == "Config":
        a["after"][field]["Env"] = ["PRIVATE_SENTINEL_ENV=changed-secret"]
    elif field == "Mounts":
        a["after"][field][0]["Source"] = "/PRIVATE_SENTINEL_CHANGED_PATH"
    elif field == "StartedAt":
        a["after"]["State"][field] = "changed PRIVATE_SENTINEL_START"
    elif field == "volume":
        a["after_volume"]["Name"] = "PRIVATE_SENTINEL_REPLACED_VOLUME"
    elif field == "consumers":
        a["after_consumers"].append("c" * 64)
    else:
        a["after"][field] = "c" * 64 if field != "RestartCount" else 1
    d = diagnostic(a)
    assert path in d["changedPaths"] and category in d["categories"]


def test_mounts_permutation_is_classified_but_still_refuses_stage1(observation):
    observation["after"]["Mounts"].reverse()
    d = diagnostic(observation)
    assert d["categories"] == ["MOUNTS_ORDER_ONLY"]
    assert d["changedPaths"] == ["container.Mounts"]


def test_created_at_only_is_classified_but_still_refuses_stage1(observation):
    observation["after_volume"]["CreatedAt"] = "PRIVATE_SENTINEL_TIMESTAMP"
    d = diagnostic(observation)
    assert d["categories"] == ["VOLUME_CREATED_AT_FIELD_ONLY"]
    assert d["changedPaths"] == ["volume.CreatedAt"]


def test_unhashable_oversize_unknown_keys_are_bounded_and_redacted(observation):
    a = observation
    a["after"]["Config"]["PRIVATE_SENTINEL_DYNAMIC_KEY"] = ["PRIVATE_SENTINEL_SECRET" * 2000] * 100
    a["after"]["Config"]["Env"] = ["PRIVATE_SENTINEL_ENV=changed"]
    d = diagnostic(a)
    assert "container.Config.<other>" in d["changedPaths"]
    assert d["truncated"] is True and d["hashes"]["container.Config"]["afterSHA256"] is None


def test_many_mount_differences_truncate_without_accepting(observation):
    a = observation
    a["before"]["Mounts"] = [{k: "PRIVATE_SENTINEL_OLD" for k in floor._MOUNT_DIAGNOSTIC_FIELDS} for _ in range(8)]
    a["after"]["Mounts"] = [{k: "PRIVATE_SENTINEL_NEW" for k in floor._MOUNT_DIAGNOSTIC_FIELDS} for _ in range(8)]
    d = diagnostic(a)
    assert "MOUNTS_CHANGED" in d["categories"]
    assert d["truncated"] and len(d["changedPaths"]) == 24


@pytest.mark.parametrize("fault", ["identity", "before-stopped", "before-restarting", "pid", "DER", "signature", "after-stopped", "after-restarting", "missing-id", "missing-config", "malformed-state"])
def test_existing_security_gate_refusals_remain(observation, monkeypatch, fault):
    a = observation
    if fault == "identity": a["rotation"]["tenantId"] = "wrong"
    elif fault == "before-stopped": a["before"]["State"]["Running"] = False
    elif fault == "before-restarting": a["before"]["State"]["Restarting"] = True
    elif fault == "pid": a["wire"]["servingPID"] = 2
    elif fault == "DER": a["wire"]["certificateDER_SHA256"] = "f" * 64
    elif fault == "signature": monkeypatch.setattr(floor.phase, "verify_floor", lambda *a, **k: (_ for _ in ()).throw(ValueError("signature rejected")))
    elif fault == "after-stopped": a["after"]["State"]["Running"] = False
    elif fault == "after-restarting": a["after"]["State"]["Restarting"] = True
    elif fault == "missing-id": del a["after"]["Id"]
    elif fault == "missing-config": del a["after"]["Config"]
    else: a["after"]["State"] = None
    # The original guard raises AttributeError for a non-object State. Stage1
    # preserves that refusal too; it does not change malformed-input semantics.
    with pytest.raises((ValueError,KeyError,TypeError,AttributeError)):
        run_observe(a)


def test_diagnostic_hash_rejects_unknown_objects_without_repr_or_callbacks():
    class Hostile:
        def __repr__(self): pytest.fail("repr must not run")
        def __str__(self): pytest.fail("str must not run")
    for value in (Hostile(), float("nan"), b"PRIVATE_SENTINEL_BYTES", {"x": Hostile()}):
        assert floor._diagnostic_hash(value) is None


@pytest.mark.parametrize("fault",["duplicate-profile","missing-profile-value","unknown-mount","privileged","rw-root","invalid-id"])
def test_plain_target_security_guards_are_not_relaxed(observation,monkeypatch,fault):
    a=observation;value=deepcopy(a["before"])
    value["Config"]["Cmd"] += ["--profile","lan-observe-v1"]
    value["HostConfig"] = dict(Privileged=False,ReadonlyRootfs=True)
    value["Mounts"][1]["Propagation"] = "rprivate"
    # Existing repair_target has its own unchanged unit coverage; this adapter
    # isolates the actual _plain additional guards without any Docker/host I/O.
    monkeypatch.setattr(floor,"repair_target",lambda *args:None)
    if fault=="duplicate-profile":value["Config"]["Cmd"] += ["--profile","lan-test-v1"]
    elif fault=="missing-profile-value":value["Config"]["Cmd"].pop()
    elif fault=="unknown-mount":value["Mounts"].append(dict(Destination="/unknown"))
    elif fault=="privileged":value["HostConfig"]["Privileged"]=True
    elif fault=="rw-root":value["HostConfig"]["ReadonlyRootfs"]=False
    else:value["Id"]="not-an-id"
    with pytest.raises(ValueError):floor._plain({},value)


def test_all_observe_guards_and_predicate_are_source_identical_except_failure_annotation():
    old = subprocess.check_output(["git", "show", "ff3169d360a707415d9b03484cf0cf3031f3912c:deploy/lan/worker_peer_floor.py"], cwd=ROOT).decode()
    previous = ast.parse(old)
    current = ast.parse((ROOT / "deploy/lan/worker_peer_floor.py").read_text(encoding="utf-8"))
    def function(tree, name): return next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name == name)
    old_observe, new_observe = function(previous,"observe"), function(current,"observe")
    old_guard = old_observe.body[-2]
    new_guard = new_observe.body[-2]
    assert isinstance(old_guard,ast.If) and isinstance(new_guard,ast.If)
    assert ast.dump(old_guard.test) == ast.dump(new_guard.test)
    assert len(new_guard.body)==1 and isinstance(new_guard.body[0],ast.Raise)
    assert new_guard.body[0].cause is None
    calls=[n for n in ast.walk(new_guard.body[0]) if isinstance(n,ast.Call)]
    assert len(calls)==2 and isinstance(calls[0].func,ast.Name) and calls[0].func.id=="ValueError"
    assert isinstance(calls[1].func,ast.Name) and calls[1].func.id=="_observation_diagnostic"
    assert [n.id for n in calls[1].args]==["before","after","volume","volume_after","consumers","consumers_after"]
    assert not calls[1].keywords
    new_guard.body = old_guard.body
    assert ast.dump(old_observe) == ast.dump(new_observe)
    for name in ("target","_plain","regular","docker","context","stopped_entries"):
        assert ast.dump(function(previous,name)) == ast.dump(function(current,name))
