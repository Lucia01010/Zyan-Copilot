import unittest
from pathlib import Path

from app.action_registry import ACTION_DEFINITIONS, execute_action, format_action_result, recommend_actions
from app.business_tools import BusinessTools


class ActionRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tools = BusinessTools(Path(__file__).resolve().parents[1] / "data/beauty_cs_agent.sqlite3")
        cls.session_a = cls.tools.get_conversation("S00082")
        cls.session_b = cls.tools.get_conversation("S00362")

    def test_registry_contains_only_named_executable_actions(self):
        self.assertGreaterEqual(len(ACTION_DEFINITIONS), 8)
        self.assertEqual(len({item.action_id for item in ACTION_DEFINITIONS}), len(ACTION_DEFINITIONS))
        self.assertTrue(all(item.tool_name for item in ACTION_DEFINITIONS))

    def test_recommendations_are_bounded_and_available(self):
        actions = recommend_actions(self.tools, "S00082")
        self.assertLessEqual(len(actions), 4)
        self.assertTrue(all(item["available"] for item in actions))
        self.assertIn("check_adverse_reaction", {item["action_id"] for item in actions})

    def test_action_result_is_grounded_and_session_isolated(self):
        first = execute_action(self.tools, "check_adverse_reaction", "S00082")
        second = execute_action(self.tools, "check_order", "S00362")
        self.assertEqual(first["session_id"], "S00082")
        self.assertEqual(second["session_id"], "S00362")
        self.assertEqual(first["source"], "adverse_reaction_work_orders")
        self.assertNotEqual(first["session_id"], second["session_id"])

    def test_missing_records_are_explicit(self):
        result = execute_action(self.tools, "check_logistics", "S00082")
        self.assertIn(result["status"], {"OK", "NOT_FOUND"})
        if result["status"] == "NOT_FOUND":
            self.assertEqual(result["data"], {})

    def test_tool_failure_returns_structured_error_payload(self):
        definition = next(item for item in ACTION_DEFINITIONS if item.action_id == "check_order")

        class FailingTools:
            pass

        setattr(FailingTools, definition.tool_name, lambda self, session_id: (_ for _ in ()).throw(RuntimeError("database is locked")))
        result = execute_action(FailingTools(), "check_order", "S00082")
        self.assertEqual(result["status"], "ERROR")
        self.assertEqual(result["session_id"], "S00082")
        self.assertEqual(result["action_id"], "check_order")
        error = result["error"]
        self.assertEqual(error["error_type"], "RuntimeError")
        self.assertIn(definition.tool_name, error["error_summary"])
        self.assertIn("进一步核实", error["suggestion"])
        self.assertNotIn("offending_parameter", error)

    def test_error_payload_gets_honest_user_message(self):
        failing = {"status": "ERROR", "data": {}, "error": {"error_type": "RuntimeError"}, "action_id": "check_order", "tool_name": "get_order_context", "session_id": "S00082"}
        self.assertEqual(format_action_result(failing), "业务查询服务暂时异常，我会记录问题并尽快核实后给您答复。")


if __name__ == "__main__":
    unittest.main()
