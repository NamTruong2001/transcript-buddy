from __future__ import annotations

from pathlib import Path

from .config import MODELS_DIR

_KNOWN = {
    "models--Systran--faster-whisper-tiny": "tiny",
    "models--Systran--faster-whisper-tiny.en": "tiny.en",
    "models--Systran--faster-whisper-base": "base",
    "models--Systran--faster-whisper-base.en": "base.en",
    "models--Systran--faster-whisper-small": "small",
    "models--Systran--faster-whisper-small.en": "small.en",
    "models--Systran--faster-whisper-medium": "medium",
    "models--Systran--faster-whisper-medium.en": "medium.en",
    "models--Systran--faster-whisper-large-v2": "large-v2",
    "models--Systran--faster-whisper-large-v3": "large-v3",
}


def _has_weights(path: Path) -> bool:
    if (path / "model.bin").exists():
        return True
    return any(path.glob("snapshots/*/model.bin"))


def list_local_models(models_dir: Path | None = None) -> list[dict]:
    root = models_dir or MODELS_DIR
    by_id: dict[str, dict] = {}
    if not root.is_dir():
        return []

    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if not _has_weights(child):
            continue
        name = _KNOWN.get(child.name, child.name if (child / "model.bin").exists() else None)
        if not name:
            continue
        size = sum(f.stat().st_size for f in child.rglob("*") if f.is_file())
        by_id[name] = {
            "id": name,
            "path": str(child),
            "size_mb": round(size / (1024 * 1024), 1),
        }
    return [by_id[k] for k in sorted(by_id.keys())]


def resolve_realtime_model(final_model: str, available: set[str]) -> str:
    heavy = {"medium", "medium.en", "large-v1", "large-v2", "large-v3", "large"}
    if final_model in heavy and "tiny" in available:
        return "tiny"
    if final_model in available:
        return final_model
    if "tiny" in available:
        return "tiny"
    return final_model
