$ErrorActionPreference = 'Stop'
$manifest = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'manifest.json') -Raw | ConvertFrom-Json
if (-not (Get-NetIPAddress -AddressFamily IPv4 | Where-Object IPAddress -EQ $manifest.nodeIP)) {
    throw 'This is not the assigned worker PC.'
}
$workerLinuxPath = '/mnt/' + $PSScriptRoot.Substring(0,1).ToLower() + $PSScriptRoot.Substring(2).Replace('\','/')
& wsl.exe -d Ubuntu -- python3 "$workerLinuxPath/worker_execution.py"
if ($LASTEXITCODE -ne 0) { throw 'Execution test setup failed; preserve the Node key and volume.' }
