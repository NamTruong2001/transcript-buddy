# Compile C# Windows Service stub (no external NSSM/WinSW download).
$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
$csc = Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if (-not (Test-Path $csc)) {
    throw "csc.exe not found: $csc"
}
$out = Join-Path $here "TranscriptWhisperSvc.exe"
& $csc /nologo /target:exe /out:$out /r:System.ServiceProcess.dll "$here\WhisperServiceStub.cs"
if ($LASTEXITCODE -ne 0) { throw "csc failed" }
Write-Host "Built $out"
Get-Item $out | Select-Object FullName, Length
