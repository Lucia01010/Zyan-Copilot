"""M14 Planner & Action Router：规划输出结构、路由规则与四个核心 case。"""
import unittest
from pathlib import Path

from app.action_registry import ACTION_DEFINITIONS, handle_copilot_chat, registry_catalog
from app.business_tools import BusinessTools
from app.planner import build_plan, run_plan

DB_PATH = Path(__file__).resolve().parents[1] / "data/beauty_cs_agent.sqlite3"
SESSION = "S00082"


class PlannerOutputTests(unittest.TestCase):
    def test_plan_step_shape(self):
        plan = build_plan("帮我查一下物流")
        self.assertEqual(plan["mode"], "direct")
        self.assertEqual(len(plan["steps"]), 1)
        step = plan["steps"][0]
        self.assertEqual(set(step.keys()), {"action", "reason", "tool"})
        self.assertEqual(step["action"], "check_logistics")
        self.assertEqual(step["tool"], "get_logistics_info")
        self.assertTrue(step["reason"])

    def test_registry_catalog_is_complete(self):
        catalog = registry_catalog()
        self.assertEqual(len(catalog), len(ACTION_DEFINITIONS))
        for item in catalog:
            self.assertTrue(item["description"], item["action_id"])
            self.assertTrue(item["trigger_examples"], item["action_id"])
            self.assertTrue(item["required_context"], item["action_id"])
            self.assertTrue(item["tool"], item["action_id"])

    def test_multi_intent_question_plans_multiple_steps(self):
        plan = build_plan("物流一直没收到，退款什么时候到账")
        self.assertEqual(plan["mode"], "planned")
        actions = [step["action"] for step in plan["steps"]]
        self.assertIn("check_logistics", actions)
        self.assertIn("check_refund", actions)

    def test_memory_skips_already_executed_actions(self):
        memory = [{"steps": [{"action": "summarize_customer_history"}]}]
        plan = build_plan("我要投诉", memory=memory)
        actions = [step["action"] for step in plan["steps"]]
        self.assertNotIn("summarize_customer_history", actions)
        self.assertIn("assess_customer_risk", actions)

    def test_chitchat_and_empty_message_plan_no_tool(self):
        self.assertEqual(build_plan("今天天气怎么样")["steps"], [])
        self.assertEqual(build_plan("   ")["steps"], [])


class PlannerRouterCaseTests(unittest.TestCase):
    """用户指定的四个核心 case：物流 / 退款 / 投诉 / 能力询问。"""

    @classmethod
    def setUpClass(cls):
        cls.tools = BusinessTools(DB_PATH)

    def test_logistics_question_calls_logistics_tool(self):
        plan = build_plan("帮我查一下物流")
        self.assertEqual(plan["mode"], "direct")
        route = run_plan(self.tools, SESSION, plan)
        self.assertEqual(route["tools_used"], ["get_logistics_info"])
        self.assertTrue(route["message"])

    def test_refund_question_calls_refund_tool(self):
        plan = build_plan("退款什么时候到账")
        self.assertEqual([step["action"] for step in plan["steps"]], ["check_refund"])
        route = run_plan(self.tools, SESSION, plan)
        self.assertEqual(route["tools_used"], ["get_refund_status"])
        self.assertTrue(route["message"])

    def test_complaint_plans_history_plus_risk(self):
        plan = build_plan("我要投诉，这件事必须给我个说法")
        self.assertEqual(plan["mode"], "planned")
        self.assertEqual([step["action"] for step in plan["steps"]], ["summarize_customer_history", "assess_customer_risk"])
        route = run_plan(self.tools, SESSION, plan)
        self.assertIn("summarize_customer_history", route["tools_used"])
        self.assertIn("get_customer_context", route["tools_used"])
        self.assertIn("历史服务摘要", route["message"])
        self.assertIn("风险等级", route["message"])

    def test_capability_question_calls_no_tool(self):
        plan = build_plan("你能做什么")
        self.assertEqual(plan["mode"], "none")
        self.assertEqual(plan["steps"], [])
        route = run_plan(self.tools, SESSION, plan)
        self.assertEqual(route["tools_used"], [])

    def test_handle_copilot_chat_exposes_plan(self):
        response = handle_copilot_chat(self.tools, SESSION, "我要投诉")
        self.assertEqual(response["plan_mode"], "planned")
        self.assertEqual([step["action"] for step in response["plan"]], ["summarize_customer_history", "assess_customer_risk"])
        response = handle_copilot_chat(self.tools, SESSION, "你能做什么")
        self.assertEqual(response["plan_mode"], "none")
        self.assertEqual(response["tools_used"], [])


if __name__ == "__main__":
    unittest.main()
