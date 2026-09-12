"""Execute the real Windows launcher with simulated WSL/network boundaries."""

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import pytest

pytestmark = pytest.mark.skipif(
    sys.platform != "win32", reason="Actual Windows PowerShell launcher"
)


@pytest.mark.parametrize(
    "fault",
    [
        "prepare",
        "apply",
        "policy",
        "node",
        "health",
        "request",
        "process",
        "same-id",
        "overlap",
        "address",
    ],
)
def test_windows_launcher_checks_inputs_arguments_and_result(tmp_path, fault):
    bundle = tmp_path / "bundle folder"
    source = tmp_path / "provided & folder"
    bundle.mkdir()
    source.mkdir()
    script = Path(__file__).resolve().parents[2] / "deploy/lan/Replace-Storage.ps1"
    shutil.copyfile(script, bundle / script.name)
    (bundle / "worker_storage_bridge.py").write_text("# boundary mocked in this test\n")
    manifest = dict(
        nodeId="nod_" + "0" * 26,
        tenantId="tenant-fixture",
        epoch="epoch-fixture",
        nodeIP="192.168.45.225",
    )
    (bundle / "manifest.json").write_text(json.dumps(manifest))
    (bundle / "storage-policy.json").write_bytes(b"policy-fixture")
    policy_hash = hashlib.sha256(b"policy-fixture").hexdigest()
    harness = tmp_path / "harness.ps1"
    harness.write_text(
        r"""
param($svScript,$svSource,$svHash,$svFault)
$ErrorActionPreference='Stop'
$global:svInvoked=$false
$global:svCaptured=@()
$global:svFault=$svFault
function Get-NetIPAddress { [pscustomobject]@{IPAddress=$(if ($global:svFault -eq 'address') {'192.168.45.224'} else {'192.168.45.225'})} }
function wsl.exe {
    $global:svInvoked=$true
    $global:svCaptured=@($args)
    $global:LASTEXITCODE=$(if ($global:svFault -eq 'process') {9} else {0})
    $svAnswer=@{nodeId=('nod_'+'0'*26);tenantId='tenant-fixture';recoveryEpoch='epoch-fixture';policySHA256=$svHash;
       requestSHA256=('a'*64);status='prepared';replacementAuthorized=$false;operationalAcceptanceAssessed=$false}
    if ($args[5] -eq 'apply') {
        $svAnswer.status='awaiting-server-mtls-verification';$svAnswer.containerId='b'*64
        $svAnswer.previousContainerId='c'*64;$svAnswer.restartPolicy='no'
    }
    if ($global:svFault -eq 'node') {$svAnswer.nodeId='wrong-node'}
    if ($global:svFault -eq 'health') {$svAnswer.operationalAcceptanceAssessed=$true}
    if ($global:svFault -eq 'request') {$svAnswer.requestSHA256='invalid'}
    if ($global:svFault -eq 'same-id') {$svAnswer.previousContainerId=$svAnswer.containerId}
    $svAnswer | ConvertTo-Json -Compress
}
$svOptions=@{StorageSource=$svSource;StoragePolicySHA256=$svHash}
if ($svFault -in @('apply','same-id')) {$svOptions.Apply=$true;$svOptions.RequestSHA256='a'*64}
if ($svFault -eq 'policy') {$svOptions.StoragePolicySHA256='0'*64}
try {
    $svResult=& $svScript @svOptions
    @{success=$true;invoked=$global:svInvoked;arguments=$global:svCaptured;status=$svResult.status} | ConvertTo-Json -Compress
} catch {
    @{success=$false;invoked=$global:svInvoked;arguments=$global:svCaptured} | ConvertTo-Json -Compress
}
""",
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(harness),
            str(bundle / script.name),
            str(tmp_path if fault == "overlap" else source),
            policy_hash,
            fault,
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    value = json.loads(result.stdout)
    assert value["success"] is (fault in ("prepare", "apply"))
    if fault in ("policy", "overlap", "address"):
        assert not value["invoked"]
    if fault in ("prepare", "apply"):
        args = value["arguments"]
        assert args[:4] == ["-d", "Ubuntu", "--", "python3"]
        assert args[7].endswith("/provided & folder")
        assert args[8] == policy_hash
        assert len(args) == (10 if fault == "apply" else 9)
