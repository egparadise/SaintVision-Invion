"""Lane and evidence-envelope guards for the hosted BuildKit reference run."""

from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "run_buildkit_rootless_roundtrip.py"
LANE = ROOT / "tools" / "run_buildkit_rootless_lane.sh"
WORKFLOW = ROOT / ".github" / "workflows" / "s08-buildkit-reference.yml"
HEAD = "a" * 40
TREE = "b" * 40


def _module():
    spec = importlib.util.spec_from_file_location("run_buildkit_rootless_roundtrip", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def test_lane_is_opt_in_pinned_and_never_uses_privileged_or_host_socket():
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    trigger = workflow[True]["workflow_dispatch"]["inputs"]["correlation_id"]
    assert trigger == {
        "description": "Opaque id used only to bind this exact manual run",
        "required": False,
        "default": "",
    }
    assert workflow["concurrency"]["cancel-in-progress"] is False
    job = workflow["jobs"]["rootless-roundtrip"]
    assert job["env"]["BUILDKIT_VERSION"] == "v0.20.2"
    assert len(job["env"]["BUILDKIT_ARCHIVE_SHA256"]) == 64
    assert job["env"]["BUILDKIT_ROOTLESS_IMAGE"] == (
        "docker.io/moby/buildkit@sha256:cb5bb371545222c430528556acfdf424144b69897f5deaad391bd227187e90df"
    )
    text = json.dumps(job, sort_keys=True) + LANE.read_text(encoding="utf-8")
    assert "--privileged" not in text
    assert "/var/run/docker.sock" not in text
    assert "docker run" in text
    assert "--security-opt seccomp=unconfined" in text
    assert "--publish 127.0.0.1:1234:1234" in text
    assert '"$SV_BUILDKIT_RUNTIME_IMAGE" \\\n  --addr tcp://0.0.0.0:1234' in text
    assert "kernel.apparmor_restrict_unprivileged_userns=0" in text
    assert "pip install --disable-pip-version-check -e services/control-plane" in text
    checkout = next(step for step in job["steps"] if step.get("uses") == "actions/checkout@v4")
    assert checkout["with"]["persist-credentials"] is False


def test_lane_shell_is_syntactically_valid():
    result = subprocess.run(
        ["bash", "-n", "tools/run_buildkit_rootless_lane.sh"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_reference_plan_has_no_secret_network_device_or_bind_capability():
    module = _module()
    request = module._request(HEAD, TREE)
    plan = module._plan(
        request,
        "c" * 64,
        datetime(2026, 10, 2, 0, 0, tzinfo=timezone.utc),
    )
    assert request["secretRefIds"] == []
    assert request["networkPolicyId"] == "none"
    assert plan["rootless"] is True
    assert plan["privileged"] is False
    assert plan["hostAccess"] is False
    assert plan["networkMode"] == "none"
    assert plan["devices"] == []
    assert plan["binds"] == []


def _container_inspect():
    return [
        {
            "State": {"Running": True, "Pid": 3210},
            "Config": {
                "User": "user",
                "Labels": {"ai.saintvision.s08-buildkit-reference": "55"},
            },
            "HostConfig": {
                "Privileged": False,
                "SecurityOpt": [
                    "seccomp=unconfined",
                    "apparmor=unconfined",
                    "systempaths=unconfined",
                ],
                "Binds": None,
                "Devices": [],
                "CapAdd": None,
            },
            "NetworkSettings": {
                "Ports": {"1234/tcp": [{"HostIp": "127.0.0.1", "HostPort": "1234"}]}
            },
            "Mounts": [
                {
                    "Type": "tmpfs",
                    "Source": "",
                    "Destination": "/home/user/.local/share/buildkit",
                    "RW": True,
                }
            ],
        }
    ]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value[0]["HostConfig"].__setitem__("Privileged", True),
        lambda value: value[0]["HostConfig"].__setitem__("Binds", ["/var/run/docker.sock:/x"]),
        lambda value: value[0]["HostConfig"].__setitem__("Devices", [{"PathOnHost": "/dev/kvm"}]),
        lambda value: value[0]["HostConfig"].__setitem__("CapAdd", ["SYS_ADMIN"]),
        lambda value: value[0]["Config"].__setitem__("User", "root"),
        lambda value: value[0]["NetworkSettings"]["Ports"]["1234/tcp"][0].__setitem__(
            "HostIp", "0.0.0.0"
        ),
        lambda value: value[0].__setitem__(
            "Mounts",
            [
                {
                    "Type": "bind",
                    "Source": "/host",
                    "Destination": "/host",
                    "RW": True,
                }
            ],
        ),
    ],
)
def test_container_boundary_rejects_privilege_host_device_and_broad_publish(monkeypatch, mutate):
    module = _module()
    monkeypatch.setenv("GITHUB_RUN_ID", "55")
    value = _container_inspect()
    mutate(value)
    with pytest.raises(RuntimeError, match="broader than declared"):
        module._validated_container_inspect(value)


def test_container_boundary_accepts_only_owned_rootless_shape(monkeypatch):
    module = _module()
    monkeypatch.setenv("GITHUB_RUN_ID", "55")
    assert module._validated_container_inspect(_container_inspect())["State"]["Pid"] == 3210


def test_container_mode_derives_pid_from_inspect_instead_of_cli(monkeypatch, tmp_path):
    module = _module()
    binary = tmp_path / "buildctl"
    binary.write_text("binary", encoding="utf-8")
    monkeypatch.setenv("INV_EVIDENCE_CODE_SHA", HEAD)
    monkeypatch.setattr(
        module, "_health_receipt", lambda *_args: (_ for _ in ()).throw(RuntimeError("stop"))
    )
    output, junit = tmp_path / "out", tmp_path / "junit.xml"

    result = module.main(
        [
            "--buildctl",
            str(binary),
            "--container-name",
            "rootless-builder",
            "--runtime-image",
            "image@sha256:" + "c" * 64,
            "--address",
            "tcp://127.0.0.1:1234",
            "--health-receipt",
            str(tmp_path / "health.json"),
            "--output-dir",
            str(output),
            "--junit",
            str(junit),
        ]
    )

    assert result == 1
    assert (
        json.loads((output / "rootless-buildkit-reference.json").read_text(encoding="utf-8"))[
            "failureClass"
        ]
        == "RuntimeError"
    )
    assert (
        json.loads((output / "rootless-buildkit-reference.json").read_text(encoding="utf-8"))[
            "failureStage"
        ]
        == "health-receipt"
    )


def test_main_emits_reference_only_evidence_and_exact_junit(monkeypatch, tmp_path):
    module = _module()
    bins = []
    for name in ("buildctl", "buildkitd", "rootlesskit"):
        path = tmp_path / name
        path.write_text("binary", encoding="utf-8")
        bins.append(path)
    monkeypatch.setenv("INV_EVIDENCE_CODE_SHA", HEAD)
    monkeypatch.setattr(module, "_health_receipt", lambda *_args: {"redacted": True})
    monkeypatch.setattr(
        module,
        "_command",
        lambda *args: HEAD if args[-2:] == ("rev-parse", "HEAD") else TREE,
    )

    class _Transport:
        def measure(self):
            return SimpleNamespace(provider=SimpleNamespace(observation_digest="c" * 64))

        def reference_roundtrip(self, _request, _plan, _output):
            return {
                "schemaVersion": 1,
                "targetKind": "ci-reference",
                "verdict": "MEASURED_PASS",
                "operationalAcceptanceAssessed": False,
                "productDispatchEnabled": False,
                "limitations": ["reference-only-no-product-consumer"],
            }

    monkeypatch.setattr(
        module.RootlessBuildkitTransport,
        "configured",
        classmethod(lambda _cls, *_args, **_kwargs: _Transport()),
    )
    output, junit, health = tmp_path / "out", tmp_path / "junit.xml", tmp_path / "health.json"
    result = module.main(
        [
            "--buildctl",
            str(bins[0]),
            "--buildkitd",
            str(bins[1]),
            "--rootlesskit",
            str(bins[2]),
            "--address",
            "unix:///tmp/buildkit.sock",
            "--daemon-pid",
            "999",
            "--health-receipt",
            str(health),
            "--output-dir",
            str(output),
            "--junit",
            str(junit),
        ]
    )
    assert result == 0
    report = json.loads((output / "rootless-buildkit-reference.json").read_text(encoding="utf-8"))
    assert report["codeSha"] == HEAD
    assert report["checkoutTreeSha"] == TREE
    assert report["cleanCheckout"] is True
    assert report["operationalAcceptanceAssessed"] is False
    assert report["productDispatchEnabled"] is False
    assert (
        '<testsuite name="s08-rootless-buildkit-reference" tests="1" failures="0"'
        in junit.read_text(encoding="utf-8")
    )


@pytest.mark.parametrize("expected", [None, "9" * 40])
def test_main_fails_closed_when_exact_head_is_missing_or_different(monkeypatch, tmp_path, expected):
    module = _module()
    monkeypatch.delenv("INV_EVIDENCE_CODE_SHA", raising=False)
    if expected is not None:
        monkeypatch.setenv("INV_EVIDENCE_CODE_SHA", expected)
    monkeypatch.setattr(module, "_health_receipt", lambda *_args: {"redacted": True})
    monkeypatch.setattr(module, "_command", lambda *_args: HEAD)
    output, junit = tmp_path / "out", tmp_path / "junit.xml"
    result = module.main(
        [
            "--buildctl",
            str(tmp_path / "buildctl"),
            "--buildkitd",
            str(tmp_path / "buildkitd"),
            "--rootlesskit",
            str(tmp_path / "rootlesskit"),
            "--address",
            "unix:///tmp/buildkit.sock",
            "--daemon-pid",
            "999",
            "--health-receipt",
            str(tmp_path / "health.json"),
            "--output-dir",
            str(output),
            "--junit",
            str(junit),
        ]
    )
    assert result == 1
    report = json.loads((output / "rootless-buildkit-reference.json").read_text(encoding="utf-8"))
    assert report == {
        "schemaVersion": 1,
        "targetKind": "ci-reference",
        "verdict": "INVALID_RUN",
        "operationalAcceptanceAssessed": False,
        "productDispatchEnabled": False,
        "failureClass": "RuntimeError",
        "failureStage": "source-binding",
    }
