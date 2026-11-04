from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MODELS_DIR = Path(os.environ.get("MODELS_DIR", ROOT / "models" / "faster-whisper"))

HOST = os.environ.get("AGENT_HOST", "0.0.0.0")
PORT = int(os.environ.get("AGENT_PORT", "8100"))
AGENT_TOKEN = os.environ.get("AGENT_TOKEN", "dev-agent-token-change-me")

# Comma-separated Whisper models to load into GPU at process startup.
# Example: PRELOAD_MODELS=tiny,small
# Empty = listen on port first; load on first session.open / POST /warmup
PRELOAD_MODELS = [
    m.strip()
    for m in os.environ.get("PRELOAD_MODELS", "tiny,small").split(",")
    if m.strip()
]

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3.5:4b")
OLLAMA_TIMEOUT_S = float(os.environ.get("OLLAMA_TIMEOUT_S", "60"))

DEVICE = os.environ.get("STT_DEVICE", "cuda")
COMPUTE_TYPE = os.environ.get("STT_COMPUTE_TYPE", "float16")

# VAD / chunking
SAMPLE_RATE = 16000
PARTIAL_EVERY_S = float(os.environ.get("PARTIAL_EVERY_S", "0.8"))
SILENCE_END_S = float(os.environ.get("SILENCE_END_S", "0.7"))
MIN_UTTERANCE_S = float(os.environ.get("MIN_UTTERANCE_S", "0.4"))
ENERGY_THRESHOLD = float(os.environ.get("ENERGY_THRESHOLD", "400.0"))
