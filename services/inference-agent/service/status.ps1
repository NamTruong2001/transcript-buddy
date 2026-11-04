. "$PSScriptRoot\_common.ps1"
Import-ServiceEnv

$svc = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if (-not $svc) {
    Write-Host "NOT INSTALLED: $ServiceName"
    exit 1
}
$svc | Format-Table Name, Status, StartType -AutoSize
$port = $env:AGENT_PORT
try {
    $h = Invoke-RestMethod -Uri "http://127.0.0.1:$port/health" -TimeoutSec 3
    Write-Host "HTTP /health ok=$($h.ok) loaded=$($h.models_loaded -join ',')"
} catch {
    Write-Host "HTTP /health unreachable on port $port"
}
