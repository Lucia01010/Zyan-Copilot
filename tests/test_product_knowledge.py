import json
import tempfile
import unittest
import gc
from pathlib import Path

from app.product_knowledge import ProductKnowledge


class ProductKnowledgeTests(unittest.TestCase):
    def test_ingest_is_idempotent_and_preserves_provenance(self):
        root = Path(__file__).resolve().parents[1]
        source = root / "data/raw/产品功能详情.jsonl"
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "catalog.sqlite3"
            catalog = ProductKnowledge(db)
            first = catalog.ingest(source)
            second = catalog.ingest(source)
            self.assertGreater(first["products"], 5000)
            self.assertTrue(second["changed"] is False)
            results = catalog.search("推荐兰蔻敏感肌面膜", top_k=2)
            self.assertTrue(results)
            self.assertIn("source_line", results[0]["metadata"])
            self.assertIn("注意事项", results[0]["text"])
            del catalog
            gc.collect()

    def test_unknown_selection_does_not_invent_product(self):
        with tempfile.TemporaryDirectory() as tmp:
            catalog = ProductKnowledge(Path(tmp) / "catalog.sqlite3")
            catalog.ingest(Path(__file__).resolve().parents[1] / "data/raw/产品功能详情.jsonl")
            results = catalog.search("推荐火星品牌敏感肌面霜", top_k=1)
            self.assertEqual(results[0]["chunk_id"], "product:insufficient")
            del catalog
            gc.collect()


if __name__ == "__main__":
    unittest.main()
