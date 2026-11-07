from __future__ import annotations

from typing import Any

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
        # qwen3.x thinking làm chậm / đôi khi content rỗng — tắt khi summarize
        "think": False,
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
    msg = data.get("message") or {}
    content = (msg.get("content") or "").strip()
    if not content:
        # một số bản Ollama nhét text vào thinking nếu think không được tôn trọng
        content = (msg.get("thinking") or "").strip()
    return content


async def list_ollama_models() -> list[dict[str, Any]]:
    """Danh sách model đã tải trong Ollama (GET /api/tags)."""
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(f"{OLLAMA_URL}/api/tags")
        resp.raise_for_status()
        data = resp.json()
    out: list[dict[str, Any]] = []
    for m in data.get("models") or []:
        name = m.get("name") or m.get("model")
        if not name:
            continue
        size = int(m.get("size") or 0)
        out.append(
            {
                "id": name,
                "name": name,
                "size_bytes": size,
                "size_gb": round(size / 1e9, 2) if size else 0,
                "modified_at": m.get("modified_at"),
                "family": ((m.get("details") or {}).get("family")),
                "parameter_size": ((m.get("details") or {}).get("parameter_size")),
            }
        )
    out.sort(key=lambda x: x["id"])
    return out


async def ollama_alive() -> bool:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags")
            return resp.status_code == 200
    except Exception:
        return False
