# Install TranscriptWhisper as a Windows Service (requires Admin).
# Uses a small compiled C# stub (no NSSM/WinSW download).

param(
    [switch]$AsCurrentUser
)

. "$PSScriptRoot\_common.ps1"
Require-Admin
Import-ServiceEnv

if (-not (Test-Path $Python)) {
    throw "Missing venv python: $Python"
}

& "$PSScriptRoot\build-stub.ps1"
$exe = Join-Path $PSScriptRoot "TranscriptWhisperSvc.exe"
if (-not (Test-Path $exe)) { throw "Stub exe missing: $exe" }

$existing = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($existing) {
    if ($existing.Status -ne "Stopped") {
        Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
    }
    sc.exe delete $ServiceName | Out-Null
    Start-Sleep -Seconds 2
}

Write-Host "Creating service $ServiceName -> $exe"
sc.exe create $ServiceName binPath= "`"$exe`"" start= auto DisplayName= "Transcript Buddy Whisper Inference"
if ($LASTEXITCODE -ne 0) { throw "sc create failed" }

sc.exe description $ServiceName "faster-whisper GPU inference backend (TCP port)" | Out-Null
sc.exe failure $ServiceName reset= 86400 actions= restart/5000/restart/15000/""/0 | Out-Null

# Environment for the stub process
$svcKey = "HKLM:\SYSTEM\CurrentControlSet\Services\$ServiceName"
$envLines = @(
    "TB_AGENT_DIR=$AgentDir"
    "TB_PYTHON=$Python"
    "PYTHONPATH=$AgentDir;$Root\src"
    "AGENT_HOST=$($env:AGENT_HOST)"
    "AGENT_PORT=$($env:AGENT_PORT)"
    "AGENT_TOKEN=$($env:AGENT_TOKEN)"
    "PRELOAD_MODELS=$($env:PRELOAD_MODELS)"
    "MODELS_DIR=$($env:MODELS_DIR)"
    "STT_DEVICE=$($env:STT_DEVICE)"
    "STT_COMPUTE_TYPE=$($env:STT_COMPUTE_TYPE)"
    "OLLAMA_URL=$($env:OLLAMA_URL)"
    "OLLAMA_MODEL=$($env:OLLAMA_MODEL)"
)
New-ItemProperty -Path $svcKey -Name "Environment" -PropertyType MultiString -Value $envLines -Force | Out-Null

if ($AsCurrentUser) {
    $user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    Write-Host "Set service account to $user (recommended for NVIDIA GPU)..."
    $secure = Read-Host "Password for $user" -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
    sc.exe config $ServiceName obj= "$user" password= "$plain"
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Could not set account. Configure Log On in services.msc if CUDA fails under LocalSystem."
    }
} else {
    Write-Host "Account: LocalSystem. If GPU/CUDA fails later, re-run: .\install.ps1 -AsCurrentUser"
}

Write-Host ""
Write-Host "Installed. No-GUI switches:"
Write-Host "  sc.exe start $ServiceName"
Write-Host "  sc.exe stop $ServiceName"
Write-Host "  .\start.ps1"
Write-Host "  .\stop.ps1"
