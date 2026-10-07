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
    <#
    Reviewer r2 (High): whitespace was accepted, and that breaks the native argument
    boundary rather than merely looking untidy. Windows PowerShell joins an -ArgumentList
    array with spaces without quoting, so a real file named 'key with space' arrived at the
    child as three arguments -- measured with an argv recorder: '-i', '...\key', 'with',
    'space'. A fragment after a space can therefore be read as an ssh option, before the
    '--' separator closes option parsing. Every whitespace character is refused here, which
    fails closed; the alternative is a quoting serializer and is a larger change than this
    boundary needs. The resolved path is re-checked, because resolution can introduce a
    component the raw value did not show.
    #>
    param([Parameter(Mandatory)][AllowEmptyString()][string]$Value)
    if ([string]::IsNullOrEmpty($Value)) { throw 'The SSH key path is empty.' }
    if ($Value.StartsWith('-')) { throw 'The SSH key path must not begin with a dash.' }
    # The RESOLVED value is the one handed to ssh, and it is the only place this rule is
    # applied: checking the raw value as well rejected nothing extra, so that second guard
    # had no witness and was removed rather than kept and described. Resolution is what can
    # introduce whitespace a caller never typed -- a relative 'id_ed25519' under a working
    # directory containing a space resolves to '...\dir with space\id_ed25519'. (Measured:
    # Resolve-Path does not expand 8.3 short names and preserves a trailing space, so
    # neither of those is the reason.) A raw value carrying a quote or control character
    # still fails closed, on Resolve-Path rather than with this message.
    $svResolved = (Resolve-Path -LiteralPath $Value).Path
    $null = Assert-SvNativeArgument -Value $svResolved -What 'The resolved SSH key path'
    if (-not (Test-Path -LiteralPath $svResolved -PathType Leaf)) {
        throw 'The SSH key path is not a file.'
    }
    return $svResolved
}

function Assert-SvNativeArgument {
    <#
    The same boundary for every value this launcher hands to a native child through
    -ArgumentList: state directories, script paths and interpreter paths. A value carrying
    whitespace or a quote would be split or re-quoted by the runtime, so it is refused with
    the reason named rather than silently mis-serialized.
    #>
    param(
        [Parameter(Mandatory)][AllowEmptyString()][AllowNull()][string]$Value,
        [Parameter(Mandatory)][string]$What
    )
    if ([string]::IsNullOrEmpty($Value)) { throw ($What + ' is empty.') }
    foreach ($character in $Value.ToCharArray()) {
        if ([char]::IsWhiteSpace($character) -or [int]$character -eq 34 -or [int]$character -lt 32) {
            throw ($What + ' must not contain whitespace, quotes or control characters: it is passed to a native command and would be split into several arguments. Move it to a path without spaces.')
        }
    }
    return $Value
}

function Get-SvArgv {
    <#
    Split a Win32 command line into arguments using the documented CRT rules: whitespace
    separates arguments outside quotes, a backslash run escapes a following quote, and two
    quotes inside a quoted argument produce one literal quote. Ownership checks compare
    these tokens rather than searching the raw string, because 'C:/pilot/r2' is a substring
    of 'C:/pilot/r2-x'.

    Returns the plain array, so EVERY call site must wrap with @(). Returning a
    comma-wrapped array instead made a wrapping caller receive one element holding the whole
    string[], and every token comparison then failed against an array -- the same unrolling
    trap Get-SvListeners had, in the opposite direction. One rule for both.
    #>
    param([Parameter(Mandatory)][AllowEmptyString()][AllowNull()][string]$CommandLine)
    $svArguments = New-Object Collections.Generic.List[string]
    if ([string]::IsNullOrWhiteSpace($CommandLine)) { return $svArguments.ToArray() }
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
    return $svArguments.ToArray()
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
    $svArgv = @(Get-SvArgv $CommandLine)
    if ($svArgv.Count -eq 0) { return $false }
    $svScriptSeen = $false
    foreach ($svToken in $svArgv) {
        if (Test-SvSamePath $svToken $ScriptPath) { $svScriptSeen = $true; break }
    }
    if (-not $svScriptSeen) { return $false }
    return (Test-SvSamePath (Get-SvArgumentValue -Argv $svArgv -Option '--state') $StatePath)
}

function Get-SvSystemSshPath {
    <# The one ssh executable this launcher will accept as a tunnel owner. #>
    return (Join-Path $env:SystemRoot 'System32/OpenSSH/ssh.exe')
}

