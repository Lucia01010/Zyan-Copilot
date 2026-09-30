import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.import_excel_to_sqlite import import_workbook


ROOT = Path(__file__).resolve().parents[1]
XLSX = ROOT / "data/raw/赛题 1：数据共情者-业务数据.xlsx"


class ExcelImportTests(unittest.TestCase):
    def test_import_is_repeatable_and_preserves_identifier_text(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db = Path(temp_dir) / "test.sqlite3"
            first = import_workbook(XLSX, db)
            second = import_workbook(XLSX, db)
            self.assertEqual(first["sha256"], second["sha256"])
            conn = sqlite3.connect(db)
            try:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM chat_messages").fetchone()[0], 998)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0], 113)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM import_runs").fetchone()[0], 2)
                identifier = conn.execute("SELECT order_number FROM orders LIMIT 1").fetchone()[0]
                self.assertIsInstance(identifier, str)
                self.assertNotIn("e+", identifier.lower())
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
