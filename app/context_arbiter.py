"""12-Factor 原则 5：上下文评估与仲裁（规则版）。

拒绝 FIFO 一刀切：按业务重要性对历史消息分级——
- 核心诉求与业务实体（订单号/单号/金额）= 必须保留，永不因窗口不足被挤出；
- 一般背景轮次 = 有空位才保留；
- 寒暄/确认类短消息 = 空间不足时优先丢弃；
- 必须保留的条目超出预算时做规则摘要压缩，超限部分合并为一条摘要。
风险引擎（assess_context）仍看全量数据，仲裁只作用于进入 LLM 上下文的投影。
"""
from __future__ import annotations

import re
from typing import Any

_CORE_INTENT_TERMS = (
    "退款", "退货", "换货", "补发", "换新", "投诉", "举报", "假货", "过敏",
    "不良反应", "差评", "仅退款", "三倍", "赔偿", "处罚", "工商", "破损",
    "少发", "漏发", "发错", "催发货", "未发货", "未收到", "赠品", "发票", "保质期",
)

_ENTITY_PATTERN = re.compile(
    r"(?:订单号|单号|编号|物流单|快递单)\s*[:：]?\s*[A-Za-z0-9\-]{5,}"
    r"|[A-Za-z]{2,}\d{6,}"
    r"|\d{8,}"
    r"|[¥￥]\s*\d+(?:\.\d+)?"
    r"|\d+(?:\.\d+)?\s*元"
)

_PLEASANTRY_TERMS = ("你好", "您好", "在吗", "谢谢", "感谢", "辛苦了", "好的", "收到", "嗯", "ok", "OK", "请稍等", "稍等", "亲")

_MAX_TEXT_CHARS = 80


def _message_text(message: dict[str, Any]) -> str:
    return str(message.get("message_text") or message.get("chat_content") or "").strip()


def _is_pleasantry(text: str) -> bool:
    return len(text) <= 12 and any(term in text.lower() for term in _PLEASANTRY_TERMS)


def _score(message: dict[str, Any], index: int, total: int) -> tuple[int, str]:
    """返回 (重要性 1-5, 命中原因)。5=必须保留，4=业务实体，3=背景，1=寒暄。"""
    if index == total - 1:
        return 5, "latest"
    text = _message_text(message)
    if any(term in text for term in _CORE_INTENT_TERMS):
        return 5, "core_intent"
    if _ENTITY_PATTERN.search(text) or message.get("order_number") or message.get("work_order_number"):
        return 4, "business_entity"
    if _is_pleasantry(text):
        return 1, "pleasantry"
    return 3, "background"


def _compress_text(text: str, limit: int = _MAX_TEXT_CHARS) -> str:
    if len(text) <= limit:
        return text
    entities = "；".join(dict.fromkeys(match.group(0) for match in _ENTITY_PATTERN.finditer(text)))
    head = text[:limit].rstrip()
    if entities and entities not in head:
        return f"{head}…（关键实体：{entities}）"
    return f"{head}…"


def arbitrate_messages(messages: list[dict[str, Any]], max_messages: int = 6, max_entries: int = 12) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """返回 (仲裁后的消息列表, 统计信息)。最新消息永远完整保留。"""
    total = len(messages)
    stats: dict[str, Any] = {"total": total, "kept": total, "compressed": 0, "dropped": 0}
    if total <= max_messages:
        return list(messages), stats

    scored = [(index, *_score(message, index, total)) for index, message in enumerate(messages)]
    must_keep = [item for item in scored if item[1] >= 4]
    background = [item for item in scored if item[1] < 4]
    background.sort(key=lambda item: item[0], reverse=True)  # 越新越优先

    # 阶段 A（完整窗口）：最新消息 + 必须保留项优先，空位按新旧由背景消息补足，总量 ≤ max_messages
    full: list[tuple[int, int, str]] = []
    latest_index = total - 1
    for item in sorted(must_keep, key=lambda item: item[0], reverse=True):
        if item[0] == latest_index or len(full) < max_messages:
            full.append(item)
    for item in background:
        if len(full) >= max_messages:
            break
        full.append(item)

    # 阶段 B（压缩区）：未进入完整窗口的必须保留项做规则摘要，总量 ≤ max_entries
    full_indices = {item[0] for item in full}
    compressed: list[tuple[int, int, str]] = []
    for item in sorted(must_keep, key=lambda item: item[0]):
        if item[0] in full_indices:
            continue
        if len(full) + len(compressed) >= max_entries:
            break
        compressed.append(item)

    kept_indices = full_indices
    compressed_indices = {item[0] for item in compressed}
    dropped = total - len(kept_indices) - len(compressed_indices)
    stats.update({"kept": len(kept_indices), "compressed": len(compressed_indices), "dropped": dropped})

    result: list[dict[str, Any]] = []
    for index in sorted(kept_indices | compressed_indices):
        message = dict(messages[index])
        if index in compressed_indices:
            message["message_text"] = _compress_text(_message_text(message))
            message["text_truncated"] = True
        result.append(message)
    return result, stats


def arbitrate_orders(orders: list[dict[str, Any]], preferred_order_number: str | None, messages: list[dict[str, Any]], max_orders: int = 3) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """订单投影排序：入参指定订单 > 会话内被提及的订单 > 其余；超出上限丢弃低相关项。"""
    total = len(orders)
    if total <= max_orders:
        return list(orders), {"total": total, "kept": total}

    def rank(order: dict[str, Any]) -> int:
        number = str(order.get("order_number") or "")
        if preferred_order_number and number == str(preferred_order_number):
            return 2
        if number and any(number in _message_text(message) for message in messages):
            return 1
        return 0

    ranked = sorted(orders, key=rank, reverse=True)
    return ranked[:max_orders], {"total": total, "kept": max_orders}
