import tempfile
import unittest
from pathlib import Path

from app.human_feedback import list_feedback, record_feedback


class HumanFeedbackTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db = Path(self._tmp.name) / "feedback.db"

    def tearDown(self):
        self._tmp.cleanup()

    def test_record_and_list_roundtrip(self):
        fid = record_feedback(self.db, "S00082", "AI 建议回复", "人工修订后的回复")
        rows = list_feedback(self.db)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["feedback_id"], fid)
        self.assertEqual(rows[0]["conversation_id"], "S00082")
        self.assertEqual(rows[0]["original_reply"], "AI 建议回复")
        self.assertEqual(rows[0]["edited_reply"], "人工修订后的回复")
        self.assertTrue(rows[0]["created_at"])

    def test_list_filters_by_conversation_and_respects_limit(self):
        record_feedback(self.db, "S00082", "a", "b")
        record_feedback(self.db, "S00002", "c", "d")
        self.assertEqual([r["conversation_id"] for r in list_feedback(self.db, conversation_id="S00082")], ["S00082"])
        self.assertEqual(len(list_feedback(self.db, limit=1)), 1)

    def test_rejects_blank_replies(self):
        with self.assertRaises(ValueError):
            record_feedback(self.db, "S00082", "  ", "b")
        with self.assertRaises(ValueError):
            record_feedback(self.db, "S00082", "a", "")

    def test_table_persists_across_connections(self):
        fid = record_feedback(self.db, None, "x", "y")
        rows = list_feedback(self.db, limit=5)  # 新连接读取，模拟进程重启后仍可审计
        self.assertIn(fid, [r["feedback_id"] for r in rows])


if __name__ == "__main__":
    unittest.main()
