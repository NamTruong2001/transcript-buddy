# Poll /ready until Whisper backend answers on AGENT_PORT.
param(
    [string]$BaseUrl = "",
    [int]$TimeoutSec = 180
)

if (-not $BaseUrl) {
    $port = if ($env:AGENT_PORT) { $env:AGENT_PORT } else { "8100" }
    $BaseUrl = "http://127.0.0.1:$port"
}

$deadline = (Get-Date).AddSeconds($TimeoutSec)
Write-Host "Waiting for $BaseUrl/ready ..."
while ((Get-Date) -lt $deadline) {
    try {
        $r = Invoke-RestMethod -Uri "$BaseUrl/ready" -TimeoutSec 3
        if ($r.ready -eq $true) {
            Write-Host "READY loaded=$($r.loaded -join ',')"
            exit 0
        }
        Write-Host "warming... loaded=$($r.loaded -join ',')"
    } catch {
        Write-Host "not up yet..."
    }
    Start-Sleep -Seconds 2
}
Write-Error "Timeout waiting for Whisper backend"
exit 1
