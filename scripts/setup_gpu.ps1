# Setup transcript-buddy with RealtimeSTT + faster-whisper on NVIDIA GPU (CUDA 12.8).
# Requires: uv, NVIDIA driver supporting CUDA 12.8+ (RTX 50 / Blackwell needs cu128).

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "==> Creating Python 3.12 venv"
uv python install 3.12
uv venv .venv --python 3.12

Write-Host "==> Installing PyTorch cu128 (required for RTX 50 / sm_120)"
uv pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128 --python .\.venv\Scripts\python.exe

Write-Host "==> Installing RealtimeSTT[faster-whisper] + CUDA 12 runtime libs"
uv pip install -r requirements.txt --python .\.venv\Scripts\python.exe

Write-Host "==> Downloading faster-whisper models into .\models\faster-whisper"
.\.venv\Scripts\python.exe .\scripts\download_models.py
if ($LASTEXITCODE -ne 0) {
    throw "Model download failed"
}

Write-Host "==> Verifying GPU"
.\.venv\Scripts\python.exe .\scripts\check_gpu.py
if ($LASTEXITCODE -ne 0) {
    throw "GPU check failed"
}

Write-Host "Setup complete. Run:"
Write-Host "  .\.venv\Scripts\python.exe .\scripts\transcribe_mic.py"
