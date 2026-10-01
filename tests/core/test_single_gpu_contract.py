from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from inv.contracts import validate_contract
from inv.errors import DomainError
from inv.ids import new_id
from inv.sandbox import SandboxProfile, compile_launch


def fixture():
    now = datetime.now(timezone.utc)
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
            "gpuCount": 1,
            "minVramBytes": 1024,
        },
        "imageDigest": "sha256:" + "a" * 64,
        "command": ["/usr/bin/printf", "gpu"],
        "timeoutSeconds": 10,
    }
    profile = SandboxProfile(
        "restricted:gpu:1",
        frozenset({workload["imageDigest"]}),
        frozenset({"/usr/bin/printf"}),
    )
    epoch = str(uuid4())
    allocation = {
        "nodeId": new_id("nod"),
        "resourceId": new_id("res"),
        "leaseId": new_id("lse"),
        "fencingToken": epoch + ":1",
        "deviceId": "GPU-01234567-89ab-cdef-0123-456789abcdef",
        "vramBytes": 24 * 1024**3,
        "providerVersion": "synthetic-gpu-provider:1",
        "profileVersion": profile.version,
        "recoveryEpoch": epoch,
        "observationDigest": "b" * 64,
        "observedAt": now.isoformat(),
        "exclusive": True,
        "runtimeCompatible": True,
        "healthy": True,
        "deviceRequestDriver": "nvidia",
    }
    return workload, profile, allocation, now


def test_single_gpu_requires_and_binds_one_fresh_measured_allocation():
    workload, profile, allocation, now = fixture()
    with pytest.raises(DomainError, match="SANDBOX-0002"):
        compile_launch(workload, profile, now=now)

    plan = compile_launch(workload, profile, gpu_allocation=allocation, now=now)
    validate_contract("SandboxLaunchSpec", plan)
    assert plan["gpuAllocation"] == allocation
    assert plan["privileged"] is False
    assert plan["hostAccess"] is False


@pytest.mark.parametrize(
    "mutate,code",
    [
        (lambda w, a, n: w["resources"].update(gpuCount=2), "SANDBOX-0002"),
        (lambda w, a, n: w["resources"].update(minVramBytes=0), "SANDBOX-0002"),
        (
            lambda w, a, n: a.update(observedAt=(n - timedelta(seconds=16)).isoformat()),
            "RES-0003",
        ),
        (lambda w, a, n: a.update(profileVersion="other"), "RES-0003"),
        (lambda w, a, n: a.update(vramBytes=512), "RES-0003"),
    ],
)
def test_gpu_count_staleness_profile_and_vram_remain_fail_closed(mutate, code):
    workload, profile, allocation, now = fixture()
    mutate(workload, allocation, now)
    with pytest.raises(DomainError, match=code):
        compile_launch(workload, profile, gpu_allocation=allocation, now=now)


def test_cpu_launch_rejects_ambient_gpu_allocation():
    workload, profile, allocation, now = fixture()
    workload["resources"].update(gpuCount=0, minVramBytes=0)
    with pytest.raises(DomainError, match="SANDBOX-0002"):
        compile_launch(workload, profile, gpu_allocation=allocation, now=now)
    plan = compile_launch(workload, profile)
    assert "gpuAllocation" not in plan


@pytest.mark.parametrize(
    "field,value",
    [
        ("healthy", False),
        ("exclusive", False),
        ("runtimeCompatible", False),
        ("deviceRequestDriver", "all"),
        ("deviceId", "*"),
    ],
)
def test_gpu_allocation_contract_rejects_broad_or_unhealthy_devices(field, value):
    _, _, allocation, _ = fixture()
    changed = deepcopy(allocation)
    changed[field] = value
    with pytest.raises(DomainError, match="VAL-0002"):
        validate_contract("GPUAllocation", changed)
