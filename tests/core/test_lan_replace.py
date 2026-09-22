"""Replacement ownership and protected-state comparison boundaries."""

from copy import deepcopy
import pytest
from test_lan_storage import plan, target
from test_lan_replacement import archive
import worker_replace as replacement


@pytest.mark.parametrize("fault", [None, "identity", "running", "image", "mount", "args"])
def test_backup_only_permits_name_and_restart_policy_change(plan, fault):
    prior = target(plan)
    prior["State"].update(Status="exited", ExitCode=0)
    prior["HostConfig"]["RestartPolicy"] = dict(Name="unless-stopped", MaximumRetryCount=0)
    current = deepcopy(prior)
    current["Name"] += "-storage-backup-test"
    current["HostConfig"]["RestartPolicy"]["Name"] = "no"
    if fault == "identity":
        current["Id"] = "e" * 64
    if fault == "running":
        current["State"]["Running"] = True
    if fault == "image":
        current["Image"] = "sha256:" + "e" * 64
    if fault == "mount":
        current["Mounts"][0]["Name"] = "other-state"
    if fault == "args":
        current["Config"]["Cmd"].append("--other")
    if fault:
        with pytest.raises(ValueError):
            replacement.old_target(dict(previous=prior), current)
    else:
        replacement.old_target(dict(previous=prior), current)


def test_protected_digest_keeps_private_key_changes_visible(plan, monkeypatch):
    monkeypatch.setattr(replacement.preflight, "state_archive", lambda c: archive(plan))
    original = replacement.preserved(plan, "container")
    monkeypatch.setattr(replacement.preflight, "state_archive", lambda c: archive(plan, "changed"))
    assert replacement.preserved(plan, "container") != original


def test_startup_checkpoint_follows_readiness(monkeypatch):
    observed = []
    monkeypatch.setattr(
        replacement.storage,
        "docker",
        lambda *args: observed.append(("docker", *args)),
    )
    monkeypatch.setattr(
        replacement,
        "check_running",
        lambda name: observed.append(("ready", name)),
    )

    replacement.start_and_confirm(
        "saintvision-node",
        "a" * 64,
        lambda phase: observed.append(("checkpoint", phase)),
    )

    assert observed == [
        ("docker", "start", "a" * 64),
        ("ready", "saintvision-node"),
        ("checkpoint", "starting"),
    ]


@pytest.mark.parametrize(
    "fault",
    [None, "ownership", "privileged", "restart", "port", "capabilities", "memory", "identifier"],
)
def test_replacement_container_requires_exact_transaction_and_limits(plan, fault):
    plan["manifest"]["agentImage"] = plan["image"]
    # Updating the fixture manifest also updates the input used by prepare/current.
    value = target(plan)
    value["Config"]["Cmd"] = replacement.command(plan)
    value["Config"]["Labels"]["ai.saintvision.storage-replace"] = "transaction"
    value["HostConfig"].update(
        RestartPolicy=dict(Name="no"),
        PortBindings={
            "18443/tcp": [
                {
                    "HostIp": plan["manifest"]["nodeIP"],
                    "HostPort": str(plan["manifest"]["nodePort"]),
                }
            ]
        },
        CapDrop=["ALL"],
        SecurityOpt=["no-new-privileges"],
        PidsLimit=128,
        Memory=268435456,
        NanoCpus=500000000,
    )
    if fault == "ownership":
        value["Config"]["Labels"]["ai.saintvision.storage-replace"] = "another"
    if fault == "privileged":
        value["HostConfig"]["Privileged"] = True
    if fault == "restart":
        value["HostConfig"]["RestartPolicy"]["Name"] = "always"
    if fault == "port":
        value["HostConfig"]["PortBindings"] = {}
    if fault == "capabilities":
        value["HostConfig"]["CapDrop"] = []
    if fault == "memory":
        value["HostConfig"]["Memory"] = 0
    record = dict(id="transaction")
    if fault == "identifier":
        record["currentId"] = "f" * 64
    if fault:
        with pytest.raises(ValueError):
            replacement.new_target(plan, record, value)
    else:
        replacement.new_target(plan, dict(id="transaction"), value)


def test_oversized_recovery_record_is_rejected_before_writing(tmp_path):
    path = tmp_path / "storage-replacement.json"
    with pytest.raises(ValueError):
        replacement.save(path, dict(data="x" * 65536))
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("field", ["CreatedAt", "Name", "Driver", "Labels", "Mountpoint"])
def test_volume_timestamp_is_not_identity_but_other_fields_remain_bound(field):
    prior = dict(
        CreatedAt="before",
        Name="owned",
        Driver="local",
        Labels={"owner": "node"},
        Mountpoint="/owned",
    )
    current = dict(prior)
    current[field] = "after"
    digest = replacement.storage.digest(replacement.preflight.canonical(prior))
    if field == "CreatedAt":
        replacement.validate_volume(prior, current, digest)
    else:
        with pytest.raises(ValueError):
            replacement.validate_volume(prior, current, digest)
