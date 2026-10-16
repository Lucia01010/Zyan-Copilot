"""M20 Conversation State Machine + M21 Agent Evaluation + M19 Tool Governance 增量测试。"""
import json
import tempfile
import unittest
from pathlib import Path

from app.action_registry import ACTION_DEFINITIONS, REGISTRY_BY_ID, registry_catalog
from app.agent_brain import SessionMemory, process_message
from app.agent_evaluation import THRESHOLDS, evaluate_agent, load_gold_cases
from app.business_tools import BusinessTools
from app.context_engine import ContextEngine
from app.conversation_state import ConversationStateMachine, derive_stage
from app.knowledge_base import KnowledgeStore

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data/beauty_cs_agent.sqlite3"


class ToolGovernanceTests(unittest.TestCase):
    """M19 增量：工具显式输入契约。"""

    def test_every_action_has_input_schema(self):
        for definition in ACTION_DEFINITIONS:
            schema = definition.input_schema
            self.assertEqual(schema["type"], "object")
            self.assertEqual(schema["required"], list(definition.required_context))
            for name in definition.required_context:
                self.assertIn(name, schema["properties"])

    def test_catalog_exposes_input_schema(self):
        for entry in registry_catalog():
            self.assertIn("input_schema", entry)
            self.assertEqual(entry["input_schema"]["required"], entry["required_context"])
        self.assertIn("question_text（用户问题原文）", REGISTRY_BY_ID["search_knowledge_base"].input_schema["required"])


class ConversationStateTests(unittest.TestCase):
    """M20：状态持久化、阶段推导、指代消解。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.sm = ConversationStateMachine(str(Path(self._tmp.name) / "state.sqlite3"))

    def tearDown(self):
        self._tmp.cleanup()

    def test_transition_and_get_roundtrip(self):
        self.assertIsNone(self.sm.get("S1"))
        self.sm.transition("S1", "processing", "business_query", ["check_logistics"])
        state = self.sm.get("S1")
        self.assertEqual(state["stage"], "processing")
        self.assertEqual(state["last_actions"], ["check_logistics"])
        self.sm.transition("S1", "awaiting_feedback", "business_query", ["check_refund"])
        self.assertEqual(self.sm.get("S1")["stage"], "awaiting_feedback")

    def test_unknown_stage_rejected(self):
        with self.assertRaises(ValueError):
            self.sm.transition("S1", "unknown_stage")

    def test_follow_up_inherits_last_action(self):
        self.sm.transition("S1", "processing", "business_query", ["check_refund"])
        self.assertEqual(self.sm.follow_up_action("S1", "怎么样了"), "check_refund")
        self.assertEqual(self.sm.follow_up_action("S1", "还没好吗"), "check_refund")
        # 无状态/无行动/非业务意图不继承
        self.assertIsNone(self.sm.follow_up_action("S2", "怎么样了"))
        self.sm.transition("S3", "new", "capability_question", [])
        self.assertIsNone(self.sm.follow_up_action("S3", "怎么样了"))

    def test_derive_stage_rules(self):
        self.assertEqual(derive_stage("capability_question", []), "new")
        self.assertEqual(derive_stage("unknown", []), "new")
        self.assertEqual(derive_stage("business_query", [{"status": "NOT_FOUND"}]), "awaiting_feedback")
        self.assertEqual(derive_stage("business_query", [{"status": "OK"}]), "processing")


class StateMachineEndToEndTests(unittest.TestCase):
    """M20 接入管线：'退款到账了吗' → '怎么样了' 追问继承上一轮退款查询，不重新开始。"""

    @classmethod
    def setUpClass(cls):
        cls.tools = BusinessTools(DB_PATH)
        cls.engine = ContextEngine(DB_PATH)
        cls.store = KnowledgeStore(DB_PATH, ROOT / "knowledge")
        cls.store.ensure_index()

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.sm = ConversationStateMachine(str(Path(self._tmp.name) / "state.sqlite3"))

    def tearDown(self):
        self._tmp.cleanup()

    def test_follow_up_reuses_last_business_action(self):
        first = process_message(self.tools, "S00082", "退款到账了吗", knowledge_store=self.store, context_engine=self.engine, memory=SessionMemory(), state_machine=self.sm)
        self.assertEqual(first["tools_used"], ["get_refund_status"])
        self.assertEqual(self.sm.get("S00082")["last_actions"], ["check_refund"])
        follow = process_message(self.tools, "S00082", "怎么样了", knowledge_store=self.store, context_engine=self.engine, memory=SessionMemory(), state_machine=self.sm)
        self.assertTrue(follow["state"]["follow_up"])
        self.assertEqual(follow["tools_used"], ["get_refund_status"])
        self.assertEqual(follow["plan"][0]["action"], "check_refund")

    def test_state_persists_in_sqlite_table(self):
        process_message(self.tools, "S00082", "物流到哪了", knowledge_store=self.store, context_engine=self.engine, memory=SessionMemory(), state_machine=self.sm)
        # 新实例读取同一库 → 状态跨实例存活（跨重启）
        sm2 = ConversationStateMachine(self.sm.db_path)
        state = sm2.get("S00082")
        self.assertEqual(state["last_intent"], "business_query")
        self.assertIn("check_logistics", state["last_actions"])


class AgentEvaluationTests(unittest.TestCase):
    """M21：四指标评估达到基线阈值。"""

    @classmethod
    def setUpClass(cls):
        cls.report = evaluate_agent(DB_PATH, ROOT / "knowledge")

    def test_gold_cases_well_formed(self):
        cases = load_gold_cases()
        self.assertGreaterEqual(len(cases["tool_cases"]), 5)
        self.assertGreaterEqual(len(cases["retrieval_cases"]), 3)
        for case in cases["tool_cases"]:
            self.assertIn("session_id", case)
            self.assertIn("message", case)
            self.assertIn("expected_tools", case)
            self.assertIn("forbidden_tools", case)

    def test_metrics_meet_thresholds(self):
        metrics = self.report["metrics"]
        self.assertGreaterEqual(metrics["tool_accuracy"], THRESHOLDS["tool_accuracy"])
        self.assertGreaterEqual(metrics["retrieval_accuracy"], THRESHOLDS["retrieval_accuracy"])
        self.assertLessEqual(metrics["hallucination_rate"], THRESHOLDS["hallucination_rate"])
        self.assertGreaterEqual(metrics["memory_accuracy"], THRESHOLDS["memory_accuracy"])
        self.assertTrue(self.report["all_passed"], json.dumps(self.report["details"], ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
