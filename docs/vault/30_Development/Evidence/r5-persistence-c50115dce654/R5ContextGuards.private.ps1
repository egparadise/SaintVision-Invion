function Assert-SvPacketPins {
 param($Plan)
 foreach($svPin in $Plan.pins){
  $svItem=Get-Item -LiteralPath $svPin.path -Force -ErrorAction Stop
  if(-not($svItem -is [IO.FileInfo]) -or ($svItem.Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'Pinned input is not ordinary'}
  if((Get-FileHash -LiteralPath $svPin.path -Algorithm SHA256).Hash.ToLowerInvariant() -cne $svPin.sha256){throw 'Packet input hash differs'}
 }
}
function Get-SvActualContext {
 param([string]$OwnerSid)
 if(-not('SvR5ContextNative' -as [type])){
  Add-Type -TypeDefinition @'
using System; using System.Text; using System.Runtime.InteropServices;
public static class SvR5ContextNative {
 [DllImport("kernel32.dll",SetLastError=true)] [return:MarshalAs(UnmanagedType.Bool)] public static extern bool IsProcessInJob(IntPtr process,IntPtr job,[MarshalAs(UnmanagedType.Bool)] out bool result);
 [DllImport("kernel32.dll")] public static extern uint GetCurrentThreadId();
 [DllImport("user32.dll",SetLastError=true)] public static extern IntPtr GetProcessWindowStation();
 [DllImport("user32.dll",SetLastError=true)] public static extern IntPtr GetThreadDesktop(uint threadId);
 [DllImport("user32.dll",CharSet=CharSet.Unicode,SetLastError=true)] [return:MarshalAs(UnmanagedType.Bool)] public static extern bool GetUserObjectInformation(IntPtr handle,int index,StringBuilder value,int length,out int needed);
}
'@
 }
 $svInJob=$false
 $svQuery=[SvR5ContextNative]::IsProcessInJob([Diagnostics.Process]::GetCurrentProcess().Handle,[IntPtr]::Zero,[ref]$svInJob)
 $svNames=@()
 foreach($svHandle in @([SvR5ContextNative]::GetProcessWindowStation(),[SvR5ContextNative]::GetThreadDesktop([SvR5ContextNative]::GetCurrentThreadId()))){
  $svName=New-Object Text.StringBuilder 512
  $svNeeded=0
  if(-not [SvR5ContextNative]::GetUserObjectInformation($svHandle,2,$svName,1024,[ref]$svNeeded)){throw 'Actual desktop/window-station query unavailable'}
  $svNames+=,$svName.ToString()
 }
 return [pscustomobject]@{pid=$PID;sessionId=(Get-Process -Id $PID).SessionId;ownerMatched=([Security.Principal.WindowsIdentity]::GetCurrent().User.Value -ceq $OwnerSid);userInteractive=[Environment]::UserInteractive;jobQuerySucceeded=$svQuery;inJob=$svInJob;windowStation=$svNames[0];desktop=$svNames[1]}
}
function Assert-SvJobFreeContext {
 param($Context,[int]$ExpectedSession,[switch]$Attended)
 if(-not $Context.ownerMatched -or -not $Context.jobQuerySucceeded -or $Context.inJob){throw 'Actual owner/job context rejected'}
 if($Attended -and ($Context.sessionId -ne $ExpectedSession -or -not $Context.userInteractive -or $Context.windowStation -ine 'WinSta0' -or $Context.desktop -ine 'Default')){throw 'Actual attended desktop/session rejected'}
}
function Assert-SvRecordRoot {
 param([string]$Root)
 $svExpected=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'wmi-runtime'))
 if(-not[string]::Equals([IO.Path]::GetFullPath($Root),$svExpected,[StringComparison]::OrdinalIgnoreCase)){throw 'Unexpected fresh record namespace'}
 foreach($svPath in @($PSScriptRoot,(Split-Path -Parent $PSScriptRoot),$svExpected)){
  $svItem=Get-Item -LiteralPath $svPath -Force -ErrorAction Stop
  if(-not($svItem -is [IO.DirectoryInfo]) -or ($svItem.Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'Record namespace ancestry is unsafe'}
 }
}
function Write-SvNewReceipt {
 param([string]$Path,$Value)
 $svRaw=[Text.Encoding]::UTF8.GetBytes(($Value | ConvertTo-Json -Depth 12))
 $svTemporary=$Path+'.pending.'+[Guid]::NewGuid().ToString('N')
 $svStream=[IO.File]::Open($svTemporary,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
 try{$svStream.Write($svRaw,0,$svRaw.Length);$svStream.Flush($true)}finally{$svStream.Dispose()}
 # Same-directory publication is atomic; Move without overwrite also owns intent.
 [IO.File]::Move($svTemporary,$Path)
}
