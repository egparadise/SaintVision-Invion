param(
    # Default to this checkout's own state directory: no drive letter is assumed.
    [string]$StatePath = (Join-Path $PSScriptRoot '../../.work/lan-pilot'),
    # Passed through to Start-LiveConsole.ps1. The tunnel PORT is read from the state;
    # only the target host and key are operator inputs, and neither is stored in Git.
    # Both are held to the same grammar the launcher uses (SvLauncherInput.ps1).
    [string]$DatabaseTunnelTarget = '',
    [string]$SshKeyPath = '',
    [string]$ShortcutName = 'SaintVision Invion',
    [switch]$Remove
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'SvLauncherInput.ps1')
$svScript = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot 'Start-LiveConsole.ps1')).Path
$StatePath = (Resolve-Path -LiteralPath $StatePath).Path
if ($ShortcutName.Contains('\') -or $ShortcutName.Contains('/') -or $ShortcutName.Contains('"')) {
    throw 'Unsupported shortcut name.'
}
# Exactly the launcher's grammar, so a target the launcher would refuse can never be
# baked into a shortcut that runs unattended.
if ($DatabaseTunnelTarget) { $DatabaseTunnelTarget = Assert-SvTunnelTarget $DatabaseTunnelTarget }
if ($SshKeyPath) { $SshKeyPath = Assert-SvKeyPath $SshKeyPath }
foreach ($svPath in @($svScript, $StatePath)) {
    if ($svPath.Contains('"') -or $svPath.Contains("`r") -or $svPath.Contains("`n")) { throw 'Unsupported path.' }
}
$svDesktop = [Environment]::GetFolderPath('Desktop')
$svLink = Join-Path $svDesktop ($ShortcutName + '.lnk')
$svMarker = Get-SvShortcutMarker
# Same ownership rule as Register-EnvironmentStartup.ps1: a link this setup did not create is
# preserved rather than overwritten. The rule lives in SvLauncherInput.ps1 so a regression
# test can drive it directly.
$null = Assert-SvOwnedShortcut -LinkPath $svLink
$svShell = New-Object -ComObject WScript.Shell
$svShortcut = $svShell.CreateShortcut($svLink)
if ($Remove) {
    if (Test-Path -LiteralPath $svLink) {
        Remove-Item -LiteralPath $svLink
        Write-Output ('Removed the owned desktop launcher: ' + $svLink)
    } else {
        Write-Output 'No owned desktop launcher to remove.'
    }
    return
}
$svArguments = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + $svScript + '" -StatePath "' + $StatePath + '" -OpenBrowser'
if ($DatabaseTunnelTarget) { $svArguments += ' -DatabaseTunnelTarget "' + $DatabaseTunnelTarget + '"' }
if ($SshKeyPath) { $svArguments += ' -SshKeyPath "' + $SshKeyPath + '"' }
$svShortcut.TargetPath = (Get-Command powershell.exe).Source
$svShortcut.Arguments = $svArguments
$svShortcut.WorkingDirectory = Split-Path $svScript -Parent
$svShortcut.WindowStyle = 7
$svShortcut.Description = $svMarker
$svShortcut.Save()
Write-Output ('Registered the owned desktop launcher: ' + $svLink)
Write-Output 'It starts only already-provisioned services and dispatches no workload.'
