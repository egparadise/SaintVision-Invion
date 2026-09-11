param([string]$StatePath = 'C:/Project/SaintVision-Invion/.work/lan-pilot')
$ErrorActionPreference = 'Stop'
$svMutex = New-Object Threading.Mutex($false, ('Local\SaintVision.LiveConsole.' + [Security.Principal.WindowsIdentity]::GetCurrent().User.Value))
$svLocked = $false
try {
try { $svLocked = $svMutex.WaitOne(30000) } catch [Threading.AbandonedMutexException] { $svLocked = $true }
if (-not $svLocked) { throw 'Another console startup is still in progress.' }
$svCheckout = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path.Replace('\','/')
$StatePath = (Resolve-Path -LiteralPath $StatePath).Path.Replace('\','/')
$svCommon = & git -C $svCheckout rev-parse --git-common-dir
if ($LASTEXITCODE -ne 0) { throw 'Git workspace unavailable.' }
if (-not [IO.Path]::IsPathRooted($svCommon)) { $svCommon = Join-Path $svCheckout $svCommon }
$svRepository = Split-Path (Resolve-Path -LiteralPath $svCommon).Path -Parent
$svPython = Join-Path $svRepository '.venv/Scripts/python.exe'
$svVite = "$svCheckout/apps/web/node_modules/vite/bin/vite.js"
if (-not (Test-Path -LiteralPath $svPython) -or -not (Test-Path -LiteralPath $svVite)) {
    throw 'Install this checkout Python and web dependencies first.'
}
$svState = Get-Content -LiteralPath "$StatePath/private-state.json" -Raw | ConvertFrom-Json
$svDatabase = & docker.exe inspect $svState.container | ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or $svDatabase[0].Config.Labels.'ai.saintvision.pilot' -ne $svState.epoch) {
    throw 'Start Docker Desktop and check the existing pilot database. No database will be reset.'
}
if (-not $svDatabase[0].State.Running) { & docker.exe start $svState.container | Out-Null }

function Start-SvListener([int]$Port,[string]$Expected,[string]$Executable,[string[]]$Arguments,[string]$Directory,[string]$LogName) {
    $svListening = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($svListening) {
        $svOwner = Get-CimInstance Win32_Process -Filter "ProcessId = $($svListening.OwningProcess)"
        if (-not $svOwner.CommandLine.Replace('\','/').Contains($Expected)) { throw "Port $Port is occupied by another service." }
        return $svListening.OwningProcess
    }
    $svProcess = Start-Process -FilePath $Executable -ArgumentList $Arguments -WorkingDirectory $Directory -WindowStyle Hidden -PassThru -RedirectStandardOutput "$StatePath/$LogName.stdout.log" -RedirectStandardError "$StatePath/$LogName.stderr.log"
    return $svProcess.Id
}
$svObserver = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -eq 'python.exe' -and $_.CommandLine -and $_.CommandLine.Replace('\','/').Contains($StatePath) -and $_.CommandLine -match 'lan_pilot.py.*\bobserve\s*$'
} | Select-Object -First 1
if (-not $svObserver) {
    $svObserver = Start-Process -FilePath $svPython -ArgumentList @('-u',"$svCheckout/tools/lan_pilot.py",'--state',$StatePath,'observe') -WorkingDirectory $svCheckout -WindowStyle Hidden -PassThru -RedirectStandardOutput "$StatePath/observer.stdout.log" -RedirectStandardError "$StatePath/observer.stderr.log"
    $svObserverId = $svObserver.Id
} else {
    $svObserverId = $svObserver.ProcessId
}
$svConsoleId = Start-SvListener 18082 "$svCheckout/tools/lan_console.py" $svPython @('-u',"$svCheckout/tools/lan_console.py",'--state',$StatePath) $svCheckout 'console'
$svWebId = Start-SvListener 3000 $svVite (Get-Command node.exe).Source @($svVite,'--host','0.0.0.0','--port','3000','--strictPort') "$svCheckout/apps/web" 'web'
@{observerPid=$svObserverId;consolePid=$svConsoleId;webPid=$svWebId} | ConvertTo-Json | Set-Content -LiteralPath "$StatePath/live-console-processes.json"
Write-Output 'SaintVision: http://localhost:3000'
Write-Output 'The page shows current connection status; no workload is started by this script.'
} finally {
    if ($svLocked) { $svMutex.ReleaseMutex() }
    $svMutex.Dispose()
}
