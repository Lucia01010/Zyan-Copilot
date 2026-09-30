import json
import subprocess
import sys
import unittest
from pathlib import Path

from app.evaluation import TokenBudgetGuard


class EvaluationTests(unittest.TestCase):
    def test_token_budget_guard_blocks_before_estimated_overrun(self):
        guard = TokenBudgetGuard(budget=40000, estimate_per_case=15000)
        self.assertTrue(guard.can_start())
        guard.record(10937)
        self.assertTrue(guard.can_start())
        guard.record(15399)
        self.assertFalse(guard.can_start())
        self.assertEqual(guard.remaining, 13664)

    def test_token_budget_guard_allows_started_request_to_record_overrun(self):
        guard = TokenBudgetGuard(budget=100, estimate_per_case=50)
        self.assertTrue(guard.can_start())
        guard.record(120)
        self.assertFalse(guard.can_start())
        self.assertEqual(guard.remaining, 0)

    def test_offline_evaluation_is_structured(self):
        root = Path(__file__).resolve().parents[1]
        output = subprocess.check_output([sys.executable, "scripts/evaluate_mvp.py"], cwd=root, text=True)
        report = json.loads(output)
        self.assertEqual(report["provider"], "mock")
        self.assertIn("risk_counts", report)
        self.assertGreater(report["customers_evaluated"], 0)
        self.assertGreaterEqual(report["input_tokens"], 0)

    def test_m8_dataset_preserves_label_provenance(self):
        root = Path(__file__).resolve().parents[1]
        subprocess.check_call([sys.executable, "scripts/build_m8_evaluation_dataset.py"], cwd=root)
        dataset = json.loads((root / "data/generated/evaluation/m8_dataset.json").read_text(encoding="utf-8"))
        self.assertGreater(len(dataset["records"]), 0)
        provenance = dataset["records"][0]["label_provenance"]
        self.assertIn("source_derived", provenance)
        self.assertEqual(provenance["manually_reviewed"], "unavailable")
        self.assertEqual(provenance["model_generated"], "not_ground_truth")

    def test_manual_gold_candidates_are_blank_and_cover_required_cases(self):
        root = Path(__file__).resolve().parents[1]
        import csv
        for encoding in ("utf-8-sig", "gb18030", "utf-16"):
            try:
                with (root / "data/generated/evaluation/manual_gold_candidates.csv").open(encoding=encoding, newline="") as handle:
                    rows = list(csv.DictReader(handle))
                break
            except (UnicodeDecodeError, UnicodeError):
                continue
        self.assertGreaterEqual(len(rows), 20)
        self.assertLessEqual(len(rows), 30)
        self.assertTrue({"S00082", "S00103", "S00075", "S00003"}.issubset({row["session_id"] for row in rows}))
        self.assertTrue(all(row["human_review_status"].strip().upper() in {"", "DONE", "NEEDS_REVIEW", "TODO"} for row in rows))

    def test_gold_v1_includes_only_done_and_allows_blank_tool_notes(self):
        root = Path(__file__).resolve().parents[1]
        from scripts.build_gold_v1 import build
        gold, counts, errors = build(root / "data/generated/evaluation/manual_gold_candidates.csv")
        self.assertFalse(errors)
        self.assertEqual(counts["DONE"], len(gold))
        self.assertTrue(all(row["human_review_status"] == "DONE" for row in gold))
        self.assertTrue(all("human_required_tools" in row and "human_review_notes" in row for row in gold))

