param(
    [Parameter(Mandatory = $true)][string]$ConfigPath,
    [Parameter(Mandatory = $true)][string]$PythonPath,
    [switch]$PlanOnly
)

$ErrorActionPreference = 'Stop'
$runner = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'Invoke-ScheduledLeafRenewal.ps1'))
$tool = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\tools\scheduled_leaf_renewal.py'))
$config = [IO.Path]::GetFullPath($ConfigPath)

foreach ($path in @($runner, $tool, $config, [IO.Path]::GetFullPath($PythonPath))) {
    $item = Get-Item -LiteralPath $path -Force -ErrorAction Stop
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or -not ($item -is [IO.FileInfo])) {
        throw 'Task input is not a regular file'
    }
}

$raw = [IO.File]::ReadAllBytes($config)
if ($raw.Length -eq 0 -or $raw.Length -gt 1048576 -or
    ($raw.Length -ge 3 -and $raw[0] -eq 0xef -and $raw[1] -eq 0xbb -and $raw[2] -eq 0xbf)) {
    throw 'Task configuration bytes are invalid'
}
$document = [Text.Encoding]::UTF8.GetString($raw) | ConvertFrom-Json
if ($document.schemaVersion -cne 'saintvision-scheduled-leaf-renewal:1' -or
    $document.sourceHeadSha -notmatch '^[a-f0-9]{40}$') {
    throw 'Task configuration contract differs'
}

$configHash = (Get-FileHash -LiteralPath $config -Algorithm SHA256).Hash.ToLowerInvariant()
$runnerHash = (Get-FileHash -LiteralPath $runner -Algorithm SHA256).Hash.ToLowerInvariant()
$toolHash = (Get-FileHash -LiteralPath $tool -Algorithm SHA256).Hash.ToLowerInvariant()
$stateHashBytes = [Security.Cryptography.SHA256]::Create().ComputeHash(
    [Text.Encoding]::UTF8.GetBytes(([IO.Path]::GetFullPath([string]$document.statePath)).ToLowerInvariant())
)
$stateHash = -join ($stateHashBytes | ForEach-Object { $_.ToString('x2') })
$taskName = "SaintVision-Leaf-Renewal-$($stateHash.Substring(0, 16))"
$isWindows = $env:OS -eq 'Windows_NT'
if (-not $isWindows -and -not $PlanOnly) { throw 'Task Scheduler registration requires Windows' }
$sid = if ($isWindows) {
    [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
} else {
    'NONWINDOWS-PLAN-ONLY'
}
$owner = "SaintVision leaf renewal owner=$sid;config=$configHash;runner=$runnerHash;tool=$toolHash"
$powerShell = (Get-Process -Id $PID).Path
$arguments = @(
    '-NoLogo', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
    '-File', $runner,
    '-ConfigPath', $config,
    '-ExpectedConfigSha256', $configHash,
    '-ExpectedRunnerSha256', $runnerHash,
    '-ExpectedToolSha256', $toolHash,
    '-PythonPath', [IO.Path]::GetFullPath($PythonPath)
)

if ($PlanOnly) {
    [ordered]@{
        schemaVersion = 'saintvision-leaf-renewal-task-plan:1'
        taskName = $taskName
        owner = $owner
        executable = $powerShell
        arguments = $arguments
        triggers = @('00:15', '12:15')
        multipleInstances = 'IgnoreNew'
        logonType = 'S4U'
        nonInteractive = $true
        elevated = $false
    } | ConvertTo-Json -Depth 5
    exit 0
}

if ($document.notificationsEnabled -cne $true) {
    throw 'Live task registration requires explicit Windows notifications'
}
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($null -ne $existing) {
    $ownerPrefix = "SaintVision leaf renewal owner=$sid;"
    if (-not $existing.Description.StartsWith($ownerPrefix, [StringComparison]::Ordinal) -or
        $existing.Actions.Count -ne 1 -or
        $existing.Actions[0].Execute -cne $powerShell) {
        throw 'Existing scheduled task is not owned by this exact registration'
    }
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

$quoted = $arguments | ForEach-Object {
    if ($_ -match '[\s"]') { '"' + ($_ -replace '([\\]*)"', '$1$1\"') + '"' } else { $_ }
}
$action = New-ScheduledTaskAction -Execute $powerShell -Argument ($quoted -join ' ')
$triggers = @(
    (New-ScheduledTaskTrigger -Daily -At '00:15')
    (New-ScheduledTaskTrigger -Daily -At '12:15')
)
$desktop = [IO.Path]::GetFullPath([Environment]::GetFolderPath('Desktop'))
$statusParent = [IO.Path]::GetFullPath((Split-Path -Parent ([string]$document.statusPath)))
if ($statusParent -cne $desktop) { throw 'Scheduled status file must be placed on the current user Desktop' }
$principal = New-ScheduledTaskPrincipal -UserId $sid -LogonType S4U -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1)
Register-ScheduledTask -TaskName $taskName -Description $owner -Action $action `
    -Trigger $triggers -Principal $principal -Settings $settings | Out-Null
Write-Output $taskName
