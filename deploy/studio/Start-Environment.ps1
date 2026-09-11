param(
    [string]$StudioRoot = 'C:/Project/SaintVision-Workspaces',
    [string]$StatePath = 'C:/Project/SaintVision-Invion/.work/lan-pilot'
)
$ErrorActionPreference = 'Stop'
$svCheckout = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path.Replace('\','/')
$StatePath = (Resolve-Path -LiteralPath $StatePath).Path.Replace('\','/')
$svMutex = New-Object Threading.Mutex($false, ('Local\SaintVision.Environment.' + [Security.Principal.WindowsIdentity]::GetCurrent().User.Value))
$svLocked = $false
try {
    try { $svLocked = $svMutex.WaitOne(0) } catch [Threading.AbandonedMutexException] { $svLocked = $true }
    if (-not $svLocked) { Write-Output 'Environment startup is already in progress.'; return }
    $svLog = Join-Path $StatePath 'environment-startup.log'
    # Login can race Docker Desktop startup. Bounded retries start only these
    # services; they never dispatch work or reset a database/Node identity.
    for ($svAttempt = 1; $svAttempt -le 12; $svAttempt++) {
        try {
            & "$svCheckout/deploy/lan/Start-LiveConsole.ps1" -StatePath $StatePath | Out-Null
            & "$svCheckout/deploy/studio/Start-DevStudio.ps1" -StudioRoot $StudioRoot -NoBrowser | Out-Null
            $svOverview = Invoke-RestMethod 'http://127.0.0.1:18082/pilot/v1/overview' -TimeoutSec 3
            if ($svOverview.source -ne 'live-postgresql-mtls') { throw 'Console health differs.' }
            $svPage = Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:3000' -TimeoutSec 3
            if ($svPage.StatusCode -ne 200) { throw 'Web health differs.' }
            $svStatus = @{ at=[DateTimeOffset]::Now.ToString('o'); status='ready'; attempt=$svAttempt; checkout=$svCheckout; scope='services-only-no-work-dispatch' }
            $svStatus | ConvertTo-Json | Set-Content -LiteralPath "$StatePath/environment-startup.json" -Encoding UTF8
            Add-Content -LiteralPath $svLog -Value ($svStatus.at + ' ready')
            Write-Output 'SaintVision services ready: http://localhost:3000 and http://127.0.0.1:18100'
            return
        } catch {
            # Do not log exception bodies: external tools can include secrets.
            Add-Content -LiteralPath $svLog -Value ([DateTimeOffset]::Now.ToString('o') + " attempt=$svAttempt failed; check service logs")
            if ($svAttempt -lt 12) { Start-Sleep -Seconds 5 }
        }
    }
    @{ at=[DateTimeOffset]::Now.ToString('o'); status='not-ready'; attempts=12; checkout=$svCheckout } | ConvertTo-Json | Set-Content -LiteralPath "$StatePath/environment-startup.json" -Encoding UTF8
    throw 'Environment startup did not complete. Check Docker Desktop and service logs; data has been preserved.'
} finally {
    if ($svLocked) { $svMutex.ReleaseMutex() }
    $svMutex.Dispose()
}
