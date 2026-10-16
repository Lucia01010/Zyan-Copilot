"""M15 RAG Knowledge Brain：摄入/embedding/检索、知识路由与"RAG 不覆盖订单事实"边界。"""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.action_registry import classify_copilot_intent, format_action_result, handle_copilot_chat
from app.business_tools import BusinessTools
from app.knowledge_base import EMBED_DIM, KnowledgeStore, embed
from app.planner import build_plan, run_plan

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data/beauty_cs_agent.sqlite3"
KNOWLEDGE_DIR = ROOT / "knowledge"
SESSION = "S00082"


class EmbeddingTests(unittest.TestCase):
    def test_embedding_is_deterministic_and_normalized(self):
        left = embed("修护精华液的使用方法")
        right = embed("修护精华液的使用方法")
        self.assertEqual(left, right)
        self.assertEqual(len(left), EMBED_DIM)
        self.assertAlmostEqual(sum(v * v for v in left) ** 0.5, 1.0, places=6)

    def test_different_texts_differ(self):
        self.assertNotEqual(embed("退货退款规则"), embed("粉底液色号怎么选"))


class IngestionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.db_path = self.tmp_path / "test_kb.sqlite3"
        self.docs = self.tmp_path / "docs"
        self.docs.mkdir()
        (self.docs / "p.md").write_text("# 产品知识\n\n## 精华用法\n\n早晚洁面后取 2-3 滴轻拍吸收。\n\n## 保质期\n\n未开封三年，开封后六个月。\n", encoding="utf-8")
        (self.docs / "r.md").write_text("# 售后规则\n\n## 退货条件\n\n七天内且不影响二次销售。\n", encoding="utf-8")
        self.store = KnowledgeStore(self.db_path, self.docs)

    def tearDown(self):
        self.tmp.cleanup()

    def test_index_builds_and_persists(self):
        indexed = self.store.ensure_index()
        self.assertEqual(indexed, {"p.md": 2, "r.md": 1})
        self.assertEqual(self.store.count(), 3)
        # 新连接同库可读：持久化生效
        reopened = KnowledgeStore(self.db_path, self.docs)
        self.assertEqual(reopened.count(), 3)

    def test_reindex_is_idempotent(self):
        self.store.ensure_index()
        first = {(c.chunk_id, c.text) for c in self.store.search("精华", top_k=10, score_threshold=-1)}
        self.store.ensure_index()
        second = {(c.chunk_id, c.text) for c in self.store.search("精华", top_k=10, score_threshold=-1)}
        self.assertEqual(first, second)

    def test_changed_file_reindexed_and_removed_file_cleaned(self):
        self.store.ensure_index()
        (self.docs / "p.md").write_text("# 产品知识\n\n## 面霜用法\n\n晚间取面霜薄涂全脸。\n", encoding="utf-8")
        indexed = self.store.ensure_index()
        self.assertEqual(indexed["p.md"], 1)
        self.assertTrue(any("面霜" in c.text for c in self.store.search("面霜", top_k=5)))
        (self.docs / "r.md").unlink()
        self.store.ensure_index()
        self.assertEqual({c.domain for c in self.store.search("退货条件", top_k=10)} - {"p"}, set())

    def test_no_match_returns_empty(self):
        self.store.ensure_index()
        self.assertEqual(self.store.search("区块链量子计算股票"), [])


class RetrievalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = KnowledgeStore(DB_PATH, KNOWLEDGE_DIR)
        cls.store.ensure_index()

    def test_product_usage_question_hits_dedicated_section(self):
        hits = self.store.search("修护精华液怎么使用")
        self.assertTrue(hits)
        self.assertEqual(hits[0].domain, "product_knowledge")
        self.assertIn("修护精华液", hits[0].section + hits[0].text)
        self.assertIn("使用", hits[0].section)

    def test_policy_question_hits_after_sales_domain(self):
        hits = self.store.search("退货需要满足什么条件")
        self.assertTrue(hits)
        self.assertIn("after_sales_rules", {h.domain for h in hits})

    def test_shelf_life_question_hits_product_knowledge(self):
        hits = self.store.search("产品保质期多久")
        self.assertEqual(hits[0].domain, "product_knowledge")
        self.assertIn("保质期", hits[0].section)


