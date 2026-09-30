import sqlite3
import unittest
from pathlib import Path

from app.api import build_risk_detail
from app.business_tools import BusinessTools


class RiskDetailApiTests(unittest.TestCase):
    def test_risk_detail_contains_linked_context_and_timeline(self):
        db = Path(__file__).resolve().parents[1] / "data/beauty_cs_agent.sqlite3"
        with sqlite3.connect(db) as conn:
            buyer = conn.execute("SELECT buyer_nickname FROM chat_messages WHERE buyer_nickname IS NOT NULL LIMIT 1").fetchone()[0]
        detail = build_risk_detail({"id": f"{buyer}:demo", "buyer_nickname": buyer, "level": "high", "reason": "测试风险", "status": "pending", "evidence": {}}, BusinessTools(db))
        self.assertEqual(detail["customer"]["buyer_nickname"], buyer)
        self.assertIn("session_id", detail)
        self.assertIn("orders", detail)
        self.assertIn("work_orders", detail)
        self.assertIn("service_timeline", detail)
        self.assertEqual(detail["current_status"], "pending")


if __name__ == "__main__":
    unittest.main()
