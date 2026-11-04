# transcript-buddy

Realtime speech-to-text web app:

- **Frontend** (Svelte + shadcn-style): mic, chọn model, live/final/summary
- **Edge API** (FastAPI + aiortc WebRTC) trên Docker Linux `new-home-server`
- **Inference agent** (faster-whisper CUDA + Ollama `qwen3.5:4b`) trên Windows GPU `pc`
- Liên kết qua **Tailscale**

Chi tiết: [docs/system-design.md](docs/system-design.md)

## Quick local (Windows GPU)

Hiện 3 process đang chạy trên máy này (nếu còn sống):

| Service | URL |
| --- | --- |
| inference-agent | http://127.0.0.1:8100/health |
| edge-api | http://127.0.0.1:8001/api/health |
| frontend | http://127.0.0.1:5173 |

Mở UI → chọn model → **Start** → nói → **Stop + Summarize**.

### Whisper backend trên Windows (port)

```powershell
cd services\inference-agent
$env:AGENT_PORT = "8100"
$env:PRELOAD_MODELS = "tiny,small"
.\run.ps1
# terminal khác: .\wait_ready.ps1
```

Edge kết nối: `AGENT_URL=ws://100.65.100.110:8100/ws` (hoặc `127.0.0.1` khi test local).

### Validate trước khi deploy

```powershell
.\.venv\Scripts\python.exe .\scripts\local_e2e.py --edge http://127.0.0.1:8001 --agent-ws ws://127.0.0.1:8100/ws
```

Chỉ deploy Linux khi lệnh trên in `ALL LOCAL E2E CHECKS PASSED` và bạn đã test mic trên UI.

## Models đã tải

`models/faster-whisper`: `tiny`, `small`, `large-v3`

```powershell
.\.venv\Scripts\python.exe .\scripts\download_models.py --models tiny,small,large-v3
```

## Deploy Linux

Xem [deploy/README.md](deploy/README.md).
