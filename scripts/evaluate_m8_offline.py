"""Offline M8 evaluator: provenance-aware dataset, Rules baseline and mock-only proxy."""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.business_tools import BusinessTools
from app.qwen_agent import BeautyAgent, QwenProvider
from app.risk_engine import assess_context


def main() -> None:
    db = Path("data/beauty_cs_agent.sqlite3")
    dataset_path = Path("data/generated/evaluation/m8_dataset.json")
    if not dataset_path.exists():
        raise SystemExit("run build_m8_evaluation_dataset.py first")
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    tools = BusinessTools(db)
    rules = []
    mock_proxy = []
    for record in dataset["records"]:
        context = tools.get_customer_context(record["buyer_nickname"]) if record["buyer_nickname"] else {"messages": [], "orders": [], "work_orders": []}
        risk = assess_context(context)
        rules.append({"conversation_id": record["conversation_id"], "risk": risk, "label_provenance": "rule_derived"})
        mock_proxy.append({"conversation_id": record["conversation_id"], "provider": "mock", "not_live_qwen": True})
    risk_counts = {level: sum(item["risk"]["level"] == level for item in rules) for level in ("low", "medium", "high", "critical")}
    report = {
        "evaluation_version": "m8.0-offline",
        "dataset": {"records": len(dataset["records"]), "source_label_records": sum(bool(r["source_labels"]["scene_major"] or r["source_labels"]["scene_minor"]) for r in dataset["records"]), "manual_reviewed_labels": "unavailable", "model_generated_labels": "not_ground_truth"},
        "systems": {
            "baseline_a_llm_only": {"status": "not_measurable_without_live_model_run", "tools": False, "ground_truth": "source scene labels do not establish intent/risk truth"},
            "baseline_b_rules": {"status": "measured", "risk_counts": risk_counts, "label_provenance": "rule_derived", "risk_accuracy": "not_reported_without_human_risk_labels"},
            "proposed_agent": {"status": "prepared_not_run", "provider": "mock_available_but_not_used_as_ground_truth", "not_live_qwen": True, "quality_metrics": "not_reported_in_offline_phase"},
        },
        "metrics": {
            "intent_accuracy": "not_measurable_without reviewed intent labels",
            "tool_selection_accuracy": "not_measurable_without case-level required-tool annotations",
            "grounding_rate": "not_run in offline-only evaluator",
            "schema_valid_rate": "not_run for live Qwen in this phase",
            "risk_rule_model_agreement": "not_measurable without comparable model outputs",
            "known_high_risk_proxy_escalation": "available as rule distribution only; not accuracy",
        },
        "case_c_disagreement": {"status": "GOLD_V1_DISAGREEMENT", "human_gold_v1": "HIGH", "rule_baseline": "CRITICAL", "qwen": "MEDIUM", "reason": "Gold v1 human label is formal; preserve model/rule disagreement without forcing a match."},
        "rules_sample": rules[:10],
    }
    output = Path("data/generated/evaluation/m8_offline_report.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
