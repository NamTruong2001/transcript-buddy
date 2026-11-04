# Start Windows Whisper inference backend on a TCP port (default 8100).
# Edge (Linux) talks to this process only via Tailscale:
#   HTTP  http://100.65.100.110:8100/health|/ready|/models|/warmup
#   WS    ws://100.65.100.110:8100/ws?token=...

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$root = Resolve-Path ..\..
$env:PYTHONPATH = "$PSScriptRoot;$root\src"
if (-not $env:AGENT_TOKEN) { $env:AGENT_TOKEN = "dev-agent-token-change-me" }
if (-not $env:AGENT_HOST) { $env:AGENT_HOST = "0.0.0.0" }
if (-not $env:AGENT_PORT) { $env:AGENT_PORT = "8100" }
# Preload common models into GPU at startup (empty string = lazy load)
if (-not $env:PRELOAD_MODELS) { $env:PRELOAD_MODELS = "tiny,small" }

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Missing venv python: $python"
}

Write-Host "=== Whisper inference backend ==="
Write-Host "Models dir : $root\models\faster-whisper"
Write-Host "Bind       : $($env:AGENT_HOST):$($env:AGENT_PORT)"
Write-Host "Preload    : $($env:PRELOAD_MODELS)"
Write-Host "Token      : (AGENT_TOKEN set)"
Write-Host ""

& $python -m uvicorn app.main:app --host $env:AGENT_HOST --port $env:AGENT_PORT
