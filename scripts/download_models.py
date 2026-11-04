"""Download faster-whisper models into the project models/ folder.

Default: tiny (realtime) + small (final).
Source: Hugging Face Systran/faster-whisper-*

Usage:
  .\\.venv\\Scripts\\python.exe scripts\\download_models.py
  .\\.venv\\Scripts\\python.exe scripts\\download_models.py --models tiny,base,small
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cuda_bootstrap import ensure_cuda_dlls  # noqa: E402
from paths import DEFAULT_MODEL, DEFAULT_REALTIME_MODEL, MODELS_DIR  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Download faster-whisper models into project")
    p.add_argument(
        "--models",
        default=f"{DEFAULT_REALTIME_MODEL},{DEFAULT_MODEL}",
        help="Comma-separated model names (default: tiny,small)",
    )
    p.add_argument(
        "--device",
        default="cuda",
        choices=("cuda", "cpu"),
        help="Device used when verifying each downloaded model",
    )
    return p.parse_args()


def download_one(name: str, device: str) -> Path:
    from faster_whisper import WhisperModel

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    compute_type = "float16" if device == "cuda" else "int8"
    print(f"Downloading/loading '{name}' -> {MODELS_DIR} ({device}/{compute_type})")
    t0 = time.time()
    model = WhisperModel(
        name,
        device=device,
        compute_type=compute_type,
        download_root=str(MODELS_DIR),
    )
    del model
    print(f"  done in {time.time() - t0:.1f}s")
    return MODELS_DIR


def main() -> int:
    ensure_cuda_dlls()
    args = parse_args()
    names = [n.strip() for n in args.models.split(",") if n.strip()]
    if not names:
        print("No models specified", file=sys.stderr)
        return 1

    print(f"Project model root: {MODELS_DIR}")
    for name in names:
        download_one(name, args.device)

    print("\nInstalled under:")
    if MODELS_DIR.is_dir():
        for child in sorted(MODELS_DIR.iterdir()):
            if child.is_dir():
                size = sum(f.stat().st_size for f in child.rglob("*") if f.is_file())
                print(f"  {child.name}  ({size / (1024 * 1024):.1f} MB)")
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
