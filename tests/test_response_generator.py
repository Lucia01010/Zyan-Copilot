"""M22 Conversational Response Generation 测试。

验收点：
1. mock provider → 一切行为不变（规则模板兜底）。
2. live provider 闲聊"你好" → LLM 人性化回应，不再是僵硬兜底话术。
3. live provider 业务查询 → LLM 基于证据组织语言；LLM 回复含无依据事实
   （编造的假单号）→ 拦截，回退证据可溯的规则模板。
4. LLM 异常/空内容 → 静默回退规则模板。
5. 多轮记忆：历史轮次（user/reply）进入发给模型的消息。
"""
import os
import tempfile
import unittest
from pathlib import Path

from app.agent_brain import SessionMemory, process_message
from app.action_registry import UNKNOWN_REPLY
from app.business_tools import BusinessTools
from app.context_engine import ContextEngine
from app.conversation_state import ConversationStateMachine
from app.knowledge_base import KnowledgeStore
from app.response_generator import build_chat_messages, generate_conversational_reply

DB_PATH = Path(__file__).resolve().parents[1] / "data/beauty_cs_agent.sqlite3"
KNOWLEDGE_DIR = Path(__file__).resolve().parents[1] / "knowledge"


class StubProvider:
    """模拟 qwen live provider：固定返回或按剧本返回。"""

    mock = False

    def __init__(self, reply="你好呀！我是知妍，很高兴见到你～有什么我可以帮你的吗？", error=None):
        self.reply = reply
        self.error = error
        self.calls = []

    def _request(self, messages, tools, *, response_format=None, stage="chat"):
        self.calls.append({"messages": messages, "stage": stage})
        if self.error:
            raise self.error
        return {"choices": [{"message": {"content": self.reply}}]}


class MockProvider:
    mock = True


class ResponseGeneratorUnitTests(unittest.TestCase):
    def test_mock_provider_returns_none(self):
        self.assertIsNone(generate_conversational_reply(MockProvider(), user_text="你好", intent="unknown"))

    def test_none_provider_returns_none(self):
        self.assertIsNone(generate_conversational_reply(None, user_text="你好", intent="unknown"))

    def test_provider_error_returns_none(self):
        provider = StubProvider(error=RuntimeError("network down"))
        self.assertIsNone(generate_conversational_reply(provider, user_text="你好", intent="unknown"))

    def test_history_included_in_messages(self):
        provider = StubProvider()
        history = [{"user": "退款什么时候到账", "reply": "已查到退款记录，状态为处理中。"}]
        generate_conversational_reply(provider, user_text="那现在呢", intent="unknown", history=history)
        sent = provider.calls[0]["messages"]
        roles = [m["role"] for m in sent]
        self.assertIn("user", roles[:-1])  # 历史 user 在本轮问题之前
        self.assertEqual(sent[-1], {"role": "user", "content": "那现在呢"})
        self.assertTrue(any(m["role"] == "assistant" and "退款记录" in m["content"] for m in sent))

    def test_results_section_marks_not_found(self):
        messages = build_chat_messages(user_text="查退款", results=[{"action_id": "check_refund", "status": "NOT_FOUND", "data": {}}])
        self.assertTrue(any("未查到相关记录" in m["content"] for m in messages if m["role"] == "system"))


class ProcessMessageLiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tools = BusinessTools(DB_PATH)
        cls.engine = ContextEngine(DB_PATH)
        cls.store = KnowledgeStore(DB_PATH, KNOWLEDGE_DIR)
        cls.store.ensure_index()

    def _run(self, text, provider, memory=None):
        # 独立临时状态机库：测试间不共享 conversation_state，杜绝顺序依赖
        fd, state_db = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        try:
            state_machine = ConversationStateMachine(state_db)
            return process_message(self.tools, "S00082", text, knowledge_store=self.store, context_engine=self.engine, memory=memory or SessionMemory(), state_machine=state_machine, llm_provider=provider)
        finally:
            os.unlink(state_db)

    def test_live_greeting_uses_llm_not_stiff_fallback(self):
        result = self._run("你好", StubProvider())
        self.assertEqual(result["intent"], "unknown")
        self.assertNotEqual(result["message"], UNKNOWN_REPLY)
        self.assertIn("知妍", result["message"])

    def test_live_greeting_with_ungrounded_fact_falls_back(self):
        # LLM 编造业务事实（假单号）→ grounding 拦截 → 回退兜底话术
        provider = StubProvider(reply="您的订单 SF1234567890 已经发货了。")
        result = self._run("你好", provider)
        self.assertEqual(result["message"], UNKNOWN_REPLY)

    def test_mock_mode_unchanged(self):
        result = self._run("你好", MockProvider())
        self.assertEqual(result["message"], UNKNOWN_REPLY)

    def test_no_provider_unchanged(self):
        result = process_message(self.tools, "S00082", "你好", knowledge_store=self.store, context_engine=self.engine, memory=SessionMemory())
        self.assertEqual(result["message"], UNKNOWN_REPLY)

    def test_live_business_reply_grounded_adopted(self):
        # LLM 照实复述证据（规则模板前 60 字含真实单号）→ 采纳 LLM 人性化表述
        template = self._run("物流到哪了", MockProvider())["message"]
        grounded_reply = "帮您看过啦，" + template[:60]
        result = self._run("物流到哪了", StubProvider(reply=grounded_reply))
        self.assertEqual(result["message"], grounded_reply)
        self.assertTrue(result["grounding"]["grounded"])

    def test_live_business_reply_with_fabricated_fact_rejected(self):
        # LLM 编造证据中不存在的单号 → 拒绝采用，回退证据可溯的规则模板（mock 基准）
        template = self._run("物流到哪了", MockProvider())["message"]
        result = self._run("物流到哪了", StubProvider(reply="您的快递 SF9988776655 明天送达。"))
        self.assertNotIn("SF9988776655", result["message"])
        self.assertEqual(result["message"], template)
        self.assertTrue(result["grounding"]["grounded"])

    def test_live_memory_written_with_user_and_reply(self):
        memory = SessionMemory()
        self._run("你好", StubProvider(), memory=memory)
        turns = memory.recall("S00082")
        self.assertEqual(turns[0]["user"], "你好")
        self.assertIn("知妍", turns[0]["reply"])

    def test_live_provider_error_falls_back_silently(self):
        result = self._run("你好", StubProvider(error=RuntimeError("timeout")))
        self.assertEqual(result["message"], UNKNOWN_REPLY)

    def test_chitchat_does_not_inherit_but_followup_does(self):
        # 回归：上一轮查物流后，"你好"不得继承（闲聊），"怎么样了"仍继承（追问）
        fd, state_db = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        try:
            sm = ConversationStateMachine(state_db)
            sm.transition("S00082", "processing", "business_query", ["check_logistics"])
            self.assertIsNone(sm.follow_up_action("S00082", "你好"))
            self.assertIsNone(sm.follow_up_action("S00082", "你好呀！"))
            self.assertIsNone(sm.follow_up_action("S00082", "谢谢"))
            self.assertEqual(sm.follow_up_action("S00082", "怎么样了"), "check_logistics")
            self.assertEqual(sm.follow_up_action("S00082", "还没好吗"), "check_logistics")
        finally:
            os.unlink(state_db)


if __name__ == "__main__":
    unittest.main()
