"""Read-only replacement admission and stale receipt boundaries."""

from copy import deepcopy
import io
import json
import tarfile
import pytest
from test_lan_storage import plan, target
import worker_replacement as replacement


def stopped(p):
    value = target(p)
    value["Config"]["Cmd"] += ["--profile", "lan-observe-v1"]
    value["State"].update(Status="exited", ExitCode=0, OOMKilled=False)
    volume = dict(
        Name="saintvision-" + p["manifest"]["nodeId"].lower() + "-state",
        Labels={"ai.saintvision.node": p["manifest"]["nodeId"]},
    )
    return value, volume, [value["Id"]]


@pytest.mark.parametrize(
    "fault",
    [
        None,
        "running",
        "workload",
        "exit",
        "oom",
        "owner",
        "shared",
        "identity",
        "extra",
        "writable",
    ],
)
def test_only_clean_stopped_owned_observation_container(plan, fault):
    value, volume, consumers = stopped(plan)
    if fault == "running":
        value["State"]["Running"] = True
    if fault == "workload":
        value["Config"]["Cmd"][-1] = "lan-workspace-v1"
    if fault == "exit":
        value["State"]["ExitCode"] = 1
    if fault == "oom":
        value["State"]["OOMKilled"] = True
    if fault == "owner":
        volume["Labels"] = {}
    if fault == "shared":
        consumers.append("d" * 64)
    if fault == "identity":
        value["Config"]["Cmd"][1] = "nod_" + "1" * 26
    if fault == "extra":
        value["Mounts"].append(dict(Destination="/workspace"))
    if fault == "writable":
        value["Mounts"][1]["RW"] = True
    if fault:
        with pytest.raises(ValueError):
            replacement.stopped_target(plan, value, volume, consumers)
    else:
        assert replacement.stopped_target(plan, value, volume, consumers) == volume["Name"]


def archive(p, fault=None):
    m = p["manifest"]
    files = {"state/" + n: b"private-fixture" for n in replacement.CREDENTIAL_FILES}
    files["state/journal/identity.json"] = json.dumps(
        dict(Tenant=m["tenantId"], Node=m["nodeId"], Epoch=m["epoch"])
    ).encode()
    if fault == "epoch":
        files["state/journal/identity.json"] = b"{}"
    if fault == "missing":
        del files["state/node-key.pem"]
    if fault == "traversal":
        files["state/../other"] = b"bad"
    if fault == "changed":
        files["state/node-key.pem"] = b"changed-private-fixture"
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w") as tar:
        for name, raw in files.items():
            e = tarfile.TarInfo(name)
            e.size = len(raw)
            e.mode = 0o100600
            if fault == "permissions":
                e.mode = 0o644
            if fault == "link":
                e.type = tarfile.SYMTYPE
                e.linkname = "/etc/passwd"
            tar.addfile(e, io.BytesIO(raw))
            if fault == "duplicate":
                tar.addfile(e, io.BytesIO(raw))
    return out.getvalue()


@pytest.mark.parametrize(
    "fault", ["epoch", "missing", "traversal", "permissions", "link", "duplicate"]
)
def test_state_archive_rejects_identity_and_unsafe_entries(plan, fault):
    with pytest.raises((ValueError, KeyError)):
        replacement.state_digest(archive(plan, fault), plan["manifest"])


def test_state_fingerprint_binds_private_bytes_without_returning_them(plan):
    result = replacement.state_digest(archive(plan), plan["manifest"])
    assert len(result) == 64
    assert result != replacement.state_digest(archive(plan, "changed"), plan["manifest"])


@pytest.mark.parametrize("fault", [None, "container", "state", "volume", "proposal", "authorized"])
def test_receipt_recheck_rejects_every_stale_boundary(plan, monkeypatch, fault):
    receipt = dict(container="a", state="b", volume="c", proposal="d", authorized=False)
    fresh = deepcopy(receipt)
    if fault:
        fresh[fault] = "changed"
    monkeypatch.setattr(replacement, "capture", lambda p: fresh)
    if fault:
        with pytest.raises(ValueError):
            replacement.recheck(plan, receipt)
    else:
        assert replacement.recheck(plan, receipt) == receipt


@pytest.mark.parametrize(
    "fault", [None, "state-write", "container-restart", "volume-replaced", "mount-order"]
)
def test_capture_detects_changes_during_inspection(plan, monkeypatch, fault):
    value, volume, consumers = stopped(plan)
    counts = {"inspect": 0, "volume": 0, "archive": 0}

    def docker(*args):
        if args[0] == "inspect":
            counts["inspect"] += 1
            current = deepcopy(value)
            if fault == "mount-order" and counts["inspect"] > 1:
                current["Mounts"].reverse()
            if fault == "container-restart" and counts["inspect"] > 1:
                current["State"]["StartedAt"] = "changed"
            return json.dumps([current]).encode()
        if args[0] == "volume":
            counts["volume"] += 1
            current = deepcopy(volume)
            if fault == "volume-replaced" and counts["volume"] > 1:
                current["CreatedAt"] = "changed"
            return json.dumps([current]).encode()
        assert args[0] == "ps"
        return consumers[0].encode()

    def state(container):
        counts["archive"] += 1
        return archive(
            plan, "changed" if fault == "state-write" and counts["archive"] > 1 else None
        )

    monkeypatch.setattr(replacement.storage, "docker", docker)
    monkeypatch.setattr(replacement, "state_archive", state)
    if fault and fault != "mount-order":
        with pytest.raises(ValueError):
            replacement.capture(plan)
    else:
        receipt = replacement.capture(plan)
        assert receipt["replacementAuthorized"] is False
        assert "private-fixture" not in json.dumps(receipt)
