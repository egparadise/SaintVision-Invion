param([Parameter(Mandatory)][string]$PlanPath,[Parameter(Mandatory)][string]$ExpectedPlanSHA256,[Parameter(Mandatory)][ValidateSet('ContextOnly','Cycle','Transition','ObserverRecovery','ScheduledTransition')][string]$Operation,[Parameter(Mandatory)][ValidatePattern('^[0-9]{8}T[0-9]{6}Z-[a-f0-9]{12}$')][string]$RunId)
$ErrorActionPreference='Stop'
if((Get-FileHash -LiteralPath $PlanPath -Algorithm SHA256).Hash.ToLowerInvariant() -cne $ExpectedPlanSHA256){throw 'Entry plan differs'}
$svP=Get-Content -LiteralPath $PlanPath -Encoding UTF8 -Raw | ConvertFrom-Json
if($svP.schemaVersion -cne 'r5-reviewed-wmi-context:1' -or $Operation -notin $svP.allowedOperations){throw 'Entry operation differs'}
if((Get-FileHash -LiteralPath $svP.guardsPath -Algorithm SHA256).Hash.ToLowerInvariant() -cne $svP.guardsSHA256){throw 'Entry guards differ'}
. $svP.guardsPath
Assert-SvPacketPins $svP
Assert-SvRecordRoot $svP.receiptRoot
$svStem=Join-Path $svP.receiptRoot ($Operation+'-'+$RunId)
$svResult=@{schemaVersion='r5-wmi-context-result:1';operation=$Operation;runId=$RunId;planSHA256=$ExpectedPlanSHA256;observedAt=[DateTimeOffset]::UtcNow.ToString('o');context=$null;exit=1;cycleExecuted=$false;transitionExecuted=$false;unattendedRenewalAccepted=$false;certificateTaskCreated=$false}
$svOldPythonHome=[Environment]::GetEnvironmentVariable('PYTHONHOME','Process')
$svOldPythonPath=[Environment]::GetEnvironmentVariable('PYTHONPATH','Process')
$svOldPath=$env:PATH
try {
 $svContext=Get-SvActualContext $svP.ownerSid
 $svResult.context=$svContext
 Assert-SvJobFreeContext -Context $svContext -ExpectedSession $svP.expectedSession -Attended:($Operation -ne 'ScheduledTransition')
 [Environment]::SetEnvironmentVariable('PYTHONHOME',$null,'Process')
 [Environment]::SetEnvironmentVariable('PYTHONPATH',$null,'Process')
 $env:PATH=(Split-Path -Parent $svP.node)+';'+(Split-Path -Parent $svP.git)+';'+$env:PATH
 if($Operation -eq 'ContextOnly'){$svResult.exit=0}
 elseif($Operation -eq 'Cycle'){
  Assert-SvPinnedScheduler $svP
  $svRaw=& $svP.python -I -B $svP.schedulerPath --config $svP.manualConfigPath --expected-config-sha256 $svP.manualConfigSHA256 --window-only 2>($svStem+'.window.stderr')
  $svWindowExit=$LASTEXITCODE
  if($svWindowExit -ne 0){throw 'Cycle public-window preflight failed'}
  $svWindow=($svRaw -join "`n") | ConvertFrom-Json
  $svResult.window=$svWindow
  if($svWindow.expired -or -not $svWindow.inWindow){$svResult.exit=4;$svResult.refusal='Normal-clock valid-leaf renewal window is not open'}
  else {
   Assert-SvPinnedScheduler $svP
   $null=& $svP.python -I -B $svP.schedulerPath --config $svP.manualConfigPath --expected-config-sha256 $svP.manualConfigSHA256 2>($svStem+'.scheduler.stderr')
   $svNative=$LASTEXITCODE
   $svResult.cycleExecuted=$true
   $svResult.schedulerExit=$svNative
   if($svNative -ne 0){throw 'Canonical cycle failed; preserve durable latch and receipts'}
   $svStatus=Get-Content -LiteralPath $svP.manualStatusPath -Encoding UTF8 -Raw | ConvertFrom-Json
   if($svStatus.outcome -cne 'renewed'){throw 'Canonical cycle did not record renewed outcome'}
   $svResult.canonicalOutcome=$svStatus.outcome
   $svResult.canonicalRunId=$svStatus.runId
   $svResult.exit=0
  }
 } else {
  $svMode=if($Operation -eq 'ScheduledTransition'){'Scheduled'}else{'Attended'}
  $null=& $svP.transitionCorePath -BindingsPath $svP.bindingsPath -BindingsSHA256 $svP.bindingsSHA256 -SelfSHA256 $svP.transitionCoreSHA256 -ReceiptRoot $svP.receiptRoot -RunId $RunId -ExecutionMode $svMode -RecoverObserverOnly:($Operation -eq 'ObserverRecovery')
  if($Operation -eq 'ObserverRecovery'){$svResult.observerRecoveryExecuted=$true}else{$svResult.transitionExecuted=$true}
  $svResult.exit=0
 }
} catch {$svResult.errorClass=$_.Exception.GetType().Name}
finally {
 $env:PATH=$svOldPath
 [Environment]::SetEnvironmentVariable('PYTHONHOME',$svOldPythonHome,'Process')
 [Environment]::SetEnvironmentVariable('PYTHONPATH',$svOldPythonPath,'Process')
 Write-SvNewReceipt ($svStem+'.result.json') $svResult
}
exit $svResult.exit
