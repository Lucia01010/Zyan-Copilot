"""M22 Conversational Response Generation — LLM 人性化对话生成。

问题：mock 链路的回复是规则模板拼接，"你好"这类闲聊只会得到僵硬兜底，
做不到自由问答、人性化、带上下文记忆的对答。

设计：
- 仅 qwen live 模式启用（provider.mock=False）；mock 模式一律返回 None，
  调用方回退规则模板，保证离线演示与测试可复现。
- 闲聊/能力咨询：LLM 凭系统提示自由对话（身份、能力边界、事实纪律写死）。
- 业务/知识查询：LLM 基于工具/RAG 结果组织自然语言，回复仍过
  Response Grounding Check——含无依据业务事实时回退规则模板。
- 多轮记忆：调用方传入 SessionMemory 的历史轮次（user/reply），
  作为对话历史随消息发给模型，实现上下文对答。

幻觉防线：系统提示明确"业务事实只能来自业务核查结果"，且输出仍被
agent_brain.grounding_check 复核，双重约束。
"""
from __future__ import annotations

import json
from typing import Any

SYSTEM_PROMPT = """你是"知妍"，美妆护肤品牌旗舰店的 AI 客服助手，正在客服工作台中协助人工客服与买家沟通。

说话要求：
1. 语气自然、亲切、有人情味，像经验丰富的客服一样对话；口语化，不机械背诵，不罗列字段名或 JSON。
2. 订单、物流、退款、工单等业务事实只能来自"业务核查结果"；结果里没有的信息就说"我去帮你核实"，严禁编造单号、金额、状态、时间。
3. 产品用法、售后规则等通用知识只能依据"知识库资料"；资料没有就如实说明。
4. 买家或客服的闲聊、问候、感谢自然回应即可，可顺势引导到服务场景。
5. 回复控制在 120 字以内。

你的能力：查询订单信息、查看物流状态、查询退款/打款进度、查看售后工单、分析客户情绪和风险、生成客服建议回复、解答产品使用与售后规则等通用知识。"""

_HISTORY_TURNS = 6
_RESULT_CHAR_LIMIT = 800


def _compact_json(value: Any, limit: int = _RESULT_CHAR_LIMIT) -> str:
    text = json.dumps(value, ensure_ascii=False, default=str)
    return text if len(text) <= limit else text[:limit] + "…"


def _context_section(context_used: dict[str, Any] | None) -> str:
    """当前服务上下文摘要：买家、订单、服务历史（脱敏为概览数字）。"""
    if not context_used:
        return ""
    customer = context_used.get("customer") or {}
    session = context_used.get("session") or {}
    lines = []
    if customer.get("buyer_nickname"):
        parts = [f"买家昵称：{customer['buyer_nickname']}"]
        if customer.get("order_count"):
            parts.append(f"历史订单 {customer['order_count']} 笔")
        if customer.get("work_order_count"):
            parts.append(f"历史工单 {customer['work_order_count']} 个")
        lines.append("· " + "，".join(parts))
    order = (context_used.get("order") or {})
    if order.get("order_number") or order.get("product_name"):
        lines.append(f"· 当前订单：{_compact_json(order, 300)}")
    if session.get("conversation_id"):
        lines.append(f"· 当前会话：{session['conversation_id']}")
    return "当前服务上下文：\n" + "\n".join(lines) if lines else ""


def _results_section(results: list[dict[str, Any]] | None) -> str:
    """工具/RAG 结果摘要：OK 证据 + NOT_FOUND/ERROR 如实标注。"""
    if not results:
        return ""
    lines = []
    for result in results:
        label = result.get("action_id") or result.get("tool_name") or "查询"
        status = result.get("status")
        if status == "OK":
            lines.append(f"· {label}（已查到）：{_compact_json(result.get('data'))}")
        elif status == "NOT_FOUND":
            lines.append(f"· {label}：未查到相关记录")
        else:
            lines.append(f"· {label}：查询异常（{result.get('error', {}).get('hint', '稍后重试') if isinstance(result.get('error'), dict) else '稍后重试'}）")
    return "本轮业务核查结果（业务事实唯一依据）：\n" + "\n".join(lines) if lines else ""


def build_chat_messages(
    *,
    user_text: str,
    context_used: dict[str, Any] | None = None,
    history: list[dict[str, Any]] | None = None,
    results: list[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    """组装发给模型的消息：系统提示 + 上下文/证据 + 对话历史 + 本轮问题。"""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for section in (_context_section(context_used), _results_section(results)):
        if section:
            messages.append({"role": "system", "content": section})
    for turn in (history or [])[-_HISTORY_TURNS:]:
        user_part = str(turn.get("user") or "").strip()
        reply_part = str(turn.get("reply") or "").strip()
        if user_part:
            messages.append({"role": "user", "content": user_part})
        if reply_part:
            messages.append({"role": "assistant", "content": reply_part})
    messages.append({"role": "user", "content": user_text})
    return messages


def generate_conversational_reply(
    provider: Any,
    *,
    user_text: str,
    intent: str,
    context_used: dict[str, Any] | None = None,
    history: list[dict[str, Any]] | None = None,
    results: list[dict[str, Any]] | None = None,
) -> str | None:
    """LLM 人性化回复；mock/异常/空内容一律返回 None 让调用方回退规则模板。"""
    if provider is None or getattr(provider, "mock", True):
        return None
    messages = build_chat_messages(user_text=user_text, context_used=context_used, history=history, results=results)
    try:
        body = provider._request(messages, [], stage="chat")
    except Exception:
        return None
    choices = body.get("choices") or []
    if not choices:
        return None
    content = str((choices[0].get("message") or {}).get("content") or "").strip()
    return content or None
