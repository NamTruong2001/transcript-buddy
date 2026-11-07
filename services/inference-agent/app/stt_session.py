from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

import numpy as np

from .config import (
    ENERGY_THRESHOLD,
    MIN_UTTERANCE_S,
    PARTIAL_EVERY_S,
    SAMPLE_RATE,
    SILENCE_END_S,
)
from .models_catalog import list_local_models, resolve_realtime_model
from .stt_engine import POOL

log = logging.getLogger("inference-agent.stt")

EmitFn = Callable[[dict], Awaitable[None]]


@dataclass
class SttSession:
    session_id: str
    model: str
    language: str | None
    emit: EmitFn
    realtime_model: str = "tiny"
    finals: list[str] = field(default_factory=list)
    _pcm: bytearray = field(default_factory=bytearray)
    _utt: bytearray = field(default_factory=bytearray)
    _speaking: bool = False
    _last_voice_ts: float = 0.0
    _last_partial_ts: float = 0.0
    _closed: bool = False
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    # Hàng đợi PCM: nhận WS không chờ GPU → tránh keepalive ping timeout
    _pcm_q: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=400))
    _worker: asyncio.Task | None = None

    @classmethod
    def create(
        cls,
        session_id: str,
        model: str,
        emit: EmitFn,
        language: str | None = None,
    ) -> SttSession:
        available = {m["id"] for m in list_local_models()}
        if model not in available:
            raise ValueError(f"Model '{model}' not installed. Available: {sorted(available)}")
        realtime = resolve_realtime_model(model, available)
        # warm models
        POOL.get(model)
        if realtime != model:
            POOL.get(realtime)
        session = cls(
            session_id=session_id,
            model=model,
            language=language,
            emit=emit,
            realtime_model=realtime,
        )
        session.start_worker()
        return session

    def start_worker(self) -> None:
        if self._worker is None or self._worker.done():
            self._worker = asyncio.create_task(self._run_worker(), name=f"stt-{self.session_id}")

    async def enqueue_pcm(self, pcm: bytes) -> None:
        """Non-blocking from WS receive loop — chỉ đẩy vào queue."""
        if self._closed or not pcm:
            return
        try:
            self._pcm_q.put_nowait(pcm)
        except asyncio.QueueFull:
            # bỏ chunk cũ nhất để theo kịp realtime
            try:
                _ = self._pcm_q.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                self._pcm_q.put_nowait(pcm)
            except asyncio.QueueFull:
                pass

    async def _run_worker(self) -> None:
        try:
            while not self._closed:
                try:
                    pcm = await asyncio.wait_for(self._pcm_q.get(), timeout=0.25)
                    await self._feed_pcm_locked(pcm)
                except asyncio.TimeoutError:
                    # hết tiếng dù không còn PCM mới
                    async with self._lock:
                        if (
                            self._speaking
                            and (time.monotonic() - self._last_voice_ts) >= SILENCE_END_S
                        ):
                            await self._finalize_utterance()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    log.exception("stt worker error")
        except asyncio.CancelledError:
            pass

    def _rms(self, pcm: bytes) -> float:
        if not pcm:
            return 0.0
        audio = np.frombuffer(pcm, dtype=np.int16)
        if audio.size == 0:
            return 0.0
        return float(np.sqrt(np.mean(audio.astype(np.float32) ** 2)))

    def _to_f32(self, pcm: bytes) -> np.ndarray:
        audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        return audio

    async def feed_pcm(self, pcm: bytes) -> None:
        """Tương thích cũ — ưu tiên enqueue_pcm từ WS."""
        await self.enqueue_pcm(pcm)

    async def _feed_pcm_locked(self, pcm: bytes) -> None:
        if self._closed or not pcm:
            return
        async with self._lock:
            now = time.monotonic()
            self._pcm.extend(pcm)
            energy = self._rms(pcm)
            voiced = energy >= ENERGY_THRESHOLD

            if voiced:
                if not self._speaking:
                    self._speaking = True
                    preroll = int(SAMPLE_RATE * 0.3) * 2
                    self._utt = bytearray(self._pcm[-preroll:])
                self._utt.extend(pcm)
                self._last_voice_ts = now
                if now - self._last_partial_ts >= PARTIAL_EVERY_S:
                    self._last_partial_ts = now
                    await self._emit_partial()
            elif self._speaking:
                self._utt.extend(pcm)
                if now - self._last_voice_ts >= SILENCE_END_S:
                    await self._finalize_utterance()

    async def _emit_partial(self) -> None:
        min_bytes = int(SAMPLE_RATE * MIN_UTTERANCE_S) * 2
        if len(self._utt) < min_bytes:
            return
        audio = self._to_f32(bytes(self._utt))
        text = await asyncio.to_thread(
            POOL.transcribe,
            self.realtime_model,
            audio,
            language=self.language,
            beam_size=1,
        )
        if text:
            await self.emit(
                {
                    "type": "transcript.partial",
                    "session_id": self.session_id,
                    "text": text,
                }
            )

    async def _finalize_utterance(self) -> None:
        min_bytes = int(SAMPLE_RATE * MIN_UTTERANCE_S) * 2
        pcm = bytes(self._utt)
        self._utt.clear()
        self._speaking = False
        if len(pcm) < min_bytes:
            return
        audio = self._to_f32(pcm)
        text = await asyncio.to_thread(
            POOL.transcribe,
            self.model,
            audio,
            language=self.language,
            beam_size=3,
        )
        if text:
            self.finals.append(text)
            await self.emit(
                {
                    "type": "transcript.final",
                    "session_id": self.session_id,
                    "text": text,
                    "index": len(self.finals) - 1,
                }
            )

    async def stop_and_flush(self) -> str:
        # rút hết queue rồi finalize
        while True:
            try:
                pcm = self._pcm_q.get_nowait()
            except asyncio.QueueEmpty:
                break
            await self._feed_pcm_locked(pcm)

        async with self._lock:
            if self._speaking and self._utt:
                await self._finalize_utterance()
            self._closed = True

        worker = self._worker
        self._worker = None
        if worker and not worker.done():
            worker.cancel()
            try:
                await worker
            except asyncio.CancelledError:
                pass
        return "\n".join(self.finals).strip()
