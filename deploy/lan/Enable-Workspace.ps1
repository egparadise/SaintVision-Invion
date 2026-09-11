param([switch]$Rollback)
$ErrorActionPreference = 'Stop'
$svManifest = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'manifest.json') -Raw | ConvertFrom-Json
if (-not (Get-NetIPAddress -AddressFamily IPv4 | Where-Object IPAddress -EQ $svManifest.nodeIP)) {
    throw 'This installation belongs to a different worker PC.'
}
if ($PSScriptRoot -notmatch '^[A-Za-z]:\\') { throw 'Extract the bundle to a local Windows drive.' }
$svLinuxPath = '/mnt/' + $PSScriptRoot.Substring(0,1).ToLower() + $PSScriptRoot.Substring(2).Replace('\','/')
$svArgs = @('-d','Ubuntu','--','python3',"$svLinuxPath/worker_workspace.py")
if ($Rollback) { $svArgs += '--rollback' }
& wsl.exe @svArgs
if ($LASTEXITCODE -ne 0) { throw 'Workspace Node upgrade failed. Preserve its key, volume and journal.' }
