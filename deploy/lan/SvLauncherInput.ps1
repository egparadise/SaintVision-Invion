# Shared input grammar and command-line parsing for the LAN launcher scripts.
#
# Dot-sourced by Start-LiveConsole.ps1 and Register-DesktopShortcut.ps1 so both enforce the
# same rules. Native argument lists are flattened by the Windows runtime, so a target that
# merely avoids quotes and newlines can still carry option syntax and whitespace and arrive
# at ssh.exe as several arguments. These functions reject anything outside an exact grammar
# instead of filtering characters.

function Test-SvHostName {
    param([Parameter(Mandatory)][AllowEmptyString()][string]$Value)
    if ($Value.Length -lt 1 -or $Value.Length -gt 253) { return $false }
    if ($Value -match '^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$') {
        foreach ($octet in @($Matches[1], $Matches[2], $Matches[3], $Matches[4])) {
            if ($octet.Length -gt 1 -and $octet.StartsWith('0')) { return $false }
            if ([int]$octet -gt 255) { return $false }
        }
        return $true
    }
    foreach ($label in $Value.Split('.')) {
        if ($label -notmatch '^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?$') { return $false }
    }
    return $true
}

function Test-SvTunnelTarget {
    param([Parameter(Mandatory)][AllowEmptyString()][string]$Value)
    if ([string]::IsNullOrEmpty($Value) -or $Value.Length -gt 320) { return $false }
    # One anchored grammar: a user that cannot begin with '-', one '@', then one host.
    # Whitespace, quotes, control characters, '=' and option syntax all fall outside it.
    if ($Value -notmatch '^[A-Za-z0-9_][A-Za-z0-9._-]{0,63}@[A-Za-z0-9.-]{1,253}$') { return $false }
    return (Test-SvHostName $Value.Substring($Value.IndexOf('@') + 1))
}

function Assert-SvTunnelTarget {
    param([Parameter(Mandatory)][AllowEmptyString()][string]$Value)
    if (-not (Test-SvTunnelTarget $Value)) {
        # The rejected value is not echoed: it can carry an operator account or host.
        throw 'The database tunnel target must be exactly user@host (IPv4 or hostname). Option syntax, whitespace, quotes and control characters are refused.'
    }
    return $Value
}

function Assert-SvKeyPath {
    param([Parameter(Mandatory)][AllowEmptyString()][string]$Value)
    if ([string]::IsNullOrEmpty($Value)) { throw 'The SSH key path is empty.' }
    if ($Value.StartsWith('-')) { throw 'The SSH key path must not begin with a dash.' }
    foreach ($character in $Value.ToCharArray()) {
        if ([int]$character -lt 32 -or [int]$character -eq 34) {
            throw 'The SSH key path must not contain quotes or control characters.'
        }
    }
    $svResolved = (Resolve-Path -LiteralPath $Value).Path
    if (-not (Test-Path -LiteralPath $svResolved -PathType Leaf)) {
        throw 'The SSH key path is not a file.'
    }
    return $svResolved
}

