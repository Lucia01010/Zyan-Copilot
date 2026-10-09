import tempfile
import unittest
from pathlib import Path

from app.qwen_agent import BeautyAgent, QwenProvider
from app.task_state import get_task, list_tasks, record_task, update_task

ROOT = Path(__file__).resolve().parents[1]


class TaskStateUnitTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db = Path(self._tmp.name) / "tasks.db"

    def tearDown(self):
        self._tmp.cleanup()

    def test_record_update_get_roundtrip_merges_business_state(self):
        record_task(self.db, "t1", "C001", "ORD1", "started", {"buyer_nickname": "小李"})
        update_task(self.db, "t1", "context_ready", {"risk_level": "high", "message_count": 9})
        update_task(self.db, "t1", "completed", {"suggestion_chars": 210}, run_id="r1")
        task = get_task(self.db, "t1")
        self.assertEqual(task["execution_state"], "completed")
        self.assertEqual(task["run_id"], "r1")
        self.assertEqual(task["business_state"], {"buyer_nickname": "小李", "risk_level": "high", "message_count": 9, "suggestion_chars": 210})

    def test_failed_state_persists_error(self):
        record_task(self.db, "t2", None, None, "started", {})
        update_task(self.db, "t2", "failed", error="boom: provider timeout")
        task = get_task(self.db, "t2")
        self.assertEqual(task["execution_state"], "failed")
        self.assertIn("boom", task["error"])

    def test_update_rejects_unknown_execution_state(self):
        record_task(self.db, "t3", None, None, "started", {})
        with self.assertRaises(ValueError):
            update_task(self.db, "t3", "flying")

    def test_get_missing_task_returns_none(self):
        self.assertIsNone(get_task(self.db, "nope"))

    def test_list_orders_by_created_and_respects_limit(self):
        for i in range(5):
            record_task(self.db, f"t{i}", None, None, "started", {"i": i})
        tasks = list_tasks(self.db, limit=3)
        self.assertEqual(len(tasks), 3)
        self.assertEqual({t["task_id"] for t in tasks}, {"t4", "t3", "t2"})


class AgentTaskLifecycleTests(unittest.TestCase):
    def test_suggest_records_full_lifecycle_and_task_id(self):
        import sqlite3

        db = ROOT / "data/beauty_cs_agent.sqlite3"
        with sqlite3.connect(db) as conn:
            buyer = conn.execute("SELECT buyer_nickname FROM chat_messages WHERE buyer_nickname IS NOT NULL LIMIT 1").fetchone()[0]
        result = BeautyAgent(db, QwenProvider(mock=True)).suggest(buyer_nickname=buyer)
        self.assertIsNotNone(result.task_id)
        task = get_task(db, result.task_id)
        self.assertEqual(task["execution_state"], "completed")
        self.assertEqual(task["run_id"], result.run_id)
        state = task["business_state"]
        self.assertEqual(state.get("buyer_nickname"), buyer)  # started 阶段
        self.assertIn("risk_level", state)  # context_ready 阶段
        self.assertEqual(state.get("provider"), "mock")  # synthesis_done 阶段
        self.assertGreater(state.get("suggestion_chars", 0), 0)  # completed 阶段
        self.assertIn(result.task_id, [t["task_id"] for t in list_tasks(db, limit=50)])


if __name__ == "__main__":
    unittest.main()
