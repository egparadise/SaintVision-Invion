param([string]$StudioRoot='C:/Project/SaintVision-Workspaces',[string]$StatePath='C:/Project/SaintVision-Invion/.work/lan-pilot')
$ErrorActionPreference = 'Stop'
$svScript = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot 'Start-Environment.ps1')).Path
$StudioRoot = (Resolve-Path -LiteralPath $StudioRoot).Path
$StatePath = (Resolve-Path -LiteralPath $StatePath).Path
foreach ($svPath in @($svScript,$StudioRoot,$StatePath)) {
    if ($svPath.Contains('"') -or $svPath.Contains("`r") -or $svPath.Contains("`n")) { throw 'Unsupported path.' }
}
$svStartup = [Environment]::GetFolderPath('Startup')
$svLink = Join-Path $svStartup 'SaintVision Environment.lnk'
$svShell = New-Object -ComObject WScript.Shell
$svShortcut = $svShell.CreateShortcut($svLink)
$svMarker = 'SaintVision owned service startup v1; no workload dispatch'
if ((Test-Path -LiteralPath $svLink) -and $svShortcut.Description -ne $svMarker) { throw 'Startup shortcut belongs to another setup; preserved.' }
$svShortcut.TargetPath = (Get-Command powershell.exe).Source
$svShortcut.Arguments = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + $svScript + '" -StudioRoot "' + $StudioRoot + '" -StatePath "' + $StatePath + '"'
$svShortcut.WorkingDirectory = Split-Path $svScript -Parent
$svShortcut.WindowStyle = 7
$svShortcut.Description = $svMarker
$svShortcut.Save()
Write-Output ('Registered current-user login startup: ' + $svLink)
