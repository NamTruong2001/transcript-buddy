"""Verify NVIDIA GPU is usable by torch, CTranslate2, and faster-whisper."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cuda_bootstrap import ensure_cuda_dlls  # noqa: E402
from paths import MODELS_DIR  # noqa: E402


def main() -> int:
    dlls = ensure_cuda_dlls()
    print(f"CUDA DLL dirs registered: {len(dlls)}")
    print(f"Project models dir: {MODELS_DIR}")

    import torch

    print(f"torch={torch.__version__} cuda={torch.version.cuda} available={torch.cuda.is_available()}")
    if not torch.cuda.is_available():
        print("ERROR: torch does not see a CUDA device", file=sys.stderr)
        return 1

    name = torch.cuda.get_device_name(0)
    cap = torch.cuda.get_device_capability(0)
    print(f"device={name} capability={cap}")
    x = torch.randn(64, 64, device="cuda")
    print(f"torch matmul ok: {(x @ x).shape}")

    import ctranslate2
    from faster_whisper import WhisperModel
    import numpy as np

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"ctranslate2={ctranslate2.__version__} cuda_devices={ctranslate2.get_cuda_device_count()}")
    t0 = time.time()
    model = WhisperModel(
        "tiny",
        device="cuda",
        compute_type="float16",
        download_root=str(MODELS_DIR),
    )
    print(f"faster-whisper tiny loaded in {time.time() - t0:.1f}s")
    audio = np.zeros(16000, dtype=np.float32)
    segments, info = model.transcribe(audio, language="en")
    list(segments)
    print(f"transcribe ok (language={info.language})")

    from RealtimeSTT import AudioToTextRecorder  # noqa: F401

    print("RealtimeSTT import ok")
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
