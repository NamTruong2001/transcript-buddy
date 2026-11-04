from __future__ import annotations

import httpx

from .config import OLLAMA_MODEL, OLLAMA_TIMEOUT_S, OLLAMA_URL

SYSTEM_PROMPT = (
    "Bạn là trợ lý tóm tắt cuộc nói chuyện. "
    "Hãy tóm tắt ngắn gọn bằng tiếng Việt (hoặc cùng ngôn ngữ với transcript), "
    "dùng markdown: ý chính, điểm nổi bật, và action items nếu có."
)


async def summarize_transcript(transcript: str, model: str | None = None) -> str:
    text = (transcript or "").strip()
    if not text:
        return "_Không có nội dung để tóm tắt._"

    payload = {
        "model": model or OLLAMA_MODEL,
        "stream": False,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Tóm tắt transcript sau:\n\n{text}",
            },
        ],
    }
    async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT_S) as client:
        resp = await client.post(f"{OLLAMA_URL}/api/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()
    return (data.get("message") or {}).get("content") or ""


async def ollama_alive() -> bool:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags")
            return resp.status_code == 200
    except Exception:
        return False
