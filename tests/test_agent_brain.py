"""M16 Agent Brain 集成测试：Context / Memory / Planner / Router / RAG / Grounding。

四个验收场景：
1. 物流咨询    → 必须使用 context + tool
2. 历史投诉    → 必须使用 memory
3. 产品使用问题 → 必须使用 RAG
4. 复杂投诉    → 必须使用 planner（多步规划）

外加 Response Grounding Check：回答必须有依据，禁止无证据业务事实。
"""
import unittest
from pathlib import Path
from unittest.mock import patch

from app.agent_brain import GROUNDING_FALLBACK, SessionMemory, grounding_check, process_message
from app.action_registry import CAPABILITY_RESPONSE
from app.business_tools import BusinessTools
from app.context_engine import ContextEngine
from app.knowledge_base import KnowledgeStore

DB_PATH = Path(__file__).resolve().parents[1] / "data/beauty_cs_agent.sqlite3"


class AgentBrainPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tools = BusinessTools(DB_PATH)
        cls.engine = ContextEngine(DB_PATH)
        cls.store = KnowledgeStore(DB_PATH, Path(__file__).resolve().parents[1] / "knowledge")
        cls.store.ensure_index()

    def test_scenario1_logistics_uses_context_and_tool(self):
        result = process_message(self.tools, "S00082", "物流到哪了", knowledge_store=self.store, context_engine=self.engine, memory=SessionMemory())
        self.assertEqual(result["intent"], "business_query")
        # context：按会话锚定装配
        self.assertEqual(result["context_used"]["session"]["conversation_id"], "S00082")
        self.assertTrue(result["context_used"]["customer"].get("buyer_nickname"))
        # tool：物流查询被执行
        self.assertIn("get_logistics_info", result["tools_used"])
        self.assertEqual(result["plan_mode"], "direct")
        # grounding：回答有依据
        self.assertTrue(result["grounding"]["grounded"])

    def test_scenario2_history_complaint_uses_memory(self):
        memory = SessionMemory()
        first = process_message(self.tools, "S00082", "这个客户又来投诉了", knowledge_store=self.store, context_engine=self.engine, memory=memory)
        self.assertEqual(first["plan_mode"], "planned")
        self.assertIn("summarize_customer_history", first["tools_used"])
        # memory：服务历史摘要被检索
        self.assertTrue(any(entry["type"] == "service_history" and entry.get("buyer_nickname") for entry in first["memory_used"]))
        # 下一轮：memory 中的历史 plan 生效，不重复规划已执行行动
        second = process_message(self.tools, "S00082", "这个客户还在投诉", knowledge_store=self.store, context_engine=self.engine, memory=memory)
        self.assertTrue(any(entry["type"] == "past_turns" and entry["count"] == 1 for entry in second["memory_used"]))
        self.assertEqual([step["action"] for step in second["plan"]], ["assess_customer_risk"])

    def test_scenario3_product_usage_question_uses_rag(self):
        result = process_message(self.tools, "S00082", "修护精华液怎么使用", knowledge_store=self.store, context_engine=self.engine, memory=SessionMemory())
        self.assertEqual(result["intent"], "knowledge_query")
        self.assertIn("search_knowledge", result["tools_used"])
        self.assertIn("参考来源", result["message"])
        self.assertIn("2-3 滴", result["message"])
        self.assertTrue(result["grounding"]["grounded"])

    def test_scenario4_complex_complaint_uses_planner(self):
        result = process_message(self.tools, "S00082", "我要投诉", knowledge_store=self.store, context_engine=self.engine, memory=SessionMemory())
        self.assertEqual(result["plan_mode"], "planned")
        self.assertEqual(len(result["plan"]), 2)
        self.assertEqual(result["plan"][0]["action"], "summarize_customer_history")
        self.assertEqual(result["plan"][1]["action"], "assess_customer_risk")
        self.assertIn("summarize_customer_history", result["tools_used"])
        self.assertIn("get_customer_context", result["tools_used"])
        self.assertIn("历史服务摘要", result["message"])

    def test_capability_question_answers_directly_without_tools(self):
        result = process_message(self.tools, "S00082", "你能做什么", knowledge_store=self.store, context_engine=self.engine, memory=SessionMemory())
        self.assertEqual(result["message"], CAPABILITY_RESPONSE)
        self.assertEqual(result["tools_used"], [])
        self.assertEqual(result["plan_mode"], "none")
        self.assertTrue(result["grounding"]["grounded"])

    def test_not_found_reply_is_honest_and_grounded(self):
        result = process_message(self.tools, "SESSION_NOT_EXIST", "退款到账了吗", knowledge_store=self.store, context_engine=self.engine, memory=SessionMemory())
        self.assertEqual(result["tools_used"], ["get_refund_status"])
        self.assertIn("未找到相关业务记录", result["message"])
        self.assertNotIn("参考来源", result["message"])
        # 未知会话无任何记忆可检索
        self.assertEqual(result["memory_used"], [])
        self.assertTrue(result["grounding"]["grounded"])

    def test_grounding_failure_replaces_reply_with_honest_fallback(self):
        fabricated = {"tools_used": ["get_logistics_info"], "results": [{"status": "OK", "data": {}, "action_id": "check_logistics"}], "evidence": [], "message": "您的运单 SF1678898618989 已签收"}
        from app import agent_brain
        with patch.object(agent_brain, "run_plan", return_value=fabricated):
            result = agent_brain.process_message(self.tools, "S00082", "物流到哪了", knowledge_store=self.store, context_engine=self.engine, memory=SessionMemory())
        self.assertFalse(result["grounding"]["grounded"])
        self.assertIn("SF1678898618989", result["grounding"]["ungrounded_facts"])
        self.assertEqual(result["message"], GROUNDING_FALLBACK)


class GroundingCheckTests(unittest.TestCase):
    def test_ungrounded_business_fact_is_rejected(self):
        result = grounding_check("您的退款 881234567890 已到账，金额 128.00 元", [{"status": "OK", "data": {"work_orders": []}}])
        self.assertFalse(result["grounded"])
        self.assertIn("881234567890", result["ungrounded_facts"])

    def test_fact_without_any_ok_evidence_is_rejected(self):
        result = grounding_check("运单 SF1678898618989 已签收", [{"status": "NOT_FOUND", "data": {}}])
        self.assertFalse(result["grounded"])
        self.assertEqual(result["evidence_count"], 0)

    def test_fact_backed_by_evidence_passes(self):
        result = grounding_check("物流单号 SF1678898618989", [{"status": "OK", "data": {"tracking_number": "SF1678898618989"}}])
        self.assertTrue(result["grounded"])
        self.assertEqual(result["ungrounded_facts"], [])

    def test_reply_without_facts_passes_vacuously(self):
        result = grounding_check("未找到相关业务记录，我会帮您进一步核实。", [])
        self.assertTrue(result["grounded"])
        self.assertEqual(result["checked_facts"], [])


if __name__ == "__main__":
    unittest.main()
