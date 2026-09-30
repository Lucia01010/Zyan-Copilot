import sqlite3
import unittest
from pathlib import Path

from app.business_tools import BusinessTools, ToolInputError
from app.risk_engine import assess_context
from app.hybrid_risk import hybrid_risk


ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data/beauty_cs_agent.sqlite3"


class BusinessToolsTests(unittest.TestCase):
    def test_order_and_conversation_tools_return_structured_data(self):
        tools = BusinessTools(DB)
        with sqlite3.connect(DB) as conn:
            order_number, conversation_id = conn.execute("SELECT order_number, conversation_id FROM orders LIMIT 1").fetchone()
        order = tools.get_order(order_number)
        self.assertEqual(order["order_number"], order_number)
        self.assertGreater(len(tools.get_conversation(conversation_id)), 0)
        self.assertEqual(set(tools.list_tools()), {"get_order", "get_conversation", "get_customer_context", "get_work_orders"})

    def test_tools_reject_missing_required_inputs(self):
        with self.assertRaises(ToolInputError):
            BusinessTools(DB).get_order("")

    def test_compact_tools_project_only_relevant_fields(self):
        tools = BusinessTools(DB)
        with sqlite3.connect(DB) as conn:
            order_number = conn.execute("SELECT order_number FROM orders LIMIT 1").fetchone()[0]
        projected = tools.list_tools(compact=True)["get_order"](order_number)
        self.assertIn("order_number", projected)
        self.assertNotIn("buyer_note", projected)


class RiskEngineTests(unittest.TestCase):
    def test_adverse_reaction_is_critical_and_explainable(self):
        result = assess_context({"messages": [], "orders": [], "work_orders": [{"source_table": "adverse_reaction_work_orders", "work_order_number": "W1"}]})
        self.assertEqual(result["level"], "critical")
        self.assertTrue(result["requires_human_review"])
        self.assertEqual(result["findings"][0]["rule_id"], "adverse_reaction")

    def test_emotion_escalation_is_high(self):
        result = assess_context({"messages": [{"message_text": "我要投诉，太失望了"}], "orders": [], "work_orders": []})
        self.assertEqual(result["level"], "high")
        self.assertIn("投诉", result["findings"][0]["evidence"]["matched_terms"])

    def test_hybrid_risk_applies_hard_floor_without_overwriting_sources(self):
        result = hybrid_risk({"messages": [{"message_text": "历史承诺回访尚未完成"}]}, "low", "medium", [{"rule_id": "long_conversation", "level": "medium"}])
        self.assertEqual(result["model_risk"], "low")
        self.assertEqual(result["rule_risk"], "medium")
        self.assertEqual(result["rule_floor"], "medium")
        self.assertEqual(result["final_risk"], "medium")

    def test_hybrid_adverse_reaction_floor_is_high(self):
        result = hybrid_risk({"messages": []}, "low", "critical", [{"rule_id": "adverse_reaction", "level": "critical"}])
        self.assertEqual(result["rule_floor"], "high")
        self.assertEqual(result["final_risk"], "high")

    def test_case_c_disagreement_is_preserved_without_label_hardcoding(self):
        result = hybrid_risk(
            {"messages": [{"message_text": "客户再次进线，询问此前承诺的回访是否完成"}]},
            "medium",
            "critical",
            [{"rule_id": "long_conversation", "level": "medium"}],
        )
        self.assertEqual(result["model_risk"], "medium")
        self.assertEqual(result["rule_risk"], "critical")
        self.assertEqual(result["rule_floor"], "medium")
        self.assertEqual(result["final_risk"], "medium")