class RoutingBoundaryTests(unittest.TestCase):
    def test_knowledge_intent_classification(self):
        self.assertEqual(classify_copilot_intent("修护精华液怎么使用"), "knowledge_query")
        self.assertEqual(classify_copilot_intent("退货需要满足什么条件"), "knowledge_query")
        self.assertEqual(classify_copilot_intent("产品保质期多久"), "knowledge_query")

    def test_business_fact_intent_stays_business(self):
        self.assertEqual(classify_copilot_intent("帮我查一下物流"), "business_query")
        self.assertEqual(classify_copilot_intent("退款什么时候到账"), "business_query")
        self.assertEqual(classify_copilot_intent("我的订单退款到账了吗"), "business_query")

    def test_product_word_in_order_question_does_not_escape_to_rag(self):
        # 提到产品名但问的是具体订单事实：业务工具优先，RAG 不得接管
        self.assertEqual(classify_copilot_intent("我买的修护精华液订单退款到账了吗"), "business_query")
        plan = build_plan("我买的修护精华液订单退款到账了吗")
        self.assertEqual([s["action"] for s in plan["steps"]], ["check_refund"])

    def test_capability_and_chitchat_remain_tool_free(self):
        self.assertEqual(classify_copilot_intent("你能做什么"), "capability_question")
        self.assertEqual(build_plan("你能做什么")["steps"], [])

    def test_adverse_reaction_event_is_business_not_knowledge(self):
        # 客户正在反馈不良反应属于业务事件（安全优先），走不良反应工单而非政策 RAG
        self.assertEqual(classify_copilot_intent("用了产品过敏发红怎么处理"), "business_query")


class EndToEndChatTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tools = BusinessTools(DB_PATH)
        cls.store = KnowledgeStore(DB_PATH, KNOWLEDGE_DIR)
        cls.store.ensure_index()

    def test_product_question_answered_from_rag(self):
        response = handle_copilot_chat(self.tools, SESSION, "修护精华液怎么使用", knowledge_store=self.store)
        self.assertEqual(response["intent"], "knowledge_query")
        self.assertEqual(response["tools_used"], ["search_knowledge"])
        self.assertIn("2-3 滴", response["message"])
        self.assertIn("参考来源", response["message"])
        self.assertIn("产品知识", response["message"])

    def test_policy_question_answered_from_rag(self):
        response = handle_copilot_chat(self.tools, SESSION, "退货需要满足什么条件", knowledge_store=self.store)
        self.assertEqual(response["intent"], "knowledge_query")
        self.assertEqual(response["tools_used"], ["search_knowledge"])
        self.assertIn("7 天", response["message"])

    def test_order_question_uses_business_tool_not_rag(self):
        response = handle_copilot_chat(self.tools, SESSION, "退款到账了吗", knowledge_store=self.store)
        self.assertEqual(response["intent"], "business_query")
        self.assertEqual(response["tools_used"], ["get_refund_status"])
        self.assertNotIn("参考来源", response["message"])

    def test_empty_knowledge_base_gives_honest_reply(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            empty_store = KnowledgeStore(tmp_path / "empty.sqlite3", tmp_path / "docs")
            (tmp_path / "docs").mkdir()
            empty_store.ensure_index()
            response = handle_copilot_chat(self.tools, SESSION, "某个冷门成分如何使用", knowledge_store=empty_store)
            self.assertEqual(response["intent"], "knowledge_query")
            self.assertIn("暂未找到", response["message"])
            self.assertNotIn("未找到相关业务记录", response["message"])


class RagDoesNotOverrideOrderDataTests(unittest.TestCase):
    """禁止 RAG 覆盖真实订单数据：知识库切片中不得出现任何真实订单号。"""

    def test_no_real_order_numbers_in_knowledge_chunks(self):
        store = KnowledgeStore(DB_PATH, KNOWLEDGE_DIR)
        store.ensure_index()
        with sqlite3.connect(DB_PATH) as conn:
            order_numbers = {row[0] for row in conn.execute("SELECT DISTINCT order_number FROM orders").fetchall()}
        chunks = store.search("订单 物流 退款 工单", top_k=20, score_threshold=-1)
        corpus = "\n".join(c.text for c in chunks)
        leaks = [number for number in order_numbers if number and number in corpus]
        self.assertEqual(leaks, [])


if __name__ == "__main__":
    unittest.main()
