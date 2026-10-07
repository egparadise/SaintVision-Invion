param(
    # Default to this checkout's own state directory: the launcher must not assume a drive letter.
    [string]$StatePath = (Join-Path $PSScriptRoot '../../.work/lan-pilot'),
    # Only needed to OPEN an external database tunnel. The port always comes from the
    # state's own dbPort; nothing about the tunnel is hardcoded here.
    [string]$DatabaseTunnelTarget = '',
    [string]$SshKeyPath = '',
    [switch]$OpenBrowser,
    # A console or web listener that serves a different pilot state is refused by default.
    # Replacing it stops our own process, so it stays an explicit operator decision.
    [switch]$ReplaceForeignStateListener
)
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

function Get-SvListener([int]$Port) {
    Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
}

# tools/lan_pilot.py defaults an older state without the field to the local Docker mode.
$svDatabaseMode = if ($svState.databaseMode) { [string]$svState.databaseMode } else { 'managed-local-docker' }
if ($svDatabaseMode -eq 'managed-local-docker') {
    $svDatabase = & docker.exe inspect $svState.container | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0 -or $svDatabase[0].Config.Labels.'ai.saintvision.pilot' -ne $svState.epoch) {
        throw 'Start Docker Desktop and check the existing pilot database. No database will be reset.'
    }
    if (-not $svDatabase[0].State.Running) {
        & docker.exe start $svState.container | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Docker start failed for the owned pilot database (exit $LASTEXITCODE). No listeners were started."
        }
    }
} elseif ($svDatabaseMode -eq 'ssh-tunnel-external') {
    # A hardened remote database has no local container. Requiring docker here is what used
    # to make this state fail; the loopback SSH tunnel is the thing to assure instead.
    $svTunnelPort = [int]$svState.dbPort
    if ($svTunnelPort -le 0 -or $svTunnelPort -gt 65535) { throw 'External pilot state does not declare a usable database port.' }
    if (-not (Get-SvListener $svTunnelPort)) {
        if (-not $DatabaseTunnelTarget) {
            throw "The external pilot database tunnel on 127.0.0.1:$svTunnelPort is not open. Re-run with -DatabaseTunnelTarget <user@host>. No database will be reset."
        }
        $svSsh = Join-Path $env:SystemRoot 'System32/OpenSSH/ssh.exe'
        if (-not (Test-Path -LiteralPath $svSsh)) { throw 'OpenSSH client is unavailable; cannot open the database tunnel.' }
        $svSshArguments = @(
            '-N','-L',"127.0.0.1:${svTunnelPort}:127.0.0.1:${svTunnelPort}",
            '-o','BatchMode=yes','-o','ExitOnForwardFailure=yes','-o','ServerAliveInterval=30'
        )
        if ($SshKeyPath) {
            $svKey = (Resolve-Path -LiteralPath $SshKeyPath).Path
            $svSshArguments += @('-i',$svKey)
        }
        $svSshArguments += $DatabaseTunnelTarget
        # No stream redirection: ssh diagnostics can name hosts and accounts.
        Start-Process -FilePath $svSsh -ArgumentList $svSshArguments -WindowStyle Hidden | Out-Null
        for ($svWait = 0; $svWait -lt 20 -and -not (Get-SvListener $svTunnelPort); $svWait++) { Start-Sleep -Milliseconds 500 }
        if (-not (Get-SvListener $svTunnelPort)) {
            throw "The database tunnel did not open within 10 seconds. Check that the database host is reachable. No listeners were started."
        }
    }
} else {
    throw "Unknown pilot database mode; refusing to start listeners."
}

