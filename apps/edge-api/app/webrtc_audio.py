from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

import av
import numpy as np
from aiortc import MediaStreamTrack

log = logging.getLogger("edge.webrtc")

PcmSink = Callable[[bytes], Awaitable[None]]


async def pump_audio_track(track: MediaStreamTrack, sink: PcmSink) -> None:
    """Decode inbound WebRTC audio → 16 kHz mono s16le PCM."""
    resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
    try:
        while True:
            frame = await track.recv()
            frames = resampler.resample(frame)
            if not isinstance(frames, list):
                frames = [frames]
            for out in frames:
                if out is None:
                    continue
                # out.planes[0] is packed s16 mono
                arr = out.to_ndarray()
                if arr.ndim > 1:
                    arr = arr.reshape(-1)
                pcm = np.asarray(arr, dtype=np.int16).tobytes()
                if pcm:
                    await sink(pcm)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        # MediaStreamError when track ends
        log.info("audio pump stopped: %s", exc)
