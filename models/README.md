# Models (local)

faster-whisper weights live under `faster-whisper/`.

Download (or refresh) with:

```powershell
.\.venv\Scripts\python.exe .\scripts\download_models.py
```

Typical installs: `tiny` (realtime), `small` (final), optional `large-v3-turbo`.

Source: Hugging Face `Systran/faster-whisper-*` / `mobiuslabsgmbh/faster-whisper-large-v3-turbo`.

Weights are gitignored (large binaries). Keep this README tracked.

Agent syncs this folder into SQLite (`services/inference-agent/data/models.db`) via `POST /models/sync`.
