"""Smoke: agent WS open → PCM → stop → summarize."""

from __future__ import annotations

import asyncio
import json
import sys

import numpy as np
import websockets


async def main() -> int:
    uri = sys.argv[1] if len(sys.argv) > 1 else "ws://127.0.0.1:8100/ws?token=dev-agent-token-change-me"
    async with websockets.connect(uri, max_size=8 * 1024 * 1024) as ws:
        ready = json.loads(await ws.recv())
        print("ready", ready)
        await ws.send(
            json.dumps(
                {
                    "type": "session.open",
                    "session_id": "smoke-1",
                    "model": "tiny",
                    "language": "en",
                }
            )
        )
        while True:
            msg = json.loads(await ws.recv())
            print("evt", msg.get("type"), msg.get("message") or msg.get("model") or "")
            if msg.get("type") == "error":
                print(msg)
                return 1
            if msg.get("type") == "session.opened":
                break

        sr = 16000
        t = np.linspace(0, 1.2, int(sr * 1.2), endpoint=False)
        tone = (0.25 * np.sin(2 * np.pi * 220 * t) * 32767).astype(np.int16).tobytes()
        # add noise bursts so energy VAD trips
        rng = np.random.default_rng(0)
        noise = (rng.normal(0, 0.15, int(sr * 1.2)) * 32767).astype(np.int16).tobytes()
        mixed = bytearray()
        for i in range(0, len(tone), 2):
            # average tone+noise roughly
            v = int.from_bytes(tone[i : i + 2], "little", signed=True) + int.from_bytes(
                noise[i : i + 2], "little", signed=True
            )
            v = max(-32768, min(32767, v))
            mixed += int(v).to_bytes(2, "little", signed=True)
        silence = np.zeros(int(sr * 1.0), dtype=np.int16).tobytes()
        chunk = int(sr * 0.04) * 2
        for blob in (bytes(mixed), silence):
            for i in range(0, len(blob), chunk):
                await ws.send(blob[i : i + chunk])
                await asyncio.sleep(0.005)

        await ws.send(json.dumps({"type": "session.stop"}))
        while True:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=90))
            print("evt", msg.get("type"))
            if msg.get("type") == "summary.done":
                print("SUMMARY_OK", (msg.get("summary") or "")[:300])
                print("TRANSCRIPT", msg.get("transcript"))
                break
            if msg.get("type") == "error":
                print("ERR", msg)
                return 1
        await ws.send(json.dumps({"type": "session.close"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
