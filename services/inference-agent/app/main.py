from __future__ import annotations

import json
import logging
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Ensure repo src/ is importable for cuda_bootstrap
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from cuda_bootstrap import ensure_cuda_dlls  # noqa: E402

ensure_cuda_dlls()

from .config import (  # noqa: E402
    AGENT_TOKEN,
    DEVICE,
    HOST,
    PORT,
    PRELOAD_MODELS,
)
from .models_catalog import list_local_models  # noqa: E402
from .stt_engine import POOL  # noqa: E402
from .stt_session import SttSession  # noqa: E402
from .summarize import ollama_alive, summarize_transcript  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("inference-agent")


def _check_token(authorization: str | None = None, token: str | None = None) -> None:
    provided = token
    if authorization and authorization.lower().startswith("bearer "):
        provided = authorization.split(" ", 1)[1].strip()
    if not provided or provided != AGENT_TOKEN:
        raise HTTPException(status_code=401, detail="invalid agent token")


def _preload_available(names: list[str]) -> list[str]:
    available = {m["id"] for m in list_local_models()}
    to_load = [n for n in names if n in available]
    missing = [n for n in names if n not in available]
    if missing:
        log.warning("skip preload (not on disk): %s", missing)
    if not to_load:
        return []
    log.info("Preloading Whisper on %s: %s", DEVICE, to_load)
    return POOL.preload(to_load)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Start Whisper inference backend on AGENT_PORT, optionally preload models."""
    log.info(
        "Whisper inference backend binding %s:%s (device=%s)",
        HOST,
        PORT,
        DEVICE,
    )
    if PRELOAD_MODELS:
        try:
            loaded = _preload_available(PRELOAD_MODELS)
            log.info("Preloaded models: %s", loaded)
        except Exception:
            log.exception("preload failed — server still listens; models load on demand")
    yield
    log.info("Whisper inference backend shutting down")


app = FastAPI(
    title="transcript-buddy whisper-inference-backend",
    version="0.2.0",
    lifespan=lifespan,
)


class WarmupBody(BaseModel):
    models: list[str] = Field(default_factory=list)


class SummarizeBody(BaseModel):
    transcript: str = ""
    model: str | None = None


@app.get("/health")
async def health():
    models = list_local_models()
    ids = [m["id"] for m in models]
    return {
        "ok": True,
        "service": "whisper-inference-backend",
        "host": HOST,
        "port": PORT,
        "device": DEVICE,
        "models": len(models),
        "model_ids": ids,
        "models_on_disk": ids,
        "models_loaded": POOL.loaded(),
        "ollama": await ollama_alive(),
        "ws": f"ws://<tailscale-ip>:{PORT}/ws",
    }


@app.get("/ready")
async def ready():
    """Ready when HTTP is up. If PRELOAD_MODELS set, those models must be loaded."""
    loaded = set(POOL.loaded())
    required = set(PRELOAD_MODELS) & {m["id"] for m in list_local_models()}
    warm = required.issubset(loaded) if required else True
    return {
        "ready": warm,
        "port": PORT,
        "required": sorted(required),
        "loaded": sorted(loaded),
    }


@app.get("/models")
async def models(authorization: str | None = Header(default=None)):
    _check_token(authorization=authorization)
    return {
        "models": list_local_models(),
        "loaded": POOL.loaded(),
    }


@app.post("/warmup")
async def warmup(body: WarmupBody, authorization: str | None = Header(default=None)):
    """Load Whisper models into GPU via HTTP (port control plane)."""
    _check_token(authorization=authorization)
    names = body.models or PRELOAD_MODELS or ["tiny"]
    try:
        loaded = _preload_available(names)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"loaded": loaded, "all_loaded": POOL.loaded()}


@app.post("/summarize")
async def summarize(body: SummarizeBody, authorization: str | None = Header(default=None)):
    """HTTP fallback khi WebSocket agent bị đứt (keepalive timeout)."""
    _check_token(authorization=authorization)
    try:
        summary = await summarize_transcript(body.transcript, model=body.model)
    except Exception as exc:
        log.exception("HTTP summarize failed")
        raise HTTPException(status_code=502, detail=f"summarize failed: {exc}") from exc
    return {"transcript": body.transcript, "summary": summary}


@app.websocket("/ws")
async def agent_ws(websocket: WebSocket):
    """Data plane: JSON control + binary PCM @ 16 kHz mono s16le."""
    token = websocket.query_params.get("token")
    auth = websocket.headers.get("authorization")
    try:
        _check_token(authorization=auth, token=token)
    except HTTPException:
        await websocket.close(code=4401)
        return

    await websocket.accept()
    session: SttSession | None = None

    async def emit(event: dict[str, Any]) -> None:
        await websocket.send_text(json.dumps(event, ensure_ascii=False))

    await emit({"type": "agent.ready", "port": PORT, "loaded": POOL.loaded()})

    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break

            if "bytes" in message and message["bytes"] is not None:
                if session is None:
                    continue
                # Không await GPU ở đây — chỉ enqueue để WS còn xử lý ping/pong
                await session.enqueue_pcm(message["bytes"])
                continue

            text = message.get("text")
            if not text:
                continue
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                await emit({"type": "error", "message": "invalid json"})
                continue

            msg_type = data.get("type")
            if msg_type == "models.list":
                await emit(
                    {
                        "type": "models",
                        "models": list_local_models(),
                        "loaded": POOL.loaded(),
                    }
                )
                continue

            if msg_type == "session.open":
                if session is not None:
                    await emit({"type": "error", "message": "session already open"})
                    continue
                model = data.get("model") or "small"
                language = data.get("language")
                sid = data.get("session_id") or str(uuid.uuid4())
                try:
                    session = SttSession.create(
                        session_id=sid,
                        model=model,
                        emit=emit,
                        language=language,
                    )
                except Exception as exc:
                    log.exception("session.open failed")
                    await emit({"type": "error", "message": str(exc)})
                    continue
                await emit(
                    {
                        "type": "session.opened",
                        "session_id": sid,
                        "model": session.model,
                        "realtime_model": session.realtime_model,
                        "loaded": POOL.loaded(),
                    }
                )
                continue

            if msg_type == "session.stop":
                if session is None:
                    await emit({"type": "error", "message": "no active session"})
                    continue
                do_summary = bool(data.get("summarize", False))
                transcript = await session.stop_and_flush()
                if not do_summary:
                    await emit(
                        {
                            "type": "session.stopped",
                            "session_id": session.session_id,
                            "transcript": transcript,
                        }
                    )
                    continue
                try:
                    summary = await summarize_transcript(transcript)
                    await emit(
                        {
                            "type": "summary.done",
                            "session_id": session.session_id,
                            "transcript": transcript,
                            "summary": summary,
                        }
                    )
                except Exception as exc:
                    log.exception("summarize failed")
                    await emit(
                        {
                            "type": "error",
                            "message": f"summarize failed: {exc}",
                            "transcript": transcript,
                        }
                    )
                continue

            if msg_type == "session.summarize":
                if session is None:
                    await emit({"type": "error", "message": "no active session"})
                    continue
                transcript = "\n".join(session.finals).strip()
                if not transcript:
                    transcript = await session.stop_and_flush()
                try:
                    summary = await summarize_transcript(transcript)
                    await emit(
                        {
                            "type": "summary.done",
                            "session_id": session.session_id,
                            "transcript": transcript,
                            "summary": summary,
                        }
                    )
                except Exception as exc:
                    log.exception("summarize failed")
                    await emit(
                        {
                            "type": "error",
                            "message": f"summarize failed: {exc}",
                            "transcript": transcript,
                        }
                    )
                continue

            if msg_type == "session.close":
                if session is not None:
                    await session.stop_and_flush()
                    sid = session.session_id
                    session = None
                    await emit({"type": "session.closed", "session_id": sid})
                continue

            await emit({"type": "error", "message": f"unknown type: {msg_type}"})
    except WebSocketDisconnect:
        log.info("client disconnected")
    finally:
        if session is not None:
            try:
                await session.stop_and_flush()
            except Exception:
                pass


@app.exception_handler(Exception)
async def on_error(_, exc: Exception):
    log.exception("unhandled")
    return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


def main() -> None:
    import uvicorn

    log.info("Starting whisper inference backend on %s:%s", HOST, PORT)
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=False)


if __name__ == "__main__":
    main()
