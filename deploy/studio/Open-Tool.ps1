param(
    [Parameter(Mandatory=$true)][string]$Workspace,
    [Parameter(Mandatory=$true)][ValidateSet('orca','codex','claude','gemini','antigravity','folder','terminal')][string]$Tool
)
$ErrorActionPreference = 'Stop'
$Workspace = (Resolve-Path -LiteralPath $Workspace).Path
if (-not (Test-Path -LiteralPath $Workspace -PathType Container)) { throw 'Workspace unavailable.' }
if ($Tool -eq 'orca') {
    & orca repo add --path $Workspace --json | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Orca project registration failed.' }
    & orca file open README.md --worktree "path:$Workspace" --json | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Orca could not open this Workspace.' }
} elseif ($Tool -eq 'folder') {
    Start-Process -FilePath explorer.exe -ArgumentList ('"' + $Workspace + '"') | Out-Null
} else {
    $svCommands = @{codex='codex.cmd';claude='claude.exe';gemini='gemini.cmd';antigravity='agy.exe';terminal='powershell.exe'}
    Get-Command $svCommands[$Tool] -ErrorAction Stop | Out-Null
    $svShell = Join-Path $PSScriptRoot 'Agent-Shell.ps1'
    # Interactive windows are intentional: the user pressed Open Tool.
    Start-Process -FilePath powershell.exe -WorkingDirectory $Workspace -ArgumentList @(
        '-NoProfile','-NoExit','-ExecutionPolicy','Bypass','-File',('"'+$svShell+'"'),
        '-Workspace',('"'+$Workspace+'"'),'-Tool',$Tool
    ) | Out-Null
}
