from __future__ import annotations

import threading
from typing import Any

from faster_whisper import WhisperModel

from .config import COMPUTE_TYPE, DEVICE, MODELS_DIR


class ModelPool:
    """Lazy-load and cache WhisperModel instances by name (GPU resident)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._models: dict[str, WhisperModel] = {}

    def loaded(self) -> list[str]:
        with self._lock:
            return sorted(self._models.keys())

    def get(self, name: str) -> WhisperModel:
        with self._lock:
            if name not in self._models:
                self._models[name] = WhisperModel(
                    name,
                    device=DEVICE,
                    compute_type=COMPUTE_TYPE,
                    download_root=str(MODELS_DIR),
                )
            return self._models[name]

    def preload(self, names: list[str]) -> list[str]:
        """Load models into GPU memory; return successfully loaded ids."""
        loaded: list[str] = []
        for name in names:
            self.get(name)
            loaded.append(name)
        return loaded

    def transcribe(
        self,
        name: str,
        audio_f32,
        *,
        language: str | None = None,
        beam_size: int = 1,
    ) -> str:
        model = self.get(name)
        segments, _info = model.transcribe(
            audio_f32,
            language=language,
            beam_size=beam_size,
            vad_filter=False,
            condition_on_previous_text=False,
        )
        parts = [seg.text.strip() for seg in segments if seg.text and seg.text.strip()]
        return " ".join(parts).strip()


POOL = ModelPool()
