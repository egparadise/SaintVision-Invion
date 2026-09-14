param(
    [Parameter(Mandatory=$true)][string]$StorageSource,
    [Parameter(Mandatory=$true)][ValidatePattern('^[a-fA-F0-9]{64}$')][string]$StoragePolicySHA256,
    [switch]$Apply,
    [ValidatePattern('^[a-fA-F0-9]{64}$')][string]$RequestSHA256
)
$ErrorActionPreference = 'Stop'
if ([bool]$Apply -ne [bool]$RequestSHA256) { throw 'Apply requires the hash returned by preparation.' }
function Convert-SvDirectory([string]$Path) {
    $svItem = Get-Item -LiteralPath $Path -Force
    if (-not $svItem.PSIsContainer -or $svItem.FullName -notmatch '^[A-Za-z]:\\' -or $null -eq $svItem.Parent) {
        throw 'Choose a specific directory on a local Windows drive.'
    }
    $svAncestor = $svItem
    while ($null -ne $svAncestor) {
        if ($svAncestor.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Directory links and junctions are not accepted.' }
        $svAncestor = $svAncestor.Parent
    }
    if ($svItem.FullName.IndexOfAny([char[]]",`n`r") -ge 0) { throw 'Unsupported directory name.' }
    return $svItem.FullName
}
$svSource = Convert-SvDirectory $StorageSource
$svBundle = Convert-SvDirectory $PSScriptRoot
$svPrefix = $svSource.TrimEnd('\') + '\'
if ($svBundle -eq $svSource -or $svBundle.StartsWith($svPrefix, [StringComparison]::OrdinalIgnoreCase) -or
    $svSource.StartsWith($svBundle.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'The source and installation bundle must be separate directories.'
}
foreach ($svFile in @('manifest.json','storage-policy.json','worker_storage_bridge.py')) {
    $svInfo = Get-Item -LiteralPath (Join-Path $svBundle $svFile) -Force
    if ($svInfo.PSIsContainer -or ($svInfo.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Unsafe bundle file.' }
}
$svManifest = Get-Content -LiteralPath (Join-Path $svBundle 'manifest.json') -Raw | ConvertFrom-Json
if (-not (Get-NetIPAddress -AddressFamily IPv4 | Where-Object IPAddress -EQ $svManifest.nodeIP)) { throw 'This is not the assigned Node PC.' }
$svPolicyHash = $StoragePolicySHA256.ToLowerInvariant()
if ((Get-FileHash -LiteralPath (Join-Path $svBundle 'storage-policy.json') -Algorithm SHA256).Hash -ne $svPolicyHash) {
    throw 'Storage policy hash differs.'
}
$svLinuxBundle = '/mnt/' + $svBundle.Substring(0,1).ToLowerInvariant() + $svBundle.Substring(2).Replace('\','/')
$svLinuxSource = '/mnt/' + $svSource.Substring(0,1).ToLowerInvariant() + $svSource.Substring(2).Replace('\','/')
$svMode = 'prepare'
if ($Apply) { $svMode = 'apply' }
$svArguments = @('-d','Ubuntu','--','python3',"$svLinuxBundle/worker_storage_bridge.py",$svMode,$svLinuxBundle,$svLinuxSource,$svPolicyHash)
if ($Apply) { $svArguments += $RequestSHA256.ToLowerInvariant() }
$svOutput = & wsl.exe @svArguments
if ($LASTEXITCODE -ne 0) { throw 'WSL storage operation failed. Preserve the request and Node journal.' }
$svResult = ($svOutput -join "`n") | ConvertFrom-Json
if ($svResult.nodeId -cne $svManifest.nodeId -or $svResult.tenantId -cne $svManifest.tenantId -or
    $svResult.recoveryEpoch -cne $svManifest.epoch -or $svResult.policySHA256 -cne $svPolicyHash -or
    $svResult.requestSHA256 -cnotmatch '^[a-f0-9]{64}$' -or $svResult.operationalAcceptanceAssessed -isnot [bool] -or
    $svResult.operationalAcceptanceAssessed) { throw 'WSL result differs from the requested Node or policy.' }
if ($Apply) {
    if ($svResult.status -cne 'awaiting-server-mtls-verification' -or $svResult.restartPolicy -cne 'no' -or
        $svResult.requestSHA256 -cne $RequestSHA256.ToLowerInvariant() -or
        $svResult.containerId -cnotmatch '^[a-f0-9]{64}$' -or $svResult.previousContainerId -cnotmatch '^[a-f0-9]{64}$' -or
        $svResult.containerId -ceq $svResult.previousContainerId) { throw 'Replacement result is incomplete or mismatched.' }
} elseif ($svResult.status -cne 'prepared' -or $svResult.replacementAuthorized -isnot [bool] -or $svResult.replacementAuthorized) {
    throw 'Preparation did not return an unapproved request.'
}
$svResult | Select-Object nodeId,tenantId,recoveryEpoch,policySHA256,requestSHA256,status,operationalAcceptanceAssessed,replacementAuthorized,containerId,previousContainerId,restartPolicy
