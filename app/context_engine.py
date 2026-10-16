"""M12 Context Engine — 统一上下文构建与隔离。

原则：
- 从单一入口（session / buyer / order）自动推导全部业务上下文；前端不必手动传大量信息。
- 按 buyer_nickname 严格隔离；切换客户 A/B 时 Context 不串线。
- 仅返回真实存在的字段；空/None 值在序列化前剔除，避免模型幻觉。
- 不修改 UI、Risk 算法、Qwen provider；风险引擎仅只读调用。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.business_tools import BusinessTools
from app.risk_engine import assess_context


_PROMISE_TERMS = ("承诺", "回访", "补发", "到账", "24小时", "明天", "保证", "一定", "尽快")


def _compact(value: dict[str, Any]) -> dict[str, Any]:
    """剔除 None / 空字符串 / 空列表，避免模型接收虚假字段。"""
    if not isinstance(value, dict):
        return value
    result: dict[str, Any] = {}
    for k, v in value.items():
        if v is None:
            continue
        if isinstance(v, str) and v.strip() == "":
            continue
        if isinstance(v, list) and not v:
            continue
        if isinstance(v, dict):
            cv = _compact(v)
            if cv:
                result[k] = cv
        else:
            result[k] = v
    return result


def _prune_messages(rows: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    return [
        _compact({
            "message_sequence": r.get("message_sequence"),
            "sent_at": r.get("sent_at"),
            "role": r.get("role"),
            "message_text": r.get("message_text") or r.get("chat_content"),
            "order_number": r.get("order_number"),
            "work_order_number": r.get("work_order_number"),
        })
        for r in rows[-limit:]
    ]


def _prune_orders(rows: list[dict[str, Any]], limit: int = 3) -> list[dict[str, Any]]:
    return [
        _compact({
            "order_number": r.get("order_number"),
            "product_name": r.get("product_name"),
            "product_sku": r.get("product_sku"),
            "quantity": r.get("quantity"),
            "order_status": r.get("order_status"),
            "paid_amount_yuan": r.get("paid_amount_yuan"),
            "carrier": r.get("carrier"),
            "tracking_number": r.get("tracking_number"),
            "gift": r.get("gift"),
            "buyer_note": r.get("buyer_note"),
        })
        for r in rows[:limit]
    ]


def _prune_work_orders(rows: list[dict[str, Any]], limit: int = 6) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in rows[:limit]:
        base = {
            "source_table": r.get("source_table"),
            "work_order_number": r.get("work_order_number"),
            "work_order_type": r.get("work_order_type"),
            "work_order_status": r.get("work_order_status") or r.get("task_status"),
            "after_sales_reason": r.get("after_sales_reason"),
            "reaction_type": r.get("reaction_type"),
            "symptom_description": r.get("symptom_description"),
            "issue_type": r.get("issue_type"),
            "carrier": r.get("carrier"),
            "problem_tracking_number": r.get("problem_tracking_number"),
            "refund_amount_yuan": r.get("refund_amount_yuan"),
            "transfer_status": r.get("transfer_status"),
            "resolution": r.get("resolution"),
        }
        out.append(_compact(base))
    return out


@dataclass
class CustomerContext:
    buyer_nickname: str | None = None
    session_count: int = 0
    order_count: int = 0
    work_order_count: int = 0

    def as_dict(self) -> dict[str, Any]:
        return _compact({
            "buyer_nickname": self.buyer_nickname,
            "session_count": self.session_count,
            "order_count": self.order_count,
            "work_order_count": self.work_order_count,
        })


@dataclass
class SessionContext:
    conversation_id: str | None = None
    message_count: int = 0
    recent_messages: list[dict[str, Any]] = field(default_factory=list)
    buyer_nickname: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return _compact({
            "conversation_id": self.conversation_id,
            "message_count": self.message_count,
            "recent_messages": self.recent_messages,
            "buyer_nickname": self.buyer_nickname,
        })


@dataclass
class ServiceHistory:
    work_orders: list[dict[str, Any]] = field(default_factory=list)
    promises: list[dict[str, Any]] = field(default_factory=list)
    other_sessions: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return _compact({
            "work_orders": self.work_orders,
            "promises": self.promises,
            "other_sessions": self.other_sessions,
        })


@dataclass
class AgentContext:
    """统一上下文对象；Qwen / Copilot 消费的唯一结构化输入。

    raw_context 保存未修剪的 messages/orders/work_orders，仅供风险引擎与
    工作流追溯内部使用，不参与 as_dict 序列化，避免超大载荷下发给模型。
    """
    customer: CustomerContext = field(default_factory=CustomerContext)
    session: SessionContext = field(default_factory=SessionContext)
    orders: list[dict[str, Any]] = field(default_factory=list)
    service_history: ServiceHistory = field(default_factory=ServiceHistory)
    risk: dict[str, Any] = field(default_factory=dict)
    available_tools: list[str] = field(default_factory=list)
    raw_context: dict[str, Any] = field(default_factory=lambda: {"messages": [], "orders": [], "work_orders": []}, repr=False)

    def as_dict(self) -> dict[str, Any]:
        return _compact({
            "customer": self.customer.as_dict(),
            "session": self.session.as_dict(),
            "orders": self.orders,
            "service_history": self.service_history.as_dict(),
            "risk": {"level": self.risk.get("level"), "requires_human_review": self.risk.get("requires_human_review"), "findings": [{"rule_id": f.get("rule_id"), "level": f.get("level"), "reason": f.get("reason"), "recommended_action": f.get("recommended_action")} for f in self.risk.get("findings", [])[:5]]} if self.risk else {},
            "available_tools": self.available_tools,
        })


class ContextEngine:
    """自动构建完整业务上下文，严格按 buyer_nickname 隔离，防数据串线。"""

    def __init__(self, db_path: Path) -> None:
        self.tools = BusinessTools(db_path)
        self.db_path = db_path

    @staticmethod
    def available_tool_names() -> list[str]:
        return [
            "get_conversation",
            "get_customer_context",
            "get_order",
            "get_work_orders",
            "check_order",
            "check_logistics",
            "check_refund",
            "check_payment",
            "check_return",
            "check_replacement",
            "check_ticket",
            "check_adverse_reaction",
            "check_service_promises",
            "summarize_customer_history",
        ]

    def _build_from_customer(self, buyer: str, *, anchor_session: str | None, session_messages: list[dict[str, Any]]) -> AgentContext:
        """以买家为锚点聚合全域上下文；所有下游数据严格归属该买家。"""
        customer_ctx = self.tools.get_customer_context(buyer, limit=200)
        all_messages = customer_ctx.get("messages", [])
        orders = customer_ctx.get("orders", [])
        work_orders = customer_ctx.get("work_orders", [])

        session_ids = sorted(set(str(m.get("conversation_id") or "") for m in all_messages if m.get("conversation_id")))
        other_sessions = [sid for sid in session_ids if sid != anchor_session][:5]

        promise_msgs = [
            m for m in all_messages
            if any(t in str(m.get("message_text") or "") for t in _PROMISE_TERMS)
        ]

        # 与会话直接关联的工单优先作为当前上下文工单（与既有 suggest 行为一致）
        raw_work_orders = work_orders
        if anchor_session:
            linked = self.tools.get_work_orders(anchor_session)
            if linked:
                raw_work_orders = linked

        # 风险引擎（只读调用，不修改 Risk 算法）
        raw_context = {"messages": session_messages or all_messages, "orders": orders, "work_orders": raw_work_orders}
        risk = assess_context(raw_context)

        return AgentContext(
            customer=CustomerContext(
                buyer_nickname=buyer,
                session_count=len(session_ids),
                order_count=len(orders),
                work_order_count=len(raw_work_orders),
            ),
            session=SessionContext(
                conversation_id=anchor_session,
                message_count=len(session_messages),
                recent_messages=_prune_messages(session_messages),
                buyer_nickname=buyer,
            ),
            orders=_prune_orders(orders),
            service_history=ServiceHistory(
                work_orders=_prune_work_orders(raw_work_orders),
                promises=_prune_messages(promise_msgs, limit=5),
                other_sessions=other_sessions,
            ),
            risk=risk,
            available_tools=self.available_tool_names(),
            raw_context=raw_context,
        )

    def build(
        self,
        session_id: str | None = None,
        *,
        conversation_id: str | None = None,
        buyer_nickname: str | None = None,
        order_number: str | None = None,
    ) -> AgentContext:
        """从任一入口自动构建上下文。无数据时安全降级为空上下文。"""
        cid = session_id or conversation_id
        if cid:
            messages = self.tools.get_conversation(cid)
            if not messages:
                return AgentContext(
                    session=SessionContext(conversation_id=cid),
                    available_tools=self.available_tool_names(),
                )
            buyer = str(messages[0].get("buyer_nickname") or "")
            if not buyer:
                return AgentContext(
                    session=SessionContext(conversation_id=cid, message_count=len(messages), recent_messages=_prune_messages(messages)),
                    available_tools=self.available_tool_names(),
                    raw_context={"messages": messages, "orders": [], "work_orders": []},
                )
            return self._build_from_customer(buyer, anchor_session=cid, session_messages=messages)

        if buyer_nickname:
            return self._build_from_customer(str(buyer_nickname), anchor_session=None, session_messages=[])

        if order_number:
            order = self.tools.get_order(order_number)
            work_orders = self.tools.get_work_orders(None, order_number)
            buyer = str(order.get("buyer_nickname") or "") if order else ""
            if buyer:
                ctx = self._build_from_customer(buyer, anchor_session=None, session_messages=[])
                # 订单入口：上下文收敛到该订单，避免带入其他订单造成干扰
                ctx.orders = _prune_orders([order] if order else [])
                ctx.raw_context = {"messages": [], "orders": [order] if order else [], "work_orders": work_orders}
                ctx.risk = assess_context(ctx.raw_context)
                return ctx
            return AgentContext(available_tools=self.available_tool_names(), raw_context={"messages": [], "orders": [], "work_orders": work_orders})

        return AgentContext(available_tools=self.available_tool_names())
