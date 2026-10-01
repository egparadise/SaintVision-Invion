#!/usr/bin/env python3
"""Run the opt-in S08-BE rootless BuildKit reference lane.

In process mode the caller passes the RootlessKit namespace PID. Container mode
derives the PID from a validated ``docker inspect`` result. This tool records
only redacted process/worker facts, then exercises the concrete transport
against the repository's scratch-only fixture. The emitted JSON is reference
evidence and is not a product ``EvidenceEnvelope``.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "control-plane" / "src"))

from inv.buildkit_transport import (  # noqa: E402
    BuildkitTransportConfiguration,
    RootlessBuildkitTransport,
)
from inv.errors import DomainError  # noqa: E402
from inv.policy import action_digest  # noqa: E402


TENANT = "123e4567-e89b-12d3-a456-426614174000"
ULID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
INSTANCE = "builder-ci-rootless-1"
PROFILE = "buildkit-rootless-ci-reference-v1"
EPOCH = 7


def _command(*arguments: str) -> str:
    result = subprocess.run(
        list(arguments),
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def _status(pid: int) -> dict[str, str]:
    values = {}
    for line in Path(f"/proc/{pid}/status").read_text(encoding="utf-8").splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            values[key] = value.strip()
    return values


def _host_uid(pid: int) -> int:
    rows = Path(f"/proc/{pid}/uid_map").read_text(encoding="ascii").splitlines()
    mappings = [tuple(int(part) for part in row.split()) for row in rows]
    if not mappings or mappings[0][0] != 0 or mappings[0][1] <= 0:
        raise RuntimeError("buildkitd is not in a rootless user namespace")
    return mappings[0][1]


def _lsm() -> str:
    apparmor = Path("/sys/module/apparmor/parameters/enabled")
    if apparmor.is_file() and apparmor.read_text(encoding="ascii").strip().lower() == "y":
        return "apparmor"
    selinux = Path("/sys/fs/selinux/enforce")
    if selinux.is_file():
        return "selinux"
    return "unavailable-ci-reference"


def _process_health_receipt(args, observed_at: datetime) -> dict:
    status = _status(args.daemon_pid)
    stat_fields = Path(f"/proc/{args.daemon_pid}/stat").read_text(encoding="ascii").split()
    return {
        "schemaVersion": 1,
        "builderInstanceId": INSTANCE,
        "builderProfileId": PROFILE,
        "recoveryEpoch": EPOCH,
        "address": args.address,
        "pid": args.daemon_pid,
        "hostUid": _host_uid(args.daemon_pid),
        "processStartTicks": int(stat_fields[21]),
        "rootless": True,
        "privileged": False,
        "hostAccess": False,
        "entitlements": [],
        "devices": [],
        "binds": [],
        "observedAt": observed_at.isoformat(),
        "buildkitVersion": _command(str(args.buildkitd), "--version"),
        "rootlesskitVersion": _command(str(args.rootlesskit), "--version"),
        "runtimeIdentity": "sha256:" + hashlib.sha256(args.buildkitd.read_bytes()).hexdigest(),
        "isolation": {
            "userNamespace": True,
            "seccompMode": "filter" if status.get("Seccomp") == "2" else "unavailable-ci-reference",
            "lsm": _lsm(),
            "noNewPrivileges": status.get("NoNewPrivs") == "1",
            "cgroupMode": (
                "v2"
                if Path("/sys/fs/cgroup/cgroup.controllers").is_file()
                else "unavailable-ci-reference"
            ),
        },
    }


def _container_health_receipt(args, observed_at: datetime) -> dict:
    values = json.loads(_command("docker", "inspect", args.container_name))
    value = _validated_container_inspect(values)
    state = value["State"]
    status = _status(state["Pid"])
    uid = int(status["Uid"].split()[0])
    if uid <= 0:
        raise RuntimeError("rootless BuildKit container process is not an unprivileged user")
    stat_fields = Path(f"/proc/{state['Pid']}/stat").read_text(encoding="ascii").split()
    image_digest = args.runtime_image.rsplit("@", 1)[-1]
    if not image_digest.startswith("sha256:"):
        raise RuntimeError("rootless BuildKit image is not digest pinned")
    return {
        "schemaVersion": 1,
        "builderInstanceId": INSTANCE,
        "builderProfileId": PROFILE,
        "recoveryEpoch": EPOCH,
        "address": args.address,
        "pid": state["Pid"],
        "hostUid": uid,
        "processStartTicks": int(stat_fields[21]),
        "rootless": True,
        "privileged": False,
        "hostAccess": False,
        "entitlements": [],
        "devices": [],
        "binds": [],
        "observedAt": observed_at.isoformat(),
        "buildkitVersion": _command(
            "docker", "exec", args.container_name, "buildkitd", "--version"
        ),
        "rootlesskitVersion": _command(
            "docker", "exec", args.container_name, "rootlesskit", "--version"
        ),
        "runtimeIdentity": image_digest,
        "isolation": {
            "userNamespace": True,
            # The official rootless image needs these host filters relaxed on a
            # hosted runner. This is why the result remains ci-reference only.
            "seccompMode": "unavailable-ci-reference",
            "lsm": "unavailable-ci-reference",
            "noNewPrivileges": status.get("NoNewPrivs") == "1",
            "cgroupMode": (
                "v2"
                if Path("/sys/fs/cgroup/cgroup.controllers").is_file()
                else "unavailable-ci-reference"
            ),
        },
    }


def _validated_container_inspect(values: object) -> dict:
    """Reject any runtime boundary wider than the declared CI reference."""

    if not isinstance(values, list) or len(values) != 1 or not isinstance(values[0], dict):
        raise RuntimeError("rootless BuildKit container boundary is broader than declared: shape")
    value = values[0]
    state, config, host = value["State"], value["Config"], value["HostConfig"]
    ports = value.get("NetworkSettings", {}).get("Ports", {}).get("1234/tcp")
    mounts = value.get("Mounts") or []
    user = config.get("User")
    if (
        state.get("Running") is not True
        or type(state.get("Pid")) is not int
        or state["Pid"] <= 1
        or not isinstance(user, str)
        or user in {"", "0", "root", "0:0", "root:root"}
    ):
        raise RuntimeError(
            "rootless BuildKit container boundary is broader than declared: identity"
        )
    if host.get("Privileged") is not False:
        raise RuntimeError(
            "rootless BuildKit container boundary is broader than declared: privileged"
        )
    if set(host.get("SecurityOpt") or []) != {
        "seccomp=unconfined",
        "apparmor=unconfined",
    }:
        observed_options = ",".join(sorted(host.get("SecurityOpt") or []))
        raise RuntimeError(
            "rootless BuildKit container boundary is broader than declared: "
            f"security-opt={observed_options}"
        )
    if host.get("Binds") not in (None, []):
        raise RuntimeError("rootless BuildKit container boundary is broader than declared: bind")
    if host.get("Devices") not in (None, []):
        raise RuntimeError("rootless BuildKit container boundary is broader than declared: device")
    if host.get("CapAdd") not in (None, []):
        raise RuntimeError(
            "rootless BuildKit container boundary is broader than declared: capability"
        )
    if host.get("MaskedPaths") not in (None, []) or host.get("ReadonlyPaths") not in (None, []):
        raise RuntimeError(
            "rootless BuildKit container boundary is broader than declared: system-path"
        )
    if any(
        mount.get("Type") != "tmpfs"
        or mount.get("Destination") != "/home/user/.local/share/buildkit"
        or mount.get("RW") is not True
        or mount.get("Source") not in (None, "")
        for mount in mounts
    ):
        raise RuntimeError("rootless BuildKit container boundary is broader than declared: mount")
    if (
        not isinstance(ports, list)
        or len(ports) != 1
        or ports[0].get("HostIp") != "127.0.0.1"
        or ports[0].get("HostPort") != "1234"
    ):
        raise RuntimeError("rootless BuildKit container boundary is broader than declared: network")
    if config.get("Labels", {}).get("ai.saintvision.s08-buildkit-reference") != os.environ.get(
        "GITHUB_RUN_ID"
    ):
        raise RuntimeError(
            "rootless BuildKit container boundary is broader than declared: ownership"
        )
    return value


def _health_receipt(args, observed_at: datetime) -> dict:
    if args.container_name:
        return _container_health_receipt(args, observed_at)
    return _process_health_receipt(args, observed_at)


def _request(head: str, tree: str) -> dict:
    return {
        "apiVersion": "inv.saintvision.ai/v1alpha1",
        "kind": "BuildRequest",
        "tenantId": TENANT,
        "projectId": f"prj_{ULID}",
        "workspaceId": f"wsp_{ULID}",
        "sourceCommitSha": head,
        "sourceTreeSha": tree,
        "contextPath": "tests/fixtures/buildkit-reference",
        "dockerfilePath": "tests/fixtures/buildkit-reference/Dockerfile",
        "targetPlatform": "linux/amd64",
        "targetStage": "runtime",
        "networkPolicyId": "none",
        "cachePolicyId": "cachepol_s08-reference",
        "secretRefIds": [],
        "timeoutSeconds": 180,
    }


def _plan(request: dict, observation_digest: str, now: datetime) -> dict:
    expires = (now + timedelta(minutes=3)).isoformat().replace("+00:00", "Z")
    return {
        "apiVersion": "inv.saintvision.ai/v1alpha1",
        "kind": "BuildPlan",
        "tenantId": request["tenantId"],
        "projectId": request["projectId"],
        "workspaceId": request["workspaceId"],
        "traceId": hashlib.sha256(f"{request['sourceCommitSha']}:rootless".encode()).hexdigest()[
            :32
        ],
        "requestDigest": action_digest(request),
        "actionDigest": action_digest(
            {
                "action": "runtime.build.execute",
                "tenantId": request["tenantId"],
                "projectId": request["projectId"],
                "workspaceId": request["workspaceId"],
                "requestDigest": action_digest(request),
            }
        ),
        "policyDecisionId": "policy-s08-buildkit-ci-reference",
        "policyVersion": "s08-build-v1",
        "policyExpiresAt": expires,
        "builderInstanceId": INSTANCE,
        "builderProfileId": PROFILE,
        "builderObservationDigest": observation_digest,
        "recoveryEpoch": EPOCH,
        "rootless": True,
        "privileged": False,
        "hostAccess": False,
        "networkMode": "none",
        "networkPolicyId": "none",
        "egressAllowlistDigest": "0" * 64,
        "devices": [],
        "binds": [],
        "budget": {
            "cpuMillis": 1000,
            "memoryBytes": 1073741824,
            "storageBytes": 1073741824,
        },
        "lease": {
            "leaseId": f"lse_{ULID}",
            "resourceId": f"res_{ULID}",
            "fencingToken": "223e4567-e89b-12d3-a456-426614174000:7",
            "expiresAt": expires,
        },
        "cacheNamespaceDigest": hashlib.sha256(b"s08-ci-reference-cache").hexdigest(),
        "secretRefsDigest": hashlib.sha256(b"[]").hexdigest(),
        "resolvedBaseImageDigests": ["sha256:" + "0" * 64],
    }


def _junit(path: Path, *, error: BaseException | None = None) -> None:
    suite = ET.Element(
        "testsuite",
        name="s08-rootless-buildkit-reference",
        tests="1",
        failures="1" if error else "0",
        errors="0",
        skipped="0",
    )
    case = ET.SubElement(suite, "testcase", name="rootless_buildkit_oci_roundtrip")
    if error:
        failure = ET.SubElement(case, "failure", message=type(error).__name__)
        failure.text = "Reference roundtrip failed; inspect redacted daemon log artifact."
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(suite).write(path, encoding="utf-8", xml_declaration=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--buildctl", type=Path, required=True)
    parser.add_argument("--buildkitd", type=Path)
    parser.add_argument("--rootlesskit", type=Path)
    parser.add_argument("--container-name")
    parser.add_argument("--runtime-image")
    parser.add_argument("--address", required=True)
    parser.add_argument("--daemon-pid", type=int)
    parser.add_argument("--health-receipt", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--junit", type=Path, required=True)
    args = parser.parse_args(argv)
    if bool(args.container_name) != bool(args.runtime_image):
        parser.error("--container-name and --runtime-image are required together")
    if not args.container_name and (args.buildkitd is None or args.rootlesskit is None):
        parser.error("process mode requires --buildkitd and --rootlesskit")
    if not args.container_name and args.daemon_pid is None:
        parser.error("process mode requires --daemon-pid")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.health_receipt.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    failure_stage = "health-receipt"
    try:
        receipt = _health_receipt(args, now)
        args.health_receipt.write_text(
            json.dumps(receipt, sort_keys=True, separators=(",", ":")), encoding="utf-8"
        )
        args.health_receipt.chmod(0o600)
        failure_stage = "source-binding"
        head = _command("git", "rev-parse", "HEAD")
        expected = os.environ.get("INV_EVIDENCE_CODE_SHA")
        if expected != head:
            raise RuntimeError("exact hosted head is not the checked-out source")
        tree = _command("git", "rev-parse", "HEAD^{tree}")
        failure_stage = "transport-configuration"
        configuration = BuildkitTransportConfiguration(
            buildctl_path=args.buildctl,
            address=args.address,
            source_root=ROOT,
            health_receipt_path=args.health_receipt,
            builder_instance_id=INSTANCE,
            builder_profile_id=PROFILE,
            recovery_epoch=EPOCH,
        )
        transport = RootlessBuildkitTransport.configured(
            configuration,
            environment={
                "INV_BUILDKIT_REFERENCE_ENABLED": "1",
                "PATH": os.environ.get("PATH", ""),
                "HOME": os.environ.get("HOME", ""),
                "XDG_RUNTIME_DIR": os.environ.get("XDG_RUNTIME_DIR", ""),
            },
        )
        failure_stage = "provider-measurement"
        measured = transport.measure()
        request = _request(head, tree)
        failure_stage = "reference-roundtrip"
        result = transport.reference_roundtrip(
            request,
            _plan(request, measured.provider.observation_digest, now),
            args.output_dir,
        )
        result["codeSha"] = head
        result["checkoutTreeSha"] = tree
        result["cleanCheckout"] = True
        (args.output_dir / "rootless-buildkit-reference.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        _junit(args.junit)
        return 0
    except BaseException as error:
        _junit(args.junit, error=error)
        failure = {
            "schemaVersion": 1,
            "targetKind": "ci-reference",
            "verdict": "INVALID_RUN",
            "operationalAcceptanceAssessed": False,
            "productDispatchEnabled": False,
            "failureClass": type(error).__name__,
            "failureStage": failure_stage,
        }
        if str(error).startswith("rootless BuildKit container boundary is broader than declared:"):
            failure["failureDetail"] = str(error)
        elif isinstance(error, DomainError):
            failure["failureCode"] = error.code
            failure["failureDetail"] = error.detail
        (args.output_dir / "rootless-buildkit-reference.json").write_text(
            json.dumps(failure, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
