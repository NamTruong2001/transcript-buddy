"""Realtime microphone transcription with RealtimeSTT + faster-whisper on NVIDIA GPU.

Usage:
  .\\.venv\\Scripts\\python.exe scripts\\transcribe_mic.py
  .\\.venv\\Scripts\\python.exe scripts\\transcribe_mic.py --model small --language vi
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cuda_bootstrap import ensure_cuda_dlls  # noqa: E402
from paths import DEFAULT_MODEL, DEFAULT_REALTIME_MODEL, MODELS_DIR  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Realtime STT on NVIDIA GPU (faster-whisper)")
    p.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="Whisper model for final transcript (tiny/base/small/medium/large-v2/...)",
    )
    p.add_argument(
        "--realtime-model",
        default=DEFAULT_REALTIME_MODEL,
        help="Smaller model used for live partial text",
    )
    p.add_argument(
        "--download-root",
        default=str(MODELS_DIR),
        help="Local folder for faster-whisper models (project models/faster-whisper)",
    )
    p.add_argument("--language", default=None, help="Force language code, e.g. vi or en")
    p.add_argument(
        "--compute-type",
        default="float16",
        help="CTranslate2 compute type (float16 recommended on NVIDIA GPU)",
    )
    p.add_argument(
        "--no-realtime",
        action="store_true",
        help="Disable live partial transcription (final text only)",
    )
    return p.parse_args()


def main() -> int:
    ensure_cuda_dlls()
    args = parse_args()
    Path(args.download_root).mkdir(parents=True, exist_ok=True)

    print(
        f"Engine=faster_whisper | device=cuda | model={args.model} "
        f"| realtime={args.realtime_model if not args.no_realtime else 'off'} "
        f"| compute_type={args.compute_type}",
        flush=True,
    )
    print(f"Models dir: {args.download_root}", flush=True)
    print("Loading VAD + Whisper on GPU (may take ~10-30s)...", flush=True)

    from RealtimeSTT import AudioToTextRecorder

    live_line = {"text": ""}

    def on_realtime(text: str) -> None:
        live_line["text"] = text
        print(f"\r[live] {text[:120]}", end="", flush=True)

    def on_final(text: str) -> None:
        if live_line["text"]:
            print(flush=True)
            live_line["text"] = ""
        if text and text.strip():
            print(f"[final] {text}", flush=True)

    kwargs = dict(
        transcription_engine="faster_whisper",
        model=args.model,
        download_root=args.download_root,
        device="cuda",
        compute_type=args.compute_type,
        gpu_device_index=0,
        language=args.language,
        spinner=False,
        # Local ONNX Silero — avoids interactive torch.hub trust prompt
        silero_backend="raw_onnx",
        enable_realtime_transcription=not args.no_realtime,
        realtime_model_type=args.realtime_model,
        on_realtime_transcription_update=on_realtime if not args.no_realtime else None,
    )

    recorder = AudioToTextRecorder(**{k: v for k, v in kwargs.items() if v is not None})
    print("Ready. Speak into the microphone. Ctrl+C to stop.\n", flush=True)

    try:
        while True:
            # Callback form keeps listening while finalization runs
            recorder.text(on_final)
    except KeyboardInterrupt:
        print("\nStopped.", flush=True)
    finally:
        recorder.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
