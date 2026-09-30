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

    def list_tools(self, compact: bool = False) -> dict[str, Callable[..., Any]]:
        tools = {
            "get_order": self.get_order,
            "get_conversation": self.get_conversation,
            "get_customer_context": self.get_customer_context,
            "get_work_orders": self.get_work_orders,
        }
        if not compact:
            return tools
        return {
            name: (lambda *args, _fn=fn, _name=name, **kwargs: self._project("order" if _name == "get_order" else "conversation" if _name == "get_conversation" else "work_orders" if _name == "get_work_orders" else "customer_context", _fn(*args, **kwargs)))
            for name, fn in tools.items()
        }
