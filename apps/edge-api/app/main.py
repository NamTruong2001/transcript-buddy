from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .agent_client import (
    agent_health,
    agent_list_models,
    agent_list_ollama_models,
    agent_warmup,
)
from .config import CORS_ORIGINS, HOST, PORT
from .sessions import MANAGER

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("edge-api")

app = FastAPI(title="transcript-buddy edge-api", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CreateSessionBody(BaseModel):
    model: str = Field(default="small")
    language: str | None = None


class OfferBody(BaseModel):
    sdp: str
    type: str = "offer"


class WarmupBody(BaseModel):
    models: list[str] = Field(default_factory=list)


class StopBody(BaseModel):
    summarize: bool = False
    model: str | None = None


class SummarizeSessionBody(BaseModel):
    model: str | None = None


@app.get("/api/health")
async def health():
    try:
        agent = await agent_health()
        return {"ok": True, "edge": True, "agent": agent}
    except Exception as exc:
        return {"ok": False, "edge": True, "agent_error": str(exc)}


@app.get("/api/models")
async def models():
    try:
        return {"models": await agent_list_models()}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"agent unreachable: {exc}") from exc


@app.get("/api/ollama/models")
async def ollama_models():
    try:
        return await agent_list_ollama_models()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"ollama list failed: {exc}") from exc


@app.post("/api/warmup")
async def warmup(body: WarmupBody):
    """Preload Whisper model(s) on the Windows agent GPU (manual / UI button)."""
    names = [m.strip() for m in body.models if m and m.strip()]
    if not names:
        raise HTTPException(status_code=400, detail="models required")
    try:
        return await agent_warmup(names)
    except Exception as exc:
        log.exception("warmup failed")
        raise HTTPException(status_code=502, detail=f"warmup failed: {exc}") from exc


@app.post("/api/sessions")
async def create_session(body: CreateSessionBody):
    try:
        session = await MANAGER.create(model=body.model, language=body.language)
    except Exception as exc:
        log.exception("create session failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {
        "session_id": session.id,
        "model": session.model,
        "state": session.state,
    }


@app.post("/api/sessions/{session_id}/webrtc/offer")
async def webrtc_offer(session_id: str, body: OfferBody):
    session = MANAGER.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")
    try:
        answer = await MANAGER.attach_webrtc(session, body.sdp, body.type)
    except Exception as exc:
        log.exception("webrtc offer failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return answer


@app.post("/api/sessions/{session_id}/stop")
async def stop_session(session_id: str, body: StopBody = StopBody()):
    session = MANAGER.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")
    want_summary = bool(body.summarize)
    llm_model = body.model
    try:
        fallback = await MANAGER.stop(session, summarize=want_summary, model=llm_model)
    except Exception as exc:
        log.exception("stop failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    event = fallback
    if event is None:
        expect = "summary.done" if want_summary else "session.stopped"
        try:
            while True:
                evt = await asyncio_wait_event(session, timeout=180.0)
                if evt.get("type") == expect:
                    event = evt
                    break
                if evt.get("type") == "error" and want_summary and "summarize" in (
                    evt.get("message") or ""
                ):
                    raise HTTPException(status_code=502, detail=evt.get("message"))
                # ignore other transcript events while waiting
                if evt.get("type") in {"transcript.partial", "transcript.final"}:
                    continue
                if evt.get("type") == "summary.done" and want_summary:
                    event = evt
                    break
                if evt.get("type") == "session.stopped" and not want_summary:
                    event = evt
                    break
        except TimeoutError as exc:
            if want_summary:
                log.warning("summary.done timeout; HTTP fallback")
                try:
                    from .agent_client import agent_summarize

                    result = await agent_summarize(
                        "\n".join(session.finals).strip(),
                        model=llm_model,
                    )
                    event = {
                        "transcript": result.get("transcript") or "\n".join(session.finals),
                        "summary": result.get("summary") or "",
                        "model": llm_model,
                    }
                except Exception as fallback_exc:
                    raise HTTPException(status_code=504, detail="summarize timeout") from fallback_exc
            else:
                event = {
                    "transcript": "\n".join(session.finals),
                    "summary": "",
                }
    return {
        "session_id": session_id,
        "transcript": (event or {}).get("transcript") or "\n".join(session.finals),
        "summary": (event or {}).get("summary") or session.summary,
        "finals": session.finals,
        "summarized": want_summary,
        "model": (event or {}).get("model") or llm_model,
    }


@app.post("/api/sessions/{session_id}/summarize")
async def summarize_session(session_id: str, body: SummarizeSessionBody = SummarizeSessionBody()):
    session = MANAGER.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")
    try:
        fallback = await MANAGER.summarize(session, model=body.model)
    except Exception as exc:
        log.exception("summarize failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    event = fallback
    if event is None:
        try:
            while True:
                evt = await asyncio_wait_event(session, timeout=180.0)
                if evt.get("type") == "summary.done":
                    event = evt
                    break
                if evt.get("type") == "error" and "summarize" in (evt.get("message") or ""):
                    raise HTTPException(status_code=502, detail=evt.get("message"))
        except TimeoutError as exc:
            raise HTTPException(status_code=504, detail="summarize timeout") from exc
    return {
        "session_id": session_id,
        "transcript": (event or {}).get("transcript") or "\n".join(session.finals),
        "summary": (event or {}).get("summary") or session.summary,
        "finals": session.finals,
        "model": (event or {}).get("model") or body.model,
    }


async def asyncio_wait_event(session, timeout: float) -> dict[str, Any]:
    return await asyncio.wait_for(session.queue.get(), timeout=timeout)


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    session = MANAGER.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")
    await MANAGER.close(session)
    return {"ok": True}


@app.websocket("/api/sessions/{session_id}/events")
async def session_events(websocket: WebSocket, session_id: str):
    session = MANAGER.get(session_id)
    if not session:
        await websocket.close(code=4404)
        return
    await websocket.accept()
    session.event_clients.append(websocket)
    await websocket.send_json({"type": "status", "state": session.state, "session_id": session_id})
    try:
        while True:
            # keep alive / ignore client pings
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in session.event_clients:
            session.event_clients.remove(websocket)


def main() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=False)


if __name__ == "__main__":
    main()
