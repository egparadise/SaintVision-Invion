$ErrorActionPreference = 'Stop'
$manifest = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'manifest.json') -Raw | ConvertFrom-Json
if (-not (Get-NetIPAddress -AddressFamily IPv4 | Where-Object IPAddress -EQ $manifest.nodeIP)) {
    throw 'This is not the configured worker PC.'
}
$workerLinuxPath = '/mnt/' + $PSScriptRoot.Substring(0,1).ToLower() + $PSScriptRoot.Substring(2).Replace('\','/')
& wsl.exe -d Ubuntu -- bash "$workerLinuxPath/repair-node.sh"
if ($LASTEXITCODE -ne 0) { throw 'Node file repair failed. Keep the existing key and journal.' }
