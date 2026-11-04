param([Parameter(Mandatory)][string]$PlanPath,[Parameter(Mandatory)][ValidatePattern('^[a-f0-9]{64}$')][string]$ExpectedPlanSHA256,[Parameter(Mandatory)][ValidateSet('ContextOnly','Cycle','Transition','ObserverRecovery','ScheduledTransition')][string]$Operation,[Parameter(Mandatory)][ValidatePattern('^[0-9]{8}T[0-9]{6}Z-[a-f0-9]{12}$')][string]$RunId,[switch]$PlanOnly)
$ErrorActionPreference='Stop'
if((Get-FileHash -LiteralPath $PlanPath -Algorithm SHA256).Hash.ToLowerInvariant() -cne $ExpectedPlanSHA256){throw 'Context plan differs'}
$svP=Get-Content -LiteralPath $PlanPath -Encoding UTF8 -Raw | ConvertFrom-Json
if($svP.schemaVersion -cne 'r5-reviewed-wmi-context:1' -or $Operation -notin $svP.allowedOperations){throw 'Context operation is outside plan'}
if((Get-FileHash -LiteralPath $svP.guardsPath -Algorithm SHA256).Hash.ToLowerInvariant() -cne $svP.guardsSHA256){throw 'Context guards differ'}
. $svP.guardsPath
Assert-SvPacketPins $svP
Assert-SvRecordRoot $svP.receiptRoot
if([Security.Principal.WindowsIdentity]::GetCurrent().User.Value -cne $svP.ownerSid){throw 'Context caller owner differs'}
$svStem=Join-Path $svP.receiptRoot ($Operation+'-'+$RunId)
$svIntent=$svStem+'.intent.json'
$svLaunch=$svStem+'.launch.json'
$svReceipt=$svStem+'.result.json'
$svUnknown=$svStem+'.completion-unknown.json'
if($PlanOnly){@{operation=$Operation;runId=$RunId;method='Win32_Process.Create';flags=16777216;desktop='Winsta0\Default';showWindow=0;oneShot=$true;executed=$false;certificateTaskCreated=$false}|ConvertTo-Json -Compress;return}
foreach($svFile in @($svIntent,$svLaunch,$svReceipt,$svUnknown)){if(Test-Path -LiteralPath $svFile){throw 'Exact one-shot record exists; preserve and do not replay'}}
Write-SvNewReceipt $svIntent @{schemaVersion='r5-wmi-launch-intent:1';planSHA256=$ExpectedPlanSHA256;operation=$Operation;runId=$RunId;observedAt=[DateTimeOffset]::UtcNow.ToString('o');callerPid=$PID}
$svArgv=@($svP.powershell,'-NoProfile','-NonInteractive','-WindowStyle','Hidden','-File',$svP.entryPath,'-PlanPath',[IO.Path]::GetFullPath($PlanPath),'-ExpectedPlanSHA256',$ExpectedPlanSHA256,'-Operation',$Operation,'-RunId',$RunId)
foreach($svArg in $svArgv){if($svArg -match '["\r\n]'){throw 'Unsafe native context argument'}}
$svLine=($svArgv | ForEach-Object {'"'+$_+'"'}) -join ' '
$svStartup=New-CimInstance -ClassName Win32_ProcessStartup -ClientOnly -Property @{CreateFlags=[uint32]16777216;ShowWindow=[uint16]0;WinstationDesktop='Winsta0\Default'}
$svCreate=Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine=$svLine;CurrentDirectory=$PSScriptRoot;ProcessStartupInformation=$svStartup} -ErrorAction Stop
Write-SvNewReceipt $svLaunch @{schemaVersion='r5-wmi-launch-result:1';observedAt=[DateTimeOffset]::UtcNow.ToString('o');operation=$Operation;runId=$RunId;returnValue=$svCreate.ReturnValue;helperPid=$svCreate.ProcessId;callerPid=$PID;planSHA256=$ExpectedPlanSHA256}
if($svCreate.ReturnValue -ne 0){throw 'WMI creation failed; preserve intent, no retry/fallback'}
$svLimit=if($Operation -eq 'Cycle'){[DateTimeOffset]::UtcNow.AddHours(4)}else{[DateTimeOffset]::UtcNow.AddMinutes(3)}
$svUnknownRecord=@{schemaVersion='r5-wmi-completion-unknown:1';operation=$Operation;runId=$RunId;planSHA256=$ExpectedPlanSHA256;exit=124;outcome='completion-unknown';reason='receipt-timeout';helperPid=$svCreate.ProcessId;intentPreserved=$true;automaticRetry=$false;childTerminationAttempted=$false;deadline=$svLimit.ToString('o')}
if(-not(Wait-SvContextReceipt -ReceiptPath $svReceipt -UnknownPath $svUnknown -Deadline $svLimit -UnknownRecord $svUnknownRecord)){throw 'Context receipt timeout; completion unknown record persisted; preserve intent, no retry'}
$svR=Get-Content -LiteralPath $svReceipt -Encoding UTF8 -Raw | ConvertFrom-Json
if($svR.planSHA256 -cne $ExpectedPlanSHA256 -or $svR.operation -cne $Operation -or $svR.runId -cne $RunId){throw 'Context receipt identity differs'}
if($svR.exit -ne 0){throw ('WMI child operation failed exit '+$svR.exit+'; preserve result/latch')}
$svR | ConvertTo-Json -Depth 12 -Compress
