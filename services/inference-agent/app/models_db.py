"""SQLite nhỏ: danh sách STT model (bật/tắt, sync từ disk) — UI đọc qua API, không cần rebuild web."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import MODELS_DB_PATH
from .models_catalog import list_local_models


def _connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or MODELS_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path | None = None) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS stt_models (
                id TEXT PRIMARY KEY,
                path TEXT NOT NULL,
                size_mb REAL NOT NULL DEFAULT 0,
                enabled INTEGER NOT NULL DEFAULT 1,
                sort_order INTEGER NOT NULL DEFAULT 100,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sync_from_disk(db_path: Path | None = None) -> list[dict[str, Any]]:
    """Quét models/faster-whisper và upsert vào DB. Model biến mất khỏi disk → enabled=0."""
    init_db(db_path)
    scanned = list_local_models()
    found_ids = {m["id"] for m in scanned}
    now = _now()
    # thứ tự ưu tiên hiển thị
    order_map = {
        "tiny": 10,
        "tiny.en": 11,
        "base": 20,
        "base.en": 21,
        "small": 30,
        "small.en": 31,
        "medium": 40,
        "medium.en": 41,
        "large-v3-turbo": 50,
        "large-v2": 60,
        "large-v3": 70,
    }

    with _connect(db_path) as conn:
        for m in scanned:
            mid = m["id"]
            sort_order = order_map.get(mid, 100)
            conn.execute(
                """
                INSERT INTO stt_models (id, path, size_mb, enabled, sort_order, updated_at)
                VALUES (?, ?, ?, 1, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    path = excluded.path,
                    size_mb = excluded.size_mb,
                    enabled = 1,
                    sort_order = excluded.sort_order,
                    updated_at = excluded.updated_at
                """,
                (mid, m["path"], float(m["size_mb"]), sort_order, now),
            )
        # ẩn model không còn trên disk
        if found_ids:
            placeholders = ",".join("?" for _ in found_ids)
            conn.execute(
                f"UPDATE stt_models SET enabled = 0, updated_at = ? WHERE id NOT IN ({placeholders})",
                [now, *found_ids],
            )
        else:
            conn.execute("UPDATE stt_models SET enabled = 0, updated_at = ?", (now,))
        conn.commit()
    return list_enabled_models(db_path)


def list_enabled_models(db_path: Path | None = None) -> list[dict[str, Any]]:
    init_db(db_path)
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, path, size_mb, enabled, sort_order, updated_at
            FROM stt_models
            WHERE enabled = 1
            ORDER BY sort_order ASC, id ASC
            """
        ).fetchall()
    return [
        {
            "id": r["id"],
            "path": r["path"],
            "size_mb": r["size_mb"],
            "enabled": bool(r["enabled"]),
            "sort_order": r["sort_order"],
            "updated_at": r["updated_at"],
        }
        for r in rows
    ]


def list_all_models(db_path: Path | None = None) -> list[dict[str, Any]]:
    init_db(db_path)
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, path, size_mb, enabled, sort_order, updated_at
            FROM stt_models
            ORDER BY sort_order ASC, id ASC
            """
        ).fetchall()
    return [
        {
            "id": r["id"],
            "path": r["path"],
            "size_mb": r["size_mb"],
            "enabled": bool(r["enabled"]),
            "sort_order": r["sort_order"],
            "updated_at": r["updated_at"],
        }
        for r in rows
    ]


def set_model_enabled(model_id: str, enabled: bool, db_path: Path | None = None) -> dict[str, Any] | None:
    init_db(db_path)
    with _connect(db_path) as conn:
        cur = conn.execute(
            "UPDATE stt_models SET enabled = ?, updated_at = ? WHERE id = ?",
            (1 if enabled else 0, _now(), model_id),
        )
        conn.commit()
        if cur.rowcount == 0:
            return None
        row = conn.execute(
            "SELECT id, path, size_mb, enabled, sort_order, updated_at FROM stt_models WHERE id = ?",
            (model_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "path": row["path"],
        "size_mb": row["size_mb"],
        "enabled": bool(row["enabled"]),
        "sort_order": row["sort_order"],
        "updated_at": row["updated_at"],
    }
