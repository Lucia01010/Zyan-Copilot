import sqlite3
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from app.intent_taxonomy import IntentTaxonomy
from app.qwen_agent import AgentOutput, BeautyAgent, QwenProvider

ROOT = Path(__file__).resolve().parents[1]


class QwenAgentTests(unittest.TestCase):
    def test_provider_defaults_to_mock_without_credentials(self):
        provider = QwenProvider(mock=True)
        self.assertEqual(provider.provider, "mock")
        self.assertTrue(provider.mock)

    def test_free_only_limits_are_bounded(self):
        provider = QwenProvider(mock=True)
        self.assertTrue(provider.free_only)
        self.assertLessEqual(provider.max_tokens, 1024)
        self.assertLessEqual(provider.max_tool_rounds, 4)
        self.assertLessEqual(provider.tool_result_char_limit, 4000)

    def test_mock_provider_creates_suggestion_and_cost_record(self):
        db = ROOT / "data/beauty_cs_agent.sqlite3"
        with sqlite3.connect(db) as conn:
            buyer = conn.execute("SELECT buyer_nickname FROM chat_messages WHERE buyer_nickname IS NOT NULL LIMIT 1").fetchone()[0]
        result = BeautyAgent(db, QwenProvider(mock=True)).suggest(buyer_nickname=buyer)
        self.assertEqual(result.provider, "mock")
        self.assertTrue(result.suggestion)
        with sqlite3.connect(db) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM agent_runs WHERE run_id = ?", (result.run_id,)).fetchone()[0], 1)

    def test_mock_reply_uses_logistics_evidence(self):
        reply = QwenProvider._mock_suggested_reply({
            "recent_messages": [{"message_text": "物流怎么还没更新"}],
            "orders": [],
            "work_orders": [{"source_table": "logistics_work_orders", "carrier": "顺丰", "problem_tracking_number": "SF123", "work_order_status": "仓库处理中"}],
        }, {"findings": [], "level": "medium"})
        self.assertIn("SF123", reply)
        self.assertIn("仓库处理中", reply)

    def test_mock_reply_uses_refund_evidence(self):
        reply = QwenProvider._mock_suggested_reply({
            "recent_messages": [{"message_text": "退款什么时候到账"}],
            "orders": [],
            "work_orders": [{"source_table": "offline_payment_work_orders", "refund_amount_yuan": "8.8", "transfer_status": "转账成功"}],
        }, {"findings": [], "level": "medium"})
        self.assertIn("8.8", reply)
        self.assertIn("转账成功", reply)

    def test_mock_reply_for_adverse_reaction_escalates(self):
        reply = QwenProvider._mock_suggested_reply({
            "recent_messages": [{"message_text": "用了之后刺痛"}],
            "orders": [],
            "work_orders": [{"source_table": "adverse_reaction_work_orders", "work_order_number": "BL123", "symptom_description": "泛红刺痛"}],
        }, {"findings": [], "level": "critical"})
        self.assertIn("BL123", reply)
        self.assertIn("人工", reply)
        self.assertIn("暂停使用", reply)

    def test_mock_reply_without_fact_requests_verification(self):
        reply = QwenProvider._mock_suggested_reply({"recent_messages": [{"message_text": "可以帮我看一下吗"}], "orders": [], "work_orders": []}, {"findings": [], "level": "low"})
        self.assertIn("进一步核实", reply)

    def test_agent_workflow_exposes_tool_checks_and_reply_basis(self):
        db = ROOT / "data/beauty_cs_agent.sqlite3"
        with sqlite3.connect(db) as conn:
            conversation_id = conn.execute("SELECT conversation_id FROM chat_messages WHERE conversation_id IS NOT NULL LIMIT 1").fetchone()[0]
        result = BeautyAgent(db, QwenProvider(mock=True)).suggest(conversation_id=conversation_id)
        self.assertIsNotNone(result.workflow)
        self.assertIn("customer_need", result.workflow)
        self.assertIn("tool_checks", result.workflow)
        self.assertIn("reply_basis", result.workflow)
        self.assertIn("get_conversation", result.tool_calls)
        self.assertIn("get_work_orders", result.tool_calls)

    def test_logistics_reply_is_grounded_in_business_fact(self):
        db = ROOT / "data/beauty_cs_agent.sqlite3"
        with sqlite3.connect(db) as conn:
            row = conn.execute("SELECT conversation_id FROM chat_messages WHERE message_text LIKE '%物流%' OR message_text LIKE '%快递%' LIMIT 1").fetchone()
        if not row:
            self.skipTest("no logistics conversation in current source data")
        result = BeautyAgent(db, QwenProvider(mock=True)).suggest(conversation_id=row[0])
        self.assertTrue(result.suggestion)
        self.assertIn("get_work_orders", result.tool_calls)

    def test_refund_and_adverse_reply_generators_are_not_generic_template(self):
        refund = QwenProvider._mock_suggested_reply({"recent_messages": [{"message_text": "退款什么时候到账"}], "orders": [], "work_orders": [{"refund_amount_yuan": "8.8", "transfer_status": "转账成功"}]}, {"findings": [], "level": "medium"})
        adverse = QwenProvider._mock_suggested_reply({"recent_messages": [{"message_text": "用了之后刺痛"}], "orders": [], "work_orders": [{"source_table": "adverse_reaction_work_orders", "work_order_number": "BL123", "symptom_description": "泛红刺痛"}]}, {"findings": [], "level": "critical"})
        self.assertNotEqual(refund, "感谢您的说明。我已结合订单和历史记录整理了情况，接下来会为您核对并尽快回复。")
        self.assertNotEqual(adverse, "感谢您的说明。我已结合订单和历史记录整理了情况，接下来会为您核对并尽快回复。")
        self.assertIn("转账成功", refund)
        self.assertIn("暂停使用", adverse)

    def test_structured_output_parser_accepts_fence_and_prose(self):
        payload = '{"intent":"售后","emotion":"关注","summary":"ok","evidence":[],"risk_level":"low","suggested_reply":"收到"}'
        self.assertEqual(QwenProvider._parse_json("```json\n" + payload + "\n```" )["risk_level"], "low")
        self.assertEqual(QwenProvider._parse_json("前置说明\n" + payload + "\n结束" )["intent"], "售后")

    def test_structured_output_validation_defaults_optional_fields(self):
        value = AgentOutput(intent="售后", emotion="关注", summary="ok", evidence=[], risk_level="low", suggested_reply="收到")
        self.assertEqual(value.tools_used, [])
        self.assertTrue(QwenProvider._validate_output(value.model_dump()))

    def test_structured_output_validation_rejects_invalid_enum_and_truncation(self):
        invalid = {"intent":"售后","emotion":"关注","summary":"ok","evidence":[],"risk_level":"urgent","suggested_reply":"收到"}
        self.assertFalse(QwenProvider._validate_output(invalid))
        self.assertEqual(QwenProvider._parse_json('{"intent":"售后"'), {})
        self.assertTrue(QwenProvider._repair_eligible("前置说明 {\"intent\":\"售后\"}", invalid))
        self.assertFalse(QwenProvider._repair_eligible("", {}))

    def test_agent_output_compression_limits(self):
        base = {"intent":"售后","emotion":"关注","summary":"ok","evidence":[],"risk_level":"low","suggested_reply":"收到"}
        self.assertTrue(QwenProvider._validate_output(base))
        self.assertFalse(QwenProvider._validate_output({**base, "summary": "x" * 181}))
        self.assertFalse(QwenProvider._validate_output({**base, "evidence": [{}] * 7}))
        self.assertFalse(QwenProvider._validate_output({**base, "recommended_actions": ["x"] * 6}))
        self.assertFalse(QwenProvider._validate_output({**base, "suggested_reply": "x" * 301}))

    def test_length_finish_reason_does_not_make_repair_eligible(self):
        self.assertFalse(QwenProvider._repair_allowed("length", "{\"intent\":\"售后\"}", {"intent": "售后"}))
        self.assertTrue(QwenProvider._repair_allowed("stop", "前置说明 {\"intent\":\"售后\"}", {"intent": "售后"}))

    def test_intent_taxonomy_exact_alias_and_invalid_pair(self):
        taxonomy = IntentTaxonomy({"产品咨询": ("套装搭配推荐",), "物流异常": ("显示签收未收到",)})
        self.assertEqual(taxonomy.normalize(" 产品咨询 ", "套装 搭配推荐"), ("产品咨询", "套装搭配推荐"))
        self.assertEqual(taxonomy.map_text("显示签收未收到"), ("物流异常", "显示签收未收到"))
        self.assertIsNone(taxonomy.normalize("产品咨询", "显示签收未收到"))
        self.assertIsNone(taxonomy.map_text("未知业务"))

    def test_json_schema_payload_is_strict_and_tool_free_for_final(self):
        provider = QwenProvider(mock=True)
        provider.provider = "qwen"
        provider.mock = False
        provider.api_key = "test-only"

        class Response:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self): return json.dumps({"choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}]}).encode()

        with patch("urllib.request.urlopen", return_value=Response()) as opened:
            provider._request([], [], response_format={"type": "json_schema", "json_schema": {"name": "agent_output", "schema": provider._api_schema(), "strict": True}}, stage="final_synthesis")
        payload = json.loads(opened.call_args.args[0].data.decode())
        self.assertEqual(payload["model"], provider.model)
        self.assertEqual(payload["response_format"]["type"], "json_schema")
        self.assertTrue(payload["response_format"]["json_schema"]["strict"])
        self.assertEqual(payload["tools"], [])
        self.assertEqual(payload["tool_choice"], "none")
        self.assertFalse(payload["enable_thinking"])
        self.assertFalse(payload["stream"])
        self.assertNotIn("test-only", json.dumps(payload))

    def test_prompts_are_externalized_and_placeholder_replaced(self):
        from app.qwen_agent import PROMPTS_DIR, load_prompt

        for name in ("stage_a_tools", "final_synthesis", "json_repair"):
            path = PROMPTS_DIR / f"{name}.txt"
            self.assertTrue(path.is_file(), f"missing prompt template: {path}")
            template = load_prompt(name, schema_contract='{"test": true}')
            self.assertTrue(template.strip(), f"empty prompt template: {name}")
            self.assertNotIn("{schema_contract}", template, f"placeholder not replaced: {name}")
        stage_a = load_prompt("stage_a_tools")
        self.assertIn("美妆客服辅助 Agent", stage_a)
        self.assertIn("阶段 A", stage_a)

