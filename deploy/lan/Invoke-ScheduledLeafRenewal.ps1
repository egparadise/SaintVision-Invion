param(
    [Parameter(Mandatory = $true)][string]$ConfigPath,
    [Parameter(Mandatory = $true)][ValidatePattern('^[a-f0-9]{64}$')][string]$ExpectedConfigSha256,
    [Parameter(Mandatory = $true)][ValidatePattern('^[a-f0-9]{64}$')][string]$ExpectedRunnerSha256,
    [Parameter(Mandatory = $true)][ValidatePattern('^[a-f0-9]{64}$')][string]$ExpectedToolSha256,
    [string]$PythonPath = 'python'
)

$ErrorActionPreference = 'Stop'
$runner = [IO.Path]::GetFullPath($PSCommandPath)
$tool = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\tools\scheduled_leaf_renewal.py'))
$config = [IO.Path]::GetFullPath($ConfigPath)

function Assert-RegularPinnedFile([string]$Path, [string]$Digest, [string]$Label) {
    $item = Get-Item -LiteralPath $Path -Force -ErrorAction Stop
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or -not ($item -is [IO.FileInfo])) {
        throw "$Label is not a regular file"
    }
    $actual = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -cne $Digest) { throw "$Label digest differs" }
}

Assert-RegularPinnedFile $runner $ExpectedRunnerSha256 'Scheduled runner'
Assert-RegularPinnedFile $tool $ExpectedToolSha256 'Scheduled renewal tool'
Assert-RegularPinnedFile $config $ExpectedConfigSha256 'Scheduled renewal configuration'

& $PythonPath -I -B $tool --config $config --expected-config-sha256 $ExpectedConfigSha256
$renewalExit = $LASTEXITCODE
if ($renewalExit -ne 0) {
    # The Python tool writes a redacted append-only receipt before returning for
    # every expected outcome.  Do not print command output or private paths here.
    throw "Scheduled leaf renewal stopped (exit $renewalExit); inspect the redacted status file."
}
