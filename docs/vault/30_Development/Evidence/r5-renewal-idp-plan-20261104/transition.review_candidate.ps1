param(
 [Parameter(Mandatory)][string]$BindingsPath,
 [Parameter(Mandatory)][ValidatePattern('^[a-f0-9]{64}$')][string]$BindingsSHA256
)
$ErrorActionPreference='Stop'
if((Get-FileHash -LiteralPath $BindingsPath -Algorithm SHA256).Hash.ToLowerInvariant() -cne $BindingsSHA256){throw 'Binding digest differs'}
$svB=Get-Content -LiteralPath $BindingsPath -Encoding UTF8 -Raw | ConvertFrom-Json
if([Security.Principal.WindowsIdentity]::GetCurrent().User.Value -cne $svB.context.sid){throw 'Execution owner differs'}
. (Join-Path $svB.pilotSource 'deploy/lan/SvLauncherInput.ps1')
$svPilot=Join-Path $svB.pilotSource 'tools/lan_pilot.py'
$svLauncher=Join-Path $svB.pilotSource 'deploy/lan/Start-LiveConsole.ps1'
# Fail before stopping anything if the pinned actual launcher dependencies differ.
$env:PATH=(Split-Path -Parent $svB.context.node)+';'+(Split-Path -Parent $svB.context.git)+';'+$env:PATH
if(-not(Test-SvSamePath (Get-Command node.exe).Source $svB.context.node)){throw 'Node runtime differs'}
if(-not(Test-SvSamePath (Get-Command git.exe).Source $svB.context.git)){throw 'Git runtime differs'}
foreach($svDep in @($svB.python,$svLauncher,(Join-Path $svB.pilotSource 'apps/web/node_modules/vite/bin/vite.js'))){
 if(-not(Test-Path -LiteralPath $svDep -PathType Leaf)){throw 'Actual launcher dependency missing'}
}
$svObservers=@(Get-CimInstance Win32_Process | Where-Object {
 $_.Name -eq 'python.exe' -and $_.CommandLine -and
 (Test-SvOwnedByState -CommandLine $_.CommandLine -ScriptPath $svPilot -StatePath $svB.statePath) -and
 @(Get-SvArgv $_.CommandLine)[-1] -eq 'observe'
})
if($svObservers.Count -gt 1){throw 'Multiple owned observers require exact disposition'}
foreach($svObserver in $svObservers){Stop-Process -Id $svObserver.ProcessId -ErrorAction Stop}
$svHost=$svB.nodes[0]
$svTarget=$svHost.user+'@'+$svHost.ip
# Reuses only exact owned tunnel/console/web; does not replace a foreign listener.
# Source launches helpers with WindowStyle Hidden; OpenBrowser is intentionally absent.
$null=& $svLauncher -StatePath $svB.statePath -DatabaseTunnelTarget $svTarget -SshKeyPath $svB.sshKeyPath
@{transitioned=$true;ownedObserverReloaded=$true;sessionId=(Get-Process -Id $PID).SessionId;workloadChanged=$false} | ConvertTo-Json -Compress
