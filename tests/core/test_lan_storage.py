"""Installer authorization/argument/archive/receipt boundaries, Docker calls simulated."""

from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
from uuid import uuid4
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "deploy/lan"))
import worker_storage as storage


@pytest.fixture
def plan(tmp_path):
    private = tmp_path / "private"
    private.mkdir()
    source = tmp_path / "provided folder"
    source.mkdir()
    manifest = dict(
        nodeId="nod_" + "0" * 26,
        tenantId=str(uuid4()),
        epoch=str(uuid4()),
        nodeIP="192.168.45.225",
        nodePort=18443,
    )
    policy = dict(
        channel=dict(
            tenant_id=manifest["tenantId"],
            node_id=manifest["nodeId"],
            recovery_epoch=manifest["epoch"],
            version=1,
            endpoint="https://192.168.45.225:18443",
            certificate_sha256="a" * 64,
        ),
        contribution_id="stc_" + "0" * 26,
        root_version=1,
        root="/contribution",
    )
    path = private / "storage-policy.json"
    path.write_text(json.dumps(policy))
    return storage.prepare(
        manifest, path, str(source), storage.digest(path.read_bytes()), "sha256:" + "b" * 64
    )


def target(p):
    m = p["manifest"]
    name = "saintvision-" + m["nodeId"].lower()
    args = []
    for k, v in {
        "--node": m["nodeId"],
        "--tenant": m["tenantId"],
        "--epoch": m["epoch"],
        "--state": "/state/journal",
        "--public-key": "/state/signer.pub",
        "--tls-key": "/state/node-key.pem",
        "--tls-cert": "/state/node-cert.pem",
        "--client-ca": "/state/ca.pem",
        "--peer-policy": "/state/peer-policy.json",
        "--storage-policy": storage.POLICY,
    }.items():
        args.extend([k, v])
    return dict(
        Id="c" * 64,
        Image=p["image"],
        Name="/" + name,
        RestartCount=0,
        Config=dict(User="", Labels={"ai.saintvision.node": m["nodeId"]}, Cmd=args),
        State=dict(Status="created", Running=False, Restarting=False, StartedAt="test"),
        HostConfig=dict(
            ReadonlyRootfs=True,
            Privileged=False,
            Mounts=[dict(Target=storage.TARGET, BindOptions=dict(NonRecursive=True))],
        ),
        Mounts=[
            dict(Destination="/state", Type="volume", Name=name + "-state", RW=True),
            dict(
                Destination=storage.TARGET,
                Type="bind",
                Source=p["source"],
                RW=False,
                Propagation="rprivate",
            ),
        ],
    )


def startup(p):
    m = p["manifest"]
    q = p["policy"]
    return dict(
        listening="0.0.0.0:18443",
        tenantId=m["tenantId"],
        nodeId=m["nodeId"],
        recoveryEpoch=m["epoch"],
        operationalAcceptanceAssessed=False,
        storagePolicy=dict(
            contributionId=q["contribution_id"],
            rootVersion=1,
            channelVersion=1,
            rootSha256=storage.digest(b"/contribution"),
            channelSha256="d" * 64,
            policySha256=p["policySHA256"],
        ),
    )


def test_mount_is_fixed_readonly_nonrecursive_and_one_argument(plan):
    args = storage.mount_args(plan)
    assert args == [
        "--mount",
        f"type=bind,source={plan['source']},target=/contribution,readonly,bind-propagation=rprivate,bind-recursive=disabled",
    ]
    storage.target(plan, target(plan))


@pytest.mark.parametrize(
    "fault",
    [
        "tenant",
        "epoch",
        "node",
        "endpoint",
        "root",
        "boolean-version",
        "unknown-key",
        "hash",
        "duplicate",
    ],
)
def test_policy_rejects_wrong_scope_and_mount_shadowing(plan, fault):
    p = plan
    q = deepcopy(p["policy"])
    if fault in ("tenant", "epoch", "node"):
        q["channel"][
            {"tenant": "tenant_id", "epoch": "recovery_epoch", "node": "node_id"}[fault]
        ] = "wrong"
    elif fault == "endpoint":
        q["channel"]["endpoint"] = "https://attacker.invalid:18443"
    elif fault == "root":
        q["root"] = "/state"
    elif fault == "boolean-version":
        q["root_version"] = True
    elif fault == "unknown-key":
        q["execute"] = "command"
    raw = json.dumps(q).encode()
    if fault == "duplicate":
        raw = raw[:-1] + b',"root":"/contribution"}'
    Path(p["policyPath"]).write_bytes(raw)
    with pytest.raises(ValueError):
        storage.prepare(
            p["manifest"],
            p["policyPath"],
            p["source"],
            "f" * 64 if fault == "hash" else storage.digest(raw),
            p["image"],
        )


