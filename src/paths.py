"""Project paths shared by scripts."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = ROOT / "models" / "faster-whisper"

# Defaults used by mic transcription
DEFAULT_MODEL = "small"
DEFAULT_REALTIME_MODEL = "tiny"