function Test-SvOwnedSshForward {
    <#
    Reviewer r2 (High): the previous check asked whether the expected forward and target
    appeared as tokens ANYWHERE in the owner's command line, and skipped the target
    comparison entirely when no target had been supplied. A command line whose real -L was
    '127.0.0.1:P:evil.example:P' passed, because the expected forward also appeared as a
    trailing remote-command token -- reproduced before this change.

    This is now positional and total:
      * argv[0] must be the exact system ssh executable;
      * there must be exactly one -L, and the token IMMEDIATELY AFTER it must equal the
        expected forward;
      * there must be a '--' separator, and the token IMMEDIATELY AFTER it must equal the
        expected target, which is required rather than optional;
      * nothing may follow the destination, so no remote command is carried.
    #>
    param(
        [Parameter(Mandatory)][AllowEmptyString()][AllowNull()][string]$CommandLine,
        [Parameter(Mandatory)][string]$ExpectedForward,
        [Parameter(Mandatory)][AllowEmptyString()][string]$ExpectedTarget
    )
    # Not redundant with the positional comparison below: Get-SvArgv can yield an empty
    # token from '""', and an empty expected target would then compare equal to it.
    if ([string]::IsNullOrEmpty($ExpectedTarget)) { return $false }
    $svArgv = @(Get-SvArgv $CommandLine)
    if ($svArgv.Count -lt 2) { return $false }
    if (-not (Test-SvSamePath $svArgv[0] (Get-SvSystemSshPath))) { return $false }

    $svForwardIndexes = @()
    $svSeparatorIndexes = @()
    for ($svIndex = 1; $svIndex -lt $svArgv.Count; $svIndex++) {
        if ([string]::Equals($svArgv[$svIndex], '-L', [StringComparison]::Ordinal)) { $svForwardIndexes += $svIndex }
        if ([string]::Equals($svArgv[$svIndex], '--', [StringComparison]::Ordinal)) { $svSeparatorIndexes += $svIndex }
    }
    # More than one forward or separator means the command line is not the shape this
    # launcher builds, so it is not identifiable as the owned tunnel.
    if ($svForwardIndexes.Count -ne 1 -or $svSeparatorIndexes.Count -ne 1) { return $false }

    $svForwardAt = $svForwardIndexes[0] + 1
    if ($svForwardAt -ge $svArgv.Count) { return $false }
    if (-not [string]::Equals($svArgv[$svForwardAt], $ExpectedForward, [StringComparison]::Ordinal)) { return $false }

    $svTargetAt = $svSeparatorIndexes[0] + 1
    if ($svTargetAt -ne $svArgv.Count - 1) { return $false }
    if (-not [string]::Equals($svArgv[$svTargetAt], $ExpectedTarget, [StringComparison]::Ordinal)) { return $false }
    return $true
}

function Assert-SvOwnedTunnelListeners {
    <#
    The single gate both the reuse path and the post-start path go through, so the two
    cannot drift: previously reuse checked tokens loosely and the post-start check looked
    only at the bind address, which a racing process could satisfy.

    Every listener on the port must be bound to a loopback address, its owning process must
    pass Test-SvOwnedSshForward, and -- when an expected process id is supplied, as it is
    after this launcher starts ssh itself -- the owning process must be exactly that id.
    The command line is read through $CommandLineProvider, which is given the owning pid, so
    the identity compared is that of the process actually holding the port.
    #>
    param(
        [Parameter(Mandatory)][AllowEmptyCollection()][AllowNull()][object[]]$Listeners,
        [Parameter(Mandatory)][string]$ExpectedForward,
        [Parameter(Mandatory)][AllowEmptyString()][string]$ExpectedTarget,
        [Parameter(Mandatory)][scriptblock]$CommandLineProvider,
        [int]$ExpectedProcessId = 0
    )
    $svListeners = @($Listeners)
    if ($svListeners.Count -eq 0) { return $false }
    $svLoopbackAddresses = @('127.0.0.1', '::1')
    foreach ($svListener in $svListeners) {
        if ($svListener.LocalAddress -notin $svLoopbackAddresses) { return $false }
        $svOwningProcess = [int]$svListener.OwningProcess
        if ($ExpectedProcessId -ne 0 -and $svOwningProcess -ne $ExpectedProcessId) { return $false }
        if (-not (Test-SvOwnedSshForward -CommandLine (& $CommandLineProvider $svOwningProcess) `
                                         -ExpectedForward $ExpectedForward `
                                         -ExpectedTarget $ExpectedTarget)) {
            return $false
        }
    }
    return $true
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
