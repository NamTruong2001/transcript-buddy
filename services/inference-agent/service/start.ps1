# ON switch — no GUI required (can run from SSH / schtasks / sc)
. "$PSScriptRoot\_common.ps1"

$svc = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if (-not $svc) {
    throw "Service '$ServiceName' not installed. Run .\install.ps1 as Administrator first."
}

if ($svc.Status -eq "Running") {
    Write-Host "$ServiceName already running"
    exit 0
}

Write-Host "Starting $ServiceName ..."
Start-Service -Name $ServiceName
Start-Sleep -Seconds 2
Get-Service -Name $ServiceName | Format-Table Name, Status, StartType -AutoSize

$port = if ($env:AGENT_PORT) { $env:AGENT_PORT } else { "8100" }
Import-ServiceEnv
$port = $env:AGENT_PORT
Write-Host "Health: http://127.0.0.1:$port/health"
