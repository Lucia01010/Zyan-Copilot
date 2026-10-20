"""M16 Zhiyan Agent Brain — 整合 Context / Memory / Planner / Action Router / RAG 成完整 Agent。

最终流程（每个业务意图消息依次经过）：

    Input
      ↓ Context Assembly   （M12 ContextEngine：按 buyer 锚定统一上下文）
      ↓ Memory Retrieval   （会话记忆：服务历史摘要 + 本会话历史 Agent 轮次）
      ↓ Planning           （M14 Planner：输出 plan steps）
      ↓ Action Selection   （M14 Action Router：Planner ↓ Tool）
      ↓ Tool/RAG           （业务工具 / M15 RAG 知识库）
      ↓ Response Generation（format_action_result 聚合渲染）
      ↓ Response Grounding Check（回答必须有依据，禁止无证据业务事实）

能力咨询 / 闲聊 / 无法识别的意图按 M14 规则不进入工具执行链路：
直接返回能力介绍或诚实说明，其余阶段为空。
"""
from __future__ import annotations

import json
import re
from typing import Any

from app.action_registry import CAPABILITY_RESPONSE, TOOL_BY_ACTION, UNKNOWN_REPLY, classify_copilot_intent
from app.context_engine import ContextEngine
from app.conversation_state import ConversationStateMachine, derive_stage
from app.planner import build_plan, run_plan
from app.response_generator import generate_conversational_reply

# 事实信号：运单/订单/工单号类 token（字母前缀+6 位以上数字，或 8 位以上连续数字）
_FACT_PATTERN = re.compile(r"[a-zA-Z]{2,}\d{6,}|\d{8,}")
# 金额类事实：128 元 / ¥128 / 128.00
_AMOUNT_PATTERN = re.compile(r"(?:¥|￥|\d+\.?\d*)\s*元|(?<![\d.])\d+\.\d{2}(?![\d])")

# Grounding 失败时的诚实兜底：不编造任何业务事实
GROUNDING_FALLBACK = "这条回复里的业务信息缺少可核实的依据，为避免误导我先不给结论；我已记录该问题并会核实业务记录后答复。"


class SessionMemory:
    """进程级会话记忆：按 session_id 保存最近若干轮 Agent 记录。

    记录 intent / plan steps / tools_used，供 Planner 去重（同一会话不重复
    规划已执行行动）与决策链展示。单进程演示场景够用；跨进程持久化留待后续。
    """

    MAX_TURNS = 10

    def __init__(self) -> None:
        self._turns: dict[str, list[dict[str, Any]]] = {}

    def remember(self, session_id: str, record: dict[str, Any]) -> None:
        turns = self._turns.setdefault(session_id, [])
        turns.append(record)
        del turns[:- self.MAX_TURNS]

    def recall(self, session_id: str) -> list[dict[str, Any]]:
        return list(self._turns.get(session_id, ()))


_DEFAULT_MEMORY = SessionMemory()


def get_default_memory() -> SessionMemory:
    return _DEFAULT_MEMORY


