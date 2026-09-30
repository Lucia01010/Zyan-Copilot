"""Explainable, deterministic rules for the M2 risk baseline."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


LEVEL_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


@dataclass(frozen=True)
class RiskFinding:
    rule_id: str
    level: str
    category: str
    reason: str
    evidence: dict[str, Any]
    recommended_action: str


def _highest(findings: list[RiskFinding]) -> str:
    return max((finding.level for finding in findings), key=lambda level: LEVEL_ORDER[level], default="low")


def assess_context(context: dict[str, Any]) -> dict[str, Any]:
    findings: list[RiskFinding] = []
    messages = context.get("messages", [])
    work_orders = context.get("work_orders", [])
    orders = context.get("orders", [])
    joined_text = " ".join(str(message.get("message_text") or message.get("chat_content") or "") for message in messages)

    adverse = [item for item in work_orders if item.get("source_table") == "adverse_reaction_work_orders"]
    if adverse:
        findings.append(RiskFinding("adverse_reaction", "critical", "safety", "发现不良反应工单，需要人工优先处理并核实停用/就医情况。", {"work_order_numbers": [x.get("work_order_number") for x in adverse]}, "立即人工接管，核实症状、停用和就医情况，按平台流程升级。"))

    urgent = [item for item in work_orders if str(item.get("complaint_urgent", "")).lower() in {"是", "1", "true", "yes"}]
    abnormal = [item for item in work_orders if str(item.get("is_abnormal", "")).lower() in {"是", "1", "true", "yes"}]
    if urgent:
        findings.append(RiskFinding("urgent_complaint", "high", "complaint", "工单标记为客诉加急。", {"work_order_numbers": [x.get("work_order_number") for x in urgent]}, "优先分配负责人并在回复前核对完整服务轨迹。"))
    if abnormal:
        findings.append(RiskFinding("abnormal_return", "high", "after_sales", "售后退货工单标记为异常。", {"work_order_numbers": [x.get("work_order_number") for x in abnormal]}, "核对退款、物流和历史工单，避免重复承诺或重复退款。"))

    escalation_terms = ("投诉", "举报", "媒体", "曝光", "12315", "生气", "失望", "再也不", "骗子")
    matched_terms = sorted({term for term in escalation_terms if term in joined_text})
    if matched_terms:
        findings.append(RiskFinding("emotion_escalation", "high", "sentiment", "聊天内容包含投诉或情绪升级信号。", {"matched_terms": matched_terms}, "使用共情式回复并转人工复核，避免继续发送模板承诺。"))

    if len(messages) >= 20:
        findings.append(RiskFinding("long_conversation", "medium", "service", "单次会话消息较多，存在重复沟通或问题未闭环迹象。", {"message_count": len(messages)}, "先总结已知事实，再确认唯一待解决事项和下一步时限。"))
    if len(orders) > 1:
        findings.append(RiskFinding("multi_order_context", "low", "context", "客户存在多个订单，需要绑定当前咨询订单。", {"order_count": len(orders)}, "回复前确认关联订单号，避免串单。"))

    return {"level": _highest(findings), "findings": [finding.__dict__ for finding in findings], "requires_human_review": any(f.level in {"high", "critical"} for f in findings)}
