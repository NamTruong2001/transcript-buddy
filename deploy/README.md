# Deploy on new-home-server (Linux)

Topology:

- This host runs `frontend` + `edge-api` (Docker)
- Windows `pc` (`100.65.100.110`) runs `inference-agent` + Ollama

## 1) Windows GPU agent

```powershell
cd D:\code\transcript-buddy\services\inference-agent
$env:AGENT_TOKEN = "dev-agent-token-change-me"
.\run.ps1
```

Health: `http://100.65.100.110:8100/health`

## 2) Linux compose

```bash
cd /path/to/transcript-buddy/deploy
cp .env.example .env
# edit AGENT_TOKEN to match Windows
docker compose up -d --build
```

UI: `http://new-home-server:5173` (Tailscale MagicDNS) or `http://100.116.37.109:5173`

## Notes

- Browser should be on Tailscale mesh (phase 1, no TURN).
- If WebRTC ICE fails behind Docker bridge, set `EDGE_NETWORK_MODE=host` and adjust ports.