function Start-SvListener([int]$Port,[string]$Expected,[string[]]$Required,[bool]$LoopbackOnly,[string]$Executable,[string[]]$Arguments,[string]$Directory,[string]$LogName) {
    $svListening = Get-SvListener $Port
    if ($svListening) {
        $svOwner = Get-CimInstance Win32_Process -Filter "ProcessId = $($svListening.OwningProcess)"
        $svCommand = if ($svOwner -and $svOwner.CommandLine) { $svOwner.CommandLine.Replace('\','/') } else { '' }
        if (-not $svCommand.Contains($Expected)) { throw "Port $Port is occupied by another service." }
        $svForeign = @($Required | Where-Object { -not $svCommand.Contains($_) })
        if ($LoopbackOnly -and $svListening.LocalAddress -notin @('127.0.0.1','::1')) {
            # Reusing a non-loopback listener would silently publish this console on the LAN.
            $svForeign += 'loopback-bind'
        }
        if ($svForeign.Count -eq 0) { return $svListening.OwningProcess }
        if (-not $ReplaceForeignStateListener) {
            throw "Port $Port already serves a different pilot state or a non-loopback bind. Re-run with -ReplaceForeignStateListener to replace this owned process, or stop it yourself. Nothing was changed."
        }
        Stop-Process -Id $svListening.OwningProcess -Force -Confirm:$false
        for ($svWait = 0; $svWait -lt 20 -and (Get-SvListener $Port); $svWait++) { Start-Sleep -Milliseconds 500 }
        if (Get-SvListener $Port) { throw "Port $Port did not become free after replacing the previous listener." }
    }
    $svProcess = Start-Process -FilePath $Executable -ArgumentList $Arguments -WorkingDirectory $Directory -WindowStyle Hidden -PassThru -RedirectStandardOutput "$StatePath/$LogName.stdout.log" -RedirectStandardError "$StatePath/$LogName.stderr.log"
    return $svProcess.Id
}

function Get-SvStateProcess([string]$Pattern) {
    Get-CimInstance Win32_Process | Where-Object {
        $_.Name -eq 'python.exe' -and $_.CommandLine -and $_.CommandLine.Replace('\','/').Contains($StatePath) -and $_.CommandLine -match $Pattern
    } | Select-Object -First 1
}

# The bootstrap download service is only started for a state that declares its port.
$svServeId = $null
if ($svState.downloadPort) {
    $svServe = Get-SvStateProcess 'lan_pilot\.py.*\bserve\s*$'
    if (-not $svServe) {
        $svServeProcess = Start-Process -FilePath $svPython -ArgumentList @('-u',"$svCheckout/tools/lan_pilot.py",'--state',$StatePath,'serve') -WorkingDirectory $svCheckout -WindowStyle Hidden -PassThru -RedirectStandardOutput "$StatePath/serve.stdout.log" -RedirectStandardError "$StatePath/serve.stderr.log"
        $svServeId = $svServeProcess.Id
    } else {
        $svServeId = $svServe.ProcessId
    }
}

$svObserver = Get-SvStateProcess 'lan_pilot\.py.*\bobserve\s*$'
if (-not $svObserver) {
    $svObserverProcess = Start-Process -FilePath $svPython -ArgumentList @('-u',"$svCheckout/tools/lan_pilot.py",'--state',$StatePath,'observe') -WorkingDirectory $svCheckout -WindowStyle Hidden -PassThru -RedirectStandardOutput "$StatePath/observer.stdout.log" -RedirectStandardError "$StatePath/observer.stderr.log"
    $svObserverId = $svObserverProcess.Id
} else {
    $svObserverId = $svObserver.ProcessId
}
# Both listeners must belong to THIS state: the console reads it, and the web page reads the console.
$svConsoleId = Start-SvListener 18082 "$svCheckout/tools/lan_console.py" @("$svCheckout/tools/lan_console.py",$StatePath) $true $svPython @('-u',"$svCheckout/tools/lan_console.py",'--state',$StatePath) $svCheckout 'console'
$svWebId = Start-SvListener 3000 $svVite @($svVite) $true (Get-Command node.exe).Source @($svVite,'--host','127.0.0.1','--port','3000','--strictPort') "$svCheckout/apps/web" 'web'
@{observerPid=$svObserverId;consolePid=$svConsoleId;webPid=$svWebId;servePid=$svServeId;databaseMode=$svDatabaseMode} | ConvertTo-Json | Set-Content -LiteralPath "$StatePath/live-console-processes.json"
if ($OpenBrowser) {
    $svReady = $false
    for ($svWait = 0; $svWait -lt 60 -and -not $svReady; $svWait++) {
        try {
            $svOverview = Invoke-RestMethod 'http://127.0.0.1:18082/pilot/v1/overview' -TimeoutSec 2
            $svPage = Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:3000' -TimeoutSec 2
            if ($svOverview.source -eq 'live-postgresql-mtls' -and $svPage.StatusCode -eq 200) { $svReady = $true }
        } catch {
            # Do not surface exception bodies: external tools can include secrets.
            Start-Sleep -Seconds 1
        }
    }
    if (-not $svReady) { throw 'The console or web page did not become ready within 60 seconds. Check the service logs in the state directory.' }
    Start-Process 'http://127.0.0.1:3000' | Out-Null
}
Write-Output 'SaintVision: http://127.0.0.1:3000'
Write-Output 'The page shows current connection status; no workload is started by this script.'
} finally {
    if ($svLocked) { $svMutex.ReleaseMutex() }
    $svMutex.Dispose()
}