@pytest.mark.parametrize("fault", ["root", "private", "parent", "comma", "relative", "replaced"])
def test_source_scope_and_changes_are_rejected(plan, fault, tmp_path):
    p = plan
    source = Path(p["source"])
    if fault == "root":
        p["source"] = source.anchor
    elif fault == "private":
        p["source"] = str(Path(p["policyPath"]).parent)
    elif fault == "parent":
        p["source"] = str(tmp_path)
    elif fault == "relative":
        p["source"] = "relative"
    elif fault == "comma":
        bad = tmp_path / "data,readonly=false"
        bad.mkdir()
        p["source"] = str(bad)
    else:
        source.rename(tmp_path / "old")
        source.mkdir()
    with pytest.raises(ValueError):
        storage.current(p)


@pytest.mark.parametrize(
    "fault",
    [
        "writable",
        "recursive",
        "other-source",
        "extra-mount",
        "image",
        "privileged",
        "restart",
        "wrong-node",
        "policy-path",
    ],
)
def test_container_substitution_never_passes(plan, fault):
    c = target(plan)
    if fault == "writable":
        c["Mounts"][1]["RW"] = True
    elif fault == "recursive":
        c["HostConfig"]["Mounts"][0]["BindOptions"]["NonRecursive"] = False
    elif fault == "other-source":
        c["Mounts"][1]["Source"] = "other"
    elif fault == "extra-mount":
        c["Mounts"].append(dict(Destination="/host", RW=True))
    elif fault == "image":
        c["Image"] = "sha256:" + "0" * 64
    elif fault == "privileged":
        c["HostConfig"]["Privileged"] = True
    elif fault == "restart":
        c["State"]["Running"] = True
        c["State"]["Status"] = "running"
    elif fault == "wrong-node":
        c["Config"]["Labels"]["ai.saintvision.node"] = "other"
    else:
        c["Config"]["Cmd"][-1] = "/state/node-key.pem"
    with pytest.raises(ValueError):
        storage.target(plan, c)


def test_policy_archive_and_return_copy_match_without_touching_keys(plan, monkeypatch):
    archive = None
    calls = []

    def docker(*args, input=None):
        nonlocal archive
        calls.append(args)
        if args[0] == "inspect":
            return json.dumps([target(plan)]).encode()
        if args[:3] == ("cp", "-a", "-"):
            archive = input
            return b""
        return archive

    monkeypatch.setattr(storage, "docker", docker)
    storage.install("owned", plan)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        assert tar.getnames() == ["storage-policy.json"]
        e = tar.getmembers()[0]
        assert e.mode == 0o600 and e.uid == e.gid == 0
        assert tar.extractfile(e).read() == Path(plan["policyPath"]).read_bytes()
    assert all(a[0] in ("inspect", "cp") for a in calls)


@pytest.mark.parametrize(
    "fault", [None, "digest", "scope", "duplicate", "restart", "acceptance", "version"]
)
def test_receipt_matches_exact_configuration_and_is_not_operational_acceptance(plan, fault):
    c = target(plan)
    c["State"].update(Running=True, Status="running")
    r = startup(plan)
    if fault == "digest":
        r["storagePolicy"]["policySha256"] = "0" * 64
    elif fault == "scope":
        r["nodeId"] = "wrong"
    elif fault == "restart":
        c["RestartCount"] = 1
    elif fault == "acceptance":
        r["operationalAcceptanceAssessed"] = True
    elif fault == "version":
        r["storagePolicy"]["rootVersion"] = 2
    logs = json.dumps(r).encode()
    logs = logs + b"\n" + logs if fault == "duplicate" else logs
    if fault:
        with pytest.raises(ValueError):
            storage.receipt(plan, c, logs)
    else:
        result = storage.receipt(plan, c, logs)
        assert result["readOnlyMount"] and not result["operationalAcceptanceAssessed"]
        assert result["status"] == "awaiting-server-mtls-verification"
        assert plan["source"] not in json.dumps(result)
