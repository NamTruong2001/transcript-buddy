from __future__ import annotations

import os

AGENT_URL = os.environ.get("AGENT_URL", "ws://100.65.100.110:8100/ws")
AGENT_TOKEN = os.environ.get("AGENT_TOKEN", "dev-agent-token-change-me")
HOST = os.environ.get("EDGE_HOST", "0.0.0.0")
PORT = int(os.environ.get("EDGE_PORT", "8000"))
CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://new-home-server:5173,http://100.116.37.109:5173",
    ).split(",")
    if o.strip()
]
