"""M20 Agent Conversation State Machine：会话状态持久化与指代消解。

解决"用户追问无信号短消息（'还是没有到账'、'怎么样了'）时 Agent 重新开始"的问题：

- 状态持久化在业务库 `conversation_state` 表（与人工反馈同一库，可审计、跨重启存活）；
- 每轮对话结束推导 stage 并记录 last_intent / last_actions；
- 下一轮消息若无法识别意图，且命中追问标记/为无实体短消息，则继承上一轮
  最后执行的业务行动重新执行（指代消解的规则版；接 qwen live 后可换模型消解）。

阶段集：new → confirmed → classified → querying → processing → awaiting_feedback → resolved
（规则版推导：能力/闲聊=new；查询结果含 NOT_FOUND=awaiting_feedback；其余=processing）
"""
from __future__ import annotations

import json
import re
import sqlite3
from contextlib import contextmanager
from typing import Any, Iterator

STAGES = ("new", "confirmed", "classified", "querying", "processing", "awaiting_feedback", "resolved")

# 追问标记：无业务实体的跟进式短消息
FOLLOW_UP_MARKERS = ("还是", "还没", "仍未", "怎么样了", "如何了", "然后呢", "进展", "再催一下", "催一下")
FOLLOW_UP_MAX_LEN = 12
# 闲聊/问候不触发指代消解，避免"你好"继承上一轮业务查询；
# 判定为整句归一化匹配（去标点），"怎么样了"这类追问不受影响
_CHITCHAT_EXACT = {"你好", "您好", "在吗", "在么", "谢谢", "感谢", "好的", "好", "嗯", "哦", "ok", "okay", "拜拜", "再见", "hello", "hi", "hey", "早", "早上好", "中午好", "下午好", "晚上好"}
_CHITCHAT_FILLER = "呀啊呢吗嘛哈喽哇~～!！。"
_CHITCHAT_HEADS = ("你好", "您好", "hello", "hi", "hey")


def _is_chitchat(text: str) -> bool:
    normalized = re.sub(r"[\s，。！？!?,.~～]", "", str(text or "").lower())
    if not normalized:
        return True
    if normalized in _CHITCHAT_EXACT:
        return True
    for head in _CHITCHAT_HEADS:
        if normalized.startswith(head):
            rest = normalized[len(head):]
            if not rest or all(ch in _CHITCHAT_FILLER for ch in rest):
                return True
    return False


class ConversationStateMachine:
    def __init__(self, db_path: str):
        self.db_path = str(db_path)
        self._ensure_table()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _ensure_table(self) -> None:
        with self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS conversation_state ("
                "session_id TEXT PRIMARY KEY, stage TEXT NOT NULL, "
                "last_intent TEXT NOT NULL DEFAULT '', last_actions TEXT NOT NULL DEFAULT '[]', "
                "updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
            )
            conn.commit()

    def get(self, session_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT stage, last_intent, last_actions, updated_at FROM conversation_state WHERE session_id = ?", (session_id,)).fetchone()
        if row is None:
            return None
        return {"session_id": session_id, "stage": row["stage"], "last_intent": row["last_intent"], "last_actions": json.loads(row["last_actions"] or "[]"), "updated_at": row["updated_at"]}

    def transition(self, session_id: str, stage: str, last_intent: str = "", last_actions: list[str] | None = None) -> None:
        if stage not in STAGES:
            raise ValueError(f"unknown conversation stage: {stage}")
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO conversation_state(session_id, stage, last_intent, last_actions, updated_at) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)",
                (session_id, stage, last_intent, json.dumps(last_actions or [], ensure_ascii=False)),
            )
            conn.commit()

    def follow_up_action(self, session_id: str, message: str) -> str | None:
        """指代消解：无法识别的短追问继承上一轮业务行动；否则返回 None。"""
        state = self.get(session_id)
        if not state or state["last_intent"] != "business_query" or not state["last_actions"]:
            return None
        text = str(message or "").strip().lower()
        if _is_chitchat(text):
            return None
        is_short = len(text) <= FOLLOW_UP_MAX_LEN
        has_marker = any(marker in text for marker in FOLLOW_UP_MARKERS)
        if is_short or has_marker:
            return state["last_actions"][0]
        return None


def derive_stage(intent: str, results: list[dict[str, Any]] | None) -> str:
    """规则版阶段推导：零工具意图=new；结果含 NOT_FOUND=awaiting_feedback；其余=processing。"""
    if intent in ("capability_question", "unknown") and not results:
        return "new"
    if any((result or {}).get("status") == "NOT_FOUND" for result in results or []):
        return "awaiting_feedback"
    return "processing"
