"""Windows Service wrapper for Whisper inference backend (port AGENT_PORT).

Install (Admin PowerShell):
  .\\service\\install.ps1

Switch without GUI:
  sc.exe start TranscriptWhisper
  sc.exe stop TranscriptWhisper
  # or
  .\\service\\start.ps1
  .\\service\\stop.ps1
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import servicemanager
import win32event
import win32service
import win32serviceutil

AGENT_DIR = Path(__file__).resolve().parents[1]
ROOT = AGENT_DIR.parents[1]
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
ENV_FILE = AGENT_DIR / "service" / "service.env"
SERVICE_NAME = "TranscriptWhisper"
SERVICE_DISPLAY = "Transcript Buddy Whisper Inference"
SERVICE_DESC = "faster-whisper GPU backend on TCP port (default 8100)"


def _load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip()


def _env_for_child() -> dict[str, str]:
    _load_env_file(ENV_FILE)
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{AGENT_DIR};{ROOT / 'src'}"
    env.setdefault("AGENT_HOST", "0.0.0.0")
    env.setdefault("AGENT_PORT", "8100")
    env.setdefault("AGENT_TOKEN", "dev-agent-token-change-me")
    env.setdefault("PRELOAD_MODELS", "")
    env.setdefault("MODELS_DIR", str(ROOT / "models" / "faster-whisper"))
    return env


class WhisperInferenceService(win32serviceutil.ServiceFramework):
    _svc_name_ = SERVICE_NAME
    _svc_display_name_ = SERVICE_DISPLAY
    _svc_description_ = SERVICE_DESC

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.proc: subprocess.Popen | None = None

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.proc.kill()

    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, ""),
        )
        log_dir = AGENT_DIR / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        stdout = open(log_dir / "service-stdout.log", "a", encoding="utf-8")
        stderr = open(log_dir / "service-stderr.log", "a", encoding="utf-8")
        child_env = _env_for_child()
        host = child_env.get("AGENT_HOST", "0.0.0.0")
        port = child_env.get("AGENT_PORT", "8100")
        cmd = [
            str(PYTHON),
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            host,
            "--port",
            port,
        ]
        self.proc = subprocess.Popen(
            cmd,
            cwd=str(AGENT_DIR),
            env=child_env,
            stdout=stdout,
            stderr=stderr,
        )
        while True:
            rc = win32event.WaitForSingleObject(self.stop_event, 1000)
            if rc == win32event.WAIT_OBJECT_0:
                break
            if self.proc.poll() is not None:
                break
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        stdout.close()
        stderr.close()
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STOPPED,
            (self._svc_name_, ""),
        )


if __name__ == "__main__":
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(WhisperInferenceService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(WhisperInferenceService)
