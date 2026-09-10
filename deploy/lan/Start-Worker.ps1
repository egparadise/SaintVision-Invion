param([Parameter(Mandatory=$true)][ValidatePattern('^[a-fA-F0-9]{64}$')][string]$CertificateSHA256)
$ErrorActionPreference = 'Stop'
$manifest = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'manifest.json') -Raw | ConvertFrom-Json
$principal = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this script from an Administrator PowerShell to add the Node firewall rule.'
}
if (-not (Get-NetIPAddress -AddressFamily IPv4 | Where-Object IPAddress -EQ $manifest.nodeIP)) {
    throw 'This is not the configured worker PC.'
}
$certificate = Join-Path $PSScriptRoot 'node-cert.pem'
Invoke-WebRequest -UseBasicParsing -Uri "http://$($manifest.serverIP):18081/node-cert.pem" -OutFile $certificate -TimeoutSec 20
if ((Get-FileHash -LiteralPath $certificate -Algorithm SHA256).Hash -ne $CertificateSHA256) {
    throw 'Certificate hash differs from the server operator value.'
}
$ruleName = 'SaintVision-LAN-Node-' + $manifest.nodeId
if (-not (Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -Name $ruleName -DisplayName $ruleName -Direction Inbound -Action Allow -Protocol TCP `
        -LocalAddress $manifest.nodeIP -LocalPort $manifest.nodePort -RemoteAddress $manifest.serverIP -Profile Any | Out-Null
} else {
    throw 'Firewall rule already exists. Inspect it before retrying; no existing rule was changed.'
}
$workerLinuxPath = '/mnt/' + $PSScriptRoot.Substring(0,1).ToLower() + $PSScriptRoot.Substring(2).Replace('\','/')
& wsl.exe -d Ubuntu -- bash "$workerLinuxPath/finish-worker.sh"
if ($LASTEXITCODE -ne 0) { throw 'Node startup failed. Preserve its journal and inspect the output.' }
