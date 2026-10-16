"""M14 Planner & Action Router：让知妍自主判断下一步行动。

Planner：输入 user message（+ 可选 context / memory），输出
plan = [{"action": ..., "reason": ..., "tool": ...}]。

Action Router：按 plan 顺序经 Action Registry 调用工具，聚合结果与回复。

路由规则：
- 明确查询：单步直达工具（mode="direct"）
- 复杂问题（投诉 / 多意图）：先规划多步（mode="planned"）
- 闲聊 / 能力咨询 / 无法识别：不调用任何工具（mode="none"）

当前为规则版实现，函数签名对齐未来 LLM Planner（registry_catalog 可直接
注入提示词），接入 qwen live 后可替换为模型规划，Router 与下游不变。
"""
from __future__ import annotations

from typing import Any

from app.action_registry import (
    BUSINESS_ROUTES,
    REGISTRY_BY_ID,
    _execute_knowledge_action,
    classify_copilot_intent,
    execute_action,
    format_action_result,
)

# 投诉/升级信号：触发"历史 + 风险"多步规划，而非单点工单查询
COMPLAINT_TERMS = ("投诉", "举报", "12315", "差评", "曝光", "消协", "315")

# 复杂问题固定规划：先回看历史服务记录，再评估客户风险
_COMPLAINT_PLAN: tuple[tuple[str, str], ...] = (
    ("summarize_customer_history", "投诉属于复杂问题，先回看历史服务记录定位来龙去脉"),
    ("assess_customer_risk", "结合历史与当前会话评估客户风险等级，确定处置优先级"),
)


def _step(action_id: str, reason: str) -> dict[str, str]:
    definition = REGISTRY_BY_ID[action_id]
    return {"action": action_id, "reason": reason, "tool": definition.tool_name}


def _memory_actions(memory: list[dict[str, Any]] | None) -> set[str]:
    """从 memory（历史 plan 或 {"actions": [...]} 记录）提取已执行过的 action 集合。"""
    done: set[str] = set()
    for entry in memory or []:
        steps = entry.get("steps") if isinstance(entry, dict) else None
        if steps:
            done.update(str(step.get("action")) for step in steps if isinstance(step, dict) and step.get("action"))
        elif isinstance(entry, dict) and entry.get("actions"):
            done.update(str(a) for a in entry["actions"])
    return done


def build_plan(
    message: str,
    intent: str | None = None,
    context: dict[str, Any] | None = None,
    memory: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """规则版 Planner。

    message：用户输入；intent：可选的预分类意图（缺省内部再分类）；
    context：M12 AgentContext 字典（可选，当前用于风险倾向提示）；
    memory：本会话历史 plan 记录（可选，用于避免重复规划已执行行动）。
    """
    normalized = "".join(str(message or "").lower().split())
    intent = intent or classify_copilot_intent(normalized)
    if not normalized or intent in {"capability_question", "unknown"}:
        # 闲聊/能力咨询/无法识别：不调用 tool
        return {"mode": "none", "steps": []}
    if intent == "knowledge_query":
        # M15：通用知识类问题（产品用法/政策规则/规范）→ RAG 知识库检索
        return {"mode": "direct", "steps": [_step("search_knowledge_base", "问题属于通用产品知识或政策规则，检索业务知识库回答，不涉及具体订单")]}
    if intent == "risk_query":
        return {"mode": "direct", "steps": [_step("assess_customer_risk", "客户风险询问，需要客户上下文并由风险引擎评估")]}

    # business_query
    if any(term in normalized for term in COMPLAINT_TERMS):
        steps = [_step(action_id, reason) for action_id, reason in _COMPLAINT_PLAN]
        done = _memory_actions(memory)
        if done:
            # memory 生效：本轮会话已执行过的行动不重复规划
            steps = [step for step in steps if step["action"] not in done]
            if not steps:
                steps = [_step("assess_customer_risk", "历史摘要已在上一轮生成，本轮直接更新风险评估")]
        return {"mode": "planned", "steps": steps}

    matched: list[str] = []
    for action_id, terms in BUSINESS_ROUTES:
        if action_id not in matched and any(term in normalized for term in terms):
            matched.append(action_id)
    if not matched:
        return {"mode": "none", "steps": []}
    # 已命中具体业务动作时，泛化的订单/工单查询不重复规划（避免"退款到账了吗"多查一次订单）
    specific = set(matched) - {"check_order", "check_ticket"}
    if specific:
        matched = [action_id for action_id in matched if action_id != "check_order"]
    if len(matched) == 1:
        action_id = matched[0]
        return {"mode": "direct", "steps": [_step(action_id, f"明确查询，直接调用「{REGISTRY_BY_ID[action_id].display_name}」")]}
    # 多意图：为每个识别到的诉求各规划一步（上限 3 步）
    steps = [_step(action_id, f"问题包含多个诉求，第 {index + 1} 步处理「{REGISTRY_BY_ID[action_id].display_name}」") for index, action_id in enumerate(matched[:3])]
    return {"mode": "planned", "steps": steps}


def run_plan(tools, session_id: str, plan: dict[str, Any], message: str = "", store: Any = None) -> dict[str, Any]:
    """Action Router：Planner ↓ Tool。逐步执行并聚合结果。

    M15：search_knowledge_base 步骤走 RAG 知识库（需要问题原文 message），
    其余步骤经 Action Registry 执行业务工具。
    """
    steps = plan.get("steps") or []
    if not steps:
        return {"tools_used": [], "results": [], "evidence": [], "message": ""}
    knowledge_store = store
    results: list[dict[str, Any]] = []
    tools_used: list[str] = []
    evidence: list[dict[str, Any]] = []
    for step in steps:
        if step["action"] == "search_knowledge_base":
            if knowledge_store is None:
                from app.knowledge_base import get_default_store

                knowledge_store = get_default_store()
            result = _execute_knowledge_action(message, session_id, knowledge_store)
        else:
            result = execute_action(tools, step["action"], session_id)
        results.append(result)
        if result.get("tool_name"):
            tools_used.append(result["tool_name"])
        evidence.append({"action_id": step["action"], "source": result.get("source"), "status": result.get("status")})
        if step["action"] == "assess_customer_risk":
            evidence.extend((result.get("data") or {}).get("findings", [])[:3])
    rendered = "\n".join(format_action_result(result) for result in results)
    return {"tools_used": tools_used, "results": results, "evidence": evidence, "message": rendered}
