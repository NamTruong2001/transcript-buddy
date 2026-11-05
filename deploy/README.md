# Deploy on new-home-server (Linux)

Topology:

- This host runs `frontend` + `edge-api` (Docker / Dokploy)
- Windows `pc` (`100.65.100.110`) runs Whisper agent (`TranscriptWhisper` service) + Ollama

## Dokploy (đang dùng)

- Project: **Transcript Buddy**
- Compose: `transcript-buddy` — source GitHub `NamTruong2001/transcript-buddy` (`main`), file `./docker-compose.yml`
- Env Dokploy: `AGENT_URL=ws://100.65.100.110:8100/ws`, `AGENT_TOKEN=...`

| Service | URL (Tailscale) |
| --- | --- |
| UI (HTTPS — dùng cái này trên điện thoại) | https://new-home-server.tailae2496.ts.net:5180 |
| UI (HTTP local trên server) | http://127.0.0.1:5180 (Docker bind localhost; Tailscale Serve proxy HTTPS) |
| Edge API | http://127.0.0.1:8010 trên server / via UI `/api/` |

> Mic/`getUserMedia` chỉ hoạt động trên **secure context** (HTTPS hoặc localhost).  
> HTTPS được expose bằng `tailscale serve --https=5180` trên `new-home-server`.

Redeploy: Dokploy UI → Deploy, hoặc API `compose.deploy` với `composeId` của service.

## 1) Windows GPU agent

```powershell
cd D:\code\transcript-buddy\services\inference-agent\service
.\status.ps1
# nếu dừng: .\start.ps1
# warmup model: POST http://127.0.0.1:8100/warmup  Authorization: Bearer <token>
```

Health: `http://100.65.100.110:8100/health`

## 2) Linux compose (thủ công, không qua Dokploy)

Repo root (Dokploy cũng dùng file này):

```bash
cp deploy/.env.example .env
# edit AGENT_TOKEN to match Windows
docker compose up -d --build
```

## E2E từ Windows

```powershell
.\.venv\Scripts\python.exe scripts\local_e2e.py --edge http://100.116.37.109:8010 --agent-ws ws://127.0.0.1:8100/ws --model tiny
```

## Notes

- Browser nên nằm trên Tailscale mesh (phase 1, chưa TURN).
- Nếu WebRTC ICE fail qua Docker bridge, cân nhắc `network_mode: host` cho edge.
