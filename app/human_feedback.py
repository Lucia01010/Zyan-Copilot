"""12-Factor 原则 3：人机协同工具化。

人工修改 AI 建议回复不再是前端自由文本，而是结构化"人类工具调用"事件：
human_feedback 表与业务数据同库持久化，记录原始建议、人工修订与会话归属，
补全"AI 建议 → 人工介入 → 最终发送"的审计链。
"""
from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

_SCHEMA = "CREATE TABLE IF NOT EXISTS human_feedback (feedback_id TEXT PRIMARY KEY, conversation_id TEXT, original_reply TEXT NOT NULL, edited_reply TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"

_COLUMNS = "feedback_id, conversation_id, original_reply, edited_reply, created_at"


@contextmanager
def _feedback_db(db_path: str | Path) -> Iterator[sqlite3.Connection]:
    """显式管理连接生命周期：事务提交后关闭连接（Windows 下文件锁随关闭释放）。"""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(_SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def _to_dict(row: tuple) -> dict[str, Any]:
    return {"feedback_id": row[0], "conversation_id": row[1], "original_reply": row[2], "edited_reply": row[3], "created_at": row[4]}


def record_feedback(db_path: str | Path, conversation_id: str | None, original_reply: str, edited_reply: str) -> str:
    """记录一次人工修订事件，返回 feedback_id。"""
    if not str(original_reply).strip():
        raise ValueError("original_reply is required")
    if not str(edited_reply).strip():
        raise ValueError("edited_reply is required")
    feedback_id = f"fb_{uuid.uuid4().hex[:12]}"
    with _feedback_db(db_path) as conn:
        conn.execute("INSERT INTO human_feedback (feedback_id, conversation_id, original_reply, edited_reply) VALUES (?, ?, ?, ?)", (feedback_id, conversation_id, original_reply, edited_reply))
    return feedback_id


def list_feedback(db_path: str | Path, conversation_id: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    """按时间倒序查询人工修订记录；指定会话时只返回该会话。"""
    query = f"SELECT {_COLUMNS} FROM human_feedback"
    params: list[Any] = []
    if conversation_id:
        query += " WHERE conversation_id = ?"
        params.append(conversation_id)
    query += " ORDER BY created_at DESC, rowid DESC LIMIT ?"
    params.append(max(1, min(limit, 100)))
    with _feedback_db(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [_to_dict(row) for row in rows]
