"""Ensure NVIDIA CUDA 12 DLLs from pip packages are findable on Windows.

CTranslate2 (faster-whisper) needs cublas64_12.dll etc. PyTorch CUDA wheels
and the nvidia-*-cu12 packages ship these under site-packages/nvidia/*/bin,
but Windows does not search that path unless we register it.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def ensure_cuda_dlls() -> list[str]:
    """Add nvidia package bin dirs to the DLL search path. Safe to call often."""
    added: list[str] = []
    site = Path(sys.prefix) / "Lib" / "site-packages" / "nvidia"
    if not site.is_dir():
        return added

    for bin_dir in sorted(site.glob("*/bin")):
        path = str(bin_dir.resolve())
        if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
            os.add_dll_directory(path)
        # Also prepend PATH for child processes / older loaders.
        current = os.environ.get("PATH", "")
        if path not in current.split(os.pathsep):
            os.environ["PATH"] = path + os.pathsep + current
        added.append(path)
    return added
