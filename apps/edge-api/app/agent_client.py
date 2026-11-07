from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from websockets.asyncio.client import connect as ws_connect

from .config import AGENT_TOKEN, AGENT_URL

log = logging.getLogger("edge.agent")

EventHandler = Callable[[dict[str, Any]], Awaitable[None]]


def http_base_from_ws(url: str) -> str:
    if url.startswith("wss://"):
        base = "https://" + url[len("wss://") :]
    elif url.startswith("ws://"):
        base = "http://" + url[len("ws://") :]
    else:
        base = url
    if base.endswith("/ws"):
        base = base[: -len("/ws")]
    return base.rstrip("/")


async def agent_health() -> dict[str, Any]:
    base = http_base_from_ws(AGENT_URL)
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(f"{base}/health")
        resp.raise_for_status()
        return resp.json()


async def agent_list_models() -> list[dict[str, Any]]:
    base = http_base_from_ws(AGENT_URL)
    headers = {"Authorization": f"Bearer {AGENT_TOKEN}"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{base}/models", headers=headers)
        resp.raise_for_status()
        return resp.json().get("models") or []


async def agent_summarize(transcript: str, model: str | None = None) -> dict[str, Any]:
    """HTTP fallback when the per-session agent WebSocket is already closed."""
    base = http_base_from_ws(AGENT_URL)
    headers = {"Authorization": f"Bearer {AGENT_TOKEN}"}
    payload: dict[str, Any] = {"transcript": transcript}
    if model:
        payload["model"] = model
    async with httpx.AsyncClient(timeout=180.0) as client:
        resp = await client.post(
            f"{base}/summarize",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()


async def agent_list_ollama_models() -> dict[str, Any]:
    base = http_base_from_ws(AGENT_URL)
    headers = {"Authorization": f"Bearer {AGENT_TOKEN}"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{base}/ollama/models", headers=headers)
        resp.raise_for_status()
        return resp.json()


async def agent_warmup(models: list[str]) -> dict[str, Any]:
    """Load Whisper model(s) into GPU without opening a session."""
    base = http_base_from_ws(AGENT_URL)
    headers = {"Authorization": f"Bearer {AGENT_TOKEN}"}
    async with httpx.AsyncClient(timeout=600.0) as client:
        resp = await client.post(
            f"{base}/warmup",
            headers=headers,
            json={"models": models},
        )
        resp.raise_for_status()
        return resp.json()


class SessionAgentLink:
    """One WebSocket to the Windows inference agent per browser session."""

    def __init__(self, on_event: EventHandler) -> None:
        self._on_event = on_event
        self._ws = None
        self._recv_task: asyncio.Task | None = None
        self._open_future: asyncio.Future | None = None

    @property
    def connected(self) -> bool:
        return self._ws is not None

    async def connect_and_open(
        self,
        session_id: str,
        model: str,
        language: str | None = None,
    ) -> dict[str, Any]:
        url = f"{AGENT_URL}?token={AGENT_TOKEN}"
        log.info("agent connect session=%s", session_id)
        # Tắt client ping: GPU/large-v3 có thể làm agent pong chậm → false "connection lost"
        # TCP/Tailscale vẫn giữ kết nối; agent WS receive loop phải luôn free (PCM queue).
        self._ws = await ws_connect(
            url,
            max_size=8 * 1024 * 1024,
            ping_interval=None,
            close_timeout=5,
        )
        loop = asyncio.get_running_loop()
        self._open_future = loop.create_future()
        self._recv_task = asyncio.create_task(self._recv_loop())
        await self.send_json(
            {
                "type": "session.open",
                "session_id": session_id,
                "model": model,
                "language": language,
            }
        )
        opened = await asyncio.wait_for(self._open_future, timeout=180.0)
        if opened.get("type") == "error":
            raise RuntimeError(opened.get("message") or "session.open failed")
        return opened

    async def _recv_loop(self) -> None:
        assert self._ws is not None
        try:
            async for raw in self._ws:
                if isinstance(raw, bytes):
                    continue
                try:
                    event = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                et = event.get("type")
                if self._open_future and not self._open_future.done():
                    if et in {"session.opened", "error"}:
                        self._open_future.set_result(event)
                await self._on_event(event)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.exception("agent link closed")
            if self._open_future and not self._open_future.done():
                self._open_future.set_exception(exc)
            await self._on_event({"type": "error", "message": "agent connection lost"})

    async def send_json(self, payload: dict[str, Any]) -> None:
        if self._ws is None:
            raise RuntimeError("agent not connected")
        await self._ws.send(json.dumps(payload, ensure_ascii=False))

    async def send_pcm(self, pcm: bytes) -> None:
        if self._ws is None or not pcm:
            return
        await self._ws.send(pcm)

    async def stop(self, *, summarize: bool = False, model: str | None = None) -> None:
        payload: dict[str, Any] = {"type": "session.stop", "summarize": summarize}
        if model:
            payload["model"] = model
        await self.send_json(payload)

    async def request_summarize(self, model: str | None = None) -> None:
        payload: dict[str, Any] = {"type": "session.summarize"}
        if model:
            payload["model"] = model
        await self.send_json(payload)

    async def close(self) -> None:
        try:
            if self._ws is not None:
                try:
                    await self.send_json({"type": "session.close"})
                except Exception:
                    pass
        finally:
            if self._recv_task:
                self._recv_task.cancel()
                self._recv_task = None
            if self._ws is not None:
                await self._ws.close()
                self._ws = None
