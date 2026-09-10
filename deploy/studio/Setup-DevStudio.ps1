param([string]$StudioRoot='C:/Project/SaintVision-Workspaces',[switch]$RebuildImage)
$ErrorActionPreference = 'Stop'
$svCheckout = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
$svCommon = & git -C $svCheckout rev-parse --git-common-dir
if ($LASTEXITCODE -ne 0) { throw 'Git workspace unavailable.' }
if (-not [IO.Path]::IsPathRooted($svCommon)) { $svCommon = Join-Path $svCheckout $svCommon }
$svRepository = Split-Path (Resolve-Path -LiteralPath $svCommon).Path -Parent
$svPython = Join-Path $svRepository '.venv/Scripts/python.exe'
$svScript = Join-Path $svCheckout 'tools/dev_studio.py'
function Invoke-Studio([string[]]$Arguments) {
    $svOutput = & $svPython $svScript --root $StudioRoot @Arguments
    if ($LASTEXITCODE -ne 0) { throw 'Studio setup step failed; existing files preserved.' }
    return $svOutput
}
Invoke-Studio @('init') | Out-Null
$svStatus = (Invoke-Studio @('status')) | ConvertFrom-Json
if (-not $svStatus.imageConfigured -or $RebuildImage) {
    Invoke-Studio @('build-image') | Out-Null
}
foreach ($svTemplate in @(@{name='ai-starter';kind='ai'},@{name='python-starter';kind='python'})) {
    if (-not ($svStatus.projects | Where-Object { $_.name -eq $svTemplate.name })) {
        Invoke-Studio @('create',$svTemplate.name,'--kind',$svTemplate.kind) | Out-Null
    }
}
Invoke-Studio @('register','SaintVision-Invion',$svCheckout) | Out-Null
$svStart = Join-Path $PSScriptRoot 'Start-DevStudio.ps1'
$svDesktop = [Environment]::GetFolderPath('Desktop')
$svShortcutPath = Join-Path $svDesktop 'SaintVision 개발 시작.lnk'
$svShell = New-Object -ComObject WScript.Shell
if (Test-Path -LiteralPath $svShortcutPath) {
    $svExisting = $svShell.CreateShortcut($svShortcutPath)
    if (-not $svExisting.Arguments.Contains('Start-DevStudio.ps1')) { throw 'An unrelated desktop shortcut has the same name; preserved.' }
}
$svShortcut = $svShell.CreateShortcut($svShortcutPath)
$svShortcut.TargetPath = (Get-Command powershell.exe).Source
$svShortcut.Arguments = '-NoProfile -ExecutionPolicy Bypass -File "'+$svStart+'" -StudioRoot "'+$StudioRoot+'"'
$svShortcut.WorkingDirectory = $svCheckout
$svShortcut.WindowStyle = 7
$svShortcut.Description = '프로젝트 · AI 도구 · 제한된 CPU 실행 · 학습 결과'
$svShortcut.Save()
& $svStart -StudioRoot $StudioRoot -NoBrowser
Write-Output 'Ready: open the desktop shortcut SaintVision 개발 시작.'
