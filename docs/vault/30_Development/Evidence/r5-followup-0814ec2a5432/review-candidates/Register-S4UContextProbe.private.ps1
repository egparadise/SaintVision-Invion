param([Parameter(Mandatory)][string]$PlanPath,[Parameter(Mandatory)][ValidatePattern('^[a-f0-9]{64}$')][string]$ExpectedPlanSHA256,[switch]$PlanOnly)
$ErrorActionPreference='Stop'
if((Get-FileHash -LiteralPath $PlanPath -Algorithm SHA256).Hash.ToLowerInvariant() -cne $ExpectedPlanSHA256){throw 'Probe plan hash differs'}
$svP=Get-Content -LiteralPath $PlanPath -Encoding UTF8 -Raw | ConvertFrom-Json
if($svP.schemaVersion -cne 'r5-s4u-readonly-probe:1' -or $svP.maximumExecutions -ne 1){throw 'Probe plan scope differs'}
if([Security.Principal.WindowsIdentity]::GetCurrent().User.Value -cne $svP.ownerSid){throw 'Probe owner differs'}
foreach($svPin in $svP.inputFiles){
 $svItem=Get-Item -LiteralPath $svPin.path -Force -ErrorAction Stop
 if(-not($svItem -is [IO.FileInfo]) -or ($svItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){throw 'Probe input is not regular'}
 if((Get-FileHash -LiteralPath $svPin.path -Algorithm SHA256).Hash.ToLowerInvariant() -cne $svPin.sha256){throw 'Probe input changed'}
}
$svArgs=@('-I','-B',$svP.runnerPath,'--plan',[IO.Path]::GetFullPath($PlanPath),'--expected-sha256',$ExpectedPlanSHA256)
$svQuoted=$svArgs | ForEach-Object {if($_ -match '[\s"]'){'"'+($_ -replace '([\\]*)"','$1$1\"')+'"'}else{$_}}
if($PlanOnly){
 @{taskName=$svP.taskName;executable=$svP.python;arguments=$svArgs;owner=$svP.ownerMarker;logonType='S4U';runLevel='Limited';triggerCount=0;demandStartOnce=$true;executionTimeLimitMinutes=10;multipleInstances='IgnoreNew';actions=@('currentStatus','runtimePreflight-1','runtimePreflight-2');registered=$false} | ConvertTo-Json -Depth 5
 return
}
if(Get-ScheduledTask -TaskName $svP.taskName -ErrorAction SilentlyContinue){throw 'Probe task already exists; preserve it'}
if((Test-Path -LiteralPath $svP.receiptPath) -or (Test-Path -LiteralPath ([IO.Path]::ChangeExtension($svP.receiptPath,'.intent.json')))){throw 'Probe sample already exists; preserve it'}
$svAction=New-ScheduledTaskAction -Execute $svP.python -Argument ($svQuoted -join ' ')
$svPrincipal=New-ScheduledTaskPrincipal -UserId $svP.ownerSid -LogonType S4U -RunLevel Limited
$svSettings=New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
# No timer, recurring trigger or automatic start: root must explicitly demand-start once.
Register-ScheduledTask -TaskName $svP.taskName -Description $svP.ownerMarker -Action $svAction -Principal $svPrincipal -Settings $svSettings | Out-Null
Write-Output $svP.taskName
