"""Read-only, whitelisted business query tools over the M1 SQLite database."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


class ToolInputError(ValueError):
    pass


@dataclass
class BusinessTools:
    db_path: Path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
        return dict(row) if row is not None else None

    @staticmethod
    def _project(name: str, value: Any) -> Any:
        fields = {
            "order": ("order_number", "conversation_id", "product_name", "product_sku", "gift", "order_status", "paid_amount_yuan", "tracking_number"),
            "message": ("message_id", "conversation_id", "message_sequence", "sent_at", "role", "message_text", "order_number", "work_order_number"),
            "work_order": ("source_table", "work_order_number", "conversation_id", "order_number", "work_order_type", "after_sales_reason", "reaction_type", "symptom_description", "work_order_status", "task_status", "complaint_urgent", "is_abnormal", "issue_type", "carrier", "problem_tracking_number", "resolution", "refund_issue_type", "refund_amount_yuan", "transfer_status", "related_tracking_number"),
        }
        if isinstance(value, list):
            kind = "message" if name == "conversation" else "work_order" if name == "work_orders" else "order"
            return [{key: item.get(key) for key in fields[kind] if key in item} for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            if name in fields:
                return {key: value.get(key) for key in fields[name] if key in value}
            return {key: BusinessTools._project("order" if key == "orders" else "conversation" if key == "messages" else "work_orders", item) for key, item in value.items() if key in {"buyer_nickname", "orders", "messages", "work_orders"}}
        return value

    def get_order(self, order_number: str) -> dict[str, Any] | None:
        if not order_number:
            raise ToolInputError("order_number is required")
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM orders WHERE order_number = ? LIMIT 1", (str(order_number),)).fetchone()
        return self._row(row)

    def get_conversation(self, conversation_id: str, limit: int = 100) -> list[dict[str, Any]]:
        if not conversation_id:
            raise ToolInputError("conversation_id is required")
        limit = max(1, min(int(limit), 500))
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM chat_messages WHERE conversation_id = ? ORDER BY CAST(message_sequence AS INTEGER), _row_number LIMIT ?",
                (str(conversation_id), limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_customer_context(self, buyer_nickname: str, limit: int = 100) -> dict[str, Any]:
        if not buyer_nickname:
            raise ToolInputError("buyer_nickname is required")
        limit = max(1, min(int(limit), 500))
        with self._connect() as conn:
            orders = conn.execute("SELECT * FROM orders WHERE buyer_nickname = ? ORDER BY ordered_at DESC LIMIT ?", (str(buyer_nickname), limit)).fetchall()
            messages = conn.execute("SELECT * FROM chat_messages WHERE buyer_nickname = ? ORDER BY sent_at DESC LIMIT ?", (str(buyer_nickname), limit)).fetchall()
            work_orders: list[dict[str, Any]] = []
            for table in ("replacement_work_orders", "offline_payment_work_orders", "logistics_work_orders", "adverse_reaction_work_orders", "after_sales_return_work_orders"):
                work_orders.extend({"source_table": table, **dict(row)} for row in conn.execute(f"SELECT * FROM {table} WHERE buyer_nickname = ? LIMIT ?", (str(buyer_nickname), limit)).fetchall())
        return {"buyer_nickname": str(buyer_nickname), "orders": [dict(row) for row in orders], "messages": [dict(row) for row in messages], "work_orders": work_orders}

    def get_work_orders(self, conversation_id: str | None = None, order_number: str | None = None) -> list[dict[str, Any]]:
        if not conversation_id and not order_number:
            raise ToolInputError("conversation_id or order_number is required")
        results: list[dict[str, Any]] = []
        with self._connect() as conn:
            for table in ("replacement_work_orders", "offline_payment_work_orders", "logistics_work_orders", "adverse_reaction_work_orders", "after_sales_return_work_orders"):
                clauses = []
                params: list[str] = []
                if conversation_id:
                    clauses.append("conversation_id = ?")
                    params.append(str(conversation_id))
                if order_number:
                    clauses.append("order_number = ?")
                    params.append(str(order_number))
                rows = conn.execute(f"SELECT * FROM {table} WHERE {' OR '.join(clauses)}", params).fetchall()
                results.extend({"source_table": table, **dict(row)} for row in rows)
        return results

    # The action layer deliberately exposes small, grounded projections.  The
    # underlying tables remain read-only and every result carries its source.
    def _session_context(self, session_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        messages = self.get_conversation(session_id)
        if not messages:
            return {"orders": [], "work_orders": [], "messages": []}, []
        buyer = messages[0].get("buyer_nickname")
        context = self.get_customer_context(str(buyer)) if buyer else {"orders": [], "work_orders": [], "messages": messages}
        linked = self.get_work_orders(session_id)
        return context, linked

    @staticmethod
    def _action_result(action_id: str, source: str, data: Any, *, found: bool = True, message: str | None = None) -> dict[str, Any]:
        return {"action_id": action_id, "status": "OK" if found else "NOT_FOUND", "source": source, "data": data if found else {}, "message": message or ("已从比赛实例数据查询到相关记录。" if found else "未找到相关业务记录。")}

    def get_order_info(self, session_id: str) -> dict[str, Any]:
        context, _ = self._session_context(session_id)
        orders = self._project("orders", context.get("orders", []))
        return self._action_result("check_order", "orders", orders, found=bool(orders))

    def get_logistics_info(self, session_id: str) -> dict[str, Any]:
        context, linked = self._session_context(session_id)
        rows = [row for row in linked if row.get("source_table") == "logistics_work_orders"]
        orders = [{key: order.get(key) for key in ("order_number", "product_name", "order_status", "tracking_number") if order.get(key) is not None} for order in context.get("orders", []) if order.get("tracking_number")]
        data = {"work_orders": self._project("work_orders", rows), "orders": orders}
        return self._action_result("check_logistics", "orders + logistics_work_orders", data, found=bool(rows or orders))

    def get_refund_status(self, session_id: str) -> dict[str, Any]:
        _, linked = self._session_context(session_id)
        rows = [row for row in linked if row.get("refund_issue_type") or row.get("refund_amount_yuan") or row.get("transfer_status")]
        return self._action_result("check_refund", "after_sales_return_work_orders + offline_payment_work_orders", self._project("work_orders", rows), found=bool(rows))

    def get_payment_status(self, session_id: str) -> dict[str, Any]:
        _, linked = self._session_context(session_id)
        rows = [row for row in linked if row.get("transfer_status") or row.get("refund_amount_yuan")]
        return self._action_result("check_payment", "offline_payment_work_orders", self._project("work_orders", rows), found=bool(rows))

    def get_return_status(self, session_id: str) -> dict[str, Any]:
        _, linked = self._session_context(session_id)
        rows = [row for row in linked if row.get("source_table") == "after_sales_return_work_orders"]
        return self._action_result("check_return", "after_sales_return_work_orders", self._project("work_orders", rows), found=bool(rows))

    def get_replacement_status(self, session_id: str) -> dict[str, Any]:
        _, linked = self._session_context(session_id)
        rows = [row for row in linked if row.get("source_table") == "replacement_work_orders"]
        return self._action_result("check_replacement", "replacement_work_orders", self._project("work_orders", rows), found=bool(rows))

    def get_ticket_status(self, session_id: str) -> dict[str, Any]:
        _, linked = self._session_context(session_id)
        return self._action_result("check_ticket", "work_orders", self._project("work_orders", linked), found=bool(linked))

    def get_adverse_reaction_record(self, session_id: str) -> dict[str, Any]:
        _, linked = self._session_context(session_id)
        rows = [row for row in linked if row.get("source_table") == "adverse_reaction_work_orders"]
        return self._action_result("check_adverse_reaction", "adverse_reaction_work_orders", self._project("work_orders", rows), found=bool(rows))

    def get_service_history(self, session_id: str) -> dict[str, Any]:
        messages = self.get_conversation(session_id)
        return self._action_result("check_service_history", "chat_messages", self._project("conversation", messages[-12:]), found=bool(messages))

    def summarize_customer_history(self, session_id: str) -> dict[str, Any]:
        """聚合当前客户的全域历史：跨会话消息、工单、服务承诺，供规则化总结消费。"""
        messages = self.get_conversation(session_id)
        if not messages:
            return self._action_result("summarize_customer_history", "chat_messages", [], found=False)
        buyer = messages[0].get("buyer_nickname")
        context = self.get_customer_context(str(buyer), limit=200) if buyer else {"orders": [], "work_orders": [], "messages": messages}
        all_messages = context.get("messages", [])
        work_orders = context.get("work_orders", [])
        orders = context.get("orders", [])
        promise_terms = ("承诺", "回访", "补发", "到账", "24小时", "明天", "保证", "一定", "尽快")
        promises = [m for m in all_messages if any(t in str(m.get("message_text") or "") for t in promise_terms)]
        sessions = sorted(set(str(m.get("conversation_id") or "") for m in all_messages if m.get("conversation_id")))
        data = {
            "buyer_nickname": buyer,
            "session_count": len(sessions),
            "message_count": len(all_messages),
            "sessions": sessions,
            "messages": self._project("conversation", all_messages),
            "work_orders": self._project("work_orders", work_orders),
            "orders": self._project("orders", orders),
            "promises": self._project("conversation", promises[-6:]),
        }
        return self._action_result("summarize_customer_history", "customer_context", data, found=bool(all_messages))

    def get_service_promises(self, session_id: str) -> dict[str, Any]:
        messages = self.get_conversation(session_id)
        terms = ("承诺", "回访", "补发", "到账", "24小时", "明天")
        matches = [message for message in messages if any(term in str(message.get("message_text") or "") for term in terms)]
        return self._action_result("check_service_promises", "chat_messages", self._project("conversation", matches[-8:]), found=bool(matches))

    def list_tools(self, compact: bool = False, include_actions: bool = False) -> dict[str, Callable[..., Any]]:
        tools = {
            "get_order": self.get_order,
            "get_conversation": self.get_conversation,
            "get_customer_context": self.get_customer_context,
            "get_work_orders": self.get_work_orders,
        }
        if include_actions:
            tools.update({
                "get_order_info": self.get_order_info, "get_logistics_info": self.get_logistics_info,
                "get_refund_status": self.get_refund_status, "get_payment_status": self.get_payment_status,
                "get_return_status": self.get_return_status, "get_replacement_status": self.get_replacement_status,
                "get_ticket_status": self.get_ticket_status, "get_adverse_reaction_record": self.get_adverse_reaction_record,
                "get_service_history": self.get_service_history, "get_service_promises": self.get_service_promises,
                "summarize_customer_history": self.summarize_customer_history,
            })
        if not compact:
            return tools
        return {
            name: (lambda *args, _fn=fn, _name=name, **kwargs: self._project("order" if _name == "get_order" else "conversation" if _name == "get_conversation" else "work_orders" if _name == "get_work_orders" else "customer_context", _fn(*args, **kwargs)))
            for name, fn in tools.items()
        }
