"""Local E2E validation: edge HTTP + agent WS STT + Ollama summarize.

Usage:
  .\\.venv\\Scripts\\python.exe scripts\\local_e2e.py
  .\\.venv\\Scripts\\python.exe scripts\\local_e2e.py --edge http://127.0.0.1:8001 --agent-ws ws://127.0.0.1:8100/ws
"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import sys
import wave
from pathlib import Path

import httpx
import numpy as np
import websockets

ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--edge", default="http://127.0.0.1:8001")
    p.add_argument("--agent-ws", default="ws://127.0.0.1:8100/ws")
    p.add_argument("--token", default="dev-agent-token-change-me")
    p.add_argument("--model", default="tiny")
    return p.parse_args()


def make_speechish_pcm(seconds: float = 2.5, sr: int = 16000) -> bytes:
    """Synthetic voiced frames (formant-ish) loud enough for energy VAD."""
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    # vowel-like mix + amplitude envelope
    sig = (
        0.45 * np.sin(2 * np.pi * 180 * t)
        + 0.25 * np.sin(2 * np.pi * 360 * t)
        + 0.15 * np.sin(2 * np.pi * 720 * t)
    )
    env = np.clip(np.sin(np.pi * t / seconds) * 1.4, 0, 1)
    audio = (sig * env * 28000).astype(np.int16)
    # pad silence for end-of-utterance
    silence = np.zeros(int(sr * 1.2), dtype=np.int16)
    return np.concatenate([audio, silence]).tobytes()


async def load_or_download_sample() -> bytes:
    """Prefer a real speech sample if downloadable; else synthetic."""
    cache = ROOT / "models" / "sample_en_16k.wav"
    if cache.exists():
        with wave.open(str(cache), "rb") as wf:
            assert wf.getframerate() == 16000
            assert wf.getnchannels() == 1
            pcm = wf.readframes(wf.getnframes())
            return pcm + np.zeros(16000, dtype=np.int16).tobytes()

    url = "https://github.com/openai/whisper/raw/main/tests/jfk.flac"
    try:
        import av

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.content
        container = av.open(io.BytesIO(data))
        resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
        chunks: list[bytes] = []
        for frame in container.decode(audio=0):
            for out in resampler.resample(frame):
                arr = out.to_ndarray().reshape(-1).astype(np.int16)
                chunks.append(arr.tobytes())
        pcm = b"".join(chunks)
        # cache as wav
        cache.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(cache), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(pcm)
        print(f"[ok] downloaded speech sample -> {cache} ({len(pcm)} bytes)")
        return pcm + np.zeros(int(16000 * 1.0), dtype=np.int16).tobytes()
    except Exception as exc:
        print(f"[warn] speech sample unavailable ({exc}); using synthetic PCM")
        return make_speechish_pcm()


async def check_edge(edge: str) -> None:
    async with httpx.AsyncClient(timeout=30.0) as client:
        health = (await client.get(f"{edge}/api/health")).json()
        assert health.get("ok") is True, health
        assert health.get("agent", {}).get("ollama") is True, health
        models = (await client.get(f"{edge}/api/models")).json()["models"]
        ids = [m["id"] for m in models]
        assert "tiny" in ids and "small" in ids, ids
        body = {"model": "tiny", "language": "en"}
        created = (await client.post(f"{edge}/api/sessions", json=body)).json()
        assert "session_id" in created, created
        sid = created["session_id"]
        # stop immediately (empty transcript summarize path)
        stopped = await client.post(f"{edge}/api/sessions/{sid}/stop")
        assert stopped.status_code == 200, await stopped.aread()
        data = stopped.json()
        assert "summary" in data, data
        await client.delete(f"{edge}/api/sessions/{sid}")
        print("[ok] edge health/models/session/stop/summarize")


async def check_agent_stt(agent_ws: str, token: str, model: str) -> None:
    uri = f"{agent_ws}?token={token}"
    pcm = await load_or_download_sample()
    async with websockets.connect(uri, max_size=8 * 1024 * 1024) as ws:
        ready = json.loads(await ws.recv())
        assert ready.get("type") == "agent.ready", ready
        await ws.send(
            json.dumps(
                {
                    "type": "session.open",
                    "session_id": "local-e2e",
                    "model": model,
                    "language": "en",
                }
            )
        )
        while True:
            msg = json.loads(await ws.recv())
            if msg.get("type") == "error":
                raise AssertionError(msg)
            if msg.get("type") == "session.opened":
                print("[ok] agent session.opened", msg.get("model"), msg.get("realtime_model"))
                break

        chunk = int(16000 * 0.04) * 2
        for i in range(0, len(pcm), chunk):
            await ws.send(pcm[i : i + chunk])
            await asyncio.sleep(0.002)

        await ws.send(json.dumps({"type": "session.stop"}))
        got_summary = False
        transcript = ""
        while True:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=120))
            t = msg.get("type")
            if t == "transcript.partial":
                print("[partial]", msg.get("text"))
            elif t == "transcript.final":
                print("[final]", msg.get("text"))
            elif t == "summary.done":
                transcript = msg.get("transcript") or ""
                summary = msg.get("summary") or ""
                print("[ok] summary.done")
                print("TRANSCRIPT:", transcript[:300] or "(empty)")
                print("SUMMARY:", summary[:400])
                got_summary = True
                break
            elif t == "error":
                raise AssertionError(msg)
        assert got_summary
        await ws.send(json.dumps({"type": "session.close"}))
        # If real JFK sample loaded, expect some transcript text
        sample = ROOT / "models" / "sample_en_16k.wav"
        if sample.exists() and not transcript.strip():
            raise AssertionError("expected non-empty transcript for JFK sample")


async def main() -> int:
    args = parse_args()
    print("Edge:", args.edge)
    print("Agent:", args.agent_ws)
    await check_edge(args.edge)
    await check_agent_stt(args.agent_ws, args.token, args.model)
    print("\nALL LOCAL E2E CHECKS PASSED")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except Exception as exc:
        print("FAILED:", exc, file=sys.stderr)
        raise
