param([Parameter(Mandatory)][string]$PlanPath,[Parameter(Mandatory)][ValidatePattern('^[a-f0-9]{64}$')][string]$PlanSHA256)
$ErrorActionPreference='Stop'
if((Get-FileHash -LiteralPath $PlanPath -Algorithm SHA256).Hash.ToLowerInvariant() -cne $PlanSHA256){throw 'IdP local plan digest differs'}
$svP=Get-Content -LiteralPath $PlanPath -Encoding UTF8 -Raw | ConvertFrom-Json
if($svP.schemaVersion -cne 'r5-idp-local-repair-plan:1'){throw 'IdP local plan schema differs'}
if((Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant() -cne $svP.applyScriptSHA256){throw 'Apply script digest differs'}
if((Get-FileHash -LiteralPath $svP.existingTLS_CA_Path -Algorithm SHA256).Hash.ToLowerInvariant() -cne $svP.existingTLS_CA_SHA256){throw 'Existing service trust source changed'}
foreach($svParent in @((Split-Path -Parent $svP.targetDirectory),(Split-Path -Parent (Split-Path -Parent $svP.backupDirectory)))){
 $svItem=Get-Item -LiteralPath $svParent -Force
 if(-not($svItem -is [IO.DirectoryInfo]) -or ($svItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){throw 'Project-local target parent is unsafe'}
}
foreach($svTarget in @($svP.targetDirectory,$svP.backupDirectory)){
 if(Test-Path -LiteralPath $svTarget){throw 'New target/backup already exists; preserve it'}
}
foreach($svOld in $svP.backups){
 $svItem=Get-Item -LiteralPath $svOld.source -Force
 if(($svItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or -not($svItem -is [IO.FileInfo])){throw 'Original input is unsafe'}
 if((Get-FileHash -LiteralPath $svOld.source -Algorithm SHA256).Hash.ToLowerInvariant() -cne $svOld.sourceSHA256){throw 'Original config changed'}
}
foreach($svCandidate in @(@{path=$svP.candidateProfile;pin=$svP.candidateProfileSHA256},@{path=$svP.candidateBundle;pin=$svP.candidateBundleSHA256})){
 $svItem=Get-Item -LiteralPath $svCandidate.path -Force
 if(-not($svItem -is [IO.FileInfo]) -or ($svItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){throw 'Candidate is not a regular file'}
 if((Get-FileHash -LiteralPath $svCandidate.path -Algorithm SHA256).Hash.ToLowerInvariant() -cne $svCandidate.pin){throw 'Candidate digest differs'}
}
$svFresh=Get-Content -LiteralPath $svP.candidateBundle -Encoding UTF8 -Raw | ConvertFrom-Json
$svCurrentUnix=[DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
if($svFresh.issuer -cne $svP.issuer -or $svFresh.expiresAt -le $svCurrentUnix -or $svFresh.expiresAt -gt ($svCurrentUnix+604800)){throw 'Candidate public bundle is no longer fresh or scoped correctly'}
$svState=Get-Content -LiteralPath $svP.tenantSource -Encoding UTF8 -Raw | ConvertFrom-Json
$svProfile=Get-Content -LiteralPath $svP.candidateProfile -Encoding UTF8 -Raw | ConvertFrom-Json
if($svState.tenantId -cne $svProfile.identity.tenant_id){throw 'Actual r5 tenant binding changed'}
# All guarded before writes; only new project-local directories/files are created.
New-Item -ItemType Directory -Path $svP.backupDirectory -ErrorAction Stop | Out-Null
foreach($svOld in $svP.backups){
 $svBackup=Join-Path $svP.backupDirectory $svOld.backupName
 Copy-Item -LiteralPath $svOld.source -Destination $svBackup -ErrorAction Stop
 if((Get-FileHash -LiteralPath $svBackup -Algorithm SHA256).Hash.ToLowerInvariant() -cne $svOld.sourceSHA256){throw 'Preserved backup digest differs'}
}
New-Item -ItemType Directory -Path $svP.targetDirectory -ErrorAction Stop | Out-Null
[IO.File]::Copy($svP.candidateBundle,$svP.targetBundle,$false)
[IO.File]::Copy($svP.candidateProfile,$svP.targetProfile,$false)
foreach($svNew in @(@{path=$svP.targetProfile;pin=$svP.candidateProfileSHA256},@{path=$svP.targetBundle;pin=$svP.candidateBundleSHA256})){
 if((Get-FileHash -LiteralPath $svNew.path -Algorithm SHA256).Hash.ToLowerInvariant() -cne $svNew.pin){throw 'New local config readback differs'}
}
Write-Output 'Created only the reviewed isolated r5 identity profile and public bundle; no service was started or switched'