def grounding_check(message: str, results: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Response Grounding Check：回答中出现的业务事实必须能在工具证据中找到。

    事实 = 运单/订单/工单号类 token、金额；证据 = status=OK 结果的 data JSON
    （RAG 命中的知识切片文本同属证据——引用来源即依据）。出现事实 token 但
    没有任何 OK 证据，或事实无法在证据中定位，都判定为无依据。
    """
    evidence_parts = [
        json.dumps(result.get("data"), ensure_ascii=False, default=str)
        for result in results or []
        if result.get("status") == "OK"
    ]
    evidence_text = "\n".join(evidence_parts)
    facts = sorted(
        {match.group(0) for match in _FACT_PATTERN.finditer(message)}
        | {match.group(0) for match in _AMOUNT_PATTERN.finditer(message)}
    )
    if facts and not evidence_parts:
        return {"grounded": False, "checked_facts": facts, "ungrounded_facts": facts, "evidence_count": 0}
    ungrounded = [fact for fact in facts if fact not in evidence_text]
    return {"grounded": not ungrounded, "checked_facts": facts, "ungrounded_facts": ungrounded, "evidence_count": len(evidence_parts)}


def _service_memory(context_used: dict[str, Any]) -> dict[str, Any]:
    """从已装配上下文提取服务记忆摘要：客户历史会话/订单/工单/承诺。"""
    customer = context_used.get("customer") or {}
    history = context_used.get("service_history") or {}
    digest = {
        "buyer_nickname": customer.get("buyer_nickname"),
        "session_count": customer.get("session_count"),
        "order_count": customer.get("order_count"),
        "work_order_count": customer.get("work_order_count"),
        "other_sessions": history.get("other_sessions") or [],
        "promise_count": len(history.get("promises") or []),
    }
    filtered = {key: value for key, value in digest.items() if value not in (None, 0, [], "")}
    if not filtered:
        return {}
    return {"type": "service_history", **filtered}


def process_message(
    tools,
    session_id: str,
    message: str,
    knowledge_store: Any = None,
    context_engine: ContextEngine | None = None,
    memory: SessionMemory | None = None,
    state_machine: ConversationStateMachine | None = None,
    llm_provider: Any = None,
    images: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Agent Brain 主入口：Input → 完整管线 → 带全阶段信息的响应。

    M22：llm_provider 为 qwen live 时，各分支回复由 LLM 生成（人性化、
    带多轮记忆）；mock 或 LLM 异常时回退规则模板，行为与 M16 一致。
    """
    memory = memory or _DEFAULT_MEMORY
    state_machine = state_machine or ConversationStateMachine(tools.db_path)
    text = str(message or "").strip()
    intent = classify_copilot_intent(text)
    past_turns = memory.recall(session_id)

    # M20 指代消解：无法识别的短追问继承上一轮业务行动
    follow_up_action: str | None = None
    if intent == "unknown":
        follow_up_action = state_machine.follow_up_action(session_id, text)
        if follow_up_action:
            intent = "business_query"

    # M22 自由对话兜底：能力咨询/闲聊在 live 模式下由 LLM 人性化回应
    def _free_reply(fallback: str) -> str:
        candidate = generate_conversational_reply(llm_provider, user_text=text, intent=intent, history=past_turns, images=images)
        if candidate and grounding_check(candidate, [])["grounded"]:
            return candidate
        return fallback

    # 能力咨询 / 无法识别：不调用任何工具，直接回答（M14 规则）
    if intent == "capability_question":
        reply = _free_reply(CAPABILITY_RESPONSE)
        state_machine.transition(session_id, "new", intent, [])
        memory.remember(session_id, {"intent": intent, "steps": [], "tools_used": [], "user": text, "reply": reply})
        return {"intent": intent, "message": reply, "tools_used": [], "evidence": [], "results": [], "context_used": {}, "memory_used": [], "plan_mode": "none", "plan": [], "state": {"stage": "new", "follow_up": False}, "grounding": {"grounded": True, "checked_facts": [], "ungrounded_facts": [], "evidence_count": 0}}
    if intent == "unknown":
        reply = _free_reply(UNKNOWN_REPLY)
        state_machine.transition(session_id, "new", intent, [])
        memory.remember(session_id, {"intent": intent, "steps": [], "tools_used": [], "user": text, "reply": reply})
        return {"intent": intent, "message": reply, "tools_used": [], "evidence": [], "results": [], "context_used": {}, "memory_used": [], "plan_mode": "none", "plan": [], "state": {"stage": "new", "follow_up": False}, "grounding": {"grounded": True, "checked_facts": [], "ungrounded_facts": [], "evidence_count": 0}}

    # 1. Context Assembly
    engine = context_engine or ContextEngine(tools.db_path)
    context_used = engine.build(session_id).as_dict()

    # 2. Memory Retrieval：服务历史摘要 + 本会话历史 Agent 轮次（供 Planner 去重）
    memory_used: list[dict[str, Any]] = []
    if past_turns:
        memory_used.append({"type": "past_turns", "count": len(past_turns), "turns": [{"intent": turn.get("intent"), "steps": turn.get("steps", [])} for turn in past_turns]})
    service_memory = _service_memory(context_used)
    if service_memory:
        memory_used.append(service_memory)

    # 3. Planning（M14）；M20 指代消解命中时直接继承上一轮业务行动
    if follow_up_action:
        plan = {"mode": "direct", "steps": [{"action": follow_up_action, "reason": "追问指代消解：继承上一轮业务行动重新核实", "tool": TOOL_BY_ACTION[follow_up_action]}]}
    else:
        plan = build_plan(text, intent, context=context_used, memory=past_turns)
    if not plan["steps"]:
        stage = derive_stage(intent, [])
        state_machine.transition(session_id, stage, intent, [])
        return {"intent": intent, "message": _free_reply(UNKNOWN_REPLY), "tools_used": [], "evidence": [], "results": [], "context_used": context_used, "memory_used": memory_used, "plan_mode": plan["mode"], "plan": [], "state": {"stage": stage, "follow_up": bool(follow_up_action)}, "grounding": {"grounded": True, "checked_facts": [], "ungrounded_facts": [], "evidence_count": 0}}

    # 4/5. Action Selection → Tool/RAG（M14 Router + M15/M17/M18 RAG）
    route = run_plan(tools, session_id, plan, message=text, store=knowledge_store)
    if not route["results"]:
        stage = derive_stage(intent, [])
        state_machine.transition(session_id, stage, intent, [])
        return {"intent": intent, "message": _free_reply(UNKNOWN_REPLY), "tools_used": [], "evidence": [], "results": [], "context_used": context_used, "memory_used": memory_used, "plan_mode": plan["mode"], "plan": plan["steps"], "state": {"stage": stage, "follow_up": bool(follow_up_action)}, "grounding": {"grounded": True, "checked_facts": [], "ungrounded_facts": [], "evidence_count": 0}}

    # 6. Response Generation：live 模式优先 LLM 基于证据人性化组织语言
    reply = route["message"]
    grounding = grounding_check(reply, route["results"])
    llm_reply = generate_conversational_reply(llm_provider, user_text=text, intent=intent, context_used=context_used, history=past_turns, results=route["results"], images=images)
    if llm_reply:
        llm_grounding = grounding_check(llm_reply, route["results"])
        if llm_grounding["grounded"]:
            reply, grounding = llm_reply, llm_grounding
        # LLM 回复含无依据事实 → 保留规则模板（证据可溯），不采用幻觉文本

    # 7. Response Grounding Check：无依据业务事实一律拦截并诚实兜底
    if not grounding["grounded"]:
        grounding["original_reply"] = reply[:160]
        reply = GROUNDING_FALLBACK

    # M20 状态迁移：本轮意图与行动落库，供下一轮指代消解与阶段跟踪
    stage = derive_stage(intent, route["results"])
    state_machine.transition(session_id, stage, intent, [step["action"] for step in plan["steps"]])

    # 写回会话记忆（user/reply 原文供 LLM 多轮对答；plan steps 供 Planner 去重）
    memory.remember(session_id, {"intent": intent, "steps": plan["steps"], "tools_used": route["tools_used"], "user": text, "reply": reply})

    return {
        "intent": intent,
        "message": reply,
        "tools_used": route["tools_used"],
        "evidence": route["evidence"],
        "results": route["results"],
        "context_used": context_used,
        "memory_used": memory_used,
        "plan_mode": plan["mode"],
        "plan": plan["steps"],
        "state": {"stage": stage, "follow_up": bool(follow_up_action)},
        "grounding": grounding,
    }