function Get-SvArgv {
    <#
    Split a Win32 command line into arguments using the documented CRT rules: whitespace
    separates arguments outside quotes, a backslash run escapes a following quote, and two
    quotes inside a quoted argument produce one literal quote. Ownership checks compare
    these tokens rather than searching the raw string, because 'C:/pilot/r2' is a substring
    of 'C:/pilot/r2-x'.
    #>
    param([Parameter(Mandatory)][AllowEmptyString()][AllowNull()][string]$CommandLine)
    $svArguments = New-Object Collections.Generic.List[string]
    if ([string]::IsNullOrWhiteSpace($CommandLine)) { return , $svArguments.ToArray() }
    $svCurrent = New-Object Text.StringBuilder
    $svQuoted = $false
    $svStarted = $false
    $svIndex = 0
    while ($svIndex -lt $CommandLine.Length) {
        $svCharacter = $CommandLine[$svIndex]
        if ($svCharacter -eq '\') {
            $svSlashes = 0
            while ($svIndex -lt $CommandLine.Length -and $CommandLine[$svIndex] -eq '\') {
                $svSlashes++
                $svIndex++
            }
            if ($svIndex -lt $CommandLine.Length -and $CommandLine[$svIndex] -eq '"') {
                $null = $svCurrent.Append('\', [int][Math]::Floor($svSlashes / 2))
                if ($svSlashes % 2 -eq 1) {
                    $null = $svCurrent.Append('"')
                    $svIndex++
                } else {
                    $svQuoted = -not $svQuoted
                    $svIndex++
                }
                $svStarted = $true
            } else {
                $null = $svCurrent.Append('\', $svSlashes)
                $svStarted = $true
            }
            continue
        }
        if ($svCharacter -eq '"') {
            if ($svQuoted -and $svIndex + 1 -lt $CommandLine.Length -and $CommandLine[$svIndex + 1] -eq '"') {
                $null = $svCurrent.Append('"')
                $svIndex += 2
            } else {
                $svQuoted = -not $svQuoted
                $svIndex++
            }
            $svStarted = $true
            continue
        }
        if (-not $svQuoted -and ($svCharacter -eq ' ' -or $svCharacter -eq "`t")) {
            if ($svStarted) {
                $svArguments.Add($svCurrent.ToString())
                $null = $svCurrent.Clear()
                $svStarted = $false
            }
            $svIndex++
            continue
        }
        $null = $svCurrent.Append($svCharacter)
        $svStarted = $true
        $svIndex++
    }
    if ($svStarted) { $svArguments.Add($svCurrent.ToString()) }
    return , $svArguments.ToArray()
}

function Get-SvNormalizedPath {
    param([Parameter(Mandatory)][AllowEmptyString()][AllowNull()][string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) { return $null }
    try {
        $svFull = [IO.Path]::GetFullPath($Value.Replace('/', '\'))
    } catch {
        return $null
    }
    return $svFull.TrimEnd('\').Replace('\', '/')
}

function Test-SvSamePath {
    param(
        [Parameter(Mandatory)][AllowEmptyString()][AllowNull()][string]$Left,
        [Parameter(Mandatory)][AllowEmptyString()][AllowNull()][string]$Right
    )
    $svLeft = Get-SvNormalizedPath $Left
    $svRight = Get-SvNormalizedPath $Right
    if ($null -eq $svLeft -or $null -eq $svRight) { return $false }
    return [string]::Equals($svLeft, $svRight, [StringComparison]::OrdinalIgnoreCase)
}

function Get-SvArgumentValue {
    <# The token that follows an exact option token, or $null. #>
    param(
        [Parameter(Mandatory)][AllowEmptyCollection()][string[]]$Argv,
        [Parameter(Mandatory)][string]$Option
    )
    for ($svIndex = 0; $svIndex -lt $Argv.Count - 1; $svIndex++) {
        if ([string]::Equals($Argv[$svIndex], $Option, [StringComparison]::Ordinal)) {
            return $Argv[$svIndex + 1]
        }
    }
    return $null
}

function Test-SvOwnedByState {
    <# True when the command line runs $ScriptPath for exactly $StatePath. #>
    param(
        [Parameter(Mandatory)][AllowEmptyString()][AllowNull()][string]$CommandLine,
        [Parameter(Mandatory)][string]$ScriptPath,
        [Parameter(Mandatory)][string]$StatePath
    )
    $svArgv = Get-SvArgv $CommandLine
    if ($svArgv.Count -eq 0) { return $false }
    $svScriptSeen = $false
    foreach ($svToken in $svArgv) {
        if (Test-SvSamePath $svToken $ScriptPath) { $svScriptSeen = $true; break }
    }
    if (-not $svScriptSeen) { return $false }
    return (Test-SvSamePath (Get-SvArgumentValue -Argv $svArgv -Option '--state') $StatePath)
}

function Get-SvShortcutMarker {
    return 'SaintVision owned desktop launcher v1; no workload dispatch'
}

function Assert-SvOwnedShortcut {
    <#
    Refuse a link this setup did not create. Kept here rather than inline in the registrar so
    the rule is exercised directly by a regression test instead of only described in source.
    #>
    param([Parameter(Mandatory)][string]$LinkPath)
    if (-not (Test-Path -LiteralPath $LinkPath)) { return $true }
    $svShell = New-Object -ComObject WScript.Shell
    $svExisting = $svShell.CreateShortcut($LinkPath)
    if ($svExisting.Description -ne (Get-SvShortcutMarker)) {
        throw 'Desktop shortcut belongs to another setup; preserved.'
    }
    return $true
}
