$ErrorActionPreference = "Stop"

$ServiceName = "TranscriptWhisper"
$AgentDir = Resolve-Path (Join-Path $PSScriptRoot "..")
$Root = Resolve-Path (Join-Path $AgentDir "..\..")
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$EnvFile = Join-Path $PSScriptRoot "service.env"

function Import-ServiceEnv {
    if (-not (Test-Path $EnvFile)) {
        Copy-Item (Join-Path $PSScriptRoot "service.env.example") $EnvFile
    }
    Get-Content $EnvFile | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) { return }
        $parts = $line.Split("=", 2)
        if ($parts.Length -eq 2) {
            [System.Environment]::SetEnvironmentVariable($parts[0].Trim(), $parts[1].Trim(), "Process")
        }
    }
    $env:PYTHONPATH = "$AgentDir;$Root\src"
    if (-not $env:MODELS_DIR) {
        $env:MODELS_DIR = Join-Path $Root "models\faster-whisper"
    }
}

function Test-IsAdmin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $p = New-Object Security.Principal.WindowsPrincipal($id)
    return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Require-Admin {
    if (-not (Test-IsAdmin)) {
        throw "Need Administrator. Right-click PowerShell -> Run as administrator, then re-run this script."
    }
}
