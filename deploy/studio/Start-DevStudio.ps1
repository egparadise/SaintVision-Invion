param([string]$StudioRoot='C:/Project/SaintVision-Workspaces',[switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$svCheckout = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
$svCommon = & git -C $svCheckout rev-parse --git-common-dir
if ($LASTEXITCODE -ne 0) { throw 'Git workspace unavailable.' }
if (-not [IO.Path]::IsPathRooted($svCommon)) { $svCommon = Join-Path $svCheckout $svCommon }
$svRepository = Split-Path (Resolve-Path -LiteralPath $svCommon).Path -Parent
$svPython = Join-Path $svRepository '.venv/Scripts/python.exe'
$svScript = Join-Path $svCheckout 'tools/dev_studio.py'
if (-not (Test-Path -LiteralPath $svPython)) { throw 'Project Python environment unavailable.' }
& $svPython $svScript --root $StudioRoot init
if ($LASTEXITCODE -ne 0) { throw 'Studio initialization failed.' }
$svListening = Get-NetTCPConnection -LocalPort 18100 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($svListening) {
    $svProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $($svListening.OwningProcess)"
    if (-not $svProcess.CommandLine -or -not $svProcess.CommandLine.Replace('\','/').Contains($svScript.Replace('\','/'))) {
        throw 'Port 18100 belongs to another program. It has been preserved.'
    }
} else {
    $svState = Join-Path $StudioRoot '.studio'
    Start-Process -FilePath $svPython -WindowStyle Hidden -WorkingDirectory $svCheckout -ArgumentList @(
        '-u',('"'+$svScript+'"'),'--root',('"'+$StudioRoot+'"'),'serve'
    ) -RedirectStandardOutput "$svState/server.stdout.log" -RedirectStandardError "$svState/server.stderr.log" | Out-Null
}
$svReady = $false
for ($svTry=0; $svTry -lt 20; $svTry++) {
    try {
        $svHealth = Invoke-RestMethod -Uri 'http://127.0.0.1:18100/healthz' -TimeoutSec 2
        if ($svHealth.service -eq 'saintvision-developer-studio' -and $svHealth.root.Replace('\','/') -eq $StudioRoot.Replace('\','/')) { $svReady = $true; break }
    } catch { }
    Start-Sleep -Milliseconds 250
}
if (-not $svReady) { throw 'Studio did not become ready. Inspect .studio/server.stderr.log.' }
if (-not $NoBrowser) {
    $svLink = & $svPython $svScript --root $StudioRoot login-link
    if ($LASTEXITCODE -ne 0) { throw 'Local login failed.' }
    # The one-time token stays in this Windows user's browser fragment; never print it.
    Start-Process -FilePath $svLink | Out-Null
}
Write-Output 'SaintVision development Studio is ready on http://127.0.0.1:18100'
