"""Host entry for pywin32 service registration (run from this directory)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "src"))

from app.winservice import WhisperInferenceService  # noqa: E402

if __name__ == "__main__":
    import servicemanager
    import win32serviceutil

    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(WhisperInferenceService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(WhisperInferenceService)
