# Whisper inference backend (Windows GPU)

Process riêng trên máy NVIDIA. **Edge Linux chỉ nói chuyện với process này qua port** (Tailscale), không chạy Whisper.

## Port contract

| Port / path | Vai trò |
| --- | --- |
| `8100` TCP | Bind mặc định (`AGENT_HOST`/`AGENT_PORT`) |
| `GET /health` | Service sống + model trên disk + model đã load GPU |
| `GET /ready` | Sẵn sàng nhận session (sau preload nếu có) |
| `GET /models` | Danh sách model local (Bearer token) |
| `POST /warmup` | Load thêm model vào GPU qua HTTP |
| `WS /ws` | Data plane: JSON control + binary PCM 16 kHz |

Ollama (`11434`) là process khác, cũng qua port local — summarize sau `session.stop`.

## Windows Service (công tắc không cần GUI)

Dùng stub C# nhỏ (`TranscriptWhisperSvc.exe`) — không cần NSSM/WinSW.

Cài **một lần** (PowerShell **Run as Administrator**):

```powershell
cd D:\code\transcript-buddy\services\inference-agent\service
# chỉnh token/port trong service.env nếu cần
.\install.ps1
# Nếu CUDA lỗi dưới LocalSystem:
# .\install.ps1 -AsCurrentUser
```

Bật / tắt (không cần GUI — SSH, `sc`, Task Scheduler đều được):

```powershell
.\start.ps1          # ON
.\stop.ps1           # OFF
.\status.ps1

# tương đương:
sc.exe start TranscriptWhisper
sc.exe stop TranscriptWhisper
```

- Auto-start khi boot (`StartType=Automatic`)
- Listen port `8100`
- Log: `services/inference-agent/logs/service-*.log`

Đã kiểm tra trên máy này: service **Running**, `GET /health` → ok.

## Chạy tay (dev)

```powershell
cd D:\code\transcript-buddy\services\inference-agent
$env:AGENT_TOKEN = "dev-agent-token-change-me"
$env:AGENT_PORT = "8100"
$env:PRELOAD_MODELS = ""            # mặc định: không preload lúc boot
# $env:PRELOAD_MODELS = "tiny,small"  # chỉ khi muốn warm GPU ngay khi start service
.\run.ps1
```

```powershell
.\wait_ready.ps1
curl.exe http://127.0.0.1:8100/health
```

Edge Linux kết nối:

```text
AGENT_URL=ws://100.65.100.110:8100/ws
AGENT_TOKEN=dev-agent-token-change-me
```

## Luồng

1. Backend Windows **listen port 8100** (+ preload Whisper nếu cấu hình).
2. Edge gọi `POST /api/sessions` → mở `WS` tới `:8100/ws` → `session.open`.
3. Edge gửi PCM binary; agent trả `transcript.partial` / `transcript.final`.
4. `session.stop` → Ollama `:11434` summarize → `summary.done`.
