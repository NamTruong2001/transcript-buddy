from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .agent_client import agent_health, agent_list_models
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
async def stop_session(session_id: str):
    session = MANAGER.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")
    await MANAGER.stop(session)
    # wait briefly for summary.done via queue
    summary = None
    try:
        while True:
            event = await asyncio_wait_event(session, timeout=90.0)
            if event.get("type") == "summary.done":
                summary = event
                break
            if event.get("type") == "error" and "summarize" in (event.get("message") or ""):
                raise HTTPException(status_code=502, detail=event.get("message"))
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail="summarize timeout") from exc
    return {
        "session_id": session_id,
        "transcript": summary.get("transcript") if summary else "\n".join(session.finals),
        "summary": summary.get("summary") if summary else session.summary,
        "finals": session.finals,
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
