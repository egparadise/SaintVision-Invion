"""Fail-closed tests for the S08-BE rootless BuildKit reference transport."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess

import pytest

from inv.buildkit_transport import (
    BuildkitTransportConfiguration,
    RootlessBuildkitTransport,
    _normalized_platforms,
)
from inv.errors import DomainError


NOW = datetime(2026, 10, 2, 3, 0, tzinfo=timezone.utc)
TENANT = "123e4567-e89b-12d3-a456-426614174000"
ULID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
HEAD = "a" * 40
TREE = "b" * 40


def test_worker_platforms_normalize_buildkit_strings_and_oci_structures():
    assert _normalized_platforms(
        [
            "linux/amd64",
            {"os": "linux", "architecture": "amd64", "variant": "v3"},
        ]
    ) == ("linux/amd64", "linux/amd64/v3")


@pytest.mark.parametrize(
    "value",
    [
        [],
        [{"os": "linux"}],
        [{"os": "linux", "architecture": "amd64", "unknown": "x"}],
        [{"os": "Linux", "architecture": "amd64"}],
        ["linux"],
        ["linux/amd64/"],
    ],
)
def test_worker_platforms_reject_unknown_or_ambiguous_shapes(value):
    with pytest.raises(DomainError, match="RES-0006"):
        _normalized_platforms(value)


def _health():
    return {
        "schemaVersion": 1,
        "builderInstanceId": "builder-ci-rootless-1",
        "builderProfileId": "buildkit-rootless-ci-reference-v1",
        "recoveryEpoch": 7,
        "address": "unix:///run/user/1001/buildkit/buildkitd.sock",
        "pid": 8123,
        "hostUid": 1001,
        "processStartTicks": 123456,
        "rootless": True,
        "privileged": False,
        "hostAccess": False,
        "entitlements": [],
        "devices": [],
        "binds": [],
        "observedAt": NOW.isoformat(),
        "buildkitVersion": "buildkitd github.com/moby/buildkit v0.20.2",
        "rootlesskitVersion": "rootlesskit version 2.3.4",
        "runtimeIdentity": "sha256:" + "7" * 64,
        "isolation": {
            "userNamespace": True,
            "seccompMode": "filter",
            "lsm": "apparmor",
            "noNewPrivileges": False,
            "cgroupMode": "v2",
        },
        "fieldSources": {
            "pid": "caller-passed-rootlesskit-process",
            "processStartTicks": "proc-rootlesskit-process",
            "rootless": "proc-uid-map",
            "privileged": "caller-asserted-reference-boundary",
            "hostAccess": "caller-asserted-reference-boundary",
            "entitlements": "caller-asserted-reference-boundary",
            "devices": "caller-asserted-reference-boundary",
            "binds": "caller-asserted-reference-boundary",
            "runtimeIdentity": "buildkitd-binary-sha256",
            "seccompMode": "proc-process-status",
            "lsm": "host-lsm-detection",
        },
    }


class _Runner:
    def __init__(self, root: Path):
        self.root = root
        self.calls = []
        self.fail = None
        self.workers = [
            {
                "ID": "worker-1",
                "Platforms": [{"architecture": "amd64", "os": "linux"}],
                "Labels": {"org.mobyproject.buildkit.worker.executor": "oci"},
            }
        ]
        self.git = {
            ("rev-parse", "HEAD"): HEAD + "\n",
            ("rev-parse", "HEAD^{tree}"): TREE + "\n",
            ("status", "--porcelain=v1", "--untracked-files=all"): "",
        }

    def run(self, arguments, *, cwd, timeout, environment):
        arguments = tuple(arguments)
        self.calls.append((arguments, cwd, timeout, dict(environment)))
        if self.fail and self.fail in arguments:
            return subprocess.CompletedProcess(arguments, 1, "", "redacted failure")
        if "debug" in arguments:
            return subprocess.CompletedProcess(arguments, 0, json.dumps(self.workers), "")
        if arguments[0] == "git":
            key = arguments[3:]
            return subprocess.CompletedProcess(arguments, 0, self.git[key], "")
        if "build" in arguments:
            output = Path(
                arguments[arguments.index("--output") + 1].split("dest=", 1)[1].split(",", 1)[0]
            )
            metadata = Path(arguments[arguments.index("--metadata-file") + 1])
            output.write_bytes(b"oci-reference")
            metadata.write_text(
                json.dumps(
                    {
                        "containerimage.digest": "sha256:" + "c" * 64,
                        "containerimage.config.digest": "sha256:" + "d" * 64,
                    }
                ),
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(arguments, 0, "build complete", "")
        raise AssertionError(arguments)


@pytest.fixture
def boundary(tmp_path):
    source = tmp_path / "source"
    context = source / "services" / "worker"
    context.mkdir(parents=True)
    (context / "Dockerfile").write_text("FROM scratch AS runtime\n", encoding="utf-8")
    health_path = tmp_path / "health.json"
    health_path.write_text(json.dumps(_health()), encoding="utf-8")
    health_path.chmod(0o600)
    configuration = BuildkitTransportConfiguration(
        buildctl_path=Path("/opt/saintvision/buildkit/bin/buildctl"),
        address=_health()["address"],
        source_root=source,
        health_receipt_path=health_path,
        builder_instance_id=_health()["builderInstanceId"],
        builder_profile_id=_health()["builderProfileId"],
        recovery_epoch=7,
    )
    runner = _Runner(source)
    transport = RootlessBuildkitTransport(
        configuration,
        runner=runner,
        environment={"PATH": "/usr/bin", "HOME": "/home/runner", "UNRELATED_SECRET": "no"},
        now=lambda: NOW,
    )
    return transport, runner, health_path


def _request():
    return {
        "apiVersion": "inv.saintvision.ai/v1alpha1",
        "kind": "BuildRequest",
        "tenantId": TENANT,
        "projectId": f"prj_{ULID}",
        "workspaceId": f"wsp_{ULID}",
        "sourceCommitSha": HEAD,
        "sourceTreeSha": TREE,
        "contextPath": "services/worker",
        "dockerfilePath": "services/worker/Dockerfile",
        "targetPlatform": "linux/amd64",
        "targetStage": "runtime",
        "networkPolicyId": "none",
        "cachePolicyId": "cachepol_s08-default",
        "secretRefIds": [],
        "timeoutSeconds": 60,
    }


def _plan(observation_digest):
    return {
        "apiVersion": "inv.saintvision.ai/v1alpha1",
        "kind": "BuildPlan",
        "tenantId": TENANT,
        "projectId": f"prj_{ULID}",
        "workspaceId": f"wsp_{ULID}",
        "traceId": "c" * 32,
        "requestDigest": "d" * 64,
        "actionDigest": "e" * 64,
        "policyDecisionId": "decision-1",
        "policyVersion": "s08-build-v1",
        "policyExpiresAt": "2026-10-02T04:00:00Z",
        "builderInstanceId": _health()["builderInstanceId"],
        "builderProfileId": _health()["builderProfileId"],
        "builderObservationDigest": observation_digest,
        "recoveryEpoch": 7,
        "rootless": True,
        "privileged": False,
        "hostAccess": False,
        "networkMode": "none",
        "networkPolicyId": "none",
        "egressAllowlistDigest": "0" * 64,
        "devices": [],
        "binds": [],
        "budget": {"cpuMillis": 1000, "memoryBytes": 1073741824, "storageBytes": 1073741824},
        "lease": {
            "leaseId": f"lse_{ULID}",
            "resourceId": f"res_{ULID}",
            "fencingToken": "223e4567-e89b-12d3-a456-426614174000:7",
            "expiresAt": "2026-10-02T03:01:00Z",
        },
        "cacheNamespaceDigest": "f" * 64,
        "secretRefsDigest": "0" * 64,
        "resolvedBaseImageDigests": ["sha256:" + "1" * 64],
    }


def test_configuration_is_disabled_unless_exact_opt_in(boundary):
    transport, _runner, _receipt = boundary
    with pytest.raises(DomainError, match="RES-0006"):
        RootlessBuildkitTransport.configured(transport.configuration, environment={})
    enabled = RootlessBuildkitTransport.configured(
        transport.configuration,
        environment={"INV_BUILDKIT_REFERENCE_ENABLED": "1"},
        runner=_runner,
        now=lambda: NOW,
    )
    assert isinstance(enabled, RootlessBuildkitTransport)


def test_product_dispatch_and_cleanup_remain_disconnected(boundary):
    transport, _runner, _receipt = boundary
    with pytest.raises(DomainError, match="RES-0006"):
        transport.dispatch(object())
    with pytest.raises(DomainError, match="VERIFY-0022"):
        transport.cancel_and_quarantine(object(), "SYS-0001")


def test_measure_binds_exact_protected_health_and_live_worker(boundary):
    transport, runner, _receipt = boundary
    measured = transport.measure()
    assert measured.provider.builder_instance_id == _health()["builderInstanceId"]
    assert measured.provider.builder_profile_id == _health()["builderProfileId"]
    assert measured.provider.recovery_epoch == 7
    assert len(measured.provider.observation_digest) == 64
    assert measured.worker_id == "worker-1"
    assert measured.platforms == ("linux/amd64",)
    assert measured.process_measurement == {
        "pid": 8123,
        "hostUid": 1001,
        "processStartTicks": 123456,
        "address": _health()["address"],
        "observedAt": NOW.isoformat(),
        "rootless": True,
        "privileged": False,
        "hostAccess": False,
        "entitlements": [],
        "runtimeIdentity": "sha256:" + "7" * 64,
        "fieldSources": _health()["fieldSources"],
    }
    arguments, _cwd, timeout, environment = runner.calls[-1]
    assert arguments[1:4] == ("--addr", _health()["address"], "debug")
    assert timeout == 10
    assert set(environment) == {"PATH", "HOME", "XDG_RUNTIME_DIR", "BUILDKIT_PROGRESS"}


@pytest.mark.parametrize(
    "mutate,code",
    [
        (lambda value: value.__setitem__("rootless", False), "RES-0006"),
        (lambda value: value.__setitem__("hostUid", 0), "RES-0006"),
        (lambda value: value.__setitem__("entitlements", ["security.insecure"]), "RES-0006"),
        (lambda value: value.__setitem__("privileged", True), "RES-0006"),
        (lambda value: value.__setitem__("hostAccess", True), "RES-0006"),
        (lambda value: value.__setitem__("recoveryEpoch", 8), "RES-0006"),
        (lambda value: value.__setitem__("address", "tcp://127.0.0.1:4321"), "RES-0006"),
        (lambda value: value.__setitem__("devices", ["/dev/dri"]), "RES-0006"),
        (lambda value: value.__setitem__("unexpected", True), "RES-0006"),
        (
            lambda value: value.__setitem__(
                "observedAt", (NOW - timedelta(seconds=16)).isoformat()
            ),
            "RES-0003",
        ),
        (
            lambda value: value.__setitem__(
                "observedAt", (NOW + timedelta(microseconds=1)).isoformat()
            ),
            "RES-0003",
        ),
        (
            lambda value: value["isolation"].__setitem__("userNamespace", False),
            "RES-0006",
        ),
    ],
)
def test_measure_rejects_unqualified_or_stale_health(boundary, mutate, code):
    transport, _runner, path = boundary
    value = _health()
    mutate(value)
    path.write_text(json.dumps(value), encoding="utf-8")
    path.chmod(0o600)
    with pytest.raises(DomainError, match=code):
        transport.measure()


def test_measure_rejects_nonexclusive_or_failed_worker_probe(boundary):
    transport, runner, _receipt = boundary
    runner.workers.append(deepcopy(runner.workers[0]))
    with pytest.raises(DomainError, match="RES-0006"):
        transport.measure()
    runner.workers.pop()
    runner.fail = "debug"
    with pytest.raises(DomainError, match="RES-0006"):
        transport.measure()


def test_reference_roundtrip_uses_fixed_no_network_oci_export(boundary, tmp_path):
    transport, runner, _receipt = boundary
    measured = transport.measure()
    output = tmp_path / "out"
    output.mkdir()
    (output / "rootless-buildkit-roundtrip.oci.tar").write_text("stale", encoding="utf-8")
    report = transport.reference_roundtrip(
        _request(), _plan(measured.provider.observation_digest), output
    )
    assert report["verdict"] == "MEASURED_PASS"
    assert report["targetKind"] == "ci-reference"
    assert report["operationalAcceptanceAssessed"] is False
    assert report["productDispatchEnabled"] is False
    assert "lease-release-not-bound" in report["limitations"]
    assert len(report["ociArchiveSha256"]) == 64
    build = next(call[0] for call in runner.calls if "build" in call[0])
    assert "--secret" not in build
    assert "--allow" not in build
    assert "--import-cache" not in build
    assert "--export-cache" not in build
    assert "force-network-mode=none" in build
    assert any(value.startswith("type=oci,dest=") for value in build)


@pytest.mark.parametrize(
    "mutate,code",
    [
        (lambda request, _plan: request.__setitem__("secretRefIds", [f"sec_{ULID}"]), "AUTH-0012"),
        (
            lambda request, _plan: request.__setitem__("networkPolicyId", "netpol_allow"),
            "AUTH-0012",
        ),
        (
            lambda request, plan: (
                request.__setitem__("networkPolicyId", "netpol_allow"),
                plan.update(
                    {
                        "networkMode": "allowlist",
                        "networkPolicyId": "netpol_allow",
                        "egressAllowlistDigest": "8" * 64,
                    }
                ),
            ),
            "AUTH-0012",
        ),
        (
            lambda _request, plan: plan.__setitem__("builderObservationDigest", "9" * 64),
            "VERIFY-0002",
        ),
        (
            lambda _request, plan: plan.__setitem__("builderInstanceId", "builder-other"),
            "VERIFY-0002",
        ),
        (
            lambda request, _plan: request.__setitem__("targetPlatform", "linux/arm64"),
            "VERIFY-0002",
        ),
    ],
)
def test_reference_roundtrip_rejects_unbound_or_broader_inputs(boundary, tmp_path, mutate, code):
    transport, runner, _receipt = boundary
    measured = transport.measure()
    request = _request()
    plan = _plan(measured.provider.observation_digest)
    mutate(request, plan)
    with pytest.raises(DomainError, match=code):
        transport.reference_roundtrip(request, plan, tmp_path / "out")
    assert not any("build" in call[0] for call in runner.calls)


@pytest.mark.parametrize(
    "git_key,value",
    [
        (("rev-parse", "HEAD"), "9" * 40 + "\n"),
        (("rev-parse", "HEAD^{tree}"), "8" * 40 + "\n"),
        (("status", "--porcelain=v1", "--untracked-files=all"), " M tracked.txt\n"),
    ],
)
def test_reference_roundtrip_requires_exact_clean_source(boundary, tmp_path, git_key, value):
    transport, runner, _receipt = boundary
    measured = transport.measure()
    runner.git[git_key] = value
    with pytest.raises(DomainError, match="VERIFY-0002"):
        transport.reference_roundtrip(
            _request(), _plan(measured.provider.observation_digest), tmp_path / "out"
        )


def test_reference_roundtrip_rejects_failed_build_or_incomplete_metadata(boundary, tmp_path):
    transport, runner, _receipt = boundary
    measured = transport.measure()
    request, plan = _request(), _plan(measured.provider.observation_digest)
    runner.fail = "build"
    with pytest.raises(DomainError, match="RES-0006"):
        transport.reference_roundtrip(request, plan, tmp_path / "failed")

    runner.fail = None
    original = runner.run

    def incomplete(arguments, **kwargs):
        result = original(arguments, **kwargs)
        if "build" in arguments:
            metadata = Path(arguments[arguments.index("--metadata-file") + 1])
            metadata.write_text("{}", encoding="utf-8")
        return result

    runner.run = incomplete
    with pytest.raises(DomainError, match="VERIFY-0002"):
        transport.reference_roundtrip(request, plan, tmp_path / "incomplete")
