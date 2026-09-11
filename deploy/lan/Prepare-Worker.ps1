$ErrorActionPreference = 'Stop'
$workerLinuxPath = '/mnt/' + $PSScriptRoot.Substring(0,1).ToLower() + $PSScriptRoot.Substring(2).Replace('\','/')
& wsl.exe -d Ubuntu -- bash "$workerLinuxPath/prepare-worker.sh"
if ($LASTEXITCODE -ne 0) { throw 'Worker preparation failed. Preserve the output above.' }
