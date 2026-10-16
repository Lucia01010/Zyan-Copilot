import unittest
from pathlib import Path

from app.action_registry import ACTION_DEFINITIONS, CAPABILITY_RESPONSE, classify_copilot_intent, execute_action, format_action_result, handle_copilot_chat, recommend_actions
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

    def test_history_summary_contains_required_sections(self):
        """summarize_customer_history 必须返回沟通次数/核心问题/时间线/承诺/建议，禁止只返回条数。"""
        result = execute_action(self.tools, "summarize_customer_history", "S00082")
        summary = format_action_result(result)
        self.assertIn("历史服务摘要", summary)
        self.assertIn("核心问题", summary)
        self.assertIn("时间线摘要", summary)
        self.assertIn("历史承诺", summary)
        self.assertIn("当前建议", summary)
        self.assertNotIn("已查到", summary)
        # 必须能回答：客户之前遇到了什么问题（核心问题段）
        self.assertTrue(any(kw in summary for kw in ("过敏", "物流", "退款", "退货", "常规", "工单", "赠品", "投诉")))

    def test_history_summary_empty_session_returns_honest_message(self):
        """无历史记录时返回'暂无历史服务记录'，禁止'未找到相关记录，我会进一步核实'。"""
        result = execute_action(self.tools, "summarize_customer_history", "SESSION_NOT_EXIST")
        summary = format_action_result(result)
        self.assertEqual(summary, "暂无历史服务记录。")
        self.assertNotIn("未找到", summary)
        self.assertNotIn("核实", summary)


class CopilotChatRoutingTests(unittest.TestCase):
    """原则 5 意图先行：能力咨询/未知意图禁止调用 business tool，业务查询才允许。"""

    @classmethod
    def setUpClass(cls):
        cls.tools = BusinessTools(Path(__file__).resolve().parents[1] / "data/beauty_cs_agent.sqlite3")

    def test_classification_rules(self):
        self.assertEqual(classify_copilot_intent("你能做什么"), "capability_question")
        self.assertEqual(classify_copilot_intent("你有什么功能"), "capability_question")
        self.assertEqual(classify_copilot_intent("介绍一下自己"), "capability_question")
        self.assertEqual(classify_copilot_intent("你可以帮助我什么"), "capability_question")
        self.assertEqual(classify_copilot_intent("帮我查一下物流"), "business_query")
        self.assertEqual(classify_copilot_intent("为什么这个客户风险这么高"), "risk_query")
        self.assertEqual(classify_copilot_intent("今天天气怎么样"), "unknown")
        self.assertEqual(classify_copilot_intent("   "), "unknown")

    def test_case1_capability_question_returns_intro_without_tools(self):
        response = handle_copilot_chat(self.tools, "S00082", "你能做什么")
        self.assertEqual(response["intent"], "capability_question")
        self.assertEqual(response["message"], CAPABILITY_RESPONSE)
        self.assertEqual(response["tools_used"], [])
        self.assertNotIn("未找到相关", response["message"])

    def test_case2_logistics_question_calls_logistics_tool(self):
        response = handle_copilot_chat(self.tools, "S00082", "帮我查一下物流")
        self.assertEqual(response["intent"], "business_query")
        self.assertEqual(response["tools_used"], ["get_logistics_info"])
        self.assertTrue(response["message"])

    def test_case3_risk_question_uses_customer_context(self):
        response = handle_copilot_chat(self.tools, "S00082", "为什么这个客户风险这么高")
        self.assertEqual(response["intent"], "risk_query")
        self.assertIn("get_customer_context", response["tools_used"])
        self.assertTrue(response["message"])

    def test_unknown_intent_gets_honest_reply_without_tool(self):
        response = handle_copilot_chat(self.tools, "S00082", "今天天气怎么样")
        self.assertEqual(response["intent"], "unknown")
        self.assertEqual(response["tools_used"], [])
        self.assertNotIn("未找到相关", response["message"])
        self.assertIn("暂时无法直接回答", response["message"])


if __name__ == "__main__":
    unittest.main()
