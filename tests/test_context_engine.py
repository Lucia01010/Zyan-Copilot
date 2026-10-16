"""M12 Context Engine：字段真实性、白名单投影、客户 A/B 隔离。"""
import unittest
from pathlib import Path

from app.context_engine import AgentContext, ContextEngine, _compact

DB_PATH = Path("data/beauty_cs_agent.sqlite3")

# DATA_CONTEXT_MAP.md 中实测存在的字段；任何超出此集合的键都视为幻觉字段
_ORDER_FIELDS = {"order_number", "product_name", "product_sku", "quantity", "order_status", "paid_amount_yuan", "carrier", "tracking_number", "gift", "buyer_note"}
_MESSAGE_FIELDS = {"message_sequence", "sent_at", "role", "message_text", "order_number", "work_order_number"}
_WORK_ORDER_FIELDS = {"source_table", "work_order_number", "work_order_type", "work_order_status", "after_sales_reason", "reaction_type", "symptom_description", "issue_type", "carrier", "problem_tracking_number", "refund_amount_yuan", "transfer_status", "resolution"}


def _walk(value):
    """递归遍历所有 dict 节点。"""
    if isinstance(value, dict):
        yield value
        for v in value.values():
            yield from _walk(v)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


class CompactTests(unittest.TestCase):
    def test_compact_drops_none_and_empty(self):
        result = _compact({"a": None, "b": "", "c": [], "d": {"x": None}, "e": 0, "f": "文本"})
        self.assertEqual(result, {"e": 0, "f": "文本"})


class ContextEngineBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = ContextEngine(DB_PATH)

    def test_session_entry_builds_full_context(self):
        ctx = self.engine.build(conversation_id="S00082")
        self.assertEqual(ctx.session.conversation_id, "S00082")
        self.assertEqual(ctx.customer.buyer_nickname, "方b**")
        self.assertGreater(ctx.session.message_count, 0)
        self.assertGreaterEqual(ctx.customer.order_count, 1)
        self.assertIn("level", ctx.risk)
        self.assertTrue(ctx.available_tools)

    def test_six_sections_present_in_payload(self):
        payload = self.engine.build(conversation_id="S00082").as_dict()
        for key in ("customer", "session", "orders", "service_history", "risk", "available_tools"):
            self.assertIn(key, payload)

    def test_unknown_session_degrades_safely(self):
        ctx = self.engine.build(conversation_id="S99999_NOT_EXIST")
        self.assertEqual(ctx.session.conversation_id, "S99999_NOT_EXIST")
        self.assertEqual(ctx.session.message_count, 0)
        self.assertIsNone(ctx.customer.buyer_nickname)
        self.assertTrue(ctx.available_tools)

    def test_no_fake_or_empty_fields_in_payload(self):
        payload = self.engine.build(conversation_id="S00082").as_dict()
        for node in _walk(payload):
            for key, value in node.items():
                self.assertIsNotNone(value, f"None 字段泄漏: {key}")
                if isinstance(value, str):
                    self.assertNotEqual(value.strip(), "", f"空字符串字段泄漏: {key}")

    def test_field_whitelists(self):
        ctx = self.engine.build(conversation_id="S00082")
        for order in ctx.orders:
            self.assertLessEqual(set(order), _ORDER_FIELDS, f"订单出现白名单外字段: {set(order) - _ORDER_FIELDS}")
        for message in ctx.session.recent_messages:
            self.assertLessEqual(set(message), _MESSAGE_FIELDS, f"消息出现白名单外字段: {set(message) - _MESSAGE_FIELDS}")
        for ticket in ctx.service_history.work_orders:
            self.assertLessEqual(set(ticket), _WORK_ORDER_FIELDS, f"工单出现白名单外字段: {set(ticket) - _WORK_ORDER_FIELDS}")


class ContextIsolationTests(unittest.TestCase):
    """客户 A/B 切换：Context 严格按买家隔离，不串线。"""

    @classmethod
    def setUpClass(cls):
        cls.engine = ContextEngine(DB_PATH)
        cls.ctx_a = cls.engine.build(conversation_id="S00082")  # 方b**
        cls.ctx_b = cls.engine.build(conversation_id="S00002")  # 冯h**

    def test_buyers_are_distinct(self):
        self.assertEqual(self.ctx_a.customer.buyer_nickname, "方b**")
        self.assertEqual(self.ctx_b.customer.buyer_nickname, "冯h**")

    def test_messages_belong_only_to_own_buyer(self):
        for message in self.ctx_a.raw_context["messages"]:
            self.assertEqual(message.get("buyer_nickname"), "方b**")
        for message in self.ctx_b.raw_context["messages"]:
            self.assertEqual(message.get("buyer_nickname"), "冯h**")

    def test_orders_do_not_cross_buyers(self):
        orders_a = {o.get("order_number") for o in self.ctx_a.raw_context["orders"]}
        orders_b = {o.get("order_number") for o in self.ctx_b.raw_context["orders"]}
        self.assertFalse(orders_a & orders_b, f"订单串线: {orders_a & orders_b}")
        for order in self.ctx_a.raw_context["orders"]:
            self.assertEqual(order.get("buyer_nickname"), "方b**")

    def test_work_orders_do_not_cross_buyers(self):
        for ticket in self.ctx_b.raw_context["work_orders"]:
            self.assertEqual(ticket.get("buyer_nickname"), "冯h**")

    def test_anchor_session_not_in_other_sessions(self):
        self.assertNotIn("S00082", self.ctx_a.service_history.other_sessions)
        self.assertNotIn("S00002", self.ctx_b.service_history.other_sessions)

    def test_risk_isolated_per_customer(self):
        self.assertIsInstance(self.ctx_a.risk.get("level"), str)
        self.assertIsInstance(self.ctx_b.risk.get("level"), str)


if __name__ == "__main__":
    unittest.main()
