# Edit tracker

## 2026-11-05 — Deploy Dokploy (new-home-server) + GitHub

- Push repo GitHub; Dokploy compose sourceType `github` (provider đã link).
- Root `docker-compose.yml` (ports frontend `5180`, edge `8010`); AGENT_URL mặc định `ws://100.65.100.110:8100/ws`.
- E2E sau deploy: UI → edge container → Windows Whisper agent qua Tailscale.

## 2026-11-05 — Windows Service TranscriptWhisper (C# stub)

- Stub `service/WhisperServiceStub.cs` → `TranscriptWhisperSvc.exe` (csc.NET).
- Scripts: `service/install|start|stop|uninstall|status.ps1`.
- Công tắc không GUI: `sc start/stop TranscriptWhisper`.
- Đã verify: service Running, `/health` ok trên port 8100.
- Tuỳ chọn `-AsCurrentUser` nếu GPU cần user session.

## 2026-11-04 — Whisper inference backend listen port + preload

- Agent Windows = service Whisper trên `AGENT_PORT` (8100): `/health`, `/ready`, `/warmup`, `/ws`.
- `PRELOAD_MODELS` load GPU lúc startup; edge chỉ nói chuyện qua port/Tailscale.
- Thêm `wait_ready.ps1`, `services/inference-agent/README.md`; cập nhật system-design.

## 2026-11-04 — UI: preview cố định + modal transcript/summary

- Live transcript chỉ giữ vài dòng trong khung cố định (không phình layout).
- Nút “Xem lại transcript” / “Tải transcript”.
- Summary chỉ hiện CTA khi có kết quả; xem full trong modal + tải `.md`.
- Thêm `apps/frontend/src/lib/components/Modal.svelte`.

## 2026-11-04 — Local E2E validated (chưa deploy remote)

- Thêm `scripts/local_e2e.py`: edge health/models/session + agent STT (JFK sample) + Ollama summarize.
- Kết quả local: transcript JFK đúng, summary `qwen3.5:4b` OK; frontend `http://127.0.0.1:5173` proxy API OK.
- Chưa `docker compose` lên `new-home-server` (đợi user xác nhận sau khi test mic UI).

## 2026-11-04 — Realtime ASR cluster (edge + agent + frontend)

- Thêm `docs/system-design.md` (topology Tailscale, WebRTC edge, Windows GPU agent).
- Scaffold `services/inference-agent` (WS PCM, faster-whisper CUDA, Ollama `qwen3.5:4b`).
- Scaffold `apps/edge-api` (FastAPI + aiortc, proxy agent).
- Scaffold `apps/frontend` (Svelte + shadcn-style UI).
- Thêm `deploy/docker-compose.yml` cho `new-home-server`.

## 2026-11-04 — Fix mic: không còn prompt Silero / in trạng thái rõ hơn

- Cài `silero-vad[onnx-cpu]`; `transcribe_mic.py` dùng `silero_use_onnx=True`.
- In `Loading...` rồi mới `Ready` sau khi recorder khởi tạo xong (tránh tưởng app treo).
- Đổi vòng lặp sang `recorder.text(callback)` để final text in ổn định hơn.
- Cập nhật `requirements.txt` + `docs/setup.md`.

## 2026-11-04 — Cài model vào project `models/faster-whisper`

- Thêm `scripts/download_models.py` tải `tiny` + `small` từ Hugging Face vào repo.
- Thêm `src/paths.py` với `MODELS_DIR`.
- Cập nhật `transcribe_mic.py` / `check_gpu.py` / `setup_gpu.ps1` dùng `download_root` local.
- Cập nhật docs + `models/README.md`; gitignore giữ `models/README.md`, bỏ qua weight files.

## 2026-11-04 — Bootstrap RealtimeSTT + faster-whisper (NVIDIA GPU)

- Tạo repo `transcript-buddy` trống → setup môi trường Python 3.12 (`.venv`).
- Cài PyTorch / torchaudio **cu128** (bắt buộc cho RTX 5060 Ti / Blackwell sm_120).
- Cài `RealtimeSTT[faster-whisper]` + `nvidia-cublas-cu12` / `cudnn` / `cuda-runtime` cho CTranslate2 trên Windows.
- Thêm `src/cuda_bootstrap.py` để đăng ký DLL CUDA 12 trước khi load model.
- Thêm scripts: `setup_gpu.ps1`, `check_gpu.py`, `transcribe_mic.py`.
- Thêm docs: `docs/setup.md`, `README.md`, `requirements.txt`, `.gitignore`.
- Smoke test: torch CUDA OK, faster-whisper `tiny` trên `cuda`/`float16` OK.
