param(
    [Parameter(Mandatory=$true)][string]$Workspace,
    [Parameter(Mandatory=$true)][ValidateSet('codex','claude','gemini','antigravity','terminal')][string]$Tool
)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Resolve-Path -LiteralPath $Workspace).Path
$svEnvironment = Join-Path $Workspace '.venv'
if (-not (Test-Path -LiteralPath "$svEnvironment/Scripts/python.exe")) {
    $svCommon = & git -C $Workspace rev-parse --git-common-dir 2>$null
    if ($LASTEXITCODE -eq 0) {
        if (-not [IO.Path]::IsPathRooted($svCommon)) { $svCommon = Join-Path $Workspace $svCommon }
        $svRepository = Split-Path (Resolve-Path -LiteralPath $svCommon).Path -Parent
        $svEnvironment = Join-Path $svRepository '.venv'
        $svGo = Join-Path $svRepository '.work/node-toolchain-1.27.1/go/bin'
        if (Test-Path -LiteralPath "$svGo/go.exe") { $env:PATH = "$svGo;$env:PATH" }
    }
}
if (Test-Path -LiteralPath "$svEnvironment/Scripts/python.exe") {
    $env:VIRTUAL_ENV = $svEnvironment
    $env:PATH = "$svEnvironment/Scripts;$env:PATH"
}
$Host.UI.RawUI.WindowTitle = "SaintVision - $Tool - $(Split-Path $Workspace -Leaf)"
Write-Host "Workspace: $Workspace"
Write-Host 'Use this workspace for this agent. Test and train from SaintVision Studio.'
switch ($Tool) {
    'codex' { & codex.cmd --sandbox workspace-write --approve-for-me }
    'claude' { & claude.exe --permission-mode auto }
    'gemini' { & gemini.cmd --approval-mode auto_edit }
    'antigravity' { & agy.exe --sandbox --mode accept-edits }
    'terminal' { Write-Host 'Development terminal ready. Your existing account and tool settings are preserved.' }
}
