# OFF switch — no GUI required
. "$PSScriptRoot\_common.ps1"

$svc = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if (-not $svc) {
    Write-Host "Service '$ServiceName' is not installed"
    exit 0
}

if ($svc.Status -eq "Stopped") {
    Write-Host "$ServiceName already stopped"
    exit 0
}

Write-Host "Stopping $ServiceName ..."
Stop-Service -Name $ServiceName -Force
Start-Sleep -Seconds 1
Get-Service -Name $ServiceName | Format-Table Name, Status, StartType -AutoSize
