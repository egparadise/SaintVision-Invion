function Assert-SvScopedDirectoryAncestry {
 param([Parameter(Mandatory)][string]$TrustedRoot,[Parameter(Mandatory)][string]$ScopeRoot,[Parameter(Mandatory)][string]$Directory,[switch]$AllowMissing)
 $svRoot=[IO.Path]::GetFullPath($TrustedRoot).TrimEnd('\','/')
 $svScope=[IO.Path]::GetFullPath($ScopeRoot).TrimEnd('\','/')
 $svDirectory=[IO.Path]::GetFullPath($Directory).TrimEnd('\','/')
 $svComparison=[StringComparison]::OrdinalIgnoreCase
 $svSep=[IO.Path]::DirectorySeparatorChar
 if(-not $svScope.StartsWith($svRoot+$svSep,$svComparison)){throw 'Scope escapes trusted workspace'}
 if($svDirectory -cne $svScope -and -not $svDirectory.StartsWith($svScope+$svSep,$svComparison)){throw 'Target escapes approved local scope'}
 $svRootItem=Get-Item -LiteralPath $svRoot -Force -ErrorAction Stop
 if(-not($svRootItem -is [IO.DirectoryInfo]) -or ($svRootItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){throw 'Trusted workspace is not an ordinary directory'}
 $svRelative=$svDirectory.Substring($svRoot.Length).TrimStart('\','/')
 $svCursor=$svRoot
 $svMissing=$false
 foreach($svPart in ($svRelative -split '[\\/]')){
  if(-not $svPart -or $svPart -in @('.','..')){throw 'Unsafe directory component'}
  $svCursor=Join-Path $svCursor $svPart
  if($svMissing){continue}
  $svItem=Get-Item -LiteralPath $svCursor -Force -ErrorAction SilentlyContinue
  if($null -eq $svItem){
   if(-not $AllowMissing){throw 'Required scoped parent is missing'}
   $svMissing=$true
   continue
  }
  if(-not($svItem -is [IO.DirectoryInfo]) -or ($svItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){throw 'Scoped ancestor is not an ordinary directory'}
 }
}

function Ensure-SvImmediateBackupsParent {
 param([Parameter(Mandatory)][string]$TrustedRoot,[Parameter(Mandatory)][string]$ScopeRoot,[Parameter(Mandatory)][string]$BackupDirectory)
 $svParent=Split-Path -Parent ([IO.Path]::GetFullPath($BackupDirectory))
 # Only the one approved immediate "backups" parent may be created.
 if(-not [string]::Equals($svParent,[IO.Path]::Combine([IO.Path]::GetFullPath($ScopeRoot),'backups'),[StringComparison]::OrdinalIgnoreCase)){throw 'Unexpected immediate backups parent'}
 Assert-SvScopedDirectoryAncestry -TrustedRoot $TrustedRoot -ScopeRoot $ScopeRoot -Directory $ScopeRoot
 Assert-SvScopedDirectoryAncestry -TrustedRoot $TrustedRoot -ScopeRoot $ScopeRoot -Directory $svParent -AllowMissing
 if(-not(Test-Path -LiteralPath $svParent)){
  New-Item -ItemType Directory -Path $svParent -ErrorAction Stop | Out-Null
 }
 Assert-SvScopedDirectoryAncestry -TrustedRoot $TrustedRoot -ScopeRoot $ScopeRoot -Directory $svParent
 if(Test-Path -LiteralPath $BackupDirectory){throw 'Backup target exists; preserve it'}
}

function Assert-SvNewIdentityTargets {
 param([Parameter(Mandatory)][string]$TrustedRoot,[Parameter(Mandatory)][string]$ScopeRoot,[Parameter(Mandatory)][string]$TargetDirectory,[Parameter(Mandatory)][string]$BackupDirectory)
 Assert-SvScopedDirectoryAncestry -TrustedRoot $TrustedRoot -ScopeRoot $ScopeRoot -Directory (Split-Path -Parent $TargetDirectory)
 Assert-SvScopedDirectoryAncestry -TrustedRoot $TrustedRoot -ScopeRoot $ScopeRoot -Directory (Split-Path -Parent $BackupDirectory) -AllowMissing
 foreach($svTarget in @($TargetDirectory,$BackupDirectory)){
  if(Test-Path -LiteralPath $svTarget){throw 'New identity/backup target exists; preserve it'}
 }
}
