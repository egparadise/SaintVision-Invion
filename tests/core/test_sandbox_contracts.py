from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import pytest
from inv.contracts import validate_contract
from inv.errors import DomainError
from inv.ids import new_id
from inv.policy import action_digest, enforce_decision
from inv.sandbox import SandboxProfile, compile_launch


@pytest.fixture
def launch():
    workload = {
        "apiVersion": "inv.saintvision.ai/v1alpha1",
        "kind": "Workload",
        "workloadId": new_id("wld"),
        "tenantId": str(uuid4()),
        "projectId": new_id("prj"),
        "workspaceId": new_id("wsp"),
        "resources": {
            "cpuMillis": 100,
            "memoryBytes": 1024,
            "gpuCount": 0,
            "minVramBytes": 0,
        },
        "imageDigest": "sha256:" + "a" * 64,
        "command": ["/usr/bin/printf", "value"],
        "timeoutSeconds": 10,
    }
    profile = SandboxProfile(
        "restricted:test:1",
        frozenset({workload["imageDigest"]}),
        frozenset({"/usr/bin/printf"}),
    )
    return workload, profile


@pytest.mark.parametrize(
    "field,value",
    [
        ("network", "host"),
        ("privileged", True),
        ("hostAccess", True),
        ("rootfsReadOnly", False),
        ("userId", 0),
        ("capDropAll", False),
        ("noNewPrivileges", False),
        ("workingDirectory", "C:\\"),
        ("workspaceMode", "host-bind"),
        ("mounts", ["/var/run/docker.sock"]),
        ("env", {"TOKEN": "value"}),
    ],
)
def test_sandbox_contract_rejects_host_access_or_isolation_downgrade(
    launch, field, value
):
    workload, profile = launch
    plan = compile_launch(workload, profile)
    plan[field] = value
    with pytest.raises(DomainError):
        validate_contract("SandboxLaunchSpec", plan)


@pytest.mark.parametrize(
    "change", ["image", "shell", "nul", "cpu", "memory", "gpu", "timeout"]
)
def test_profile_limits_block_unapproved_execution(launch, change):
    workload, profile = launch
    if change == "image":
        workload["imageDigest"] = "sha256:" + "b" * 64
    elif change == "shell":
        workload["command"] = ["/bin/sh", "-c", "anything"]
    elif change == "nul":
        workload["command"][1] = "nul\x00value"
    elif change == "cpu":
        workload["resources"]["cpuMillis"] = profile.max_cpu_millis + 1
    elif change == "memory":
        workload["resources"]["memoryBytes"] = profile.max_memory_bytes + 1
    elif change == "gpu":
        workload["resources"]["gpuCount"] = 1
    elif change == "timeout":
        workload["timeoutSeconds"] = profile.max_timeout_seconds + 1
    with pytest.raises(DomainError, match="SANDBOX-0002"):
        compile_launch(workload, profile)


@pytest.mark.parametrize(
    "executable",
    ["printf", "/bin/../bin/sh", "/bin//sh", "/bin/./sh", "/bin/sh\x00", "/bin\\sh"],
)
def test_profile_executable_allowlist_is_canonical(launch, executable):
    _, profile = launch
    with pytest.raises(ValueError):
        replace(profile, executables=frozenset({executable}))


def test_shell_metacharacters_are_literal_container_arguments(launch):
    workload, profile = launch
    literal = "$(secret); & command | not-a-host-shell"
    workload["command"][1] = literal
    plan = compile_launch(workload, profile)
    assert plan["argv"] == ["/usr/bin/printf", literal]
    assert plan["argv"] is not workload["command"]


def test_legacy_policy_boundary_also_requires_two_people_for_L2(launch):
    workload, _ = launch
    now = datetime.now(timezone.utc)
    decision = {
        "decisionId": "synthetic",
        "tenantId": workload["tenantId"],
        "projectId": workload["projectId"],
        "subjectId": "requester",
        "effect": "require_approval",
        "riskLevel": "L2",
        "actionDigest": action_digest(workload),
        "expiresAt": (now + timedelta(seconds=10)).isoformat(),
        "requiredApprovals": 1,
        "approvedBy": ["alice"],
    }
    with pytest.raises(DomainError, match="AUTH-0014"):
        enforce_decision(
            decision,
            action=workload,
            tenant_id=workload["tenantId"],
            project_id=workload["projectId"],
            subject_id="requester",
            now=now,
        )
