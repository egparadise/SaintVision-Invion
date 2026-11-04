param([Parameter(Mandatory)][string]$BindingsPath,[Parameter(Mandatory)][string]$BindingsSHA256,[Parameter(Mandatory)][string]$SelfSHA256,[Parameter(Mandatory)][string]$ReceiptRoot,[Parameter(Mandatory)][ValidatePattern('^[0-9]{8}T[0-9]{6}Z-[a-f0-9]{12}$')][string]$RunId,[ValidateSet('Attended','Scheduled')][string]$ExecutionMode='Attended',[switch]$RecoverObserverOnly)
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'R5ContextGuards.private.ps1')
Assert-SvRecordRoot $ReceiptRoot
if((Get-FileHash -LiteralPath $BindingsPath -Algorithm SHA256).Hash.ToLowerInvariant() -cne $BindingsSHA256){throw 'Binding differs'}
$svB=Get-Content -LiteralPath $BindingsPath -Encoding UTF8 -Raw | ConvertFrom-Json
if((Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant() -cne $SelfSHA256){throw 'Attended transition script differs from the pinned packet'}
$svActualContext=Get-SvActualContext $svB.context.sid
Assert-SvJobFreeContext -Context $svActualContext -ExpectedSession $svB.context.sessionId -Attended:($ExecutionMode -eq 'Attended')
$svB.attendedRunId=$RunId
$svB.attendedReceiptPath=Join-Path $ReceiptRoot ('transition-core-'+$RunId+'.json')
$svB.recoveryObserverStdout=Join-Path $ReceiptRoot ('observer-'+$RunId+'.private.stdout')
$svB.recoveryObserverStderr=Join-Path $ReceiptRoot ('observer-'+$RunId+'.private.stderr')
. (Join-Path $svB.pilotSource 'deploy/lan/SvLauncherInput.ps1')
$svPilot=Join-Path $svB.pilotSource 'tools/lan_pilot.py'
function Get-SvObserverGroup {
 $svAll=@(Get-CimInstance Win32_Process | Where-Object {$_.Name -eq 'python.exe' -and $_.CommandLine -and (Test-SvOwnedByState -CommandLine $_.CommandLine -ScriptPath $svPilot -StatePath $svB.statePath) -and @(Get-SvArgv $_.CommandLine)[-1] -eq 'observe'})
 foreach($svProcess in $svAll){
  $svOwner=Invoke-CimMethod -InputObject $svProcess -MethodName GetOwnerSid -ErrorAction Stop
  if($svOwner.ReturnValue -ne 0 -or $svOwner.Sid -cne $svB.context.sid){throw 'Exact observer process owner differs'}
 }
 $svIds=@($svAll | ForEach-Object {$_.ProcessId})
 $svRoots=@($svAll | Where-Object {$_.ParentProcessId -notin $svIds})
 if($svRoots.Count -gt 1){throw 'Multiple independent observer roots require disposition'}
 # A Windows virtualenv redirector and its child may both carry identical argv.
 return $svAll
}
function Stop-SvExactObserver {
 param($Expected)
 $svNow=Get-CimInstance Win32_Process -Filter ('ProcessId = '+$Expected.ProcessId) -ErrorAction Stop
 if($null -eq $svNow){return}
 if($svNow.CreationDate -ne $Expected.CreationDate -or $svNow.CommandLine -cne $Expected.CommandLine){throw 'Observer PID was reused or source changed'}
 $svOwner=Invoke-CimMethod -InputObject $svNow -MethodName GetOwnerSid -ErrorAction Stop
 if($svOwner.ReturnValue -ne 0 -or $svOwner.Sid -cne $svB.context.sid){throw 'Observer owner changed before stop'}
 Stop-Process -Id $Expected.ProcessId -ErrorAction Stop
}
function Start-SvObserverIfAbsent {
 $svGroup=@(Get-SvObserverGroup)
 if($svGroup.Count){return}
 $svArgs=@('-E','-B','-u',$svPilot,'--state',$svB.statePath,'observe')
 foreach($svArg in @($svB.python,$svPilot,$svB.statePath)){$null=Assert-SvNativeArgument -Value $svArg -What 'Bound observer argument'}
 $svProc=Start-Process -FilePath $svB.python -ArgumentList $svArgs -WorkingDirectory $svB.pilotSource -WindowStyle Hidden -PassThru -RedirectStandardOutput $svB.recoveryObserverStdout -RedirectStandardError $svB.recoveryObserverStderr
 Start-Sleep -Milliseconds 800
 if($svProc.HasExited -or @((Get-SvObserverGroup)).Count -eq 0){throw 'Exact observer fallback did not remain running'}
}
function Assert-SvRealObservation {
 $svRaw=& $svB.python -E -B $svPilot --state $svB.statePath observe --once
 $svExit=$LASTEXITCODE
 if($svExit -ne 0){throw 'Observation native exit failed'}
 $svV=($svRaw -join "`n") | ConvertFrom-Json
 $svExpected=@($svB.nodes | ForEach-Object {$_.nodeId} | Sort-Object)
 $svActual=@($svV.nodes | ForEach-Object {$_.nodeId} | Sort-Object)
 if($svActual.Count -ne 2 -or @(Compare-Object $svExpected $svActual).Count){throw 'Actual observation members differ'}
 foreach($svN in $svV.nodes){
  if($svN.observed -ne $true -or $svN.node.status -cne 'online'){throw 'Real mTLS observation unavailable'}
  $svAge=([DateTimeOffset]::UtcNow-[DateTimeOffset]::Parse($svN.snapshot.receivedAt)).TotalSeconds
  if($svAge -lt -1 -or $svAge -gt 20){throw 'Persisted snapshot is not fresh'}
 }
}
$svOldPythonPath=[Environment]::GetEnvironmentVariable('PYTHONPATH','Process')
$svOldPythonHome=[Environment]::GetEnvironmentVariable('PYTHONHOME','Process')
$svOldPath=$env:PATH
$svPrimary=$null
try {
 [Environment]::SetEnvironmentVariable('PYTHONPATH',$null,'Process')
 [Environment]::SetEnvironmentVariable('PYTHONHOME',$null,'Process')
 $env:PATH=(Split-Path -Parent $svB.context.node)+';'+(Split-Path -Parent $svB.context.git)+';'+$env:PATH
 $svStatus=& $svB.python -I -B $svB.followupGatePath --bindings $BindingsPath --bindings-sha256 $BindingsSHA256 --action currentStatus --run-id $svB.attendedRunId
 $svStatusExit=$LASTEXITCODE
 if($svStatusExit -ne 0){throw 'Exact source/state/tunnel guard failed before observer stop'}
 if($RecoverObserverOnly){Start-SvObserverIfAbsent;Assert-SvRealObservation;return}
 if(Test-Path -LiteralPath $svB.attendedReceiptPath){throw 'Attended result exists; preserve it'}
 $svGroup=@(Get-SvObserverGroup)
 # Stop only exact matched descendants, leaves first, then the matched root.
 $svIds=@($svGroup | ForEach-Object {$_.ProcessId})
 foreach($svChild in @($svGroup | Where-Object {$_.ParentProcessId -in $svIds})){Stop-SvExactObserver $svChild}
 foreach($svRoot in @($svGroup | Where-Object {$_.ParentProcessId -notin $svIds})){
  if(Get-Process -Id $svRoot.ProcessId -ErrorAction SilentlyContinue){Stop-SvExactObserver $svRoot}
 }
 try {
  $svH=$svB.nodes[0]
  $null=& (Join-Path $svB.pilotSource 'deploy/lan/Start-LiveConsole.ps1') -StatePath $svB.statePath -DatabaseTunnelTarget ($svH.user+'@'+$svH.ip) -SshKeyPath $svB.sshKeyPath
  if(@(Get-SvObserverGroup).Count -eq 0){throw 'Launcher left no exact observer'}
  Assert-SvRealObservation
 } catch {
  $svPrimary=$_.Exception.GetType().Name
  Start-SvObserverIfAbsent
  Assert-SvRealObservation
 }
 $svResult=@{schemaVersion='r5-attended-transition-receipt:1';attended=($ExecutionMode -eq 'Attended');executionMode=$ExecutionMode;actualContext=$svActualContext;sourceHead=$svB.pilotSourceHead;stateSHA256=$svB.stateSHA256;ownerMatched=$true;sessionId=(Get-Process -Id $PID).SessionId;primaryLauncherSucceeded=($null -eq $svPrimary);primaryErrorClass=$svPrimary;observerRecovered=($null -ne $svPrimary);exactObserverAndRealObservationAccepted=$true;unattendedRenewalAccepted=$false;observedAt=[DateTimeOffset]::UtcNow.ToString('o')}
 $svBytes=[Text.Encoding]::UTF8.GetBytes(($svResult | ConvertTo-Json -Depth 4))
 $svStream=[IO.File]::Open($svB.attendedReceiptPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
 try{$svStream.Write($svBytes,0,$svBytes.Length);$svStream.Flush($true)}finally{$svStream.Dispose()}
 if($svPrimary){throw 'Launcher failed; exact observer recovered; primary gate remains failed for attended review'}
} finally {
 $env:PATH=$svOldPath
 [Environment]::SetEnvironmentVariable('PYTHONPATH',$svOldPythonPath,'Process')
 [Environment]::SetEnvironmentVariable('PYTHONHOME',$svOldPythonHome,'Process')
}
