param(
    # Default to this checkout's own state directory: the launcher must not assume a drive letter.
    [string]$StatePath = (Join-Path $PSScriptRoot '../../.work/lan-pilot'),
    # Only needed to OPEN an external database tunnel. The port always comes from the
    # state's own dbPort; nothing about the tunnel is hardcoded here. The target is held to
    # an exact user@host grammar by SvLauncherInput.ps1.
    [string]$DatabaseTunnelTarget = '',
    [string]$SshKeyPath = '',
    [switch]$OpenBrowser,
    # A console or web listener that serves a different pilot state is refused by default.
    # Replacing it stops a process, so it stays an explicit operator decision.
    [switch]$ReplaceForeignStateListener
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'SvLauncherInput.ps1')
$svMutex = New-Object Threading.Mutex($false, ('Local\SaintVision.LiveConsole.' + [Security.Principal.WindowsIdentity]::GetCurrent().User.Value))
$svLocked = $false
try {
try { $svLocked = $svMutex.WaitOne(30000) } catch [Threading.AbandonedMutexException] { $svLocked = $true }
if (-not $svLocked) { throw 'Another console startup is still in progress.' }
$svCheckout = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path.Replace('\','/')
$StatePath = (Resolve-Path -LiteralPath $StatePath).Path.Replace('\','/')
# Validate operator inputs before anything is started or inspected.
if ($DatabaseTunnelTarget) { $DatabaseTunnelTarget = Assert-SvTunnelTarget $DatabaseTunnelTarget }
if ($SshKeyPath) { $SshKeyPath = Assert-SvKeyPath $SshKeyPath }
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
$svLoopback = @('127.0.0.1', '::1')

function Get-SvListeners([int]$Port) {
    # Every listener on the port, not the first: a second non-loopback bind must be visible.
    # Emit the objects and let every CALL SITE wrap with @(). Returning ", $array" instead
    # makes the empty case arrive as one element holding an empty array, whose LocalAddress
    # is null and therefore reads as a non-loopback bind -- the opposite failure.
    Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
}

function Get-SvOwnerCommandLine([int]$ProcessId) {
    $svOwner = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction SilentlyContinue
    if ($svOwner -and $svOwner.CommandLine) { return $svOwner.CommandLine }
    return ''
}

# tools/lan_pilot.py only substitutes the local default when the key is genuinely absent
# (setdefault); a present-but-wrong value is refused there. Match that exactly: a null,
# empty or unknown mode must fail closed before any Docker call or listener.
$svModeDeclared = @($svState.PSObject.Properties | Where-Object { $_.Name -eq 'databaseMode' }).Count -gt 0
if (-not $svModeDeclared) {
    $svDatabaseMode = 'managed-local-docker'
} else {
    $svDatabaseMode = $svState.databaseMode
    if ($svDatabaseMode -isnot [string] -or $svDatabaseMode -notin @('managed-local-docker', 'ssh-tunnel-external')) {
        throw 'Database mode differs from the pilot contract; refusing to start listeners. No database will be reset.'
    }
}

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
    # to make this state fail; the loopback SSH forward is the thing to assure instead.
    if (@($svState.PSObject.Properties | Where-Object { $_.Name -eq 'dbPort' }).Count -eq 0) {
        throw 'External pilot state does not declare a database port.'
    }
    $svTunnelPort = 0
    if (-not [int]::TryParse([string]$svState.dbPort, [ref]$svTunnelPort) -or $svTunnelPort -le 0 -or $svTunnelPort -gt 65535) {
        throw 'External pilot state does not declare a usable database port.'
    }
    $svForward = "127.0.0.1:${svTunnelPort}:127.0.0.1:${svTunnelPort}"
    $svExisting = @(Get-SvListeners $svTunnelPort)
    if ($svExisting.Count -gt 0) {
        # Any listener is not a tunnel. Every bind must be loopback, and the owner must be an
        # ssh client carrying this exact forward and target; otherwise fail closed.
        foreach ($svListener in $svExisting) {
            if ($svListener.LocalAddress -notin $svLoopback) {
                throw "Port $svTunnelPort is bound on a non-loopback address; refusing to treat it as the database tunnel. No listeners were started."
            }
        }
        $svOwned = $false
        foreach ($svListener in $svExisting) {
            $svArgv = Get-SvArgv (Get-SvOwnerCommandLine $svListener.OwningProcess)
            if ($svArgv.Count -eq 0) { continue }
            if (-not (Test-SvSamePath $svArgv[0] (Join-Path $env:SystemRoot 'System32/OpenSSH/ssh.exe'))) { continue }
            $svSeenForward = $false
            foreach ($svToken in $svArgv) {
                if ([string]::Equals($svToken, $svForward, [StringComparison]::Ordinal)) { $svSeenForward = $true }
            }
            if (-not $svSeenForward) { continue }
            if ($DatabaseTunnelTarget) {
                $svSeenTarget = $false
                foreach ($svToken in $svArgv) {
                    if ([string]::Equals($svToken, $DatabaseTunnelTarget, [StringComparison]::Ordinal)) { $svSeenTarget = $true }
                }
                if (-not $svSeenTarget) { continue }
            }
            $svOwned = $true
            break
        }
        if (-not $svOwned) {
            throw "Port $svTunnelPort is held by a process this launcher cannot identify as the owned database tunnel. No listeners were started."
        }
    } else {
        if (-not $DatabaseTunnelTarget) {
            throw "The external pilot database tunnel on 127.0.0.1:$svTunnelPort is not open. Re-run with -DatabaseTunnelTarget <user@host>. No database will be reset."
        }
        $svSsh = Join-Path $env:SystemRoot 'System32/OpenSSH/ssh.exe'
        if (-not (Test-Path -LiteralPath $svSsh)) { throw 'OpenSSH client is unavailable; cannot open the database tunnel.' }
        # Every option is fixed here and '--' closes option parsing, so the validated target
        # can only ever be read as the destination.
        $svSshArguments = @(
            '-N','-L',$svForward,
            '-o','BatchMode=yes','-o','ExitOnForwardFailure=yes','-o','ServerAliveInterval=30',
            '-o','StrictHostKeyChecking=accept-new'
        )
        if ($SshKeyPath) { $svSshArguments += @('-o','IdentitiesOnly=yes','-i',$SshKeyPath) }
        $svSshArguments += @('--',$DatabaseTunnelTarget)
        # No stream redirection: ssh diagnostics can name hosts and accounts.
        Start-Process -FilePath $svSsh -ArgumentList $svSshArguments -WindowStyle Hidden | Out-Null
        for ($svWait = 0; $svWait -lt 20; $svWait++) {
            if (@(Get-SvListeners $svTunnelPort).Count -gt 0) { break }
            Start-Sleep -Milliseconds 500
        }
        $svOpened = @(Get-SvListeners $svTunnelPort)
        if ($svOpened.Count -eq 0) {
            throw "The database tunnel did not open within 10 seconds. Check that the database host is reachable. No listeners were started."
        }
        foreach ($svListener in $svOpened) {
            if ($svListener.LocalAddress -notin $svLoopback) {
                throw "The database tunnel opened on a non-loopback address; refusing to continue. No listeners were started."
            }
        }
    }
} else {
    throw 'Unknown pilot database mode; refusing to start listeners.'
}

function Start-SvListener([int]$Port,[string]$ScriptPath,[bool]$RequireState,[string]$Executable,[string[]]$Arguments,[string]$Directory,[string]$LogName) {
    $svListeners = @(Get-SvListeners $Port)
    if ($svListeners.Count -gt 0) {
        $svForeign = @()
        foreach ($svListener in $svListeners) {
            if ($svListener.LocalAddress -notin $svLoopback) {
                # Reusing a non-loopback listener would silently publish this console on the LAN.
                $svForeign += 'non-loopback-bind'
                continue
            }
            $svCommandLine = Get-SvOwnerCommandLine $svListener.OwningProcess
            $svArgv = Get-SvArgv $svCommandLine
            $svScriptSeen = $false
            foreach ($svToken in $svArgv) {
                if (Test-SvSamePath $svToken $ScriptPath) { $svScriptSeen = $true; break }
            }
            if (-not $svScriptSeen) { throw "Port $Port is occupied by another service." }
            if ($RequireState -and -not (Test-SvOwnedByState -CommandLine $svCommandLine -ScriptPath $ScriptPath -StatePath $StatePath)) {
                $svForeign += 'other-state'
            }
        }
        if ($svForeign.Count -eq 0) { return $svListeners[0].OwningProcess }
        if (-not $ReplaceForeignStateListener) {
            throw "Port $Port already serves a different pilot state or a non-loopback bind. Re-run with -ReplaceForeignStateListener to replace this owned process, or stop it yourself. Nothing was changed."
        }
        foreach ($svListener in $svListeners) {
            Stop-Process -Id $svListener.OwningProcess -Force -Confirm:$false
        }
        for ($svWait = 0; $svWait -lt 20 -and @(Get-SvListeners $Port).Count -gt 0; $svWait++) { Start-Sleep -Milliseconds 500 }
        if (@(Get-SvListeners $Port).Count -gt 0) { throw "Port $Port did not become free after replacing the previous listener." }
    }
    $svProcess = Start-Process -FilePath $Executable -ArgumentList $Arguments -WorkingDirectory $Directory -WindowStyle Hidden -PassThru -RedirectStandardOutput "$StatePath/$LogName.stdout.log" -RedirectStandardError "$StatePath/$LogName.stderr.log"
    return $svProcess.Id
}

function Get-SvStateProcess([string]$ScriptPath,[string]$Verb) {
    # Exact state token, not a substring: 'C:/pilot/r2' must not match 'C:/pilot/r2-x'.
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.Name -eq 'python.exe' -and $_.CommandLine -and
        (Test-SvOwnedByState -CommandLine $_.CommandLine -ScriptPath $ScriptPath -StatePath $StatePath) -and
        @(Get-SvArgv $_.CommandLine)[-1] -eq $Verb
    } | Select-Object -First 1
}

$svPilotScript = "$svCheckout/tools/lan_pilot.py"
$svConsoleScript = "$svCheckout/tools/lan_console.py"

# The bootstrap download service is only started for a state that declares its port.
$svServeId = $null
if (@($svState.PSObject.Properties | Where-Object { $_.Name -eq 'downloadPort' }).Count -gt 0 -and $svState.downloadPort) {
    $svServe = Get-SvStateProcess $svPilotScript 'serve'
    if (-not $svServe) {
        $svServeProcess = Start-Process -FilePath $svPython -ArgumentList @('-u',$svPilotScript,'--state',$StatePath,'serve') -WorkingDirectory $svCheckout -WindowStyle Hidden -PassThru -RedirectStandardOutput "$StatePath/serve.stdout.log" -RedirectStandardError "$StatePath/serve.stderr.log"
        $svServeId = $svServeProcess.Id
    } else {
        $svServeId = $svServe.ProcessId
    }
}

$svObserver = Get-SvStateProcess $svPilotScript 'observe'
if (-not $svObserver) {
    $svObserverProcess = Start-Process -FilePath $svPython -ArgumentList @('-u',$svPilotScript,'--state',$StatePath,'observe') -WorkingDirectory $svCheckout -WindowStyle Hidden -PassThru -RedirectStandardOutput "$StatePath/observer.stdout.log" -RedirectStandardError "$StatePath/observer.stderr.log"
    $svObserverId = $svObserverProcess.Id
} else {
    $svObserverId = $svObserver.ProcessId
}
# Both listeners must belong to THIS state: the console reads it, and the web page reads the console.
$svConsoleId = Start-SvListener 18082 $svConsoleScript $true $svPython @('-u',$svConsoleScript,'--state',$StatePath) $svCheckout 'console'
$svWebId = Start-SvListener 3000 $svVite $false (Get-Command node.exe).Source @($svVite,'--host','127.0.0.1','--port','3000','--strictPort') "$svCheckout/apps/web" 'web'
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
