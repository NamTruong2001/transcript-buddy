from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from aiortc import RTCPeerConnection, RTCSessionDescription

from .agent_client import SessionAgentLink, agent_summarize
from .webrtc_audio import pump_audio_track

log = logging.getLogger("edge.sessions")


@dataclass
class Session:
    id: str
    model: str
    language: str | None = None
    agent: SessionAgentLink | None = None
    pc: RTCPeerConnection | None = None
    audio_task: asyncio.Task | None = None
    event_clients: list[Any] = field(default_factory=list)
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    state: str = "created"
    finals: list[str] = field(default_factory=list)
    partial: str = ""
    summary: str = ""


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    async def create(self, model: str, language: str | None = None) -> Session:
        sid = str(uuid.uuid4())
        session = Session(id=sid, model=model, language=language)
        self._sessions[sid] = session

        async def on_event(event: dict[str, Any]) -> None:
            et = event.get("type")
            if et == "transcript.partial":
                session.partial = event.get("text") or ""
            elif et == "transcript.final":
                text = event.get("text") or ""
                if text:
                    session.finals.append(text)
                session.partial = ""
            elif et == "summary.done":
                session.summary = event.get("summary") or ""
                session.state = "summarized"
            await session.queue.put(event)
            dead = []
            for ws in session.event_clients:
                try:
                    await ws.send_json(event)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                if ws in session.event_clients:
                    session.event_clients.remove(ws)

        link = SessionAgentLink(on_event)
        session.agent = link
        opened = await link.connect_and_open(sid, model, language)
        session.state = "ready"
        log.info("session %s opened model=%s realtime=%s", sid, model, opened.get("realtime_model"))
        return session

    async def attach_webrtc(self, session: Session, offer_sdp: str, offer_type: str = "offer") -> dict:
        if session.pc is not None:
            await session.pc.close()

        pc = RTCPeerConnection()
        session.pc = pc

        @pc.on("track")
        def on_track(track):
            if track.kind != "audio":
                return
            if session.audio_task:
                session.audio_task.cancel()

            async def sink(pcm: bytes) -> None:
                if session.agent:
                    await session.agent.send_pcm(pcm)

            session.audio_task = asyncio.create_task(pump_audio_track(track, sink))
            session.state = "recording"

        await pc.setRemoteDescription(RTCSessionDescription(sdp=offer_sdp, type=offer_type))
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        # wait briefly for ICE gathering
        for _ in range(50):
            if pc.iceGatheringState == "complete":
                break
            await asyncio.sleep(0.05)
        assert pc.localDescription is not None
        return {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}

    async def stop(self, session: Session) -> dict[str, Any] | None:
        """Stop recording and request summary.

        Returns a summary.done-like dict when HTTP fallback was used; otherwise None
        and the caller should wait for the agent WebSocket summary.done event.
        """
        session.state = "summarizing"
        if session.audio_task:
            session.audio_task.cancel()
            session.audio_task = None
        if session.pc:
            try:
                await session.pc.close()
            except Exception:
                pass
            session.pc = None

        transcript = "\n".join(session.finals).strip()
        if session.agent:
            try:
                await session.agent.stop()
                return None
            except Exception as exc:
                log.warning("agent WS stop failed (%s); HTTP summarize fallback", exc)

        # Fallback: WS đã chết (keepalive timeout) → tóm tắt qua HTTP với finals đã có
        try:
            result = await agent_summarize(transcript)
        except Exception as exc:
            log.exception("HTTP summarize fallback failed")
            raise RuntimeError(f"summarize failed: {exc}") from exc
        summary = result.get("summary") or ""
        session.summary = summary
        session.state = "summarized"
        event = {
            "type": "summary.done",
            "session_id": session.id,
            "transcript": result.get("transcript") or transcript,
            "summary": summary,
        }
        await session.queue.put(event)
        return event

    async def close(self, session: Session) -> None:
        try:
            await self.stop(session)
        except Exception:
            pass
        if session.agent:
            await session.agent.close()
            session.agent = None
        self._sessions.pop(session.id, None)


MANAGER = SessionManager()
