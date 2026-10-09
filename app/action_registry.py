"""Grounded quick actions for the Zhiyan Copilot plugin.

The registry is the single allowlist shared by recommendation and execution.
It never fabricates a result: tools return NOT_FOUND when the instance data
does not contain the requested business record.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.business_tools import BusinessTools
from app.error_compactor import compact_tool_error


@dataclass(frozen=True)
class ActionDefinition:
    action_id: str
    display_name: str
    tool_name: str
    scenes: tuple[str, ...]
    source: str


ACTION_DEFINITIONS: tuple[ActionDefinition, ...] = (
    ActionDefinition("check_order", "查看订单信息", "get_order_info", ("订单", "普通咨询", "赠品"), "orders"),
    ActionDefinition("check_logistics", "查看物流信息", "get_logistics_info", ("物流", "未收到", "发货"), "orders + logistics_work_orders"),
    ActionDefinition("check_refund", "查看退款状态", "get_refund_status", ("退款", "到账", "售后"), "after_sales_return_work_orders + offline_payment_work_orders"),
    ActionDefinition("check_payment", "查看打款状态", "get_payment_status", ("线下打款", "退款", "到账"), "offline_payment_work_orders"),
    ActionDefinition("check_return", "查看退货进度", "get_return_status", ("退货", "退款"), "after_sales_return_work_orders"),
    ActionDefinition("check_replacement", "查看换货状态", "get_replacement_status", ("换货", "补发"), "replacement_work_orders"),
    ActionDefinition("check_ticket", "查看售后工单", "get_ticket_status", ("售后", "工单", "投诉"), "work_orders"),
    ActionDefinition("check_adverse_reaction", "查看不良反应记录", "get_adverse_reaction_record", ("不良反应", "过敏", "发红", "瘙痒", "刺痛"), "adverse_reaction_work_orders"),
    ActionDefinition("check_service_history", "查看历史沟通", "get_service_history", ("历史", "投诉", "重复进线", "不良反应"), "chat_messages"),
    ActionDefinition("check_service_promises", "查看历史服务承诺", "get_service_promises", ("承诺", "补发", "回访", "赠品"), "chat_messages"),
)

REGISTRY_BY_ID = {item.action_id: item for item in ACTION_DEFINITIONS}
TOOL_BY_ACTION = {item.action_id: item.tool_name for item in ACTION_DEFINITIONS}


def _conversation_text(tools: BusinessTools, session_id: str) -> str:
    return " ".join(str(row.get("message_text") or row.get("chat_content") or "") for row in tools.get_conversation(session_id)[-12:])


def recommend_actions(tools: BusinessTools, session_id: str) -> list[dict[str, Any]]:
    """Return 1-4 high-signal actions from current instance context."""
    text = _conversation_text(tools, session_id)
    ranked: list[tuple[int, ActionDefinition, str]] = []
    rules = (
        ("check_adverse_reaction", ("过敏", "发红", "瘙痒", "刺痛", "不适"), "需要核对不良反应登记和处理状态"),
        ("check_logistics", ("物流", "快递", "没收到", "未收到", "发货", "签收"), "消费者正在询问配送或签收状态"),
        ("check_refund", ("退款", "退钱", "到账", "钱退", "售后单关闭"), "消费者正在询问退款或到账进度"),
        ("check_payment", ("打款", "支付宝", "线下"), "当前对话涉及线下打款状态"),
        ("check_return", ("退货", "退回", "仓库签收"), "需要核对退货和售后进度"),
        ("check_replacement", ("换货", "补发", "漏发", "少件"), "需要核对换货或补发状态"),
        ("check_service_promises", ("赠品", "承诺", "回访"), "需要核对历史服务承诺"),
        ("check_service_history", ("投诉", "重复", "再次进线", "历史"), "需要回看历史沟通"),
    )
    for action_id, terms, reason in rules:
        if any(term in text for term in terms):
            ranked.append((len([term for term in terms if term in text]), REGISTRY_BY_ID[action_id], reason))
    if not ranked:
        ranked.append((1, REGISTRY_BY_ID["check_order"], "先核对当前订单和商品上下文"))
    ranked.sort(key=lambda item: item[0], reverse=True)
    selected = ranked[:3]
    if len(selected) < 2 and selected[0][1].action_id not in {"check_service_history", "check_order"}:
        selected.append((0, REGISTRY_BY_ID["check_service_history"], "必要时回看历史服务记录"))
    return [{"action_id": definition.action_id, "label": definition.display_name, "reason": reason, "priority": "primary" if index == 0 else "secondary", "tool_name": definition.tool_name, "available": True, "source": definition.source} for index, (_, definition, reason) in enumerate(selected[:4])]


def execute_action(tools: BusinessTools, action_id: str, session_id: str) -> dict[str, Any]:
    definition = REGISTRY_BY_ID.get(action_id)
    if definition is None:
        raise KeyError(f"unknown action: {action_id}")
    tool: Callable[..., Any] = getattr(tools, definition.tool_name)
    try:
        result = tool(session_id)
    except Exception as exc:
        # 原则 6 错误压缩：结构化 ERROR 载荷随响应返回供审计/自纠，不向上抛裸异常
        return {"status": "ERROR", "data": {}, "error": compact_tool_error(definition.tool_name, exc), "action_id": action_id, "tool_name": definition.tool_name, "session_id": session_id}
    return {**result, "action_id": action_id, "tool_name": definition.tool_name, "session_id": session_id}


def format_action_result(result: dict[str, Any]) -> str:
    if result.get("status") == "ERROR":
        return "业务查询服务暂时异常，我会记录问题并尽快核实后给您答复。"
    if result.get("status") != "OK":
        return "当前比赛实例数据未找到相关记录，我会帮您进一步核实。"
    data = result.get("data") or {}
    action_id = result.get("action_id")
    if action_id == "check_logistics":
        rows = data.get("work_orders") or []
        orders = data.get("orders") or []
        row = rows[0] if rows else {}
        order = orders[0] if orders else {}
        carrier = row.get("carrier") or ""
        tracking = row.get("problem_tracking_number") or order.get("tracking_number")
        status = row.get("work_order_status") or row.get("resolution") or order.get("order_status") or "已记录"
        parts = ["当前订单物流信息已查到"]
        if carrier: parts.append(f"承运商：{carrier}")
        if tracking: parts.append(f"物流单号：{tracking}")
        parts.append(f"当前状态：{status}")
        parts.append("当前实例数据未提供更详细的实时轨迹。")
        return "；".join(parts) + "。"
    if action_id in {"check_refund", "check_payment", "check_return", "check_replacement", "check_ticket", "check_adverse_reaction"}:
        rows = data if isinstance(data, list) else data.get("work_orders") or []
        row = rows[0] if rows else {}
        number = row.get("work_order_number")
        status = row.get("transfer_status") or row.get("work_order_status") or row.get("task_status") or "待核实"
        label = {"check_refund": "退款", "check_payment": "打款", "check_return": "退货", "check_replacement": "补发/换货", "check_ticket": "售后工单", "check_adverse_reaction": "不良反应记录"}[action_id]
        return f"当前{label}记录状态为“{status}”" + (f"，记录编号为 {number}" if number else "") + "。"
    if action_id == "check_order":
        rows = data if isinstance(data, list) else []
        return f"当前客户共有 {len(rows)} 条订单记录，已为您列出相关订单信息。"
    if action_id == "check_service_history":
        rows = data if isinstance(data, list) else []
        return f"已查到当前会话 {len(rows)} 条历史沟通记录。"
    if action_id == "check_service_promises":
        rows = data if isinstance(data, list) else []
        return f"已查到 {len(rows)} 条包含承诺或服务跟进信息的沟通记录。"
    return "已完成查询。"
