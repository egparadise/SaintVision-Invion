"""Compile a fixed restricted launch contract; never execute a host command.

Profile and runtime capabilities come from trusted configuration/Node verification.
These Python objects do not authenticate a Node or prove OS isolation by themselves.
"""

from dataclasses import dataclass
from pathlib import PurePosixPath
import re
from datetime import datetime, timedelta
from .contracts import validate_contract
from .errors import DomainError

REQUIRED_CAPABILITIES = frozenset(
    {
        "filesystem_isolation",
        "network_deny",
        "non_root",
        "no_new_privileges",
        "cap_drop_all",
        "read_only_root",
        "pids_limit",
        "cpu_limit",
        "memory_limit",
        "monotonic_deadline",
        "durable_command_inbox",
        "allocation_fence",
    }
)


@dataclass(frozen=True)
class SandboxProfile:
    version: str
    images: frozenset[str]
    executables: frozenset[str]
    max_cpu_millis: int = 1000
    max_memory_bytes: int = 536870912
    max_timeout_seconds: int = 30

    def __post_init__(self):
        if not isinstance(self.version, str) or not 1 <= len(self.version) <= 200:
            raise ValueError("Versioned sandbox configuration required")
        if (
            type(self.images) is not frozenset
            or type(self.executables) is not frozenset
            or not self.images
            or not self.executables
        ):
            raise ValueError("Immutable nonempty sandbox allowlists required")
        if any(
            not isinstance(image, str) or re.fullmatch(r"sha256:[0-9a-f]{64}", image) is None
            for image in self.images
        ):
            raise ValueError("Pinned image digests required")
        if any(
            not isinstance(exe, str)
            or not exe.startswith("/")
            or str(PurePosixPath(exe)) != exe
            or any(part in {".", "..", ""} for part in exe.split("/")[1:])
            or "\\" in exe
            or "\x00" in exe
            for exe in self.executables
        ):
            raise ValueError("Canonical absolute container executable paths required")
        if any(
            type(n) is not int or not 1 <= n <= 9007199254740991
            for n in [
                self.max_cpu_millis,
                self.max_memory_bytes,
                self.max_timeout_seconds,
            ]
        ):
            raise ValueError("Positive sandbox limits required")


@dataclass(frozen=True)
class RuntimeCapabilities:
    node_id: str
    recovery_epoch: str
    profile_version: str
    expires_at: datetime
    features: frozenset[str]

    def check(self, *, node_id, epoch, profile_version, now):
        if (
            self.node_id != node_id
            or self.recovery_epoch != epoch
            or self.profile_version != profile_version
            or not isinstance(self.expires_at, datetime)
            or self.expires_at.tzinfo is None
            or not now < self.expires_at <= now + timedelta(seconds=30)
            or type(self.features) is not frozenset
            or not REQUIRED_CAPABILITIES.issubset(self.features)
        ):
            raise DomainError(
                "SANDBOX-0001",
                "Current verified sandbox capabilities are unavailable",
                403,
            )


def compile_launch(workload, profile: SandboxProfile, *, workspace_input=None):
    validate_contract("WorkloadSpec", workload)
    resources = workload["resources"]
    argv = workload["command"]
    if (
        workload["imageDigest"] not in profile.images
        or argv[0] not in profile.executables
        or len(argv) > 128
        or any(not arg or "\x00" in arg or len(arg) > 4096 for arg in argv)
        or resources["cpuMillis"] > profile.max_cpu_millis
        or resources["memoryBytes"] > profile.max_memory_bytes
        or resources["gpuCount"] != 0
        or resources["minVramBytes"] != 0
        or workload["timeoutSeconds"] > profile.max_timeout_seconds
    ):
        raise DomainError("SANDBOX-0002", "Workload exceeds the approved sandbox profile", 403)
    plan = {
        "profileVersion": profile.version,
        "imageDigest": workload["imageDigest"],
        "argv": list(argv),
        "workspaceId": workload["workspaceId"],
        "workingDirectory": "/workspace",
        "workspaceMode": "ephemeral",
        "cpuMillis": resources["cpuMillis"],
        "memoryBytes": resources["memoryBytes"],
        "timeoutSeconds": workload["timeoutSeconds"],
        "pidsLimit": 64,
        "userId": 65532,
        "network": "none",
        "rootfsReadOnly": True,
        "capDropAll": True,
        "noNewPrivileges": True,
        "privileged": False,
        "hostAccess": False,
    }
    if "workspaceResume" in workload or "workspaceStart" in workload:
        if workspace_input is None:
            raise DomainError("AUTH-0044", "Verified Workspace input required", 403)
        plan.update(
            workspaceMode="initialized" if "workspaceStart" in workload else "restored",
            workspaceInput=workspace_input,
        )
    elif workspace_input is not None:
        raise DomainError("AUTH-0044", "Unexpected Workspace input", 403)
    validate_contract("SandboxLaunchSpec", plan)
    return plan
