param([Parameter(Mandatory=$true)][ValidatePattern('^[a-fA-F0-9]{64}$')][string]$CertificateSHA256,
      [string]$StorageSource,
      [ValidatePattern('^[a-fA-F0-9]{64}$')][string]$StoragePolicySHA256)
$ErrorActionPreference = 'Stop'
$manifest = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'manifest.json') -Raw | ConvertFrom-Json
$svIsColocated = [string]$manifest.serverIP -eq [string]$manifest.nodeIP
if ($manifest.coLocatedWithControlPlane -ne $svIsColocated) {
    throw 'Control Plane co-location metadata differs from the configured addresses.'
}
if ($svIsColocated -and ($manifest.measurementEligible.s05 -ne $false `
        -or $manifest.measurementEligible.s07 -ne $false `
        -or $manifest.exclusionReason -ne 'cp-host-colocation')) {
    throw 'The co-located Node is not excluded from ADR-100 measurement denominators.'
}
$svStorageArgs = @()
if ($StorageSource -or $StoragePolicySHA256) {
    if (-not $StorageSource -or -not $StoragePolicySHA256) { throw 'Specify both StorageSource and StoragePolicySHA256.' }
    $svSource = Get-Item -LiteralPath $StorageSource
    if (-not $svSource.PSIsContainer -or $svSource.FullName -notmatch '^[A-Za-z]:\\' -or $svSource.Parent -eq $null) {
        throw 'Choose a specific folder on a local Windows drive.'
    }
    $svFolderPrefix = $svSource.FullName.TrimEnd('\') + '\'
    if ($PSScriptRoot.StartsWith($svFolderPrefix, [StringComparison]::OrdinalIgnoreCase) -or $PSScriptRoot -eq $svSource.FullName) {
        throw 'The contributed folder must not include the installation bundle.'
    }
    $svPolicy = Join-Path $PSScriptRoot 'storage-policy.json'
    if ((Get-FileHash -LiteralPath $svPolicy -Algorithm SHA256).Hash -ne $StoragePolicySHA256) { throw 'Storage policy hash differs.' }
    $svLinuxSource = '/mnt/' + $svSource.FullName.Substring(0,1).ToLower() + $svSource.FullName.Substring(2).Replace('\','/')
    $svStorageArgs = @($svLinuxSource, $StoragePolicySHA256.ToLowerInvariant())
}
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
    $existingRule = Get-NetFirewallRule -Name $ruleName
    $addresses = $existingRule | Get-NetFirewallAddressFilter
    $ports = $existingRule | Get-NetFirewallPortFilter
    if ($existingRule.Direction -ne 'Inbound' -or $existingRule.Action -ne 'Allow' -or $existingRule.Enabled -ne 'True' `
        -or (@($addresses.LocalAddress) -join ',') -ne $manifest.nodeIP `
        -or (@($addresses.RemoteAddress) -join ',') -ne $manifest.serverIP `
        -or (@($ports.LocalPort) -join ',') -ne [string]$manifest.nodePort `
        -or [string]$ports.Protocol -notin @('TCP','6')) {
        throw 'Existing firewall rule differs from this Node configuration; no rule was changed.'
    }
}
$workerLinuxPath = '/mnt/' + $PSScriptRoot.Substring(0,1).ToLower() + $PSScriptRoot.Substring(2).Replace('\','/')
& wsl.exe -d Ubuntu -- bash "$workerLinuxPath/finish-worker.sh" @svStorageArgs
if ($LASTEXITCODE -ne 0) { throw 'Node startup failed. Preserve its journal and inspect the output.' }
