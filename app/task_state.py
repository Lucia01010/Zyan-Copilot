"""12-Factor 原则 7：统一执行状态与业务状态。

task 级全局状态持久化到与业务数据相同的 SQLite：
- execution_state 记录"进行到哪一步"（started/context_ready/synthesis_done/completed/failed）；
- business_state_json 记录"处理什么数据"（入参、上下文规模、风险等级、仲裁统计、用量）。
状态全程可观测（GET /api/agent/tasks），进程重启后任务轨迹仍在；演示场景不做断点续传执行。
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

_SCHEMA = "CREATE TABLE IF NOT EXISTS agent_tasks (task_id TEXT PRIMARY KEY, conversation_id TEXT, order_number TEXT, execution_state TEXT NOT NULL, business_state_json TEXT NOT NULL DEFAULT '{}', error TEXT, run_id TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"

_EXECUTION_STATES = ("started", "context_ready", "synthesis_done", "completed", "failed")

_TASK_COLUMNS = "task_id, conversation_id, order_number, execution_state, business_state_json, error, run_id, created_at, updated_at"


@contextmanager
def _task_db(db_path: str | Path) -> Iterator[sqlite3.Connection]:
    """显式管理连接生命周期：事务提交后关闭连接（Windows 下文件锁随关闭释放）。"""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(_SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def _to_dict(row: tuple) -> dict[str, Any]:
    return {"task_id": row[0], "conversation_id": row[1], "order_number": row[2], "execution_state": row[3], "business_state": json.loads(row[4]), "error": row[5], "run_id": row[6], "created_at": row[7], "updated_at": row[8]}


def record_task(db_path: str | Path, task_id: str, conversation_id: str | None, order_number: str | None, execution_state: str, business_state: dict[str, Any] | None = None) -> None:
    """创建任务记录（执行状态与业务状态在同一行）。"""
    with _task_db(db_path) as conn:
        conn.execute("INSERT INTO agent_tasks (task_id, conversation_id, order_number, execution_state, business_state_json, updated_at) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)", (task_id, conversation_id, order_number, execution_state, json.dumps(business_state or {}, ensure_ascii=False, default=str)))


def update_task(db_path: str | Path, task_id: str, execution_state: str, business_state: dict[str, Any] | None = None, error: str | None = None, run_id: str | None = None) -> None:
    """推进执行状态；business_state 增量合并，已写入的键不被覆盖为空。"""
    if execution_state not in _EXECUTION_STATES:
        raise ValueError(f"unknown execution_state: {execution_state}")
    with _task_db(db_path) as conn:
        row = conn.execute("SELECT business_state_json FROM agent_tasks WHERE task_id = ?", (task_id,)).fetchone()
        merged: dict[str, Any] = json.loads(row[0]) if row else {}
        if business_state:
            merged.update(business_state)
        conn.execute("UPDATE agent_tasks SET execution_state = ?, business_state_json = ?, error = ?, run_id = COALESCE(?, run_id), updated_at = CURRENT_TIMESTAMP WHERE task_id = ?", (execution_state, json.dumps(merged, ensure_ascii=False, default=str), error, run_id, task_id))


def get_task(db_path: str | Path, task_id: str) -> dict[str, Any] | None:
    with _task_db(db_path) as conn:
        row = conn.execute(f"SELECT {_TASK_COLUMNS} FROM agent_tasks WHERE task_id = ?", (task_id,)).fetchone()
    return _to_dict(row) if row else None


def list_tasks(db_path: str | Path, limit: int = 20) -> list[dict[str, Any]]:
    with _task_db(db_path) as conn:
        rows = conn.execute(f"SELECT {_TASK_COLUMNS} FROM agent_tasks ORDER BY created_at DESC, rowid DESC LIMIT ?", (max(1, min(limit, 100)),)).fetchall()
    return [_to_dict(row) for row in rows]
